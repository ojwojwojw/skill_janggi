from __future__ import annotations

from typing import TYPE_CHECKING

from game.ai.types import AIAction
from game.model.board import Board
from game.model.constants import Team, UnitType
from game.model.unit import Unit

if TYPE_CHECKING:
    from game.ai.brain import SimpleAI


def king_defense_action_bonus(
    ai: SimpleAI,
    actor: Unit,
    action: AIAction,
    board: Board,
    units: list[Unit],
    ai_king: Unit | None,
    threatening_enemy: Unit,
    panic_mode: bool,
) -> float:
    """왕을 위협하는 적에 대응하도록 일반 행동 점수에 방어 보너스를 더한다."""
    score = 0.0
    streak = ai.king_threat_streaks.get(threatening_enemy.id, 0)

    if action.action_target == threatening_enemy.position:
        score += 120.0 + streak * 35.0
        if actor.unit_type != UnitType.KING:
            score += 45.0

    actor_position_after = action.move_target or actor.position

    if actor.unit_type != UnitType.KING:
        current_dist = board.distance(actor.position, threatening_enemy.position)
        moved_dist = board.distance(actor_position_after, threatening_enemy.position)

        if moved_dist < current_dist:
            score += 35.0
        elif moved_dist > current_dist:
            score -= 25.0

        if ai_king is not None:
            current_king_dist = board.distance(actor.position, ai_king.position)
            moved_king_dist = board.distance(actor_position_after, ai_king.position)
            if moved_king_dist < current_king_dist:
                score += 20.0
            elif moved_king_dist > current_king_dist:
                score -= 20.0

    if panic_mode:
        score *= 1.8

    return score


def filter_and_boost_panic_actions(
    ai: SimpleAI,
    actions: list[AIAction],
    board: Board,
    units: list[Unit],
    ai_king: Unit,
    threatening_enemy: Unit,
) -> list[AIAction]:
    """패닉 상태에서 의미 없는 행동을 약화하고 유효 방어 행동을 강화한다."""
    boosted: list[AIAction] = []

    for action in actions:
        actor = ai._find_unit(units, action.unit_id)
        if actor is None:
            continue

        defensive_score = panic_defense_score(ai, action, actor, board, units, ai_king, threatening_enemy)
        action.score += defensive_score
        if defensive_score <= 0 and action.action_type is None:
            action.score -= 180.0

        boosted.append(action)

    return boosted


def panic_defense_score(
    ai: SimpleAI,
    action: AIAction,
    actor: Unit,
    board: Board,
    units: list[Unit],
    ai_king: Unit,
    threatening_enemy: Unit,
) -> float:
    """왕이 급한 상황일 때 행동 하나가 얼마나 위협 해소에 기여하는지 계산한다."""
    score = 0.0
    streak = ai.king_threat_streaks.get(threatening_enemy.id, 0)

    if action.action_target == threatening_enemy.position:
        expected_damage = actor.attack_power()
        can_kill_threat = threatening_enemy.hp <= expected_damage

        if can_kill_threat:
            score += 520.0 + streak * 120.0
            if actor.unit_type != UnitType.KING:
                score += 120.0
        else:
            score += 120.0 + streak * 25.0
            if ai._enemy_threatens_ai_king(
                threatening_enemy,
                board,
                [u for u in units if u.team == Team.PLAYER and u.is_alive()],
                [u for u in units if u.team == Team.AI and u.is_alive()],
            ):
                score -= 170.0

    simulated = units
    moved_actor = actor
    actor_pos_after = actor.position

    if action.move_target is not None:
        simulated = ai._simulate_move(units, actor.id, action.move_target)
        found = ai._find_unit(simulated, actor.id)
        if found is not None:
            moved_actor = found
            actor_pos_after = action.move_target

    attack_targets = moved_actor.attack_targets(board, simulated)
    skill_targets = moved_actor.skill_targets(board, simulated)
    can_attack_after_move = threatening_enemy.position in attack_targets
    can_skill_after_move = threatening_enemy.position in skill_targets
    can_kill_after_move = threatening_enemy.hp <= moved_actor.attack_power()

    if can_attack_after_move:
        score += (320.0 if can_kill_after_move else 80.0) + streak * (80.0 if can_kill_after_move else 20.0)
    if can_skill_after_move:
        score += (260.0 if can_kill_after_move else 70.0) + streak * (60.0 if can_kill_after_move else 18.0)

    if actor.unit_type == UnitType.KING and action.move_target is not None:
        old_threats = ai._tile_threat_count(
            ai_king.position,
            board,
            [u for u in units if u.team == Team.PLAYER and u.is_alive()],
            [u for u in units if u.team == Team.AI and u.is_alive()],
        )
        new_threats = ai._tile_threat_count(
            action.move_target,
            board,
            [u for u in simulated if u.team == Team.PLAYER and u.is_alive()],
            [u for u in simulated if u.team == Team.AI and u.is_alive()],
        )

        old_enemy_dist = board.distance(actor.position, threatening_enemy.position)
        new_enemy_dist = board.distance(action.move_target, threatening_enemy.position)
        can_attack_threat = threatening_enemy.position in attack_targets
        can_skill_threat = threatening_enemy.position in skill_targets

        if new_threats < old_threats:
            score += 360.0
        if new_threats == 0:
            score += 260.0
        if new_threats > 0:
            score -= 240.0

        if new_enemy_dist < old_enemy_dist:
            if can_attack_threat or can_skill_threat:
                score += 70.0
            else:
                score -= 150.0

        if new_enemy_dist > old_enemy_dist:
            score += 220.0

        if action.action_type is None and new_enemy_dist <= 1 and not (can_attack_threat or can_skill_threat):
            score -= 120.0

    if actor.unit_type != UnitType.KING:
        before_dist = board.distance(actor.position, threatening_enemy.position)
        after_dist = board.distance(actor_pos_after, threatening_enemy.position)
        if after_dist < before_dist:
            score += 55.0 + max(0, 4 - after_dist) * 12.0
        elif after_dist > before_dist:
            score -= 110.0

    if actor.unit_type != UnitType.KING:
        before_king_dist = board.distance(actor.position, ai_king.position)
        after_king_dist = board.distance(actor_pos_after, ai_king.position)
        if after_king_dist < before_king_dist:
            score += 70.0
        elif after_king_dist > before_king_dist:
            score -= 70.0

    if actor.unit_type != UnitType.KING and action.move_target is not None:
        if ai._is_between_king_and_threat(action.move_target, ai_king.position, threatening_enemy.position, board):
            score += 240.0

    if actor.unit_type == UnitType.MAGE and action.move_target is not None:
        if action.action_type is None:
            score -= 260.0
        if not can_attack_after_move and not can_skill_after_move:
            score -= 220.0
        if (can_attack_after_move or can_skill_after_move) and not can_kill_after_move:
            score -= 90.0

    history = ai.recent_positions.get(actor.id, [])
    if action.move_target is not None and len(history) >= 2 and action.move_target == history[-2]:
        score -= 180.0
    if action.move_target is not None and len(history) >= 3 and len(set(history[-3:] + [action.move_target])) <= 2:
        score -= 220.0

    return score
