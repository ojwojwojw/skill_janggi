from __future__ import annotations

import random
from dataclasses import dataclass, field

from game.model.constants import BOARD_SIZE

Position = tuple[int, int]


@dataclass(slots=True)
class Board:
    """보드 크기, 장애물, 좌표 계산을 담당하는 순수 모델."""

    width: int = BOARD_SIZE
    height: int = BOARD_SIZE
    blocked_tiles: set[Position] = field(default_factory=set)

    def in_bounds(self, position: Position) -> bool:
        """좌표가 현재 보드 범위 안에 있는지 확인한다."""
        x, y = position
        return 0 <= x < self.width and 0 <= y < self.height

    def is_blocked(self, position: Position) -> bool:
        """좌표가 장애물 타일인지 확인한다."""
        return position in self.blocked_tiles

    def is_walkable(self, position: Position) -> bool:
        """좌표가 보드 안에 있고 장애물도 아닌지 확인한다."""
        return self.in_bounds(position) and not self.is_blocked(position)

    def orthogonal_positions(self, origin: Position, distance: int) -> list[Position]:
        """기준 좌표에서 상하좌우 방향 후보 타일을 만든다."""
        x, y = origin
        results: list[Position] = []
        for step in range(1, distance + 1):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                candidate = (x + dx * step, y + dy * step)
                if self.in_bounds(candidate):
                    results.append(candidate)
        return results

    def diagonal_positions(self, origin: Position, distance: int) -> list[Position]:
        """기준 좌표에서 대각선 방향 후보 타일을 만든다."""
        x, y = origin
        results: list[Position] = []
        for step in range(1, distance + 1):
            for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                candidate = (x + dx * step, y + dy * step)
                if self.in_bounds(candidate):
                    results.append(candidate)
        return results

    def knight_positions(self, origin: Position) -> list[Position]:
        """나이트 점프 패턴에 해당하는 후보 타일을 만든다."""
        x, y = origin
        results: list[Position] = []
        for dx, dy in ((1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)):
            candidate = (x + dx, y + dy)
            if self.in_bounds(candidate):
                results.append(candidate)
        return results

    def tiles_in_square(self, center: Position, radius: int) -> list[Position]:
        """중심 타일 기준 정사각형 범위의 모든 타일을 반환한다."""
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
        """기본 전장의 장애물 배치를 돌려준다."""
        return {(2, 3), (5, 3), (2, 4), (5, 4)}

    @staticmethod
    def preset_obstacles(name: str, rng: random.Random | None = None) -> set[Position]:
        """맵 이름에 맞는 장애물 프리셋을 생성한다."""
        rng = rng or random.Random()
        presets: dict[str, set[Position]] = {
            "classic": {(2, 3), (5, 3), (2, 4), (5, 4)},
            "wings": {(1, 2), (6, 2), (1, 5), (6, 5), (2, 3), (5, 4)},
            "river": {(3, 2), (4, 2), (2, 3), (5, 3), (2, 4), (5, 4), (3, 5), (4, 5)},
            "fort": {(1, 2), (6, 2), (3, 2), (4, 2), (1, 5), (6, 5), (3, 5), (4, 5)},
            "cross": {(3, 1), (4, 1), (2, 3), (5, 3), (2, 4), (5, 4), (3, 6), (4, 6)},
            "diamond": {(3, 2), (2, 3), (5, 3), (2, 4), (5, 4), (4, 5)},
            "lanes": {(2, 2), (5, 2), (3, 3), (4, 3), (3, 4), (4, 4), (2, 5), (5, 5)},
        }
        if name == "chaos":
            return Board.default_obstacles() | Board.symmetric_random_obstacles(rng)
        return set(presets.get(name, Board.default_obstacles()))

    @staticmethod
    def symmetric_random_obstacles(rng: random.Random | None = None) -> set[Position]:
        """혼전 맵용 대칭 랜덤 장애물을 생성한다."""
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
        """두 타일 사이의 맨해튼 거리를 계산한다."""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])
