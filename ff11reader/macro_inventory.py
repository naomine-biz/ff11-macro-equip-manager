"""Pure /equip parsing, inventory assessment and storage-number proposals."""
from dataclasses import dataclass
import re

STORAGES = {0: 0, 1: 8, **{n: n + 8 for n in range(2, 9)}}
SLOTS = set('main sub range ranged ammo head neck ear1 ear2 l.ear r.ear body hands ring1 ring2 l.ring r.ring back waist legs feet メイン サブ 遠隔 矢弾 頭 首 左耳 右耳 胴 両手 左指 右指 背 腰 両脚 両足'.split())
SLOTS.update('メインウェポン サブウェポン レンジウェポン 左手の指 右手の指'.split())
LABELS = {
    'match': '一致', 'unspecified_unique': '収納未指定・Fix可能',
    'unspecified_multiple': '収納未指定・候補複数',
    'wrong_unique': '収納違い・Fix可能', 'same_storage_multiple': '同一収納に候補複数',
    'elsewhere_multiple': '別の収納に候補複数', 'missing': '候補なし',
    'unavailable_storage': '装備用収納への移動が必要', 'incomplete': '取得不足',
    'invalid': '記述を確認', 'remove': '装備を外す',
}


@dataclass(frozen=True)
class EquipCommand:
    item_name: str
    storage: int | None
    item_end: int
    storage_span: tuple[int, int] | None
    valid: bool = True


@dataclass(frozen=True)
class MacroItemReference:
    address: tuple
    line: int
    text: str
    state: str
    candidates: tuple = ()  # container, internal slot, item type
    replacement: str | None = None


def parse_equip(line):
    tokens = list(re.finditer(r'【(?:[^【】]|【[^】]*】)*】|"[^"]*"|[^\s]+', line))
    def value(token):
        text = token.group()
        return text[1:-1] if text.startswith(('【', '"')) else text
    if not tokens or value(tokens[0]).lower() != '/equip':
        return None
    if len(tokens) < 2 or value(tokens[1]).lower() not in SLOTS:
        return EquipCommand('', None, 0, None, False)
    if len(tokens) == 2:
        return EquipCommand('', None, tokens[1].end(), None)
    item = value(tokens[2])
    # A wait tag can be attached directly to the item or storage argument.
    item = re.split(r'(?i)<wait[.\s]', item, maxsplit=1)[0]
    item_end = tokens[2].start() + len(item) if '<wait' in tokens[2].group().lower() else tokens[2].end()
    tail = line[item_end:]
    number = re.match(r'\s+([0-9]+)(?=\s|<|$)', tail)
    if number:
        storage = int(number[1])
        span = (item_end + number.start(1), item_end + number.end(1))
        return EquipCommand(item, storage, item_end, span, storage in STORAGES)
    if tail.strip() and not tail.lstrip().lower().startswith('<wait'):
        return EquipCommand(item, None, item_end, None, False)
    return EquipCommand(item, None, item_end, None)


def assess_macro_inventory(character, items):
    result = []
    complete = all(character.inventory_coverage.get(n) == 'loaded' for n in range(17))
    for macro in character.macros:
        for number, line in enumerate(macro.lines, 1):
            command = parse_equip(line.display)
            if command is None:
                continue
            state, replacement, candidates = 'invalid', None, ()
            if command.valid and not command.item_name:
                state = 'remove'
            elif command.valid:
                rows = [r for r in character.inventory if items.get(r.item_id, {}).get('name') == command.item_name]
                candidates = tuple((r.container, r.index, r.item_id) for r in rows)
                chosen = [r for r in rows if r.container == STORAGES.get(command.storage)] if command.storage is not None else []
                # Duplicate observations and invalid positions cannot justify a unique Fix.
                sound = all(1 <= r.index <= 80 and sum(x.container == r.container and x.index == r.index for x in character.inventory) == 1 for r in rows)
                if not complete or not sound:
                    state = 'incomplete'
                elif len(chosen) > 1:
                    state = 'same_storage_multiple'
                elif len(chosen) == 1:
                    state = 'match'
                elif not rows:
                    state = 'missing'
                elif len(rows) > 1:
                    state = 'unspecified_multiple' if command.storage is None else 'elsewhere_multiple'
                elif rows[0].container not in STORAGES.values():
                    state = 'unavailable_storage'
                else:
                    state = 'unspecified_unique' if command.storage is None else 'wrong_unique'
                    storage = next(n for n, bag in STORAGES.items() if bag == rows[0].container)
                    if command.storage_span:
                        start, end = command.storage_span
                        replacement = line.display[:start] + str(storage) + line.display[end:]
                    else:
                        replacement = line.display[:command.item_end] + ' ' + str(storage) + line.display[command.item_end:]
            result.append(MacroItemReference((macro.book, macro.palette, macro.bank, macro.key), number, line.display, state, candidates, replacement))
    return tuple(result)
