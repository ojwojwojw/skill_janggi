from __future__ import annotations

import pygame

from game.model.constants import BACKGROUND_COLOR, BUTTON_ACTIVE, BUTTON_COLOR, PANEL_BORDER, SUBTEXT_COLOR, TEXT_COLOR
from game.roster import DIFFICULTY_TITLES, MAP_OPTIONS
from game.ui.assets import draw_wrapped_left
from game.ui.views.shared import FontMap, draw_panel


def draw_setup_menu(
    screen: pygame.Surface,
    fonts: FontMap,
    map_rects: dict[str, pygame.Rect],
    difficulty_rects: dict[int, pygame.Rect],
    hovered_map: str | None,
    hovered_diff: int | None,
    selected_difficulty: int,
    selected_map: str,
    start_rect: pygame.Rect,
    hovered_start: bool,
) -> None:
    """맵과 난이도를 고르는 전투 설정 화면을 그린다."""
    screen.fill(BACKGROUND_COLOR)
    card = pygame.Rect(96, 56, 1088, 608)
    draw_panel(screen, card, radius=22)

    screen.blit(fonts["tiny"].render("전투 준비", True, (255, 220, 120)), (132, 84))
    screen.blit(fonts["hero"].render("전투 설정", True, TEXT_COLOR), (128, 104))
    screen.blit(fonts["small"].render("맵과 난이도를 고른 뒤 다음 단계로 이동하세요.", True, SUBTEXT_COLOR), (132, 176))

    screen.blit(fonts["body"].render("AI 난이도", True, TEXT_COLOR), (132, 200))
    for level, rect in difficulty_rects.items():
        active = level == selected_difficulty
        fill = BUTTON_ACTIVE if active or hovered_diff == level else BUTTON_COLOR
        pygame.draw.rect(screen, fill, rect, border_radius=12)
        pygame.draw.rect(screen, PANEL_BORDER, rect, width=2, border_radius=12)
        label = fonts["small"].render(DIFFICULTY_TITLES[level], True, TEXT_COLOR)
        screen.blit(label, label.get_rect(center=rect.center))

    screen.blit(fonts["body"].render("맵 선택", True, TEXT_COLOR), (132, 360))
    for key, title, desc in MAP_OPTIONS:
        rect = map_rects[key]
        active = key == selected_map
        fill = BUTTON_ACTIVE if active else BUTTON_COLOR
        if hovered_map == key:
            fill = (96, 126, 176) if active else (70, 86, 116)
        pygame.draw.rect(screen, fill, rect, border_radius=16)
        border = (255, 220, 120) if active else PANEL_BORDER
        pygame.draw.rect(screen, border, rect, width=2, border_radius=16)
        screen.blit(fonts["body"].render(title, True, TEXT_COLOR), (rect.x + 14, rect.y + 12))
        draw_wrapped_left(screen, fonts["small"], desc, SUBTEXT_COLOR, (rect.x + 14, rect.y + 42), rect.width - 24, 17)

    fill = (104, 148, 224) if hovered_start else (84, 128, 208)
    pygame.draw.rect(screen, fill, start_rect, border_radius=14)
    pygame.draw.rect(screen, (255, 230, 150), start_rect, width=2, border_radius=14)
    surface = fonts["body"].render("다음", True, TEXT_COLOR)
    screen.blit(surface, surface.get_rect(center=start_rect.center))
