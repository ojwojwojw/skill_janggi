from __future__ import annotations

from dataclasses import dataclass, field

from game.board import Board, Position
from game.constants import Team, UnitType
from game.skill import SKILLS

ATTACK_POWER = {
    UnitType.KING: 1,
    UnitType.SWORDMAN: 1,
    UnitType.ARCHER: 1,
    UnitType.MAGE: 1,
    UnitType.KNIGHT: 1,
    UnitType.BISHOP: 1,
    UnitType.LANCER: 1,
}


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
    attack_bonus: int = 0
    armor: int = 0
    boss: bool = False

    def is_alive(self) -> bool:
        return self.hp > 0

    def is_melee(self) -> bool:
        return self.unit_type in {UnitType.KING, UnitType.SWORDMAN, UnitType.KNIGHT}

    def move(self, destination: Position) -> None:
        self.position = destination

    def attack_power(self) -> int:
        return ATTACK_POWER[self.unit_type] + self.attack_bonus

    def attack(self, target: "Unit", amount: int | None = None) -> int:
        return target.take_damage(self.attack_power() if amount is None else amount)

    def use_skill(self) -> None:
        self.cooldowns["skill"] = SKILLS[self.unit_type].cooldown

    def can_use_skill(self) -> bool:
        return self.cooldowns.get("skill", 0) <= 0

    def take_damage(self, amount: int) -> int:
        actual = max(0, amount - (1 if self.shield_turns > 0 else 0) - self.armor)
        self.hp -= actual
        return actual

    def tick_cooldowns(self) -> None:
        for key, value in list(self.cooldowns.items()):
            self.cooldowns[key] = max(0, value - 1)
        if self.shield_turns > 0:
            self.shield_turns -= 1

    def basic_move_targets(self, board: Board, units: list["Unit"]) -> list[Position]:
        occupied = {unit.position for unit in units if unit.is_alive() and unit.id != self.id}

        def open_tiles(candidates: list[Position]) -> list[Position]:
            return [pos for pos in candidates if board.is_walkable(pos) and pos not in occupied]

        if self.unit_type == UnitType.KING:
            return open_tiles(board.orthogonal_positions(self.position, 1))
        if self.unit_type == UnitType.SWORDMAN:
            return self._orthogonal_walk(board, units, 2)
        if self.unit_type == UnitType.ARCHER:
            return open_tiles(board.orthogonal_positions(self.position, 1))
        if self.unit_type == UnitType.MAGE:
            return open_tiles(board.diagonal_positions(self.position, 1))
        if self.unit_type == UnitType.KNIGHT:
            return open_tiles(board.knight_positions(self.position))
        if self.unit_type == UnitType.BISHOP:
            return self._diagonal_walk(board, units, 3)
        if self.unit_type == UnitType.LANCER:
            return self._orthogonal_walk(board, units, 2)
        return []

    def attack_preview_tiles(self, board: Board) -> list[Position]:
        if self.unit_type in {UnitType.KING, UnitType.SWORDMAN, UnitType.KNIGHT}:
            return [pos for pos in board.orthogonal_positions(self.position, 1) if not board.is_blocked(pos)]
        if self.unit_type == UnitType.ARCHER:
            return self._line_preview_tiles(board, 3)
        if self.unit_type == UnitType.MAGE:
            return [pos for pos in board.tiles_in_square(self.position, 1) if pos != self.position and not board.is_blocked(pos)]
        if self.unit_type == UnitType.BISHOP:
            return self._diagonal_preview_tiles(board, 3)
        if self.unit_type == UnitType.LANCER:
            return self._line_preview_tiles(board, 2)
        return []

    def attack_targets(self, board: Board, units: list["Unit"]) -> list[Position]:
        enemies = {unit.position for unit in units if unit.is_alive() and unit.team != self.team}
        if self.unit_type in {UnitType.KING, UnitType.SWORDMAN, UnitType.KNIGHT, UnitType.MAGE}:
            return [pos for pos in self.attack_preview_tiles(board) if pos in enemies]
        if self.unit_type in {UnitType.ARCHER, UnitType.LANCER}:
            return self._line_targets(board, units, 3 if self.unit_type == UnitType.ARCHER else 2, stop_after_first=True)
        if self.unit_type == UnitType.BISHOP:
            return self._diagonal_targets(board, units, 3, stop_after_first=True)
        return []

    def skill_targets(self, board: Board, units: list["Unit"]) -> list[Position]:
        if not self.can_use_skill():
            return []
        occupied = {unit.position: unit for unit in units if unit.is_alive() and unit.id != self.id}
        if self.unit_type == UnitType.KING:
            if self.boss:
                return [tile for tile in board.tiles_in_square(self.position, 2) if tile != self.position and not board.is_blocked(tile)]
            return [ally.position for ally in units if ally.is_alive() and ally.team == self.team]
        if self.unit_type == UnitType.SWORDMAN:
            return self._charge_targets(board, units)
        if self.unit_type == UnitType.ARCHER:
            return self._line_skill_targets(board, 3)
        if self.unit_type == UnitType.MAGE:
            return [tile for tile in board.tiles_in_square(self.position, 3) if not board.is_blocked(tile)]
        if self.unit_type == UnitType.KNIGHT:
            return [
                tile for tile in board.knight_positions(self.position)
                if board.is_walkable(tile) and (tile not in occupied or occupied[tile].team != self.team)
            ]
        if self.unit_type == UnitType.BISHOP:
            return self._diagonal_skill_targets(board, 4)
        if self.unit_type == UnitType.LANCER:
            return self._line_skill_targets(board, 3)
        return []

    def _orthogonal_walk(self, board: Board, units: list["Unit"], max_steps: int) -> list[Position]:
        occupied = {unit.position for unit in units if unit.is_alive() and unit.id != self.id}
        valid: list[Position] = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for step in range(1, max_steps + 1):
                candidate = (self.position[0] + dx * step, self.position[1] + dy * step)
                if not board.is_walkable(candidate) or candidate in occupied:
                    break
                valid.append(candidate)
        return valid

    def _diagonal_walk(self, board: Board, units: list["Unit"], max_steps: int) -> list[Position]:
        occupied = {unit.position for unit in units if unit.is_alive() and unit.id != self.id}
        valid: list[Position] = []
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
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
                if not board.in_bounds(candidate) or board.is_blocked(candidate):
                    break
                tiles.append(candidate)
        return tiles

    def _diagonal_preview_tiles(self, board: Board, max_range: int) -> list[Position]:
        tiles: list[Position] = []
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            for step in range(1, max_range + 1):
                candidate = (self.position[0] + dx * step, self.position[1] + dy * step)
                if not board.in_bounds(candidate) or board.is_blocked(candidate):
                    break
                tiles.append(candidate)
        return tiles

    def _line_targets(self, board: Board, units: list["Unit"], max_range: int, stop_after_first: bool) -> list[Position]:
        occupied = {unit.position: unit for unit in units if unit.is_alive() and unit.id != self.id}
        targets: list[Position] = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for step in range(1, max_range + 1):
                candidate = (self.position[0] + dx * step, self.position[1] + dy * step)
                if not board.in_bounds(candidate) or board.is_blocked(candidate):
                    break
                blocking = occupied.get(candidate)
                if blocking is None:
                    continue
                if blocking.team != self.team:
                    targets.append(candidate)
                if stop_after_first:
                    break
        return targets

    def _diagonal_targets(self, board: Board, units: list["Unit"], max_range: int, stop_after_first: bool) -> list[Position]:
        occupied = {unit.position: unit for unit in units if unit.is_alive() and unit.id != self.id}
        targets: list[Position] = []
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            for step in range(1, max_range + 1):
                candidate = (self.position[0] + dx * step, self.position[1] + dy * step)
                if not board.in_bounds(candidate) or board.is_blocked(candidate):
                    break
                blocking = occupied.get(candidate)
                if blocking is None:
                    continue
                if blocking.team != self.team:
                    targets.append(candidate)
                if stop_after_first:
                    break
        return targets

    def _line_skill_targets(self, board: Board, max_range: int) -> list[Position]:
        targets: list[Position] = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for step in range(1, max_range + 1):
                candidate = (self.position[0] + dx * step, self.position[1] + dy * step)
                if not board.in_bounds(candidate) or board.is_blocked(candidate):
                    break
                targets.append(candidate)
        return targets

    def _diagonal_skill_targets(self, board: Board, max_range: int) -> list[Position]:
        targets: list[Position] = []
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            for step in range(1, max_range + 1):
                candidate = (self.position[0] + dx * step, self.position[1] + dy * step)
                if not board.in_bounds(candidate) or board.is_blocked(candidate):
                    break
                targets.append(candidate)
        return targets

    def _charge_targets(self, board: Board, units: list["Unit"]) -> list[Position]:
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
