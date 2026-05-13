from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pygame

from game.ai import SimpleAI
from game.board import Board, Position
from game.constants import (
    ATTACK_BUTTON,
    END_TURN_BUTTON,
    LOG_PANEL_RECT,
    MOVE_BUTTON,
    SKILL_BUTTON,
    ActionMode,
    GameState,
    Team,
    TEAM_NAMES,
    UNIT_DISPLAY_NAMES,
    UnitType,
)
from game.skill import SKILLS
from game.unit import Unit

ACTION_BUTTONS = {
    ActionMode.MOVE: pygame.Rect(*MOVE_BUTTON),
    ActionMode.ATTACK: pygame.Rect(*ATTACK_BUTTON),
    ActionMode.SKILL: pygame.Rect(*SKILL_BUTTON),
}

PLAYER_KING_POS = (3, 7)
AI_KING_POS = (4, 0)
PLAYER_HOME_POSITIONS = [(x, y) for y in (7, 6) for x in range(8) if (x, y) != PLAYER_KING_POS]
AI_HOME_POSITIONS = [(x, y) for y in (0, 1) for x in range(8) if (x, y) != AI_KING_POS]

BASE_HP = {
    UnitType.KING: 8,
    UnitType.SWORDMAN: 4,
    UnitType.ARCHER: 4,
    UnitType.MAGE: 4,
    UnitType.KNIGHT: 5,
    UnitType.BISHOP: 4,
    UnitType.LANCER: 5,
}


@dataclass(slots=True)
class ClickContext:
    board_tile: Position | None = None
    clicked_unit: Unit | None = None


