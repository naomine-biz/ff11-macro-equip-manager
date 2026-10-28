"""PT-20..27: generated binary fixtures, fault schedules and restart recovery."""
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch
from ff11reader import saving, file_transaction, macro_saving, equipment_saving
from ff11reader.edit_application import Editor
from ff11reader.editing import Change, Edit
from tests.property_support import GameFixture, isolated, seeds, check_sequence


class Crash(BaseException):
    """Simulates interruption that bypasses ordinary exception rollback."""


@contextmanager
def instrument(fixture, fault=None, at=1, crash=False, external=False):
    events=[];counts={};descriptors={};written=set();verified=set();backups=set();stages=set()
    original_open=Path.open;original_read=Path.read_bytes
    original_fsync=file_transaction.os.fsync;original_replace=file_transaction.os.replace
    targets=set(fixture.original)
    def hit(event,path):
        events.append((event,str(path)));counts[event]=counts.get(event,0)+1
        if event==fault and counts[event]==at:
            if external:
                raw=bytearray(fixture.expected[path]);raw[0]^=1;path.write_bytes(raw)
            raise Crash(event) if crash else OSError('injected '+event)
    def category(path):
        if path.name.endswith('.original.dat'):return 'backup'
        if path.name.startswith(('.ff11-macro-','.ff11-equipment-')):return 'stage'
        return None
    def opened(path,*args,**kwargs):
        mode=args[0] if args else kwargs.get('mode','r');kind=category(path)
        if kind and mode=='xb':hit(kind+'_open',path)
        stream=original_open(path,*args,**kwargs)
        if kind and mode=='xb':descriptors[stream.fileno()]=(kind,path)
        return stream
    def synced(fd):
        record=descriptors.pop(fd,None)
        if record:hit(record[0]+'_fsync',record[1])
        return original_fsync(fd)
    def read(path):
        kind=category(path)
        if kind:
            hit(kind+'_verify',path)
            if kind=='backup':backups.add(path)
            else:stages.add(path)
        if path in written and path not in verified:
            verified.add(path);hit('verify',path)
        return original_read(path)
    def replaced(src,dst):
        src,dst=Path(src),Path(dst)
        if dst in targets and category(src)=='stage':
            # Independent event invariant: every backup and stage verified first.
            assert len(backups)==len(targets), ('backup order',events)
            assert len(stages)==len(targets), ('stage order',events)
            hit('replace',dst)
            result=original_replace(src,dst);written.add(dst)
            hit('replaced',dst)
            return result
        return original_replace(src,dst)
    with patch.object(Path,'open',opened),patch.object(Path,'read_bytes',read),patch.object(file_transaction.os,'fsync',synced),patch.object(file_transaction.os,'replace',replaced):
        yield events


