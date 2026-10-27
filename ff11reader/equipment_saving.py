"""Equipment reference persistence: encode only domain-approved position fixes."""
from contextlib import ExitStack
from dataclasses import dataclass, asdict
from pathlib import Path
import os
import json
import re
from uuid import uuid4
from .codecs import BAGS, equipsets, inventory
from .domain import Character
from .fixes import plan_fixes
from .saving import digest, patch_equipment, locked_read, atomic_replace, require_game_closed
from .macro_saving import write_json

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
    deferred: int = 0

def prepare_equipment_save(saved, working, folder):
    original=next(c for c in saved.characters if c.folder_id==folder)
    edited=next(c for c in working.characters if c.folder_id==folder)
    allowed={(x.equipset,x.slot):x for x in plan_fixes(original).changes}
    old={e.number:e for e in original.equipsets};grouped={};deferred=0
    for e in edited.equipsets:
        before=old[e.number];deferred+=e.title.display!=before.title.display
        for a,b in zip(before.slots,e.slots):
            values=lambda s:(s.name,s.action,s.item_id,s.container,s.index)
            if values(a)==values(b):continue
            change=allowed.get((e.number,a.name))
            if change is None or values(b)!=(a.name,a.action,a.item_id,*change.after):
                deferred+=1;continue
            grouped.setdefault((e.number-1)//20,[]).append(change)
    if not grouped:raise ValueError('保存できる参照位置の補正がありません。先に補正案を作業データへ適用してください。')
    records={Path(s['path']).resolve():s for s in saved.sources}
    parents={p.parent for p in records if p.parent.name==folder and p.parent.parent.name.upper()=='USER'}
    if len(parents)!=1 or not re.fullmatch('[0-9a-fA-F]+',folder):raise ValueError('保存先を特定できません。')
    parent=parents.pop();required={parent/f'es{page}.dat' for page in grouped}|{parent/name for name in BAGS}
    data={}
    for p in sorted(required):
        if p not in records:raise ValueError('読込元の検証情報が不足しています。')
        raw=p.read_bytes()
        if digest(raw)!=records[p]['sha256']:raise ValueError('ゲームファイルが変わりました。再読み込みしてください。')
        data[p]=raw
    # Validate against binary sources too, before showing a save preview.
    source=Character(folder)
    for page in grouped:source.equipsets.extend(equipsets(data[parent/f'es{page}.dat'],page))
    for name,bag in BAGS.items():
        source.inventory.extend(inventory(data[parent/name],bag));source.inventory_coverage[bag]='loaded'
    valid=plan_fixes(source).changes
    files=[]
    for page,changes in sorted(grouped.items()):
        if any(x not in valid for x in changes):raise ValueError('補正候補が変わりました。再読み込みしてください。')
        target=parent/f'es{page}.dat';raw=data[target]
        files.append(EquipmentFile(str(target),page,raw,patch_equipment(raw,page,changes),tuple(changes)))
    return EquipmentSavePlan(folder,tuple(files),tuple((str(p),digest(raw)) for p,raw in data.items()),deferred)

def execute_equipment_save(plan,backup_root):
    require_game_closed()
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
        if not f.changes or patch_equipment(f.original,f.page,f.changes)!=f.replacement:raise ValueError('保存計画が不正です。')
        if len({(x.equipset,x.slot) for x in f.changes})!=len(f.changes):raise ValueError('変更枠が重複しています。')
    required=targets|{parent/name for name in BAGS}
    if len(plan.dependencies)!=len(required) or {Path(p).resolve() for p,_ in plan.dependencies}!=required:
        raise ValueError('全保存対象と全収納の検証情報が必要です。')
    with ExitStack() as stack:
        handles={};data={}
        for name,expected in plan.dependencies:
            p=Path(name).resolve();handle=ExitStack();stack.enter_context(handle);handles[p]=handle
            raw=handle.enter_context(locked_read(p))
            if digest(raw)!=expected:raise ValueError('プレビュー後にファイルが変わりました。')
            data[p]=raw
        source=Character(plan.character)
        for f in plan.files:
            if data[Path(f.target).resolve()]!=f.original:raise ValueError('保存元が変わりました。')
            source.equipsets.extend(equipsets(f.original,f.page))
        for name,bag in BAGS.items():
            source.inventory.extend(inventory(data[parent/name],bag));source.inventory_coverage[bag]='loaded'
        allowed=plan_fixes(source).changes
        if any(c not in allowed for f in plan.files for c in f.changes):raise ValueError('一意な補正条件を満たしていません。')
        folder=backup_root/uuid4().hex;folder.mkdir(parents=True,exist_ok=False)
        receipt={'kind':'equipment-reference-fix','character':plan.character,'files':[],'dependencies':dict(plan.dependencies)}
        for i,f in enumerate(plan.files):
            filename=f'{i:03}.original.dat'
            with (folder/filename).open('xb') as stream:
                stream.write(f.original);stream.flush();os.fsync(stream.fileno())
            if (folder/filename).read_bytes()!=f.original:raise OSError('バックアップ検証に失敗しました。')
            receipt['files'].append({'target':f.target,'backup':filename,'page':f.page,'before_sha256':digest(f.original),'after_sha256':digest(f.replacement),'changes':[asdict(c) for c in f.changes]})
        write_json(folder/'receipt.json',receipt)
        staged={}
        try:
            for f in plan.files:
                p=Path(f.target);tmp=p.with_name('.ff11-equipment-'+uuid4().hex+'.tmp');staged[p]=tmp
                with tmp.open('xb') as stream:
                    stream.write(f.replacement);stream.flush();os.fsync(stream.fileno())
                if tmp.read_bytes()!=f.replacement:raise OSError('一時ファイルの検証に失敗しました。')
            attempted=[]
            try:
                for f in plan.files:
                    p=Path(f.target);require_game_closed();handles[p.resolve()].close()
                    if p.read_bytes()!=f.original:raise ValueError('置換直前に装備セットが変更されました。')
                    attempted.append(f);os.replace(staged[p],p)
                    if p.read_bytes()!=f.replacement:raise OSError('保存後の内容が一致しません。')
                    equipsets(p.read_bytes(),f.page)
            except Exception as error:
                failed=[]
                for f in reversed(attempted):
                    try:
                        require_game_closed();p=Path(f.target);current=p.read_bytes()
                        if current==f.original:continue
                        if current!=f.replacement:raise ValueError('保存後に別の変更を検出')
                        atomic_replace(p,f.original)
                        if p.read_bytes()!=f.original:raise OSError('復元後の内容が不一致')
                    except Exception as rollback_error:failed.append(str(rollback_error))
                write_json(folder/'failure.json',{'error':str(error),'rollback_errors':failed})
                raise RuntimeError(f'保存を中止しました。復元確認: {"要確認" if failed else "完了"}。バックアップ: {folder}') from error
            write_json(folder/'verified.json',{'files':len(plan.files),'status':'verified'})
            return folder
        finally:
            for tmp in staged.values():tmp.unlink(missing_ok=True)


def restore_equipment_backup(folder,apply=False):
    """Validate a complete backup set; retry safely after an interrupted restore."""
    folder=Path(folder).resolve();receipt=json.loads((folder/'receipt.json').read_text(encoding='utf-8'))
    if receipt.get('kind')!='equipment-reference-fix' or not receipt.get('files'):raise ValueError('装備セットのバックアップを指定してください。')
    entries=[];seen=set();root=None
    for entry in receipt['files']:
        target=Path(entry['target']).resolve();page=entry['page']
        if not isinstance(page,int) or not 0<=page<10:raise ValueError('バックアップのファイル番号が不正です。')
        name=f'es{page}.dat'
        if target.name!=name or target.parent.name!=receipt['character'] or target.parent.parent.name.upper()!='USER':raise ValueError('復元先が不正です。')
        if root is None:root=target.parent.parent.parent
        if target.parent.parent.parent!=root or target in seen:raise ValueError('復元先が重複または複数のインストール先にあります。')
        seen.add(target)
        backup=(folder/entry['backup']).resolve()
        if backup.parent!=folder:raise ValueError('バックアップのパスが不正です。')
        raw=backup.read_bytes()
        if digest(raw)!=entry['before_sha256']:raise ValueError('バックアップが破損しています。')
        equipsets(raw,page)
        if digest(target.read_bytes()) not in (entry['before_sha256'],entry['after_sha256']):raise ValueError('保存後に別の変更があり、復元を保留しました。')
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
