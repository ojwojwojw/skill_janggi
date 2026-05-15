from __future__ import annotations

import pygame

from game.model.constants import BUTTON_ACTIVE, BUTTON_COLOR, PANEL_BORDER, PANEL_COLOR, SCREEN_HEIGHT, SCREEN_WIDTH, SUBTEXT_COLOR, TEXT_COLOR
from game.ui.views.shared import FontMap


def draw_game_over_overlay(
    screen: pygame.Surface,
    fonts: FontMap,
    winner_text: str,
    button_rect: pygame.Rect,
    hovered: bool,
) -> None:
    """전투 종료 후 결과와 복귀 버튼이 담긴 오버레이를 그린다."""
    veil = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    veil.fill((8, 10, 18, 148))
    screen.blit(veil, (0, 0))
    panel = pygame.Rect(414, 252, 452, 204)
    pygame.draw.rect(screen, PANEL_COLOR, panel, border_radius=22)
    pygame.draw.rect(screen, PANEL_BORDER, panel, width=2, border_radius=22)
    screen.blit(fonts["title"].render("전투 종료", True, TEXT_COLOR), (panel.x + 34, panel.y + 26))
    screen.blit(fonts["body"].render(winner_text, True, TEXT_COLOR), (panel.x + 36, panel.y + 86))
    screen.blit(fonts["small"].render("버튼을 누르면 메인 화면으로 돌아갑니다.", True, SUBTEXT_COLOR), (panel.x + 36, panel.y + 118))
    fill = BUTTON_ACTIVE if hovered else BUTTON_COLOR
    pygame.draw.rect(screen, fill, button_rect, border_radius=14)
    pygame.draw.rect(screen, PANEL_BORDER, button_rect, width=2, border_radius=14)
    label = fonts["body"].render("메인 화면", True, TEXT_COLOR)
    screen.blit(label, label.get_rect(center=button_rect.center))


def draw_exit_button(
    screen: pygame.Surface,
    fonts: FontMap,
    button_rect: pygame.Rect,
    hovered: bool,
    label_text: str,
) -> None:
    """우측 상단의 화면 이탈 버튼을 그린다."""
    fill = BUTTON_ACTIVE if hovered else BUTTON_COLOR
    pygame.draw.rect(screen, fill, button_rect, border_radius=12)
    pygame.draw.rect(screen, PANEL_BORDER, button_rect, width=2, border_radius=12)
    label = fonts["small"].render(label_text, True, TEXT_COLOR)
    screen.blit(label, label.get_rect(center=button_rect.center))
