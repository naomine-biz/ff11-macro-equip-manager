"""Ownership and transactional regression tests for persistent edit state."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest
from unittest.mock import patch
from ff11reader.domain import ItemReference, Text
from ff11reader.editing import EditSession, Edit, Change, edit_macro
from ff11reader.edit_application import Editor
from tests.test_editing_properties import source
from tests.property_support import isolated


class PersistentStateTests(unittest.TestCase):
    def test_input_views_history_and_forks_are_isolated(self):
        with isolated() as base:
            original=source(base)
            c=original.characters[0];e=c.equipsets[0]
            ref=ItemReference(inventory_source={'nested':{'values':[1,2]}})
            e=replace(e,slots=tuple(replace(slot,item_reference=ref) for slot in e.slots))
            c.equipsets=[e]
            session=EditSession(original);before=session.working
            ref.inventory_source['nested']['values'].clear()
            self.assertEqual(session.working,before)
            for view in (session.working,session.baseline,session.saved):
                view.characters[0].equipsets[0].slots[0].item_reference.inventory_source['nested']['values'].clear()
                view.characters[0].macros.clear()
            self.assertEqual(session.working,before)
            fork=session.fork()
            c=fork.character('a');m=c.macros[0]
            fork.apply(edit_macro(c,m,'branch',[x.display for x in m.lines]))
            self.assertFalse(session.dirty);self.assertTrue(fork.dirty)
            exported=fork.history;exported.clear()
            self.assertEqual(fork.history_length(),1)
            fork.undo();self.assertFalse(fork.dirty);fork.redo();self.assertTrue(fork.dirty)
            self.assertEqual(session.working,before)

    def test_incremental_view_reuses_detached_values_and_repairs_mutation(self):
        with isolated() as base:
            editor=Editor(source(base),base/'draft.json')
            before=editor.snapshot()
            edit=editor.prepare_macro_edit('a',(1,1,'ctrl',1),'Changed',['']*6)
            editor.apply(edit)
            after=editor.snapshot(before)
            self.assertIs(after.characters[1],before.characters[1])
            self.assertIs(after.characters[0].macros[1],before.characters[0].macros[1])
            self.assertEqual(before.characters[0].macros[0].title.display,'Base')
            after.characters[1].macros.clear()
            after.items[100]['name']='outside'
            repaired=editor.snapshot(after)
            self.assertEqual(len(repaired.characters[1].macros),2)
            self.assertEqual(repaired.items[100]['name'],'Robe')
            self.assertEqual(repaired,editor.snapshot())
            editor.undo();undone=editor.snapshot(repaired)
            self.assertEqual(undone.characters[0].macros[0].title.display,'Base')

    def test_draft_failure_leaves_all_roots_and_history_unchanged(self):
        with isolated() as base:
            editor=Editor(source(base),base/'draft.json')
            editor.apply(editor.prepare_macro_edit('a',(1,1,'ctrl',1),'Changed',['']*6))
            for operation in (editor.undo,lambda:editor.apply(editor.prepare_macro_edit('a',(1,1,'ctrl',1),'Other',['']*6))):
                state=editor.snapshot();baseline=editor.session.baseline;saved=editor.session.saved
                history=editor.session.history;status=editor.edit_status();raw=(base/'draft.json').read_bytes()
                with patch.object(editor.store,'save',side_effect=OSError('synthetic')):
                    with self.assertRaises(OSError):operation()
                self.assertEqual(editor.snapshot(),state)
                self.assertEqual(editor.session.baseline,baseline);self.assertEqual(editor.session.saved,saved)
                self.assertEqual(editor.session.history,history);self.assertEqual(editor.edit_status(),status)
                self.assertEqual((base/'draft.json').read_bytes(),raw)

    def test_baseline_json_cache_preserves_v3_and_invalidates_on_reset(self):
        with isolated() as base:
            editor=Editor(source(base),base/'draft.json')
            editor.apply(editor.prepare_macro_edit('a',(1,1,'ctrl',1),'Changed',['']*6))
            first=json.loads((base/'draft.json').read_text(encoding='utf-8'))
            with patch.object(EditSession,'baseline_records',side_effect=AssertionError('baseline encoded twice')):
                editor.undo();editor.redo()
            second=json.loads((base/'draft.json').read_text(encoding='utf-8'))
            self.assertEqual(first['baseline'],second['baseline']);self.assertEqual(second['version'],3)
            editor.start_fresh()
            editor.apply(editor.prepare_macro_edit('a',(1,1,'ctrl',1),'Reset',['']*6))
            reopened=Editor(source(base),base/'draft.json')
            self.assertIsNone(reopened.blocked);self.assertEqual(reopened.snapshot(),editor.snapshot())

    def test_incoming_edit_and_exposed_history_cannot_change_internal_values(self):
        with isolated() as base:
            session=EditSession(source(base));c=session.character('a');e=c.equipsets[0]
            reference=ItemReference(inventory_source={'nested':[1]})
            changed=replace(e,title=Text('New','','draft'),slots=tuple(replace(s,item_reference=reference) for s in e.slots))
            edit=Edit('rename',(Change('a','equipsets',(1,),e,changed),))
            session.apply(edit);state=session.working
            reference.inventory_source['nested'].clear()
            exported=session.history
            exported[0].changes[0].after.slots[0].item_reference.inventory_source['nested'].append(2)
            self.assertEqual(session.history[0].changes[0].after.slots[0].item_reference.inventory_source['nested'],[1])
            self.assertEqual(session.working,state)
            session.undo();session.redo();self.assertEqual(session.working,state)

    def test_fork_shares_unchanged_entries_without_copying_catalog(self):
        with isolated() as base:
            original=source(base);original.items[999]={'large':['synthetic']*10000}
            session=EditSession(original);fork=session.fork()
            before=session._working
            self.assertIs(before,fork._working)
            c=original.characters[0];m=c.macros[0]
            with patch('ff11reader.edit_state.deepcopy',wraps=deepcopy) as copying:
                fork.apply(edit_macro(c,m,'Changed',[line.display for line in m.lines]))
            after=fork._working
            self.assertIs(before._entries['b','macros',(1,1,'ctrl',1)],after._entries['b','macros',(1,1,'ctrl',1)])
            self.assertIsNot(before._entries['a','macros',(1,1,'ctrl',1)],after._entries['a','macros',(1,1,'ctrl',1)])
            self.assertTrue(all(call.args[0] is not before._template.items for call in copying.call_args_list))
            self.assertFalse(session.dirty);self.assertTrue(fork.dirty)
