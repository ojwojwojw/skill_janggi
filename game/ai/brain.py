from __future__ import annotations

import random

from game.ai.defense import filter_and_boost_panic_actions, king_defense_action_bonus, panic_defense_score
from game.ai.helpers import (
    adjacent_blocked_count,
    available_support_strikers,
    diagonal_tiles,
    enemy_threatens_ai_king,
    is_ai_king_in_crisis,
    is_between_king_and_threat,
    is_intruder_tile,
    king_lane_bonus,
    line_tiles,
    nearby_enemy_count,
    pressure_bonus,
    priority_enemy_against_ai_king,
    priority_enemy_king,
    refresh_king_threat_memory,
    support_priority_enemy_bonus,
    threatened_targets_bonus,
    tile_threat_count,
)
from game.ai.scoring import actions_from_position, find_unit, score_attack, score_move, score_skill, simulate_move
from game.ai.types import AIAction
from game.model.board import Board, Position
from game.model.constants import Team, UnitType
from game.model.unit import Unit


class SimpleAI:
    """난이도별 가중치를 적용해 AI 행동을 선택하는 메인 두뇌."""

    def __init__(self, difficulty: int = 3, seed: int | None = None) -> None:
        """난이도와 랜덤 시드를 초기화하고 행동 기억 상태를 준비한다."""
        self.difficulty = max(1, min(7, difficulty))
        self.rng = random.Random(seed)

        self.last_positions: dict[str, Position] = {}
        self.last_targets: dict[str, Position] = {}
        self.recent_positions: dict[str, list[Position]] = {}

        self.previous_ai_king_hp: int | None = None
        self.king_threat_streaks: dict[str, int] = {}

        self.last_actor_id: str | None = None
        self.same_actor_streak: int = 0

    def choose_action(self, board: Board, units: list[Unit]) -> AIAction | None:
        """현재 보드에서 가능한 행동 후보를 평가해 최종 행동 하나를 고른다."""
        ai_units = [unit for unit in units if unit.team == Team.AI and unit.is_alive()]
        enemies = [unit for unit in units if unit.team == Team.PLAYER and unit.is_alive()]
        if not ai_units or not enemies:
            return None

        ai_king = next((unit for unit in ai_units if unit.unit_type == UnitType.KING), None)
        threatening_enemy: Unit | None = None
        panic_mode = False

        if ai_king is not None:
            self._refresh_king_threat_memory(board, ai_king, enemies, ai_units)
            threatening_enemy = self._priority_enemy_against_ai_king(board, enemies, ai_units)
            panic_mode = self._is_ai_king_in_crisis(board, enemies, ai_units)

        actions: list[AIAction] = []

        for unit in ai_units:
            current_actions = self._actions_from_position(unit, board, units)

            for action in current_actions:
                action.score += 8.0
                if threatening_enemy is not None:
                    action.score += self._king_defense_action_bonus(
                        actor=unit,
                        action=action,
                        board=board,
                        units=units,
                        ai_king=ai_king,
                        threatening_enemy=threatening_enemy,
                        panic_mode=panic_mode,
                    )
                actions.append(action)

            for move in unit.basic_move_targets(board, units):
                moved_units = self._simulate_move(units, unit.id, move)
                moved_unit = self._find_unit(moved_units, unit.id)
                if moved_unit is None:
                    continue

                move_score = self._score_move(unit, move, board, moved_units)
                follow_up_actions = self._actions_from_position(moved_unit, board, moved_units)
                action = AIAction(unit_id=unit.id, move_target=move, score=move_score)

                if follow_up_actions:
                    action.score -= 320.0
                if threatening_enemy is not None:
                    action.score += self._king_defense_action_bonus(
                        actor=unit,
                        action=action,
                        board=board,
                        units=units,
                        ai_king=ai_king,
                        threatening_enemy=threatening_enemy,
                        panic_mode=panic_mode,
                    )
                actions.append(action)

                for follow_up in follow_up_actions:
                    follow_up.move_target = move
                    follow_up.score += 90.0
                    if threatening_enemy is not None:
                        follow_up.score += self._king_defense_action_bonus(
                            actor=unit,
                            action=follow_up,
                            board=board,
                            units=units,
                            ai_king=ai_king,
                            threatening_enemy=threatening_enemy,
                            panic_mode=panic_mode,
                        )
                    actions.append(follow_up)

        if not actions:
            return None

        self._apply_mage_position_rules(actions, ai_units, board, units, panic_mode, threatening_enemy)
        self._apply_intruder_guard_rules(actions, ai_units, board, units)
        self._apply_repeat_actor_penalty(actions, ai_units, threatening_enemy)

        if panic_mode and threatening_enemy is not None and ai_king is not None:
            actions = self._filter_and_boost_panic_actions(actions, board, units, ai_king, threatening_enemy)

        self._apply_support_unit_bias(actions, ai_units, ai_king, enemies, panic_mode)

        actions.sort(key=lambda action: action.score, reverse=True)
        chosen = self._pick_for_difficulty(actions)
        self._remember_chosen_action(chosen, ai_units, ai_king)
        return chosen

    def _apply_mage_position_rules(
        self,
        actions: list[AIAction],
        ai_units: list[Unit],
        board: Board,
        units: list[Unit],
        panic_mode: bool,
        threatening_enemy: Unit | None,
    ) -> None:
        """마법사가 무의미하게 배회하지 않도록 위치 보정을 적용한다."""
        for action in actions:
            actor = next((unit for unit in ai_units if unit.id == action.unit_id), None)
            if actor is None or actor.unit_type != UnitType.MAGE:
                continue

            if action.action_type is None:
                simulated_for_action = units
                moved_actor = actor
                if action.move_target is not None:
                    simulated_for_action = self._simulate_move(units, actor.id, action.move_target)
                    found_actor = self._find_unit(simulated_for_action, actor.id)
                    if found_actor is not None:
                        moved_actor = found_actor

                can_attack_after_move = bool(moved_actor.attack_targets(board, simulated_for_action))
                can_skill_after_move = bool(moved_actor.skill_targets(board, simulated_for_action))

                if can_attack_after_move:
                    action.score += 36.0
                elif can_skill_after_move:
                    action.score -= 18.0
                else:
                    action.score -= 90.0

                mage_history = self.recent_positions.get(actor.id, [])
                if action.move_target is not None:
                    if len(mage_history) >= 2 and action.move_target == mage_history[-2]:
                        action.score -= 90.0
                    if len(mage_history) >= 3 and action.move_target in mage_history[-3:]:
                        action.score -= 55.0

            if panic_mode and threatening_enemy is not None and action.action_target != threatening_enemy.position:
                simulated_for_action = units
                moved_actor = actor
                if action.move_target is not None:
                    simulated_for_action = self._simulate_move(units, actor.id, action.move_target)
                    found_actor = self._find_unit(simulated_for_action, actor.id)
                    if found_actor is not None:
                        moved_actor = found_actor

                can_pressure_threat = (
                    threatening_enemy.position in moved_actor.attack_targets(board, simulated_for_action)
                    or threatening_enemy.position in moved_actor.skill_targets(board, simulated_for_action)
                )
                if not can_pressure_threat:
                    action.score -= 260.0

    def _apply_intruder_guard_rules(
        self,
        actions: list[AIAction],
        ai_units: list[Unit],
        board: Board,
        units: list[Unit],
    ) -> None:
        """침입 적을 보고 있는 원거리 유닛이 자리를 쉽게 비우지 않게 보정한다."""
        for action in actions:
            actor = next((unit for unit in ai_units if unit.id == action.unit_id), None)
            if actor is None or actor.unit_type not in {UnitType.ARCHER, UnitType.MAGE}:
                continue

            current_attack_targets = actor.attack_targets(board, units)
            intruder_attack_targets = [target for target in current_attack_targets if self._is_intruder_tile(target)]
            if not intruder_attack_targets:
                continue

            if action.action_type == "attack" and action.action_target in intruder_attack_targets:
                action.score += 220.0
                if action.move_target is None:
                    action.score += 90.0
            elif action.move_target is not None:
                action.score -= 240.0
                if action.action_type is None:
                    action.score -= 120.0

    def _apply_repeat_actor_penalty(
        self,
        actions: list[AIAction],
        ai_units: list[Unit],
        threatening_enemy: Unit | None,
    ) -> None:
        """같은 유닛만 연속으로 움직이는 경향을 완화한다."""
        if threatening_enemy is None or len(ai_units) <= 1:
            return
        for action in actions:
            actor = next((unit for unit in ai_units if unit.id == action.unit_id), None)
            if actor is None:
                continue
            if actor.unit_type != UnitType.KING and action.unit_id == self.last_actor_id and action.action_type is None:
                action.score -= 10.0 + self.same_actor_streak * 6.0

    def _apply_support_unit_bias(
        self,
        actions: list[AIAction],
        ai_units: list[Unit],
        ai_king: Unit | None,
        enemies: list[Unit],
        panic_mode: bool,
    ) -> None:
        """고난도에서 지원형 스트라이커가 왕 대신 압박을 담당하도록 유도한다."""
        support_units = self._available_support_strikers(ai_units)
        if self.difficulty < 6 or ai_king is None or not support_units or panic_mode:
            return

        for action in actions:
            actor = next((unit for unit in ai_units if unit.id == action.unit_id), None)
            if actor is None:
                continue

            if actor.unit_type == UnitType.KING:
                action.score -= 42.0
                if action.move_target is not None:
                    action.score -= 22.0
                if action.action_type in {"attack", "skill"}:
                    action.score -= 18.0

                enemy_king = next((enemy for enemy in enemies if enemy.unit_type == UnitType.KING and enemy.is_alive()), None)
                if enemy_king is not None and action.action_target == enemy_king.position and enemy_king.hp <= 2:
                    action.score += 48.0
                if action.action_type == "skill":
                    action.score += 46.0
            elif actor.unit_type in {UnitType.KNIGHT, UnitType.LANCER, UnitType.MAGE} and action.action_type == "skill":
                action.score += 26.0
                if actor.unit_type == UnitType.MAGE:
                    action.score += 28.0
                elif actor.unit_type in {UnitType.KNIGHT, UnitType.LANCER}:
                    action.score += 8.0

    def _remember_chosen_action(self, chosen: AIAction, ai_units: list[Unit], ai_king: Unit | None) -> None:
        """선택한 행동을 다음 턴 평가에 쓰도록 기억 상태에 저장한다."""
        acting_unit = next((unit for unit in ai_units if unit.id == chosen.unit_id), None)
        if acting_unit is not None:
            self.last_positions[chosen.unit_id] = acting_unit.position
            history = self.recent_positions.setdefault(chosen.unit_id, [])
            history.append(acting_unit.position)
            if len(history) > 4:
                del history[0]

        if chosen.unit_id == self.last_actor_id:
            self.same_actor_streak += 1
        else:
            self.last_actor_id = chosen.unit_id
            self.same_actor_streak = 1

        if chosen.move_target is not None:
            self.last_targets[chosen.unit_id] = chosen.move_target

        if ai_king is not None:
            self.previous_ai_king_hp = ai_king.hp

    def _pick_for_difficulty(self, actions: list[AIAction]) -> AIAction:
        """난이도별 오차 범위를 반영해 최종 행동을 선택한다."""
        if self.difficulty >= 7 or len(actions) == 1:
            return actions[0]
        if self.difficulty == 6:
            pool = actions[: min(2, len(actions))]
            return self.rng.choices(pool, weights=[10, 1][: len(pool)], k=1)[0]
        if self.difficulty == 5:
            return actions[0]
        if self.difficulty == 4:
            pool = actions[: min(3, len(actions))]
            return self.rng.choices(pool, weights=[8, 2, 1][: len(pool)], k=1)[0]
        if self.difficulty == 3:
            pool = actions[: min(3, len(actions))]
            return self.rng.choices(pool, weights=[4, 2, 1][: len(pool)], k=1)[0]
        if self.difficulty == 2:
            pool = actions[: min(6, len(actions))]
            return self.rng.choice(pool)
        pool = actions[: min(10, len(actions))]
        return self.rng.choice(pool)

    def _actions_from_position(self, unit: Unit, board: Board, units: list[Unit]) -> list[AIAction]:
        """주어진 유닛과 보드 상태에서 가능한 행동 후보를 다시 계산한다."""
        return actions_from_position(self, unit, board, units)

    def _simulate_move(self, units: list[Unit], unit_id: str, move_target: Position) -> list[Unit]:
        """이동 결과를 가정한 유닛 목록 사본을 만든다."""
        return simulate_move(units, unit_id, move_target)

    def _find_unit(self, units: list[Unit], unit_id: str) -> Unit | None:
        """유닛 목록에서 id가 일치하는 객체를 찾는다."""
        return find_unit(units, unit_id)

    def _score_attack(self, unit: Unit, target: Position, board: Board, enemies: list[Unit]) -> float:
        """공격 행동의 점수를 계산한다."""
        return score_attack(self, unit, target, board, enemies)

    def _score_skill(self, unit: Unit, target: Position, board: Board, units: list[Unit], enemies: list[Unit]) -> float:
        """스킬 행동의 점수를 계산한다."""
        return score_skill(self, unit, target, board, units, enemies)

    def _score_move(self, unit: Unit, move: Position, board: Board, units: list[Unit]) -> float:
        """이동 행동의 점수를 계산한다."""
        return score_move(self, unit, move, board, units)

    def _is_ai_king_in_crisis(self, board: Board, enemies: list[Unit], allies: list[Unit]) -> bool:
        """AI 왕이 즉시 위협받는 위기 상황인지 판정한다."""
        return is_ai_king_in_crisis(self, board, enemies, allies)

    def _filter_and_boost_panic_actions(
        self,
        actions: list[AIAction],
        board: Board,
        units: list[Unit],
        ai_king: Unit,
        threatening_enemy: Unit,
    ) -> list[AIAction]:
        """위기 상황에서 의미 있는 행동만 남기고 점수를 보정한다."""
        return filter_and_boost_panic_actions(self, actions, board, units, ai_king, threatening_enemy)

    def _panic_defense_score(
        self,
        action: AIAction,
        actor: Unit,
        board: Board,
        units: list[Unit],
        ai_king: Unit,
        threatening_enemy: Unit,
    ) -> float:
        """위기 대응 관점에서 행동의 방어 가치를 계산한다."""
        return panic_defense_score(self, action, actor, board, units, ai_king, threatening_enemy)

    def _king_defense_action_bonus(
        self,
        actor: Unit,
        action: AIAction,
        board: Board,
        units: list[Unit],
        ai_king: Unit | None,
        threatening_enemy: Unit,
        panic_mode: bool,
    ) -> float:
        """왕 보호에 기여하는 행동에 추가 가중치를 준다."""
        return king_defense_action_bonus(self, actor, action, board, units, ai_king, threatening_enemy, panic_mode)

    def _is_between_king_and_threat(self, tile: Position, king_pos: Position, threat_pos: Position, board: Board) -> bool:
        """지정 칸이 왕과 위협 유닛 사이를 막는 위치인지 본다."""
        return is_between_king_and_threat(tile, king_pos, threat_pos, board)

    def _tile_threat_count(self, tile: Position, board: Board, enemies: list[Unit], allies: list[Unit]) -> int:
        """지정 칸을 공격할 수 있는 적의 수를 센다."""
        return tile_threat_count(tile, board, enemies, allies)

    def _line_tiles(self, origin: Position, target: Position, board: Board, max_range: int) -> set[Position]:
        """직선 기준으로 도달 가능한 타일 집합을 만든다."""
        return line_tiles(origin, target, board, max_range)

    def _diagonal_tiles(self, origin: Position, target: Position, board: Board, max_range: int) -> set[Position]:
        """대각선 기준으로 도달 가능한 타일 집합을 만든다."""
        return diagonal_tiles(origin, target, board, max_range)

    def _threatened_targets_bonus(self, unit: Unit, move: Position, board: Board, units: list[Unit]) -> float:
        """위협 중인 적을 더 압박하는 위치에 보너스를 준다."""
        return threatened_targets_bonus(self, unit, move, board, units)

    def _pressure_bonus(self, tile: Position, board: Board, enemies: list[Unit]) -> float:
        """전진 압박에 유리한 위치에 보너스를 준다."""
        return pressure_bonus(tile, board, enemies)

    def _king_lane_bonus(self, tile: Position, board: Board, enemies: list[Unit]) -> float:
        """적 왕 진로를 막거나 압박하는 위치에 보너스를 준다."""
        return king_lane_bonus(tile, board, enemies)

    def _nearby_enemy_count(self, tile: Position, enemies: list[Unit], board: Board) -> int:
        """지정 칸 주변의 적 유닛 수를 센다."""
        return nearby_enemy_count(tile, enemies, board)

    def _adjacent_blocked_count(self, tile: Position, board: Board) -> int:
        """지정 칸 주변에서 막혀 있는 방향 수를 센다."""
        return adjacent_blocked_count(tile, board)

    def _is_intruder_tile(self, tile: Position) -> bool:
        """지정 칸이 AI 진영 깊숙이 침투한 위치인지 판정한다."""
        return is_intruder_tile(tile)

    def _enemy_threatens_ai_king(self, enemy: Unit, board: Board, enemies: list[Unit], allies: list[Unit]) -> bool:
        """특정 적이 현재 AI 왕을 직접 위협하는지 본다."""
        return enemy_threatens_ai_king(enemy, board, enemies, allies)

    def _priority_enemy_against_ai_king(self, board: Board, enemies: list[Unit], allies: list[Unit]) -> Unit | None:
        """AI 왕을 가장 강하게 위협하는 적을 반환한다."""
        return priority_enemy_against_ai_king(self, board, enemies, allies)

    def _priority_enemy_king(self, enemies: list[Unit]) -> Unit | None:
        """현재 집중해야 할 적 왕 객체를 반환한다."""
        return priority_enemy_king(enemies)

    def _available_support_strikers(self, allies: list[Unit]) -> list[Unit]:
        """연계 공격에 투입 가능한 지원형 유닛 목록을 반환한다."""
        return available_support_strikers(allies)

    def _refresh_king_threat_memory(self, board: Board, ai_king: Unit, enemies: list[Unit], allies: list[Unit]) -> None:
        """왕 위협 추적 캐시를 최신 보드 상태로 갱신한다."""
        refresh_king_threat_memory(self, board, ai_king, enemies, allies)

    def _support_priority_enemy_bonus(
        self,
        unit: Unit,
        threatening_enemy: Unit,
        board: Board,
        units: list[Unit],
        move_target: Position | None = None,
    ) -> float:
        """우선 표적을 보조 공격하는 행동에 추가 점수를 준다."""
        return support_priority_enemy_bonus(self, unit, threatening_enemy, board, units, move_target)
