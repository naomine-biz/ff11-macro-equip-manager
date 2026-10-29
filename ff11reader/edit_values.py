"""Pure semantic edit values and structural validation."""
from .domain import Macro, Equipset, Text, Slot

SLOT_NAMES=tuple('main sub range ammo head body hands legs feet neck waist ear1 ear2 ring1 ring2 back'.split())

def key(value):
    if isinstance(value,Macro):return value.book,value.palette,value.bank,value.key
    if isinstance(value,Equipset):return (value.number,)
    raise ValueError('編集対象の型が不正です。')

def text_value(text):return text.display,tuple(text.tokens or ())


def value(item):
    if isinstance(item,Macro):return key(item),text_value(item.title),tuple(text_value(x) for x in item.lines)
    if isinstance(item,Equipset):return key(item),item.title.display,tuple(slot_value(s) for s in item.slots)
    raise ValueError('編集対象の型が不正です。')

def slot_value(s):return s.name,s.action,s.item_id,s.container,s.index

def character_value(c):
    def indexed(items):
        pairs=[(key(x),value(x)) for x in items]
        if len(dict(pairs))!=len(pairs):raise ValueError('編集対象のキーが重複しています。')
        return dict(pairs)
    return indexed(c.macros),indexed(c.equipsets)

def snapshot_value(snapshot):
    pairs=[(c.folder_id,character_value(c)) for c in snapshot.characters]
    if len(dict(pairs))!=len(pairs):raise ValueError('キャラクターのキーが重複しています。')
    return dict(pairs)

def validate_text(text):
    from .text_editing import validate_tokens
    if not isinstance(text,Text) or not isinstance(text.display,str) or any(c in text.display for c in ('\n','\r','\0')):
        raise ValueError('文字列に改行・NULを含めることはできません。')
    validate_tokens(text)

def integer(n,low,high):return type(n) is int and low<=n<=high

def validate_structure(item,kind):
    expected=Macro if kind=='macros' else Equipset if kind=='equipsets' else None
    if expected is None or not isinstance(item,expected):raise ValueError('編集対象の型が不正です。')
    validate_text(item.title)
    if kind=='macros':
        if not integer(item.book,1,40) or not integer(item.palette,1,10) or item.bank not in ('ctrl','alt') or not integer(item.key,1,10):raise ValueError('マクロの位置が不正です。')
        if not isinstance(item.lines,tuple) or len(item.lines)!=6:raise ValueError('マクロは6行必要です。')
        for text in item.lines:validate_text(text)
    else:
        if not integer(item.number,1,200):raise ValueError('装備セット番号が不正です。')
        if not isinstance(item.slots,tuple) or len(item.slots)!=16 or any(not isinstance(s,Slot) for s in item.slots) or tuple(s.name for s in item.slots)!=SLOT_NAMES:raise ValueError('装備セットは所定の16枠が必要です。')

def validate_transition(before,after,kind):
    validate_structure(before,kind);validate_structure(after,kind)
    if key(before)!=key(after):raise ValueError('編集対象のキーが変わっています。')
    if kind=='equipsets':
        for a,b in zip(before.slots,after.slots):
            if slot_value(a)==slot_value(b):continue  # Preserve unedited unknown source values.
            validate_slot(b)


def validate_slot(slot):
    if slot.name not in SLOT_NAMES or slot.action not in ('keep','remove','equip'):raise ValueError('装備枠の動作または部位が不正です。')
    if slot.action=='equip' and not (integer(slot.item_id,1,65534) and integer(slot.container,0,16) and integer(slot.index,1,80)):raise ValueError('装備枠の参照値が不正です。')
    if slot.action in ('keep','remove') and (slot.item_id,slot.container,slot.index)!=(None,None,None):raise ValueError('装備しない枠の参照値は空にしてください。')
