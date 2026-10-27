import unittest
from ff11reader.domain import InventoryRow
from ff11reader.fixes import plan_fixes
from ff11reader.references import assess_equipment
from ff11reader.presentation import present_slot
from test_references import character, slot


class PresentationTests(unittest.TestCase):
    def status(self,rows,coverage=None):
        c=character([slot()],rows,coverage or {i:'loaded' for i in range(17)})
        c.equipsets=assess_equipment(c)
        return present_slot(c.equipsets[0].slots[0],1,plan_fixes(c))

    def test_four_main_actions(self):
        self.assertEqual(self.status([InventoryRow(8,1,100)]).status,'match')
        view=self.status([InventoryRow(8,5,100)])
        self.assertEqual(view.status,'fixable');self.assertEqual(view.change.after,(8,5))
        self.assertEqual(self.status([InventoryRow(8,5,100),InventoryRow(8,6,100)]).status,'multiple')
        self.assertEqual(self.status([]).status,'missing')

    def test_fixable_is_never_shown_for_domain_blocked_plan(self):
        for rows,coverage in [([InventoryRow(8,5,100,quantity=2)],None),
                              ([InventoryRow(8,5,100)],{8:'loaded'})]:
            self.assertEqual(self.status(rows,coverage).status,'needs_review')

    def test_unique_item_in_safe_is_fixable_for_style_sets(self):
        self.assertEqual(self.status([InventoryRow(1,5,100)]).status,'fixable')

    def test_exact_match_keeps_priority_over_other_candidates(self):
        self.assertEqual(self.status([InventoryRow(8,1,100),InventoryRow(8,5,100)]).status,'match')


if __name__=='__main__':unittest.main()
