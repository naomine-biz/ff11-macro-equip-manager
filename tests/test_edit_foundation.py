"""Stage-one contracts; synthetic models and application-owned temporary paths."""
import ast
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ff11reader.domain import Text, Equipset, Slot, ItemReference
from ff11reader.edit_values import SLOT_NAMES, value
from ff11reader.editing import EditSession, Edit, Change, edit_macro, plan_macro_fixes
from ff11reader.edit_application import Editor
from tests.test_editing import snapshot, text, TEMP_ROOT

class FoundationTests(unittest.TestCase):
    def test_semantic_precondition_ignores_source_metadata(self):
        source=snapshot();c=source.characters[0];macro=c.macros[0]
        session=EditSession(source);edit=edit_macro(c,macro,'New',[x.display for x in macro.lines])
        session.working.characters[0].macros[0]=replace(macro,title=replace(macro.title,raw_hex='different',state='resolved'))
        self.assertFalse(session.dirty)
        session.apply(edit);session.undo();self.assertFalse(session.dirty)
        session.redo();self.assertTrue(session.dirty)

    def test_invalid_batch_is_atomic_even_through_generic_apply(self):
        source=snapshot();c=source.characters[0];m=c.macros[0];session=EditSession(source)
        valid=edit_macro(c,m,'New',[x.display for x in m.lines]).changes[0]
        invalid=[replace(valid,after=replace(m,lines=m.lines[:5])),
                 replace(valid,after=replace(m,title=Text('bad\n','','draft'))),
                 replace(valid,after=replace(m,key=11)),
                 replace(valid,after=object()),replace(valid,key=(2,2,'alt',1))]
        for change in invalid:
            with self.assertRaises(ValueError):session.apply(Edit('invalid',(valid,change)))
            self.assertFalse(session.dirty);self.assertEqual(session.cursor,0);self.assertEqual(session.history,[])
        with self.assertRaises(ValueError):session.apply(Edit('duplicate',(valid,valid)))

    def test_dirty_checks_missing_targets_and_character_keys(self):
        source=snapshot();session=EditSession(source)
        session.working.characters[0].macros.clear();self.assertTrue(session.dirty)
        session=EditSession(source);session.working.characters.clear();self.assertTrue(session.dirty)
        session=EditSession(source);session.working.characters.append(deepcopy(session.working.characters[0]))
        with self.assertRaises(ValueError):_ = session.dirty

    def test_read_views_and_preview_are_detached(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            editor=Editor(snapshot(),Path(tmp)/'draft.json')
            exposed=editor.session;exposed.working.characters.clear();exposed.history.append('bad')
            view=editor.snapshot();view.characters[0].macros.clear()
            self.assertEqual(editor.edit_status(),(0,0,False))
            self.assertEqual(len(editor.snapshot().characters[0].macros),1)
            edit=editor.prepare_macro_edit('one',(1,1,'ctrl',1),'New',['']*6)
            editor.apply(edit);editor.undo();self.assertFalse(editor.session.dirty)

    def test_equipment_validation_and_derived_state_undo(self):
        source=snapshot();c=source.characters[0]
        slots=tuple(Slot(n,'keep',None,None,None,'') for n in SLOT_NAMES)
        e=Equipset(1,text('Set'),slots);c.equipsets=[e];session=EditSession(source)
        bad=replace(e,slots=(replace(slots[0],action='equip',item_id=100,container=8,index=0),)+slots[1:])
        with self.assertRaises(ValueError):session.apply(Edit('bad',(Change('one','equipsets',(1,),e,bad),)))
        renamed=replace(e,title=text('New'))
        session.apply(Edit('rename',(Change('one','equipsets',(1,),e,renamed),)))
        self.assertNotEqual(session.working.characters[0].equipsets[0],renamed) # Derived assessments recomputed.
        session.undo();self.assertFalse(session.dirty);session.redo();self.assertTrue(session.dirty)

    def test_noop_still_checks_target_and_does_not_add_history(self):
        source=snapshot();m=source.characters[0].macros[0];session=EditSession(source)
        noop=Change('one','macros',(1,1,'ctrl',1),m,replace(m,title=replace(m.title,raw_hex='other')))
        session.apply(Edit('noop',(noop,)));self.assertEqual(session.cursor,0)
        self.assertEqual(session.working.characters[0].macros[0],m)
        with self.assertRaises(ValueError):session.apply(Edit('missing',(replace(noop,character='missing'),)))
        self.assertFalse(session.dirty)

    def test_dependency_boundaries(self):
        root=Path(__file__).resolve().parents[1]/'ff11reader'
        for name in ('domain','edit_values','editing','fixes','references','save_plan','inventory_observation','macro_inventory','macro_links','wardrobe_usage'):
            tree=ast.parse((root/(name+'.py')).read_text(encoding='utf-8'))
            imports=[n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
            imports += [a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names]
            self.assertFalse(set(imports)&{'pathlib','os','tkinter','saving','adapters','file_transaction'},(name,imports))
        ui=ast.parse((root/'ui.py').read_text(encoding='utf-8'))
        attrs=[n.attr for n in ast.walk(ui) if isinstance(n,ast.Attribute)]
        self.assertNotIn('_session',attrs);self.assertNotIn('session',attrs)
        self.assertNotIn('execute_batch',attrs)
        for name in ('macro_saving','equipment_saving'):
            src=(root/(name+'.py')).read_text(encoding='utf-8')
            self.assertIn('return execute_batch(',src)
            self.assertNotIn('os.replace(',src)
        self.assertNotIn('from .macro_saving', (root/'equipment_saving.py').read_text(encoding='utf-8'))

        legacy=ast.parse((root/'saving.py').read_text(encoding='utf-8'))
        execute=next(n for n in legacy.body if isinstance(n,ast.FunctionDef) and n.name=='execute_save')
        calls=[n.func for n in ast.walk(execute) if isinstance(n,ast.Call)]
        self.assertTrue(any(isinstance(f,ast.Name) and f.id=='execute_batch' for f in calls))
        self.assertFalse(any((isinstance(f,ast.Name) and f.id=='atomic_replace') or
                             (isinstance(f,ast.Attribute) and f.attr in ('write_bytes','replace')) for f in calls))
