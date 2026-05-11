from __future__ import annotations

from pathlib import Path

import pygame

from game.constants import (
    ACTION_PANEL_RECT,
    ATTACK_BUTTON,
    ATTACK_HIGHLIGHT,
    BACKGROUND_COLOR,
    BLUE_TEAM,
    BOARD_ORIGIN,
    BOARD_PIXEL_SIZE,
    BUTTON_ACTIVE,
    BUTTON_COLOR,
    BUTTON_DISABLED,
    END_TURN_BUTTON,
    GRID_DARK,
    GRID_LIGHT,
    HP_BAR_BG,
    HP_BAR_FILL,
    HP_BAR_LOW,
    INFO_PANEL_RECT,
    LOG_PANEL_BG,
    LOG_PANEL_RECT,
    LOG_SCROLLBAR_BG,
    LOG_SCROLLBAR_FG,
    MOVE_BUTTON,
    MOVE_HIGHLIGHT,
    OBSTACLE_COLOR,
    OBSTACLE_EDGE,
    PANEL_BORDER,
    PANEL_COLOR,
    RED_TEAM,
    RIVER_TILE,
    RIVER_TILE_DARK,
    SELECT_HIGHLIGHT,
    SIDEBAR_HEIGHT,
    SIDEBAR_WIDTH,
    SIDEBAR_X,
    SIDEBAR_Y,
    SKILL_BUTTON,
    SKILL_HIGHLIGHT,
    SUBTEXT_COLOR,
    TEAM_NAMES,
    TEXT_COLOR,
    TILE_SIZE,
    UNIT_DISPLAY_NAMES,
    UNIT_GLYPHS,
    ActionMode,
    Team,
    UnitType,
)

ACTION_BUTTONS = {
    ActionMode.MOVE: pygame.Rect(*MOVE_BUTTON),
    ActionMode.ATTACK: pygame.Rect(*ATTACK_BUTTON),
    ActionMode.SKILL: pygame.Rect(*SKILL_BUTTON),
}


