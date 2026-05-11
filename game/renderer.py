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
    SCREEN_HEIGHT,
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
    ActionMode,
    GameState,
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
        self.sprite_dir = project_root / 'assets' / 'sprites'
        self.ui_dir = project_root / 'assets' / 'ui'
        self.font = pygame.font.SysFont('malgungothic', 15)
        self.small_font = pygame.font.SysFont('malgungothic', 13)
        self.tiny_font = pygame.font.SysFont('malgungothic', 12)
        self.title_font = pygame.font.SysFont('malgungothic', 20, bold=True)
        self.big_font = pygame.font.SysFont('malgungothic', 26, bold=True)
        self._ensure_assets()
        self.board_surface = pygame.transform.scale(
            pygame.image.load(self.ui_dir / 'board.png').convert(),
            (BOARD_PIXEL_SIZE, BOARD_PIXEL_SIZE),
        )
        self.overlay_move = pygame.transform.scale(
            pygame.image.load(self.ui_dir / 'tile_move.png').convert_alpha(),
            (TILE_SIZE, TILE_SIZE),
        )
        self.overlay_attack = pygame.transform.scale(
            pygame.image.load(self.ui_dir / 'tile_attack.png').convert_alpha(),
            (TILE_SIZE, TILE_SIZE),
        )
        self.overlay_skill = pygame.transform.scale(
            pygame.image.load(self.ui_dir / 'tile_skill.png').convert_alpha(),
            (TILE_SIZE, TILE_SIZE),
        )
        self.overlay_attack_preview = self._make_outline_overlay((233, 92, 92, 120), inset=16, width=3)
        self.sprites = self._load_unit_sprites()

    def draw(self, game) -> None:
        self.screen.fill(BACKGROUND_COLOR)
        self._draw_board(game)
        self._draw_sidebar(game)
        self._draw_bottom_hint()

    def _draw_board(self, game) -> None:
        self.screen.blit(self.board_surface, BOARD_ORIGIN)
        self._draw_obstacles(game)
        self._draw_overlays(game)
        self._draw_effects(game)
        for unit in game.living_units:
            self._draw_unit(unit)

    def _draw_sidebar(self, game) -> None:
        sidebar = pygame.Rect(SIDEBAR_X, SIDEBAR_Y, SIDEBAR_WIDTH, SIDEBAR_HEIGHT)
        pygame.draw.rect(self.screen, PANEL_COLOR, sidebar, border_radius=16)
        pygame.draw.rect(self.screen, PANEL_BORDER, sidebar, width=2, border_radius=16)

        self._draw_text(self.title_font, f'{game.turn_count} 턴', TEXT_COLOR, (SIDEBAR_X + 24, SIDEBAR_Y + 20))
        turn_color = BLUE_TEAM if game.current_turn == Team.PLAYER else RED_TEAM
        self._draw_text(self.font, f'현재 차례: {TEAM_NAMES[game.current_turn]}', turn_color, (SIDEBAR_X + 24, SIDEBAR_Y + 50))
        self._draw_text(self.small_font, game.turn_status_text(), SUBTEXT_COLOR, (SIDEBAR_X + 24, SIDEBAR_Y + 74))
        self._draw_text(self.small_font, game.step_guide_text(), (185, 198, 224), (SIDEBAR_X + 24, SIDEBAR_Y + 96))

        self._draw_end_turn_button(game)
        self._draw_info_panel(game)
        self._draw_action_panel(game)
        self._draw_log_panel(game)

    def _draw_info_panel(self, game) -> None:
        panel = pygame.Rect(*INFO_PANEL_RECT)
        self._draw_card(panel)
        self._draw_text(self.font, '전투 정보', TEXT_COLOR, (panel.x + 14, panel.y + 10))

        left_rect = pygame.Rect(panel.x + 14, panel.y + 40, 262, panel.height - 54)
        right_rect = pygame.Rect(panel.x + 318, panel.y + 40, panel.width - 332, panel.height - 54)
        divider_x = panel.x + 296
        pygame.draw.line(self.screen, PANEL_BORDER, (divider_x, panel.y + 34), (divider_x, panel.bottom - 16), 1)

        self._draw_text(self.font, '선택한 유닛', TEXT_COLOR, (left_rect.x, left_rect.y))
        summary_rect = pygame.Rect(left_rect.x, left_rect.y + 24, left_rect.width, 138)
        summary_lines = game.unit_summary()[:6]
        self._draw_lines_clipped(summary_rect, self.small_font, summary_lines, SUBTEXT_COLOR, line_gap=16)

        if game.selected_unit is not None:
            hp_y = min(summary_rect.bottom + 14, left_rect.bottom - 18)
            self._draw_hp_bar(left_rect.x, hp_y, 220, 8, game.selected_unit.hp, game.selected_unit.max_hp)

        self._draw_text(self.font, '스킬 / 피드백', TEXT_COLOR, (right_rect.x, right_rect.y))
        if game.selected_unit is None:
            skill_lines = [game.last_feedback]
        else:
            skill_lines = [
                game.selected_skill(),
                self._skill_description(game.selected_unit.unit_type),
                game.last_feedback,
            ]
        content_rect = pygame.Rect(right_rect.x, right_rect.y + 24, right_rect.width, right_rect.height - 28)
        self._draw_wrapped_lines(content_rect, self.small_font, skill_lines, SUBTEXT_COLOR, line_gap=16)

    def _draw_action_panel(self, game) -> None:
        panel = pygame.Rect(*ACTION_PANEL_RECT)
        self._draw_card(panel)
        self._draw_text(self.font, '행동 선택', TEXT_COLOR, (panel.x + 14, panel.y + 10))
        self._draw_text(self.small_font, game.action_summary_text(), SUBTEXT_COLOR, (panel.x + 118, panel.y + 12))

        labels = {
            ActionMode.MOVE: '이동 (M)',
            ActionMode.ATTACK: '공격 (A)',
            ActionMode.SKILL: '스킬 (Q)',
        }
        for mode, rect in ACTION_BUTTONS.items():
            active = game.action_mode == mode
            enabled = game.selected_unit is not None
            color = BUTTON_ACTIVE if active and enabled else BUTTON_COLOR if enabled else BUTTON_DISABLED
            pygame.draw.rect(self.screen, color, rect, border_radius=10)
            pygame.draw.rect(self.screen, PANEL_BORDER, rect, width=2, border_radius=10)
            self._draw_centered_text(self.font, labels[mode], TEXT_COLOR, rect)

        helper_rect = pygame.Rect(panel.x + 14, panel.bottom - 24, panel.width - 28, 18)
        helper = '버튼 선택 후 보드에서 대상 칸을 클릭하세요.'
        self._draw_single_line_fit(helper_rect, self.tiny_font, helper, SUBTEXT_COLOR)

    def _draw_log_panel(self, game) -> None:
        panel = pygame.Rect(*LOG_PANEL_RECT)
        self._draw_card(panel)
        self._draw_text(self.font, '전투 기록', TEXT_COLOR, (panel.x + 14, panel.y + 10))
        self._draw_text(self.tiny_font, '휠 스크롤', (132, 144, 170), (panel.right - 62, panel.y + 13))

        inner = pygame.Rect(panel.x + 12, panel.y + 34, panel.width - 30, panel.height - 48)
        y = inner.y
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(inner)
        for line in game.visible_logs(visible_lines=4):
            wrapped = self._wrap_text_pixels(self.small_font, line, inner.width - 12)
            for piece in wrapped[:2]:
                self._draw_text(self.small_font, piece, SUBTEXT_COLOR, (inner.x, y))
                y += 14
                if y > inner.bottom - 2:
                    break
            y += 4
            if y > inner.bottom - 2:
                break
        self.screen.set_clip(prev_clip)
        self._draw_scrollbar(game, panel, visible_lines=4)

    def _draw_end_turn_button(self, game) -> None:
        rect = pygame.Rect(*END_TURN_BUTTON)
        color = BUTTON_COLOR if game.state == GameState.PLAYER_TURN else BUTTON_DISABLED
        pygame.draw.rect(self.screen, color, rect, border_radius=10)
        pygame.draw.rect(self.screen, PANEL_BORDER, rect, width=2, border_radius=10)
        self._draw_centered_text(self.small_font, '턴 종료', TEXT_COLOR, rect)

    def _draw_bottom_hint(self) -> None:
        hint = '유닛 선택 -> 버튼 선택 -> 보드 클릭. 바위는 통과 불가.'
        self._draw_text(self.small_font, hint, SUBTEXT_COLOR, (40, SCREEN_HEIGHT - 28))

    def _draw_card(self, rect: pygame.Rect) -> None:
        pygame.draw.rect(self.screen, LOG_PANEL_BG, rect, border_radius=12)
        pygame.draw.rect(self.screen, PANEL_BORDER, rect, width=2, border_radius=12)

    def _draw_obstacles(self, game) -> None:
        for tile in game.board.blocked_tiles:
            px = BOARD_ORIGIN[0] + tile[0] * TILE_SIZE
            py = BOARD_ORIGIN[1] + tile[1] * TILE_SIZE
            rock = pygame.Rect(px + 8, py + 8, TILE_SIZE - 16, TILE_SIZE - 16)
            pygame.draw.rect(self.screen, OBSTACLE_COLOR, rock, border_radius=10)
            pygame.draw.rect(self.screen, OBSTACLE_EDGE, rock, width=2, border_radius=10)
            pygame.draw.line(self.screen, OBSTACLE_EDGE, (rock.x + 10, rock.y + 14), (rock.right - 12, rock.bottom - 12), 2)
            pygame.draw.line(self.screen, (60, 68, 84), (rock.centerx, rock.y + 10), (rock.centerx - 10, rock.bottom - 10), 2)

    def _draw_overlays(self, game) -> None:
        if game.selected_unit is None:
            return
        self._blit_tile_overlay(game.selected_unit.position, self._make_overlay(SELECT_HIGHLIGHT))
        for tile in game.attack_preview_tiles:
            self._blit_tile_overlay(tile, self.overlay_attack_preview)
        if game.action_mode == ActionMode.MOVE:
            for tile in game.valid_move_tiles:
                self._blit_tile_overlay(tile, self.overlay_move)
        elif game.action_mode == ActionMode.ATTACK:
            for tile in game.valid_attack_tiles:
                self._blit_tile_overlay(tile, self.overlay_attack)
        elif game.action_mode == ActionMode.SKILL:
            for tile in game.valid_skill_tiles:
                self._blit_tile_overlay(tile, self.overlay_skill)

    def _draw_effects(self, game) -> None:
        for effect in getattr(game, 'effects', []):
            effect_type = effect['type']
            tile = effect['position']
            timer = float(effect['timer'])
            max_timer = float(effect.get('max_timer', timer))
            progress = 1.0 - (timer / max_timer if max_timer > 0 else 1.0)
            px = BOARD_ORIGIN[0] + tile[0] * TILE_SIZE
            py = BOARD_ORIGIN[1] + tile[1] * TILE_SIZE
            center = (px + TILE_SIZE // 2, py + TILE_SIZE // 2)
            alpha = int(255 * max(0.0, min(1.0, timer / max_timer if max_timer else 0.0)))
            if effect_type == 'text':
                self._draw_floating_text(effect, center, alpha, progress)
                continue
            if effect_type == 'beam':
                self._draw_beam(effect, alpha)
                continue
            overlay = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            if effect_type == 'move':
                pygame.draw.rect(overlay, (100, 240, 180, alpha), (10, 10, TILE_SIZE - 20, TILE_SIZE - 20), width=4, border_radius=10)
            elif effect_type == 'attack':
                radius = int(16 + 8 * progress)
                pygame.draw.circle(overlay, (255, 90, 90, alpha), (TILE_SIZE // 2, TILE_SIZE // 2), radius, width=4)
            elif effect_type == 'slash':
                pygame.draw.line(overlay, (255, 180, 180, alpha), (14, TILE_SIZE - 14), (TILE_SIZE - 14, 14), 4)
                pygame.draw.line(overlay, (255, 110, 110, alpha), (18, TILE_SIZE - 12), (TILE_SIZE - 12, 18), 2)
            elif effect_type == 'skill_cast':
                radius = int(12 + 12 * progress)
                pygame.draw.circle(overlay, (255, 214, 90, alpha), (TILE_SIZE // 2, TILE_SIZE // 2), radius, width=3)
            elif effect_type == 'shield':
                radius = int(18 + 6 * progress)
                pygame.draw.circle(overlay, (255, 228, 120, alpha), (TILE_SIZE // 2, TILE_SIZE // 2), radius, width=4)
            elif effect_type == 'select':
                pygame.draw.rect(overlay, (255, 255, 255, alpha), (8, 8, TILE_SIZE - 16, TILE_SIZE - 16), width=3, border_radius=10)
            elif effect_type == 'dash':
                self._draw_dash(effect.get('origin', tile), tile, alpha)
            elif effect_type == 'burst':
                self._draw_burst(effect, alpha)
            else:
                radius = int(18 + 10 * progress)
                pygame.draw.circle(overlay, (255, 214, 90, alpha), (TILE_SIZE // 2, TILE_SIZE // 2), radius, width=4)
            self.screen.blit(overlay, (px, py))

    def _draw_floating_text(self, effect: dict[str, object], center: tuple[int, int], alpha: int, progress: float) -> None:
        text = str(effect.get('text', ''))
        color = tuple(effect.get('color', (255, 255, 255)))
        surface = self.big_font.render(text, True, color)
        surface.set_alpha(alpha)
        rect = surface.get_rect(center=(center[0], center[1] - int(16 * progress)))
        self.screen.blit(surface, rect)

    def _draw_beam(self, effect: dict[str, object], alpha: int) -> None:
        path = effect.get('path', [])
        origin = effect.get('origin')
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
        target = effect['position']
        burst_surface = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        center = self._tile_center(target)
        pygame.draw.circle(burst_surface, (255, 160, 70, alpha), center, int(TILE_SIZE * 0.8), width=6)
        pygame.draw.circle(burst_surface, (255, 220, 120, alpha // 2), center, int(TILE_SIZE * 1.15), width=3)
        for tile in effect.get('tiles', []):
            px = BOARD_ORIGIN[0] + tile[0] * TILE_SIZE
            py = BOARD_ORIGIN[1] + tile[1] * TILE_SIZE
            pygame.draw.rect(burst_surface, (255, 130, 60, alpha // 3), (px + 6, py + 6, TILE_SIZE - 12, TILE_SIZE - 12), border_radius=8)
        self.screen.blit(burst_surface, (0, 0))

    def _draw_unit(self, unit) -> None:
        sprite = self.sprites[(unit.unit_type, unit.team)]
        px = BOARD_ORIGIN[0] + unit.position[0] * TILE_SIZE
        py = BOARD_ORIGIN[1] + unit.position[1] * TILE_SIZE
        self.screen.blit(sprite, (px, py))
        self._draw_hp_bar(px + 7, py + TILE_SIZE - 12, TILE_SIZE - 14, 6, unit.hp, unit.max_hp)
        if unit.shield_turns > 0:
            self.screen.blit(self.small_font.render('막', True, (255, 228, 120)), (px + TILE_SIZE - 24, py + 2))

    def _tile_center(self, tile: tuple[int, int]) -> tuple[int, int]:
        return (BOARD_ORIGIN[0] + tile[0] * TILE_SIZE + TILE_SIZE // 2, BOARD_ORIGIN[1] + tile[1] * TILE_SIZE + TILE_SIZE // 2)

    def _draw_hp_bar(self, x: int, y: int, width: int, height: int, hp: int, max_hp: int) -> None:
        pygame.draw.rect(self.screen, HP_BAR_BG, pygame.Rect(x, y, width, height), border_radius=4)
        ratio = 0 if max_hp <= 0 else hp / max_hp
        fill_width = max(0, int(width * ratio))
        color = HP_BAR_FILL if ratio > 0.4 else HP_BAR_LOW
        if fill_width > 0:
            pygame.draw.rect(self.screen, color, pygame.Rect(x, y, fill_width, height), border_radius=4)
        pygame.draw.rect(self.screen, PANEL_BORDER, pygame.Rect(x, y, width, height), width=1, border_radius=4)

    def _draw_lines_clipped(self, rect: pygame.Rect, font: pygame.font.Font, lines: list[str], color: tuple[int, int, int], line_gap: int) -> None:
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(rect)
        y = rect.y
        for line in lines:
            self._draw_text(font, line, color, (rect.x, y))
            y += line_gap
            if y > rect.bottom - line_gap:
                break
        self.screen.set_clip(prev_clip)

    def _draw_wrapped_lines(self, rect: pygame.Rect, font: pygame.font.Font, lines: list[str], color: tuple[int, int, int], line_gap: int) -> None:
        prev_clip = self.screen.get_clip()
        self.screen.set_clip(rect)
        y = rect.y
        for line in lines:
            wrapped = self._wrap_text_pixels(font, line, rect.width)
            for piece in wrapped:
                self._draw_text(font, piece, color, (rect.x, y))
                y += line_gap
                if y > rect.bottom - line_gap:
                    self.screen.set_clip(prev_clip)
                    return
            y += 2
            if y > rect.bottom - line_gap:
                self.screen.set_clip(prev_clip)
                return
        self.screen.set_clip(prev_clip)

    def _draw_single_line_fit(self, rect: pygame.Rect, font: pygame.font.Font, text: str, color: tuple[int, int, int]) -> None:
        clipped = text
        while clipped and font.size(clipped)[0] > rect.width:
            clipped = clipped[:-2] + '…' if len(clipped) > 2 else '…'
        self._draw_text(font, clipped, color, (rect.x, rect.y))

    def _draw_scrollbar(self, game, panel: pygame.Rect, visible_lines: int) -> None:
        if len(game.logs) <= visible_lines:
            return
        track = pygame.Rect(panel.right - 14, panel.y + 10, 6, panel.height - 20)
        pygame.draw.rect(self.screen, LOG_SCROLLBAR_BG, track, border_radius=4)
        total = len(game.logs)
        thumb_height = max(24, int(track.height * (visible_lines / total)))
        max_scroll = max(1, game.max_log_scroll(visible_lines))
        scroll_ratio = game.log_scroll / max_scroll
        thumb_y = track.y + int((track.height - thumb_height) * scroll_ratio)
        pygame.draw.rect(self.screen, LOG_SCROLLBAR_FG, pygame.Rect(track.x, thumb_y, track.width, thumb_height), border_radius=4)

    def _wrap_text_pixels(self, font: pygame.font.Font, text: str, max_width: int) -> list[str]:
        if not text:
            return ['']
        if font.size(text)[0] <= max_width:
            return [text]

        words = text.split(' ')
        if len(words) == 1:
            chunks: list[str] = []
            current = ''
            for char in text:
                candidate = current + char
                if current and font.size(candidate)[0] > max_width:
                    chunks.append(current)
                    current = char
                else:
                    current = candidate
            if current:
                chunks.append(current)
            return chunks

        lines: list[str] = []
        current = ''
        for word in words:
            candidate = word if not current else f'{current} {word}'
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                if font.size(word)[0] <= max_width:
                    current = word
                else:
                    lines.extend(self._wrap_text_pixels(font, word, max_width)[:-1])
                    current = self._wrap_text_pixels(font, word, max_width)[-1]
        if current:
            lines.append(current)
        return lines

    def _draw_text(self, font: pygame.font.Font, text: str, color: tuple[int, int, int], pos: tuple[int, int]) -> None:
        self.screen.blit(font.render(text, True, color), pos)

    def _draw_centered_text(self, font: pygame.font.Font, text: str, color: tuple[int, int, int], rect: pygame.Rect) -> None:
        surface = font.render(text, True, color)
        self.screen.blit(surface, surface.get_rect(center=rect.center))

    def _blit_tile_overlay(self, tile: tuple[int, int], overlay: pygame.Surface) -> None:
        px = BOARD_ORIGIN[0] + tile[0] * TILE_SIZE
        py = BOARD_ORIGIN[1] + tile[1] * TILE_SIZE
        self.screen.blit(overlay, (px, py))

    def _load_unit_sprites(self) -> dict[tuple[UnitType, Team], pygame.Surface]:
        mapping = {
            (UnitType.KING, Team.PLAYER): self.sprite_dir / 'king_blue.png',
            (UnitType.KING, Team.AI): self.sprite_dir / 'king_red.png',
            (UnitType.SWORDMAN, Team.PLAYER): self.sprite_dir / 'swordman_blue.png',
            (UnitType.SWORDMAN, Team.AI): self.sprite_dir / 'swordman_red.png',
            (UnitType.ARCHER, Team.PLAYER): self.sprite_dir / 'archer_blue.png',
            (UnitType.ARCHER, Team.AI): self.sprite_dir / 'archer_red.png',
            (UnitType.MAGE, Team.PLAYER): self.sprite_dir / 'mage_blue.png',
            (UnitType.MAGE, Team.AI): self.sprite_dir / 'mage_red.png',
        }
        return {
            key: pygame.transform.scale(pygame.image.load(path).convert_alpha(), (TILE_SIZE, TILE_SIZE))
            for key, path in mapping.items()
        }

    def _skill_description(self, unit_type: UnitType) -> str:
        descriptions = {
            UnitType.KING: '1턴 동안 받는 피해가 1 감소합니다.',
            UnitType.SWORDMAN: '직선으로 돌진하고 적과 닿으면 바로 공격합니다.',
            UnitType.ARCHER: '직선 방향 최대 3칸의 적을 한 번에 관통합니다.',
            UnitType.MAGE: '사거리 3칸 안의 3x3 범위에 폭발을 일으킵니다.',
        }
        return descriptions[unit_type]

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
        board_path = self.ui_dir / 'board.png'
        if not board_path.exists():
            surface = pygame.Surface((BOARD_PIXEL_SIZE, BOARD_PIXEL_SIZE))
            for y in range(8):
                for x in range(8):
                    color = GRID_LIGHT if (x + y) % 2 == 0 else GRID_DARK
                    pygame.draw.rect(surface, color, (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE))
                    pygame.draw.rect(surface, (18, 22, 34), (x * TILE_SIZE, y * TILE_SIZE, TILE_SIZE, TILE_SIZE), width=1)
            pygame.image.save(surface, board_path)
        for name, color in (
            ('tile_move.png', MOVE_HIGHLIGHT),
            ('tile_attack.png', ATTACK_HIGHLIGHT),
            ('tile_skill.png', SKILL_HIGHLIGHT),
        ):
            path = self.ui_dir / name
            if not path.exists():
                pygame.image.save(self._make_overlay(color), path)
