"""Domain service: compare equipment references with observed cache rows.

No filesystem or binary knowledge. Matching means stored location and type ID
agree with the cache. Augments are not inputs to reference-state evaluation.
"""
from collections import defaultdict
from dataclasses import replace
from .domain import EquipmentReference, ItemReference, ItemReferenceState as State

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
    positions=defaultdict(list); by_item=defaultdict(list); result=[]
    for row in character.inventory:
        positions[row.container,row.index].append(row)
        by_item[row.item_id].append((row.container,row.index))
    for equipset in character.equipsets:
        resolved=[]
        for slot in equipset.slots:
            if slot.action in ('keep','remove'):
                resolved.append(replace(slot,item_reference=ItemReference(State.NOT_APPLICABLE,'not_applicable')))
                continue
            rows=positions.get((slot.container,slot.index),[])
            if slot.action!='equip': status='unknown_action'
            elif (slot.item_id is None or not 1<=slot.item_id<65535 or
                  slot.container is None or not 0<=slot.container<=16 or
                  slot.index is None or not 1<=slot.index<=80):
                status='invalid_reference'
            elif character.inventory_coverage.get(slot.container)!='loaded': status='cache_unavailable'
            elif len(rows)>1: status='ambiguous_position'
            elif not rows: status='cache_position_empty'
            elif rows[0].item_id!=slot.item_id: status='cache_item_mismatch'
            else: status='cache_match'
            candidates=tuple(sorted(set(by_item.get(slot.item_id,[]))))
            all_loaded=all(character.inventory_coverage.get(b)=='loaded' for b in range(17))
            if status=='cache_match':
                state=State.MATCH
            elif status in ('invalid_reference','unknown_action','ambiguous_position','cache_unavailable'):
                state=State.INSUFFICIENT_DATA
            elif len(candidates)>1: state=State.MULTIPLE_CANDIDATES
            elif candidates:
                state=State.SAME_TYPE_ELSEWHERE if all_loaded else State.INSUFFICIENT_DATA
            else: state=State.NOT_OBSERVED if all_loaded else State.INSUFFICIENT_DATA
            assessment=ItemReference(state,status,tuple(r.item_id for r in rows),candidates,
                                     (sources or {}).get(slot.container))
            resolved.append(replace(slot,item_reference=assessment))
        result.append(replace(equipset,slots=tuple(resolved)))
    return result


def compare_equipment(character, sources=None):
    """Compatibility query; the canonical assessments live on resolved slots."""
    return [EquipmentReference(e.number,s) for e in assess_equipment(character,sources)
            for s in e.slots if s.action not in ('keep','remove')]
