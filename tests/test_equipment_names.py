"""Equipment name edits against generated files only."""
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import unittest
from ff11reader import equipment_saving as saving
from ff11reader.codecs import equipsets
from ff11reader.edit_application import Editor
from ff11reader.elevation import encode, decode
from tests import test_equipment_saving as fixtures


class EquipmentNameTests(unittest.TestCase):
    setUp=fixtures.EquipmentSavingTests.setUp
    load=fixtures.EquipmentSavingTests.load

    def rename(self,number=1,title='新しい名前'):
        edit=self.editor.prepare_equipment_name_edit('abc',number,title)
        self.editor.apply(edit)
        return edit

    def test_history_restart_save_backup_and_undo(self):
        self.editor.undo()  # remove the fixture position fix
        self.rename()
        self.editor.undo();self.assertEqual(self.editor.session.working.characters[0].equipsets[0].title.display,'Test')
        self.editor.redo()
        self.editor=Editor(self.source,self.base/'draft.json')
        plan=self.editor.prepare_equipment_save('abc','all')
        self.assertEqual(len(plan.dependencies),1)
        self.assertEqual(decode(encode(plan)),plan)
        file=plan.files[0]
        changed={i for i,(a,b) in enumerate(zip(file.original,file.replacement)) if a!=b}
        self.assertTrue(changed<=set(range(8,24))|set(range(24,40)))
        self.assertEqual(file.original[40:],file.replacement[40:])
        backup=self.editor.save_equipment(plan,self.base/'backups')
        self.assertEqual((backup/'000.original.dat').read_bytes(),file.original)
        self.assertFalse(self.editor.session.dirty)
        self.editor=Editor(self.load(),self.base/'draft.json')
        self.assertIsNone(self.editor.blocked)
        self.editor.undo();self.assertTrue(self.editor.session.dirty)
        reverse=self.editor.prepare_equipment_save('abc','all')
        self.editor.save_equipment(reverse,self.base/'backups')
        self.assertEqual(equipsets(Path(file.target).read_bytes(),0)[0].title.display,'Test')
        self.editor.redo();self.assertTrue(self.editor.session.dirty)

    def test_mixed_save_and_fix_only_preserves_pending_name(self):
        self.rename()
        all_plan=self.editor.prepare_equipment_save('abc','all')
        self.assertEqual(sum(len(f.changes) for f in all_plan.files),3)
        fix_plan=self.editor.prepare_equipment_save('abc')
        self.assertEqual(fix_plan.deferred,1)
        self.editor.save_equipment(fix_plan,self.base/'backups')
        self.assertTrue(self.editor.session.dirty)
        names=self.editor.prepare_equipment_save('abc','all')
        self.assertEqual(len(names.dependencies),1)
        self.editor.save_equipment(names,self.base/'backups')
        self.assertFalse(self.editor.session.dirty)

    def test_name_only_ignores_inventory_and_rejects_stale_target(self):
        self.editor.undo();self.rename()
        for path in self.folder.glob('*.dat'):
            if not path.name.startswith('es'):path.unlink()
        plan=self.editor.prepare_equipment_save('abc','all')
        target=Path(plan.files[0].target)
        original=target.read_bytes();target.write_bytes(original+b'x')
        with self.assertRaises(ValueError):saving.execute_equipment_save(plan,self.base/'backups')
        target.write_bytes(original)
        self.editor.save_equipment(plan,self.base/'backups')
        self.assertFalse(self.editor.session.dirty)

    def test_noop_and_invalid_name_do_not_write_game_files(self):
        self.editor.undo();cursor=self.editor.session.cursor
        self.rename(title='Test');self.assertEqual(self.editor.session.cursor,cursor)
        for name in ('a'*17,'漢'*9,'emoji😀','{AT:01020304}','【定型文】','a\t'):
            with self.subTest(name=name):
                edit=self.rename(title=name)
                with self.assertRaises(ValueError):self.editor.prepare_equipment_save('abc','all')
                self.editor.undo()
        for f in self.plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)

    def test_tampered_name_plan_and_scope_rejected(self):
        self.editor.undo();self.rename()
        plan=self.editor.prepare_equipment_save('abc','all');f=plan.files[0];c=f.changes[0]
        for bad in (replace(plan,scope='reference-fix'),replace(plan,files=(replace(f,changes=(replace(c,after='Other'),)),)),replace(plan,files=(replace(f,changes=(c,c)),))):
            with self.assertRaises(ValueError):saving.execute_equipment_save(bad,self.base/'backups')
        self.assertEqual(Path(f.target).read_bytes(),f.original)

    def test_backup_restores_name_and_stale_preview_is_rejected(self):
        self.editor.undo();self.rename()
        plan=self.editor.prepare_equipment_save('abc','all')
        self.rename(title='別名')
        with self.assertRaises(ValueError):self.editor.save_equipment(plan,self.base/'backups')
        self.editor.undo()
        backup=self.editor.save_equipment(plan,self.base/'backups')
        saving.restore_equipment_backup(backup,apply=True)
        for f in plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)

    def test_name_batch_failure_rolls_back(self):
        self.editor.undo();self.rename();self.rename(21,'別名')
        plan=self.editor.prepare_equipment_save('abc','all')
        original=saving.os.replace
        def fail(src,dst):
            if Path(dst).name=='es1.dat' and Path(src).name.startswith('.ff11-equipment-'):raise OSError('synthetic failure')
            return original(src,dst)
        with patch.object(saving.os,'replace',side_effect=fail):
            with self.assertRaises((RuntimeError,OSError)):self.editor.save_equipment(plan,self.base/'backups')
        for f in plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)
        self.assertTrue(self.editor.session.dirty)


