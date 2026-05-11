from __future__ import annotations

import random
from dataclasses import dataclass, field

from game.constants import BOARD_SIZE

Position = tuple[int, int]


@dataclass(slots=True)
class Board:
    width: int = BOARD_SIZE
    height: int = BOARD_SIZE
    blocked_tiles: set[Position] = field(default_factory=set)

    def in_bounds(self, position: Position) -> bool:
        x, y = position
        return 0 <= x < self.width and 0 <= y < self.height

    def is_blocked(self, position: Position) -> bool:
        return position in self.blocked_tiles

    def is_walkable(self, position: Position) -> bool:
        return self.in_bounds(position) and not self.is_blocked(position)

    def orthogonal_positions(self, origin: Position, distance: int) -> list[Position]:
        x, y = origin
        results: list[Position] = []
        for step in range(1, distance + 1):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                candidate = (x + dx * step, y + dy * step)
                if self.in_bounds(candidate):
                    results.append(candidate)
        return results

    def diagonal_positions(self, origin: Position, distance: int) -> list[Position]:
        x, y = origin
        results: list[Position] = []
        for step in range(1, distance + 1):
            for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                candidate = (x + dx * step, y + dy * step)
                if self.in_bounds(candidate):
                    results.append(candidate)
        return results

    def knight_positions(self, origin: Position) -> list[Position]:
        x, y = origin
        results: list[Position] = []
        for dx, dy in ((1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)):
            candidate = (x + dx, y + dy)
            if self.in_bounds(candidate):
                results.append(candidate)
        return results

    def tiles_in_square(self, center: Position, radius: int) -> list[Position]:
        cx, cy = center
        tiles: list[Position] = []
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                pos = (x, y)
                if self.in_bounds(pos):
                    tiles.append(pos)
        return tiles

    @staticmethod
    def default_obstacles() -> set[Position]:
        return {(2, 3), (5, 3), (2, 4), (5, 4)}

    @staticmethod
    def preset_obstacles(name: str, rng: random.Random | None = None) -> set[Position]:
        rng = rng or random.Random()
        presets: dict[str, set[Position]] = {
            "classic": {(2, 3), (5, 3), (2, 4), (5, 4)},
            "wings": {(1, 2), (6, 2), (1, 5), (6, 5), (2, 3), (5, 4)},
            "river": {(3, 2), (4, 2), (2, 3), (5, 3), (2, 4), (5, 4), (3, 5), (4, 5)},
            "fort": {(1, 2), (6, 2), (3, 2), (4, 2), (1, 5), (6, 5), (3, 5), (4, 5)},
            "cross": {(3, 1), (4, 1), (2, 3), (5, 3), (2, 4), (5, 4), (3, 6), (4, 6)},
        }
        if name == "chaos":
            return Board.default_obstacles() | Board.symmetric_random_obstacles(rng)
        return set(presets.get(name, Board.default_obstacles()))

    @staticmethod
    def symmetric_random_obstacles(rng: random.Random | None = None) -> set[Position]:
        rng = rng or random.Random()
        anchors = [
            (1, 2), (2, 2), (5, 2), (6, 2),
            (0, 3), (1, 3), (6, 3), (7, 3),
        ]
        pair_count = rng.choice((1, 2))
        chosen: set[Position] = set()
        for anchor in rng.sample(anchors, k=pair_count):
            mirror = (BOARD_SIZE - 1 - anchor[0], BOARD_SIZE - 1 - anchor[1])
            chosen.add(anchor)
            chosen.add(mirror)
        return chosen

    @staticmethod
    def distance(a: Position, b: Position) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])
