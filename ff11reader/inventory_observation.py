"""Shared domain checks for observed inventory locations."""
from collections import defaultdict


def valid_position(container, index):
    return type(container) is int and 0 <= container <= 16 and type(index) is int and 1 <= index <= 80


class InventoryObservation:
    def __init__(self, character):
        self.coverage = character.inventory_coverage
        self.positions = defaultdict(list)
        self.by_type = defaultdict(list)
        for row in character.inventory:
            self.positions[row.container, row.index].append(row)
            self.by_type[row.item_id].append(row)

    @property
    def complete(self):
        return all(self.coverage.get(bag) == 'loaded' for bag in range(17))

    def sound(self, row):
        return (valid_position(row.container, row.index)
                and self.coverage.get(row.container) == 'loaded'
                and len(self.positions[row.container, row.index]) == 1)
