import tempfile
from copy import deepcopy
from pathlib import Path
from dataclasses import replace
import unittest
from unittest.mock import patch
from ff11reader.domain import Character, Macro, Text, InventoryRow, Snapshot, Slot, Equipset
from ff11reader.references import assess_equipment
from ff11reader.fixes import plan_fixes
from ff11reader.macro_inventory import assess_macro_inventory, parse_equip
from ff11reader.editing import EditSession, Edit, Change, edit_macro, plan_macro_fixes
from ff11reader.edit_application import Editor
from ff11reader.draft_store import DraftStore


TEMP_ROOT=Path(__file__).resolve().parents[1]/'work'/'edit-tests'
TEMP_ROOT.mkdir(parents=True,exist_ok=True)

def text(s):
    return Text(s, s.encode('utf-8').hex(), 'test')


def snapshot(line='/equip body "Robe" <wait 2>'):
    macro=Macro(1,1,'ctrl',1,text('Regen'),tuple(text(s) for s in [line,'','','','','']))
    c=Character('one',macros=[macro],inventory=[InventoryRow(10,3,100)],inventory_coverage={n:'loaded' for n in range(17)})
    return Snapshot('id','now',[c],{100:{'name':'Robe'}},[{'path':'fixture','sha256':'abc'}],[],'test')


class MacroInventoryTests(unittest.TestCase):
    def assess(self,line,rows,coverage=None):
        s=snapshot(line);c=s.characters[0];c.inventory=rows
        if coverage is not None:c.inventory_coverage=coverage
        return assess_macro_inventory(c,s.items)[0]

    def test_storage_mapping_and_suffix_preservation(self):
        for number,bag in [(0,0),(1,8),(2,10),(8,16)]:
            line='【/equip】 【胴】 【Robe】  <wait 2>'
            r=self.assess(line,[InventoryRow(bag,3,100)])
            self.assertEqual(r.state,'unspecified_unique')
            self.assertEqual(r.replacement,f'【/equip】 【胴】 【Robe】 {number}  <wait 2>')
        for slot in ('メインウェポン','サブウェポン','レンジウェポン','左手の指','右手の指'):
            self.assertTrue(parse_equip(f'【/equip】 【{slot}】 【Robe】 2').valid)
        r=self.assess('/equip body "Robe" 1<wait.2>',[InventoryRow(10,3,100)])
        self.assertEqual(r.state,'wrong_unique')
        self.assertEqual(r.replacement,'/equip body "Robe" 2<wait.2>')

    def test_state_matrix(self):
        a=InventoryRow(10,3,100);b=InventoryRow(10,4,100);c=InventoryRow(8,5,100)
        cases=[('/equip body Robe 2',[a,c],'match'),
               ('/equip body Robe',[a,c],'unspecified_multiple'),
               ('/equip body Robe 2',[a,b],'same_storage_multiple'),
               ('/equip body Robe 0',[a,c],'elsewhere_multiple'),
               ('/equip body Robe 0',[],'missing'),
               ('/equip body Robe',[InventoryRow(1,3,100)],'unavailable_storage'),
               ('/equip body Robe 9',[a],'invalid'),
               ('/equip body',[],'remove')]
        for line,rows,state in cases:
            r=self.assess(line,rows)
            self.assertEqual(r.state,state,(line,rows));self.assertIsNone(r.replacement)

    def test_incomplete_or_duplicate_positions_never_fix(self):
        row=InventoryRow(10,3,100)
        self.assertEqual(self.assess('/equip body Robe',[row],{}).state,'incomplete')
        self.assertIsNone(self.assess('/equip body Robe',[row,row]).replacement)
        self.assertIsNone(parse_equip('/echo /equip body Robe'))
        self.assertFalse(parse_equip('/equip body Robe abc').valid)
        nested=parse_equip('/equip 胴 【勝負服【青】】 2')
        self.assertTrue(nested.valid);self.assertEqual(nested.item_name,'勝負服【青】')