class GameManager:
    def __init__(
        self,
        project_root: Path,
        blocked_tiles: set[Position] | None = None,
        player_roster: list[UnitType] | None = None,
        ai_roster: list[UnitType] | None = None,
        player_positions: list[Position] | None = None,
        ai_positions: list[Position] | None = None,
        ai_difficulty: int = 3,
        map_name: str = "classic",
    ) -> None:
        self.project_root = project_root
        self.map_name = map_name
        self.ai_difficulty = ai_difficulty
        self.board = Board(blocked_tiles=set(blocked_tiles or set()))
        self.units = self._create_units(
            player_roster or self._default_roster(),
            ai_roster or self._default_roster(),
            player_positions=player_positions,
            ai_positions=ai_positions,
        )
        self.ai = SimpleAI(ai_difficulty)
        self.state = GameState.PLAYER_TURN
        self.action_mode = ActionMode.MOVE
        self.selected_unit_id: str | None = None
        self.inspected_unit_id: str | None = None
        self.activation_unit_id: str | None = None
        self.activation_move_used = False
        self.activation_action_used = False
        self.current_turn = Team.PLAYER
        self.turn_count = 1
        self.winner: Team | None = None
        self.logs: list[str] = ["전투가 시작되었습니다. 청팀이 선공입니다."]
        self.saved_log_path: Path | None = None
        self.log_scroll = 0
        self.sound_events: list[str] = []
        self.ai_delay = 0.65
        self.ai_timer = 0.0
        self.last_feedback = "아군 유닛을 선택한 뒤 이동, 공격 또는 스킬을 고르세요."
        self.effects: list[dict[str, object]] = []
        self.end_turn_warning_armed = False
        self.end_turn_rect = pygame.Rect(*END_TURN_BUTTON)
        self.log_panel_rect = pygame.Rect(*LOG_PANEL_RECT)
        self.start_turn(Team.PLAYER, opening=True)

    def _default_roster(self) -> list[UnitType]:
        return [
            UnitType.ARCHER,
            UnitType.SWORDMAN,
            UnitType.SWORDMAN,
            UnitType.KNIGHT,
            UnitType.MAGE,
            UnitType.LANCER,
            UnitType.ARCHER,
        ]

    def _create_units(
        self,
        player_roster: list[UnitType],
        ai_roster: list[UnitType],
        player_positions: list[Position] | None = None,
        ai_positions: list[Position] | None = None,
    ) -> list[Unit]:
        player_king_pos = self._resolve_king_position(Team.PLAYER)
        ai_king_pos = self._resolve_king_position(Team.AI)
        units = [
            self._make_unit("p_king", Team.PLAYER, UnitType.KING, player_king_pos),
            self._make_unit("a_king", Team.AI, UnitType.KING, ai_king_pos),
        ]
        resolved_player_positions = (
            player_positions
            if player_positions is not None and len(player_positions) == len(player_roster)
            else self._resolve_deploy_positions(player_roster, Team.PLAYER, {player_king_pos})
        )
        resolved_ai_positions = (
            ai_positions
            if ai_positions is not None and len(ai_positions) == len(ai_roster)
            else self._resolve_deploy_positions(ai_roster, Team.AI, {ai_king_pos})
        )
        for idx, (unit_type, position) in enumerate(zip(player_roster, resolved_player_positions)):
            units.append(self._make_unit(f"p_{unit_type.name.lower()}_{idx}", Team.PLAYER, unit_type, position))
        for idx, (unit_type, position) in enumerate(zip(ai_roster, resolved_ai_positions)):
            units.append(self._make_unit(f"a_{unit_type.name.lower()}_{idx}", Team.AI, unit_type, position))
        return units

    def _make_unit(self, unit_id: str, team: Team, unit_type: UnitType, position: Position) -> Unit:
        hp = BASE_HP[unit_type]
        attack_bonus = 0
        armor = 0
        boss = False
        if team == Team.AI and unit_type == UnitType.KING:
            if self.ai_difficulty >= 7:
                hp += 10
                attack_bonus = 2
                armor = 0
                boss = True
            elif self.ai_difficulty >= 6:
                hp += 4
                attack_bonus = 1
        return Unit(
            unit_id,
            f"{TEAM_NAMES[team]} {UNIT_DISPLAY_NAMES[unit_type]}",
            unit_type,
            team,
            hp,
            hp,
            position,
            attack_bonus=attack_bonus,
            armor=armor,
            boss=boss,
        )

    def _resolve_king_position(self, team: Team) -> Position:
        preferred = PLAYER_KING_POS if team == Team.PLAYER else AI_KING_POS
        if self.board.is_walkable(preferred):
            return preferred
        fallback_pool = PLAYER_HOME_POSITIONS if team == Team.PLAYER else AI_HOME_POSITIONS
        for candidate in fallback_pool:
            if self.board.is_walkable(candidate):
                return candidate
        return preferred

    def _resolve_deploy_positions(self, roster: list[UnitType], team: Team, reserved: set[Position]) -> list[Position]:
        pool = PLAYER_HOME_POSITIONS if team == Team.PLAYER else AI_HOME_POSITIONS
        available = [pos for pos in pool if self.board.is_walkable(pos) and pos not in reserved]
        assigned: dict[int, Position] = {}

        for idx, unit_type in sorted(enumerate(roster), key=lambda item: self._deploy_priority(item[1]), reverse=True):
            if not available:
                break
            best_position = max(available, key=lambda pos: self._deploy_score(unit_type, pos, team, list(assigned.values())))
            assigned[idx] = best_position
            available.remove(best_position)

        if len(assigned) < len(roster):
            fallback_positions = [pos for pos in pool if pos not in reserved and pos not in assigned.values()]
            for idx in range(len(roster)):
                if idx in assigned:
                    continue
                assigned[idx] = fallback_positions.pop(0)

        return [assigned[idx] for idx in range(len(roster))]

    def _deploy_priority(self, unit_type: UnitType) -> int:
        priorities = {
            UnitType.KNIGHT: 5,
            UnitType.BISHOP: 4,
            UnitType.MAGE: 3,
            UnitType.LANCER: 3,
            UnitType.ARCHER: 2,
            UnitType.SWORDMAN: 1,
        }
        return priorities.get(unit_type, 0)

    def _deploy_score(self, unit_type: UnitType, position: Position, team: Team, assigned_positions: list[Position] | None = None) -> float:
        probe = Unit("probe", "probe", unit_type, team, 1, 1, position)
        move_count = len(probe.basic_move_targets(self.board, []))
        center_bias = 3.5 - abs(position[0] - 3.5)
        front_rank = -position[1] if team == Team.AI else position[1]
        stagger_target = 6 if team == Team.PLAYER else 1
        back_target = 7 if team == Team.PLAYER else 0
        stagger_bonus = 2.4 if ((position[0] % 2 == 0 and position[1] == stagger_target) or (position[0] % 2 == 1 and position[1] == back_target)) else 0.0
        ai_formation_bonus = 0.0
        assigned_positions = assigned_positions or []
        if team == Team.AI:
            formation_mode = self.ai_difficulty % 3
            if formation_mode == 0:
                ai_formation_bonus = 2.8 - abs(position[0] - 3.5)
            elif formation_mode == 1:
                ai_formation_bonus = 2.0 if position[0] in {1, 6} else 0.0
            else:
                ai_formation_bonus = 2.2 if position[1] == 1 else 0.0

        score = move_count * 12.0 + center_bias + stagger_bonus + ai_formation_bonus
        if assigned_positions:
            close_allies = sum(1 for other in assigned_positions if self.board.distance(position, other) <= 1)
            near_allies = sum(1 for other in assigned_positions if self.board.distance(position, other) == 2)
            if team == Team.AI:
                score -= close_allies * 11.0
                score -= near_allies * 3.5
                if self.ai_difficulty >= 6 and position[0] in {0, 7}:
                    score += 3.0
                if self.ai_difficulty >= 5 and position[1] == 0:
                    score -= 2.5
            else:
                score -= close_allies * 4.0
        if unit_type == UnitType.KNIGHT:
            score += move_count * 6.0 + center_bias * 1.6
        elif unit_type in {UnitType.SWORDMAN, UnitType.LANCER}:
            score += front_rank * 1.4
        elif unit_type in {UnitType.ARCHER, UnitType.BISHOP, UnitType.MAGE}:
            score -= front_rank * 1.1
        return score

    def start_turn(self, team: Team, opening: bool = False) -> None:
        self.current_turn = team
        if not opening:
            for unit in self.units:
                if unit.team == team and unit.is_alive():
                    unit.tick_cooldowns()
        self.ai_timer = 0.0
        self.selected_unit_id = None
        self.inspected_unit_id = None
        self.activation_unit_id = None
        self.activation_move_used = False
        self.activation_action_used = False
        self.action_mode = ActionMode.MOVE
        self.end_turn_warning_armed = False
        self.log(f"{TEAM_NAMES[team]} 차례입니다.")
        if team == Team.PLAYER:
            self.last_feedback = "아군 유닛을 고른 뒤 이동, 공격 또는 스킬을 선택하세요."
        else:
            self.last_feedback = "적팀이 수를 계산 중입니다."

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.state == GameState.GAME_OVER:
            return
        if event.type == pygame.KEYDOWN and self.state == GameState.PLAYER_TURN:
            if event.key == pygame.K_q:
                self.action_mode = ActionMode.SKILL
            elif event.key == pygame.K_a:
                self.action_mode = ActionMode.ATTACK
            elif event.key == pygame.K_e:
                self.try_end_player_turn()
                return
            elif event.key == pygame.K_m or event.key == pygame.K_ESCAPE:
                self.action_mode = ActionMode.MOVE
            self.last_feedback = self.mode_help_text()
        if event.type == pygame.MOUSEWHEEL:
            mouse_pos = pygame.mouse.get_pos()
            if self.log_panel_rect.collidepoint(mouse_pos):
                self.scroll_logs(event.y)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def _handle_click(self, mouse_pos: tuple[int, int]) -> None:
        if self.state != GameState.PLAYER_TURN:
            return
        if self.end_turn_rect.collidepoint(mouse_pos):
            self.try_end_player_turn("청 진영이 턴을 종료했습니다.")
            return

        for mode, rect in ACTION_BUTTONS.items():
            if rect.collidepoint(mouse_pos):
                self.action_mode = mode
                self.end_turn_warning_armed = False
                self.last_feedback = self.mode_help_text()
                return

        click = self._click_context(mouse_pos)
        if click.board_tile is None:
            return

        if click.clicked_unit is not None:
            self.inspected_unit_id = click.clicked_unit.id

        if (
            self.action_mode == ActionMode.SKILL
            and self.selected_unit is not None
            and click.board_tile in self.valid_skill_tiles
            and self.can_unit_act(self.selected_unit)
        ):
            self.activation_unit_id = self.selected_unit.id
            self.activation_action_used = True
            self._resolve_skill(self.selected_unit, click.board_tile)
            if self.state != GameState.GAME_OVER:
                self.end_player_turn()
            return

        if click.clicked_unit and click.clicked_unit.team == Team.PLAYER:
            if self.can_select_unit(click.clicked_unit):
                self.selected_unit_id = click.clicked_unit.id
                self.action_mode = ActionMode.ATTACK if self.activation_unit_id == click.clicked_unit.id and self.activation_move_used else ActionMode.MOVE
                self.last_feedback = self.mode_help_text()
                self.add_effect("select", click.clicked_unit.position, duration=0.25)
            else:
                self.last_feedback = "이미 행동한 유닛은 다시 선택할 수 없습니다."
            return

        if click.clicked_unit and click.clicked_unit.team != Team.PLAYER:
            if self.selected_unit is None or self.action_mode == ActionMode.MOVE:
                self.last_feedback = f"{click.clicked_unit.name} 정보를 확인 중입니다."
                return

        unit = self.selected_unit
        if unit is None:
            self.last_feedback = "먼저 아군 유닛을 선택하세요."
            return
        if self.board.is_blocked(click.board_tile):
            self.last_feedback = "그 칸은 장애물이라 이동할 수 없습니다."
            return

        if self.action_mode == ActionMode.MOVE:
            if not self.can_unit_move(unit):
                self.last_feedback = "이 유닛은 이미 이동했습니다."
                return
            if click.board_tile not in self.valid_move_tiles:
                self.last_feedback = "이동 가능한 칸을 선택하세요."
                return
            start = unit.position
            unit.move(click.board_tile)
            self.activation_unit_id = unit.id
            self.activation_move_used = True
            self.selected_unit_id = unit.id
            self.inspected_unit_id = unit.id
            self.add_effect("move", start, duration=0.30)
            self.add_effect("move", click.board_tile, duration=0.45)
            self.log(f"{unit.name} 이동: {start} -> {click.board_tile}")
            self.queue_sound("move")
            if self.valid_attack_tiles or self.valid_skill_tiles:
                self.action_mode = ActionMode.ATTACK
                self.last_feedback = "이동 완료. 이어서 공격하거나 스킬을 사용할 수 있습니다."
            else:
                self.last_feedback = "이동 완료. 이 유닛은 더 할 수 있는 행동이 없습니다."
            return

        if self.action_mode == ActionMode.ATTACK:
            if not self.can_unit_act(unit):
                self.last_feedback = "이 유닛은 이미 행동했습니다."
                return
            if click.clicked_unit is None or click.clicked_unit.position not in self.valid_attack_tiles:
                self.last_feedback = "공격 가능한 적 유닛을 선택하세요."
                return
            self.activation_unit_id = unit.id
            self.activation_action_used = True
            self._resolve_basic_attack(unit, click.clicked_unit)
            if self.state != GameState.GAME_OVER:
                self.end_player_turn()
            return

        if self.action_mode == ActionMode.SKILL:
            if not self.can_unit_act(unit):
                self.last_feedback = "이 유닛은 이미 행동했습니다."
                return
            if click.board_tile not in self.valid_skill_tiles:
                self.last_feedback = "스킬 대상 칸을 선택하세요."
                return
            self.activation_unit_id = unit.id
            self.activation_action_used = True
            self._resolve_skill(unit, click.board_tile)
            if self.state != GameState.GAME_OVER:
                self.end_player_turn()

    def _click_context(self, mouse_pos: tuple[int, int]) -> ClickContext:
        from game.renderer import board_tile_at_pixel

        tile = board_tile_at_pixel(mouse_pos)
        return ClickContext() if tile is None else ClickContext(tile, self.unit_at(tile))

    @property
    def selected_unit(self) -> Unit | None:
        if self.selected_unit_id is None:
            return None
        return next((unit for unit in self.units if unit.id == self.selected_unit_id and unit.is_alive()), None)

    @property
    def inspected_unit(self) -> Unit | None:
        if self.inspected_unit_id is None:
            return None
        return next((unit for unit in self.units if unit.id == self.inspected_unit_id and unit.is_alive()), None)

    @property
    def focused_unit(self) -> Unit | None:
        return self.inspected_unit or self.selected_unit

    @property
    def living_units(self) -> list[Unit]:
        return [unit for unit in self.units if unit.is_alive()]

    def can_select_unit(self, unit: Unit) -> bool:
        return unit.team == self.current_turn and unit.is_alive() and (self.activation_unit_id is None or self.activation_unit_id == unit.id)

    def can_unit_move(self, unit: Unit) -> bool:
        return unit.team == self.current_turn and unit.is_alive() and not self.activation_action_used and not self.activation_move_used and (self.activation_unit_id is None or self.activation_unit_id == unit.id)

    def can_unit_act(self, unit: Unit) -> bool:
        return unit.team == self.current_turn and unit.is_alive() and not self.activation_action_used and (self.activation_unit_id is None or self.activation_unit_id == unit.id)

    @property
    def valid_move_tiles(self) -> list[Position]:
        unit = self.selected_unit
        return unit.basic_move_targets(self.board, self.living_units) if unit and self.can_unit_move(unit) else []

    @property
    def attack_preview_tiles(self) -> list[Position]:
        unit = self.selected_unit
        return unit.attack_preview_tiles(self.board) if unit and self.can_unit_act(unit) else []

    @property
    def valid_attack_tiles(self) -> list[Position]:
        unit = self.selected_unit
        return unit.attack_targets(self.board, self.living_units) if unit and self.can_unit_act(unit) else []

    @property
    def valid_skill_tiles(self) -> list[Position]:
        unit = self.selected_unit
        return unit.skill_targets(self.board, self.living_units) if unit and self.can_unit_act(unit) else []

    def update(self, dt: float) -> None:
        self._update_effects(dt)
        if self.state == GameState.AI_TURN:
            self.ai_timer += dt
            if self.ai_timer >= self.ai_delay:
                self.ai_timer = 0.0
                self._execute_ai_turn()

    def _execute_ai_turn(self) -> None:
        action = self.ai.choose_action(self.board, self.living_units)
        if action is None:
            self.end_ai_turn("적팀이 턴을 종료했습니다.")
            return
        unit = self.get_unit(action.unit_id)
        if unit is None:
            self.end_ai_turn("적팀이 행동할 유닛을 찾지 못했습니다.")
            return
        if action.move_target is not None:
            start = unit.position
            unit.move(action.move_target)
            self.add_effect("move", start, duration=0.30)
            self.add_effect("move", action.move_target, duration=0.45)
            self.log(f"{unit.name} 이동: {start} -> {action.move_target}")
            self.queue_sound("move")
        if action.action_type == "attack" and action.action_target is not None:
            target = self.unit_at(action.action_target)
            if target is not None:
                self._resolve_basic_attack(unit, target)
        elif action.action_type == "skill" and action.action_target is not None:
            self._resolve_skill(unit, action.action_target)
        elif action.move_target is not None:
            self.last_feedback = f"{unit.name}이 이동만 하고 턴을 마쳤습니다."
        if self.state != GameState.GAME_OVER:
            self.end_ai_turn()

    def _resolve_basic_attack(self, attacker: Unit, target: Unit) -> None:
        target_tile = target.position
        self.add_effect("slash", target.position, duration=0.30)
        damage = attacker.attack(target)
        self.queue_sound("attack")
        self._show_damage_feedback(target, damage)
        if damage > 0:
            self.log(f"{attacker.name} 공격: {target.name}에게 피해 {damage}")
            self.last_feedback = f"{target.name} 체력: {target.hp}/{target.max_hp}"
        else:
            self.log(f"{attacker.name} 공격: {target.name}의 보호막에 막혔습니다.")
            self.last_feedback = "보호막이 피해를 막아냈습니다."
        self._cleanup_dead_units()
        if attacker.is_melee() and not target.is_alive():
            attacker.move(target_tile)
            self.inspected_unit_id = attacker.id
            self.add_effect("move", target_tile, duration=0.32)
            self.log(f"{attacker.name} 전진: 처치 후 빈 칸을 점령했습니다.")
        self._check_victory()
        if self.state == GameState.GAME_OVER:
            self.queue_sound("win")

    def _resolve_skill(self, unit: Unit, target_tile: Position) -> None:
        unit.use_skill()
        skill = SKILLS[unit.unit_type]
        self.add_effect("skill_cast", unit.position, duration=0.35)
        self.queue_sound("skill")
        if unit.unit_type == UnitType.KING:
            if unit.boss:
                teleported, hits = self._resolve_terror_slam(unit, target_tile)
                self.log(f"{unit.name} 스킬 사용: 공포 강림, 피해 대상 {hits}")
                self.last_feedback = "괴물 왕이 순간이동 후 공포 강림을 쏟아냈습니다." if teleported else f"괴물 왕의 공포 강림이 {hits}명을 휩쓸었습니다."
                self._cleanup_dead_units()
                self._check_victory()
                if self.state == GameState.GAME_OVER:
                    self.queue_sound("win")
                return
            target = self.unit_at(target_tile)
            if target is not None and target.team == unit.team:
                target.shield_turns = max(target.shield_turns, 1)
                self.add_effect("shield", target.position, duration=0.70)
                self.add_effect("text", target.position, duration=0.75, text="보호", color=(255, 226, 110))
                self.log(f"{unit.name} 스킬 사용: {skill.name}")
                self.last_feedback = f"{target.name}에게 1턴 보호막을 부여했습니다."
        elif unit.unit_type == UnitType.SWORDMAN:
            self._resolve_charge(unit, target_tile)
        elif unit.unit_type == UnitType.ARCHER:
            hits = self._resolve_piercing_shot(unit, target_tile)
            self.log(f"{unit.name} 스킬 사용: {skill.name}, 피해 대상 {hits}")
            self.last_feedback = f"관통 사격 적중 수: {hits}"
        elif unit.unit_type == UnitType.MAGE:
            hits = self._resolve_flame_burst(unit, target_tile)
            self.log(f"{unit.name} 스킬 사용: {skill.name}, 피해 대상 {hits}")
            self.last_feedback = f"화염 폭발 적중 수: {hits}"
        elif unit.unit_type == UnitType.KNIGHT:
            self._resolve_leap_strike(unit, target_tile)
        elif unit.unit_type == UnitType.BISHOP:
            hits = self._resolve_bishop_beam(unit, target_tile)
            self.log(f"{unit.name} 스킬 사용: {skill.name}, 피해 대상 {hits}")
            self.last_feedback = f"대각 광선 적중 수: {hits}"
        elif unit.unit_type == UnitType.LANCER:
            success = self._resolve_lancer_thrust(unit, target_tile)
            self.log(f"{unit.name} 스킬 사용: {skill.name}")
            if not success and not self.last_feedback:
                self.last_feedback = "관통 돌진이 적에게 닿지 않았습니다."
        self._cleanup_dead_units()
        self._check_victory()
        if self.state == GameState.GAME_OVER:
            self.queue_sound("win")

    def _resolve_charge(self, unit: Unit, target_tile: Position) -> None:
        start = unit.position
        dx = 0 if target_tile[0] == unit.position[0] else (1 if target_tile[0] > unit.position[0] else -1)
        dy = 0 if target_tile[1] == unit.position[1] else (1 if target_tile[1] > unit.position[1] else -1)
        target_unit = self.unit_at(target_tile)
        if target_unit and target_unit.team != unit.team:
            landing = (target_tile[0] - dx, target_tile[1] - dy)
            if landing != unit.position and self.unit_at(landing) is None and self.board.is_walkable(landing):
                unit.move(landing)
                self.inspected_unit_id = unit.id
                self.add_effect("dash", landing, duration=0.45, origin=start)
            damage = unit.attack(target_unit)
            self.add_effect("slash", target_unit.position, duration=0.35)
            self._show_damage_feedback(target_unit, damage)
            target_origin = target_unit.position
            if damage > 0 and target_unit.is_alive() and self._push_unit(target_unit, dx, dy):
                self._advance_into_tile(unit, target_origin, start)
                self.last_feedback = f"{target_unit.name}을 밀어내고 그 자리를 차지했습니다."
            elif damage > 0:
                self.last_feedback = f"돌진으로 {target_unit.name}에게 피해를 주었습니다."
            else:
                self.last_feedback = "돌진이 보호막에 막혔습니다."
        else:
            unit.move(target_tile)
            self.inspected_unit_id = unit.id
            self.add_effect("dash", target_tile, duration=0.45, origin=start)
            self.last_feedback = f"{unit.name}이 돌진으로 전진했습니다."

    def _resolve_piercing_shot(self, unit: Unit, target_tile: Position) -> int:
        dx = 0 if target_tile[0] == unit.position[0] else (1 if target_tile[0] > unit.position[0] else -1)
        dy = 0 if target_tile[1] == unit.position[1] else (1 if target_tile[1] > unit.position[1] else -1)
        hits = 0
        cursor = unit.position
        path: list[Position] = []
        for _ in range(3):
            cursor = (cursor[0] + dx, cursor[1] + dy)
            if not self.board.in_bounds(cursor) or self.board.is_blocked(cursor):
                break
            path.append(cursor)
            target = self.unit_at(cursor)
            if target and target.team != unit.team:
                self._show_damage_feedback(target, target.take_damage(1))
                hits += 1
        self.add_effect("beam", target_tile, duration=0.32, origin=unit.position, path=path)
        return hits

    def _resolve_terror_slam(self, unit: Unit, target_tile: Position) -> tuple[bool, int]:
        start = unit.position
        teleported = False
        if self.board.is_walkable(target_tile):
            occupant = self.unit_at(target_tile)
            if occupant is None:
                unit.move(target_tile)
                self.inspected_unit_id = unit.id
                self.add_effect("teleport", target_tile, duration=0.55, origin=start)
                teleported = True
        affected_tiles = [tile for tile in self.board.tiles_in_square(target_tile, 1) if not self.board.is_blocked(tile)]
        self.add_effect("boss_burst", target_tile, duration=0.78, tiles=affected_tiles, origin=start if teleported else unit.position)
        self.add_effect("text", target_tile, duration=0.8, text="공포", color=(255, 92, 92))
        hits = 0
        for tile in affected_tiles:
            target = self.unit_at(tile)
            if target is None or target.team == unit.team:
                continue
            damage = target.take_damage(2)
            self._show_damage_feedback(target, damage)
            hits += 1
            dx = 0 if target.position[0] == unit.position[0] else (1 if target.position[0] > unit.position[0] else -1)
            dy = 0 if target.position[1] == unit.position[1] else (1 if target.position[1] > unit.position[1] else -1)
            if dx != 0 or dy != 0:
                self._push_unit(target, dx, dy)
        return teleported, hits

    def _resolve_flame_burst(self, unit: Unit, target_tile: Position) -> int:
        hits = 0
        affected_tiles = [tile for tile in self.board.tiles_in_square(target_tile, 1) if not self.board.is_blocked(tile)]
        self.add_effect("burst", target_tile, duration=0.55, tiles=affected_tiles)
        for tile in affected_tiles:
            target = self.unit_at(tile)
            if target and target.team != unit.team:
                self._show_damage_feedback(target, target.take_damage(1))
                hits += 1
        return hits

    def _resolve_leap_strike(self, unit: Unit, target_tile: Position) -> None:
        start = unit.position
        target = self.unit_at(target_tile)
        self.add_effect("dash", target_tile, duration=0.40, origin=start)
        if target and target.team != unit.team:
            damage = unit.attack(target)
            self._show_damage_feedback(target, damage)
            if not target.is_alive():
                unit.move(target_tile)
                self.inspected_unit_id = unit.id
                self.last_feedback = f"{unit.name}이 적을 쓰러뜨리고 자리를 차지했습니다."
            else:
                push_dx = 0 if target.position[0] == unit.position[0] else (1 if target.position[0] > unit.position[0] else -1)
                push_dy = 0 if target.position[1] == unit.position[1] else (1 if target.position[1] > unit.position[1] else -1)
                if self._push_unit(target, push_dx, push_dy, distance=2):
                    self.last_feedback = f"도약 강타로 {target.name}을 강하게 밀어냈습니다."
                else:
                    self.last_feedback = f"도약 강타는 적중했지만 {target.name}은 더 밀리지 않았습니다."
        else:
            unit.move(target_tile)
            self.inspected_unit_id = unit.id
            unit.shield_turns = max(unit.shield_turns, 1)
            self.add_effect("shield", target_tile, duration=0.55)
            self.last_feedback = f"{unit.name}이 도약 후 1턴 보호막을 얻었습니다."

    def _resolve_bishop_beam(self, unit: Unit, target_tile: Position) -> int:
        dx = 1 if target_tile[0] > unit.position[0] else -1
        dy = 1 if target_tile[1] > unit.position[1] else -1
        hits = 0
        path: list[Position] = []
        cursor = unit.position
        for _ in range(4):
            cursor = (cursor[0] + dx, cursor[1] + dy)
            if not self.board.in_bounds(cursor) or self.board.is_blocked(cursor):
                break
            path.append(cursor)
            target = self.unit_at(cursor)
            if target and target.team != unit.team:
                self._show_damage_feedback(target, target.take_damage(1))
                hits += 1
        self.add_effect("beam", target_tile, duration=0.36, origin=unit.position, path=path)
        return hits

    def _resolve_lancer_thrust(self, unit: Unit, target_tile: Position) -> bool:
        dx = 0 if target_tile[0] == unit.position[0] else (1 if target_tile[0] > unit.position[0] else -1)
        dy = 0 if target_tile[1] == unit.position[1] else (1 if target_tile[1] > unit.position[1] else -1)
        cursor = unit.position
        path: list[Position] = []
        furthest_open = unit.position
        struck_target: Unit | None = None
        for _ in range(3):
            cursor = (cursor[0] + dx, cursor[1] + dy)
            if not self.board.in_bounds(cursor) or self.board.is_blocked(cursor):
                break
            path.append(cursor)
            target = self.unit_at(cursor)
            if target is None:
                furthest_open = cursor
                continue
            if target.team == unit.team:
                break
            struck_target = target
            break

        if struck_target is None:
            start = unit.position
            if furthest_open != unit.position:
                unit.move(furthest_open)
                self.inspected_unit_id = unit.id
                self.add_effect("dash", furthest_open, duration=0.40, origin=start)
                self.last_feedback = f"{unit.name}이 창을 겨누며 전진했습니다."
            else:
                self.last_feedback = "관통 돌진이 막혀 제자리에서 멈췄습니다."
            self.add_effect("beam", furthest_open, duration=0.28, origin=start, path=path)
            return False

        landing = (struck_target.position[0] - dx, struck_target.position[1] - dy)
        start = unit.position
        if landing != unit.position and self.board.is_walkable(landing) and self.unit_at(landing) is None:
            unit.move(landing)
            self.inspected_unit_id = unit.id
            self.add_effect("dash", landing, duration=0.40, origin=start)
        damage = unit.attack(struck_target)
        self._show_damage_feedback(struck_target, damage)
        target_origin = struck_target.position
        pushed = struck_target.is_alive() and self._push_unit(struck_target, dx, dy, distance=7)
        if pushed:
            self._advance_into_tile(unit, target_origin, start)
        self.add_effect("beam", struck_target.position, duration=0.28, origin=start, path=path)
        if damage > 0 and pushed:
            self.last_feedback = f"{struck_target.name}을 밀어내고 그 자리를 차지했습니다."
        elif damage > 0:
            self.last_feedback = f"{struck_target.name}을 찌르며 돌진했지만 더 밀어내지는 못했습니다."
        elif pushed:
            self.last_feedback = f"{struck_target.name}의 피해는 막혔지만 밀어내고 그 자리를 차지했습니다."
        else:
            self.last_feedback = "관통 돌진이 적에게 닿았지만 큰 흔들림은 없었습니다."
        return damage > 0 or pushed

    def _show_damage_feedback(self, target: Unit, damage: int) -> None:
        self.inspected_unit_id = target.id
        if damage > 0:
            self.add_effect("attack", target.position, duration=0.45)
            self.add_effect("text", target.position, duration=0.85, text=f"-{damage}", color=(255, 120, 120))
        else:
            self.add_effect("shield", target.position, duration=0.45)
            self.add_effect("text", target.position, duration=0.80, text="막힘", color=(255, 214, 120))

    def _advance_into_tile(self, unit: Unit, destination: Position, origin: Position) -> None:
        if unit.position == destination:
            return
        if not self.board.is_walkable(destination) or self.unit_at(destination) is not None:
            return
        unit.move(destination)
        self.inspected_unit_id = unit.id
        self.add_effect("dash", destination, duration=0.30, origin=origin)

    def _push_unit(self, target: Unit, dx: int, dy: int, distance: int = 1) -> bool:
        last_open_tile: Position | None = None
        for step in range(1, distance + 1):
            push_tile = (target.position[0] + dx * step, target.position[1] + dy * step)
            if not self.board.is_walkable(push_tile) or self.unit_at(push_tile) is not None:
                break
            last_open_tile = push_tile
        if last_open_tile is None:
            return False
        target.move(last_open_tile)
        self.add_effect("move", last_open_tile, duration=0.30)
        return True

    def try_end_player_turn(self, reason: str | None = None) -> bool:
        if not self.activation_move_used:
            self.end_turn_warning_armed = False
            self.last_feedback = "턴 종료 전에는 반드시 아군 유닛을 한 번 이동해야 합니다."
            return False
        self.end_turn_warning_armed = False
        self.end_player_turn(reason)
        return True

    def end_player_turn(self, reason: str | None = None) -> None:
        if reason:
            self.log(reason)
        self.queue_sound("end_turn")
        self.state = GameState.AI_TURN
        self.start_turn(Team.AI)

    def end_ai_turn(self, reason: str | None = None) -> None:
        if reason:
            self.log(reason)
        self.queue_sound("end_turn")
        self.turn_count += 1
        self.state = GameState.PLAYER_TURN
        self.start_turn(Team.PLAYER)

    def get_unit(self, unit_id: str) -> Unit | None:
        return next((unit for unit in self.units if unit.id == unit_id and unit.is_alive()), None)

    def unit_at(self, position: Position) -> Unit | None:
        return next((unit for unit in self.units if unit.is_alive() and unit.position == position), None)

    def log(self, message: str) -> None:
        if self.log_scroll > 0:
            self.log_scroll += 1
        self.logs.append(message)
        self.log_scroll = min(self.log_scroll, self.max_log_scroll())

    def export_battle_log(self) -> Path:
        if self.saved_log_path is not None:
            return self.saved_log_path
        log_dir = self.project_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        winner_name = TEAM_NAMES[self.winner] if self.winner is not None else "미정"
        log_path = log_dir / f"battle_log_{now.strftime('%Y%m%d_%H%M%S')}.txt"
        header = [
            "스킬 장기 전투 로그",
            f"저장 시각: {now.strftime('%Y-%m-%d %H:%M:%S')}",
            f"맵: {self.map_name}",
            f"난이도: {self.ai_difficulty}",
            f"승리 팀: {winner_name}",
            "",
            "[전투 기록]",
        ]
        log_path.write_text("\n".join(header + self.logs) + "\n", encoding="utf-8")
        self.saved_log_path = log_path
        return log_path

    def queue_sound(self, sound_name: str) -> None:
        self.sound_events.append(sound_name)

    def drain_sound_events(self) -> list[str]:
        queued = list(self.sound_events)
        self.sound_events.clear()
        return queued

    def scroll_logs(self, delta: int) -> None:
        self.log_scroll = max(0, min(self.max_log_scroll(), self.log_scroll + delta))

    def max_log_scroll(self, visible_lines: int = 4) -> int:
        estimated_wrapped_lines = len(self.logs) * 3
        return max(0, estimated_wrapped_lines - visible_lines)

    def visible_logs(self, visible_lines: int = 4) -> list[str]:
        end = len(self.logs) - self.log_scroll
        start = max(0, end - visible_lines)
        return self.logs[start:end]

    def mode_help_text(self) -> str:
        unit = self.selected_unit
        if unit is None:
            return "먼저 청 진영 유닛을 선택하세요."
        if self.action_mode == ActionMode.MOVE:
            return "이동 가능한 칸을 눌러 자리를 잡으세요."
        if self.action_mode == ActionMode.ATTACK:
            return "공격 가능한 적 유닛을 선택하세요."
        if self.action_mode == ActionMode.SKILL:
            return "금색 강조 칸이 스킬 대상입니다."
        return "행동 방식을 선택하세요."

    def step_guide_text(self) -> str:
        unit = self.selected_unit
        if unit is None:
            return "1. 유닛 선택  2. 이동  3. 공격 또는 스킬"
        if self.action_mode == ActionMode.MOVE:
            return "초록 칸이 이동 가능 위치입니다."
        if self.action_mode == ActionMode.ATTACK:
            return "붉은 윤곽 칸은 현재 공격 사거리입니다."
        if self.action_mode == ActionMode.SKILL:
            return "금색 강조 칸이 스킬 대상 위치입니다."
        return "행동 바에서 원하는 행동을 선택하세요."

    def turn_status_text(self) -> str:
        if self.state == GameState.PLAYER_TURN:
            return "청 진영 행동 중"
        if self.state == GameState.AI_TURN:
            return f"적팀 계산 중... {max(0.0, self.ai_delay - self.ai_timer):.1f}초"
        return f"승리: {TEAM_NAMES[self.winner]}" if self.winner is not None else "대기 중..."

    def action_summary_text(self) -> str:
        unit = self.selected_unit
        if unit is None:
            return "선택된 아군 없음"
        move_state = "사용" if self.activation_move_used and self.activation_unit_id == unit.id else "가능"
        action_state = "사용" if self.activation_action_used and self.activation_unit_id == unit.id else "가능"
        return f"이동 {move_state} | 행동 {action_state}"

    def add_effect(self, effect_type: str, position: Position, duration: float = 0.45, **extra: object) -> None:
        effect = {"type": effect_type, "position": position, "timer": duration, "max_timer": duration}
        effect.update(extra)
        self.effects.append(effect)

    def _update_effects(self, dt: float) -> None:
        next_effects: list[dict[str, object]] = []
        for effect in self.effects:
            timer = float(effect["timer"]) - dt
            if timer > 0:
                effect["timer"] = timer
                next_effects.append(effect)
        self.effects = next_effects

    def _cleanup_dead_units(self) -> None:
        for unit in self.units:
            if unit.hp <= 0:
                unit.hp = 0
                if self.inspected_unit_id == unit.id:
                    self.inspected_unit_id = None
                if self.selected_unit_id == unit.id:
                    self.selected_unit_id = None

    def _check_victory(self) -> bool:
        player_king_alive = any(unit.unit_type == UnitType.KING and unit.team == Team.PLAYER and unit.is_alive() for unit in self.units)
        ai_king_alive = any(unit.unit_type == UnitType.KING and unit.team == Team.AI and unit.is_alive() for unit in self.units)
        if player_king_alive and ai_king_alive:
            return False
        self.winner = Team.PLAYER if player_king_alive else Team.AI
        self.state = GameState.GAME_OVER
        self.log(f"대국 종료. {TEAM_NAMES[self.winner]} 승리")
        saved_path = self.export_battle_log()
        self.log(f"전투 로그 저장: {saved_path.name}")
        self.last_feedback = f"{TEAM_NAMES[self.winner]} 승리"
        return True

    def selected_skill(self) -> str:
        unit = self.focused_unit
        if unit is None:
            return "-"
        if unit.boss and unit.unit_type == UnitType.KING:
            return f"공포 강림/순간이동  재사용 {unit.cooldowns.get('skill', 0)}/3"
        skill = SKILLS[unit.unit_type]
        return f"{skill.name}  재사용 {unit.cooldowns.get('skill', 0)}/{skill.cooldown}"

    def unit_summary(self) -> list[str]:
        unit = self.focused_unit
        if unit is None:
            return ["선택된 유닛이 없습니다."]
        skill = SKILLS[unit.unit_type]
        return [
            f"팀: {TEAM_NAMES[unit.team]}",
            f"병종: {UNIT_DISPLAY_NAMES[unit.unit_type]}",
            f"체력: {unit.hp}/{unit.max_hp}",
            f"공격력: {unit.attack_power()}",  
            f"공격 범위: {len(unit.attack_preview_tiles(self.board))}",
            f"스킬: {skill.name}",
            f"재사용: {unit.cooldowns.get('skill', 0)}",
        ]

