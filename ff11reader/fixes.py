"""Pure domain planning and application to a working copy; no file writer."""
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
    # Canonical semantic inputs; source bytes and enumeration order are separate.
    value = [character.folder_id, sorted(character.inventory_coverage.items()),
             sorted((r.container, r.index, r.item_id, str(r.quantity)) for r in character.inventory),
             sorted((e.number, sorted((s.name, s.action, s.item_id, s.container, s.index)
                                     for s in e.slots)) for e in character.equipsets)]
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def plan_fixes(character):
    changes, issues = [], []
    for e in assess_equipment(character):
        for s in e.slots:
            assessment = s.item_reference
            if assessment.fix_target is not None:
                changes.append(FixChange(e.number, s.name, s.item_id,
                                         (s.container, s.index), assessment.fix_target))
            elif assessment.reason is not None:
                issues.append(FixIssue(e.number, s.name, assessment.reason))
    return FixPlan(character.folder_id, fingerprint(character),
                   tuple(sorted(changes, key=lambda x: (x.equipset, x.slot))),
                   tuple(sorted(issues, key=lambda x: (x.equipset, x.slot))))


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
