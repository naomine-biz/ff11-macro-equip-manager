from dataclasses import asdict,replace
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
from ff11reader.domain import Equipset,Slot,InventoryRow
from ff11reader.application import inspect_wardrobe_usage
from ff11reader.wardrobe_usage import inspect_wardrobes
from ff11reader.editing import EditSession,edit_macro
from tests.test_editing import snapshot,text,TEMP_ROOT


class WardrobeUsageTests(unittest.TestCase):
    def test_scope_and_both_reference_sources(self):
        s=snapshot('/equip body Robe 2');c=s.characters[0]
        s.items.update({101:{'name':'Hat'},102:{'name':'Unused'}})
        c.inventory += [InventoryRow(8,1,101),InventoryRow(16,1,102),InventoryRow(0,1,102)]
        c.equipsets=[Equipset(200,text('Style'),(Slot('head','equip',101,8,1,''),))]
        before=asdict(c);rows=inspect_wardrobe_usage(s,c)
        self.assertEqual([(r.item.item_id,r.state) for r in rows],[(101,'referenced'),(100,'referenced'),(102,'unreferenced')])
        self.assertEqual(asdict(c),before)

    def test_same_name_in_other_storage_can_be_unreferenced(self):
        s=snapshot('/equip body Robe 2');c=s.characters[0];c.inventory.append(InventoryRow(8,2,100))
        self.assertEqual([r.state for r in inspect_wardrobes(c,s.items)],['unreferenced','referenced'])
        c.macros=[replace(c.macros[0],lines=(text('/equip body Robe'),))]
        self.assertTrue(all(r.state=='possible' for r in inspect_wardrobes(c,s.items)))

    def test_broken_equipment_position_and_wrong_macro_storage_are_candidates(self):
        s=snapshot('/equip body Robe 0');c=s.characters[0]
        self.assertEqual(inspect_wardrobes(c,s.items)[0].state,'possible')
        c.macros=[];c.equipsets=[Equipset(1,text(''),(Slot('body','equip',100,8,9,''),))]
        self.assertEqual(inspect_wardrobes(c,s.items)[0].state,'possible')
        c.equipsets=[Equipset(1,text(''),(Slot('body','equip',101,10,3,''),))]
        self.assertEqual(inspect_wardrobes(c,s.items)[0].state,'unreferenced')

    def test_identical_items_and_exact_set_reference(self):
        s=snapshot('/echo hi');c=s.characters[0];c.inventory.append(InventoryRow(10,4,100))
        c.equipsets=[Equipset(1,text(''),(Slot('body','equip',100,10,3,''),))]
        self.assertEqual([r.state for r in inspect_wardrobes(c,s.items)],['referenced','unreferenced'])
        c.macros=[replace(c.macros[0],lines=(text('/equip body Robe 2'),))]
        self.assertEqual([r.state for r in inspect_wardrobes(c,s.items)],['referenced','possible'])

    def test_read_failures_and_unresolved_name_are_deferred(self):
        s=snapshot('/echo hi');c=s.characters[0]
        s.diagnostics=[{'code':'source_unreadable','path':str(Path('USER')/'one'/'mcr3.dat')}]
        self.assertEqual(inspect_wardrobe_usage(s,c)[0].state,'incomplete')
        s.diagnostics=[];s.items={}
        self.assertEqual(inspect_wardrobe_usage(s,c)[0].state,'incomplete')

    def test_edit_and_undo_recompute_without_cross_character_references(self):
        s=snapshot('/equip body Robe 2');session=EditSession(s);c=session.working.characters[0];m=c.macros[0]
        session.apply(edit_macro(c,m,m.title.display,['/echo hi','','','','','']))
        self.assertEqual(inspect_wardrobe_usage(session.working,session.working.characters[0])[0].state,'unreferenced')
        session.undo()
        self.assertEqual(inspect_wardrobe_usage(session.working,session.working.characters[0])[0].state,'referenced')
        with self.assertRaises(ValueError):inspect_wardrobe_usage(s,replace(c,folder_id='other'))

    @unittest.skipUnless(os.environ.get('FF11_RUN_INTEGRATION')=='1','Enable Tk checks')
    def test_list_filter_and_inventory_navigation(self):
        import tkinter as tk
        from tkinter import ttk
        from ff11reader.ui import ReaderWindow
        from ff11reader.edit_application import Editor
        s=snapshot();c=s.characters[0]
        s.items[101]={'name':'Unused'};c.inventory+=[InventoryRow(8,2,100),InventoryRow(16,7,101)]
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            app=tk.Tk();app.withdraw();errors=[];app.report_callback_exception=lambda *e:errors.append(e)
            try:
                with patch('ff11reader.ui.Editor',side_effect=lambda source:Editor(source,Path(tmp)/'draft.json')):view=ReaderWindow(app,s)
                view.show_unused_wardrobe();app.update()
                window=next(w for w in app.winfo_children() if isinstance(w,tk.Toplevel))
                def descendants(w):
                    for child in w.winfo_children():yield child;yield from descendants(child)
                widgets=list(descendants(window));tree=next(w for w in widgets if isinstance(w,ttk.Treeview));choice=next(w for w in widgets if isinstance(w,ttk.Combobox))
                self.assertEqual(len(tree.get_children()),1)
                self.assertIn('Unused',tree.item('0','values'))
                choice.current(1);choice.event_generate('<<ComboboxSelected>>');app.update();self.assertEqual(len(tree.get_children()),2)
                choice.current(0);choice.event_generate('<<ComboboxSelected>>');app.update()
                next(w for w in widgets if isinstance(w,ttk.Button) and w.cget('text')=='インベントリで開く').invoke();app.update()
                self.assertEqual(view.mode.get(),'インベントリ');self.assertEqual(view.selected,16)
                self.assertIn('Unused',view.detail.get('1.0','end'));self.assertFalse(errors,errors)
            finally:app.destroy()
