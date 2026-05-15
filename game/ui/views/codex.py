from __future__ import annotations

import pygame

from game.engine.game_manager import BASE_HP
from game.model.constants import BACKGROUND_COLOR, BUTTON_ACTIVE, BUTTON_COLOR, PANEL_BORDER, SUBTEXT_COLOR, TEXT_COLOR, UNIT_COSTS, UnitType
from game.model.unit import ATTACK_POWER
from game.roster import UNIT_LABELS, codex_detail_lines
from game.ui.assets import draw_wrapped_left
from game.ui.views.shared import FontMap, draw_panel


def draw_codex_menu(
    screen: pygame.Surface,
    fonts: FontMap,
    unit_rects: dict[UnitType, pygame.Rect],
    selected_unit: UnitType,
    hovered_unit: UnitType | None,
    preview_sprites: dict[UnitType, pygame.Surface],
    back_rect: pygame.Rect,
    hovered_back: bool,
) -> None:
    """기물 도감 화면에서 기물 설명과 스탯 정보를 그린다."""
    screen.fill(BACKGROUND_COLOR)
    card = pygame.Rect(84, 30, 1112, 660)
    draw_panel(screen, card, radius=22)

    screen.blit(fonts["tiny"].render("기물 정보", True, (255, 220, 120)), (122, 64))
    screen.blit(fonts["title"].render("기물 도감", True, TEXT_COLOR), (118, 88))
    screen.blit(fonts["small"].render("각 기물의 체력, 공격, 이동, 스킬 정보를 확인하세요.", True, SUBTEXT_COLOR), (118, 130))

    for unit, rect in unit_rects.items():
        active = unit == selected_unit
        fill = BUTTON_ACTIVE if active or hovered_unit == unit else BUTTON_COLOR
        pygame.draw.rect(screen, fill, rect, border_radius=14)
        pygame.draw.rect(screen, (255, 220, 120) if active else PANEL_BORDER, rect, width=2, border_radius=14)
        screen.blit(preview_sprites[unit], (rect.x + 10, rect.y + 12))
        screen.blit(fonts["body"].render(UNIT_LABELS[unit], True, TEXT_COLOR), (rect.x + 84, rect.y + 14))
        small_line = "비용 고정" if unit == UnitType.KING else f"비용 {UNIT_COSTS.get(unit, '-')}"
        screen.blit(fonts["small"].render(small_line, True, (255, 220, 120)), (rect.x + 84, rect.y + 44))
        screen.blit(fonts["small"].render(f"공격 {ATTACK_POWER[unit]} / 체력 {BASE_HP[unit]}", True, SUBTEXT_COLOR), (rect.x + 84, rect.y + 65))

    detail = pygame.Rect(118, 438, 962, 200)
    draw_panel(screen, detail, radius=18, fill=(17, 22, 34))
    screen.blit(preview_sprites[selected_unit], (142, 458))
    screen.blit(fonts["title"].render(UNIT_LABELS[selected_unit], True, TEXT_COLOR), (232, 458))
    y = 504
    for index, line in enumerate(codex_detail_lines(selected_unit)):
        color = (255, 220, 120) if index in {0, 3} else SUBTEXT_COLOR
        draw_wrapped_left(screen, fonts["small"], line, color, (232, y), 814, 18)
        y += 30 if index == 4 else 22

    back_fill = BUTTON_ACTIVE if hovered_back else BUTTON_COLOR
    pygame.draw.rect(screen, back_fill, back_rect, border_radius=14)
    pygame.draw.rect(screen, PANEL_BORDER, back_rect, width=2, border_radius=14)
    back_label = fonts["body"].render("뒤로", True, TEXT_COLOR)
    screen.blit(back_label, back_label.get_rect(center=back_rect.center))
