from __future__ import annotations

import pygame

from game.model.constants import PANEL_BORDER, PANEL_COLOR

FontMap = dict[str, pygame.font.Font]


def draw_panel(
    screen: pygame.Surface,
    rect: pygame.Rect,
    *,
    radius: int,
    fill: tuple[int, int, int] = PANEL_COLOR,
    border: tuple[int, int, int] = PANEL_BORDER,
    border_width: int = 2,
) -> None:
    """공통 카드 패널 배경과 테두리를 그린다."""
    pygame.draw.rect(screen, fill, rect, border_radius=radius)
    pygame.draw.rect(screen, border, rect, width=border_width, border_radius=radius)
