from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pygame

from game.ai.brain import SimpleAI
from game.engine.gameplay import GameplayResolutionMixin
from game.model.board import Board, Position
from game.model.constants import (
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
from game.model.skill import SKILLS
from game.model.unit import Unit
from game.turns.ai import ai_feedback_text, ai_move_only_feedback, ai_phase_delay, ai_preview_effects, choose_ai_action
from game.turns.player import (
    action_mode_for_key,
    blocked_selection_feedback,
    mode_help_text,
    move_completion_state,
    selected_unit_action_mode,
    should_auto_end_turn_after_action,
)
from game.tutorial.logic import (
    advance_tutorial_decision,
    build_tutorial_complete_card,
    build_tutorial_steps,
    build_tutorial_transition_card,
    tick_tutorial_ai_observe_pending,
    tick_tutorial_summary_pending,
    tutorial_allows_action_mode,
    tutorial_current_goal,
    tutorial_forced_attack_tiles,
    tutorial_forced_move_tiles,
    tutorial_forced_skill_tiles,
    tutorial_forced_unit,
    tutorial_goal_text,
)

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
    """클릭 한 번으로 판별한 보드 타일과 대상 정보를 묶어 둔 객체."""
    board_tile: Position | None = None
    clicked_unit: Unit | None = None


class GameManager(GameplayResolutionMixin):
    """전투 상태, 입력, 턴 전환, 튜토리얼을 총괄하는 런타임 관리자."""

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
        tutorial_mode: bool = False,
    ) -> None:
        """새 전투 세션을 만들고 보드, 유닛, 튜토리얼 상태를 초기화한다."""
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
        self.ai_delay = 0.0
        self.ai_timer = 0.0
        self.ai_phase = "idle"
        self.pending_ai_action = None
        self.ai_focus_unit_id: str | None = None
        self.ai_rng = random.Random()
        self.last_feedback = "아군 유닛을 선택한 뒤 이동, 공격 또는 스킬을 고르세요."
        self.effects: list[dict[str, object]] = []
        self.end_turn_warning_armed = False
        self.end_turn_rect = pygame.Rect(*END_TURN_BUTTON)
        self.log_panel_rect = pygame.Rect(*LOG_PANEL_RECT)
        self.tutorial_mode = tutorial_mode
        self.tutorial_steps = self._build_tutorial_steps()
        self.tutorial_index = 0
        self.tutorial_visible = tutorial_mode
        self.tutorial_waiting_for_action = False
        self.tutorial_pending_step_index: int | None = None
        self.tutorial_resume_action: str | None = None
        self.tutorial_summary_card: dict[str, object] | None = None
        self.tutorial_ai_observe_pending = False
        self.tutorial_ai_observe_timer = 0.0
        self.tutorial_summary_pending = False
        self.tutorial_summary_pending_timer = 0.0
        self.tutorial_summary_pending_card: dict[str, object] | None = None
        self.tutorial_completed = False
        self.start_turn(Team.PLAYER, opening=True)

    def _default_roster(self) -> list[UnitType]:
        """별도 입력이 없을 때 사용할 기본 로스터를 반환한다."""
        return [
            UnitType.ARCHER,
            UnitType.SWORDMAN,
            UnitType.SWORDMAN,
            UnitType.KNIGHT,
            UnitType.MAGE,
            UnitType.LANCER,
            UnitType.ARCHER,
            UnitType.BISHOP,
            UnitType.KNIGHT,
        ]

    def _create_units(
        self,
        player_roster: list[UnitType],
        ai_roster: list[UnitType],
        player_positions: list[Position] | None = None,
        ai_positions: list[Position] | None = None,
    ) -> list[Unit]:
        """양 팀 로스터와 배치 좌표를 바탕으로 전체 유닛 목록을 생성한다."""
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
        """팀, 종류, 위치 정보를 바탕으로 실제 유닛 객체를 만든다."""
        hp = BASE_HP[unit_type]
        attack_bonus = 0
        armor = 0
        boss = False
        if team == Team.AI and unit_type == UnitType.KING:
            if self.ai_difficulty >= 7:
                hp += 6
                attack_bonus = 1
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
        """왕의 기본 위치가 막혔는지 확인하고 대체 위치를 찾는다."""
        preferred = PLAYER_KING_POS if team == Team.PLAYER else AI_KING_POS
        if self.board.is_walkable(preferred):
            return preferred
        fallback_pool = PLAYER_HOME_POSITIONS if team == Team.PLAYER else AI_HOME_POSITIONS
        for candidate in fallback_pool:
            if self.board.is_walkable(candidate):
                return candidate
        return preferred

    def _resolve_deploy_positions(self, roster: list[UnitType], team: Team, reserved: set[Position]) -> list[Position]:
        """남은 홈 타일 중에서 로스터에 맞는 배치 좌표를 계산한다."""
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
        """자동 배치 시 기물 우선순위를 반환한다."""
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
        """자동 배치 후보 칸의 전략 점수를 계산한다."""
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
        """지정 팀의 턴을 시작하며 쿨다운, 피드백, AI 단계 상태를 정리한다."""
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
        self.pending_ai_action = None
        self.ai_focus_unit_id = None
        self.ai_phase = "idle"
        self.tutorial_resume_action = None
        self.log(f"{TEAM_NAMES[team]} 차례입니다.")
        if team == Team.PLAYER:
            self.last_feedback = "아군 유닛을 고른 뒤 이동, 공격 또는 스킬을 선택하세요."
        else:
            self.last_feedback = "적팀이 수를 계산 중입니다."
            self._set_ai_phase("thinking")

    def handle_event(self, event: pygame.event.Event) -> None:
        """pygame 입력 이벤트를 받아 현재 게임 상태에 맞게 분기 처리한다."""
        if self.state == GameState.GAME_OVER:
            return
        if self.tutorial_summary_pending:
            return
        if self._handle_tutorial_pending_input(event):
            return
        if self._handle_tutorial_toggle_input(event):
            return
        if self._handle_tutorial_visible_input(event):
            return
        if self._handle_player_key_input(event):
            return
        if self._handle_mousewheel_input(event):
            return
        self._handle_player_mouse_input(event)

    def _handle_tutorial_pending_input(self, event: pygame.event.Event) -> bool:
        """다음 단계 대기 중인 튜토리얼 입력을 처리한다."""
        if not self.tutorial_mode or self.tutorial_visible or self.tutorial_pending_step_index is None:
            return False
        if event.type == pygame.KEYDOWN and event.key in {pygame.K_SPACE, pygame.K_RETURN, pygame.K_RIGHT}:
            self.tutorial_index = self.tutorial_pending_step_index
            self.tutorial_pending_step_index = None
            self.tutorial_visible = True
            self.last_feedback = str(self.tutorial_steps[self.tutorial_index]["title"])
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.tutorial_index = self.tutorial_pending_step_index
            self.tutorial_pending_step_index = None
            self.tutorial_visible = True
            self.last_feedback = str(self.tutorial_steps[self.tutorial_index]["title"])
            return True
        return True

    def _handle_tutorial_toggle_input(self, event: pygame.event.Event) -> bool:
        """참고용 튜토리얼 카드 열기와 닫기 입력을 처리한다."""
        if self.tutorial_mode or self.tutorial_visible:
            return False
        if event.type == pygame.KEYDOWN and event.key in {pygame.K_F1, pygame.K_h}:
            self.tutorial_visible = True
            self.last_feedback = "튜토리얼을 다시 열었습니다."
            return True
        return False

    def _handle_tutorial_visible_input(self, event: pygame.event.Event) -> bool:
        """현재 표시 중인 튜토리얼 카드 입력을 처리한다."""
        if not self.tutorial_visible:
            return False
        if event.type == pygame.KEYDOWN:
            if event.key in {pygame.K_ESCAPE, pygame.K_F1, pygame.K_h}:
                self.tutorial_visible = False
                self.last_feedback = "튜토리얼을 닫았습니다. F1 또는 H로 다시 열 수 있습니다."
            elif event.key in {pygame.K_SPACE, pygame.K_RETURN, pygame.K_RIGHT}:
                self.advance_tutorial()
            elif event.key == pygame.K_LEFT:
                self.rewind_tutorial()
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.advance_tutorial()
            return True
        return False

    def _handle_player_key_input(self, event: pygame.event.Event) -> bool:
        """플레이어 턴의 키보드 입력을 처리한다."""
        if event.type != pygame.KEYDOWN or self.state != GameState.PLAYER_TURN:
            return False
        requested_mode = action_mode_for_key(event.key)
        if requested_mode is not None:
            if not self._tutorial_allows_action_mode(requested_mode):
                self.last_feedback = self._tutorial_goal_text()
                return True
            self.action_mode = requested_mode
        elif event.key == pygame.K_e:
            self.try_end_player_turn()
            return True
        self.last_feedback = self.mode_help_text()
        return True

    def _handle_mousewheel_input(self, event: pygame.event.Event) -> bool:
        """마우스 휠 입력으로 로그 스크롤을 처리한다."""
        if event.type != pygame.MOUSEWHEEL:
            return False
        mouse_pos = pygame.mouse.get_pos()
        if self.log_panel_rect.collidepoint(mouse_pos):
            self.scroll_logs(event.y)
            return True
        return False

    def _handle_player_mouse_input(self, event: pygame.event.Event) -> None:
        """플레이어 턴의 마우스 입력을 처리한다."""
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_click(event.pos)

    def _handle_click(self, mouse_pos: tuple[int, int]) -> None:
        """현재 행동 모드에 따라 클릭 결과를 해석한다."""
        if self.state != GameState.PLAYER_TURN:
            return
        if self.end_turn_rect.collidepoint(mouse_pos):
            self.try_end_player_turn("청 진영이 턴을 종료했습니다.")
            return

        for mode, rect in ACTION_BUTTONS.items():
            if rect.collidepoint(mouse_pos):
                if not self._tutorial_allows_action_mode(mode):
                    self.last_feedback = self._tutorial_goal_text()
                    return
                self.action_mode = mode
                self.end_turn_warning_armed = False
                self.last_feedback = self.mode_help_text()
                return

        click = self._click_context(mouse_pos)
        if click.board_tile is None:
            return

        if click.clicked_unit is not None:
            self.inspected_unit_id = click.clicked_unit.id

        if self._handle_quick_skill_click(click):
            return

        if click.clicked_unit and click.clicked_unit.team == Team.PLAYER:
            self._handle_player_unit_click(click.clicked_unit)
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
            self._handle_move_click(unit, click.board_tile)
            return

        if self.action_mode == ActionMode.ATTACK:
            self._handle_attack_click(unit, click.clicked_unit)
            return

        if self.action_mode == ActionMode.SKILL:
            self._handle_skill_click(unit, click.board_tile)

    def _handle_quick_skill_click(self, click: ClickContext) -> bool:
        """즉시 스킬 시전이 가능한 클릭인지 판정하고 처리한다."""
        if (
            self.action_mode != ActionMode.SKILL
            or self.selected_unit is None
            or click.board_tile not in self.valid_skill_tiles
            or not self.can_unit_act(self.selected_unit)
        ):
            return False
        self.activation_unit_id = self.selected_unit.id
        self.activation_action_used = True
        self._resolve_skill(self.selected_unit, click.board_tile)
        self._notify_tutorial("skill", unit=self.selected_unit, target_tile=click.board_tile)
        if self.state != GameState.GAME_OVER and should_auto_end_turn_after_action(
            "skill",
            self.tutorial_mode,
            self._tutorial_current_goal(),
        ):
            self.end_player_turn()
        return True

    def _handle_player_unit_click(self, unit: Unit) -> None:
        """플레이어가 유닛을 클릭했을 때 선택 상태를 갱신한다."""
        if self.can_select_unit(unit):
            self.selected_unit_id = unit.id
            self.action_mode = selected_unit_action_mode(
                unit.id,
                self.activation_unit_id,
                self.activation_move_used,
            )
            self.last_feedback = self.mode_help_text()
            self.add_effect("select", unit.position, duration=0.25)
            self._notify_tutorial("select", unit=unit)
            return
        forced_unit = self._tutorial_forced_unit()
        self.last_feedback = blocked_selection_feedback(forced_unit.name if forced_unit is not None else None)

    def _handle_move_click(self, unit: Unit, tile: Position) -> None:
        """이동 모드에서 클릭한 타일로 실제 이동을 처리한다."""
        if not self.can_unit_move(unit):
            self.last_feedback = "이 유닛은 이미 이동했습니다."
            return
        if tile not in self.valid_move_tiles:
            self.last_feedback = "이동 가능한 칸을 선택하세요."
            return
        start = unit.position
        unit.move(tile)
        self.activation_unit_id = unit.id
        self.activation_move_used = True
        self.selected_unit_id = unit.id
        self.inspected_unit_id = unit.id
        self.add_effect("move", start, duration=0.30)
        self.add_effect("move", tile, duration=0.45)
        self.log(f"{unit.name} 이동: {start} -> {tile}")
        self.queue_sound("move")
        self._notify_tutorial("move", unit=unit, destination=tile)
        next_mode, feedback = move_completion_state(bool(self.valid_attack_tiles or self.valid_skill_tiles))
        if next_mode is not None:
            self.action_mode = next_mode
        self.last_feedback = feedback

    def _handle_attack_click(self, unit: Unit, target: Unit | None) -> None:
        """공격 모드에서 선택한 대상을 실제로 공격한다."""
        if not self.can_unit_act(unit):
            self.last_feedback = "이 유닛은 이미 행동했습니다."
            return
        if target is None or target.position not in self.valid_attack_tiles:
            self.last_feedback = "공격 가능한 적 유닛을 선택하세요."
            return
        self.activation_unit_id = unit.id
        self.activation_action_used = True
        self._resolve_basic_attack(unit, target)
        self._notify_tutorial("attack", unit=unit, target=target)
        if self.state != GameState.GAME_OVER and should_auto_end_turn_after_action(
            "attack",
            self.tutorial_mode,
            self._tutorial_current_goal(),
        ):
            self.end_player_turn()

    def _handle_skill_click(self, unit: Unit, tile: Position) -> None:
        """스킬 모드에서 선택한 타일에 스킬을 사용한다."""
        if not self.can_unit_act(unit):
            self.last_feedback = "이 유닛은 이미 행동했습니다."
            return
        if tile not in self.valid_skill_tiles:
            self.last_feedback = "스킬 대상 칸을 선택하세요."
            return
        self.activation_unit_id = unit.id
        self.activation_action_used = True
        self._resolve_skill(unit, tile)
        if self.state != GameState.GAME_OVER:
            self.end_player_turn()

    def _click_context(self, mouse_pos: tuple[int, int]) -> ClickContext:
        """마우스 좌표를 보드 타일과 유닛 정보로 변환한다."""
        from game.engine.renderer import board_tile_at_pixel

        tile = board_tile_at_pixel(mouse_pos)
        return ClickContext() if tile is None else ClickContext(tile, self.unit_at(tile))

    @property
    def selected_unit(self) -> Unit | None:
        """현재 선택된 유닛 객체를 반환한다."""
        if self.selected_unit_id is None:
            return None
        return next((unit for unit in self.units if unit.id == self.selected_unit_id and unit.is_alive()), None)

    @property
    def inspected_unit(self) -> Unit | None:
        """현재 정보 패널에서 바라보는 유닛 객체를 반환한다."""
        if self.inspected_unit_id is None:
            return None
        return next((unit for unit in self.units if unit.id == self.inspected_unit_id and unit.is_alive()), None)

    @property
    def focused_unit(self) -> Unit | None:
        """선택 상태와 조사 상태를 합쳐 UI 기준의 포커스 유닛을 반환한다."""
        return self.inspected_unit or self.selected_unit

    @property
    def living_units(self) -> list[Unit]:
        """현재 살아 있는 유닛 목록만 반환한다."""
        return [unit for unit in self.units if unit.is_alive()]

    def can_select_unit(self, unit: Unit) -> bool:
        """지금 이 유닛을 새로 선택할 수 있는지 판단한다."""
        forced_unit = self._tutorial_forced_unit()
        if forced_unit is not None and unit.id != forced_unit.id:
            return False
        return unit.team == self.current_turn and unit.is_alive() and (self.activation_unit_id is None or self.activation_unit_id == unit.id)

    def can_unit_move(self, unit: Unit) -> bool:
        """현재 턴과 활성화 상태 기준으로 이동 가능 여부를 반환한다."""
        return unit.team == self.current_turn and unit.is_alive() and not self.activation_action_used and not self.activation_move_used and (self.activation_unit_id is None or self.activation_unit_id == unit.id)

    def can_unit_act(self, unit: Unit) -> bool:
        """현재 턴과 활성화 상태 기준으로 공격 또는 스킬 가능 여부를 반환한다."""
        return unit.team == self.current_turn and unit.is_alive() and not self.activation_action_used and (self.activation_unit_id is None or self.activation_unit_id == unit.id)

    @property
    def valid_move_tiles(self) -> list[Position]:
        """선택된 유닛이 이동할 수 있는 타일 목록을 반환한다."""
        unit = self.selected_unit
        if unit is None or not self.can_unit_move(unit):
            return []
        tiles = unit.basic_move_targets(self.board, self.living_units)
        tutorial_tiles = self._tutorial_forced_move_tiles(unit)
        return [tile for tile in tiles if tile in tutorial_tiles] if tutorial_tiles is not None else tiles

    @property
    def attack_preview_tiles(self) -> list[Position]:
        """선택된 유닛의 공격 미리보기 타일을 반환한다."""
        unit = self.selected_unit
        return unit.attack_preview_tiles(self.board) if unit and self.can_unit_act(unit) else []

    @property
    def valid_attack_tiles(self) -> list[Position]:
        """선택된 유닛이 실제로 공격 가능한 타일 목록을 반환한다."""
        unit = self.selected_unit
        if unit is None or not self.can_unit_act(unit):
            return []
        tiles = unit.attack_targets(self.board, self.living_units)
        tutorial_tiles = self._tutorial_forced_attack_tiles(unit)
        return [tile for tile in tiles if tile in tutorial_tiles] if tutorial_tiles is not None else tiles

    @property
    def valid_skill_tiles(self) -> list[Position]:
        """선택된 유닛이 실제로 스킬을 사용할 수 있는 타일 목록을 반환한다."""
        unit = self.selected_unit
        if unit is None or not self.can_unit_act(unit):
            return []
        tiles = unit.skill_targets(self.board, self.living_units)
        tutorial_tiles = self._tutorial_forced_skill_tiles(unit)
        return [tile for tile in tiles if tile in tutorial_tiles] if tutorial_tiles is not None else tiles

    def update(self, dt: float) -> None:
        """프레임 시간 경과에 따라 이펙트와 AI 턴 진행을 갱신한다."""
        self._update_effects(dt)
        if self.tutorial_summary_pending:
            summary_tick = tick_tutorial_summary_pending(
                self.tutorial_summary_pending,
                self.tutorial_summary_pending_timer,
                dt,
                bool(self.effects),
            )
            self.tutorial_summary_pending = summary_tick["pending"]
            self.tutorial_summary_pending_timer = summary_tick["timer"]
            if summary_tick["should_show_card"]:
                self.tutorial_visible = True
                self.tutorial_summary_card = self.tutorial_summary_pending_card
                self.tutorial_summary_pending_card = None
        if self.tutorial_ai_observe_pending:
            observe_tick = tick_tutorial_ai_observe_pending(
                self.tutorial_ai_observe_pending,
                self.tutorial_ai_observe_timer,
                dt,
                bool(self.effects),
            )
            self.tutorial_ai_observe_pending = observe_tick["pending"]
            self.tutorial_ai_observe_timer = observe_tick["timer"]
            if observe_tick["should_complete_observe"]:
                self._notify_tutorial("ai_turn_complete")
        if self.state == GameState.AI_TURN:
            self.ai_timer += dt
            if self.ai_timer >= self.ai_delay:
                self.ai_timer = 0.0
                if self.ai_phase == "thinking":
                    self._plan_ai_turn()
                elif self.ai_phase == "acting":
                    self._execute_ai_turn()

    def _plan_ai_turn(self) -> None:
        """AI가 다음에 실행할 행동을 미리 계산하고 프리뷰 상태를 세팅한다."""
        action = choose_ai_action(
            self.ai,
            self.board,
            self.living_units,
            self.tutorial_mode,
            self.tutorial_waiting_for_action,
            self._tutorial_current_goal(),
        )
        if action is None:
            self.end_ai_turn("적팀이 턴을 종료했습니다.")
            return
        self.pending_ai_action = action
        unit = self.get_unit(action.unit_id)
        if unit is not None:
            self.ai_focus_unit_id = unit.id
            self.inspected_unit_id = unit.id
            for effect in ai_preview_effects(action, self.ai_delay):
                target = str(effect["target"])
                if target == "unit":
                    self.add_effect(str(effect["type"]), unit.position, duration=float(effect["duration"]))
                elif target == "move_target" and action.move_target is not None:
                    self.add_effect(str(effect["type"]), action.move_target, duration=float(effect["duration"]))
                elif target == "action_target" and action.action_target is not None:
                    self.add_effect(str(effect["type"]), action.action_target, duration=float(effect["duration"]))
        self._set_ai_phase("acting")
        if unit is not None:
            feedback = ai_feedback_text(unit, action)
            if feedback is not None:
                self.last_feedback = feedback

    def _execute_ai_turn(self) -> None:
        """미리 계산된 AI 행동을 실제 게임 상태에 반영한다."""
        action = self.pending_ai_action
        self.pending_ai_action = None
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
        else:
            feedback = ai_move_only_feedback(unit, action)
            if feedback is not None:
                self.last_feedback = feedback
        if self.state != GameState.GAME_OVER:
            self.end_ai_turn()

    def try_end_player_turn(self, reason: str | None = None) -> bool:
        """플레이어가 턴 종료 조건을 만족했는지 확인한 뒤 종료를 시도한다."""
        if not self.activation_move_used:
            self.end_turn_warning_armed = False
            self.last_feedback = "턴 종료 전에는 반드시 아군 유닛을 한 번 이동해야 합니다."
            return False
        if self.tutorial_mode and self._tutorial_current_goal() == "end_turn":
            self.end_turn_warning_armed = False
            self._notify_tutorial("end_turn")
            return True
        self.end_turn_warning_armed = False
        self.end_player_turn(reason)
        return True

    def end_player_turn(self, reason: str | None = None) -> None:
        """플레이어 턴을 닫고 AI 턴 준비 상태로 전환한다."""
        if reason:
            self.log(reason)
        self.queue_sound("end_turn")
        self.state = GameState.AI_TURN
        self.start_turn(Team.AI)

    def end_ai_turn(self, reason: str | None = None) -> None:
        """AI 턴을 닫고 다시 플레이어 턴으로 넘긴다."""
        if reason:
            self.log(reason)
        self.queue_sound("end_turn")
        self.turn_count += 1
        self.state = GameState.PLAYER_TURN
        self.start_turn(Team.PLAYER)
        if self.tutorial_mode and self.tutorial_waiting_for_action and self.tutorial_index < len(self.tutorial_steps):
            if self.tutorial_steps[self.tutorial_index].get("goal") == "observe_ai_turn":
                self.tutorial_ai_observe_pending = True
                self.tutorial_ai_observe_timer = 0.55

    def get_unit(self, unit_id: str) -> Unit | None:
        """id로 살아 있는 유닛 하나를 조회한다."""
        return next((unit for unit in self.units if unit.id == unit_id and unit.is_alive()), None)

    def unit_at(self, position: Position) -> Unit | None:
        """지정 좌표를 점유 중인 살아 있는 유닛을 반환한다."""
        return next((unit for unit in self.units if unit.is_alive() and unit.position == position), None)

    def log(self, message: str) -> None:
        """전투 로그를 추가하고 스크롤 상태를 조정한다."""
        if self.log_scroll > 0:
            self.log_scroll += 1
        self.logs.append(message)
        self.log_scroll = min(self.log_scroll, self.max_log_scroll())

    def export_battle_log(self) -> Path:
        """현재 전투 로그를 파일로 저장하고 저장 경로를 반환한다."""
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
        """재생할 사운드 이벤트를 큐에 추가한다."""
        self.sound_events.append(sound_name)

    def drain_sound_events(self) -> list[str]:
        """누적된 사운드 이벤트를 꺼내고 큐를 비운다."""
        queued = list(self.sound_events)
        self.sound_events.clear()
        return queued

    def scroll_logs(self, delta: int) -> None:
        """로그 스크롤 오프셋을 안전한 범위 안에서 조정한다."""
        self.log_scroll = max(0, min(self.max_log_scroll(), self.log_scroll + delta))

    def max_log_scroll(self, visible_lines: int = 4) -> int:
        """현재 로그 기준 최대 스크롤 가능 값을 반환한다."""
        estimated_wrapped_lines = len(self.logs) * 3
        return max(0, estimated_wrapped_lines - visible_lines)

    def visible_logs(self, visible_lines: int = 4) -> list[str]:
        """현재 스크롤 위치에 맞는 표시용 로그만 잘라서 반환한다."""
        end = len(self.logs) - self.log_scroll
        start = max(0, end - visible_lines)
        return self.logs[start:end]

    def mode_help_text(self) -> str:
        """현재 행동 모드에 맞는 도움말 문구를 반환한다."""
        return mode_help_text(self.selected_unit is not None, self.action_mode)

    def step_guide_text(self) -> str:
        """현재 튜토리얼 단계나 일반 진행에 맞는 안내 문구를 반환한다."""
        if self.tutorial_mode and self.tutorial_pending_step_index is not None:
            return "실습 완료. 화면 안내를 읽고 좌클릭 또는 Space로 다음 설명으로 넘어가세요."
        if self.tutorial_mode and self.tutorial_waiting_for_action:
            return self._tutorial_goal_text()
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
        """현재 턴 상태를 UI에 표시할 짧은 문구로 반환한다."""
        if self.state == GameState.PLAYER_TURN:
            return "청 진영 행동 중"
        if self.state == GameState.AI_TURN:
            remaining = max(0.0, self.ai_delay - self.ai_timer)
            if self.ai_phase == "acting":
                return f"적팀 행동 준비 중... {remaining:.1f}초"
            return f"적팀 계산 중... {remaining:.1f}초"
        return f"승리: {TEAM_NAMES[self.winner]}" if self.winner is not None else "대기 중..."

    def action_summary_text(self) -> str:
        """현재 화면 상단에 표시할 액션 요약 문구를 반환한다."""
        if self.tutorial_visible:
            return f"튜토리얼 {self.tutorial_index + 1}/{len(self.tutorial_steps)}"
        if self.tutorial_mode and self.tutorial_pending_step_index is not None:
            return "튜토리얼 다음 설명 대기"
        if self.tutorial_mode and self.tutorial_waiting_for_action:
            return "튜토리얼 실습 중"
        unit = self.selected_unit
        if unit is None:
            return "선택된 아군 없음"
        move_state = "사용" if self.activation_move_used and self.activation_unit_id == unit.id else "가능"
        action_state = "사용" if self.activation_action_used and self.activation_unit_id == unit.id else "가능"
        return f"이동 {move_state} | 행동 {action_state}"

    def tutorial_card(self) -> dict[str, object] | None:
        """현재 보여줘야 할 튜토리얼 카드 데이터를 반환한다."""
        if not self.tutorial_visible:
            return None
        if self.tutorial_summary_card is not None:
            return self.tutorial_summary_card
        if not self.tutorial_steps:
            return None
        return self.tutorial_steps[self.tutorial_index]

    def advance_tutorial(self) -> None:
        """현재 카드/단계 상태를 기반으로 튜토리얼을 다음 상태로 전환한다."""
        decision = advance_tutorial_decision(
            self.tutorial_visible,
            self.tutorial_summary_card,
            self.tutorial_pending_step_index,
            self.tutorial_mode,
            self.tutorial_index,
            self.tutorial_steps,
        )
        action = decision["action"]
        if action == "noop":
            return
        if action == "show_pending_step":
            self.tutorial_summary_card = None
            self.tutorial_index = int(decision["next_index"])
            self.tutorial_pending_step_index = None
            self.tutorial_visible = True
            self.last_feedback = str(decision["feedback"])
            return
        if action == "complete_tutorial":
            self.tutorial_visible = False
            self.tutorial_summary_card = None
            self.tutorial_mode = False
            self.tutorial_waiting_for_action = False
            self.tutorial_pending_step_index = None
            self.tutorial_resume_action = None
            self.tutorial_summary_pending = False
            self.tutorial_summary_pending_card = None
            self.tutorial_ai_observe_pending = False
            if self.state != GameState.GAME_OVER:
                self.state = GameState.PLAYER_TURN
                self.start_turn(Team.PLAYER, opening=True)
            self.last_feedback = str(decision["feedback"])
            return
        if action == "advance_info_step":
            self.tutorial_index = int(decision["next_index"])
            self.last_feedback = str(decision["feedback"])
            return
        if action == "wait_for_action":
            self.tutorial_visible = False
            self.tutorial_waiting_for_action = True
            self.last_feedback = str(decision["feedback"])
            return
        if action == "wait_for_action_and_resume_turn":
            self.tutorial_visible = False
            self.tutorial_waiting_for_action = True
            self.last_feedback = str(decision["feedback"])
            self.end_player_turn("청 진영이 턴을 종료했습니다.")
            return
        if action == "close_reference":
            self.tutorial_visible = False
            self.last_feedback = str(decision["feedback"])
            return
        if action == "advance_reference":
            self.tutorial_index = int(decision["next_index"])
            self.last_feedback = str(decision["feedback"])

    def rewind_tutorial(self) -> None:
        """참고 모드에서 이전 튜토리얼 카드로 되돌아간다."""
        if not self.tutorial_visible or self.tutorial_mode:
            return
        self.tutorial_index = max(0, self.tutorial_index - 1)
        self.last_feedback = str(self.tutorial_steps[self.tutorial_index]["title"])

    def add_effect(self, effect_type: str, position: Position, duration: float = 0.45, **extra: object) -> None:
        """화면에 표시할 이펙트 하나를 큐에 추가한다."""
        effect = {"type": effect_type, "position": position, "timer": duration, "max_timer": duration}
        effect.update(extra)
        self.effects.append(effect)

    def _build_tutorial_steps(self) -> list[dict[str, object]]:
        """기본 튜토리얼 단계 목록을 생성한다."""
        return build_tutorial_steps()

    def _set_ai_phase(self, phase: str) -> None:
        """AI 턴 내부 단계와 타이머를 초기화한다."""
        self.ai_phase = phase
        self.ai_timer = 0.0
        self.ai_delay = ai_phase_delay(phase, self.ai_rng)

    def _tutorial_goal_text(self) -> str:
        """현재 튜토리얼 목표 문구를 반환한다."""
        return tutorial_goal_text(self.tutorial_mode, self.tutorial_index, self.tutorial_steps)

    def _tutorial_current_goal(self) -> str | None:
        """현재 튜토리얼 goal 키를 반환한다."""
        return tutorial_current_goal(self.tutorial_mode, self.tutorial_index, self.tutorial_steps)

    def _tutorial_allows_action_mode(self, mode: ActionMode) -> bool:
        """튜토리얼이 특정 행동 모드를 허용하는지 판정한다."""
        return tutorial_allows_action_mode(mode, self.tutorial_mode, self.tutorial_waiting_for_action, self._tutorial_current_goal())

    def _tutorial_forced_unit(self) -> Unit | None:
        """현재 단계에서 강제로 선택해야 하는 유닛을 반환한다."""
        return tutorial_forced_unit(
            self.living_units,
            self.tutorial_mode,
            self.tutorial_waiting_for_action,
            self._tutorial_current_goal(),
        )

    def _tutorial_forced_move_tiles(self, unit: Unit) -> set[Position] | None:
        """현재 단계에서 허용되는 이동 타일 제한을 반환한다."""
        return tutorial_forced_move_tiles(unit, self.tutorial_mode, self.tutorial_waiting_for_action, self._tutorial_current_goal())

    def _tutorial_forced_attack_tiles(self, unit: Unit) -> set[Position] | None:
        """현재 단계에서 허용되는 공격 타일 제한을 반환한다."""
        return tutorial_forced_attack_tiles(unit, self.tutorial_mode, self.tutorial_waiting_for_action, self._tutorial_current_goal())

    def _tutorial_forced_skill_tiles(self, unit: Unit) -> set[Position] | None:
        """현재 단계에서 허용되는 스킬 타일 제한을 반환한다."""
        return tutorial_forced_skill_tiles(unit, self.tutorial_mode, self.tutorial_waiting_for_action, self._tutorial_current_goal())

    def _notify_tutorial(self, event_type: str, **payload: object) -> None:
        """플레이어 행동 이벤트를 튜토리얼 진행기로 전달한다."""
        if not self.tutorial_mode or not self.tutorial_waiting_for_action or self.tutorial_index >= len(self.tutorial_steps):
            return
        step = self.tutorial_steps[self.tutorial_index]
        goal = step.get("goal")
        completed = False

        if goal == "select_swordman" and event_type == "select":
            unit = payload.get("unit")
            completed = isinstance(unit, Unit) and unit.team == Team.PLAYER and unit.unit_type == UnitType.SWORDMAN
        elif goal == "select_archer" and event_type == "select":
            unit = payload.get("unit")
            completed = isinstance(unit, Unit) and unit.team == Team.PLAYER and unit.unit_type == UnitType.ARCHER
        elif goal == "move_any" and event_type == "move":
            unit = payload.get("unit")
            completed = isinstance(unit, Unit) and unit.team == Team.PLAYER
        elif goal == "attack_any" and event_type == "attack":
            unit = payload.get("unit")
            target = payload.get("target")
            completed = isinstance(unit, Unit) and isinstance(target, Unit) and unit.team == Team.PLAYER and target.team == Team.AI
        elif goal == "skill_any" and event_type == "skill":
            unit = payload.get("unit")
            target_tile = payload.get("target_tile")
            completed = isinstance(unit, Unit) and unit.team == Team.PLAYER and unit.unit_type == UnitType.ARCHER and target_tile == (4, 3)
        elif goal == "end_turn" and event_type == "end_turn":
            completed = True
        elif goal == "observe_ai_turn" and event_type == "ai_turn_complete":
            completed = True

        if not completed:
            return

        self.tutorial_waiting_for_action = False
        step_title = str(step["title"])
        self.log(f"튜토리얼 진행: {step_title} 완료")
        if self.tutorial_index >= len(self.tutorial_steps) - 1:
            self.tutorial_completed = True
            self.tutorial_visible = False
            self.tutorial_summary_pending = True
            self.tutorial_summary_pending_timer = 0.55
            self.tutorial_summary_pending_card = build_tutorial_complete_card()
            self.last_feedback = "튜토리얼을 마무리했습니다. 좌클릭 또는 Space로 안내를 닫아보세요."
            return

        next_index = self.tutorial_index + 1
        self.tutorial_pending_step_index = next_index
        self.tutorial_visible = False
        self.tutorial_summary_pending = True
        self.tutorial_summary_pending_timer = 0.45
        next_title = str(self.tutorial_steps[next_index]["title"])
        self.tutorial_summary_pending_card = build_tutorial_transition_card(step_title, next_title)
        if self.tutorial_steps[next_index].get("goal") == "observe_ai_turn":
            self.tutorial_resume_action = "end_player_turn"
        self.last_feedback = f"{step_title} 완료. 좌클릭 또는 Space로 다음 설명을 확인하세요."

    def _update_effects(self, dt: float) -> None:
        """시간 경과에 따라 이펙트 타이머를 줄이고 만료된 항목을 정리한다."""
        next_effects: list[dict[str, object]] = []
        for effect in self.effects:
            timer = float(effect["timer"]) - dt
            if timer > 0:
                effect["timer"] = timer
                next_effects.append(effect)
        self.effects = next_effects

    def _cleanup_dead_units(self) -> None:
        """체력이 0 이하인 유닛의 후처리 상태를 정리한다."""
        for unit in self.units:
            if unit.hp <= 0:
                unit.hp = 0
                if self.inspected_unit_id == unit.id:
                    self.inspected_unit_id = None
                if self.selected_unit_id == unit.id:
                    self.selected_unit_id = None

    def _check_victory(self) -> bool:
        """승패 조건이 충족되었는지 확인한다."""
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
        """포커스 유닛 기준으로 현재 표시할 스킬 이름을 반환한다."""
        unit = self.focused_unit
        if unit is None:
            return "-"
        if unit.boss and unit.unit_type == UnitType.KING:
            return f"공포 강림/순간이동  재사용 {unit.cooldowns.get('skill', 0)}/3"
        skill = SKILLS[unit.unit_type]
        return f"{skill.name}  재사용 {unit.cooldowns.get('skill', 0)}/{skill.cooldown}"

    def unit_summary(self) -> list[str]:
        """포커스 유닛 정보 패널에 들어갈 요약 문구 목록을 만든다."""
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

