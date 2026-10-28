"""Shared guarded file transaction; no macro/equipment candidate rules."""
from contextlib import ExitStack
from pathlib import Path
from uuid import uuid4
import json
import os
from .saving import digest, locked_read

def write_json(path,value):
    with path.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())


def execute_batch(plan, backup_root, root, validate, decode, kind, prefix, serialize,
                  require_closed, write_record, restore):
    require_closed()
    root=Path(root).resolve();backup_root=Path(backup_root).resolve()
    if backup_root.is_relative_to(root):raise ValueError('バックアップ先はゲームフォルダの外に指定してください。')
    targets={Path(f.target).resolve() for f in plan.files}
    if not targets or len(targets)!=len(plan.files):raise ValueError('保存先が空または重複しています。')
    with ExitStack() as stack:
        handles={};data={}
        for name,expected in plan.dependencies:
            p=Path(name).resolve()
            if p in data or not p.is_relative_to(root):raise ValueError('検証対象が不正です。')
            handle=ExitStack();stack.enter_context(handle);handles[p]=handle
            raw=handle.enter_context(locked_read(p))
            if digest(raw)!=expected:raise ValueError('プレビュー後にファイルが変わりました。')
            data[p]=raw
        if not targets.issubset(data):raise ValueError('保存対象の検証情報が不足しています。')
        for f in plan.files:
            if data[Path(f.target).resolve()]!=f.original:raise ValueError('保存元が変わりました。')
        validate(data)
        folder=backup_root/uuid4().hex;folder.mkdir(parents=True,exist_ok=False)
        receipt={'kind':kind,'character':plan.character,'files':[],'dependencies':dict(plan.dependencies)}
        for i,f in enumerate(plan.files):
            filename=f'{i:03}.original.dat'
            with (folder/filename).open('xb') as stream:
                stream.write(f.original);stream.flush();os.fsync(stream.fileno())
            if (folder/filename).read_bytes()!=f.original:raise OSError('バックアップ検証に失敗しました。')
            receipt['files'].append({'target':f.target,'backup':filename,'page':f.page,'before_sha256':digest(f.original),'after_sha256':digest(f.replacement),'changes':[serialize(c) for c in f.changes]})
        write_record(folder/'receipt.json',receipt)
        staged={}
        try:
            for f in plan.files:
                p=Path(f.target);tmp=p.with_name(prefix+uuid4().hex+'.tmp');staged[p]=tmp
                with tmp.open('xb') as stream:
                    stream.write(f.replacement);stream.flush();os.fsync(stream.fileno())
                if tmp.read_bytes()!=f.replacement:raise OSError('一時ファイルの検証に失敗しました。')
            attempted=[]
            try:
                for f in plan.files:
                    p=Path(f.target);require_closed();handles[p.resolve()].close()
                    if p.read_bytes()!=f.original:raise ValueError('置換直前に保存元が変更されました。')
                    attempted.append(f);os.replace(staged[p],p)
                    if p.read_bytes()!=f.replacement:raise OSError('保存後の内容が一致しません。')
                    decode(p.read_bytes(),f.page)
            except Exception as error:
                failed=[]
                for f in reversed(attempted):
                    try:
                        require_closed();p=Path(f.target);current=p.read_bytes()
                        if current==f.original:continue
                        if current!=f.replacement:raise ValueError('保存後に別の変更を検出')
                        restore(p,f.original)
                        if p.read_bytes()!=f.original:raise OSError('復元後の内容が不一致')
                    except Exception as rollback_error:failed.append(str(rollback_error))
                write_record(folder/'failure.json',{'error':str(error),'rollback_errors':failed})
                raise RuntimeError(f'保存を中止しました。復元確認: {"要確認" if failed else "完了"}。バックアップ: {folder}') from error
            write_record(folder/'verified.json',{'files':len(plan.files),'status':'verified'})
            return folder
        finally:
            for tmp in staged.values():tmp.unlink(missing_ok=True)
