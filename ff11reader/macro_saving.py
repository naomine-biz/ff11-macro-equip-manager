"""Guarded macro storage-number persistence. Preserve original text/token bytes."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import re
import os
from uuid import uuid4
from .codecs import checked, macros, BAGS
from .domain import Text
from .editing import macro_key
from .macro_inventory import assess_macro_inventory, parse_equip
from .saving import digest, locked_read, atomic_replace, require_game_closed


@dataclass(frozen=True)
class LineChange:
    address: tuple
    line: int
    before: str
    after: str
    original: bytes
    replacement: bytes


@dataclass(frozen=True)
class MacroFile:
    target: str
    page: int
    original: bytes
    replacement: bytes
    changes: tuple


@dataclass(frozen=True)
class MacroSavePlan:
    character: str
    files: tuple
    dependencies: tuple
    deferred: int = 0


def patch_line(raw, before, after, resolver):
    """Map displayed character boundaries back to original bytes, including ATs."""
    if len(raw)!=61:raise ValueError('マクロ行のサイズが不正です。')
    displayed=''; boundaries=[0]; index=0
    while index<len(raw) and raw[index]:
        if raw[index]==0xFD and index+5<len(raw) and raw[index+5]==0xFD:
            name=resolver(raw[index+1:index+5])
            if name is None:raise ValueError('定型文を解決できません。')
            segment='【'+name+'】';index+=6
        else:
            byte=raw[index];size=2 if 0x81<=byte<=0x9f or 0xe0<=byte<=0xfc else 1
            segment=raw[index:index+size].decode('cp932',errors='strict');index+=size
        displayed+=segment
        boundaries.extend([None]*(len(segment)-1)+[index])
    if displayed!=before or index>=61:raise ValueError('マクロの元バイトと表示が一致しません。')
    command=parse_equip(before);new=parse_equip(after)
    if not command or not new or not command.valid or not new.valid or new.storage is None:
        raise ValueError('収納番号Fixの形式を確認してください。')
    start,end=command.storage_span or (command.item_end,command.item_end)
    inserted=str(new.storage) if command.storage_span else ' '+str(new.storage)
    if before[:start]+inserted+before[end:]!=after:raise ValueError('収納番号以外の変更が含まれています。')
    left,right=boundaries[start],boundaries[end]
    if left is None or right is None:raise ValueError('定型文の内部を変更することはできません。')
    payload=raw[:left]+inserted.encode('ascii')+raw[right:index]
    if len(payload)>60:raise ValueError('収納番号を追加するとマクロ行の60バイト上限を超えます。')
    # Keep the unused trailing bytes; only the new content and NUL are written.
    out=bytearray(raw);out[:len(payload)+1]=payload+b'\0'
    return bytes(out)


def patch_file(original,page,changes):
    checked(original,7624);out=bytearray(original);seen=set()
    for change in changes:
        book,palette,bank,key=change.address
        if (book-1)*10+palette-1!=page or bank not in ('ctrl','alt') or not 1<=key<=10 or not 1<=change.line<=6:
            raise ValueError('マクロの保存位置が不正です。')
        identity=(change.address,change.line)
        if identity in seen:raise ValueError('保存位置が重複しています。')
        seen.add(identity)
        offset=24+((0 if bank=='ctrl' else 10)+key-1)*380+4+(change.line-1)*61
        if original[offset:offset+61]!=change.original or len(change.replacement)!=61:
            raise ValueError('元のマクロ行が変わっています。')
        out[offset:offset+61]=change.replacement
    out[8:24]=hashlib.md5(out[24:]).digest()
    macros(bytes(out),page)
    return bytes(out)


def prepare_macro_save(saved,working,folder):
    from .adapters import LocalReader
    from .dictionaries import resolve_token
    original=next(c for c in saved.characters if c.folder_id==folder)
    edited=next(c for c in working.characters if c.folder_id==folder)
    records={Path(s['path']).resolve():s for s in saved.sources}
    parent=next((p.parent for p in records if p.parent.name==folder and p.parent.parent.name.upper()=='USER'),None)
    if parent is None or not re.fullmatch('[0-9a-fA-F]+',folder):raise ValueError('キャラクターの保存先を確認してください。')
    root=parent.parent.parent
    reader=LocalReader(root);phrases=reader.load_phrases()
    resolver=lambda token:resolve_token(token,phrases,saved.items)
    for source in reader.sources:
        p=Path(source['path']).resolve()
        if p not in records or source['sha256']!=records[p]['sha256']:raise ValueError('定型文データが変わりました。再読み込みしてください。')
    refs={(r.address,r.line):r for r in assess_macro_inventory(original,saved.items)}
    old={macro_key(m):m for m in original.macros};grouped={};deferred=0
    for macro in edited.macros:
        key=macro_key(macro);before=old[key]
        deferred+=before.title.display!=macro.title.display
        for n,(a,b) in enumerate(zip(before.lines,macro.lines),1):
            if a.display==b.display:continue
            ref=refs.get((key,n))
            if ref is None or ref.replacement is None or ref.replacement!=b.display:
                deferred+=1;continue
            raw=bytes.fromhex(a.raw_hex)
            try:replacement=patch_line(raw,a.display,b.display,resolver)
            except ValueError as exc:
                raise ValueError(f'ブック {macro.book:02} / パレット {macro.palette} / {macro.bank.upper()} {macro.key if macro.key<10 else 0} / {n}行目: {exc}') from exc
            page=(macro.book-1)*10+macro.palette-1
            grouped.setdefault(page,[]).append(LineChange(key,n,a.display,b.display,raw,replacement))
    if not grouped:raise ValueError('保存できる収納番号Fixがありません。先にFixを作業データへ適用してください。')
    files=[]
    for page,changes in sorted(grouped.items()):
        target=parent/('mcr'+(str(page) if page else '')+'.dat')
        if target not in records:raise ValueError('読込元のマクロファイルが見つかりません。')
        raw=target.read_bytes()
        if digest(raw)!=records[target]['sha256']:raise ValueError('マクロが変更されています。再読み込みしてください。')
        files.append(MacroFile(str(target),page,raw,patch_file(raw,page,changes),tuple(changes)))
    required={Path(f.target) for f in files}|{parent/name for name in BAGS}
    # Item/phrase dictionaries are part of name-to-ID verification.
    required.update(p for p in records if not p.is_relative_to(root/'USER'))
    dependencies=[]
    for p in sorted(required):
        raw=p.read_bytes()
        if p not in records or digest(raw)!=records[p]['sha256']:raise ValueError('読込元が変更されています。再読み込みしてください。')
        dependencies.append((str(p),digest(raw)))
    return MacroSavePlan(folder,tuple(files),tuple(dependencies),deferred)


def write_json(path,value):
    with path.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())


def execute_macro_save(plan,backup_root):
    from .application import load_snapshot
    require_game_closed()
    if not plan.files:raise ValueError('保存対象がありません。')
    root=Path(plan.files[0].target).resolve().parent.parent.parent
    backup_root=Path(backup_root).resolve()
    if backup_root.is_relative_to(root):raise ValueError('バックアップ先はゲームフォルダの外に指定してください。')
    targets={Path(f.target).resolve() for f in plan.files}
    if len(targets)!=len(plan.files):raise ValueError('保存先が重複しています。')
    for f in plan.files:
        p=Path(f.target).resolve()
        expected=root/'USER'/plan.character/('mcr'+(str(f.page) if f.page else '')+'.dat')
        if p!=expected or not 0<=f.page<400:raise ValueError('保存先が不正です。')
    with ExitStack() as stack:
        handles={};seen=set()
        for name,expected in plan.dependencies:
            p=Path(name).resolve()
            if p in seen or not p.is_relative_to(root):raise ValueError('検証対象が不正です。')
            seen.add(p)
            handle=ExitStack();stack.enter_context(handle);handles[p]=handle
            if digest(handle.enter_context(locked_read(p)))!=expected:raise ValueError('プレビュー後にファイルが変わりました。')
        # Rebuild the domain proposal from the locked game data.
        fresh=load_snapshot(root);proposed=deepcopy(fresh)
        character=next(c for c in proposed.characters if c.folder_id==plan.character)
        changes={(change.address,change.line):change for f in plan.files for change in f.changes}
        character.macros=[replace(m,lines=tuple(Text(changes[(macro_key(m),n)].after,'','draft') if (macro_key(m),n) in changes else line for n,line in enumerate(m.lines,1))) for m in character.macros]
        verified=prepare_macro_save(fresh,proposed,plan.character)
        if verified.files!=plan.files or verified.dependencies!=plan.dependencies:raise ValueError('保存計画が現在のFix案と一致しません。')
        folder=backup_root/uuid4().hex;folder.mkdir(parents=True,exist_ok=False)
        receipt={'kind':'macro-storage-fix','character':plan.character,'files':[],'dependencies':dict(plan.dependencies)}
        for i,f in enumerate(plan.files):
            filename=f'{i:03}.original.dat'
            with (folder/filename).open('xb') as stream:
                stream.write(f.original);stream.flush();os.fsync(stream.fileno())
            if (folder/filename).read_bytes()!=f.original:raise OSError('バックアップ検証に失敗しました。')
            receipt['files'].append({'target':f.target,'backup':filename,'page':f.page,'before_sha256':digest(f.original),'after_sha256':digest(f.replacement),
                                     'changes':[{'address':c.address,'line':c.line,'before':c.before,'after':c.after} for c in f.changes]})
        write_json(folder/'receipt.json',receipt)
        # Create every staged file before changing any target (permission/space preflight).
        staged={}
        try:
            for f in plan.files:
                p=Path(f.target);tmp=p.with_name('.ff11-macro-'+uuid4().hex+'.tmp');staged[p]=tmp
                with tmp.open('xb') as stream:
                    stream.write(f.replacement);stream.flush();os.fsync(stream.fileno())
                if tmp.read_bytes()!=f.replacement:raise OSError('保存用一時ファイルの検証に失敗しました。')
            require_game_closed()
            attempted=[]
            try:
                for f in plan.files:
                    p=Path(f.target);require_game_closed();handles[p].close()
                    if p.read_bytes()!=f.original:raise ValueError('置換直前にマクロが変更されました。')
                    attempted.append(f);os.replace(staged[p],p)
                    if p.read_bytes()!=f.replacement:raise OSError('保存後の内容が一致しません。')
                    macros(p.read_bytes(),f.page)
            except Exception as error:
                failed=[]
                for f in reversed(attempted):
                    try:
                        require_game_closed()
                        p=Path(f.target);current=p.read_bytes()
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


def restore_macro_backup(folder,apply=False):
    """Validate a complete backup set; retry safely after an interrupted restore."""
    folder=Path(folder).resolve();receipt=json.loads((folder/'receipt.json').read_text(encoding='utf-8'))
    if receipt.get('kind')!='macro-storage-fix' or not receipt.get('files'):raise ValueError('マクロのバックアップを指定してください。')
    entries=[];seen=set();root=None
    for entry in receipt['files']:
        target=Path(entry['target']).resolve();page=entry['page']
        if not isinstance(page,int) or not 0<=page<400:raise ValueError('バックアップのパレット番号が不正です。')
        name='mcr'+(str(page) if page else '')+'.dat'
        if target.name!=name or target.parent.name!=receipt['character'] or target.parent.parent.name.upper()!='USER':raise ValueError('復元先が不正です。')
        if root is None:root=target.parent.parent.parent
        if target.parent.parent.parent!=root or target in seen:raise ValueError('復元先が重複または複数のインストール先にあります。')
        seen.add(target)
        backup=(folder/entry['backup']).resolve()
        if backup.parent!=folder:raise ValueError('バックアップのパスが不正です。')
        raw=backup.read_bytes()
        if digest(raw)!=entry['before_sha256']:raise ValueError('バックアップが破損しています。')
        macros(raw,page)
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
