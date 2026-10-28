"""Single-file equipment reference writer. Backups are outside the installation."""
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from pathlib import Path
import ctypes
import hashlib
import json
import os
import re
import subprocess
import tempfile
from uuid import uuid4
from .codecs import BAGS, SLOTS, equipsets, inventory
from .domain import Character
from .fixes import plan_fixes


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require_game_closed():
    if os.name != 'nt':
        raise RuntimeError('実ファイル保存はWindowsのみ対応しています。')
    from ctypes import wintypes as w
    class Entry(ctypes.Structure):
        _fields_ = [('size',w.DWORD),('usage',w.DWORD),('pid',w.DWORD),
                    ('heap',ctypes.c_size_t),('module',w.DWORD),('threads',w.DWORD),
                    ('parent',w.DWORD),('priority',w.LONG),('flags',w.DWORD),('name',w.WCHAR*260)]
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD]
    api.CreateToolhelp32Snapshot.restype=w.HANDLE
    api.Process32FirstW.argtypes=[w.HANDLE,ctypes.POINTER(Entry)]
    api.Process32NextW.argtypes=[w.HANDLE,ctypes.POINTER(Entry)]
    api.CloseHandle.argtypes=[w.HANDLE]
    handle=api.CreateToolhelp32Snapshot(2,0)
    if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
    try:
        entry=Entry();entry.size=ctypes.sizeof(entry)
        if not api.Process32FirstW(handle,ctypes.byref(entry)):raise ctypes.WinError(ctypes.get_last_error())
        while True:
            if entry.name.lower() in ('pol.exe','polboot.exe','ffxi.exe'):
                raise RuntimeError('FF11とPlayOnlineを終了してから保存してください。')
            if not api.Process32NextW(handle,ctypes.byref(entry)):
                if ctypes.get_last_error()!=18:raise ctypes.WinError(ctypes.get_last_error())
                break
    finally:api.CloseHandle(handle)


