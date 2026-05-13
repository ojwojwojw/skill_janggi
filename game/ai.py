from __future__ import annotations

import random
from dataclasses import dataclass, replace

from game.board import Board, Position
from game.constants import Team, UnitType
from game.unit import Unit


@dataclass(slots=True)
class AIAction:
    unit_id: str
    move_target: Position | None = None
    action_type: str | None = None
    action_target: Position | None = None
    score: float = 0.0


class SimpleAI:
    """
    스킬장기 기본 AI.

    핵심 개선점:
    - AI 왕이 직접 공격 가능 상태면 KING PANIC MODE 진입
    - 왕 위협 기물을 최우선 목표로 지정
    - 왕 방어/차단/위협 제거 행동에 큰 보너스 부여
    - 왕 위기 중 의미 없는 이동, 반복 산책, 위협과 멀어지는 행동 강한 감점
    """

    def __init__(self, difficulty: int = 3, seed: int | None = None) -> None:
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
                action = AIAction(unit_id=unit.id, move_target=move, score=move_score)

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

                for follow_up in self._actions_from_position(moved_unit, board, moved_units):
                    follow_up.move_target = move
                    follow_up.score += 9.0

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

        # 술사 산책 억제 2차 필터:
        # 전체 액션 후보가 모인 뒤, 술사의 목적 없는 단순 이동을 한 번 더 누른다.
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

            # 왕 위기 상황에서 술사가 위협 기물을 압박하지 않는 이동은 거의 금지한다.
            if panic_mode and threatening_enemy is not None:
                if action.action_target != threatening_enemy.position:
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

        if threatening_enemy is not None and len(ai_units) > 1:
            for action in actions:
                actor = next((unit for unit in ai_units if unit.id == action.unit_id), None)
                if actor is None:
                    continue

                if actor.unit_type != UnitType.KING and action.unit_id == self.last_actor_id and action.action_type is None:
                    action.score -= 10.0 + self.same_actor_streak * 6.0

        if panic_mode and threatening_enemy is not None and ai_king is not None:
            actions = self._filter_and_boost_panic_actions(actions, board, units, ai_king, threatening_enemy)

        actions.sort(key=lambda action: action.score, reverse=True)
        chosen = self._pick_for_difficulty(actions)

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

        return chosen

    def _pick_for_difficulty(self, actions: list[AIAction]) -> AIAction:
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
        enemies = [candidate for candidate in units if candidate.team != unit.team and candidate.is_alive()]
        allies = [candidate for candidate in units if candidate.team == unit.team and candidate.is_alive()]
        actions: list[AIAction] = []

        for target in unit.attack_targets(board, units):
            score = self._score_attack(unit, target, board, enemies)
            victim = next((enemy for enemy in enemies if enemy.position == target), None)

            if victim is not None and self._enemy_threatens_ai_king(victim, board, enemies, allies):
                score += 80.0

            actions.append(AIAction(unit_id=unit.id, action_type="attack", action_target=target, score=score))

        for target in unit.skill_targets(board, units):
            score = self._score_skill(unit, target, board, units, enemies)
            if score <= 0:
                continue

            affected_enemies = [
                enemy
                for enemy in enemies
                if enemy.position == target or enemy.position in board.tiles_in_square(target, 1)
            ]

            if any(self._enemy_threatens_ai_king(enemy, board, enemies, allies) for enemy in affected_enemies):
                score += 70.0

            actions.append(AIAction(unit_id=unit.id, action_type="skill", action_target=target, score=score))

        return actions

    def _simulate_move(self, units: list[Unit], unit_id: str, move_target: Position) -> list[Unit]:
        simulated: list[Unit] = []
        for unit in units:
            simulated.append(replace(unit, position=move_target) if unit.id == unit_id else replace(unit))
        return simulated

    def _find_unit(self, units: list[Unit], unit_id: str) -> Unit | None:
        return next((unit for unit in units if unit.id == unit_id and unit.is_alive()), None)

    def _score_attack(self, unit: Unit, target: Position, board: Board, enemies: list[Unit]) -> float:
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
            if self._is_intruder_tile(target):
                score += 70.0
            if victim.unit_type in {UnitType.SWORDMAN, UnitType.KNIGHT, UnitType.LANCER}:
                score += 18.0

        if self.difficulty >= 4 and victim.hp <= unit.attack_power():
            score += 22.0
        if self.difficulty >= 4 and victim.unit_type == UnitType.KING:
            score += 40.0
        if self.difficulty >= 5:
            score += self._pressure_bonus(target, board, enemies)
        if self.difficulty >= 6 and unit.is_melee():
            score += 12.0
        if self.difficulty >= 6 and unit.unit_type in {UnitType.KING, UnitType.MAGE}:
            score += 14.0
        if self.difficulty >= 7:
            threatened_enemy = self._nearby_enemy_count(target, enemies, board)
            if threatened_enemy:
                score += threatened_enemy * 4.0
            if unit.unit_type == UnitType.KING:
                score += 18.0

        return score

    def _score_skill(self, unit: Unit, target: Position, board: Board, units: list[Unit], enemies: list[Unit]) -> float:
        if unit.unit_type == UnitType.KING:
            if unit.boss:
                affected = {tile for tile in board.tiles_in_square(target, 1) if not board.is_blocked(tile)}
                hits = [enemy for enemy in enemies if enemy.position in affected]
                if not hits:
                    return -1.0
                king_hit = any(enemy.unit_type == UnitType.KING for enemy in hits)
                return 92.0 + len(hits) * 30.0 + (52.0 if king_hit else 0.0)
            return 18.0 if unit.hp <= 4 and unit.shield_turns == 0 else -1.0

        if unit.unit_type == UnitType.SWORDMAN:
            victim = next((enemy for enemy in enemies if enemy.position == target), None)
            base = 56.0 if victim else 18.0
            if victim and victim.unit_type == UnitType.KING:
                base += 24.0
            if self.difficulty >= 4:
                base += self._pressure_bonus(target, board, enemies)
            if self.difficulty >= 6 and victim and victim.hp <= 2:
                base += 22.0
            return base

        if unit.unit_type == UnitType.ARCHER:
            hits = [enemy for enemy in enemies if enemy.position in self._line_tiles(unit.position, target, board, 3)]
            if not hits:
                return -1.0
            return 26.0 + len(hits) * (22.0 if self.difficulty >= 4 else 18.0)

        if unit.unit_type == UnitType.MAGE:
            affected = {tile for tile in board.tiles_in_square(target, 1) if not board.is_blocked(tile)}
            hits = [enemy for enemy in enemies if enemy.position in affected]
            if not hits:
                return -1.0
            king_hit = any(enemy.unit_type == UnitType.KING for enemy in hits)
            base = 16.0 + len(hits) * (22.0 if self.difficulty >= 4 else 18.0) + (14.0 if king_hit else 0.0)
            if len(hits) == 1:
                base -= 18.0
            elif len(hits) >= 3:
                base += 14.0
            return base

        if unit.unit_type == UnitType.KNIGHT:
            victim = next((enemy for enemy in enemies if enemy.position == target), None)
            if victim:
                base = 54.0 + (18.0 if victim.hp <= 2 else 0.0)
                if self.difficulty >= 4:
                    base += self._pressure_bonus(target, board, enemies)
                if self.difficulty >= 6:
                    base += 10.0
                return base
            return 16.0 - min(board.distance(target, enemy.position) for enemy in enemies)

        if unit.unit_type == UnitType.BISHOP:
            hits = [enemy for enemy in enemies if enemy.position in self._diagonal_tiles(unit.position, target, board, 4)]
            if not hits:
                return -1.0
            return 28.0 + len(hits) * (26.0 if self.difficulty >= 4 else 22.0)

        if unit.unit_type == UnitType.LANCER:
            victim = next((enemy for enemy in enemies if enemy.position == target), None)
            if not victim:
                return -1.0
            base = 48.0 + (18.0 if victim.hp <= 2 else 0.0)
            if self.difficulty >= 4 and victim.unit_type == UnitType.KING:
                base += 18.0
            if self.difficulty >= 6:
                base += 8.0
            return base

        return -1.0

    def _score_move(self, unit: Unit, move: Position, board: Board, units: list[Unit]) -> float:
        enemies = [candidate for candidate in units if candidate.team != unit.team and candidate.is_alive()]
        allies = [candidate for candidate in units if candidate.team == unit.team and candidate.is_alive()]

        current_enemy_dist = min(board.distance(unit.position, enemy.position) for enemy in enemies)
        nearest_enemy = min(board.distance(move, enemy.position) for enemy in enemies)
        threatened = self._tile_threat_count(move, board, enemies, allies)
        current_attack_count = len(unit.attack_targets(board, units))
        current_skill_count = len(unit.skill_targets(board, units))
        current_intruder_attack_count = sum(1 for target in unit.attack_targets(board, units) if self._is_intruder_tile(target))

        simulated = self._simulate_move(units, unit.id, move)
        moved_unit = self._find_unit(simulated, unit.id)

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
            moved_intruder_attack_count = sum(1 for target in moved_attack_targets if self._is_intruder_tile(target))

            if current_attack_count > 0 and attack_count <= current_attack_count:
                score -= 72.0
            if current_intruder_attack_count > 0 and moved_intruder_attack_count == 0:
                score -= 140.0
            if current_intruder_attack_count > 0 and attack_count <= current_attack_count:
                score -= 55.0
            if current_skill_count > 0 and attack_count == 0 and skill_count <= current_skill_count:
                score -= 24.0

        # 술사 산책 억제 패치:
        # 술사는 스킬/공격으로 실제 압박을 만들지 못하는 단순 이동을 낮게 평가한다.
        if unit.unit_type == UnitType.MAGE:
            mage_history = self.recent_positions.get(unit.id, [])
            current_attack_count = len(unit.attack_targets(board, units))
            current_skill_count = len(unit.skill_targets(board, units))

            if attack_count == 0 and skill_count == 0:
                score -= 45.0

            # 직전-직전 위치로 돌아가는 왕복 이동 강한 감점.
            if len(mage_history) >= 2 and move == mage_history[-2]:
                score -= 75.0

            # 최근 3~4턴 안에서 맴도는 이동도 감점.
            if len(mage_history) >= 3 and move in mage_history[-3:]:
                score -= 45.0
            if len(mage_history) >= 4 and move in mage_history[-4:]:
                score -= 35.0

            # 이동 후에도 공격/스킬 대상이 없다면 술사는 움직일 이유가 거의 없다.
            if moved_unit is not None:
                can_do_something_after_move = bool(
                    moved_unit.attack_targets(board, simulated)
                    or moved_unit.skill_targets(board, simulated)
                )
                if not can_do_something_after_move:
                    score -= 60.0
                else:
                    score += 18.0

                if attack_count > 0:
                    score += 96.0 + attack_count * 22.0
                elif current_attack_count == 0 and nearest_enemy <= 2:
                    score += 34.0

                if skill_count > 0:
                    score += 16.0 + skill_count * 5.0

                if nearest_enemy < current_enemy_dist:
                    score += 22.0

                if current_skill_count == 0 and nearest_enemy <= 3:
                    score += 18.0

                priority_enemy_for_mage = self._priority_enemy_against_ai_king(board, enemies, allies)
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

                    # 왕 위협 기물과 멀어지는 술사 이동은 산책으로 본다.
                    if moved_priority_dist >= current_priority_dist and not can_pressure_priority_enemy:
                        score -= 70.0

        if self.difficulty >= 4:
            score += self._threatened_targets_bonus(unit, move, board, units)
            score -= threatened * 2.0

        if self.difficulty >= 5:
            score += self._king_lane_bonus(move, board, enemies)

        if self.difficulty >= 6:
            score -= threatened * 3.5
            score += attack_count * 8.0 + skill_count * 5.0
            if attack_count == 0 and skill_count == 0:
                score -= 22.0
            if nearest_enemy >= current_enemy_dist and attack_count == 0:
                score -= 10.0
            if unit.unit_type in {UnitType.MAGE, UnitType.KING} and self._adjacent_blocked_count(move, board) >= 2:
                score -= 8.0
            if unit.unit_type in {UnitType.MAGE, UnitType.KING} and attack_count == 0 and skill_count == 0:
                score -= 12.0

        if self.difficulty >= 7 and unit.unit_type == UnitType.KING:
            score += 16.0 if threatened == 0 else -threatened * 10.0
            if attack_count == 0 and skill_count == 0:
                score -= 28.0
            if attack_count > 0 or skill_count > 0:
                score += 18.0

        previous_position = self.last_positions.get(unit.id)
        if previous_position == move:
            score -= 18.0 if unit.unit_type == UnitType.BISHOP else 12.0

        previous_target = self.last_targets.get(unit.id)
        if previous_target == move:
            score -= 10.0 if self.difficulty < 6 else 14.0

        if self.difficulty >= 6 and self._adjacent_blocked_count(unit.position, board) >= 2 and self._adjacent_blocked_count(move, board) >= 2:
            score -= 10.0

        history = self.recent_positions.get(unit.id, [])
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

        threatening_enemy = self._priority_enemy_against_ai_king(board, enemies, allies)
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

                score += self._support_priority_enemy_bonus(unit, threatening_enemy, board, units, move)

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
                if self.last_actor_id == unit.id and self.same_actor_streak >= 2 and attack_count == 0 and skill_count == 0:
                    score -= 14.0 + self.same_actor_streak * 4.0

        return score

    def _is_ai_king_in_crisis(self, board: Board, enemies: list[Unit], allies: list[Unit]) -> bool:
        ai_king = next(
            (ally for ally in allies if ally.team == Team.AI and ally.unit_type == UnitType.KING and ally.is_alive()),
            None,
        )
        if ai_king is None:
            return False

        direct_threats = [
            enemy for enemy in enemies
            if self._enemy_threatens_ai_king(enemy, board, enemies, allies)
        ]
        if direct_threats:
            return True

        repeated_threats = [
            enemy for enemy in enemies
            if self.king_threat_streaks.get(enemy.id, 0) >= 3 and board.distance(enemy.position, ai_king.position) <= 2
        ]
        if repeated_threats:
            return True

        if self.previous_ai_king_hp is not None and ai_king.hp < self.previous_ai_king_hp:
            return True

        return False

    def _filter_and_boost_panic_actions(
        self,
        actions: list[AIAction],
        board: Board,
        units: list[Unit],
        ai_king: Unit,
        threatening_enemy: Unit,
    ) -> list[AIAction]:
        """
        왕 위기 상황에서는 일반 포지셔닝보다 왕 생존을 강제한다.
        모든 액션을 버리지는 않고, 방어성 행동에 압도적 가중치를 준다.
        """
        boosted: list[AIAction] = []

        for action in actions:
            actor = self._find_unit(units, action.unit_id)
            if actor is None:
                continue

            defensive_score = self._panic_defense_score(action, actor, board, units, ai_king, threatening_enemy)
            action.score += defensive_score

            # 완전히 무의미한 산책성 행동은 크게 눌러준다.
            if defensive_score <= 0 and action.action_type is None:
                action.score -= 180.0

            boosted.append(action)

        return boosted

    def _panic_defense_score(
        self,
        action: AIAction,
        actor: Unit,
        board: Board,
        units: list[Unit],
        ai_king: Unit,
        threatening_enemy: Unit,
    ) -> float:
        score = 0.0
        streak = self.king_threat_streaks.get(threatening_enemy.id, 0)

        # 1. 위협 기물을 직접 때릴 때도 "처치 가능 여부"를 최우선으로 본다.
        #    이전 버전은 때리기만 해도 높은 점수를 줘서, 왕이 계속 맞는 상황을 못 끊었다.
        if action.action_target == threatening_enemy.position:
            expected_damage = actor.attack_power()
            can_kill_threat = threatening_enemy.hp <= expected_damage

            if action.action_type == "skill":
                # 스킬 피해량이 유닛마다 다를 수 있으므로 보수적으로 공격력 기준으로 본다.
                can_kill_threat = threatening_enemy.hp <= expected_damage

            if can_kill_threat:
                score += 520.0 + streak * 120.0
                if actor.unit_type != UnitType.KING:
                    score += 120.0
            else:
                # 못 죽이는 공격은 의미는 있지만, 왕이 다음 턴 또 맞으면 실패라서 과대평가 금지.
                score += 120.0 + streak * 25.0
                if self._enemy_threatens_ai_king(threatening_enemy, board, [u for u in units if u.team == Team.PLAYER and u.is_alive()], [u for u in units if u.team == Team.AI and u.is_alive()]):
                    score -= 170.0

        # 2. 이동 후 위협 기물을 공격/스킬 범위에 넣는 것은 좋지만,
        #    즉시 처치가 안 되면 왕 후퇴/차단보다 낮게 본다.
        simulated = units
        moved_actor = actor
        actor_pos_after = actor.position

        if action.move_target is not None:
            simulated = self._simulate_move(units, actor.id, action.move_target)
            found = self._find_unit(simulated, actor.id)
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

        # 3. 왕이 직접 위험한 경우, 왕 이동은 안전 타일로 갈 때만 보너스.
        if actor.unit_type == UnitType.KING and action.move_target is not None:
            old_threats = self._tile_threat_count(
                ai_king.position,
                board,
                [u for u in units if u.team == Team.PLAYER and u.is_alive()],
                [u for u in units if u.team == Team.AI and u.is_alive()],
            )
            new_threats = self._tile_threat_count(
                action.move_target,
                board,
                [u for u in simulated if u.team == Team.PLAYER and u.is_alive()],
                [u for u in simulated if u.team == Team.AI and u.is_alive()],
            )

            old_enemy_dist = board.distance(actor.position, threatening_enemy.position)
            new_enemy_dist = board.distance(action.move_target, threatening_enemy.position)
            can_attack_threat = threatening_enemy.position in attack_targets
            can_skill_threat = threatening_enemy.position in skill_targets

            # 왕은 안전해지는 이동을 최우선한다.
            # 위협 기물을 이번 턴에 제거하지 못한다면, 왕 후퇴가 가장 안정적인 답이다.
            if new_threats < old_threats:
                score += 360.0
            if new_threats == 0:
                score += 260.0
            if new_threats > 0:
                score -= 240.0

            # 핵심 패치: 왕이 위협 기물 쪽으로 무작정 전진하지 않게 한다.
            # 단, 이동 후 즉시 위협 기물을 공격/스킬로 처리할 수 있으면 예외를 둔다.
            if new_enemy_dist < old_enemy_dist:
                if can_attack_threat or can_skill_threat:
                    score += 70.0
                else:
                    score -= 150.0

            # 위협 기물과 거리를 벌리는 왕의 후퇴는 매우 고평가한다.
            if new_enemy_dist > old_enemy_dist:
                score += 220.0

            # 왕이 공격 가능하다는 이유만으로 전진하는 현상을 억제한다.
            if action.action_type is None and new_enemy_dist <= 1 and not (can_attack_threat or can_skill_threat):
                score -= 120.0

        # 4. 아군이 위협 기물에 가까워지는 것은 좋지만,
        #    처치/차단/왕 후퇴가 아니면 과대평가하지 않는다.
        if actor.unit_type != UnitType.KING:
            before_dist = board.distance(actor.position, threatening_enemy.position)
            after_dist = board.distance(actor_pos_after, threatening_enemy.position)
            if after_dist < before_dist:
                score += 55.0 + max(0, 4 - after_dist) * 12.0
            elif after_dist > before_dist:
                score -= 110.0

        # 5. 왕 주변으로 복귀하는 행동 보너스.
        if actor.unit_type != UnitType.KING:
            before_king_dist = board.distance(actor.position, ai_king.position)
            after_king_dist = board.distance(actor_pos_after, ai_king.position)
            if after_king_dist < before_king_dist:
                score += 70.0
            elif after_king_dist > before_king_dist:
                score -= 70.0

        # 6. 차단 보너스: 위협 기물과 왕 사이에 몸을 넣는 행동을 높게 본다.
        if actor.unit_type != UnitType.KING and action.move_target is not None:
            if self._is_between_king_and_threat(action.move_target, ai_king.position, threatening_enemy.position, board):
                score += 240.0

        # 7. 술사 산책은 panic mode에서 거의 금지한다.
        if actor.unit_type == UnitType.MAGE and action.move_target is not None:
            if action.action_type is None:
                score -= 260.0
            if not can_attack_after_move and not can_skill_after_move:
                score -= 220.0
            if (can_attack_after_move or can_skill_after_move) and not can_kill_after_move:
                score -= 90.0

        # 8. 단순 반복 산책 방지.
        history = self.recent_positions.get(actor.id, [])
        if action.move_target is not None and len(history) >= 2 and action.move_target == history[-2]:
            score -= 180.0
        if action.move_target is not None and len(history) >= 3 and len(set(history[-3:] + [action.move_target])) <= 2:
            score -= 220.0

        return score

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
        score = 0.0
        streak = self.king_threat_streaks.get(threatening_enemy.id, 0)

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

    def _is_between_king_and_threat(self, tile: Position, king_pos: Position, threat_pos: Position, board: Board) -> bool:
        """tile이 왕과 위협 기물 사이를 막는 위치인지 대략 판정한다.

        장기/체스류 보드게임에서 정확한 사거리 계산은 유닛별로 다르지만,
        여기서는 실전 방어용 휴리스틱으로 쓴다.
        같은 행/열/대각선 위협일 때 중간 칸이면 차단으로 본다.
        """
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

    def _tile_threat_count(self, tile: Position, board: Board, enemies: list[Unit], allies: list[Unit]) -> int:
        all_units = enemies + allies
        count = 0
        for enemy in enemies:
            if tile in enemy.attack_targets(board, all_units) or tile in enemy.skill_targets(board, all_units):
                count += 1
        return count

    def _line_tiles(self, origin: Position, target: Position, board: Board, max_range: int) -> set[Position]:
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

    def _diagonal_tiles(self, origin: Position, target: Position, board: Board, max_range: int) -> set[Position]:
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

    def _threatened_targets_bonus(self, unit: Unit, move: Position, board: Board, units: list[Unit]) -> float:
        simulated = self._simulate_move(units, unit.id, move)
        moved_unit = self._find_unit(simulated, unit.id)

        if moved_unit is None:
            return 0.0

        attack_targets = moved_unit.attack_targets(board, simulated)
        skill_targets = moved_unit.skill_targets(board, simulated)

        bonus = len(attack_targets) * 9.0
        bonus += len(skill_targets) * 4.0

        if any(enemy.unit_type == UnitType.KING and enemy.position in attack_targets for enemy in simulated if enemy.team != moved_unit.team):
            bonus += 20.0

        return bonus

    def _pressure_bonus(self, tile: Position, board: Board, enemies: list[Unit]) -> float:
        if not enemies:
            return 0.0

        nearest_enemy = min(board.distance(tile, enemy.position) for enemy in enemies)
        nearest_king = min(
            (board.distance(tile, enemy.position) for enemy in enemies if enemy.unit_type == UnitType.KING),
            default=nearest_enemy,
        )

        return max(0.0, 8.0 - nearest_enemy * 1.5) + max(0.0, 10.0 - nearest_king * 2.0)

    def _king_lane_bonus(self, tile: Position, board: Board, enemies: list[Unit]) -> float:
        king = next((enemy for enemy in enemies if enemy.unit_type == UnitType.KING), None)

        if king is None:
            return 0.0

        distance = board.distance(tile, king.position)
        return max(0.0, 12.0 - distance * 2.5)

    def _nearby_enemy_count(self, tile: Position, enemies: list[Unit], board: Board) -> int:
        return sum(1 for enemy in enemies if board.distance(tile, enemy.position) <= 2)

    def _adjacent_blocked_count(self, tile: Position, board: Board) -> int:
        return sum(1 for adjacent in board.orthogonal_positions(tile, 1) if board.is_blocked(adjacent))

    def _is_intruder_tile(self, tile: Position) -> bool:
        return tile[1] <= 3

    def _enemy_threatens_ai_king(self, enemy: Unit, board: Board, enemies: list[Unit], allies: list[Unit]) -> bool:
        ai_king = next(
            (ally for ally in allies if ally.team == Team.AI and ally.unit_type == UnitType.KING and ally.is_alive()),
            None,
        )

        if ai_king is None:
            return False

        simulated = enemies + allies
        return ai_king.position in enemy.attack_targets(board, simulated) or ai_king.position in enemy.skill_targets(board, simulated)

    def _priority_enemy_against_ai_king(self, board: Board, enemies: list[Unit], allies: list[Unit]) -> Unit | None:
        ai_king = next(
            (ally for ally in allies if ally.team == Team.AI and ally.unit_type == UnitType.KING and ally.is_alive()),
            None,
        )

        streak_threats = [enemy for enemy in enemies if self.king_threat_streaks.get(enemy.id, 0) >= 2]
        if streak_threats:
            return min(
                streak_threats,
                key=lambda enemy: (
                    -self.king_threat_streaks.get(enemy.id, 0),
                    enemy.hp,
                    board.distance(enemy.position, ai_king.position) if ai_king is not None else 0,
                ),
            )

        threatening = [enemy for enemy in enemies if self._enemy_threatens_ai_king(enemy, board, enemies, allies)]
        if threatening:
            return min(threatening, key=lambda enemy: enemy.hp)

        if ai_king is None:
            return None

        # 왕에게 가까운 적도 잠재 위협으로 본다.
        return min(enemies, key=lambda enemy: board.distance(enemy.position, ai_king.position), default=None)

    def _refresh_king_threat_memory(self, board: Board, ai_king: Unit, enemies: list[Unit], allies: list[Unit]) -> None:
        active_ids: set[str] = set()

        for enemy in enemies:
            threatens = self._enemy_threatens_ai_king(enemy, board, enemies, allies)
            adjacent = board.distance(enemy.position, ai_king.position) <= 1
            close = board.distance(enemy.position, ai_king.position) <= 2

            if threatens or adjacent:
                active_ids.add(enemy.id)
                self.king_threat_streaks[enemy.id] = self.king_threat_streaks.get(enemy.id, 0) + 1
            elif close:
                self.king_threat_streaks[enemy.id] = self.king_threat_streaks.get(enemy.id, 0) + 0
            elif enemy.id in self.king_threat_streaks:
                self.king_threat_streaks[enemy.id] = max(0, self.king_threat_streaks[enemy.id] - 1)

        if self.previous_ai_king_hp is not None and ai_king.hp < self.previous_ai_king_hp:
            for enemy in enemies:
                if board.distance(enemy.position, ai_king.position) <= 2:
                    self.king_threat_streaks[enemy.id] = self.king_threat_streaks.get(enemy.id, 0) + 2

        for enemy_id in list(self.king_threat_streaks):
            if enemy_id not in active_ids and self.king_threat_streaks[enemy_id] == 0:
                del self.king_threat_streaks[enemy_id]

    def _support_priority_enemy_bonus(
        self,
        unit: Unit,
        threatening_enemy: Unit,
        board: Board,
        units: list[Unit],
        move_target: Position | None = None,
    ) -> float:
        origin = move_target if move_target is not None else unit.position
        current_distance = board.distance(unit.position, threatening_enemy.position)
        moved_distance = board.distance(origin, threatening_enemy.position)

        simulated = units if move_target is None else self._simulate_move(units, unit.id, move_target)
        moved_unit = self._find_unit(simulated, unit.id)

        if moved_unit is None:
            return 0.0

        attack_targets = moved_unit.attack_targets(board, simulated)
        skill_targets = moved_unit.skill_targets(board, simulated)

        bonus = 0.0
        streak = self.king_threat_streaks.get(threatening_enemy.id, 0)

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
