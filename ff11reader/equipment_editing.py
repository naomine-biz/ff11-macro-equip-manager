"""Pure equipment-slot selection rules and edit plans."""
from dataclasses import replace
from .domain import Slot
from .edit_values import SLOT_NAMES, validate_slot, validate_transition


def candidates(character, items, slot, query=''):
    if slot not in SLOT_NAMES:raise ValueError('部位が不正です。')
    rows=tuple(row for row in character.inventory if slot in items.get(row.item_id,{}).get('equip_slots',()))
    return search_rows(rows,items,query)


def search_rows(rows,items,query=''):
    query=query.strip().casefold()
    return tuple(row for row in rows if not query or query in (items.get(row.item_id,{}).get('name') or '').casefold() or query in str(row.item_id))


def validate_selection(character, items, slot):
    validate_slot(slot)
    if slot.action in ('keep','remove'):return
    rows=[r for r in character.inventory if (r.container,r.index)==(slot.container,slot.index)]
    if len(rows)!=1 or rows[0].item_id!=slot.item_id:raise ValueError('選択した持ち物の位置と種類IDを確認できません。')
    if slot.name not in items.get(slot.item_id,{}).get('equip_slots',()):raise ValueError('この部位に装備できるアイテムを選んでください。')


def edit_slot(character, items, equipment, name, action, selection=None):
    from .editing import Edit, Change
    if name not in SLOT_NAMES or action not in ('keep','remove','equip'):raise ValueError('部位または動作が不正です。')
    before=equipment.slots[SLOT_NAMES.index(name)]
    if action=='equip':
        if not isinstance(selection,tuple) or len(selection)!=3:raise ValueError('装備する持ち物を選んでください。')
        item,container,index=selection
    else:
        if selection is not None:raise ValueError('変更しない・外すにはアイテムを指定しません。')
        item=container=index=None
    after=Slot(name,action,item,container,index,before.raw_hex)
    slots=list(equipment.slots);slots[SLOT_NAMES.index(name)]=after
    updated=replace(equipment,slots=tuple(slots))
    validate_transition(equipment,updated,'equipsets')
    validate_selection(character,items,after)
    return Edit('装備枠を編集',(Change(character.folder_id,'equipsets',(equipment.number,),equipment,updated),))
