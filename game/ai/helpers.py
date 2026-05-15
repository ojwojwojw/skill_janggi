from __future__ import annotations

from typing import TYPE_CHECKING

from game.model.board import Board, Position
from game.model.constants import Team, UnitType
from game.model.unit import Unit

if TYPE_CHECKING:
    from game.ai.brain import SimpleAI


def line_tiles(origin: Position, target: Position, board: Board, max_range: int) -> set[Position]:
    """원점에서 목표 방향으로 뻗는 직선 타일 집합을 만든다."""
    dx = 0 if target[0] == origin[0] else (1 if target[0] > origin[0] else -1)
    dy = 0 if target[1] == origin[1] else (1 if target[1] > origin[1] else -1)
    tiles: set[Position] = set()
    cursor = origin

    for _ in range(max_range):
        cursor = (cursor[0] + dx, cursor[1] + dy)
        if not board.in_bounds(cursor) or board.is_blocked(cursor):
            break
        tiles.add(cursor)

    return tiles


def diagonal_tiles(origin: Position, target: Position, board: Board, max_range: int) -> set[Position]:
    """원점에서 목표 방향으로 뻗는 대각선 타일 집합을 만든다."""
    dx = 1 if target[0] > origin[0] else -1
    dy = 1 if target[1] > origin[1] else -1
    tiles: set[Position] = set()
    cursor = origin

    for _ in range(max_range):
        cursor = (cursor[0] + dx, cursor[1] + dy)
        if not board.in_bounds(cursor) or board.is_blocked(cursor):
            break
        tiles.add(cursor)

    return tiles


def is_between_king_and_threat(tile: Position, king_pos: Position, threat_pos: Position, board: Board) -> bool:
    """타일이 왕과 위협 유닛 사이의 차단 위치인지 판정한다."""
    if tile == king_pos or tile == threat_pos:
        return False

    kx, ky = king_pos
    tx, ty = threat_pos
    x, y = tile

    same_row = ky == ty == y and min(kx, tx) < x < max(kx, tx)
    same_col = kx == tx == x and min(ky, ty) < y < max(ky, ty)
    same_diag = abs(kx - tx) == abs(ky - ty) and abs(kx - x) == abs(ky - y) and abs(tx - x) == abs(ty - y)
    between_diag = same_diag and min(kx, tx) < x < max(kx, tx) and min(ky, ty) < y < max(ky, ty)

    return same_row or same_col or between_diag


def tile_threat_count(tile: Position, board: Board, enemies: list[Unit], allies: list[Unit]) -> int:
    """특정 타일을 즉시 위협할 수 있는 적 수를 센다."""
    all_units = enemies + allies
    count = 0
    for enemy in enemies:
        if tile in enemy.attack_targets(board, all_units) or tile in enemy.skill_targets(board, all_units):
            count += 1
    return count


def threatened_targets_bonus(ai: SimpleAI, unit: Unit, move: Position, board: Board, units: list[Unit]) -> float:
    """이동 후 늘어나는 공격/스킬 위협량을 보너스로 환산한다."""
    simulated = ai._simulate_move(units, unit.id, move)
    moved_unit = ai._find_unit(simulated, unit.id)

    if moved_unit is None:
        return 0.0

    attack_targets = moved_unit.attack_targets(board, simulated)
    skill_targets = moved_unit.skill_targets(board, simulated)

    bonus = len(attack_targets) * 9.0
    bonus += len(skill_targets) * 4.0

    if any(enemy.unit_type == UnitType.KING and enemy.position in attack_targets for enemy in simulated if enemy.team != moved_unit.team):
        bonus += 20.0

    return bonus


def pressure_bonus(tile: Position, board: Board, enemies: list[Unit]) -> float:
    """적, 특히 적 왕에게 가까워지는 압박 가치를 점수화한다."""
    if not enemies:
        return 0.0

    nearest_enemy = min(board.distance(tile, enemy.position) for enemy in enemies)
    nearest_king = min(
        (board.distance(tile, enemy.position) for enemy in enemies if enemy.unit_type == UnitType.KING),
        default=nearest_enemy,
    )

    return max(0.0, 8.0 - nearest_enemy * 1.5) + max(0.0, 10.0 - nearest_king * 2.0)


def king_lane_bonus(tile: Position, board: Board, enemies: list[Unit]) -> float:
    """적 왕을 향한 접근 라인 가치만 따로 계산한다."""
    king = next((enemy for enemy in enemies if enemy.unit_type == UnitType.KING), None)
    if king is None:
        return 0.0
    distance = board.distance(tile, king.position)
    return max(0.0, 12.0 - distance * 2.5)


def nearby_enemy_count(tile: Position, enemies: list[Unit], board: Board) -> int:
    """주변 2칸 안에 있는 적 수를 센다."""
    return sum(1 for enemy in enemies if board.distance(tile, enemy.position) <= 2)


def adjacent_blocked_count(tile: Position, board: Board) -> int:
    """타일 주변 상하좌우에 막힌 칸이 몇 개인지 센다."""
    return sum(1 for adjacent in board.orthogonal_positions(tile, 1) if board.is_blocked(adjacent))


def is_intruder_tile(tile: Position) -> bool:
    """AI 진영 입장에서 전방 침입 구역인지 판정한다."""
    return tile[1] <= 3


def enemy_threatens_ai_king(enemy: Unit, board: Board, enemies: list[Unit], allies: list[Unit]) -> bool:
    """적 유닛이 현재 턴에 AI 왕을 위협하는지 판정한다."""
    ai_king = next(
        (ally for ally in allies if ally.team == Team.AI and ally.unit_type == UnitType.KING and ally.is_alive()),
        None,
    )
    if ai_king is None:
        return False
    simulated = enemies + allies
    return ai_king.position in enemy.attack_targets(board, simulated) or ai_king.position in enemy.skill_targets(board, simulated)


