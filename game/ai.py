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
    def __init__(self, difficulty: int = 3, seed: int | None = None) -> None:
        self.difficulty = max(1, min(5, difficulty))
        self.rng = random.Random(seed)

    def choose_action(self, board: Board, units: list[Unit]) -> AIAction | None:
        ai_units = [unit for unit in units if unit.team == Team.AI and unit.is_alive()]
        enemies = [unit for unit in units if unit.team == Team.PLAYER and unit.is_alive()]
        if not ai_units or not enemies:
            return None

        actions: list[AIAction] = []
        for unit in ai_units:
            actions.extend(self._actions_from_position(unit, board, units))
            for move in unit.basic_move_targets(board, units):
                moved_units = self._simulate_move(units, unit.id, move)
                moved_unit = self._find_unit(moved_units, unit.id)
                if moved_unit is None:
                    continue
                actions.append(AIAction(unit_id=unit.id, move_target=move, score=self._score_move(unit, move, board, moved_units)))
                for follow_up in self._actions_from_position(moved_unit, board, moved_units):
                    follow_up.move_target = move
                    follow_up.score += 9.0
                    actions.append(follow_up)

        if not actions:
            return None

        actions.sort(key=lambda action: action.score, reverse=True)
        return self._pick_for_difficulty(actions)

    def _pick_for_difficulty(self, actions: list[AIAction]) -> AIAction:
        if self.difficulty == 5 or len(actions) == 1:
            return actions[0]
        if self.difficulty == 4:
            return actions[0] if self.rng.random() < 0.82 or len(actions) < 2 else actions[1]
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
        actions: list[AIAction] = []
        for target in unit.attack_targets(board, units):
            actions.append(AIAction(unit_id=unit.id, action_type="attack", action_target=target, score=self._score_attack(unit, target, board, enemies)))
        for target in unit.skill_targets(board, units):
            score = self._score_skill(unit, target, board, units, enemies)
            if score > 0:
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
        return score

    def _score_skill(self, unit: Unit, target: Position, board: Board, units: list[Unit], enemies: list[Unit]) -> float:
        if unit.unit_type == UnitType.KING:
            return 18.0 if unit.hp <= 4 and unit.shield_turns == 0 else -1.0
        if unit.unit_type == UnitType.SWORDMAN:
            victim = next((enemy for enemy in enemies if enemy.position == target), None)
            return 56.0 if victim else 18.0
        if unit.unit_type == UnitType.ARCHER:
            hits = [enemy for enemy in enemies if enemy.position in self._line_tiles(unit.position, target, board, 3)]
            return 26.0 + len(hits) * 18.0 if hits else -1.0
        if unit.unit_type == UnitType.MAGE:
            affected = {tile for tile in board.tiles_in_square(target, 1) if not board.is_blocked(tile)}
            hits = [enemy for enemy in enemies if enemy.position in affected]
            return 22.0 + len(hits) * 20.0 if hits else -1.0
        if unit.unit_type == UnitType.KNIGHT:
            victim = next((enemy for enemy in enemies if enemy.position == target), None)
            if victim:
                return 54.0 + (18.0 if victim.hp <= 2 else 0.0)
            return 16.0 - min(board.distance(target, enemy.position) for enemy in enemies)
        if unit.unit_type == UnitType.BISHOP:
            hits = [enemy for enemy in enemies if enemy.position in self._diagonal_tiles(unit.position, target, board, 4)]
            return 28.0 + len(hits) * 22.0 if hits else -1.0
        if unit.unit_type == UnitType.LANCER:
            victim = next((enemy for enemy in enemies if enemy.position == target), None)
            return 48.0 + (18.0 if victim and victim.hp <= 2 else 0.0) if victim else -1.0
        return -1.0

    def _score_move(self, unit: Unit, move: Position, board: Board, units: list[Unit]) -> float:
        enemies = [candidate for candidate in units if candidate.team != unit.team and candidate.is_alive()]
        allies = [candidate for candidate in units if candidate.team == unit.team and candidate.is_alive()]
        current_enemy_dist = min(board.distance(unit.position, enemy.position) for enemy in enemies)
        nearest_enemy = min(board.distance(move, enemy.position) for enemy in enemies)
        threatened = self._tile_threat_count(move, board, enemies, allies)

        score = 18.0 - nearest_enemy * 2.2
        if nearest_enemy < current_enemy_dist:
            score += 7.0
        if threatened == 0:
            score += 6.0
        else:
            score -= threatened * 6.5
        if unit.unit_type in {UnitType.KNIGHT, UnitType.BISHOP}:
            score += 3.0
        if unit.unit_type == UnitType.KING:
            score -= threatened * 8.0
        return score

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
