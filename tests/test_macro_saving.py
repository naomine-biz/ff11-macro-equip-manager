from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from ff11reader import macro_saving as saving
from ff11reader.codecs import BAGS, macros, inventory
from ff11reader.domain import Character, Snapshot, Text
from ff11reader.editing import plan_macro_fixes, edit_macro
from ff11reader.edit_application import Editor
from tests.test_saving import checksum


class MacroSavingTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'work'/'macro-save-tests';root.mkdir(parents=True,exist_ok=True)
        temp=tempfile.TemporaryDirectory(dir=root);self.addCleanup(temp.cleanup)
        self.base=Path(temp.name);self.root=self.base/'game';self.folder=self.root/'USER'/'abc';self.folder.mkdir(parents=True)
        for page in (0,1):
            data=bytearray(7624);data[:8]=b'HEADER!!'
            line=b'/equip body Robe 2 <wait 2>'
            data[28:28+len(line)]=line
            data[24+370:24+374]=b'Test'
            (self.folder/('mcr'+(str(page) if page else '')+'.dat')).write_bytes(checksum(data))
        for name,bag in BAGS.items():
            data=bytearray(4240);struct.pack_into('<HH',data,0,0x208,4216)
            if bag==8:struct.pack_into('<BBH',data,0xA3C+5*20+16,5,0,100)
            (self.folder/name).write_bytes(checksum(data))
        self.addCleanup(patch.stopall)
        patch('ff11reader.adapters.LocalReader.load_phrases',return_value={}).start()
        patch('ff11reader.application.load_snapshot',side_effect=lambda root:self.load()).start()
        patch('ff11reader.macro_saving.require_game_closed').start()
        patch('ff11reader.saving.require_game_closed').start()
        self.source=self.load();self.editor=Editor(self.source,self.base/'draft.json')
        self.editor.macro_fixes('abc',plan_macro_fixes(self.source.characters[0],self.source.items))
        self.plan=self.editor.prepare_macro_save('abc')

    def load(self):
        c=Character('abc')
        for page in (0,1):c.macros.extend(macros((self.folder/('mcr'+(str(page) if page else '')+'.dat')).read_bytes(),page))
        for name,bag in BAGS.items():
            c.inventory.extend(inventory((self.folder/name).read_bytes(),bag));c.inventory_coverage[bag]='loaded'
        sources=[{'path':str(p.resolve()),'sha256':saving.digest(p.read_bytes())} for p in self.folder.glob('*.dat')]
        return Snapshot('test','now',[c],{100:{'name':'Robe'}},sources,[],'test')

    def test_save_backup_checkpoint_restart_and_undo(self):
        before={p:p.read_bytes() for p in self.folder.iterdir()}
        folder=self.editor.save_macros(self.plan,self.base/'backups')
        self.assertEqual(len(self.plan.files),2)
        for index,f in enumerate(self.plan.files):
            self.assertEqual(Path(f.target).read_bytes(),f.replacement)
            self.assertEqual((folder/f'{index:03}.original.dat').read_bytes(),f.original)
            offsets={i for i,(a,b) in enumerate(zip(f.original,f.replacement)) if a!=b}
            self.assertEqual(offsets-set(range(8,24)),{45})
        for p,data in before.items():
            if p.name not in ('mcr.dat','mcr1.dat'):self.assertEqual(p.read_bytes(),data)
        self.assertFalse(self.editor.session.dirty)
        reopened=Editor(self.load(),self.base/'draft.json');self.assertIsNone(reopened.blocked)
        self.assertFalse(reopened.session.dirty);reopened.undo();self.assertTrue(reopened.session.dirty)
        self.assertIn('Robe 2',reopened.session.working.characters[0].macros[0].lines[0].display)
        reopened.redo();self.assertFalse(reopened.session.dirty)
        self.assertIn('Robe 1',macros((self.folder/'mcr.dat').read_bytes(),0)[0].lines[0].display)

    def test_stale_macro_inventory_and_plan_tamper_rejected(self):
        file=self.plan.files[0]
        altered=replace(file,replacement=file.original)
        with self.assertRaises(ValueError):saving.execute_macro_save(replace(self.plan,files=(altered,)+self.plan.files[1:]),self.base/'backups')
        with self.assertRaises(ValueError):saving.execute_macro_save(replace(self.plan,dependencies=()),self.base/'backups')
        target=self.folder/'wr.dat';raw=target.read_bytes();target.write_bytes(raw+b'x')
        with self.assertRaises(ValueError):saving.execute_macro_save(self.plan,self.base/'backups')
        self.assertEqual(Path(file.target).read_bytes(),file.original)

    def test_partial_failure_rolls_back_all_written_files(self):
        original_replace=saving.os.replace
        def fail_second(src,dst):
            if Path(dst).name=='mcr1.dat' and Path(src).name.startswith('.ff11-macro-'):raise OSError('simulated failure')
            return original_replace(src,dst)
        with patch.object(saving.os,'replace',side_effect=fail_second):
            with self.assertRaisesRegex(RuntimeError,'完了'):self.editor.save_macros(self.plan,self.base/'backups')
        for f in self.plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)
        self.assertTrue(self.editor.session.dirty)
        self.assertFalse(self.editor.store.path.with_suffix('.pending.json').exists())

    def test_unrelated_manual_edits_are_retained(self):
        c=self.editor.session.working.characters[0];m=c.macros[0]
        lines=[l.display for l in m.lines];lines[1]='/echo custom'
        self.editor.apply(edit_macro(c,m,'Renamed',lines))
        plan=self.editor.prepare_macro_save('abc');self.assertEqual(plan.deferred,2)
        self.assertIn('名前',plan.deferred_changes[0].target)
        self.assertIn('2行目',plan.deferred_changes[1].target)
        self.assertTrue(all(c.reason for c in plan.deferred_changes))
        self.editor.save_macros(plan,self.base/'backups')
        self.assertTrue(self.editor.session.dirty)
        game=self.load().characters[0].macros[0]
        self.assertEqual(game.title.display,'Test');self.assertEqual(game.lines[1].display,'')
        reopened=Editor(self.load(),self.base/'draft.json');self.assertIsNone(reopened.blocked)
        self.assertEqual(reopened.session.working.characters[0].macros[0].title.display,'Renamed')

    def test_draft_checkpoint_failure_recovers_on_restart(self):
        save=self.editor.store.save;calls=0
        def fail_checkpoint(session):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('disk full')
            return save(session)
        with patch.object(self.editor.store,'save',side_effect=fail_checkpoint):
            with self.assertRaisesRegex(RuntimeError,'完了'):self.editor.save_macros(self.plan,self.base/'backups')
        self.assertTrue(self.editor.store.path.with_suffix('.pending.json').exists())
        reopened=Editor(self.load(),self.base/'draft.json')
        self.assertIsNone(reopened.blocked);self.assertFalse(reopened.session.dirty)
        self.assertFalse(reopened.store.path.with_suffix('.pending.json').exists())

    def test_game_running_blocks_before_backup(self):
        with patch('ff11reader.saving.require_game_closed',side_effect=RuntimeError('running')):
            with self.assertRaises(RuntimeError):self.editor.save_macros(self.plan,self.base/'backups')
        self.assertFalse((self.base/'backups').exists())

    def test_restore_and_later_changes_protected(self):
        folder=self.editor.save_macros(self.plan,self.base/'backups')
        self.assertEqual(len(saving.restore_macro_backup(folder)),2)
        for f in self.plan.files:self.assertEqual(Path(f.target).read_bytes(),f.replacement)
        saving.restore_macro_backup(folder,True)
        for f in self.plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)
        saving.restore_macro_backup(folder,True)  # already restored
        target=Path(self.plan.files[0].target);target.write_bytes(b'other changes')
        with self.assertRaises(ValueError):saving.restore_macro_backup(folder,True)
        self.assertEqual(target.read_bytes(),b'other changes')

    def test_preview_edit_race_and_backup_failure_write_nothing(self):
        original=self.editor.store.save
        with patch('ff11reader.macro_saving.write_json',side_effect=OSError('backup full')):
            with self.assertRaises(OSError):self.editor.save_macros(self.plan,self.base/'backups')
        for f in self.plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)
        self.editor.undo()
        with self.assertRaises(ValueError):self.editor.save_macros(self.plan,self.base/'backups')

    def test_pending_cleanup_after_checkpoint_already_saved(self):
        self.editor.save_macros(self.plan,self.base/'backups')
        pending=self.editor.store.path.with_suffix('.pending.json')
        data=json.loads(self.editor.store.path.read_text(encoding='utf-8'));data['draft_revision']='old'
        pending.write_text(json.dumps(data),encoding='utf-8')
        reopened=Editor(self.load(),self.base/'draft.json')
        self.assertIsNone(reopened.blocked);self.assertFalse(pending.exists())

    @unittest.skipUnless(os.environ.get('FF11_RUN_INTEGRATION')=='1','Enable Tk integration checks')
    def test_gui_preview_then_save_fixture_only(self):
        import tkinter as tk
        from tkinter import ttk
        from ff11reader.ui import ReaderWindow
        app=tk.Tk();app.withdraw();errors=[];app.report_callback_exception=lambda *e:errors.append(e)
        save=self.editor.save_macros
        try:
            with patch('ff11reader.ui.Editor',return_value=self.editor):view=ReaderWindow(app,self.source)
            view.preview_game_save();app.update()
            window=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel))
            detail=next(w for w in window.winfo_children() if isinstance(w,tk.Text)).get('1.0','end')
            self.assertIn('/equip body Robe 1 <wait 2>',detail)
            for f in self.plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)
            button=next(w for w in window.winfo_children() if isinstance(w,ttk.Button))
            with patch.object(self.editor,'save_macros',side_effect=lambda p,root:save(p,self.base/'backups')):button.invoke()
            app.update()
            self.assertFalse(view.editor.session.dirty);self.assertFalse(errors,errors)
            for f in self.plan.files:self.assertEqual(Path(f.target).read_bytes(),f.replacement)
        finally:app.destroy()

    @unittest.skipUnless(os.environ.get('FF11_RUN_INTEGRATION')=='1','Enable Tk integration checks')
    def test_gui_shows_deferred_target_and_reason(self):
        import tkinter as tk
        from ff11reader.ui import ReaderWindow
        c=self.editor.session.working.characters[0];m=c.macros[0]
        self.editor.apply(edit_macro(c,m,'Renamed',[l.display for l in m.lines]))
        app=tk.Tk();app.withdraw()
        try:
            with patch('ff11reader.ui.Editor',return_value=self.editor):view=ReaderWindow(app,self.source)
            view.preview_game_save();app.update()
            window=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel))
            detail=next(w for w in window.winfo_children() if isinstance(w,tk.Text)).get('1.0','end')
            self.assertIn('名前',detail);self.assertIn('マクロの編集をゲームに保存',detail)
            self.assertIn('作業データに残す',detail)
            for f in self.plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)
        finally:app.destroy()

    def test_deferred_only_has_targets_and_reasons(self):
        self.editor.undo()
        c=self.editor.session.working.characters[0];m=c.macros[0]
        self.editor.apply(edit_macro(c,m,'New',[l.display for l in m.lines]))
        with self.assertRaisesRegex(ValueError,'名前.*マクロの編集をゲームに保存'):self.editor.prepare_macro_save('abc')

    def test_token_zero_bytes_japanese_padding_and_length_limit(self):
        token=bytes.fromhex('fd02000201fd')
        payload=b'/equip body '+token+b' <wait 2>'
        raw=payload+b'\0'+b'Q'*(60-len(payload))
        before='/equip body 【装備】 <wait 2>';after='/equip body 【装備】 1 <wait 2>'
        result=saving.patch_line(raw,before,after,lambda t:'装備')
        self.assertIn(token,result);self.assertEqual(result[-1:],b'Q')
        with self.assertRaises(ValueError):saving.patch_line(raw,before,'/equip body 【別装備】 1 <wait 2>',lambda t:'装備')
        long=b'/equip body '+b'a'*48
        with self.assertRaisesRegex(ValueError,'60'):saving.patch_line(long+b'\0',long.decode(),long.decode()+' 1',lambda t:None)
