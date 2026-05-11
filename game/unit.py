from __future__ import annotations

from dataclasses import dataclass, field

from game.board import Board, Position
from game.constants import Team, UnitType
from game.skill import SKILLS


@dataclass(slots=True)
class Unit:
    id: str
    name: str
    unit_type: UnitType
    team: Team
    hp: int
    max_hp: int
    position: Position
    cooldowns: dict[str, int] = field(default_factory=dict)
    shield_turns: int = 0

    def is_alive(self) -> bool:
        return self.hp > 0

    def move(self, destination: Position) -> None:
        self.position = destination

    def attack(self, target: 'Unit') -> int:
        return target.take_damage(1)

    def use_skill(self) -> None:
        self.cooldowns['skill'] = SKILLS[self.unit_type].cooldown

    def can_use_skill(self) -> bool:
        return self.cooldowns.get('skill', 0) <= 0

    def take_damage(self, amount: int) -> int:
        actual = max(0, amount - (1 if self.shield_turns > 0 else 0))
        self.hp -= actual
        return actual

    def tick_cooldowns(self) -> None:
        for key, value in list(self.cooldowns.items()):
            self.cooldowns[key] = max(0, value - 1)
        if self.shield_turns > 0:
            self.shield_turns -= 1

    def basic_move_targets(self, board: Board, units: list['Unit']) -> list[Position]:
        occupied = {unit.position for unit in units if unit.is_alive() and unit.id != self.id}

        def add_if_open(candidates: list[Position]) -> list[Position]:
            return [pos for pos in candidates if board.is_walkable(pos) and pos not in occupied]

        if self.unit_type == UnitType.KING:
            return add_if_open(board.orthogonal_positions(self.position, 1))
        if self.unit_type == UnitType.SWORDMAN:
            return self._orthogonal_walk(board, units, 2)
        if self.unit_type == UnitType.ARCHER:
            return add_if_open(board.orthogonal_positions(self.position, 1))
        if self.unit_type == UnitType.MAGE:
            return add_if_open(board.diagonal_positions(self.position, 1))
        return []

    def attack_preview_tiles(self, board: Board) -> list[Position]:
        if self.unit_type in (UnitType.KING, UnitType.SWORDMAN):
            return [pos for pos in board.orthogonal_positions(self.position, 1) if not board.is_blocked(pos)]
        if self.unit_type == UnitType.ARCHER:
            return self._line_preview_tiles(board, 3)
        if self.unit_type == UnitType.MAGE:
            return [pos for pos in board.tiles_in_square(self.position, 1) if pos != self.position and not board.is_blocked(pos)]
        return []

    def attack_targets(self, board: Board, units: list['Unit']) -> list[Position]:
        enemies = {unit.position for unit in units if unit.is_alive() and unit.team != self.team}
        if self.unit_type in (UnitType.KING, UnitType.SWORDMAN):
            return [pos for pos in self.attack_preview_tiles(board) if pos in enemies]
        if self.unit_type == UnitType.ARCHER:
            return self._line_targets(board, units, 3, stop_after_first=True)
        if self.unit_type == UnitType.MAGE:
            return [pos for pos in self.attack_preview_tiles(board) if pos in enemies]
        return []

    def skill_targets(self, board: Board, units: list['Unit']) -> list[Position]:
        if not self.can_use_skill():
            return []
        if self.unit_type == UnitType.KING:
            return [self.position]
        if self.unit_type == UnitType.SWORDMAN:
            return self._charge_targets(board, units)
        if self.unit_type == UnitType.ARCHER:
            return self._line_skill_targets(board)
        if self.unit_type == UnitType.MAGE:
            return [tile for tile in board.tiles_in_square(self.position, 3) if not board.is_blocked(tile)]
        return []

    def _orthogonal_walk(self, board: Board, units: list['Unit'], max_steps: int) -> list[Position]:
        occupied = {unit.position for unit in units if unit.is_alive() and unit.id != self.id}
        valid: list[Position] = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for step in range(1, max_steps + 1):
                candidate = (self.position[0] + dx * step, self.position[1] + dy * step)
                if not board.is_walkable(candidate) or candidate in occupied:
                    break
                valid.append(candidate)
        return valid

    def _line_preview_tiles(self, board: Board, max_range: int) -> list[Position]:
        tiles: list[Position] = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for step in range(1, max_range + 1):
                candidate = (self.position[0] + dx * step, self.position[1] + dy * step)
                if not board.in_bounds(candidate):
                    break
                if board.is_blocked(candidate):
                    break
                tiles.append(candidate)
        return tiles

    def _line_targets(self, board: Board, units: list['Unit'], max_range: int, stop_after_first: bool) -> list[Position]:
        occupied = {unit.position: unit for unit in units if unit.is_alive() and unit.id != self.id}
        targets: list[Position] = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for step in range(1, max_range + 1):
                candidate = (self.position[0] + dx * step, self.position[1] + dy * step)
                if not board.in_bounds(candidate):
                    break
                if board.is_blocked(candidate):
                    break
                blocking = occupied.get(candidate)
                if blocking is None:
                    continue
                if blocking.team != self.team:
                    targets.append(candidate)
                if stop_after_first:
                    break
        return targets

    def _line_skill_targets(self, board: Board) -> list[Position]:
        targets: list[Position] = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for step in range(1, 4):
                candidate = (self.position[0] + dx * step, self.position[1] + dy * step)
                if not board.in_bounds(candidate):
                    break
                if board.is_blocked(candidate):
                    break
                targets.append(candidate)
        return targets

    def _charge_targets(self, board: Board, units: list['Unit']) -> list[Position]:
        occupied = {unit.position: unit for unit in units if unit.is_alive() and unit.id != self.id}
        targets: list[Position] = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for step in range(1, 4):
                candidate = (self.position[0] + dx * step, self.position[1] + dy * step)
                if not board.in_bounds(candidate) or board.is_blocked(candidate):
                    break
                blocker = occupied.get(candidate)
                if blocker is None:
                    targets.append(candidate)
                    continue
                if blocker.team != self.team:
                    targets.append(candidate)
                break
        return targets
