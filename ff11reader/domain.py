"""Domain values: no filesystem, registry, GUI or binary offsets."""
from dataclasses import dataclass, field
from enum import StrEnum


class ItemReferenceState(StrEnum):
    MATCH = 'match'
    SAME_TYPE_ELSEWHERE = 'same_type_elsewhere'
    MULTIPLE_CANDIDATES = 'multiple_candidates'
    NOT_OBSERVED = 'not_observed'
    INSUFFICIENT_DATA = 'insufficient_data'
    NOT_APPLICABLE = 'not_applicable'


@dataclass(frozen=True)
class ItemReference:
    state: ItemReferenceState = ItemReferenceState.INSUFFICIENT_DATA
    observation: str = 'unassessed'
    observed_item_ids: tuple[int, ...] = ()
    candidates: tuple[tuple[int, int], ...] = ()
    inventory_source: dict | None = None
    certainty: str = 'cache_observation_only'
    reason: str | None = None
    fix_target: tuple[int, int] | None = None


@dataclass(frozen=True)
class TextToken:
    start: int
    end: int
    identity: str


@dataclass(frozen=True)
class Text:
    display: str
    raw_hex: str
    state: str
    tokens: tuple[TextToken, ...] | None = None


@dataclass(frozen=True)
class Macro:
    book: int
    palette: int
    bank: str
    key: int
    title: Text
    lines: tuple[Text, ...]


@dataclass(frozen=True)
class Slot:
    name: str
    action: str
    item_id: int | None
    container: int | None
    index: int | None
    raw_hex: str
    item_reference: ItemReference = field(default_factory=ItemReference)


@dataclass(frozen=True)
class Equipset:
    number: int
    title: Text
    slots: tuple[Slot, ...]


@dataclass(frozen=True)
class InventoryRow:
    container: int
    index: int
    item_id: int
    quantity: int | None = None
    augment_state: str = 'unknown'
    augment_reason: str = 'local_source_unsupported'
    raw_hex: str = ''


@dataclass
class Character:
    folder_id: str
    display_name: str | None = None
    account: str | None = None
    identity_status: str = 'unknown'
    books: dict = field(default_factory=dict)
    macros: list[Macro] = field(default_factory=list)
    equipsets: list[Equipset] = field(default_factory=list)
    inventory: list[InventoryRow] = field(default_factory=list)
    inventory_coverage: dict[int, str] = field(default_factory=dict)
    @property
    def equipment_references(self):
        # Read model only: owns no duplicate status or candidate data.
        return [EquipmentReference(e.number,s) for e in self.equipsets
                for s in e.slots if s.action not in ('keep','remove')]


@dataclass(frozen=True)
class EquipmentReference:
    equipset: int
    piece: Slot

    @property
    def slot(self): return self.piece.name
    @property
    def expected_item_id(self): return self.piece.item_id
    @property
    def container(self): return self.piece.container
    @property
    def index(self): return self.piece.index
    @property
    def status(self): return self.piece.item_reference.observation
    @property
    def observed_item_ids(self): return self.piece.item_reference.observed_item_ids
    @property
    def candidates(self): return self.piece.item_reference.candidates
    @property
    def inventory_source(self): return self.piece.item_reference.inventory_source
    @property
    def certainty(self): return self.piece.item_reference.certainty


@dataclass
class Snapshot:
    id: str
    captured_at: str
    characters: list[Character]
    items: dict
    sources: list
    diagnostics: list
    installation_key: str = ''
    capabilities: dict = field(default_factory=lambda: {
        'read_macros': True, 'read_equipsets': True,
        'inventory': 'local_cache_partial_freshness_unknown',
        'augments': 'unsupported', 'write': 'equipset_reference_single_file_guarded'})
    phrases: dict = field(default_factory=dict)
    phrase_readings: dict = field(default_factory=dict)
