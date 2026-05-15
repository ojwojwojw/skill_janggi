from __future__ import annotations

from dataclasses import dataclass, field

from game.model.board import Board, Position
from game.model.constants import Team, UnitType
from game.model.skill import SKILLS

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
    """전투 중 개별 기물의 상태와 규칙을 담는 모델."""

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
        """현재 체력이 1 이상인지 반환한다."""
        return self.hp > 0

    def is_melee(self) -> bool:
        """근접 전투 유닛인지 반환한다."""
        return self.unit_type in {UnitType.KING, UnitType.SWORDMAN, UnitType.KNIGHT}

    def move(self, destination: Position) -> None:
        """유닛 위치를 새 타일로 갱신한다."""
        self.position = destination

    def attack_power(self) -> int:
        """현재 유닛의 실질 공격력을 계산한다."""
        return ATTACK_POWER[self.unit_type] + self.attack_bonus

    def attack(self, target: "Unit", amount: int | None = None) -> int:
        """대상 유닛에게 피해를 적용하고 실제 피해량을 돌려준다."""
        return target.take_damage(self.attack_power() if amount is None else amount)

    def use_skill(self) -> None:
        """스킬 사용 후 쿨다운을 설정한다."""
        self.cooldowns["skill"] = SKILLS[self.unit_type].cooldown

    def can_use_skill(self) -> bool:
        """스킬이 준비 상태인지 확인한다."""
        return self.cooldowns.get("skill", 0) <= 0

    def take_damage(self, amount: int) -> int:
        """보호막과 방어력을 반영해 피해를 적용한다."""
        actual = max(0, amount - (1 if self.shield_turns > 0 else 0) - self.armor)
        self.hp -= actual
        return actual

    def tick_cooldowns(self) -> None:
        """턴 종료 시 쿨다운과 보호막 지속 턴을 감소시킨다."""
        for key, value in list(self.cooldowns.items()):
            self.cooldowns[key] = max(0, value - 1)
        if self.shield_turns > 0:
            self.shield_turns -= 1

    def basic_move_targets(self, board: Board, units: list["Unit"]) -> list[Position]:
        """유닛 타입 규칙에 맞는 기본 이동 가능 타일을 계산한다."""
        occupied = {unit.position for unit in units if unit.is_alive() and unit.id != self.id}

        def open_tiles(candidates: list[Position]) -> list[Position]:
            """막힌 칸과 점유된 칸을 제외한 이동 가능 후보만 남긴다."""
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
        """실제 적 유무와 무관하게 공격 사거리 미리보기 타일을 만든다."""
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
        """현재 배치 기준으로 실제 공격 가능한 적 타일만 추린다."""
        enemies = {unit.position for unit in units if unit.is_alive() and unit.team != self.team}
        if self.unit_type in {UnitType.KING, UnitType.SWORDMAN, UnitType.KNIGHT, UnitType.MAGE}:
            return [pos for pos in self.attack_preview_tiles(board) if pos in enemies]
        if self.unit_type in {UnitType.ARCHER, UnitType.LANCER}:
            return self._line_targets(board, units, 3 if self.unit_type == UnitType.ARCHER else 2, stop_after_first=True)
        if self.unit_type == UnitType.BISHOP:
            return self._diagonal_targets(board, units, 3, stop_after_first=True)
        return []

    def skill_targets(self, board: Board, units: list["Unit"]) -> list[Position]:
        """유닛 타입과 쿨다운을 반영해 스킬 대상 타일을 계산한다."""
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
        """직선 이동형 유닛의 경로를 충돌 체크와 함께 계산한다."""
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
        """대각선 이동형 유닛의 경로를 충돌 체크와 함께 계산한다."""
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
        """직선 원거리 공격용 미리보기 타일을 만든다."""
        tiles: list[Position] = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for step in range(1, max_range + 1):
                candidate = (self.position[0] + dx * step, self.position[1] + dy * step)
                if not board.in_bounds(candidate) or board.is_blocked(candidate):
                    break
                tiles.append(candidate)
        return tiles

    def _diagonal_preview_tiles(self, board: Board, max_range: int) -> list[Position]:
        """대각 원거리 공격용 미리보기 타일을 만든다."""
        tiles: list[Position] = []
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            for step in range(1, max_range + 1):
                candidate = (self.position[0] + dx * step, self.position[1] + dy * step)
                if not board.in_bounds(candidate) or board.is_blocked(candidate):
                    break
                tiles.append(candidate)
        return tiles

    def _line_targets(self, board: Board, units: list["Unit"], max_range: int, stop_after_first: bool) -> list[Position]:
        """직선 방향으로 실제 적중 가능한 적 타일을 계산한다."""
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
        """대각선 방향으로 실제 적중 가능한 적 타일을 계산한다."""
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
        """직선형 스킬이 지정 가능한 타일을 계산한다."""
        targets: list[Position] = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for step in range(1, max_range + 1):
                candidate = (self.position[0] + dx * step, self.position[1] + dy * step)
                if not board.in_bounds(candidate) or board.is_blocked(candidate):
                    break
                targets.append(candidate)
        return targets

    def _diagonal_skill_targets(self, board: Board, max_range: int) -> list[Position]:
        """대각선형 스킬이 지정 가능한 타일을 계산한다."""
        targets: list[Position] = []
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            for step in range(1, max_range + 1):
                candidate = (self.position[0] + dx * step, self.position[1] + dy * step)
                if not board.in_bounds(candidate) or board.is_blocked(candidate):
                    break
                targets.append(candidate)
        return targets

    def _charge_targets(self, board: Board, units: list["Unit"]) -> list[Position]:
        """검병 돌진 스킬이 노릴 수 있는 직선 타일을 계산한다."""
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
