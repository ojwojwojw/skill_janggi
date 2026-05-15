from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from game.ai.helpers import diagonal_tiles, line_tiles
from game.ai.types import AIAction
from game.model.board import Board, Position
from game.model.constants import UnitType
from game.model.unit import Unit

if TYPE_CHECKING:
    from game.ai.brain import SimpleAI


def simulate_move(units: list[Unit], unit_id: str, move_target: Position) -> list[Unit]:
    """가상 이동 결과를 원본 리스트를 건드리지 않고 복제해 만든다."""
    return [replace(unit, position=move_target) if unit.id == unit_id else replace(unit) for unit in units]


def find_unit(units: list[Unit], unit_id: str) -> Unit | None:
    """살아 있는 유닛 목록에서 id로 유닛을 찾는다."""
    return next((unit for unit in units if unit.id == unit_id and unit.is_alive()), None)


def actions_from_position(ai: SimpleAI, unit: Unit, board: Board, units: list[Unit]) -> list[AIAction]:
    """현재 위치 기준으로 공격/스킬 행동 후보와 초기 점수를 생성한다."""
    enemies = [candidate for candidate in units if candidate.team != unit.team and candidate.is_alive()]
    allies = [candidate for candidate in units if candidate.team == unit.team and candidate.is_alive()]
    actions: list[AIAction] = []

    for target in unit.attack_targets(board, units):
        score = score_attack(ai, unit, target, board, enemies)
        victim = next((enemy for enemy in enemies if enemy.position == target), None)
        if victim is not None and ai._enemy_threatens_ai_king(victim, board, enemies, allies):
            score += 80.0
        actions.append(AIAction(unit_id=unit.id, action_type="attack", action_target=target, score=score))

    for target in unit.skill_targets(board, units):
        score = score_skill(ai, unit, target, board, units, enemies)
        if score <= 0:
            continue

        affected_enemies = [
            enemy
            for enemy in enemies
            if enemy.position == target or enemy.position in board.tiles_in_square(target, 1)
        ]
        if any(ai._enemy_threatens_ai_king(enemy, board, enemies, allies) for enemy in affected_enemies):
            score += 70.0
        actions.append(AIAction(unit_id=unit.id, action_type="skill", action_target=target, score=score))

    if unit.unit_type == UnitType.MAGE:
        has_skill_option = any(action.action_type == "skill" for action in actions)
        if has_skill_option:
            for action in actions:
                if action.action_type == "skill":
                    action.score += 44.0
                elif action.action_type == "attack":
                    action.score -= 34.0

    if unit.unit_type == UnitType.KING and unit.boss:
        has_skill_option = any(action.action_type == "skill" for action in actions)
        if has_skill_option:
            for action in actions:
                if action.action_type == "skill":
                    action.score += 72.0
                elif action.action_type == "attack":
                    action.score -= 26.0

    return actions


