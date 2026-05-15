from __future__ import annotations

import pygame

from game.model.constants import BACKGROUND_COLOR, BUTTON_ACTIVE, BUTTON_COLOR, PANEL_BORDER, SUBTEXT_COLOR, TEXT_COLOR
from game.ui.assets import draw_wrapped_left
from game.ui.views.shared import FontMap, draw_panel


def draw_main_menu(
    screen: pygame.Surface,
    fonts: FontMap,
    menu_buttons: dict[str, pygame.Rect],
    hovered_button: str | None,
) -> None:
    """메인 메뉴 카드와 주요 진입 버튼을 그린다."""
    screen.fill(BACKGROUND_COLOR)
    card = pygame.Rect(220, 72, 840, 576)
    draw_panel(screen, card, radius=28)

    glow = pygame.Rect(card.x + 44, card.y + 58, card.width - 88, 130)
    pygame.draw.rect(screen, (30, 40, 66), glow, border_radius=24)
    screen.blit(fonts["tiny"].render("전략 대전", True, (255, 220, 120)), (card.x + 70, card.y + 78))
    screen.blit(fonts["hero"].render("스킬 장기", True, TEXT_COLOR), (card.x + 66, card.y + 104))
    draw_wrapped_left(
        screen,
        fonts["small"],
        "전장을 고르고 새 게임을 시작하거나, 튜토리얼로 기본 흐름을 먼저 익혀보세요.",
        SUBTEXT_COLOR,
        (card.x + 70, card.y + 158),
        card.width - 140,
        18,
    )

    labels = {"start": "게임 시작", "tutorial": "튜토리얼", "codex": "기물 도감"}
    for key, rect in menu_buttons.items():
        primary = key == "start"
        hovered = hovered_button == key
        fill = (104, 148, 224) if primary and hovered else (84, 128, 208) if primary else BUTTON_ACTIVE if hovered else BUTTON_COLOR
        border = (255, 230, 150) if primary else PANEL_BORDER
        pygame.draw.rect(screen, fill, rect, border_radius=16)
        pygame.draw.rect(screen, border, rect, width=2, border_radius=16)
        label = fonts["body"].render(labels[key], True, TEXT_COLOR)
        screen.blit(label, label.get_rect(center=rect.center))
