"""Synthetic slot selection, serialization, guarded save and UI tests."""
from dataclasses import replace
from pathlib import Path
import os
import struct
import unittest
from unittest.mock import patch
from ff11reader import codecs, equipment_saving as saving
from ff11reader.edit_application import Editor
from ff11reader.equipment_editing import candidates
from ff11reader.edit_values import slot_value
from ff11reader.elevation import encode, decode
from ff11reader.fixes import plan_fixes
from tests import test_equipment_saving as fixtures
from tests.test_saving import checksum


def record(item,mask,name):
    b=bytearray(0x1400);struct.pack_into('<H',b,0,item);struct.pack_into('<H',b,0x12,mask)
    pos=0x3C if 0x4000<=item<0x5A00 else 0x30 if 0x2800<=item<0x7000 else 0x1C
    struct.pack_into('<III',b,pos,1,12,0)
    encoded=name.encode('cp932');b[pos+40:pos+40+len(encoded)]=encoded
    return bytes(((v<<5)|(v>>3))&255 for v in b)


class SlotFixture(unittest.TestCase):
    def setUp(self):
        fixtures.EquipmentSavingTests.setUp(self)
        self.master=self.base/'game'/'ROM'/'1'/'1.DAT';self.master.parent.mkdir(parents=True)
        self.master.write_bytes(record(0x4001,3,'剣')+record(0x2801,32,'胴装備')+record(0x2802,0x1800,'耳装備')+record(0x2803,0x6000,'指装備'))
        self.table=self.base/'game'/'FTABLE.DAT';table=bytearray((max(codecs.DAT_IDS)+1)*2)
        for logical in codecs.DAT_IDS:struct.pack_into('<H',table,logical*2,129)
        self.table.write_bytes(table)
        for bag,entries in ((1,[(3,0x4001)]),(8,[(6,0x4001),(7,0x2801),(8,0x2802),(9,0x2803)])):
            path=self.folder/next(n for n,b in codecs.BAGS.items() if b==bag)
            raw=bytearray(path.read_bytes())
            for index,item in entries:struct.pack_into('<BBH',raw,0xA3C+index*20+16,index,0,item)
            path.write_bytes(checksum(raw))
        self.source=self.load();self.editor=Editor(self.source,self.base/'slot-draft.json')
        self.original={p:p.read_bytes() for p in self.base.joinpath('game').rglob('*.dat')}

    def load(self):
        source=fixtures.EquipmentSavingTests.load(self)
        if hasattr(self,'master'):
            source.items.update({i:dict(v,source_path=str(self.master.resolve())) for i,v in codecs.item_records(self.master.read_bytes()).items()})
            source.sources.extend({'path':str(p.resolve()),'sha256':saving.digest(p.read_bytes())} for p in (self.master,self.table))
        return source

    def edit(self,slot='main',action='equip',selection=(0x4001,1,3),number=1):
        edit=self.editor.prepare_equipment_slot_edit('abc',number,slot,action,selection)
        self.editor.apply(edit);return edit

    def preview(self):return self.editor.prepare_equipment_save('abc','all')


