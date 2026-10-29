"""On-demand Windows elevation for an already reviewed save plan."""
from dataclasses import fields, is_dataclass
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
from uuid import uuid4


def _types():
    from .macro_saving import MacroSavePlan, MacroFile, LineChange
    from .equipment_saving import EquipmentSavePlan, EquipmentFile
    from .fixes import FixChange
    from .domain import TextToken
    from .save_plan import DeferredChange
    return {c.__name__:c for c in (MacroSavePlan,MacroFile,LineChange,EquipmentSavePlan,EquipmentFile,FixChange,TextToken,DeferredChange)}


def encode(value):
    if is_dataclass(value):
        if type(value).__name__ not in _types():raise ValueError('保存要求の型が不正です。')
        return {'type':type(value).__name__,'fields':{f.name:encode(getattr(value,f.name)) for f in fields(value)}}
    if isinstance(value,bytes):return {'bytes':value.hex()}
    if isinstance(value,tuple):return {'tuple':[encode(v) for v in value]}
    if value is None or type(value) in (str,int,bool):return value
    raise ValueError('保存要求の値が不正です。')


def decode(value):
    if isinstance(value,dict):
        if set(value)=={'bytes'}:return bytes.fromhex(value['bytes'])
        if set(value)=={'tuple'}:return tuple(decode(v) for v in value['tuple'])
        if set(value)=={'type','fields'}:
            cls=_types().get(value['type'])
            if cls is None:raise ValueError('保存要求の型が不正です。')
            return cls(**{k:decode(v) for k,v in value['fields'].items()})
        raise ValueError('保存要求が不正です。')
    if value is None or type(value) in (str,int,bool):return value
    raise ValueError('保存要求の値が不正です。')


def execute_request(request, expected_hash):
    """Helper entry: read once, authenticate reviewed bytes, then revalidate on disk."""
    raw=Path(request).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_hash:raise ValueError('保存要求が変更されました。プレビューを開き直してください。')
    data=json.loads(raw)
    if set(data)!={'version','plan','backup_root'} or data['version']!=1:raise ValueError('保存要求の形式が不正です。')
    plan=decode(data['plan'])
    from .macro_saving import MacroSavePlan, execute_macro_save
    from .equipment_saving import EquipmentSavePlan, execute_equipment_save
    executors={MacroSavePlan:execute_macro_save,EquipmentSavePlan:execute_equipment_save}
    if type(plan) not in executors:raise ValueError('保存要求の種類が不正です。')
    return executors[type(plan)](plan,Path(data['backup_root']))


def launch_elevated(request, digest):
    """Wait for one elevated helper; never relaunch the editing application."""
    import ctypes
    from ctypes import wintypes as w
    class ShellInfo(ctypes.Structure):
        _fields_=[('cbSize',w.DWORD),('fMask',w.ULONG),('hwnd',w.HWND),('lpVerb',w.LPCWSTR),
                  ('lpFile',w.LPCWSTR),('lpParameters',w.LPCWSTR),('lpDirectory',w.LPCWSTR),
                  ('nShow',ctypes.c_int),('hInstApp',w.HINSTANCE),('lpIDList',ctypes.c_void_p),
                  ('lpClass',w.LPCWSTR),('hkeyClass',w.HKEY),('dwHotKey',w.DWORD),
                  ('hIcon',w.HANDLE),('hProcess',w.HANDLE)]
    shell=ctypes.WinDLL('shell32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    shell.ShellExecuteExW.argtypes=[ctypes.POINTER(ShellInfo)];shell.ShellExecuteExW.restype=w.BOOL
    kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];kernel.WaitForSingleObject.restype=w.DWORD
    kernel.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)];kernel.GetExitCodeProcess.restype=w.BOOL
    kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
    script=Path(__file__).resolve().parents[1]/'save_helper.py'
    args=subprocess.list2cmdline(['-I','-B',str(script),str(request),digest])
    info=ShellInfo();info.cbSize=ctypes.sizeof(info);info.fMask=0x40|0x100;info.lpVerb='runas'
    info.lpFile=sys.executable;info.lpParameters=args;info.lpDirectory=str(script.parent);info.nShow=0
    if not shell.ShellExecuteExW(ctypes.byref(info)):
        error=ctypes.get_last_error()
        if error==1223:raise RuntimeError('管理者確認を取り消しました。編集内容は残っています。保存ボタンから再試行できます。')
        raise OSError(error,'管理者権限の保存処理を開始できませんでした。')
    try:
        if kernel.WaitForSingleObject(info.hProcess,0xFFFFFFFF)!=0:raise RuntimeError('保存処理の終了を確認できませんでした。')
        code=w.DWORD()
        if not kernel.GetExitCodeProcess(info.hProcess,ctypes.byref(code)):raise RuntimeError('保存結果を確認できませんでした。')
        return code.value
    finally:kernel.CloseHandle(info.hProcess)


def execute_with_permission(plan,backup_root,execute):
    try:return execute(plan,backup_root)
    except PermissionError:
        if os.name!='nt':raise
        # Retrying is only safe before any source has changed.
        if not all(Path(f.target).read_bytes()==f.original for f in plan.files):raise
    root=Path(backup_root).resolve();root.mkdir(parents=True,exist_ok=True)
    request=root/('save-request-'+uuid4().hex+'.json')
    result=request.with_suffix('.result.json')
    raw=json.dumps({'version':1,'plan':encode(plan),'backup_root':str(root)},ensure_ascii=False).encode('utf-8')
    try:
        with request.open('xb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        exit_code=launch_elevated(request,hashlib.sha256(raw).hexdigest())
        if not result.exists():raise RuntimeError('保存処理から結果が届きませんでした。復旧記録を確認してください。')
        response=json.loads(result.read_text(encoding='utf-8'))
        if exit_code!=0 or response.get('status')!='verified':
            raise RuntimeError(response.get('error','管理者権限での保存に失敗しました。'))
        backup=Path(response['backup']).resolve()
        if backup.parent!=root or not (backup/'verified.json').is_file():raise RuntimeError('保存完了記録を確認できませんでした。')
        receipt=json.loads((backup/'receipt.json').read_text(encoding='utf-8'))
        if {f['target'] for f in receipt['files']}!={f.target for f in plan.files}:raise RuntimeError('バックアップ対象が一致しません。')
        for f in plan.files:
            entry=next(x for x in receipt['files'] if x['target']==f.target)
            original=(backup/entry['backup']).resolve()
            if original.parent!=backup or original.read_bytes()!=f.original:raise RuntimeError('バックアップ内容が一致しません。')
            if Path(f.target).read_bytes()!=f.replacement:raise RuntimeError('保存後の内容が一致しません。')
        return backup
    finally:
        request.unlink(missing_ok=True);result.unlink(missing_ok=True)
