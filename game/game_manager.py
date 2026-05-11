from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pygame

from game.ai import SimpleAI
from game.board import Board, Position
from game.constants import ATTACK_BUTTON, END_TURN_BUTTON, LOG_PANEL_RECT, MOVE_BUTTON, SKILL_BUTTON, ActionMode, GameState, Team, TEAM_NAMES, UNIT_DISPLAY_NAMES, UnitType
from game.skill import SKILLS
from game.unit import Unit

ACTION_BUTTONS = {
    ActionMode.MOVE: pygame.Rect(*MOVE_BUTTON),
    ActionMode.ATTACK: pygame.Rect(*ATTACK_BUTTON),
    ActionMode.SKILL: pygame.Rect(*SKILL_BUTTON),
}


@dataclass(slots=True)
class ClickContext:
    board_tile: Position | None = None
    clicked_unit: Unit | None = None


class GameManager:
    def __init__(self, project_root: Path, blocked_tiles: set[Position] | None = None) -> None:
        self.project_root = project_root
        self.board = Board(blocked_tiles=set(blocked_tiles or set()))
        self.units = self._create_units()
        self.ai = SimpleAI()
        self.state = GameState.PLAYER_TURN
        self.action_mode = ActionMode.MOVE
        self.selected_unit_id: str | None = None
        self.current_turn = Team.PLAYER
        self.turn_count = 1
        self.winner: Team | None = None
        self.logs: list[str] = ["전투 시작. 청팀부터 시작합니다."]
        self.log_scroll = 0
        self.ai_delay = 0.7
        self.ai_timer = 0.0
        self.last_feedback = "유닛을 클릭한 뒤 이동, 공격, 스킬 중 하나를 선택하세요."
        self.effects: list[dict[str, object]] = []
        self.end_turn_warning_armed = False
        self.end_turn_rect = pygame.Rect(*END_TURN_BUTTON)
        self.log_panel_rect = pygame.Rect(*LOG_PANEL_RECT)
        self.start_turn(Team.PLAYER, opening=True)

    def _create_units(self) -> list[Unit]:
        return [
            Unit("p_archer_1", "청팀 궁수 A", UnitType.ARCHER, Team.PLAYER, 2, 2, (1, 7)),
            Unit("p_archer_2", "청팀 궁수 B", UnitType.ARCHER, Team.PLAYER, 2, 2, (6, 7)),
            Unit("p_king", "청팀 왕", UnitType.KING, Team.PLAYER, 5, 5, (3, 7)),
            Unit("p_mage", "청팀 마법사", UnitType.MAGE, Team.PLAYER, 2, 2, (4, 7)),
            Unit("p_sword_1", "청팀 검사 A", UnitType.SWORDMAN, Team.PLAYER, 3, 3, (2, 6)),
            Unit("p_sword_2", "청팀 검사 B", UnitType.SWORDMAN, Team.PLAYER, 3, 3, (5, 6)),
            Unit("a_archer_1", "홍팀 궁수 A", UnitType.ARCHER, Team.AI, 2, 2, (1, 0)),
            Unit("a_archer_2", "홍팀 궁수 B", UnitType.ARCHER, Team.AI, 2, 2, (6, 0)),
            Unit("a_king", "홍팀 왕", UnitType.KING, Team.AI, 5, 5, (3, 0)),
            Unit("a_mage", "홍팀 마법사", UnitType.MAGE, Team.AI, 2, 2, (4, 0)),
            Unit("a_sword_1", "홍팀 검사 A", UnitType.SWORDMAN, Team.AI, 3, 3, (2, 1)),
            Unit("a_sword_2", "홍팀 검사 B", UnitType.SWORDMAN, Team.AI, 3, 3, (5, 1)),
        ]

    def start_turn(self, team: Team, opening: bool = False) -> None:
        self.current_turn = team
        if not opening:
            for unit in self.units:
                if unit.team == team and unit.is_alive():
                    unit.tick_cooldowns()
        self.ai_timer = 0.0
        self.selected_unit_id = None
        self.action_mode = ActionMode.MOVE
        self.end_turn_warning_armed = False
        self.log(f"{TEAM_NAMES[team]} 차례입니다.")
        if team == Team.PLAYER:
            self.last_feedback = "유닛을 클릭하면 이동 칸과 공격 사거리가 함께 표시됩니다."
        else:
            self.last_feedback = "홍팀이 지형을 살피며 행동을 고르는 중입니다."

    def handle_event(self, event: pygame.event.Event) -> None:
        if self.state == GameState.GAME_OVER:
            return
        if event.type == pygame.KEYDOWN and self.state == GameState.PLAYER_TURN:
            if event.key == pygame.K_q:
                self.action_mode = ActionMode.SKILL
                self.last_feedback = self.mode_help_text()
            elif event.key == pygame.K_a:
                self.action_mode = ActionMode.ATTACK
                self.last_feedback = self.mode_help_text()
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
            if self.selected_unit is None and not self.end_turn_warning_armed:
                self.end_turn_warning_armed = True
                self.last_feedback = "아직 행동하지 않았습니다. 턴을 정말 종료하려면 한 번 더 누르세요."
                return
            self.end_turn_warning_armed = False
            self.end_player_turn("플레이어가 턴을 종료했습니다.")
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

        if click.clicked_unit and click.clicked_unit.team == Team.PLAYER:
            self.selected_unit_id = click.clicked_unit.id
            self.action_mode = ActionMode.MOVE
            self.end_turn_warning_armed = False
            self.last_feedback = "초록은 이동, 붉은 테두리는 공격 사거리입니다. 공격이나 스킬은 오른쪽 버튼을 누르세요."
            self.add_effect("select", click.clicked_unit.position, duration=0.25)
            return

        unit = self.selected_unit
        if unit is None:
            self.last_feedback = "먼저 청팀 유닛을 선택하세요."
            return

        if self.board.is_blocked(click.board_tile):
            self.last_feedback = "바위 지형은 통과할 수 없습니다. 다른 칸을 선택하세요."
            return

        if self.action_mode == ActionMode.MOVE and click.board_tile in self.valid_move_tiles:
            start = unit.position
            unit.move(click.board_tile)
            self.add_effect("move", start, duration=0.30)
            self.add_effect("move", click.board_tile, duration=0.45)
            self.log(f"{unit.name} 이동: {start} -> {click.board_tile}")
            self.last_feedback = f"{unit.name} 이동 완료"
            self.end_player_turn()
            return

        if self.action_mode == ActionMode.ATTACK:
            if click.clicked_unit and click.clicked_unit.position in self.valid_attack_tiles:
                self._resolve_basic_attack(unit, click.clicked_unit)
            else:
                self.last_feedback = "공격은 붉게 채워진 적 칸을 클릭해야 실제로 실행됩니다."
            return

        if self.action_mode == ActionMode.SKILL:
            if click.board_tile in self.valid_skill_tiles:
                self._resolve_skill(unit, click.board_tile)
            else:
                self.last_feedback = "스킬은 노란 칸을 클릭해야 실제로 실행됩니다."

    def _click_context(self, mouse_pos: tuple[int, int]) -> ClickContext:
        from game.renderer import board_tile_at_pixel

        tile = board_tile_at_pixel(mouse_pos)
        if tile is None:
            return ClickContext()
        return ClickContext(tile, self.unit_at(tile))

    @property
    def selected_unit(self) -> Unit | None:
        if self.selected_unit_id is None:
            return None
        return next((unit for unit in self.units if unit.id == self.selected_unit_id and unit.is_alive()), None)

    @property
    def living_units(self) -> list[Unit]:
        return [unit for unit in self.units if unit.is_alive()]

    @property
    def valid_move_tiles(self) -> list[Position]:
        unit = self.selected_unit
        return unit.basic_move_targets(self.board, self.living_units) if unit else []

    @property
    def attack_preview_tiles(self) -> list[Position]:
        unit = self.selected_unit
        return unit.attack_preview_tiles(self.board) if unit else []

    @property
    def valid_attack_tiles(self) -> list[Position]:
        unit = self.selected_unit
        return unit.attack_targets(self.board, self.living_units) if unit else []

    @property
    def valid_skill_tiles(self) -> list[Position]:
        unit = self.selected_unit
        return unit.skill_targets(self.board, self.living_units) if unit else []

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
            self.end_ai_turn("AI가 행동하지 않고 턴을 넘겼습니다.")
            return

        unit = self.get_unit(action.unit_id)
        if unit is None:
            self.end_ai_turn("AI 유닛을 찾지 못했습니다.")
            return

        if action.action_type == "move":
            start = unit.position
            unit.move(action.target)
            self.add_effect("move", start, duration=0.30)
            self.add_effect("move", action.target, duration=0.45)
            self.log(f"{unit.name} 이동: {start} -> {action.target}")
            self.last_feedback = f"{unit.name} 이동 완료"
        elif action.action_type == "attack":
            target = self.unit_at(action.target)
            if target:
                self._resolve_basic_attack(unit, target, auto_end=False)
        elif action.action_type == "skill":
            self._resolve_skill(unit, action.target, auto_end=False)

        if self.state != GameState.GAME_OVER:
            self.end_ai_turn()

    def _resolve_basic_attack(self, attacker: Unit, target: Unit, auto_end: bool = True) -> None:
        self.add_effect("slash", target.position, duration=0.30)
        damage = attacker.attack(target)
        self._show_damage_feedback(target, damage)
        if damage > 0:
            self.log(f"{attacker.name} 공격: {target.name}에게 {damage} 피해")
            self.last_feedback = f"공격 적중: {target.name} 체력 {target.hp}/{target.max_hp}"
        else:
            self.log(f"{attacker.name} 공격: {target.name}의 보호막에 막혔습니다")
            self.last_feedback = "공격이 보호막에 막혔습니다."
        self._cleanup_dead_units()
        if self._check_victory():
            return
        if auto_end:
            if attacker.team == Team.PLAYER:
                self.end_player_turn()
            else:
                self.end_ai_turn()

    def _resolve_skill(self, unit: Unit, target_tile: Position, auto_end: bool = True) -> None:
        unit.use_skill()
        skill = SKILLS[unit.unit_type]
        self.add_effect("skill_cast", unit.position, duration=0.35)
        if unit.unit_type == UnitType.KING:
            unit.shield_turns = 1
            self.add_effect("shield", unit.position, duration=0.70)
            self.add_effect("text", unit.position, duration=0.75, text="보호막", color=(255, 226, 110))
            self.log(f"{unit.name} 스킬 사용: {skill.name}. 다음 아군 턴 전까지 받는 피해가 1 감소합니다.")
            self.last_feedback = f"{unit.name}에게 보호막이 생겼습니다."
        elif unit.unit_type == UnitType.SWORDMAN:
            self._resolve_charge(unit, target_tile)
        elif unit.unit_type == UnitType.ARCHER:
            hits = self._resolve_piercing_shot(unit, target_tile)
            self.log(f"{unit.name} 스킬 사용: {skill.name}. 적 {hits}기에게 적중했습니다.")
            self.last_feedback = f"관통 사격 적중 수: {hits}"
        elif unit.unit_type == UnitType.MAGE:
            hits = self._resolve_flame_burst(unit, target_tile)
            self.log(f"{unit.name} 스킬 사용: {skill.name}. 적 {hits}기를 불태웠습니다.")
            self.last_feedback = f"화염 폭발 적중 수: {hits}"

        self._cleanup_dead_units()
        if self._check_victory():
            return

        if auto_end:
            if unit.team == Team.PLAYER:
                self.end_player_turn()
            else:
                self.end_ai_turn()

    def _resolve_charge(self, unit: Unit, target_tile: Position) -> None:
        start = unit.position
        dx = 0 if target_tile[0] == unit.position[0] else (1 if target_tile[0] > unit.position[0] else -1)
        dy = 0 if target_tile[1] == unit.position[1] else (1 if target_tile[1] > unit.position[1] else -1)
        target_unit = self.unit_at(target_tile)
        if target_unit and target_unit.team != unit.team:
            landing = (target_tile[0] - dx, target_tile[1] - dy)
            if landing != unit.position and self.unit_at(landing) is None and self.board.is_walkable(landing):
                unit.move(landing)
                self.add_effect("dash", landing, duration=0.45, origin=start)
            damage = unit.attack(target_unit)
            self.add_effect("slash", target_unit.position, duration=0.35)
            self._show_damage_feedback(target_unit, damage)
            if damage > 0:
                self.log(f"{unit.name} 돌진 공격: {target_unit.name}에게 {damage} 피해")
                self.last_feedback = f"돌진 적중: {target_unit.name} 체력 {target_unit.hp}/{target_unit.max_hp}"
            else:
                self.log(f"{unit.name} 돌진 공격: {target_unit.name}의 보호막에 막혔습니다")
                self.last_feedback = "돌진 공격이 보호막에 막혔습니다."
        else:
            unit.move(target_tile)
            self.add_effect("dash", target_tile, duration=0.45, origin=start)
            self.log(f"{unit.name} 돌진 이동: {start} -> {target_tile}")
            self.last_feedback = f"{unit.name} 돌진 이동 완료"

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
                damage = target.take_damage(1)
                self._show_damage_feedback(target, damage)
                hits += 1
        self.add_effect("beam", target_tile, duration=0.32, origin=unit.position, path=path)
        return hits

    def _resolve_flame_burst(self, unit: Unit, target_tile: Position) -> int:
        hits = 0
        affected_tiles = [tile for tile in self.board.tiles_in_square(target_tile, 1) if not self.board.is_blocked(tile)]
        self.add_effect("burst", target_tile, duration=0.55, tiles=affected_tiles)
        for tile in affected_tiles:
            target = self.unit_at(tile)
            if target and target.team != unit.team:
                damage = target.take_damage(1)
                self._show_damage_feedback(target, damage)
                hits += 1
        return hits

    def _show_damage_feedback(self, target: Unit, damage: int) -> None:
        if damage > 0:
            self.add_effect("attack", target.position, duration=0.45)
            self.add_effect("text", target.position, duration=0.85, text=f"-{damage}", color=(255, 120, 120))
        else:
            self.add_effect("shield", target.position, duration=0.45)
            self.add_effect("text", target.position, duration=0.80, text="막힘", color=(255, 214, 120))

    def end_player_turn(self, reason: str | None = None) -> None:
        if reason:
            self.log(reason)
        self.state = GameState.AI_TURN
        self.start_turn(Team.AI)

    def end_ai_turn(self, reason: str | None = None) -> None:
        if reason:
            self.log(reason)
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

    def scroll_logs(self, delta: int) -> None:
        self.log_scroll = max(0, min(self.max_log_scroll(), self.log_scroll + delta))

    def max_log_scroll(self, visible_lines: int = 4) -> int:
        return max(0, len(self.logs) - visible_lines)

    def visible_logs(self, visible_lines: int = 4) -> list[str]:
        end = len(self.logs) - self.log_scroll
        start = max(0, end - visible_lines)
        return self.logs[start:end]

    def mode_help_text(self) -> str:
        if self.selected_unit is None:
            return "먼저 청팀 유닛을 클릭한 뒤 A/M/Q를 선택하세요."
        if self.action_mode == ActionMode.MOVE:
            return "초록은 이동, 붉은 테두리는 공격 사거리입니다. 이동할 칸을 클릭하세요."
        if self.action_mode == ActionMode.ATTACK:
            return "공격 선택됨. 붉게 채워진 적 칸을 클릭해야 실제로 공격합니다."
        return "스킬 선택됨. 노란 칸의 대상을 클릭해야 실제로 스킬이 나갑니다."

    def step_guide_text(self) -> str:
        if self.selected_unit is None:
            return "1. 청팀 유닛 선택 -> 2. A/M/Q 선택 -> 3. 보드에서 대상 클릭"
        if self.action_mode == ActionMode.MOVE:
            return "현재 단계: 3 / 초록 이동 칸과 붉은 공격 사거리를 확인하세요"
        if self.action_mode == ActionMode.ATTACK:
            return "현재 단계: 3 / 붉게 채워진 적 칸을 클릭하세요"
        return "현재 단계: 3 / 노란 스킬 대상을 클릭하세요"

    def turn_status_text(self) -> str:
        if self.state == GameState.PLAYER_TURN:
            return "당신의 차례입니다"
        if self.state == GameState.AI_TURN:
            remain = max(0.0, self.ai_delay - self.ai_timer)
            return f"홍팀 행동 중... {remain:.1f}초"
        if self.state == GameState.GAME_OVER and self.winner is not None:
            return f"전투 종료: {TEAM_NAMES[self.winner]} 승리"
        return "대기 중"

    def action_summary_text(self) -> str:
        unit = self.selected_unit
        if unit is None:
            return "선택된 유닛 없음"
        if self.action_mode == ActionMode.MOVE:
            return f"이동 {len(self.valid_move_tiles)}칸 / 공격 사거리 {len(self.attack_preview_tiles)}칸"
        if self.action_mode == ActionMode.ATTACK:
            return f"공격 사거리 {len(self.attack_preview_tiles)}칸 / 명중 가능 {len(self.valid_attack_tiles)}칸"
        return f"스킬 가능 {len(self.valid_skill_tiles)}칸"

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

    def _check_victory(self) -> bool:
        player_king_alive = any(unit.unit_type == UnitType.KING and unit.team == Team.PLAYER and unit.is_alive() for unit in self.units)
        ai_king_alive = any(unit.unit_type == UnitType.KING and unit.team == Team.AI and unit.is_alive() for unit in self.units)
        if player_king_alive and ai_king_alive:
            return False
        self.winner = Team.PLAYER if player_king_alive else Team.AI
        self.state = GameState.GAME_OVER
        self.log(f"게임 종료. {TEAM_NAMES[self.winner]} 승리")
        self.last_feedback = f"{TEAM_NAMES[self.winner]} 승리"
        return True

    def selected_skill(self) -> str:
        unit = self.selected_unit
        if unit is None:
            return "-"
        skill = SKILLS[unit.unit_type]
        current = unit.cooldowns.get("skill", 0)
        return f"{skill.name} (재사용 {current}/{skill.cooldown})"

    def unit_summary(self) -> list[str]:
        unit = self.selected_unit
        if unit is None:
            return ["선택된 유닛이 없습니다."]
        skill = SKILLS[unit.unit_type]
        return [
            unit.name,
            f"유형: {UNIT_DISPLAY_NAMES[unit.unit_type]}",
            f"체력: {unit.hp}/{unit.max_hp}",
            f"위치: {unit.position}",
            f"기본 공격 범위: {len(unit.attack_preview_tiles(self.board))}칸",
            f"스킬: {skill.name}",
            f"재사용 대기: {unit.cooldowns.get('skill', 0)}",
        ]