class SlotEditingTests(SlotFixture):
    def test_candidates_all_storage_and_multi_slot_masks(self):
        c=self.source.characters[0]
        self.assertEqual([(r.container,r.index) for r in candidates(c,self.source.items,'main')],[(1,3),(8,6)])
        self.assertEqual(len(candidates(c,self.source.items,'body')),1)
        for slot in ('ear1','ear2','ring1','ring2'):self.assertEqual(len(candidates(c,self.source.items,slot)),1)
        self.assertEqual(len(candidates(c,self.source.items,'main','16385')),2)
        for selection in ((0x2801,8,7),(0x4001,1,4),(0x4001,8,7)):
            with self.assertRaises(ValueError):self.editor.prepare_equipment_slot_edit('abc',1,'main','equip',selection)
        self.assertEqual(self.editor.session.cursor,0)

    def test_history_save_reopen_and_reverse_save(self):
        self.edit();self.editor.undo();self.assertEqual(self.editor.session.working.characters[0].equipsets[0].slots[0].item_id,100)
        self.editor.redo();self.edit('body','equip',(0x2801,8,7))
        plan=self.preview();self.assertEqual(decode(encode(plan)),plan)
        self.assertEqual(len(plan.dependencies),5)  # es, two storage files, FTABLE, one catalog
        for f in plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)
        backup=self.editor.save_equipment(plan,self.base/'backups')
        self.assertEqual((backup/'000.original.dat').read_bytes(),plan.files[0].original)
        self.assertFalse(self.editor.session.dirty)
        reopened=Editor(self.load(),self.base/'slot-draft.json');self.assertIsNone(reopened.blocked)
        reopened.undo();self.assertTrue(reopened.session.dirty)
        reverse=reopened.prepare_equipment_save('abc','all')
        reopened.save_equipment(reverse,self.base/'backups')
        self.assertEqual(self.load().characters[0].equipsets[0].slots[5].action,'keep')
        reopened.redo();self.assertTrue(reopened.session.dirty)
        for p,raw in self.original.items():
            if p.name!='es0.dat':self.assertEqual(p.read_bytes(),raw)

    def test_keep_remove_need_no_inventory_or_dictionary(self):
        for name in ('keep','remove'):
            with self.subTest(action=name):
                self.edit(action=name,selection=None)
                plan=self.preview();self.assertEqual(len(plan.dependencies),1)
                f=plan.files[0];slot=codecs.equipsets(f.replacement,0)[0].slots[0]
                self.assertEqual(slot_value(slot),('main',name,None,None,None))
                changed={i for i,(a,b) in enumerate(zip(f.original,f.replacement)) if a!=b}
                self.assertTrue(changed<=set(range(8,24))|{40})
                self.editor.undo()

    def test_stale_sources_tampering_and_missing_evidence(self):
        self.edit();plan=self.preview()
        for path in (self.master,self.table,self.folder/'bs.dat',self.folder/'es0.dat'):
            raw=path.read_bytes();path.write_bytes(raw+b'x')
            with self.assertRaises(ValueError):saving.execute_equipment_save(plan,self.base/'backups')
            path.write_bytes(raw)
        f=plan.files[0];change=f.changes[0]
        for bad in (replace(plan,dependencies=()),replace(plan,catalogs=()),replace(plan,scope='reference-fix'),replace(plan,files=(replace(f,changes=(replace(change,after=('equip',0x2801,8,7)),)),))):
            with self.assertRaises(ValueError):saving.execute_equipment_save(bad,self.base/'backups')
        self.assertEqual(Path(f.target).read_bytes(),f.original)
        self.assertFalse((self.base/'backups').exists())

    def test_rechecks_slot_mask_even_with_updated_dependency_hash(self):
        self.edit();plan=self.preview()
        self.master.write_bytes(record(0x4001,32,'剣'))
        forged=replace(plan,dependencies=tuple((p,saving.digest(self.master.read_bytes()) if Path(p)==self.master else h) for p,h in plan.dependencies))
        with self.assertRaisesRegex(ValueError,'部位'):saving.execute_equipment_save(forged,self.base/'backups')
        for f in plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)

    def test_manual_choice_preserves_other_fix_rules(self):
        original=plan_fixes(self.source.characters[0])
        self.edit()
        current=self.editor.session.working.characters[0]
        self.assertEqual(str(current.equipsets[0].slots[0].item_reference.state),'match')
        self.assertEqual([x for x in plan_fixes(current).changes if x.equipset==21],[x for x in original.changes if x.equipset==21])
        self.editor.undo()
        self.assertEqual(plan_fixes(self.editor.session.working.characters[0]).changes,original.changes)

    def test_noop_stale_preview_and_inventory_collision(self):
        self.edit();cursor=self.editor.session.cursor;self.edit();self.assertEqual(self.editor.session.cursor,cursor)
        plan=self.preview();self.edit('body','equip',(0x2801,8,7))
        with self.assertRaises(ValueError):self.editor.save_equipment(plan,self.base/'backups')
        from ff11reader.equipment_editing import validate_selection
        c=self.source.characters[0];row=next(r for r in c.inventory if r.container==1 and r.index==3)
        c.inventory.append(row)
        slot=self.editor.session.working.characters[0].equipsets[0].slots[0]
        with self.assertRaises(ValueError):validate_selection(c,self.source.items,slot)

    def test_fix_only_scope_retains_manual_edit(self):
        self.editor.equipment_fixes('abc',plan_fixes(self.source.characters[0]))
        self.edit('body','equip',(0x2801,8,7))
        plan=self.editor.prepare_equipment_save('abc');self.assertEqual(plan.deferred,1)
        self.editor.save_equipment(plan,self.base/'backups')
        self.assertTrue(self.editor.session.dirty)
        self.editor.save_equipment(self.preview(),self.base/'backups');self.assertFalse(self.editor.session.dirty)

    def test_slot_batch_failure_restores_originals(self):
        self.edit();self.edit(number=21)
        plan=self.preview();original=saving.os.replace
        def fail(src,dst):
            if Path(dst).name=='es1.dat' and Path(src).name.startswith('.ff11-equipment-'):raise OSError('synthetic failure')
            return original(src,dst)
        with patch.object(saving.os,'replace',side_effect=fail):
            with self.assertRaises(RuntimeError):self.editor.save_equipment(plan,self.base/'backups')
        for f in plan.files:self.assertEqual(Path(f.target).read_bytes(),f.original)
        self.assertTrue(self.editor.session.dirty)


