"""Requirement regressions: synthetic values only (GAP-01..04)."""
from dataclasses import asdict, replace
import unittest
from ff11reader.domain import Character, Equipset, InventoryRow, Macro, Slot, Text, ItemReferenceState as State
from ff11reader.edit_values import SLOT_NAMES
from ff11reader.macro_inventory import assess_macro_inventory
from ff11reader.references import assess_equipment
from ff11reader.fixes import plan_fixes, apply_fixes
from ff11reader.presentation import present_slot
from ff11reader.wardrobe_usage import inspect_wardrobes


def source(line='/equip body Robe 1'):
    text=lambda s: Text(s, '', 'test')
    macro=Macro(1,1,'ctrl',1,text('Test'),tuple(text(s) for s in [line,'','','','','']))
    slots=tuple(Slot(n,'equip',100,8,13,'00') if n=='body' else Slot(n,'keep',None,None,None,'00') for n in SLOT_NAMES)
    return Character('synthetic',macros=[macro],equipsets=[Equipset(1,text('Set'),slots)],
                     inventory=[InventoryRow(8,11,100)],inventory_coverage={i:'loaded' for i in range(17)})

ITEMS={100:{'name':'Robe'},200:{'name':'Other'}}

class ReferenceRegressions(unittest.TestCase):
    def test_explicit_storage_match_is_local(self):
        # MAC-002 / PT-09: other storage does not invalidate an explicit match.
        c=source();c.inventory_coverage[1]='missing'
        self.assertEqual(assess_macro_inventory(c,ITEMS)[0].state,'match')
        c.macros=[replace(c.macros[0],lines=(Text('/equip body Robe','','test'),)+c.macros[0].lines[1:])]
        self.assertEqual(assess_macro_inventory(c,ITEMS)[0].state,'incomplete')

    def test_unrelated_invalid_candidate_does_not_hide_explicit_match(self):
        c=source();c.inventory.append(InventoryRow(10,0,100))
        self.assertEqual(assess_macro_inventory(c,ITEMS)[0].state,'match')
        c.inventory.append(InventoryRow(8,11,200))
        self.assertEqual(assess_macro_inventory(c,ITEMS)[0].state,'incomplete')

    def test_slot_and_plan_share_blocking_reason(self):
        # EQ-004 / D-01: quantity and coverage are part of the slot assessment.
        for reason in ('quantity_not_one','incomplete_inventory','ambiguous_target'):
            with self.subTest(reason=reason):
                c=source()
                if reason=='quantity_not_one':c.inventory=[InventoryRow(8,11,100,2)]
                elif reason=='incomplete_inventory':
                    c.inventory=[InventoryRow(8,13,100)];c.inventory_coverage[8]='missing'
                else:c.inventory.append(InventoryRow(8,11,200))
                c.equipsets=assess_equipment(c);slot=c.equipsets[0].slots[5]
                plan=plan_fixes(c)
                self.assertEqual(slot.item_reference.state,State.INSUFFICIENT_DATA)
                self.assertEqual(slot.item_reference.reason,reason)
                self.assertIsNone(slot.item_reference.fix_target)
                self.assertEqual([(x.slot,x.reason) for x in plan.issues],[('body',reason)])
                self.assertEqual(plan.changes,())
                self.assertEqual(present_slot(slot,1,plan).status,'needs_review')

    def test_slot_owns_unique_target_and_exact_match_priority(self):
        c=source();c.equipsets=assess_equipment(c);slot=c.equipsets[0].slots[5]
        self.assertEqual(slot.item_reference.fix_target,(8,11))
        plan=plan_fixes(c);self.assertEqual(plan.changes[0].after,slot.item_reference.fix_target)
        fixed=apply_fixes(c,plan);fixed.inventory.append(InventoryRow(10,4,100))
        fixed.inventory_coverage[1]='missing'
        fixed.equipsets=assess_equipment(fixed)
        self.assertEqual(fixed.equipsets[0].slots[5].item_reference.state,State.MATCH)
        self.assertIsNone(fixed.equipsets[0].slots[5].item_reference.fix_target)
        self.assertFalse(plan_fixes(fixed).changes)

    def test_usage_never_confirms_invalid_observation(self):
        # WARD-001 / PT-30: invalid direct observations remain uncertain.
        for kind in ('duplicate','unread','invalid'):
            for origin in ('macro','equipset'):
                with self.subTest(kind=kind,origin=origin):
                    c=source();c.equipsets=[replace(c.equipsets[0],slots=tuple(replace(s,index=11) if s.action=='equip' else s for s in c.equipsets[0].slots))]
                    if origin=='macro':c.equipsets=[]
                    else:c.macros=[]
                    if kind=='duplicate':c.inventory.append(InventoryRow(8,11,200))
                    elif kind=='unread':c.inventory_coverage[8]='missing'
                    else:
                        c.inventory=[InventoryRow(8,0,100)]
                        c.equipsets=[replace(e,slots=tuple(replace(s,index=0) if s.action=='equip' else s for s in e.slots)) for e in c.equipsets]
                    usage=next(x for x in inspect_wardrobes(c,ITEMS) if x.item.item_id==100)
                    self.assertEqual(usage.state,'incomplete')

    def test_fix_preview_ignores_order_and_raw_metadata(self):
        # D-02 / PT-02: semantic prerequisites are independent of representation.
        c=source();c.equipsets.append(replace(c.equipsets[0],number=2))
        plan=plan_fixes(c)
        reordered=replace(c,equipsets=[replace(e,slots=tuple(replace(s,raw_hex='ff') for s in e.slots)) for e in reversed(c.equipsets)])
        self.assertEqual(plan_fixes(reordered),plan)
        fixed=apply_fixes(reordered,plan)
        self.assertTrue(all(e.slots[5].index==11 for e in fixed.equipsets))
        c.inventory.append(InventoryRow(10,2,100));before=asdict(c)
        with self.assertRaises(ValueError):apply_fixes(c,plan)
        self.assertEqual(asdict(c),before)

    def test_old_draft_assessment_can_be_recomputed(self):
        # Old draft fields remain readable; derived fields are recalculated.
        from ff11reader.draft_store import encode, decode
        c=source();slot=assess_equipment(c)[0].slots[5]
        record=encode(slot)
        fields=record['fields']['item_reference']['fields']
        fields.pop('reason');fields.pop('fix_target')
        old_slot=decode(record)
        self.assertIsNone(old_slot.item_reference.fix_target)
        c.equipsets=[replace(c.equipsets[0],slots=tuple(old_slot if s.name=='body' else s for s in c.equipsets[0].slots))]
        reassessed=assess_equipment(c)[0].slots[5]
        self.assertEqual(reassessed.item_reference.fix_target,(8,11))
