"""Domain service: compare equipment references with observed cache rows.

No filesystem or binary knowledge. Matching means stored location and type ID
agree with the cache. Augments are not inputs to reference-state evaluation.
"""
from dataclasses import replace
from .domain import EquipmentReference, ItemReference, ItemReferenceState as State
from .inventory_observation import InventoryObservation, valid_position

STATUS_LABELS = {
    'cache_match':'キャッシュ一致',
    'cache_item_mismatch':'位置のID不一致（要確認）',
    'cache_position_empty':'該当行なし（要確認）',
    'cache_unavailable':'キャッシュ未取得',
    'invalid_reference':'参照値が範囲外',
    'unknown_action':'未知の装備動作',
    'ambiguous_position':'キャッシュ位置が重複',
}


def assess_equipment(character, sources=None):
    observation = InventoryObservation(character)
    result = []
    for equipset in character.equipsets:
        resolved = []
        for slot in equipset.slots:
            if slot.action in ('keep', 'remove'):
                resolved.append(replace(slot, item_reference=ItemReference(State.NOT_APPLICABLE, 'not_applicable')))
                continue
            rows = observation.positions[slot.container, slot.index]
            valid_type = type(slot.item_id) is int and 1 <= slot.item_id < 65535
            if slot.action != 'equip':
                status = 'unknown_action'
            elif not valid_type or not valid_position(slot.container, slot.index):
                status = 'invalid_reference'
            elif observation.coverage.get(slot.container) != 'loaded':
                status = 'cache_unavailable'
            elif len(rows) > 1:
                status = 'ambiguous_position'
            elif not rows:
                status = 'cache_position_empty'
            elif rows[0].item_id != slot.item_id:
                status = 'cache_item_mismatch'
            else:
                status = 'cache_match'

            candidates = observation.by_type.get(slot.item_id, [])
            target = None
            reason = None
            if status == 'cache_match':
                state = State.MATCH
            elif slot.action != 'equip' or not valid_type:
                state, reason = State.INSUFFICIENT_DATA, 'invalid_reference'
            elif not observation.complete:
                state, reason = State.INSUFFICIENT_DATA, 'incomplete_inventory'
            elif not candidates:
                state, reason = State.NOT_OBSERVED, 'not_observed'
            elif len(candidates) > 1:
                state, reason = State.MULTIPLE_CANDIDATES, 'multiple_candidates'
            elif not observation.sound(candidates[0]):
                state, reason = State.INSUFFICIENT_DATA, 'ambiguous_target'
            elif candidates[0].quantity is not None and candidates[0].quantity != 1:
                state, reason = State.INSUFFICIENT_DATA, 'quantity_not_one'
            else:
                state = State.SAME_TYPE_ELSEWHERE
                target = candidates[0].container, candidates[0].index
            assessment = ItemReference(
                state, status, tuple(r.item_id for r in rows),
                tuple(sorted((r.container, r.index) for r in candidates)),
                (sources or {}).get(slot.container), reason=reason, fix_target=target)
            resolved.append(replace(slot, item_reference=assessment))
        result.append(replace(equipset, slots=tuple(resolved)))
    return result


def compare_equipment(character, sources=None):
    """Compatibility query; the canonical assessments live on resolved slots."""
    return [EquipmentReference(e.number,s) for e in assess_equipment(character,sources)
            for s in e.slots if s.action not in ('keep','remove')]
