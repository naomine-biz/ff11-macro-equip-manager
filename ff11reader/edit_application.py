"""Edit use cases: coordinate pure transactions and application-owned storage."""
from copy import deepcopy
from pathlib import Path
from .editing import EditSession, Edit, Change, plan_macro_fixes
from .draft_store import DraftStore
from .fixes import apply_fixes


class Editor:
    def __init__(self, snapshot, path=None):
        self.store = DraftStore(path or Path(__file__).resolve().parent.parent / 'work' / 'drafts' / (snapshot.installation_key + '.json'))
        self.blocked = None
        try:
            self.session = self.store.load(snapshot)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            self.blocked = str(exc)
            self.session = EditSession(snapshot)

    def execute(self, operation):
        if self.blocked:
            raise ValueError(self.blocked)
        next_session = deepcopy(self.session)
        operation(next_session)
        self.store.save(next_session)
        self.session = next_session

    def apply(self, edit):
        self.execute(lambda s: s.apply(edit))

    def undo(self):
        self.execute(lambda s: s.undo())

    def redo(self):
        self.execute(lambda s: s.redo())

    def macro_fixes(self, character, preview, address=None):
        current = next(c for c in self.session.working.characters if c.folder_id == character)
        if preview != plan_macro_fixes(current, self.session.working.items, address):
            raise ValueError('Fix案が変わりました。プレビューを開き直してください。')
        self.apply(preview)

    def equipment_fixes(self, character, plan):
        current = next(c for c in self.session.working.characters if c.folder_id == character)
        sources = {s.container: s.item_reference.inventory_source for e in current.equipsets for s in e.slots if s.container is not None}
        updated = apply_fixes(current, plan, sources)
        changes = tuple(Change(character, 'equipsets', (a.number,), a, b) for a, b in zip(current.equipsets, updated.equipsets) if a != b)
        self.apply(Edit('装備セットの参照Fix', changes))

    def start_fresh(self):
        self.store.archive()
        self.session = EditSession(self.session.baseline)
        self.blocked = None