def board_tile_at_pixel(mouse_pos: tuple[int, int]) -> tuple[int, int] | None:
    x, y = mouse_pos
    board_x, board_y = BOARD_ORIGIN
    if not (board_x <= x < board_x + BOARD_PIXEL_SIZE and board_y <= y < board_y + BOARD_PIXEL_SIZE):
        return None
    return ((x - board_x) // TILE_SIZE, (y - board_y) // TILE_SIZE)


class Renderer:
    def __init__(self, screen: pygame.Surface, project_root: Path) -> None:
        self.screen = screen
        self.project_root = project_root
        self.sprite_dir = project_root / "assets" / "sprites"
        self.ui_dir = project_root / "assets" / "ui"
        self.font = pygame.font.SysFont("malgungothic", 15)
        self.small_font = pygame.font.SysFont("malgungothic", 13)
        self.tiny_font = pygame.font.SysFont("malgungothic", 12)
        self.title_font = pygame.font.SysFont("malgungothic", 20, bold=True)
        self.big_font = pygame.font.SysFont("malgungothic", 26, bold=True)
        self.log_emphasis_font = pygame.font.SysFont("malgungothic", 13, bold=True)
        self._ensure_assets()
        self.board_surface = pygame.transform.scale(pygame.image.load(self.ui_dir / "board.png").convert(), (BOARD_PIXEL_SIZE, BOARD_PIXEL_SIZE))
        self.overlay_move = pygame.transform.scale(pygame.image.load(self.ui_dir / "tile_move.png").convert_alpha(), (TILE_SIZE, TILE_SIZE))
        self.overlay_attack = pygame.transform.scale(pygame.image.load(self.ui_dir / "tile_attack.png").convert_alpha(), (TILE_SIZE, TILE_SIZE))
        self.overlay_skill = pygame.transform.scale(pygame.image.load(self.ui_dir / "tile_skill.png").convert_alpha(), (TILE_SIZE, TILE_SIZE))
        self.overlay_attack_preview = self._make_outline_overlay((233, 92, 92, 120), inset=16, width=3)
        self.sprites = self._load_unit_sprites()
        self.action_icons = {
            ActionMode.MOVE: pygame.image.load(self.ui_dir / "icon_move.png").convert_alpha(),
            ActionMode.ATTACK: pygame.image.load(self.ui_dir / "icon_attack.png").convert_alpha(),
            ActionMode.SKILL: pygame.image.load(self.ui_dir / "icon_skill.png").convert_alpha(),
            "end": pygame.image.load(self.ui_dir / "icon_end.png").convert_alpha(),
        }

    def draw(self, game) -> None:
        self.screen.fill(BACKGROUND_COLOR)
        self._draw_board(game)
        self._draw_log_panel(game)
        self._draw_sidebar_shell(game)
        self._draw_info_panel(game)
        self._draw_action_panel(game)

    def _draw_board(self, game) -> None:
        self.screen.blit(self.board_surface, BOARD_ORIGIN)
        self._draw_obstacles(game)
        self._draw_overlays(game)
        self._draw_effects(game)
        for unit in game.living_units:
            self._draw_unit(unit)

    def _draw_sidebar_shell(self, game) -> None:
        sidebar = pygame.Rect(SIDEBAR_X, SIDEBAR_Y, SIDEBAR_WIDTH, SIDEBAR_HEIGHT)
        pygame.draw.rect(self.screen, PANEL_COLOR, sidebar, border_radius=16)
        pygame.draw.rect(self.screen, PANEL_BORDER, sidebar, width=2, border_radius=16)
        self._draw_text(self.title_font, f"{game.turn_count} 턴", TEXT_COLOR, (SIDEBAR_X + 20, SIDEBAR_Y + 18))
        turn_color = BLUE_TEAM if game.current_turn == Team.PLAYER else RED_TEAM
        self._draw_text(self.font, f"현재 차례: {TEAM_NAMES[game.current_turn]} 진영", turn_color, (SIDEBAR_X + 20, SIDEBAR_Y + 50))
        self._draw_text(self.small_font, game.turn_status_text(), SUBTEXT_COLOR, (SIDEBAR_X + 20, SIDEBAR_Y + 74))
        self._draw_text(self.small_font, game.step_guide_text(), (190, 204, 230), (SIDEBAR_X + 20, SIDEBAR_Y + 96))

    def _draw_info_panel(self, game) -> None:
        panel = pygame.Rect(*INFO_PANEL_RECT)
        self._draw_card(panel)
        self._draw_text(self.font, "유닛 정보", TEXT_COLOR, (panel.x + 14, panel.y + 10))

        focused = game.focused_unit
        if focused is None:
            self._draw_text(self.small_font, "아군이나 적 유닛을 클릭해 정보를 확인하세요.", SUBTEXT_COLOR, (panel.x + 18, panel.y + 42))
            return

        portrait_rect = pygame.Rect(panel.x + 18, panel.y + 44, 108, 142)
        detail_rect = pygame.Rect(panel.x + 140, panel.y + 44, panel.width - 158, 146)
        team_color = BLUE_TEAM if focused.team == Team.PLAYER else RED_TEAM

        pygame.draw.rect(self.screen, (29, 37, 55), portrait_rect, border_radius=14)
        pygame.draw.rect(self.screen, team_color, portrait_rect, width=2, border_radius=14)
        portrait = pygame.transform.scale(self.sprites[(focused.unit_type, focused.team)], (80, 80))
        self.screen.blit(portrait, portrait.get_rect(center=(portrait_rect.centerx, portrait_rect.y + 52)))
        self._draw_centered_text(self.small_font, TEAM_NAMES[focused.team], team_color, pygame.Rect(portrait_rect.x, portrait_rect.bottom - 32, portrait_rect.width, 16))
        self._draw_centered_text(self.small_font, UNIT_DISPLAY_NAMES[focused.unit_type], TEXT_COLOR, pygame.Rect(portrait_rect.x, portrait_rect.bottom - 16, portrait_rect.width, 16))

        self._draw_text(self.title_font, focused.name, TEXT_COLOR, (detail_rect.x, detail_rect.y))
        self._draw_text(self.small_font, f"병종 {UNIT_DISPLAY_NAMES[focused.unit_type]}", SUBTEXT_COLOR, (detail_rect.x, detail_rect.y + 28))
        self._draw_hp_meter(detail_rect.x, detail_rect.y + 54, detail_rect.width - 10, 18, focused.hp, focused.max_hp)
        self._draw_text(self.small_font, f"체력 {focused.hp}/{focused.max_hp}", TEXT_COLOR, (detail_rect.x, detail_rect.y + 80))

        chip_y = detail_rect.y + 104
        chip_gap = 10
        chip_w = (detail_rect.width - chip_gap * 2) // 3
        self._draw_stat_chip(pygame.Rect(detail_rect.x, chip_y, chip_w, 34), "공격력", str(focused.attack_power()))
        self._draw_stat_chip(pygame.Rect(detail_rect.x + chip_w + chip_gap, chip_y, chip_w, 34), "공격 범위", str(len(focused.attack_preview_tiles(game.board))))
        shield_text = f"{focused.shield_turns}턴" if focused.shield_turns > 0 else "없음"
        self._draw_stat_chip(pygame.Rect(detail_rect.x + (chip_w + chip_gap) * 2, chip_y, chip_w, 34), "보호막", shield_text)

        skill_rect = pygame.Rect(panel.x + 18, panel.y + 202, panel.width - 36, 50)
        pygame.draw.rect(self.screen, (35, 43, 63), skill_rect, border_radius=12)
        pygame.draw.rect(self.screen, PANEL_BORDER, skill_rect, width=1, border_radius=12)
        self._draw_text(self.tiny_font, "스킬", SUBTEXT_COLOR, (skill_rect.x + 12, skill_rect.y + 7))
        self._draw_text(self.small_font, game.selected_skill(), TEXT_COLOR, (skill_rect.x + 12, skill_rect.y + 23))

    def _draw_stat_chip(self, rect: pygame.Rect, label: str, value: str) -> None:
        pygame.draw.rect(self.screen, (35, 43, 63), rect, border_radius=10)
        pygame.draw.rect(self.screen, PANEL_BORDER, rect, width=1, border_radius=10)
        self._draw_text(self.tiny_font, label, SUBTEXT_COLOR, (rect.x + 8, rect.y + 6))
        self._draw_text(self.tiny_font, value, TEXT_COLOR, (rect.x + 8, rect.y + 18))

    def _draw_action_panel(self, game) -> None:
        panel = pygame.Rect(*ACTION_PANEL_RECT)
        self._draw_card(panel)
        self._draw_text(self.font, "행동 바", TEXT_COLOR, (panel.x + 14, panel.y + 10))
        self._draw_text(self.small_font, game.action_summary_text(), SUBTEXT_COLOR, (panel.x + 90, panel.y + 12))

        labels = {ActionMode.MOVE: "이동", ActionMode.ATTACK: "공격", ActionMode.SKILL: "스킬"}
        for mode in (ActionMode.MOVE, ActionMode.ATTACK, ActionMode.SKILL):
            rect = ACTION_BUTTONS[mode]
            active = game.action_mode == mode
            enabled = game.selected_unit is not None
            color = BUTTON_ACTIVE if active and enabled else BUTTON_COLOR if enabled else BUTTON_DISABLED
            pygame.draw.rect(self.screen, color, rect, border_radius=10)
            pygame.draw.rect(self.screen, PANEL_BORDER, rect, width=2, border_radius=10)
            self.screen.blit(self.action_icons[mode], (rect.x + 8, rect.y + 4))
            self._draw_text(self.font, labels[mode], TEXT_COLOR, (rect.x + 36, rect.y + 9))

        end_rect = pygame.Rect(*END_TURN_BUTTON)
        pygame.draw.rect(self.screen, BUTTON_COLOR, end_rect, border_radius=10)
        pygame.draw.rect(self.screen, PANEL_BORDER, end_rect, width=2, border_radius=10)
        self.screen.blit(self.action_icons["end"], (end_rect.x + 8, end_rect.y + 4))
        self._draw_text(self.font, "턴 종료", TEXT_COLOR, (end_rect.x + 36, end_rect.y + 9))

        hint_rect = pygame.Rect(panel.x + 16, panel.y + 88, panel.width - 32, 18)
        self._draw_single_line_fit(hint_rect, self.tiny_font, game.last_feedback, SUBTEXT_COLOR)

    def _draw_log_panel(self, game) -> None:
        panel = pygame.Rect(*LOG_PANEL_RECT)
        self._draw_card(panel)
        self._draw_text(self.font, "전투 기록", TEXT_COLOR, (panel.x + 12, panel.y + 10))
        self._draw_text(self.tiny_font, "휠", (132, 144, 170), (panel.right - 20, panel.y + 12))

        inner = pygame.Rect(panel.x + 10, panel.y + 36, panel.width - 24, panel.height - 46)
        line_height = 14
        visible_lines = max(1, inner.height // line_height)
        segments = self._build_log_segments(game.logs, inner.width - 8)
        total_segments = len(segments)
        max_scroll = max(0, total_segments - visible_lines)
        scroll = max(0, min(game.log_scroll, max_scroll))
        start = max(0, total_segments - visible_lines - scroll)
        visible_segments = segments[start : start + visible_lines]

        y = inner.y
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(inner)
        for text, emphasized in visible_segments:
            font = self.log_emphasis_font if emphasized else self.small_font
            color = TEXT_COLOR if emphasized else SUBTEXT_COLOR
            self._draw_text(font, text, color, (inner.x, y))
            y += line_height
            if y > inner.bottom - 2:
                break
        self.screen.set_clip(prev_clip)
        self._draw_scrollbar(game, panel, visible_lines, total_segments)

    def _draw_card(self, rect: pygame.Rect) -> None:
        pygame.draw.rect(self.screen, LOG_PANEL_BG, rect, border_radius=12)
        pygame.draw.rect(self.screen, PANEL_BORDER, rect, width=2, border_radius=12)

    def _draw_obstacles(self, game) -> None:
        for tile in game.board.blocked_tiles:
            px = BOARD_ORIGIN[0] + tile[0] * TILE_SIZE
            py = BOARD_ORIGIN[1] + tile[1] * TILE_SIZE
            shape = pygame.Rect(px + 8, py + 8, TILE_SIZE - 16, TILE_SIZE - 16)
            if getattr(game, "map_name", "") == "river":
                pygame.draw.rect(self.screen, RIVER_TILE, shape, border_radius=10)
                pygame.draw.rect(self.screen, RIVER_TILE_DARK, shape, width=2, border_radius=10)
                pygame.draw.arc(self.screen, (175, 220, 255), (shape.x + 6, shape.y + 8, 18, 10), 0.1, 3.0, 2)
                pygame.draw.arc(self.screen, (175, 220, 255), (shape.x + 20, shape.y + 18, 18, 10), 0.1, 3.0, 2)
                pygame.draw.arc(self.screen, (175, 220, 255), (shape.x + 10, shape.y + 28, 18, 10), 0.1, 3.0, 2)
            else:
                pygame.draw.rect(self.screen, OBSTACLE_COLOR, shape, border_radius=10)
                pygame.draw.rect(self.screen, OBSTACLE_EDGE, shape, width=2, border_radius=10)
                pygame.draw.line(self.screen, OBSTACLE_EDGE, (shape.x + 10, shape.y + 14), (shape.right - 12, shape.bottom - 12), 2)
                pygame.draw.line(self.screen, (60, 68, 84), (shape.centerx, shape.y + 10), (shape.centerx - 10, shape.bottom - 10), 2)

    def _draw_overlays(self, game) -> None:
        if game.focused_unit is not None:
            self._blit_tile_overlay(game.focused_unit.position, self._make_outline_overlay((255, 255, 255, 110), inset=12, width=2))
        if game.selected_unit is None:
            return
        self._blit_tile_overlay(game.selected_unit.position, self._make_overlay(SELECT_HIGHLIGHT))
        for tile in game.attack_preview_tiles:
            self._blit_tile_overlay(tile, self.overlay_attack_preview)
        tile_map = {
            ActionMode.MOVE: game.valid_move_tiles,
            ActionMode.ATTACK: game.valid_attack_tiles,
            ActionMode.SKILL: game.valid_skill_tiles,
        }
        overlay_map = {
            ActionMode.MOVE: self.overlay_move,
            ActionMode.ATTACK: self.overlay_attack,
            ActionMode.SKILL: self.overlay_skill,
        }
        for tile in tile_map[game.action_mode]:
            self._blit_tile_overlay(tile, overlay_map[game.action_mode])

    def _draw_effects(self, game) -> None:
        for effect in getattr(game, "effects", []):
            effect_type = effect["type"]
            tile = effect["position"]
            timer = float(effect["timer"])
            max_timer = float(effect.get("max_timer", timer))
            progress = 1.0 - (timer / max_timer if max_timer > 0 else 1.0)
            px = BOARD_ORIGIN[0] + tile[0] * TILE_SIZE
            py = BOARD_ORIGIN[1] + tile[1] * TILE_SIZE
            center = (px + TILE_SIZE // 2, py + TILE_SIZE // 2)
            alpha = int(255 * max(0.0, min(1.0, timer / max_timer if max_timer else 0.0)))
            if effect_type == "text":
                self._draw_floating_text(effect, center, alpha, progress)
                continue
            if effect_type == "beam":
                self._draw_beam(effect, alpha)
                continue
            overlay = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            if effect_type == "move":
                pygame.draw.rect(overlay, (100, 240, 180, alpha), (10, 10, TILE_SIZE - 20, TILE_SIZE - 20), width=4, border_radius=10)
            elif effect_type == "attack":
                pygame.draw.circle(overlay, (255, 90, 90, alpha), (TILE_SIZE // 2, TILE_SIZE // 2), int(16 + 8 * progress), width=4)
            elif effect_type == "slash":
                pygame.draw.line(overlay, (255, 180, 180, alpha), (14, TILE_SIZE - 14), (TILE_SIZE - 14, 14), 4)
                pygame.draw.line(overlay, (255, 110, 110, alpha), (18, TILE_SIZE - 12), (TILE_SIZE - 12, 18), 2)
            elif effect_type == "skill_cast":
                pygame.draw.circle(overlay, (255, 214, 90, alpha), (TILE_SIZE // 2, TILE_SIZE // 2), int(12 + 12 * progress), width=3)
            elif effect_type == "shield":
                pygame.draw.circle(overlay, (255, 228, 120, alpha), (TILE_SIZE // 2, TILE_SIZE // 2), int(18 + 6 * progress), width=4)
            elif effect_type == "select":
                pygame.draw.rect(overlay, (255, 255, 255, alpha), (8, 8, TILE_SIZE - 16, TILE_SIZE - 16), width=3, border_radius=10)
            elif effect_type == "dash":
                self._draw_dash(effect.get("origin", tile), tile, alpha)
            elif effect_type == "burst":
                self._draw_burst(effect, alpha)
            self.screen.blit(overlay, (px, py))

    def _draw_floating_text(self, effect: dict[str, object], center: tuple[int, int], alpha: int, progress: float) -> None:
        surface = self.big_font.render(str(effect.get("text", "")), True, tuple(effect.get("color", (255, 255, 255))))
        surface.set_alpha(alpha)
        self.screen.blit(surface, surface.get_rect(center=(center[0], center[1] - int(16 * progress))))

    def _draw_beam(self, effect: dict[str, object], alpha: int) -> None:
        path = effect.get("path", [])
        origin = effect.get("origin")
        if not origin or not path:
            return
        beam_surface = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        points = [self._tile_center(origin)] + [self._tile_center(tile) for tile in path]
        pygame.draw.lines(beam_surface, (255, 214, 90, alpha), False, points, 6)
        pygame.draw.lines(beam_surface, (255, 245, 180, min(255, alpha + 20)), False, points, 2)
        self.screen.blit(beam_surface, (0, 0))

    def _draw_dash(self, origin: tuple[int, int], tile: tuple[int, int], alpha: int) -> None:
        dash_surface = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        pygame.draw.line(dash_surface, (120, 255, 210, alpha), self._tile_center(origin), self._tile_center(tile), 8)
        self.screen.blit(dash_surface, (0, 0))

    def _draw_burst(self, effect: dict[str, object], alpha: int) -> None:
        burst_surface = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        center = self._tile_center(effect["position"])
        pygame.draw.circle(burst_surface, (255, 160, 70, alpha), center, int(TILE_SIZE * 0.8), width=6)
        pygame.draw.circle(burst_surface, (255, 220, 120, alpha // 2), center, int(TILE_SIZE * 1.15), width=3)
        for tile in effect.get("tiles", []):
            px = BOARD_ORIGIN[0] + tile[0] * TILE_SIZE
            py = BOARD_ORIGIN[1] + tile[1] * TILE_SIZE
            pygame.draw.rect(burst_surface, (255, 130, 60, alpha // 3), (px + 6, py + 6, TILE_SIZE - 12, TILE_SIZE - 12), border_radius=8)
        self.screen.blit(burst_surface, (0, 0))

    def _draw_unit(self, unit) -> None:
        sprite = self.sprites[(unit.unit_type, unit.team)]
        px = BOARD_ORIGIN[0] + unit.position[0] * TILE_SIZE
        py = BOARD_ORIGIN[1] + unit.position[1] * TILE_SIZE
        self.screen.blit(sprite, (px, py))
        self._draw_hp_bar(px + 6, py + TILE_SIZE - 14, TILE_SIZE - 12, 8, unit.hp, unit.max_hp)
        hp_text = self.tiny_font.render(str(unit.hp), True, TEXT_COLOR)
        self.screen.blit(hp_text, hp_text.get_rect(center=(px + TILE_SIZE // 2, py + TILE_SIZE - 20)))
        if unit.shield_turns > 0:
            badge = pygame.Rect(px + TILE_SIZE - 24, py + 2, 20, 20)
            pygame.draw.ellipse(self.screen, (76, 184, 255), badge)
            pygame.draw.ellipse(self.screen, (190, 236, 255), badge, width=2)
            shield_surface = self.tiny_font.render(str(unit.shield_turns), True, (12, 26, 44))
            self.screen.blit(shield_surface, shield_surface.get_rect(center=badge.center))

    def _tile_center(self, tile: tuple[int, int]) -> tuple[int, int]:
        return (BOARD_ORIGIN[0] + tile[0] * TILE_SIZE + TILE_SIZE // 2, BOARD_ORIGIN[1] + tile[1] * TILE_SIZE + TILE_SIZE // 2)

    def _draw_hp_bar(self, x: int, y: int, width: int, height: int, hp: int, max_hp: int) -> None:
        pygame.draw.rect(self.screen, HP_BAR_BG, pygame.Rect(x, y, width, height), border_radius=4)
        ratio = 0 if max_hp <= 0 else hp / max_hp
        fill_width = max(0, int(width * ratio))
        if fill_width > 0:
            color = HP_BAR_FILL if ratio > 0.4 else HP_BAR_LOW
            pygame.draw.rect(self.screen, color, pygame.Rect(x, y, fill_width, height), border_radius=4)
        pygame.draw.rect(self.screen, PANEL_BORDER, pygame.Rect(x, y, width, height), width=1, border_radius=4)

    def _draw_hp_meter(self, x: int, y: int, width: int, height: int, hp: int, max_hp: int) -> None:
        self._draw_hp_bar(x, y, width, height, hp, max_hp)
        ratio = 0 if max_hp <= 0 else hp / max_hp
        color = HP_BAR_FILL if ratio > 0.4 else HP_BAR_LOW
        pygame.draw.circle(self.screen, color, (x + width + 8, y + height // 2), 5)

    def _draw_single_line_fit(self, rect: pygame.Rect, font: pygame.font.Font, text: str, color: tuple[int, int, int]) -> None:
        clipped = text
        while clipped and font.size(clipped)[0] > rect.width:
            clipped = clipped[:-4] + "..."
        self._draw_text(font, clipped, color, (rect.x, rect.y))

    def _draw_scrollbar(self, game, panel: pygame.Rect, visible_lines: int, total_lines: int) -> None:
        if total_lines <= visible_lines:
            return
        track = pygame.Rect(panel.right - 10, panel.y + 36, 4, panel.height - 46)
        pygame.draw.rect(self.screen, LOG_SCROLLBAR_BG, track, border_radius=4)
        thumb_height = max(18, int(track.height * (visible_lines / total_lines)))
        max_scroll = max(1, total_lines - visible_lines)
        scroll = max(0, min(game.log_scroll, max_scroll))
        thumb_y = track.y + int((track.height - thumb_height) * (scroll / max_scroll))
        thumb_y = max(track.y, min(thumb_y, track.bottom - thumb_height))
        pygame.draw.rect(self.screen, LOG_SCROLLBAR_FG, pygame.Rect(track.x, thumb_y, track.width, thumb_height), border_radius=4)

    def _build_log_segments(self, logs: list[str], max_width: int) -> list[tuple[str, bool]]:
        segments: list[tuple[str, bool]] = []
        for index, line in enumerate(logs):
            emphasized = index == len(logs) - 1
            font = self.log_emphasis_font if emphasized else self.small_font
            for piece in self._wrap_text_pixels(font, line, max_width):
                segments.append((piece, emphasized))
        return segments

    def _wrap_text_pixels(self, font: pygame.font.Font, text: str, max_width: int) -> list[str]:
        if not text or font.size(text)[0] <= max_width:
            return [text]
        words = text.split(" ")
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _draw_text(self, font: pygame.font.Font, text: str, color: tuple[int, int, int], pos: tuple[int, int]) -> None:
        self.screen.blit(font.render(text, True, color), pos)

    def _draw_centered_text(self, font: pygame.font.Font, text: str, color: tuple[int, int, int], rect: pygame.Rect) -> None:
        surface = font.render(text, True, color)
        self.screen.blit(surface, surface.get_rect(center=rect.center))

    def _blit_tile_overlay(self, tile: tuple[int, int], overlay: pygame.Surface) -> None:
        self.screen.blit(overlay, (BOARD_ORIGIN[0] + tile[0] * TILE_SIZE, BOARD_ORIGIN[1] + tile[1] * TILE_SIZE))

    def _load_unit_sprites(self) -> dict[tuple[UnitType, Team], pygame.Surface]:
        mapping = {
            (UnitType.KING, Team.PLAYER): self.sprite_dir / "king_blue.png",
            (UnitType.KING, Team.AI): self.sprite_dir / "king_red.png",
            (UnitType.SWORDMAN, Team.PLAYER): self.sprite_dir / "swordman_blue.png",
            (UnitType.SWORDMAN, Team.AI): self.sprite_dir / "swordman_red.png",
            (UnitType.ARCHER, Team.PLAYER): self.sprite_dir / "archer_blue.png",
            (UnitType.ARCHER, Team.AI): self.sprite_dir / "archer_red.png",
            (UnitType.MAGE, Team.PLAYER): self.sprite_dir / "mage_blue.png",
            (UnitType.MAGE, Team.AI): self.sprite_dir / "mage_red.png",
            (UnitType.KNIGHT, Team.PLAYER): self.sprite_dir / "knight_blue.png",
            (UnitType.KNIGHT, Team.AI): self.sprite_dir / "knight_red.png",
            (UnitType.BISHOP, Team.PLAYER): self.sprite_dir / "bishop_blue.png",
            (UnitType.BISHOP, Team.AI): self.sprite_dir / "bishop_red.png",
            (UnitType.LANCER, Team.PLAYER): self.sprite_dir / "lancer_blue.png",
            (UnitType.LANCER, Team.AI): self.sprite_dir / "lancer_red.png",
        }
        return {key: pygame.transform.scale(pygame.image.load(path).convert_alpha(), (TILE_SIZE, TILE_SIZE)) for key, path in mapping.items()}

    def _make_overlay(self, color: tuple[int, int, int, int]) -> pygame.Surface:
        surface = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        pygame.draw.rect(surface, color, (6, 6, TILE_SIZE - 12, TILE_SIZE - 12), border_radius=10)
        return surface

    def _make_outline_overlay(self, color: tuple[int, int, int, int], inset: int = 12, width: int = 3) -> pygame.Surface:
        surface = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        pygame.draw.rect(surface, color, (inset, inset, TILE_SIZE - inset * 2, TILE_SIZE - inset * 2), width=width, border_radius=8)
        return surface

    def _ensure_assets(self) -> None:
        self.sprite_dir.mkdir(parents=True, exist_ok=True)
        self.ui_dir.mkdir(parents=True, exist_ok=True)
        board_path = self.ui_dir / "board.png"
        if not board_path.exists():
            surface = pygame.Surface((BOARD_PIXEL_SIZE, BOARD_PIXEL_SIZE))
            for y in range(8):
                for x in range(8):
                    pygame.draw.rect(surface, GRID_LIGHT if (x + y) % 2 == 0 else GRID_DARK, (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))
                    pygame.draw.rect(surface, (18, 22, 34), (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE), width=1)
            pygame.image.save(surface, board_path)
        for name, color in (("tile_move.png", MOVE_HIGHLIGHT), ("tile_attack.png", ATTACK_HIGHLIGHT), ("tile_skill.png", SKILL_HIGHLIGHT)):
            path = self.ui_dir / name
            if not path.exists():
                pygame.image.save(self._make_overlay(color), path)
        sprite_specs = [(f"{unit.name.lower()}_blue.png", BLUE_TEAM, UNIT_GLYPHS[unit]) for unit in UnitType] + [(f"{unit.name.lower()}_red.png", RED_TEAM, UNIT_GLYPHS[unit]) for unit in UnitType]
        for filename, color, glyph in sprite_specs:
            path = self.sprite_dir / filename
            if not path.exists():
                pygame.image.save(self._make_unit_sprite(color, glyph), path)

    def _make_unit_sprite(self, color: tuple[int, int, int], glyph: str) -> pygame.Surface:
        surface = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        pygame.draw.circle(surface, color, (TILE_SIZE // 2, TILE_SIZE // 2), TILE_SIZE // 2 - 6)
        pygame.draw.circle(surface, (240, 244, 255), (TILE_SIZE // 2, TILE_SIZE // 2), TILE_SIZE // 2 - 6, width=2)
        text = self.title_font.render(glyph, True, (12, 18, 28))
        surface.blit(text, text.get_rect(center=(TILE_SIZE // 2, TILE_SIZE // 2)))
        return surface