def priority_enemy_against_ai_king(ai: SimpleAI, board: Board, enemies: list[Unit], allies: list[Unit]) -> Unit | None:
    """AI 왕 관점에서 가장 먼저 대응해야 할 적을 고른다."""
    ai_king = next(
        (ally for ally in allies if ally.team == Team.AI and ally.unit_type == UnitType.KING and ally.is_alive()),
        None,
    )

    streak_threats = [enemy for enemy in enemies if ai.king_threat_streaks.get(enemy.id, 0) >= 2]
    if streak_threats:
        return min(
            streak_threats,
            key=lambda enemy: (
                -ai.king_threat_streaks.get(enemy.id, 0),
                enemy.hp,
                board.distance(enemy.position, ai_king.position) if ai_king is not None else 0,
            ),
        )

    threatening = [enemy for enemy in enemies if enemy_threatens_ai_king(enemy, board, enemies, allies)]
    if threatening:
        return min(threatening, key=lambda enemy: enemy.hp)

    if ai_king is None:
        return None
    return min(enemies, key=lambda enemy: board.distance(enemy.position, ai_king.position), default=None)


def priority_enemy_king(enemies: list[Unit]) -> Unit | None:
    """살아 있는 적 왕을 반환한다."""
    return next((enemy for enemy in enemies if enemy.unit_type == UnitType.KING and enemy.is_alive()), None)


def available_support_strikers(allies: list[Unit]) -> list[Unit]:
    """지원형 공격 역할을 맡길 수 있는 AI 유닛만 추린다."""
    return [
        ally
        for ally in allies
        if ally.is_alive() and ally.unit_type in {UnitType.KNIGHT, UnitType.LANCER, UnitType.MAGE}
    ]


def refresh_king_threat_memory(ai: SimpleAI, board: Board, ai_king: Unit, enemies: list[Unit], allies: list[Unit]) -> None:
    """왕을 위협한 적의 누적 위협 기록을 업데이트한다."""
    active_ids: set[str] = set()

    for enemy in enemies:
        threatens = enemy_threatens_ai_king(enemy, board, enemies, allies)
        adjacent = board.distance(enemy.position, ai_king.position) <= 1
        close = board.distance(enemy.position, ai_king.position) <= 2

        if threatens or adjacent:
            active_ids.add(enemy.id)
            ai.king_threat_streaks[enemy.id] = ai.king_threat_streaks.get(enemy.id, 0) + 1
        elif close:
            ai.king_threat_streaks[enemy.id] = ai.king_threat_streaks.get(enemy.id, 0) + 0
        elif enemy.id in ai.king_threat_streaks:
            ai.king_threat_streaks[enemy.id] = max(0, ai.king_threat_streaks[enemy.id] - 1)

    if ai.previous_ai_king_hp is not None and ai_king.hp < ai.previous_ai_king_hp:
        for enemy in enemies:
            if board.distance(enemy.position, ai_king.position) <= 2:
                ai.king_threat_streaks[enemy.id] = ai.king_threat_streaks.get(enemy.id, 0) + 2

    for enemy_id in list(ai.king_threat_streaks):
        if enemy_id not in active_ids and ai.king_threat_streaks[enemy_id] == 0:
            del ai.king_threat_streaks[enemy_id]


def is_ai_king_in_crisis(ai: SimpleAI, board: Board, enemies: list[Unit], allies: list[Unit]) -> bool:
    """직접 위협, 누적 압박, 최근 피해를 종합해 패닉 여부를 판단한다."""
    ai_king = next(
        (ally for ally in allies if ally.team == Team.AI and ally.unit_type == UnitType.KING and ally.is_alive()),
        None,
    )
    if ai_king is None:
        return False

    direct_threats = [enemy for enemy in enemies if enemy_threatens_ai_king(enemy, board, enemies, allies)]
    if direct_threats:
        return True

    repeated_threats = [
        enemy for enemy in enemies
        if ai.king_threat_streaks.get(enemy.id, 0) >= 3 and board.distance(enemy.position, ai_king.position) <= 2
    ]
    if repeated_threats:
        return True

    if ai.previous_ai_king_hp is not None and ai_king.hp < ai.previous_ai_king_hp:
        return True

    return False


def support_priority_enemy_bonus(
    ai: SimpleAI,
    unit: Unit,
    threatening_enemy: Unit,
    board: Board,
    units: list[Unit],
    move_target: Position | None = None,
) -> float:
    """보조 공격 유닛이 우선 목표를 압박할 때 줄 추가 보너스를 계산한다."""
    origin = move_target if move_target is not None else unit.position
    current_distance = board.distance(unit.position, threatening_enemy.position)
    moved_distance = board.distance(origin, threatening_enemy.position)

    simulated = units if move_target is None else ai._simulate_move(units, unit.id, move_target)
    moved_unit = ai._find_unit(simulated, unit.id)
    if moved_unit is None:
        return 0.0

    attack_targets = moved_unit.attack_targets(board, simulated)
    skill_targets = moved_unit.skill_targets(board, simulated)

    bonus = 0.0
    streak = ai.king_threat_streaks.get(threatening_enemy.id, 0)

    if threatening_enemy.position in attack_targets:
        bonus += 120.0 + streak * 35.0
    if threatening_enemy.position in skill_targets:
        bonus += 90.0 + streak * 30.0

    if moved_distance < current_distance:
        bonus += 35.0
    elif moved_distance > current_distance:
        bonus -= 28.0

    if moved_distance <= 2:
        bonus += 28.0

    if moved_distance >= 4 and threatening_enemy.position not in attack_targets and threatening_enemy.position not in skill_targets:
        bonus -= 32.0

    return bonus