@contextmanager
def locked_read(path, replaceable=False):
    # Deny writers; allow our atomic rename on the one target file.
    if os.name != 'nt':
        with path.open('rb') as stream:
            yield stream.read()
        return
    from ctypes import wintypes
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                               ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    api.CreateFileW.restype = wintypes.HANDLE
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = api.CreateFileW(str(path), 0x80000000, 1 | (4 if replaceable else 0),
                             None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield path.read_bytes()
    finally:
        api.CloseHandle(handle)


@dataclass(frozen=True)
class SavePlan:
    target: str
    dependencies: tuple[tuple[str, str], ...]
    changes: tuple
    original: bytes
    replacement: bytes


def patch_equipment(data, file_index, changes):
    decoded = {e.number: e for e in equipsets(data, file_index)}
    out = bytearray(data)
    seen = set()
    for change in changes:
        key = change.equipset, change.slot
        if key in seen or change.equipset not in decoded or change.slot not in SLOTS:
            raise ValueError('変更対象が不正です。')
        seen.add(key)
        slot = next(s for s in decoded[change.equipset].slots if s.name == change.slot)
        if (slot.action, slot.item_id, slot.container, slot.index) != (
                'equip', change.item_id, *change.before):
            raise ValueError('保存前の枠とプレビューが一致しません。')
        bag, index = change.after
        if not 0 <= bag <= 16 or not 1 <= index <= 80:
            raise ValueError('移動先が範囲外です。')
        offset = 24 + ((change.equipset - 1) % 20) * 80 + 16 + SLOTS.index(change.slot) * 4
        out[offset] = (out[offset] & 3) | (bag << 2)
        out[offset + 1] = index
    out[8:24] = hashlib.md5(out[24:]).digest()
    equipsets(bytes(out), file_index)
    return bytes(out)


def prepare_save(snapshot, character, number, slot_name=None):
    """A selected set (or one slot), always limited to one esN.dat."""
    if not any(c is character for c in snapshot.characters):
        raise ValueError('Unknown character')
    if not 1 <= number <= 200:
        raise ValueError('装備セット番号が範囲外です。')
    file_index = (number - 1) // 20
    records = {Path(s['path']).resolve(): s for s in snapshot.sources
               if Path(s['path']).parent.name == character.folder_id}
    targets = [p for p in records if p.name.lower() == f'es{file_index}.dat']
    if len(targets) != 1:
        raise ValueError('保存元ファイルを特定できません。')
    target = targets[0]
    if target.parent.parent.name.upper() != 'USER':
        raise ValueError('USER外のファイルには保存できません。')
    paths = [target] + [target.parent / name for name in BAGS]
    data = {}
    for path in paths:
        raw = path.read_bytes()
        if path not in records or digest(raw) != records[path]['sha256']:
            raise ValueError('ゲームファイルが変わりました。再読み込みしてください。')
        data[path] = raw
    # Recompute from disk, not mutable UI drafts.
    source = Character(character.folder_id)
    source.equipsets = equipsets(data[target], file_index)
    for name, bag in BAGS.items():
        source.inventory.extend(inventory(data[target.parent / name], bag))
        source.inventory_coverage[bag] = 'loaded'
    changes = tuple(x for x in plan_fixes(source).changes
                    if x.equipset == number and (slot_name is None or x.slot == slot_name))
    if not changes:
        raise ValueError('この対象には自動補正できる枠がありません。')
    replacement = patch_equipment(data[target], file_index, changes)
    return SavePlan(str(target), tuple((str(p), digest(data[p])) for p in paths),
                    changes, data[target], replacement)


def atomic_replace(target, data):
    # tempfile.mkstemp can retry PermissionError indefinitely on Windows when
    # os.access incorrectly reports Program Files as writable. Fail immediately.
    name = target.parent / ('.ff11-fix-' + uuid4().hex + '.tmp')
    try:
        with name.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if Path(name).read_bytes() != data:
            raise OSError('一時ファイルの検証に失敗しました。')
        os.replace(name, target)
    finally:
        if name.exists():
            name.unlink()


def execute_save(plan, backup_root):
    require_game_closed()
    target = Path(plan.target).resolve()
    backup_root = Path(backup_root).resolve()
    game_root = target.parent.parent.parent
    if backup_root.is_relative_to(game_root):
        raise ValueError('バックアップはゲームフォルダの外に必要です。')
    if not re.fullmatch(r'es[0-9]\.dat', target.name) or target.parent.parent.name.upper() != 'USER':
        raise ValueError('保存対象が不正です。')
    if patch_equipment(plan.original, int(target.name[2]), plan.changes) != plan.replacement:
        raise ValueError('保存計画が不正です。')
    expected_paths = {str(target)} | {str(target.parent / name) for name in BAGS}
    if len(plan.dependencies) != 18 or {p for p, _ in plan.dependencies} != expected_paths:
        raise ValueError('全収納の検証情報が必要です。')
    from types import SimpleNamespace
    from .file_transaction import execute_batch, write_json

    def validate(data):
        source = Character(target.parent.name)
        source.equipsets = equipsets(data[target], int(target.name[2]))
        for name, bag in BAGS.items():
            source.inventory.extend(inventory(data[target.parent / name], bag))
            source.inventory_coverage[bag] = 'loaded'
        allowed = plan_fixes(source).changes
        if not plan.changes or any(change not in allowed for change in plan.changes):
            raise ValueError('自動補正の条件を満たさない変更です。')

    file = SimpleNamespace(target=str(target), page=int(target.name[2]),
                           original=plan.original, replacement=plan.replacement,
                           changes=plan.changes)
    batch = SimpleNamespace(character=target.parent.name, files=(file,),
                            dependencies=plan.dependencies)
    try:
        return execute_batch(batch, backup_root, game_root, validate, equipsets,
                             'equipment-reference-fix', '.ff11-fix-', asdict,
                             require_game_closed, write_json, atomic_replace,
                             single_file_receipt=True)
    except RuntimeError as exc:
        # Preserve the CLI's I/O error category together with rollback details.
        if isinstance(exc.__cause__, OSError):
            raise OSError(str(exc)) from exc
        raise


def restore_backup(folder):
    """Restore only if current bytes still equal our saved output."""
    require_game_closed()
    folder = Path(folder)
    receipt = json.loads((folder / 'receipt.json').read_text(encoding='utf-8'))
    target = Path(receipt['target']).resolve()
    if not re.fullmatch(r'es[0-9]\.dat', target.name) or target.parent.parent.name.upper() != 'USER':
        raise ValueError('復元対象が不正です。')
    original = (folder / 'original.dat').read_bytes()
    if digest(original) != receipt['before_sha256']:
        raise ValueError('バックアップが破損しています。')
    equipsets(original, int(target.name[2]))
    with locked_read(target, True) as current:
        if digest(current) != receipt['after_sha256']:
            raise ValueError('保存後にゲームデータが変わっています。復元を中止しました。')
        require_game_closed()
    if digest(target.read_bytes()) != receipt['after_sha256']:
        raise ValueError('復元直前にゲームデータが変わりました。')
    atomic_replace(target, original)
    if target.read_bytes() != original:
        raise OSError('復元後の検証に失敗しました。')
    return target
