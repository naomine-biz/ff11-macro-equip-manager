"""In-memory edit transactions. No GUI, filesystem or binary encoding."""
from copy import deepcopy
from dataclasses import dataclass, replace
from .domain import Text
from .macro_inventory import assess_macro_inventory
from .references import assess_equipment


@dataclass(frozen=True)
class Change:
    character: str
    kind: str
    key: tuple
    before: object
    after: object


@dataclass(frozen=True)
class Edit:
    label: str
    changes: tuple[Change, ...]


def macro_key(macro):
    return macro.book, macro.palette, macro.bank, macro.key


def edit_macro(character, macro, title, lines):
    if len(lines) != 6 or any('\n' in s or '\r' in s or '\0' in s for s in [title, *lines]):
        raise ValueError('マクロは名前と6行で入力してください。')
    def text(before, value):
        return before if before.display == value else Text(value, '', 'draft')
    updated = replace(macro, title=text(macro.title, title), lines=tuple(text(a, b) for a, b in zip(macro.lines, lines)))
    return Edit('マクロを編集', (Change(character.folder_id, 'macros', macro_key(macro), macro, updated),))


def plan_macro_fixes(character, items, address=None):
    refs = assess_macro_inventory(character, items)
    changes = []
    for macro in character.macros:
        key = macro_key(macro)
        if address is not None and key != address:
            continue
        fixes = {r.line: r.replacement for r in refs if r.address == key and r.replacement is not None}
        if fixes:
            lines = tuple(Text(fixes[n], '', 'draft') if n in fixes else line for n, line in enumerate(macro.lines, 1))
            changes.append(Change(character.folder_id, 'macros', key, macro, replace(macro, lines=lines)))
    return Edit('マクロの収納番号Fix', tuple(changes))


class EditSession:
    def __init__(self, snapshot):
        self.baseline = deepcopy(snapshot)
        self.working = deepcopy(snapshot)
        self.history = []
        self.cursor = 0

    @property
    def dirty(self):
        return any(a.macros != b.macros or a.equipsets != b.equipsets for a, b in zip(self.baseline.characters, self.working.characters))

    def _apply(self, edit, reverse=False):
        working = deepcopy(self.working)
        seen = set()
        for change in edit.changes:
            identity = (change.character, change.kind, change.key)
            if identity in seen or change.kind not in ('macros', 'equipsets'):
                raise ValueError('編集操作の対象が不正です。')
            seen.add(identity)
            character = next((c for c in working.characters if c.folder_id == change.character), None)
            if character is None:
                raise ValueError('編集対象のキャラクターが見つかりません。')
            values = getattr(character, change.kind)
            key = macro_key if change.kind == 'macros' else lambda e: (e.number,)
            index = next((i for i, v in enumerate(values) if key(v) == change.key), None)
            before, after = (change.after, change.before) if reverse else (change.before, change.after)
            if index is None or values[index] != before or key(after) != change.key:
                raise ValueError('作業データが変わりました。変更案を作り直してください。')
            values[index] = after
        for character in working.characters:
            sources = {s.container: s.item_reference.inventory_source for e in character.equipsets for s in e.slots if s.container is not None}
            character.equipsets = assess_equipment(character, sources)
        self.working = working

    def apply(self, edit):
        edit = replace(edit, changes=tuple(c for c in edit.changes if c.before != c.after))
        if not edit.changes:
            return
        self._apply(edit)
        self.history[self.cursor:] = [edit]
        self.cursor += 1

    def undo(self):
        if self.cursor:
            self._apply(self.history[self.cursor - 1], True)
            self.cursor -= 1

    def redo(self):
        if self.cursor < len(self.history):
            self._apply(self.history[self.cursor])
            self.cursor += 1
