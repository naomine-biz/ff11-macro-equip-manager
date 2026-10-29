"""Equipment names and domain-approved position fixes, with guarded persistence."""
from contextlib import ExitStack
from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import os
import json
import re
from uuid import uuid4
from .codecs import BAGS, equipsets, inventory, text
from .domain import Character
from .fixes import plan_fixes, FixChange
from .saving import digest, patch_equipment, locked_read, atomic_replace, require_game_closed
from .file_transaction import execute_batch, write_json
from .save_plan import DeferredChange, deferred_text, require_same_targets

@dataclass(frozen=True)
class EquipmentNameChange:
    equipset: int
    before: str
    after: str


def patch_name(raw,before,after):
    if len(raw)!=16 or text(raw).display!=before:raise ValueError('装備セット名の原本が一致しません。')
    if before==after:return raw
    if not isinstance(after,str) or any(ord(c)<32 or ord(c)==127 for c in after):raise ValueError('装備セット名に制御文字を含めることはできません。')
    from .macro_text import TOKEN_DISPLAY
    if TOKEN_DISPLAY.search(after) or any(c in after for c in ('【','】')):raise ValueError('装備セット名への定型文入力は未対応です。')
    try:encoded=after.encode('cp932',errors='strict')
    except UnicodeError as exc:raise ValueError('装備セット名にCP932で保存できない文字があります。') from exc
    if len(encoded)>16:raise ValueError(f'装備セット名は16バイト以内です（{len(encoded)}バイト）。')
    out=bytearray(raw);out[:len(encoded)]=encoded
    if len(encoded)<16:out[len(encoded)]=0
    if text(bytes(out)).display!=after:raise ValueError('保存後に装備セット名が変わります。')
    return bytes(out)


def patch_file(raw,page,changes):
    if not changes or any(type(c) not in (FixChange,EquipmentNameChange) for c in changes):raise ValueError('保存変更の種類が不正です。')
    fixes=tuple(c for c in changes if isinstance(c,FixChange))
    names=tuple(c for c in changes if isinstance(c,EquipmentNameChange))
    if len({c.equipset for c in names})!=len(names):raise ValueError('名前変更が重複しています。')
    decoded={e.number:e for e in equipsets(raw,page)}
    out=bytearray(patch_equipment(raw,page,fixes))
    for change in names:
        if change.equipset not in decoded:raise ValueError('名前変更の対象が不正です。')
        offset=24+(change.equipset-1)%20*80
        out[offset:offset+16]=patch_name(raw[offset:offset+16],change.before,change.after)
    out[8:24]=hashlib.md5(out[24:]).digest()
    return bytes(out)


@dataclass(frozen=True)
class EquipmentFile:
    target: str
    page: int
    original: bytes
    replacement: bytes
    changes: tuple

@dataclass(frozen=True)
class EquipmentSavePlan:
    character: str
    files: tuple
    dependencies: tuple
    deferred_changes: tuple = ()
    scope: str = 'reference-fix'

    @property
    def deferred(self):return len(self.deferred_changes)

