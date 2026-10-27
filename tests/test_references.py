import unittest
from ff11reader.domain import Character, Equipset, Slot, InventoryRow, Text
from ff11reader.references import compare_equipment


def slot(name='head',item=100,bag=8,index=1,action='equip'):
    return Slot(name,action,item,bag,index,'')


def character(slots,rows=(),coverage=None):
    c=Character('abc');c.equipsets=[Equipset(1,Text('set','','cp932'),tuple(slots))]
    c.inventory=list(rows);c.inventory_coverage=coverage if coverage is not None else {8:'loaded'}
    return c


class ReferenceTests(unittest.TestCase):
    def test_matching_cache_is_not_live_or_individual_confirmation(self):
        r=compare_equipment(character([slot()],[InventoryRow(8,1,100)]))[0]
        self.assertEqual(r.status,'cache_match')
        self.assertEqual(r.certainty,'cache_observation_only')

    def test_wrong_item_retains_observed_and_all_candidates_without_rebinding(self):
        c=character([slot()],[InventoryRow(8,1,200),InventoryRow(8,3,100),InventoryRow(8,4,100)])
        r=compare_equipment(c)[0]
        self.assertEqual(r.status,'cache_item_mismatch')
        self.assertEqual(r.observed_item_ids,(200,))
        self.assertEqual(r.candidates,((8,3),(8,4)))
        self.assertEqual(r.index,1)

    def test_loaded_empty_and_missing_and_unreadable_are_distinct(self):
        for coverage,status in [({8:'loaded'},'cache_position_empty'),({},'cache_unavailable'),({8:'unreadable'},'cache_unavailable')]:
            self.assertEqual(compare_equipment(character([slot()],coverage=coverage))[0].status,status)

    def test_keep_and_remove_are_excluded_and_unknown_is_reported(self):
        c=character([slot(action='keep'),slot(action='remove'),slot(action='unknown')])
        rows=compare_equipment(c)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0].status,'unknown_action')

    def test_invalid_values_are_not_declared_lost(self):
        for kwargs in ({'item':0},{'item':65535},{'index':0},{'index':81},{'bag':17},{'bag':None}):
            self.assertEqual(compare_equipment(character([slot(**kwargs)]))[0].status,'invalid_reference')

    def test_duplicate_position_is_ambiguous(self):
        c=character([slot()],[InventoryRow(8,1,100),InventoryRow(8,1,100)])
        self.assertEqual(compare_equipment(c)[0].status,'ambiguous_position')

    def test_candidates_do_not_cross_character_boundary(self):
        a=character([slot()]);b=character([],[InventoryRow(8,1,100)])
        self.assertEqual(compare_equipment(a)[0].candidates,())
        self.assertEqual(compare_equipment(b),[])

    def test_source_evidence_kept_for_empty_position(self):
        proof={'sha256':'a'*64,'mtime_ns':1}
        r=compare_equipment(character([slot()]),{8:proof})[0]
        self.assertEqual(r.inventory_source,proof)


if __name__=='__main__':unittest.main()
