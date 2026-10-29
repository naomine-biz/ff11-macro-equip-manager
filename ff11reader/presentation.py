"""Action-oriented view values derived from domain state and the Fix plan."""
from dataclasses import dataclass
from .domain import ItemReferenceState as State


@dataclass(frozen=True)
class SlotPresentation:
    status: str
    instruction: str
    change: object = None


def present_slot(slot, equipset, plan):
    if slot.action in ('keep','remove'):
        return SlotPresentation('not_applicable','変更しない枠です。' if slot.action=='keep' else '装備を外す指定です。')
    if slot.item_reference.state==State.MATCH:
        return SlotPresentation('match','対応は不要です。')
    change=next((c for c in plan.changes if c.equipset==equipset and c.slot==slot.name),None)
    if slot.item_reference.fix_target is not None and change:return SlotPresentation('fixable','Fix案を確認して、まとめて参照を更新できます。',change)
    reason=slot.item_reference.reason
    if reason=='multiple_candidates':
        return SlotPresentation('multiple','候補の場所を確認してください。')
    if reason=='not_observed':
        return SlotPresentation('missing','アイテムの所在を確認してください。')
    reasons={'incomplete_inventory':'読み取れない収納があります。詳細を確認してください。',
             'quantity_not_one':'候補の数量を確認してください。',
             'ambiguous_target':'候補の位置を一意に決められません。詳細を確認してください。',
             'invalid_reference':'保存された参照値を確認してください。'}
    return SlotPresentation('needs_review',reasons.get(reason, 'この枠の詳細を確認してください。'))


def format_token_ids(tokens):
    return ", ".join(token.identity for token in tokens or ()) or "なし"
