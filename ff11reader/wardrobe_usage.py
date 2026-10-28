"""Pure reverse references from /equip and all equipment sets to wardrobe rows."""
from collections import defaultdict
from dataclasses import dataclass
from .domain import InventoryRow
from .macro_inventory import parse_equip, STORAGES

WARDROBES = frozenset(STORAGES[n] for n in range(1,9))


@dataclass(frozen=True)
class WardrobeUsage:
    item: InventoryRow
    state: str
    references: tuple[str, ...]


def inspect_wardrobes(character, items, incomplete=False):
    rows=character.inventory
    by_type=defaultdict(list);by_name=defaultdict(list);positions=defaultdict(list)
    direct=defaultdict(list);possible=defaultdict(list)
    def key(row):return row.container,row.index,row.item_id
    for row in rows:
        by_type[row.item_id].append(row);positions[row.container,row.index].append(row)
        name=items.get(row.item_id,{}).get('name')
        if name:by_name[name].append(row)
    for equipset in character.equipsets:
        for slot in equipset.slots:
            if slot.action in ('keep','remove'):continue
            if slot.action!='equip' or not slot.item_id:
                incomplete=True;continue
            candidates=by_type[slot.item_id]
            exact=[r for r in candidates if (r.container,r.index)==(slot.container,slot.index)]
            label=f'装備セット {equipset.number:03} {equipset.title.display} / {slot.name}'
            if len(exact)==1 and len(positions[slot.container,slot.index])==1:
                direct[key(exact[0])].append(label)
            else:
                for row in candidates:possible[key(row)].append(label+'（保存位置違いの候補）')
    for macro in character.macros:
        for number,line in enumerate(macro.lines,1):
            command=parse_equip(line.display)
            if command is None:continue
            if "{AT:" in line.display:incomplete=True
            if not command.item_name:
                if not command.valid:incomplete=True
                continue
            candidates=by_name[command.item_name]
            selected=[r for r in candidates if r.container==STORAGES.get(command.storage)] if command.storage is not None else candidates
            label=f'ブック {macro.book:02} / パレット {macro.palette} / {macro.bank.upper()} {macro.key if macro.key<10 else 0} {macro.title.display} / {number}行目'
            if command.valid and len(selected)==1:
                direct[key(selected[0])].append(label)
            else:
                for row in selected or candidates:possible[key(row)].append(label+'（参照先の候補）')
    result=[]
    for row in sorted(rows,key=lambda r:(r.container,r.index)):
        if row.container not in WARDROBES:continue
        identity=key(row)
        if direct[identity]:state='referenced';refs=direct[identity]+possible[identity]
        elif possible[identity]:state='possible';refs=possible[identity]
        elif (incomplete or character.inventory_coverage.get(row.container)!='loaded' or
              not items.get(row.item_id,{}).get('name') or not 1<=row.index<=80 or len(positions[row.container,row.index])!=1):
            state='incomplete';refs=['読み取れないデータや参照先を特定できない情報があるため、未参照か判断できません。']
        else:state='unreferenced';refs=[]
        result.append(WardrobeUsage(row,state,tuple(refs)))
    return tuple(result)
