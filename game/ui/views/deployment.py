from __future__ import annotations

from pathlib import Path

import pygame

from game.model.constants import BACKGROUND_COLOR, BOARD_ORIGIN, BOARD_PIXEL_SIZE, BUTTON_ACTIVE, BUTTON_COLOR, PANEL_BORDER, SUBTEXT_COLOR, TEXT_COLOR, TILE_SIZE, UnitType
from game.roster import UNIT_LABELS
from game.ui.assets import draw_wrapped_left
from game.ui.views.rects import build_deployment_slot_rect
from game.ui.views.shared import FontMap, draw_panel
from game.engine.game_manager import PLAYER_HOME_POSITIONS, PLAYER_KING_POS


def draw_deployment_menu(
    screen: pygame.Surface,
    fonts: FontMap,
    project_root: Path,
    roster: list[UnitType],
    placements: dict[int, tuple[int, int]],
    selected_index: int | None,
    blocked_tiles: set[tuple[int, int]],
    map_name: str,
    preview_sprites: dict[UnitType, pygame.Surface],
    action_rects: dict[str, pygame.Rect],
    hover_action: str | None,
) -> None:
    """배치 화면의 보드, 배치 슬롯, 시작 버튼을 그린다."""
    screen.fill(BACKGROUND_COLOR)
    board_surface = pygame.transform.scale(
        pygame.image.load(project_root / "assets" / "ui" / "board.png").convert(),
        (BOARD_PIXEL_SIZE, BOARD_PIXEL_SIZE),
    )
    screen.blit(board_surface, BOARD_ORIGIN)

    for tile in blocked_tiles:
        px = BOARD_ORIGIN[0] + tile[0] * TILE_SIZE
        py = BOARD_ORIGIN[1] + tile[1] * TILE_SIZE
        shape = pygame.Rect(px + 8, py + 8, TILE_SIZE - 16, TILE_SIZE - 16)
        if map_name == "river":
            pygame.draw.rect(screen, (56, 118, 190), shape, border_radius=10)
            pygame.draw.rect(screen, (35, 82, 144), shape, width=2, border_radius=10)
        else:
            pygame.draw.rect(screen, (88, 96, 116), shape, border_radius=10)
            pygame.draw.rect(screen, (138, 148, 176), shape, width=2, border_radius=10)

    for tile in PLAYER_HOME_POSITIONS:
        if tile in blocked_tiles or tile == PLAYER_KING_POS:
            continue
        px = BOARD_ORIGIN[0] + tile[0] * TILE_SIZE
        py = BOARD_ORIGIN[1] + tile[1] * TILE_SIZE
        pygame.draw.rect(screen, (84, 138, 220, 88), (px + 5, py + 5, TILE_SIZE - 10, TILE_SIZE - 10), border_radius=10)

    king_px = BOARD_ORIGIN[0] + PLAYER_KING_POS[0] * TILE_SIZE
    king_py = BOARD_ORIGIN[1] + PLAYER_KING_POS[1] * TILE_SIZE
    pygame.draw.rect(screen, (255, 210, 92), (king_px + 4, king_py + 4, TILE_SIZE - 8, TILE_SIZE - 8), width=3, border_radius=10)
    king_label = fonts["tiny"].render("왕", True, (255, 230, 160))
    screen.blit(king_label, (king_px + 8, king_py + 8))

    for idx, tile in placements.items():
        unit = roster[idx]
        px = BOARD_ORIGIN[0] + tile[0] * TILE_SIZE
        py = BOARD_ORIGIN[1] + tile[1] * TILE_SIZE
        screen.blit(preview_sprites[unit], (px, py))
        if selected_index == idx:
            pygame.draw.rect(screen, (255, 220, 120), (px + 3, py + 3, TILE_SIZE - 6, TILE_SIZE - 6), width=3, border_radius=10)

    panel = pygame.Rect(820, 42, 404, 636)
    draw_panel(screen, panel, radius=18)
    screen.blit(fonts["title"].render("배치", True, TEXT_COLOR), (846, 64))
    draw_wrapped_left(screen, fonts["small"], "전투가 시작되기 전에 기물을 배치하세요. 왕은 고정된 위치에 배치됩니다.", SUBTEXT_COLOR, (846, 106), 340, 18)
    screen.blit(fonts["small"].render("기물은 파란색으로 강조된 칸에만 놓을 수 있습니다.", True, (160, 214, 255)), (846, 154))

    for idx, unit in enumerate(roster):
        rect = build_deployment_slot_rect(idx)
        active = idx == selected_index
        filled = idx in placements
        fill = BUTTON_ACTIVE if active else (56, 68, 92) if filled else (40, 46, 58)
        pygame.draw.rect(screen, fill, rect, border_radius=12)
        pygame.draw.rect(screen, PANEL_BORDER, rect, width=2, border_radius=12)
        thumb = pygame.transform.scale(preview_sprites[unit], (38, 38))
        screen.blit(thumb, (rect.x + 8, rect.y + 3))
        state = f"{placements[idx]}" if filled else "미배치"
        screen.blit(fonts["body"].render(UNIT_LABELS[unit], True, TEXT_COLOR), (rect.x + 54, rect.y + 9))
        screen.blit(fonts["small"].render(state, True, SUBTEXT_COLOR), (rect.right - 102, rect.y + 11))

    labels = {"auto": "자동 배치", "clear": "초기화", "start": "전투 시작"}
    ready = len(placements) == len(roster)
    for key, rect in action_rects.items():
        enabled = key != "start" or ready
        fill = BUTTON_ACTIVE if hover_action == key and enabled else BUTTON_COLOR if enabled else (43, 48, 58)
        pygame.draw.rect(screen, fill, rect, border_radius=12)
        pygame.draw.rect(screen, PANEL_BORDER, rect, width=2, border_radius=12)
        label = fonts["body"].render(labels[key], True, TEXT_COLOR)
        screen.blit(label, label.get_rect(center=rect.center))