class SlotCodecTests(unittest.TestCase):
    def test_master_slot_masks_and_non_equipment(self):
        items=codecs.item_records(record(0x2801,0x1800,'耳')+record(1,0xFFFF,'素材'))
        self.assertEqual(items[0x2801]['equip_slots'],('ear1','ear2'))
        self.assertEqual(items[1]['equip_slots'],())


@unittest.skipUnless(os.environ.get('FF11_RUN_INTEGRATION')=='1','Enable Tk checks')
class SlotUITests(SlotFixture):
    def test_selection_preview_undo_redo_and_save_preview(self):
        import tkinter as tk
        from tkinter import ttk
        from ff11reader.ui import ReaderWindow
        app=tk.Tk();app.withdraw();errors=[];app.report_callback_exception=lambda *e:errors.append(e)
        try:
            with patch('ff11reader.ui.Editor',return_value=self.editor):view=ReaderWindow(app,self.source)
            view.nav.selection_set(0);view.select_navigation();view.inspect_slot(view.selected.slots[0]);view.slot_edit_button.invoke();app.update()
            edit=view.slot_editor;self.assertEqual(len(edit.visible),2)
            edit.query.set('剣');edit.filter();edit.action.set('equip');edit.toggle();edit.listing.selection_set('0');edit.preview_button.invoke();app.update()
            preview=[w for w in app.winfo_children() if isinstance(w,tk.Toplevel) and w is not edit.window][-1]
            detail=next(w for w in preview.winfo_children() if isinstance(w,tk.Text)).get('1.0','end')
            self.assertIn('剣',detail);self.assertIn('モグ金庫',detail)
            next(w for w in preview.winfo_children() if isinstance(w,ttk.Button)).invoke();app.update()
            self.assertEqual(view.character.equipsets[0].slots[0].container,1)
            view.undo_fix();app.update();self.assertEqual(view.character.equipsets[0].slots[0].item_id,100)
            view.redo_edit();view.preview_equipment_save();app.update()
            self.assertFalse(errors,errors)
            for p,raw in self.original.items():self.assertEqual(p.read_bytes(),raw)
        finally:app.destroy()


class SlotByteProperties(unittest.TestCase):
    def test_generated_action_transitions_preserve_other_bytes(self):
        import hashlib
        import random
        for seed in range(240):
            with self.subTest(seed=seed):
                rng=random.Random(seed);page=rng.randrange(10);number=page*20+rng.randrange(20)+1
                index=rng.randrange(16);name=codecs.SLOTS[index]
                offset=24+(number-1)%20*80+16+index*4
                raw=bytearray(1624);raw[:8]=rng.randbytes(8)
                raw[offset:offset+4]=rng.randbytes(4);raw[offset]=(raw[offset]&0xFC)|(seed%3)
                original=checksum(raw);before=codecs.equipsets(original,page)[(number-1)%20].slots[index]
                action=('keep','remove','equip')[(seed//3)%3]
                fields=(action,rng.randrange(1,65535),rng.randrange(17),rng.randrange(1,81)) if action=='equip' else (action,None,None,None)
                change=saving.EquipmentSlotChange(number,name,saving.slot_fields(before),fields)
                actual=saving.patch_file(original,page,(change,))
                expected=bytearray(original)
                if action=='equip':struct.pack_into('<BBH',expected,offset,fields[2]*4+1,fields[3],fields[1])
                else:expected[offset]=(expected[offset]&0xFC)|(0 if action=='keep' else 2)
                expected[8:24]=hashlib.md5(expected[24:]).digest()
                self.assertEqual(actual,bytes(expected))
                decoded=codecs.equipsets(actual,page)[(number-1)%20].slots[index]
                self.assertEqual(saving.slot_fields(decoded),fields)