def score_attack(ai: SimpleAI, unit: Unit, target: Position, board: Board, enemies: list[Unit]) -> float:
    """기본 공격 하나의 가치를 킬각, 왕 압박, 병종 특성까지 반영해 평가한다."""
    victim = next(enemy for enemy in enemies if enemy.position == target)
    score = 46.0 + unit.attack_power() * 6.0

    if victim.unit_type == UnitType.KING:
        score += 120.0
    if victim.hp <= unit.attack_power():
        score += 40.0

    score += max(0, 6 - board.distance(unit.position, target))

    if unit.is_melee():
        score += 8.0
    if unit.unit_type == UnitType.BISHOP:
        score += 6.0
    if unit.unit_type == UnitType.LANCER:
        score += 4.0
    if unit.unit_type == UnitType.MAGE:
        score += 22.0
        if board.distance(unit.position, target) <= 1:
            score += 12.0
    if unit.unit_type == UnitType.ARCHER:
        score += 26.0

    if unit.unit_type in {UnitType.ARCHER, UnitType.MAGE}:
        if ai._is_intruder_tile(target):
            score += 70.0
        if victim.unit_type in {UnitType.SWORDMAN, UnitType.KNIGHT, UnitType.LANCER}:
            score += 18.0

    if ai.difficulty >= 4 and victim.hp <= unit.attack_power():
        score += 22.0
    if ai.difficulty >= 4 and victim.unit_type == UnitType.KING:
        score += 62.0
        if unit.unit_type in {UnitType.SWORDMAN, UnitType.KNIGHT, UnitType.LANCER}:
            score += 36.0
        elif unit.unit_type in {UnitType.ARCHER, UnitType.MAGE, UnitType.BISHOP}:
            score += 28.0 + max(0, 4 - victim.hp) * 8.0
    if ai.difficulty >= 5:
        score += ai._pressure_bonus(target, board, enemies)
    if ai.difficulty >= 6 and unit.is_melee():
        score += 12.0
    if ai.difficulty >= 6 and unit.unit_type in {UnitType.KING, UnitType.MAGE}:
        score += 14.0
    if ai.difficulty >= 7:
        threatened_enemy = ai._nearby_enemy_count(target, enemies, board)
        if threatened_enemy:
            score += threatened_enemy * 4.0
        if unit.unit_type == UnitType.KING:
            score += 18.0

    return score


def score_skill(ai: SimpleAI, unit: Unit, target: Position, board: Board, units: list[Unit], enemies: list[Unit]) -> float:
    """병종별 스킬 효과를 기준으로 스킬 타일 점수를 계산한다."""
    if unit.unit_type == UnitType.KING:
        if unit.boss:
            affected = {tile for tile in board.tiles_in_square(target, 1) if not board.is_blocked(tile)}
            hits = [enemy for enemy in enemies if enemy.position in affected]
            if not hits:
                return -1.0
            king_hit = any(enemy.unit_type == UnitType.KING for enemy in hits)
            base = 124.0 + len(hits) * 34.0 + (62.0 if king_hit else 0.0)
            if len(hits) >= 2:
                base += 22.0
            return base
        return 18.0 if unit.hp <= 4 and unit.shield_turns == 0 else -1.0

    if unit.unit_type == UnitType.SWORDMAN:
        victim = next((enemy for enemy in enemies if enemy.position == target), None)
        base = 56.0 if victim else 18.0
        if victim and victim.unit_type == UnitType.KING:
            base += 56.0
        if ai.difficulty >= 4:
            base += ai._pressure_bonus(target, board, enemies)
        if ai.difficulty >= 6 and victim and victim.hp <= 2:
            base += 22.0
        return base

    if unit.unit_type == UnitType.ARCHER:
        hits = [enemy for enemy in enemies if enemy.position in line_tiles(unit.position, target, board, 3)]
        if not hits:
            return -1.0
        king_hit = any(enemy.unit_type == UnitType.KING for enemy in hits)
        return 26.0 + len(hits) * (22.0 if ai.difficulty >= 4 else 18.0) + (28.0 if king_hit else 0.0)

    if unit.unit_type == UnitType.MAGE:
        affected = {tile for tile in board.tiles_in_square(target, 1) if not board.is_blocked(tile)}
        hits = [enemy for enemy in enemies if enemy.position in affected]
        if not hits:
            return -1.0
        king_hit = any(enemy.unit_type == UnitType.KING for enemy in hits)
        base = 26.0 + len(hits) * (24.0 if ai.difficulty >= 4 else 20.0) + (52.0 if king_hit else 0.0)
        if len(hits) == 1:
            base += 10.0
        elif len(hits) >= 3:
            base += 18.0
        if ai.difficulty >= 6 and len(hits) >= 2:
            base += 24.0
        return base

    if unit.unit_type == UnitType.KNIGHT:
        victim = next((enemy for enemy in enemies if enemy.position == target), None)
        if victim:
            base = 54.0 + (18.0 if victim.hp <= 2 else 0.0)
            if victim.unit_type == UnitType.KING:
                base += 48.0
            if ai.difficulty >= 4:
                base += ai._pressure_bonus(target, board, enemies)
            if ai.difficulty >= 6:
                base += 22.0
            return base
        return 16.0 - min(board.distance(target, enemy.position) for enemy in enemies)

    if unit.unit_type == UnitType.BISHOP:
        hits = [enemy for enemy in enemies if enemy.position in diagonal_tiles(unit.position, target, board, 4)]
        if not hits:
            return -1.0
        king_hit = any(enemy.unit_type == UnitType.KING for enemy in hits)
        return 28.0 + len(hits) * (26.0 if ai.difficulty >= 4 else 22.0) + (24.0 if king_hit else 0.0)

    if unit.unit_type == UnitType.LANCER:
        victim = next((enemy for enemy in enemies if enemy.position == target), None)
        if not victim:
            return -1.0
        base = 48.0 + (18.0 if victim.hp <= 2 else 0.0)
        if ai.difficulty >= 4 and victim.unit_type == UnitType.KING:
            base += 50.0
        if ai.difficulty >= 6:
            base += 22.0
        return base

    return -1.0


