"""Owned persistent edit state. Domain values cross this boundary as detached values."""
from copy import deepcopy
from dataclasses import fields, is_dataclass, replace
from immutables import Map
from .edit_values import key, value, snapshot_value
from .references import assess_equipment

_MISSING = object()


def detached(current, previous=_MISSING):
    """Reuse only the caller's detached values, never a stored mutable object."""
    if previous is not _MISSING and type(current) is type(previous) and current == previous:
        return previous
    if is_dataclass(current):
        return replace(current, **{f.name: detached(getattr(current, f.name),
            getattr(previous, f.name, _MISSING)) for f in fields(current)})
    if isinstance(current, list):
        old = previous if isinstance(previous, list) else []
        return [detached(x, old[i] if i < len(old) else _MISSING) for i, x in enumerate(current)]
    if isinstance(current, tuple):
        old = previous if isinstance(previous, tuple) else ()
        return tuple(detached(x, old[i] if i < len(old) else _MISSING) for i, x in enumerate(current))
    if isinstance(current, dict):
        old = previous if isinstance(previous, dict) else {}
        return {deepcopy(k): detached(v, old.get(k, _MISSING)) for k, v in current.items()}
    return deepcopy(current)


class SnapshotState:
    """Private storage: owned values are replaced, never mutated after construction."""
    def __init__(self, snapshot):
        snapshot_value(snapshot)  # Reject duplicate identities at the boundary.
        template = deepcopy(snapshot)
        entries, orders = {}, {}
        for c in template.characters:
            for kind in ('macros', 'equipsets'):
                values = getattr(c, kind)
                orders[c.folder_id, kind] = tuple(key(x) for x in values)
                entries.update({(c.folder_id, kind, key(x)): x for x in values})
                setattr(c, kind, [])
        self._token = object()
        self._template = template
        self._entries = Map(entries)
        self._orders = orders
        self._semantic = Map({k: value(v) for k, v in entries.items()})
        self._characters = frozenset(c.folder_id for c in template.characters)

    def source_header(self):
        return self._template.installation_key, deepcopy(self._template.sources)

    def edit_records(self):
        return {c.folder_id: {kind: [deepcopy(self._entries[c.folder_id,kind,address])
            for address in self._orders[c.folder_id,kind]] for kind in ('macros','equipsets')}
            for c in self._template.characters}

    def __deepcopy__(self, memo):
        # Internal ownership permits sharing. Export/read always detach values.
        return self

    def same_values(self, other):
        return self._characters == other._characters and self._semantic == other._semantic

    def read(self, folder, kind, address):
        return deepcopy(self._entries[folder, kind, address])

    def has(self, identity): return identity in self._entries

    def read_character(self, folder):
        c = next(c for c in self._template.characters if c.folder_id == folder)
        return deepcopy(self._character(c))

    def items(self): return deepcopy(self._template.items)

    def _character(self, c):
        return replace(c, **{kind: [self._entries[c.folder_id, kind, address]
            for address in self._orders[c.folder_id, kind]] for kind in ('macros', 'equipsets')})

    def export(self, previous=None):
        # The assembled view is internal until detached() has processed it.
        view = replace(self._template, characters=[self._character(c) for c in self._template.characters])
        return detached(view, previous if previous is not None else _MISSING)

    def updated(self, replacements):
        result = object.__new__(SnapshotState)
        result._token = object()
        result._template, result._orders, result._characters = self._template, self._orders, self._characters
        entries = self._entries.mutate()
        semantic = self._semantic.mutate()
        for identity, item in replacements.items():
            entries[identity] = deepcopy(item)
            semantic[identity] = value(item)
        result._entries, result._semantic = entries.finish(), semantic.finish()
        # Inventory is unchanged by edit operations. Only equipment edits need reassessment.
        folders = {folder for folder, kind, address in replacements if kind == 'equipsets'}
        if folders:
            entries = result._entries.mutate()
            for folder in folders:
                template = next(c for c in self._template.characters if c.folder_id == folder)
                c = deepcopy(replace(template, equipsets=[result._entries[folder,'equipsets',address]
                    for address in self._orders[folder,'equipsets']]))
                sources = {s.container:s.item_reference.inventory_source for e in c.equipsets
                    for s in e.slots if s.container is not None}
                for e in assess_equipment(c, sources): entries[folder, 'equipsets', (e.number,)] = e
            result._entries = entries.finish()
        return result
