"""Seeded generators, independent fixtures, shrinking and synthetic I/O isolation."""
from contextlib import contextmanager, ExitStack
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import random
import struct
import sys
import tempfile
from unittest.mock import patch
# Load lazy imports before enabling the I/O guard.
from ff11reader import adapters, application, codecs, equipment_saving, macro_saving, saving, file_transaction
from ff11reader.domain import Character, Snapshot, Text
from ff11reader.edit_application import Editor
from ff11reader.editing import Change, Edit, plan_macro_fixes
from ff11reader.fixes import plan_fixes
from ff11reader.references import assess_equipment

ROOT = Path(__file__).resolve().parents[1] / 'work' / 'property-tests'
ACTIVE = ContextVar('property_test_root', default=None)


def audit(event, args):
    root = ACTIVE.get()
    if root is None:
        return
    if event.startswith(('socket.', 'winreg.')) or event in ('subprocess.Popen', 'ctypes.dlopen', 'ctypes.dlsym', 'ctypes.call_function'):
        raise AssertionError('Forbidden external access: ' + event)
    paths = ()
    if event == 'open': paths = args[:1]
    elif event in ('os.rename', 'os.link', 'os.symlink'): paths = args[:2]
    elif event in ('os.remove', 'os.rmdir', 'os.mkdir', 'os.listdir', 'os.scandir'): paths = args[:1]
    for path in paths:
        if isinstance(path, (str, bytes, os.PathLike)):
            actual = Path(os.fsdecode(path)).absolute()
            if not actual.is_relative_to(root):
                raise AssertionError(f'File access outside synthetic root: {event}: {actual}')


sys.addaudithook(audit)


@contextmanager
def isolated():
    ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
        root = Path(tmp).resolve()
        with ExitStack() as stack:
            # No process enumeration, installation discovery, resources or native locking.
            for module in (saving, macro_saving, equipment_saving):
                stack.enter_context(patch.object(module, 'require_game_closed', return_value=None))
            stack.enter_context(patch.object(adapters, 'discover', side_effect=AssertionError('Installation discovery forbidden')))
            stack.enter_context(patch.object(application, 'installations', side_effect=AssertionError('Installation discovery forbidden')))
            stack.enter_context(patch.object(adapters.LocalReader, 'load_phrases', return_value={}))
            @contextmanager
            def locked(path, *args, **kwargs):
                yield path.read_bytes()
            stack.enter_context(patch.object(file_transaction, 'locked_read', locked))
            stack.enter_context(patch.object(saving, 'locked_read', locked))
            token = ACTIVE.set(root)
            try:
                yield root
            finally:
                ACTIVE.reset(token)


def seeds():
    return [int(s) for s in os.environ.get('FF11_PROPERTY_SEEDS', '0,1,7,19,42,127').split(',')]


def failure_signature(exc):
    tb = exc.__traceback__
    while tb.tb_next: tb = tb.tb_next
    return type(exc).__name__, tb.tb_frame.f_code.co_name, tb.tb_lineno