def score_move(ai: SimpleAI, unit: Unit, move: Position, board: Board, units: list[Unit]) -> float:
    """이동 후의 압박, 안전성, 후속 행동 가능성을 종합해 이동 점수를 계산한다."""
    enemies = [candidate for candidate in units if candidate.team != unit.team and candidate.is_alive()]
    allies = [candidate for candidate in units if candidate.team == unit.team and candidate.is_alive()]

    current_enemy_dist = min(board.distance(unit.position, enemy.position) for enemy in enemies)
    nearest_enemy = min(board.distance(move, enemy.position) for enemy in enemies)
    threatened = ai._tile_threat_count(move, board, enemies, allies)
    current_attack_count = len(unit.attack_targets(board, units))
    current_skill_count = len(unit.skill_targets(board, units))
    current_intruder_attack_count = sum(1 for target in unit.attack_targets(board, units) if ai._is_intruder_tile(target))

    simulated = ai._simulate_move(units, unit.id, move)
    moved_unit = ai._find_unit(simulated, unit.id)

    attack_count = 0
    skill_count = 0
    if moved_unit is not None:
        attack_count = len(moved_unit.attack_targets(board, simulated))
        skill_count = len(moved_unit.skill_targets(board, simulated))

    score = 18.0 - nearest_enemy * 2.2

    if nearest_enemy < current_enemy_dist:
        score += 7.0

    if threatened == 0:
        score += 6.0
    else:
        score -= threatened * 6.5

    score += attack_count * 4.0 + skill_count * 2.5

    if attack_count == 0 and skill_count == 0:
        score -= 8.0

    if nearest_enemy >= current_enemy_dist and attack_count == 0 and skill_count == 0:
        score -= 6.0

    if unit.unit_type in {UnitType.KNIGHT, UnitType.BISHOP}:
        score += 3.0

    if unit.unit_type == UnitType.KING:
        score -= threatened * 8.0
        if nearest_enemy <= 2:
            score -= 14.0
        if unit.shield_turns > 0 and attack_count == 0 and skill_count == 0:
            score -= 18.0

    if unit.unit_type in {UnitType.ARCHER, UnitType.MAGE, UnitType.BISHOP} and nearest_enemy <= 1 and attack_count == 0:
        score -= 16.0

    if unit.unit_type == UnitType.MAGE and nearest_enemy <= 2 and skill_count == 0:
        score -= 8.0

    if unit.unit_type in {UnitType.ARCHER, UnitType.MAGE}:
        moved_attack_targets = moved_unit.attack_targets(board, simulated) if moved_unit is not None else []
        moved_intruder_attack_count = sum(1 for target in moved_attack_targets if ai._is_intruder_tile(target))

        if current_attack_count > 0 and attack_count <= current_attack_count:
            score -= 72.0
        if current_intruder_attack_count > 0 and moved_intruder_attack_count == 0:
            score -= 140.0
        if current_intruder_attack_count > 0 and attack_count <= current_attack_count:
            score -= 55.0
        if current_skill_count > 0 and attack_count == 0 and skill_count <= current_skill_count:
            score -= 24.0

    if unit.unit_type == UnitType.MAGE:
        mage_history = ai.recent_positions.get(unit.id, [])
        current_attack_count = len(unit.attack_targets(board, units))
        current_skill_count = len(unit.skill_targets(board, units))

        if attack_count == 0 and skill_count == 0:
            score -= 45.0
        if len(mage_history) >= 2 and move == mage_history[-2]:
            score -= 75.0
        if len(mage_history) >= 3 and move in mage_history[-3:]:
            score -= 45.0
        if len(mage_history) >= 4 and move in mage_history[-4:]:
            score -= 35.0

        if moved_unit is not None:
            can_do_something_after_move = bool(moved_unit.attack_targets(board, simulated) or moved_unit.skill_targets(board, simulated))
            if not can_do_something_after_move:
                score -= 60.0
            else:
                score += 18.0

            if attack_count > 0:
                score += 96.0 + attack_count * 22.0
            elif current_attack_count == 0 and nearest_enemy <= 2:
                score += 34.0

            if skill_count > 0:
                score += 26.0 + skill_count * 7.0

            if nearest_enemy < current_enemy_dist:
                score += 22.0

            if current_skill_count == 0 and nearest_enemy <= 3:
                score += 18.0

            priority_enemy_for_mage = ai._priority_enemy_against_ai_king(board, enemies, allies)
            if priority_enemy_for_mage is not None:
                current_priority_dist = board.distance(unit.position, priority_enemy_for_mage.position)
                moved_priority_dist = board.distance(move, priority_enemy_for_mage.position)
                can_pressure_priority_enemy = (
                    priority_enemy_for_mage.position in moved_unit.attack_targets(board, simulated)
                    or priority_enemy_for_mage.position in moved_unit.skill_targets(board, simulated)
                )

                if can_pressure_priority_enemy:
                    score += 65.0
                else:
                    score -= 55.0

                if moved_priority_dist < current_priority_dist:
                    score += 30.0
                if moved_priority_dist <= 1:
                    score += 45.0
                elif moved_priority_dist <= 2:
                    score += 24.0

                if moved_priority_dist >= current_priority_dist and not can_pressure_priority_enemy:
                    score -= 70.0

        if nearest_enemy <= 1:
            score -= 62.0
            if attack_count > 0 and skill_count == 0:
                score -= 42.0
        elif nearest_enemy <= 2 and threatened > 0 and attack_count > 0 and skill_count == 0:
            score -= 32.0
        if attack_count > 0 and skill_count == 0 and nearest_enemy <= 2:
            score -= 26.0
        if skill_count > 0 and nearest_enemy >= 2:
            score += 18.0

    if ai.difficulty >= 4:
        score += ai._threatened_targets_bonus(unit, move, board, units)
        score -= threatened * 2.0

    if ai.difficulty >= 5:
        score += ai._king_lane_bonus(move, board, enemies)

    if ai.difficulty >= 6:
        score -= threatened * 3.5
        score += attack_count * 8.0 + skill_count * 5.0
        if attack_count == 0 and skill_count == 0:
            score -= 22.0
        if nearest_enemy >= current_enemy_dist and attack_count == 0:
            score -= 10.0
        if unit.unit_type in {UnitType.MAGE, UnitType.KING} and ai._adjacent_blocked_count(move, board) >= 2:
            score -= 8.0
        if unit.unit_type in {UnitType.MAGE, UnitType.KING} and attack_count == 0 and skill_count == 0:
            score -= 12.0

    if ai.difficulty >= 7 and unit.unit_type == UnitType.KING:
        score += 16.0 if threatened == 0 else -threatened * 10.0
        if attack_count == 0 and skill_count == 0:
            score -= 28.0
        if attack_count > 0 or skill_count > 0:
            score += 18.0

    previous_position = ai.last_positions.get(unit.id)
    if previous_position == move:
        score -= 18.0 if unit.unit_type == UnitType.BISHOP else 12.0

    previous_target = ai.last_targets.get(unit.id)
    if previous_target == move:
        score -= 10.0 if ai.difficulty < 6 else 14.0

    if ai.difficulty >= 6 and ai._adjacent_blocked_count(unit.position, board) >= 2 and ai._adjacent_blocked_count(move, board) >= 2:
        score -= 10.0

    history = ai.recent_positions.get(unit.id, [])
    if len(history) >= 2 and move == history[-2]:
        score -= 20.0
    if len(history) >= 3 and move in history[-3:]:
        score -= 8.0
    if len(history) >= 4 and move in history[-4:]:
        score -= 12.0 if attack_count == 0 and skill_count == 0 else 5.0
    if len(history) >= 3 and len(set(history[-3:] + [move])) <= 2:
        score -= 18.0 if attack_count == 0 and skill_count == 0 else 8.0

    if unit.unit_type == UnitType.KING and len(history) >= 3:
        recent_loop = history[-3:] + [move]
        if len(set(recent_loop)) <= 2:
            score -= 28.0

    threatening_enemy = ai._priority_enemy_against_ai_king(board, enemies, allies)
    if threatening_enemy is not None:
        current_priority_dist = board.distance(unit.position, threatening_enemy.position)
        moved_priority_dist = board.distance(move, threatening_enemy.position)

        if unit.unit_type == UnitType.KING:
            if moved_priority_dist >= current_priority_dist:
                score -= 24.0
            else:
                score += 4.0
        else:
            if moved_priority_dist < current_priority_dist:
                score += 18.0
            elif moved_priority_dist > current_priority_dist:
                score -= 10.0

            score += ai._support_priority_enemy_bonus(unit, threatening_enemy, board, units, move)

            if moved_unit is not None:
                attack_targets = moved_unit.attack_targets(board, simulated)
                skill_targets = moved_unit.skill_targets(board, simulated)
            else:
                attack_targets = []
                skill_targets = []

            if moved_priority_dist >= current_priority_dist and attack_count == 0 and skill_count == 0:
                score -= 18.0
            if moved_priority_dist >= 3 and threatening_enemy.position not in attack_targets:
                score -= 10.0
            if moved_priority_dist <= 2:
                score += 8.0
            if ai.last_actor_id == unit.id and ai.same_actor_streak >= 2 and attack_count == 0 and skill_count == 0:
                score -= 14.0 + ai.same_actor_streak * 4.0

    enemy_king = ai._priority_enemy_king(enemies)
    if enemy_king is not None and moved_unit is not None:
        current_king_dist = board.distance(unit.position, enemy_king.position)
        moved_king_dist = board.distance(move, enemy_king.position)
        king_attack_available = enemy_king.position in moved_unit.attack_targets(board, simulated)
        king_skill_available = enemy_king.position in moved_unit.skill_targets(board, simulated)

        if unit.unit_type in {UnitType.SWORDMAN, UnitType.KNIGHT, UnitType.LANCER, UnitType.KING}:
            if moved_king_dist < current_king_dist:
                score += 16.0 + max(0, 4 - moved_king_dist) * 6.0
            elif moved_king_dist > current_king_dist and attack_count == 0 and skill_count == 0:
                score -= 14.0
            if moved_king_dist <= 2:
                score += 18.0
            if king_attack_available or king_skill_available:
                score += 42.0
            if unit.unit_type in {UnitType.KNIGHT, UnitType.LANCER}:
                if moved_king_dist <= 3:
                    score += 22.0
                if king_skill_available:
                    score += 34.0
                if moved_king_dist < current_king_dist and (attack_count > 0 or skill_count > 0):
                    score += 18.0
        else:
            if king_attack_available:
                score += 68.0
            if king_skill_available:
                score += 58.0
            if enemy_king.hp <= 3 and (king_attack_available or king_skill_available):
                score += 28.0
            if moved_king_dist < current_king_dist and (attack_count > 0 or skill_count > 0):
                score += 22.0
            elif moved_king_dist > current_king_dist and attack_count == 0 and skill_count == 0:
                score -= 12.0

    return score