def prepare_equipment_save(saved, working, folder, scope='reference-fix'):
    if scope not in ('reference-fix','all'):raise ValueError('保存範囲が不正です。')
    original=next(c for c in saved.characters if c.folder_id==folder)
    edited=next(c for c in working.characters if c.folder_id==folder)
    require_same_targets(original,edited)
    allowed={(x.equipset,x.slot):x for x in plan_fixes(original).changes}
    old={e.number:e for e in original.equipsets};grouped={};deferred=[]
    for e in edited.equipsets:
        before=old[e.number]
        address=f'装備セット {e.number:03} {e.title.display}'
        if e.title.display!=before.title.display:
            if scope=='all':grouped.setdefault((e.number-1)//20,[]).append(EquipmentNameChange(e.number,before.title.display,e.title.display))
            else:deferred.append(DeferredChange(address+' / 名前','名前の変更は装備セットの編集保存から保存できます。'))
        for a,b in zip(before.slots,e.slots):
            values=lambda s:(s.name,s.action,s.item_id,s.container,s.index)
            if values(a)==values(b):continue
            change=allowed.get((e.number,a.name))
            if change is None or values(b)!=(a.name,a.action,a.item_id,*change.after):
                deferred.append(DeferredChange(address+' / '+a.name,'この枠は自動補正の保存対象外です。現在保存できるのは、同じ種類IDの候補が1つに決まる位置の補正です。'));continue
            grouped.setdefault((e.number-1)//20,[]).append(change)
    if not grouped:raise ValueError('保存できる装備セットの変更がありません。先に変更案を作業データへ適用してください。'+('\n'+deferred_text(deferred) if deferred else ''))
    records={Path(s['path']).resolve():s for s in saved.sources}
    parents={p.parent for p in records if p.parent.name==folder and p.parent.parent.name.upper()=='USER'}
    if len(parents)!=1 or not re.fullmatch('[0-9a-fA-F]+',folder):raise ValueError('保存先を特定できません。')
    parent=parents.pop();required={parent/f'es{page}.dat' for page in grouped}
    has_fixes=any(isinstance(c,FixChange) for changes in grouped.values() for c in changes)
    if has_fixes:required.update(parent/name for name in BAGS)
    data={}
    for p in sorted(required):
        if p not in records:raise ValueError('読込元の検証情報が不足しています。')
        raw=p.read_bytes()
        if digest(raw)!=records[p]['sha256']:raise ValueError('ゲームファイルが変わりました。再読み込みしてください。')
        data[p]=raw
    # Validate against binary sources too, before showing a save preview.
    source=Character(folder)
    for page in grouped:source.equipsets.extend(equipsets(data[parent/f'es{page}.dat'],page))
    if has_fixes:
        for name,bag in BAGS.items():
            source.inventory.extend(inventory(data[parent/name],bag));source.inventory_coverage[bag]='loaded'
    valid=plan_fixes(source).changes
    files=[]
    for page,changes in sorted(grouped.items()):
        if any(isinstance(x,FixChange) and x not in valid for x in changes):raise ValueError('補正候補が変わりました。再読み込みしてください。')
        target=parent/f'es{page}.dat';raw=data[target]
        files.append(EquipmentFile(str(target),page,raw,patch_file(raw,page,changes),tuple(changes)))
    return EquipmentSavePlan(folder,tuple(files),tuple((str(p),digest(raw)) for p,raw in data.items()),tuple(deferred),scope)

def execute_equipment_save(plan,backup_root):
    require_game_closed()
    if plan.scope not in ('reference-fix','all'):raise ValueError('保存範囲が不正です。')
    if plan.scope!='all' and any(isinstance(c,EquipmentNameChange) for f in plan.files for c in f.changes):raise ValueError('名前変更の保存範囲が不正です。')
    if not plan.files:raise ValueError('保存対象がありません。')
    root=Path(plan.files[0].target).resolve().parent.parent.parent
    backup_root=Path(backup_root).resolve()
    if backup_root.is_relative_to(root):raise ValueError('バックアップ先はゲームフォルダの外に指定してください。')
    targets={Path(f.target).resolve() for f in plan.files}
    if len(targets)!=len(plan.files):raise ValueError('保存先が重複しています。')
    if not re.fullmatch('[0-9a-fA-F]+',plan.character):raise ValueError('キャラクターIDが不正です。')
    parent=root/'USER'/plan.character
    for f in plan.files:
        if Path(f.target).resolve()!=parent/f'es{f.page}.dat' or not 0<=f.page<10:raise ValueError('保存先が不正です。')
        if not f.changes or patch_file(f.original,f.page,f.changes)!=f.replacement:raise ValueError('保存計画が不正です。')
        fixes=[x for x in f.changes if isinstance(x,FixChange)]
        if len({(x.equipset,x.slot) for x in fixes})!=len(fixes):raise ValueError('変更枠が重複しています。')
    has_fixes=any(isinstance(c,FixChange) for f in plan.files for c in f.changes)
    required=targets|({parent/name for name in BAGS} if has_fixes else set())
    if len(plan.dependencies)!=len(required) or {Path(p).resolve() for p,_ in plan.dependencies}!=required:
        raise ValueError('保存対象と補正に必要な収納の検証情報が必要です。')
    def validate(data):
        source=Character(plan.character)
        for f in plan.files:
            if data[Path(f.target).resolve()]!=f.original:raise ValueError('保存元が変わりました。')
            source.equipsets.extend(equipsets(f.original,f.page))
        if has_fixes:
            for name,bag in BAGS.items():
                source.inventory.extend(inventory(data[parent/name],bag));source.inventory_coverage[bag]='loaded'
        allowed=plan_fixes(source).changes
        if any(isinstance(c,FixChange) and c not in allowed for f in plan.files for c in f.changes):raise ValueError('一意な補正条件を満たしていません。')
    return execute_batch(plan,backup_root,root,validate,equipsets,'equipment-edit' if plan.scope=='all' else 'equipment-reference-fix','.ff11-equipment-',
                         asdict,require_game_closed,write_json,atomic_replace)


def restore_equipment_backup(folder,apply=False):
    """Validate a complete backup set; retry safely after an interrupted restore."""
    folder=Path(folder).resolve();receipt=json.loads((folder/'receipt.json').read_text(encoding='utf-8'))
    if receipt.get('kind') not in ('equipment-reference-fix','equipment-edit') or not receipt.get('files'):raise ValueError('装備セットのバックアップを指定してください。')
    entries=[];seen=set();root=None
    for entry in receipt['files']:
        target=Path(entry['target']).resolve();page=entry['page']
        if not isinstance(page,int) or not 0<=page<10:raise ValueError('バックアップのファイル番号が不正です。')
        name=f'es{page}.dat'
        if target.name!=name or target.parent.name!=receipt['character'] or target.parent.parent.name.upper()!='USER':raise ValueError('復元先が不正です。')
        if root is None:root=target.parent.parent.parent
        if target.parent.parent.parent!=root or target in seen:raise ValueError('復元先に重複があるか、異なるインストール先のファイルが含まれています。')
        seen.add(target)
        backup=(folder/entry['backup']).resolve()
        if backup.parent!=folder:raise ValueError('バックアップのパスが不正です。')
        raw=backup.read_bytes()
        if digest(raw)!=entry['before_sha256']:raise ValueError('バックアップが破損しています。')
        equipsets(raw,page)
        if digest(target.read_bytes()) not in (entry['before_sha256'],entry['after_sha256']):raise ValueError('保存後にファイルが変更されたため、復元を保留しました。')
        entries.append((target,raw,entry))
    if not apply:return tuple(str(p) for p,_,_ in entries)
    require_game_closed()
    with ExitStack() as stack:
        locks={}
        for target,raw,entry in entries:
            handle=ExitStack();stack.enter_context(handle);locks[target]=handle
            current=handle.enter_context(locked_read(target))
            if digest(current) not in (entry['before_sha256'],entry['after_sha256']):raise ValueError('復元前にファイルが変わりました。')
        for target,raw,entry in entries:
            require_game_closed();locks[target].close()
            if digest(target.read_bytes()) not in (entry['before_sha256'],entry['after_sha256']):raise ValueError('置換直前にファイルが変わりました。')
            atomic_replace(target,raw)
            if target.read_bytes()!=raw:raise OSError('復元後検証に失敗しました。')
    return tuple(str(p) for p,_,_ in entries)