class SavingProperties(unittest.TestCase):
    def test_generated_partial_save_bytes_and_history(self):
        # PT-20/23/27. Expected bytes are constructed by the fixture, not patch_*.
        for kind in ('macro','equipment'):
            for seed in seeds():
                with self.subTest(kind=kind,seed=seed),isolated() as base:
                    f=GameFixture(base,kind,seed,1+seed%3);f.fix()
                    fixed=f.editor.snapshot();f.editor.undo()
                    count=1+seed%len(f.specs);changes=[]
                    for spec in f.specs[:count]:
                        c=f.editor.snapshot().characters[0];after=fixed.characters[0]
                        if kind=='macro':
                            key=lambda m:(m.book,m.palette,m.bank,m.key);collection='macros'
                        else:key=lambda e:(e.number,);collection='equipsets'
                        before=next(x for x in getattr(c,collection) if key(x)==spec['key'])
                        new=next(x for x in getattr(after,collection) if key(x)==spec['key'])
                        changes.append(Change('abc',collection,spec['key'],before,new))
                    f.editor.apply(Edit('subset',tuple(changes)));f.manual_title()
                    plan=f.preview()
                    self.assertEqual(len(plan.files),count)
                    self.assertEqual(len(plan.deferred_changes),1)
                    self.assertIn('名前',plan.deferred_changes[0].target)
                    self.assertTrue(plan.deferred_changes[0].reason)
                    before=f.bytes();folder=f.save(plan)
                    for i,path in enumerate(f.original):
                        expected=f.expected[path] if i<count else f.original[path]
                        self.assertEqual(path.read_bytes(),expected)
                        self.assertEqual(expected[8:24],hashlib.md5(expected[24:]).digest())
                    for path,raw in before.items():
                        if path not in f.original:self.assertEqual(path.read_bytes(),raw)
                    self.assertEqual(len(list(folder.glob('*.original.dat'))),count)
                    self.assertEqual(f.editor.edit_status(),(2,2,True))
                    persisted=f.bytes();f.reopen();self.assertIsNone(f.editor.blocked)
                    for method,expected_status in [('undo',(1,2,False)),('undo',(0,2,True)),('redo',(1,2,False)),('redo',(2,2,True))]:
                        getattr(f.editor,method)();self.assertEqual(f.editor.edit_status(),expected_status)
                        self.assertEqual(f.bytes(),persisted)
                    f.reopen();self.assertEqual(f.editor.edit_status(),(2,2,True))

    def test_generated_preconditions_reject_stale_saves(self):
        # PT-21: vary dependency, original, working state and plan tampering.
        for kind in ('macro','equipment'):
            for seed,mode in enumerate(('target','inventory','working','plan','running')):
                with self.subTest(kind=kind,mode=mode),isolated() as base:
                    f=GameFixture(base,kind,seed,2);f.fix();plan=f.preview()
                    if mode=='target':next(iter(f.original)).write_bytes(b'external target')
                    elif mode=='inventory':(f.folder/'wr.dat').write_bytes(b'external inventory')
                    elif mode=='working':f.editor.undo()
                    elif mode=='plan':plan=replace(plan,files=(replace(plan.files[0],replacement=plan.files[0].original),)+plan.files[1:])
                    before=f.bytes()
                    with instrument(f) as events:
                        if mode=='running':
                            with patch.object(saving,'require_game_closed',side_effect=RuntimeError('synthetic running')):
                                with self.assertRaises((ValueError,RuntimeError)):f.save(plan)
                        else:
                            with self.assertRaises((ValueError,RuntimeError)):f.save(plan)
                    self.assertEqual(f.bytes(),before)
                    self.assertFalse(any(e=='replace' for e,_ in events))

    def test_every_preparation_fault_leaves_originals_untouched(self):
        # PT-22: every file in 1/2/3-file batches, before open/fsync/verification.
        for kind in ('macro','equipment'):
            for count in (1,2,3):
                for phase in ('backup_open','backup_fsync','backup_verify','stage_open','stage_fsync','stage_verify'):
                    for at in range(1,count+1):
                        with self.subTest(kind=kind,count=count,phase=phase,at=at),isolated() as base:
                            f=GameFixture(base,kind,at+count,count);f.fix();plan=f.preview()
                            with instrument(f,phase,at) as events:
                                with self.assertRaises((OSError,RuntimeError)):f.save(plan)
                            self.assertEqual(f.bytes(),f.all_original)
                            self.assertFalse(any(e=='replace' for e,_ in events))
                            self.assertFalse((base/'draft.pending.json').exists())

    def test_every_write_fault_rolls_back_or_preserves_external_bytes(self):
        # PT-25: each before/after replace and verification location.
        for kind in ('macro','equipment'):
            for phase in ('replace','replaced','verify'):
                for at in (1,2,3):
                    for external in (False,True):
                        if external and phase!='replaced':continue
                        with self.subTest(kind=kind,phase=phase,at=at,external=external),isolated() as base:
                            f=GameFixture(base,kind,at,3);f.fix();plan=f.preview()
                            with instrument(f,phase,at,external=external):
                                with self.assertRaises(RuntimeError):f.save(plan)
                            for i,path in enumerate(f.original,1):
                                expected=bytearray(f.expected[path]);expected[0]^=1
                                self.assertEqual(path.read_bytes(),bytes(expected) if external and i==at else f.original[path])
                            if external:
                                self.assertIsNotNone(f.editor.blocked)
                                with self.assertRaises(ValueError):f.editor.undo()
                                f.reopen();self.assertIsNotNone(f.editor.blocked)
                            else:
                                self.assertIsNone(f.editor.blocked);f.reopen();self.assertIsNone(f.editor.blocked)
                                self.assertTrue(f.editor.session.dirty)

    def test_interrupted_save_recovers_only_known_complete_states(self):
        # PT-26: interrupt before first output and after every replaced target.
        for kind in ('macro','equipment'):
            for phase,at in [('backup_open',1),('replace',1),('replaced',1),('replaced',2),('replaced',3)]:
                with self.subTest(kind=kind,phase=phase,at=at),isolated() as base:
                    f=GameFixture(base,kind,at,3);f.fix();plan=f.preview()
                    with instrument(f,phase,at,crash=True):
                        with self.assertRaises(Crash):f.save(plan)
                    f.reopen()
                    if phase=='replaced' and at<3:
                        self.assertIsNotNone(f.editor.blocked)
                        with self.assertRaises(ValueError):f.editor.redo()
                    else:
                        self.assertIsNone(f.editor.blocked)
                        self.assertEqual(f.editor.session.dirty,phase!='replaced')
                        first=f.bytes();f.reopen();self.assertEqual(f.bytes(),first)
                        self.assertEqual(f.editor.edit_status(),(1,1,phase!='replaced'))

    def test_checkpoint_crashes_before_after_sync_and_cleanup(self):
        for kind in ('macro','equipment'):
            for phase in ('before_sync','after_sync','cleanup'):
                with self.subTest(kind=kind,phase=phase),isolated() as base:
                    f=GameFixture(base,kind,42,3);f.fix();plan=f.preview()
                    store=f.editor.store.save;unlink=Path.unlink;calls=0
                    def sync(session):
                        nonlocal calls
                        calls+=1
                        if calls==2 and phase=='before_sync':raise Crash(phase)
                        result=store(session)
                        if calls==2 and phase=='after_sync':raise Crash(phase)
                        return result
                    def remove(path,*a,**kw):
                        if phase=='cleanup' and path==base/'draft.pending.json':raise Crash(phase)
                        return unlink(path,*a,**kw)
                    with patch.object(f.editor.store,'save',side_effect=sync),patch.object(Path,'unlink',remove):
                        with self.assertRaises(Crash):f.save(plan)
                    f.reopen();self.assertIsNone(f.editor.blocked)
                    self.assertEqual(f.editor.edit_status(),(1,1,False))
                    for path,expected in f.expected.items():self.assertEqual(path.read_bytes(),expected)
                    f.reopen();self.assertEqual(f.editor.edit_status(),(1,1,False))

    def test_generated_macro_byte_boundaries(self):
        # PT-24 current Fix scope: CP932, embedded-zero tokens and 60-byte limit.
        token=bytes.fromhex('fd02000201fd')
        for seed in seeds():
            rng=random.Random(seed)
            for item,display in [(b'Robe','Robe'),('装備'.encode('cp932'),'装備'),(token,'【装備】')]:
                for after_size in (59,60,61):
                    prefix=b'/equip body '+item
                    payload=prefix+b' '*(after_size-2-len(prefix))
                    raw=payload+b'\0'+bytes([rng.randrange(1,128)])*(60-len(payload))
                    before='/equip body '+display+' '*(after_size-2-len(prefix))
                    after='/equip body '+display+' 1'+' '*(after_size-2-len(prefix))
                    with self.subTest(seed=seed,item=display,size=after_size):
                        if after_size>60:
                            with self.assertRaises(ValueError):macro_saving.patch_line(raw,before,after,lambda _: '装備')
                        else:
                            result=macro_saving.patch_line(raw,before,after,lambda _: '装備')
                            expected=bytearray(raw);output=prefix+b' 1'+payload[len(prefix):]
                            expected[:len(output)+1]=output+b'\0'
                            self.assertEqual(result,bytes(expected))
                            self.assertEqual(len(result),61)

    def replay_save_sequence(self, kind, seed, operations):
        # PT-16: separate logical model for edit/history/partial-save transitions.
        with isolated() as base:
            f=GameFixture(base,kind,seed,2)
            current=[('Test',False),('Test',False)]
            saved=list(current);history=[];cursor=0
            def projection(snapshot):
                c=snapshot.characters[0];result=[]
                for spec in f.specs:
                    if kind=='macro':
                        item=next(m for m in c.macros if (m.book,m.palette,m.bank,m.key)==spec['key'])
                        line=item.lines[spec['line']-1].display
                        self.assertIn(line,(spec['before'],spec['after']))
                        fixed=line==spec['after']
                    else:
                        item=next(e for e in c.equipsets if (e.number,)==spec['key'])
                        slot=item.slots[spec['part']]
                        self.assertIn((slot.container,slot.index),((8,2),(spec['bag'],spec['position'])))
                        fixed=(slot.container,slot.index)==(spec['bag'],spec['position'])
                    result.append((item.title.display,fixed))
                return result
            for op in operations:
                after=list(current)
                if op=='fix':
                    f.fix();after=[(name,True) for name,_ in current]
                elif op=='one_fix':
                    c=f.editor.snapshot().characters[0];spec=f.specs[0]
                    if kind=='macro':
                        item=next(m for m in c.macros if (m.book,m.palette,m.bank,m.key)==spec['key'])
                        lines=list(item.lines);lines[spec['line']-1]=replace(lines[spec['line']-1],display=spec['after'],raw_hex='',state='draft')
                        changed=replace(item,lines=tuple(lines));collection='macros'
                    else:
                        item=next(e for e in c.equipsets if (e.number,)==spec['key'])
                        slots=list(item.slots);slots[spec['part']]=replace(slots[spec['part']],container=spec['bag'],index=spec['position'])
                        changed=replace(item,slots=tuple(slots));collection='equipsets'
                    f.editor.apply(Edit('one fix',(Change('abc',collection,spec['key'],item,changed),)))
                    after[0]=(current[0][0],True)
                elif op=='rename':f.manual_title();after[0]=('Manual',current[0][1])
                elif op=='undo':
                    f.editor.undo()
                    if cursor:cursor-=1;current=list(history[cursor][0])
                elif op=='redo':
                    f.editor.redo()
                    if cursor<len(history):current=list(history[cursor][1]);cursor+=1
                elif op=='restart':f.reopen();self.assertIsNone(f.editor.blocked)
                elif op=='save':
                    eligible=[i for i in range(2) if current[i][1] and not saved[i][1]]
                    if not eligible:
                        with self.assertRaises(ValueError):f.preview()
                    else:
                        plan=f.preview();self.assertEqual(len(plan.files),len(eligible))
                        f.save(plan)
                        for i in eligible:saved[i]=(saved[i][0],True)
                elif op=='fail':
                    with patch.object(f.editor.store,'save',side_effect=OSError('synthetic work save failure')):
                        with self.assertRaises(OSError):f.editor.undo()
                if op in ('fix','one_fix','rename') and after!=current:
                    history[cursor:]=[(list(current),list(after))];cursor+=1;current=after
                self.assertEqual(projection(f.editor.snapshot()),current)
                self.assertEqual(projection(f.editor.session.saved),saved)
                self.assertEqual(f.editor.edit_status(),(cursor,len(history),current!=saved))
                for i,path in enumerate(f.original):
                    self.assertEqual(path.read_bytes(),f.expected[path] if saved[i][1] else f.original[path])

    def test_generated_sequences_include_partial_save_and_restart(self):
        for kind in ('macro','equipment'):
            for seed in seeds():
                rng=random.Random(seed)
                ops=['one_fix','rename','save','restart','undo','undo','redo','fix','save']
                ops += [rng.choice(['fix','one_fix','rename','undo','redo','save','restart','fail']) for _ in range(18)]
                with self.subTest(kind=kind,seed=seed):
                    check_sequence('PT-16-save-'+kind,seed,ops,lambda sequence:self.replay_save_sequence(kind,seed,sequence))

    def test_rollback_failure_blocks_reopen_and_operations(self):
        for kind in ('macro','equipment'):
            for at in (1,2,3):
                with self.subTest(kind=kind,at=at),isolated() as base:
                    f=GameFixture(base,kind,at,3);f.fix();plan=f.preview()
                    module=macro_saving if kind=='macro' else equipment_saving
                    with instrument(f,'replaced',at),patch.object(module,'atomic_replace',side_effect=OSError('restore failed')):
                        with self.assertRaises(RuntimeError):f.save(plan)
                    self.assertIsNotNone(f.editor.blocked)
                    self.assertTrue((base/'draft.pending.json').exists())
                    failure=json.loads(next((base/'backups').glob('*/failure.json')).read_text(encoding='utf-8'))
                    self.assertTrue(failure['rollback_errors'])
                    f.reopen()
                    if at<3:
                        self.assertIsNotNone(f.editor.blocked)
                        with self.assertRaises(ValueError):f.editor.undo()
                    else:
                        # Every target equals the planned output; restart verifies completion.
                        self.assertIsNone(f.editor.blocked)
                        self.assertFalse(f.editor.session.dirty)

    def test_saved_undo_branch_reopen_regression(self):
        # Minimized by PT-16, seed 42. Retain as a fixed regression.
        for kind in ('macro','equipment'):
            with self.subTest(kind=kind):
                self.replay_save_sequence(kind,42,['fix','save','undo','one_fix','restart'])
