"""In-memory edit transactions. No GUI, filesystem or binary encoding."""
from copy import deepcopy
from dataclasses import dataclass, replace
from .domain import Text
from .edit_values import value, character_value, snapshot_value, validate_transition, key as edit_key
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


def contents(character):
    """Semantic edit contents, independent of binary encoding and derived states."""
    return character_value(character)


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
        self.saved = deepcopy(snapshot)
        self.history = []
        self.cursor = 0

    @property
    def dirty(self):
        return snapshot_value(self.saved) != snapshot_value(self.working)

    def _apply(self, edit, reverse=False):
        if not isinstance(edit,Edit) or not isinstance(edit.changes,tuple):raise ValueError('編集案の形式が不正です。')
        snapshot_value(self.working)
        working = deepcopy(self.working)
        seen = set()
        for change in edit.changes:
            if not isinstance(change,Change) or not isinstance(change.key,tuple) or not isinstance(change.character,str):raise ValueError('変更の形式が不正です。')
            validate_transition(change.before,change.after,change.kind)
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
            if index is None or value(values[index]) != value(before) or key(after) != change.key:
                raise ValueError('作業データが変わりました。変更案を作り直してください。')
            if value(before)!=value(after):values[index] = deepcopy(after)
        for character in working.characters:
            sources = {s.container: s.item_reference.inventory_source for e in character.equipsets for s in e.slots if s.container is not None}
            character.equipsets = assess_equipment(character, sources)
        self.working = working

    def apply(self, edit):
        if not isinstance(edit,Edit) or not isinstance(edit.changes,tuple):raise ValueError('編集案の形式が不正です。')
        for c in edit.changes:
            if not isinstance(c,Change):raise ValueError('変更の形式が不正です。')
            validate_transition(c.before,c.after,c.kind)
            if not isinstance(c.key,tuple) or c.key!=edit_key(c.before) or not isinstance(c.character,str):raise ValueError('変更対象のキーが不正です。')
        if len({(c.character,c.kind,c.key) for c in edit.changes})!=len(edit.changes):raise ValueError('変更対象が重複しています。')
        self._apply(edit)
        edit = replace(edit, changes=tuple(c for c in edit.changes if value(c.before) != value(c.after)))
        if not edit.changes:
            return
        self.history[self.cursor:] = [deepcopy(edit)]
        self.cursor += 1

    def undo(self):
        if self.cursor:
            self._apply(self.history[self.cursor - 1], True)
            self.cursor -= 1

    def redo(self):
        if self.cursor < len(self.history):
            self._apply(self.history[self.cursor])
            self.cursor += 1


def plan_equipment_edit(character,plan):
    from .fixes import apply_fixes
    sources={s.container:s.item_reference.inventory_source for e in character.equipsets for s in e.slots if s.container is not None}
    updated=apply_fixes(character,plan,sources)
    changes=tuple(Change(character.folder_id,'equipsets',(a.number,),a,b) for a,b in zip(character.equipsets,updated.equipsets) if value(a)!=value(b))
    return Edit('装備セットの参照Fix',changes)
