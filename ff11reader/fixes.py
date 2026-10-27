"""Pure domain planning and application to a working copy; no file writer."""
from collections import defaultdict
from dataclasses import dataclass, replace
import hashlib
import json
from .references import assess_equipment



@dataclass(frozen=True)
class FixChange:
    equipset: int
    slot: str
    item_id: int
    before: tuple[int, int]
    after: tuple[int, int]


@dataclass(frozen=True)
class FixIssue:
    equipset: int
    slot: str
    reason: str


@dataclass(frozen=True)
class FixPlan:
    character: str
    fingerprint: str
    changes: tuple[FixChange, ...]
    issues: tuple[FixIssue, ...]
    basis: str = 'unique_in_local_inventory_observation'


def fingerprint(character):
    value=[character.folder_id,sorted(character.inventory_coverage.items()),
           sorted((r.container,r.index,r.item_id,str(r.quantity)) for r in character.inventory),
           [(e.number,[(s.name,s.action,s.item_id,s.container,s.index,s.raw_hex) for s in e.slots]) for e in character.equipsets]]
    return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def plan_fixes(character):
    by_item=defaultdict(list);positions=defaultdict(list);changes=[];issues=[]
    for row in character.inventory:
        by_item[row.item_id].append(row);positions[row.container,row.index].append(row)
    complete=all(character.inventory_coverage.get(b)=='loaded' for b in range(17))
    for e in character.equipsets:
        for s in e.slots:
            if s.action in ('keep','remove'):continue
            observed=positions.get((s.container,s.index),[])
            if s.action=='equip' and len(observed)==1 and observed[0].item_id==s.item_id:continue
            reason=None
            if s.action!='equip' or s.item_id is None or not 1<=s.item_id<65535:reason='invalid_reference'
            elif not complete:reason='incomplete_inventory'
            candidates=by_item.get(s.item_id,[])
            if reason is None:
                if not candidates:reason='not_observed'
                elif len(candidates)!=1:reason='multiple_candidates'
                else:
                    target=candidates[0]
                    if not 0<=target.container<=16 or not 1<=target.index<=80 or len(positions[target.container,target.index])!=1:reason='ambiguous_target'
                    elif target.quantity is not None and target.quantity!=1:reason='quantity_not_one'
            if reason:
                issues.append(FixIssue(e.number,s.name,reason));continue
            changes.append(FixChange(e.number,s.name,s.item_id,(s.container,s.index),(target.container,target.index)))
    return FixPlan(character.folder_id,fingerprint(character),tuple(changes),tuple(issues))


def apply_fixes(character, plan, sources=None):
    # Recompute to reject stale or altered previews before changing any slot.
    if plan!=plan_fixes(character):raise ValueError('作業データが変わりました。Fix案を作り直してください。')
    changes={(x.equipset,x.slot):x for x in plan.changes}
    equipsets=[]
    for e in character.equipsets:
        slots=[]
        for s in e.slots:
            change=changes.get((e.number,s.name))
            slots.append(replace(s,container=change.after[0],index=change.after[1]) if change else s)
        equipsets.append(replace(e,slots=tuple(slots)))
    working=replace(character,equipsets=equipsets)
    working.equipsets=assess_equipment(working,sources)
    return working
