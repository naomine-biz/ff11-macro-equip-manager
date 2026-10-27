from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from ff11reader import equipment_saving as saving
from ff11reader.codecs import BAGS, equipsets, inventory
from ff11reader.domain import Character, Snapshot, Text
from ff11reader.edit_application import Editor
from ff11reader.editing import Edit, Change
from ff11reader.fixes import plan_fixes
from ff11reader.references import assess_equipment
from tests.test_saving import checksum

class EquipmentSavingTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'work'/'equipment-save-tests';root.mkdir(parents=True,exist_ok=True)
        tmp=tempfile.TemporaryDirectory(dir=root);self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name);self.folder=self.base/'game'/'USER'/'abc';self.folder.mkdir(parents=True)
        for page in (0,1):
            raw=bytearray(1624);raw[:8]=b'HEADER!!';raw[24:28]=b'Test'
            struct.pack_into('<BBH',raw,40,8*4+1,2,100)
            (self.folder/f'es{page}.dat').write_bytes(checksum(raw))
        for name,bag in BAGS.items():
            raw=bytearray(4240);struct.pack_into('<HH',raw,0,0x208,4216)
            if bag==8:struct.pack_into('<BBH',raw,0xA3C+5*20+16,5,0,100)
            (self.folder/name).write_bytes(checksum(raw))
        self.addCleanup(patch.stopall)
        patch('ff11reader.equipment_saving.require_game_closed').start()
        patch('ff11reader.saving.require_game_closed').start()
        self.source=self.load();self.editor=Editor(self.source,self.base/'draft.json')
        self.editor.equipment_fixes('abc',plan_fixes(self.source.characters[0]))
        self.plan=self.editor.prepare_equipment_save('abc')

    def load(self):
        c=Character('abc')
        for page in (0,1):c.equipsets.extend(equipsets((self.folder/f'es{page}.dat').read_bytes(),page))
        for name,bag in BAGS.items():
            c.inventory.extend(inventory((self.folder/name).read_bytes(),bag));c.inventory_coverage[bag]='loaded'
        c.equipsets=assess_equipment(c)
        sources=[{'path':str(p.resolve()),'sha256':saving.digest(p.read_bytes())} for p in self.folder.glob('*.dat')]
        return Snapshot('test','now',[c],{100:{'name':'Sword'}},sources,[],'test')

    def test_save_backups_checkpoint_restart_undo_redo(self):
        before={p:p.read_bytes() for p in self.folder.iterdir()}
        folder=self.editor.save_equipment(self.plan,self.base/'backups')
        self.assertEqual(len(self.plan.files),2)
        for i,f in enumerate(self.plan.files):
            self.assertEqual(Path(f.target).read_bytes(),f.replacement)
            self.assertEqual((folder/f'{i:03}.original.dat').read_bytes(),f.original)
            self.assertEqual({i for i,(a,b) in enumerate(zip(f.original,f.replacement)) if a!=b}-set(range(8,24)),{41})
            self.assertEqual(equipsets(f.replacement,f.page)[0].slots[0].index,5)
        for p,raw in before.items():
            if not p.name.startswith('es'):self.assertEqual(p.read_bytes(),raw)
        self.assertFalse(self.editor.session.dirty)
        reopened=Editor(self.load(),self.base/'draft.json');self.assertIsNone(reopened.blocked)
        self.assertFalse(reopened.session.dirty);reopened.undo();self.assertTrue(reopened.session.dirty)
        self.assertEqual(reopened.session.working.characters[0].equipsets[0].slots[0].index,2)
        reopened.redo();self.assertFalse(reopened.session.dirty)

    def test_stale_inventory_files_and_tampered_plan(self):
        f=self.plan.files[0]
        for plan in (replace(self.plan,dependencies=()),replace(self.plan,files=(replace(f,replacement=f.original),)+self.plan.files[1:])):
            with self.assertRaises(ValueError):saving.execute_equipment_save(plan,self.base/'backups')
        for name in ('wr.dat','es0.dat'):
            p=self.folder/name;raw=p.read_bytes();p.write_bytes(raw+b'x')
            with self.assertRaises(ValueError):saving.execute_equipment_save(self.plan,self.base/'backups')
            p.write_bytes(raw)
        self.assertFalse((self.base/'backups').exists())

    def test_partial_failure_rolls_back(self):
        original=saving.os.replace
        def fail(src,dst):
            if Path(dst).name=='es1.dat' and Path(src).name.startswith('.ff11-equipment-'):raise OSError('simulated')
            return original(src,dst)
        with patch.object(saving.os,'replace',side_effect=fail):
            with self.assertRaisesRegex(RuntimeError,'完了'):self.editor.save_equipment(self.plan,self.base/'backups')
        for f in self.plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)
        self.assertTrue(self.editor.session.dirty)
        self.assertFalse(self.editor.store.path.with_suffix('.pending.json').exists())

    def test_backup_failure_and_running_game_write_nothing(self):
        with patch.object(saving,'write_json',side_effect=OSError('full')):
            with self.assertRaises(OSError):self.editor.save_equipment(self.plan,self.base/'backups')
        with patch('ff11reader.saving.require_game_closed',side_effect=RuntimeError('running')):
            with self.assertRaises(RuntimeError):self.editor.save_equipment(self.plan,self.base/'backups')
        for f in self.plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)

    def test_checkpoint_failure_recovers(self):
        save=self.editor.store.save;calls=0
        def fail(session):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('full')
            return save(session)
        with patch.object(self.editor.store,'save',side_effect=fail):
            with self.assertRaisesRegex(RuntimeError,'完了'):self.editor.save_equipment(self.plan,self.base/'backups')
        reopened=Editor(self.load(),self.base/'draft.json')
        self.assertIsNone(reopened.blocked);self.assertFalse(reopened.session.dirty)
        self.assertFalse(reopened.store.path.with_suffix('.pending.json').exists())

    def test_preview_race_and_unrelated_edit_retained(self):
        self.editor.undo()
        with self.assertRaises(ValueError):self.editor.save_equipment(self.plan,self.base/'backups')
        self.editor.redo()
        c=self.editor.session.working.characters[0];e=c.equipsets[0]
        changed=replace(e,title=Text('Renamed','','draft'))
        self.editor.apply(Edit('rename',(Change('abc','equipsets',(e.number,),e,changed),)))
        plan=self.editor.prepare_equipment_save('abc');self.assertEqual(plan.deferred,1)
        self.editor.save_equipment(plan,self.base/'backups')
        self.assertTrue(self.editor.session.dirty)
        self.assertEqual(self.load().characters[0].equipsets[0].title.display,'Test')
        reopened=Editor(self.load(),self.base/'draft.json');self.assertIsNone(reopened.blocked)
        self.assertEqual(reopened.session.working.characters[0].equipsets[0].title.display,'Renamed')

    def test_only_applied_subset_saved(self):
        working=deepcopy(self.source);working.characters[0].equipsets[0]=self.editor.session.working.characters[0].equipsets[0]
        plan=saving.prepare_equipment_save(self.source,working,'abc')
        self.assertEqual(len(plan.files),1);self.assertEqual(len(plan.files[0].changes),1)
        self.assertEqual(plan.files[0].page,0)

    def test_restore_after_partial_write_and_external_change(self):
        folder=self.editor.save_equipment(self.plan,self.base/'backups')
        self.assertEqual(len(saving.restore_equipment_backup(folder)),2)
        first=self.plan.files[0];Path(first.target).write_bytes(first.original)
        saving.restore_equipment_backup(folder,True)
        for f in self.plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)
        saving.restore_equipment_backup(folder,True)
        Path(first.target).write_bytes(b'external update')
        with self.assertRaises(ValueError):saving.restore_equipment_backup(folder,True)
        self.assertEqual(Path(first.target).read_bytes(),b'external update')

    def test_candidate_changes_and_staging_failure(self):
        f=self.plan.files[0];change=replace(f.changes[0],after=(8,6))
        altered=replace(f,changes=(change,),replacement=saving.patch_equipment(f.original,f.page,(change,)))
        with self.assertRaises(ValueError):saving.execute_equipment_save(replace(self.plan,files=(altered,)+self.plan.files[1:]),self.base/'backups')
        original=Path.open
        def fail(path,*args,**kwargs):
            if path.name.startswith('.ff11-equipment-'):raise PermissionError('denied')
            return original(path,*args,**kwargs)
        with patch.object(Path,'open',fail):
            with self.assertRaises(PermissionError):self.editor.save_equipment(self.plan,self.base/'backups')
        for f in self.plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)
        self.assertFalse(self.editor.store.path.with_suffix('.pending.json').exists())

    def test_failed_rollback_keeps_pending_and_blocks_edits(self):
        original=saving.os.replace
        def fail(src,dst):
            if Path(dst).name=='es1.dat' and Path(src).name.startswith('.ff11-equipment-'):raise OSError('simulated')
            return original(src,dst)
        with patch.object(saving.os,'replace',side_effect=fail), patch.object(saving,'atomic_replace',side_effect=OSError('rollback failed')):
            with self.assertRaisesRegex(RuntimeError,'復旧確認'):self.editor.save_equipment(self.plan,self.base/'backups')
        self.assertIsNotNone(self.editor.blocked)
        self.assertTrue(self.editor.store.path.with_suffix('.pending.json').exists())
        reopened=Editor(self.load(),self.base/'draft.json');self.assertIsNotNone(reopened.blocked)
        folder=next((self.base/'backups').iterdir())
        saving.restore_equipment_backup(folder,True)
        reopened=Editor(self.load(),self.base/'draft.json');self.assertIsNone(reopened.blocked)
        self.assertTrue(reopened.session.dirty)

    @unittest.skipUnless(os.environ.get('FF11_RUN_INTEGRATION')=='1','Enable Tk checks')
    def test_gui_preview_and_save_fixture_only(self):
        import tkinter as tk
        from tkinter import ttk
        from ff11reader.ui import ReaderWindow
        app=tk.Tk();app.withdraw();errors=[];app.report_callback_exception=lambda *e:errors.append(e)
        save=self.editor.save_equipment
        try:
            with patch('ff11reader.ui.Editor',return_value=self.editor):view=ReaderWindow(app,self.source)
            view.preview_equipment_save();app.update()
            window=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel))
            detail=next(w for w in window.winfo_children() if isinstance(w,tk.Text)).get('1.0','end')
            self.assertIn('001  Test',detail);self.assertIn('021  Test',detail)
            for f in self.plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)
            button=next(w for w in window.winfo_children() if isinstance(w,ttk.Button))
            with patch.object(self.editor,'save_equipment',side_effect=lambda p,root:save(p,self.base/'backups')):button.invoke()
            app.update();self.assertFalse(errors,errors);self.assertFalse(self.editor.session.dirty)
            for f in self.plan.files:self.assertEqual(Path(f.target).read_bytes(),f.replacement)
        finally:app.destroy()
