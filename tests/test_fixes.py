from dataclasses import asdict, replace
import unittest
from ff11reader.domain import InventoryRow, ItemReferenceState
from ff11reader.fixes import plan_fixes, apply_fixes
from test_references import character, slot


def source(slots=None,rows=None):
    return character(slots or [slot()],rows or [InventoryRow(8,5,100)],{i:'loaded' for i in range(17)})


class FixTests(unittest.TestCase):
    def test_unique_candidate_updates_all_references_in_working_copy(self):
        c=source([slot(),slot(name='body')]);before=asdict(c);p=plan_fixes(c)
        self.assertEqual(len(p.changes),2);fixed=apply_fixes(c,p)
        self.assertEqual(asdict(c),before)
        self.assertTrue(all(s.index==5 and s.item_reference.state==ItemReferenceState.MATCH for s in fixed.equipsets[0].slots))
        self.assertTrue(all(s.raw_hex=='' for s in fixed.equipsets[0].slots))
        self.assertFalse(plan_fixes(fixed).changes)

    def test_duplicate_in_other_storage_blocks_unique_fix(self):
        p=plan_fixes(source(rows=[InventoryRow(8,5,100),InventoryRow(1,2,100)]))
        self.assertFalse(p.changes);self.assertEqual(p.issues[0].reason,'multiple_candidates')

    def test_partial_coverage_blocks_fix(self):
        c=source();c.inventory_coverage[16]='missing'
        p=plan_fixes(c);self.assertFalse(p.changes);self.assertEqual(p.issues[0].reason,'incomplete_inventory')

    def test_unique_target_in_every_storage_is_fixable(self):
        for bag in range(17):
            c=source(rows=[InventoryRow(bag,5,100)]);p=plan_fixes(c)
            self.assertEqual(p.changes[0].after,(bag,5))
            fixed=apply_fixes(c,p)
            self.assertEqual(fixed.equipsets[0].slots[0].item_reference.state,ItemReferenceState.MATCH)

    def test_stale_or_altered_plan_is_rejected_atomically(self):
        c=source();p=plan_fixes(c);c.inventory.append(InventoryRow(8,6,200))
        before=asdict(c)
        with self.assertRaises(ValueError):apply_fixes(c,p)
        self.assertEqual(asdict(c),before)
        with self.assertRaises(ValueError):apply_fixes(source(),replace(p,changes=()))

    def test_matching_and_no_reference_slots_are_unchanged(self):
        p=plan_fixes(source([slot(index=5),slot(action='keep'),slot(action='remove')]))
        self.assertFalse(p.changes);self.assertFalse(p.issues)

    def test_no_candidate_and_repeated_position_are_blocked(self):
        p=plan_fixes(source(rows=[InventoryRow(8,5,200)]));self.assertEqual(p.issues[0].reason,'not_observed')
        p=plan_fixes(source(rows=[InventoryRow(8,5,100),InventoryRow(8,5,200)]))
        self.assertEqual(p.issues[0].reason,'ambiguous_target')
