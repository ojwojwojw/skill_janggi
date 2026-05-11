from __future__ import annotations

from dataclasses import dataclass

from game.board import Board, Position
from game.constants import Team, UnitType
from game.unit import Unit


@dataclass(slots=True)
class AIAction:
    action_type: str
    unit_id: str
    target: Position
    score: float = 0.0


class SimpleAI:
    def choose_action(self, board: Board, units: list[Unit]) -> AIAction | None:
        ai_units = [unit for unit in units if unit.team == Team.AI and unit.is_alive()]
        enemies = [unit for unit in units if unit.team == Team.PLAYER and unit.is_alive()]
        if not ai_units or not enemies:
            return None

        actions: list[AIAction] = []
        all_units = ai_units + enemies
        enemy_king = next((unit for unit in enemies if unit.unit_type == UnitType.KING), None)
        ally_king = next((unit for unit in ai_units if unit.unit_type == UnitType.KING), None)

        for unit in ai_units:
            for target in unit.attack_targets(board, all_units):
                score = self._score_attack(unit, target, board, enemies, enemy_king)
                actions.append(AIAction('attack', unit.id, target, score))

            for target in unit.skill_targets(board, all_units):
                score = self._score_skill(unit, target, board, enemies, enemy_king)
                if score > 0:
                    actions.append(AIAction('skill', unit.id, target, score))

            for move in unit.basic_move_targets(board, all_units):
                score = self._score_move(unit, move, board, ai_units, enemies, ally_king)
                actions.append(AIAction('move', unit.id, move, score))

        if not actions:
            return None

        actions.sort(key=lambda action: action.score, reverse=True)
        return actions[0]

    def _score_attack(self, unit: Unit, target: Position, board: Board, enemies: list[Unit], enemy_king: Unit | None) -> float:
        victim = next(enemy for enemy in enemies if enemy.position == target)
        score = 40.0
        if victim.unit_type == UnitType.KING:
            score += 120.0
        if victim.hp <= 1:
            score += 45.0
        score += max(0, 6 - board.distance(unit.position, target))
        return score

    def _score_skill(self, unit: Unit, target: Position, board: Board, enemies: list[Unit], enemy_king: Unit | None) -> float:
        affected = self._skill_affected_tiles(unit, target, board)
        hits = [enemy for enemy in enemies if enemy.position in affected]
        if not hits and unit.unit_type != UnitType.KING:
            return -1.0

        score = 22.0
        if unit.unit_type == UnitType.KING:
            return 12.0 if unit.hp <= 3 and unit.shield_turns == 0 else -1.0
        score += len(hits) * 18.0
        score += sum(16.0 for enemy in hits if enemy.hp <= 1)
        score += sum(40.0 for enemy in hits if enemy.unit_type == UnitType.KING)
        return score

    def _score_move(self, unit: Unit, move: Position, board: Board, allies: list[Unit], enemies: list[Unit], ally_king: Unit | None) -> float:
        nearest_enemy = min(board.distance(move, enemy.position) for enemy in enemies)
        current_enemy_dist = min(board.distance(unit.position, enemy.position) for enemy in enemies)
        threatened = self._tile_threat_count(move, board, enemies, allies)
        score = 18.0 - nearest_enemy * 2.4
        if nearest_enemy < current_enemy_dist:
            score += 6.0
        if threatened == 0:
            score += 6.0
        else:
            score -= threatened * 6.5
        if unit.unit_type == UnitType.KING:
            score -= threatened * 8.0
        if ally_king and unit.unit_type != UnitType.KING:
            king_dist = board.distance(move, ally_king.position)
            if king_dist <= 2:
                score += 3.0
        return score

    def _tile_threat_count(self, tile: Position, board: Board, enemies: list[Unit], allies: list[Unit]) -> int:
        simulated_enemy_targets = 0
        all_units = enemies + allies
        for enemy in enemies:
            attack_tiles = enemy.attack_targets(board, all_units)
            skill_tiles = enemy.skill_targets(board, all_units)
            if tile in attack_tiles or tile in skill_tiles:
                simulated_enemy_targets += 1
        return simulated_enemy_targets

    def _skill_affected_tiles(self, unit: Unit, target: Position, board: Board) -> set[Position]:
        if unit.unit_type == UnitType.KING:
            return {unit.position}
        if unit.unit_type == UnitType.SWORDMAN:
            return {target}
        if unit.unit_type == UnitType.ARCHER:
            dx = 0 if target[0] == unit.position[0] else (1 if target[0] > unit.position[0] else -1)
            dy = 0 if target[1] == unit.position[1] else (1 if target[1] > unit.position[1] else -1)
            tiles: set[Position] = set()
            cursor = unit.position
            for _ in range(3):
                cursor = (cursor[0] + dx, cursor[1] + dy)
                if not board.in_bounds(cursor) or board.is_blocked(cursor):
                    break
                tiles.add(cursor)
            return tiles
        if unit.unit_type == UnitType.MAGE:
            return {tile for tile in board.tiles_in_square(target, 1) if not board.is_blocked(tile)}
        return set()