class NameEncodingTests(unittest.TestCase):
    def test_boundaries_padding_and_empty(self):
        raw=b'Old\0'+b'X'*12
        for name in ('a'*16,'漢'*8,'','A'):
            out=saving.patch_name(raw,'Old',name)
            self.assertEqual(len(out),16)
            length=len(name.encode('cp932'))
            if length<16:
                self.assertEqual(out[length],0)
                self.assertEqual(out[length+1:],raw[length+1:])
        for name in ('a'*17,'漢'*9,'😀','a\n','a\0','a\t'):
            with self.assertRaises(ValueError):saving.patch_name(raw,'Old',name)


@unittest.skipUnless(__import__('os').environ.get('FF11_RUN_INTEGRATION')=='1','Enable Tk integration checks')
class EquipmentNameUITests(unittest.TestCase):
    setUp=fixtures.EquipmentSavingTests.setUp
    load=fixtures.EquipmentSavingTests.load

    def test_edit_preview_history_and_save_preview(self):
        import tkinter as tk
        from tkinter import ttk
        from ff11reader.ui import ReaderWindow
        self.editor.undo()
        app=tk.Tk();app.withdraw();errors=[];app.report_callback_exception=lambda *e:errors.append(e)
        def windows():return [w for w in app.winfo_children() if isinstance(w,tk.Toplevel)]
        try:
            with patch('ff11reader.ui.Editor',return_value=self.editor):view=ReaderWindow(app,self.source)
            view.mode.set('装備セット');view.change_mode();view.nav.selection_set(0);view.select_navigation();app.update()
            self.assertEqual(str(view.equipment_name_button['state']),'normal')
            with patch('ff11reader.ui.dialogs.askstring',return_value='新しい名前'):view.equipment_name_button.invoke()
            app.update();preview=windows()[-1]
            self.assertEqual(view.character.equipsets[0].title.display,'Test')
            button=next(w for w in preview.winfo_children() if isinstance(w,ttk.Button))
            button.invoke();app.update()
            self.assertEqual(view.character.equipsets[0].title.display,'新しい名前')
            view.undo_fix();app.update();self.assertEqual(view.character.equipsets[0].title.display,'Test')
            view.redo_edit();app.update();self.assertEqual(view.character.equipsets[0].title.display,'新しい名前')
            view.preview_equipment_save();app.update()
            detail=next(w for w in windows()[-1].winfo_children() if isinstance(w,tk.Text)).get('1.0','end')
            self.assertIn('前: Test',detail);self.assertIn('後: 新しい名前',detail)
            for f in self.plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)
            view.mode.set('マクロ');view.change_mode();app.update()
            self.assertEqual(str(view.equipment_name_button['state']),'disabled')
            self.assertFalse(errors,errors)
        finally:app.destroy()


class NameBytePreservationTests(unittest.TestCase):
    def test_generated_names_preserve_other_fields(self):
        import hashlib
        import random
        from tests.test_saving import checksum
        for seed in range(200):
            with self.subTest(seed=seed):
                rng=random.Random(seed);page=rng.randrange(10);record=rng.randrange(20)
                raw=bytearray(1624);raw[:8]=rng.randbytes(8)
                offset=24+record*80
                raw[offset:offset+16]=b'Old\0'+rng.randbytes(12)
                raw=checksum(raw)
                name=''.join(rng.choice('Ab9漢字カナ') for _ in range(rng.randrange(9)))
                number=page*20+record+1
                result=saving.patch_file(raw,page,(saving.EquipmentNameChange(number,'Old',name),))
                expected=bytearray(raw);encoded=name.encode('cp932')
                expected[offset:offset+len(encoded)]=encoded
                if len(encoded)<16:expected[offset+len(encoded)]=0
                expected[8:24]=hashlib.md5(expected[24:]).digest()
                self.assertEqual(result,bytes(expected))
                self.assertEqual(equipsets(result,page)[record].title.display,name)