class EditingTests(unittest.TestCase):
    def test_batch_undo_redo_branch_and_raw_preservation(self):
        s=snapshot();c=s.characters[0]
        c.macros.append(replace(c.macros[0],key=2))
        session=EditSession(s);plan=plan_macro_fixes(c,s.items)
        session.apply(plan)
        self.assertEqual(session.cursor,1)
        self.assertTrue(all(m.lines[0].display.endswith('2 <wait 2>') for m in session.working.characters[0].macros))
        self.assertEqual(c.macros[0].lines[0].display,'/equip body "Robe" <wait 2>')
        session.undo();self.assertFalse(session.dirty)
        self.assertEqual(session.working.characters[0].macros,c.macros)
        session.redo();self.assertTrue(session.dirty)
        session.undo();m=session.working.characters[0].macros[0]
        session.apply(edit_macro(c,m,'New',[l.display for l in m.lines]))
        self.assertEqual(len(session.history),1)
        self.assertEqual(session.working.characters[0].macros[0].lines,m.lines)
        session.redo();self.assertEqual(session.cursor,1)

    def test_stale_batch_is_atomic_and_cross_character(self):
        s=snapshot();c=s.characters[0];other=replace(deepcopy(c),folder_id='two');s.characters.append(other)
        session=EditSession(s);m=c.macros[0]
        edit=edit_macro(c,m,'New',[l.display for l in m.lines])
        bad=Change('two','macros',(1,1,'ctrl',1),replace(m,title=text('stale')),m)
        with self.assertRaises(ValueError):session.apply(Edit('batch',edit.changes+(bad,)))
        self.assertFalse(session.dirty);self.assertEqual(session.cursor,0)
        good=edit_macro(other,m,'Other',[l.display for l in m.lines])
        session.apply(Edit('batch',edit.changes+good.changes));session.undo();self.assertFalse(session.dirty)

    def test_persistence_redo_conflict_and_failed_save(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            path=Path(tmp)/'draft.json';s=snapshot();c=s.characters[0]
            editor=Editor(s,path);plan=plan_macro_fixes(c,s.items)
            editor.macro_fixes('one',plan);editor.undo()
            resumed=Editor(s,path);self.assertFalse(resumed.blocked);self.assertEqual(len(resumed.session.history),1)
            resumed.redo();self.assertTrue(resumed.session.dirty)
            with self.assertRaises(ValueError):editor.redo()  # second app instance
            self.assertFalse(path.with_suffix('.lock').exists())
            with patch.object(resumed.store,'save',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):resumed.undo()
            self.assertTrue(resumed.session.dirty)
            changed=snapshot();changed.sources[0]['sha256']='changed'
            conflict=Editor(changed,path);self.assertTrue(conflict.blocked)
            before=path.read_bytes()
            with self.assertRaises(ValueError):conflict.undo()
            self.assertEqual(before,path.read_bytes())
            conflict.start_fresh();self.assertTrue(list(Path(tmp).glob('*.archived-*.json')))

    def test_fix_recomputed_and_no_game_save_dependency(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            s=snapshot();e=Editor(s,Path(tmp)/'draft.json');plan=plan_macro_fixes(s.characters[0],s.items)
            # Simulate changed input via a new read, not a mutation of the public view.
            s.characters[0].inventory.append(InventoryRow(8,4,100))
            e=Editor(s,Path(tmp)/'draft.json')
            with self.assertRaises(ValueError):e.macro_fixes('one',plan)
            self.assertEqual(e.session.cursor,0)

    def test_corrupt_draft_is_preserved(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            path=Path(tmp)/'draft.json';path.write_text('broken')
            e=Editor(snapshot(),path);self.assertTrue(e.blocked)
            self.assertEqual(path.read_text(),'broken')

    def test_equipment_and_macro_share_persistent_history(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            s=snapshot();c=s.characters[0]
            from ff11reader.edit_values import SLOT_NAMES
            c.equipsets=[Equipset(1,text('Set'),tuple(Slot(n,'equip',100,10,9,'') if n=='body' else Slot(n,'keep',None,None,None,'') for n in SLOT_NAMES))]
            c.equipsets=assess_equipment(c,{10:{'path':'inventory','sha256':'abc'}})
            path=Path(tmp)/'draft.json';e=Editor(s,path)
            e.equipment_fixes('one',plan_fixes(c))
            e.macro_fixes('one',plan_macro_fixes(e.session.working.characters[0],s.items))
            resumed=Editor(s,path);self.assertFalse(resumed.blocked)
            resumed.undo();self.assertEqual(resumed.session.working.characters[0].equipsets[0].slots[5].index,3)
            resumed.undo();self.assertFalse(resumed.session.dirty)
            resumed.redo();self.assertEqual(resumed.session.working.characters[0].equipsets[0].slots[5].index,3)