def check_sequence(property_id, seed, operations, replay):
    try:
        replay(operations)
        return
    except Exception as exc:
        signature, original = failure_signature(exc), repr(exc)
    # Delta debugging: retain a failure at the same assertion, never a new setup error.
    minimal = list(operations)
    width = max(1, len(minimal) // 2)
    while width:
        changed = False
        for start in range(0, len(minimal), width):
            candidate = minimal[:start] + minimal[start + width:]
            if not candidate: continue
            try: replay(candidate)
            except Exception as exc:
                if failure_signature(exc) == signature:
                    minimal = candidate; changed = True; break
        if not changed: width //= 2
    ROOT.mkdir(parents=True, exist_ok=True)
    report = ROOT / f'{property_id}-{seed}.json'
    report.write_text(json.dumps({'property': property_id, 'seed': seed, 'operations': operations,
                                  'minimal_operations': minimal, 'failure': original}, ensure_ascii=False, indent=2), encoding='utf-8')
    raise AssertionError(f'{property_id} seed={seed}; minimized counterexample: {report}; {original}')


def checksum(raw):
    raw = bytearray(raw)
    raw[8:24] = hashlib.md5(raw[24:]).digest()
    return bytes(raw)


# Literal format constants are the test oracle, independent of the encoder.
BAGS = {'is.dat':0, 'bs.dat':1, 'cl.dat':2, 'ti.dat':3, 'mb.dat':4, 'sb.dat':5,
        'sk.dat':6, 'ca.dat':7, 'wr.dat':8, 'b2.dat':9,
        'wr_2.dat':10, 'wr_3.dat':11, 'wr_4.dat':12, 'wr_5.dat':13,
        'wr_6.dat':14, 'wr_7.dat':15, 'wr_8.dat':16}


class GameFixture:
    def __init__(self, base, kind, seed, count=3):
        self.base, self.kind = base, kind
        self.folder = base / 'game' / 'USER' / 'abc'
        self.folder.mkdir(parents=True)
        rng = random.Random(seed)
        self.specs, self.original, self.expected = [], {}, {}
        storage_map = {0:0, 1:8, 2:10, 3:11, 4:12, 5:13, 6:14, 7:15, 8:16}
        bag_number = rng.randrange(9)
        bag = storage_map[bag_number]
        for page in range(count):
            index, part = rng.randrange(20), rng.randrange(16)
            position = 5 + page
            if kind == 'macro':
                raw = bytearray(7624)
                line_number = rng.randrange(6)
                offset = 24 + index * 380 + 4 + line_number * 61
                before = f'/equip body Robe{page} {(bag_number + 1) % 9} <wait.1>'
                after = f'/equip body Robe{page} {bag_number} <wait.1>'
                raw[offset:offset+61] = before.encode() + b'\0' + b'Q' * (60-len(before))
                raw[24+index*380+370:24+index*380+374] = b'Test'
                path = self.folder / ('mcr' + (str(page) if page else '') + '.dat')
                expected = bytearray(raw)
                expected[offset:offset+len(after)+1] = after.encode() + b'\0'
                key = (1,page+1,'ctrl' if index<10 else 'alt',index%10+1)
                spec = {'key':key,'line':line_number+1,'before':before,'after':after,'offset':offset}
            else:
                raw = bytearray(1624)
                offset = 24 + index*80 + 16 + part*4
                raw[24+index*80:24+index*80+4] = b'Test'
                struct.pack_into('<BBH', raw, offset, 8*4+1, 2, 100+page)
                path = self.folder / f'es{page}.dat'
                expected = bytearray(raw)
                expected[offset] = bag*4+1
                expected[offset+1] = position
                spec = {'key':(page*20+index+1,), 'part':part, 'offset':offset, 'bag':bag, 'position':position}
            # Unknown header bytes must survive writes.
            raw[:8] = expected[:8] = bytes(rng.randrange(256) for _ in range(8))
            self.original[path], self.expected[path] = checksum(raw), checksum(expected)
            path.write_bytes(self.original[path]); self.specs.append(spec)
        for name, storage in BAGS.items():
            raw = bytearray(4240); struct.pack_into('<HH',raw,0,0x208,4216)
            if storage == bag:
                for page in range(count):
                    struct.pack_into('<BBH',raw,0xA3C+(5+page)*20+16,5+page,0,100+page)
            (self.folder/name).write_bytes(checksum(raw))
        self.all_original = self.bytes()
        self.initial = self.load()
        self.editor = Editor(self.initial, base/'draft.json')

    def bytes(self):
        return {p:p.read_bytes() for p in self.folder.glob('*.dat')}

    def load(self):
        c = Character('abc')
        for page, path in enumerate(self.original):
            if self.kind == 'macro': c.macros.extend(codecs.macros(path.read_bytes(),page))
            else: c.equipsets.extend(codecs.equipsets(path.read_bytes(),page))
        for name, bag in BAGS.items():
            c.inventory.extend(codecs.inventory((self.folder/name).read_bytes(),bag))
            c.inventory_coverage[bag] = 'loaded'
        c.equipsets = assess_equipment(c)
        sources = [{'path':str(p),'sha256':hashlib.sha256(raw).hexdigest()} for p,raw in self.bytes().items()]
        return Snapshot('synthetic','now',[c],{100+i:{'name':f'Robe{i}'} for i in range(len(self.specs))},sources,[],'synthetic')

    def fix(self):
        c = self.editor.snapshot().characters[0]
        if self.kind == 'macro': self.editor.macro_fixes('abc', plan_macro_fixes(c,self.initial.items))
        else: self.editor.equipment_fixes('abc',plan_fixes(c))

    def preview(self):
        return (self.editor.prepare_macro_save if self.kind=='macro' else self.editor.prepare_equipment_save)('abc')

    def save(self, plan):
        # Macro save's locked reread is redirected exclusively to this synthetic tree.
        with patch.object(application, 'load_snapshot', side_effect=lambda root:self.load()):
            return (self.editor.save_macros if self.kind=='macro' else self.editor.save_equipment)(plan,self.base/'backups')

    def reopen(self):
        self.editor = Editor(self.load(),self.base/'draft.json')
        return self.editor

    def manual_title(self):
        c = self.editor.snapshot().characters[0]
        key = self.specs[0]['key']
        if self.kind=='macro':
            item = next(m for m in c.macros if (m.book,m.palette,m.bank,m.key)==key)
            kind='macros'
        else:
            item = next(e for e in c.equipsets if (e.number,)==key);kind='equipsets'
        self.editor.apply(Edit('manual',(Change('abc',kind,key,item,replace(item,title=Text('Manual','','draft'))),)))
