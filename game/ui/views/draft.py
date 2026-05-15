from __future__ import annotations

from typing import Callable

import pygame

from game.model.constants import BACKGROUND_COLOR, BUTTON_ACTIVE, BUTTON_COLOR, DRAFT_SIZE, PANEL_BORDER, SUBTEXT_COLOR, TEXT_COLOR, UNIT_COSTS, UnitType
from game.roster import UNIT_DRAFT_BLURBS_LOCAL, UNIT_LABELS
from game.ui.assets import draw_wrapped_left
from game.ui.views.shared import FontMap, draw_panel


def draw_draft_menu(
    screen: pygame.Surface,
    fonts: FontMap,
    roster: list[UnitType],
    selected_difficulty: int,
    selected_unit: UnitType,
    hovered_unit: UnitType | None,
    hover_button: str | None,
    unit_rects: dict[UnitType, pygame.Rect],
    action_rects: dict[str, pygame.Rect],
    preview_sprites: dict[UnitType, pygame.Surface],
    budget_text: str,
    can_add_unit_fn: Callable[[list[UnitType], UnitType, int], bool],
) -> None:
    """드래프트 화면의 예산, 선택 편성, 기물 카드, 액션 버튼을 그린다."""
    screen.fill(BACKGROUND_COLOR)
    card = pygame.Rect(84, 26, 1112, 666)
    draw_panel(screen, card, radius=22)

    screen.blit(fonts["title"].render("기물 드래프트", True, TEXT_COLOR), (118, 66))
    screen.blit(fonts["body"].render(budget_text, True, (255, 220, 120)), (118, 112))
    screen.blit(fonts["small"].render("왕은 자동 포함됩니다. 각 기물의 자세한 정보는 도감에서 확인할 수 있습니다.", True, SUBTEXT_COLOR), (118, 144))

    summary = pygame.Rect(118, 188, 318, 432)
    draw_panel(screen, summary, radius=16, fill=(17, 22, 34))
    screen.blit(fonts["body"].render("선택한 편성", True, TEXT_COLOR), (138, 194))
    screen.blit(fonts["small"].render("왕 자동 포함", True, SUBTEXT_COLOR), (138, 226))

    for idx in range(DRAFT_SIZE):
        y = 268 + idx * 41
        slot_rect = pygame.Rect(134, y, 286, 32)
        pygame.draw.rect(screen, (35, 42, 60), slot_rect, border_radius=10)
        if idx < len(roster):
            unit = roster[idx]
            label = f"{idx + 1}. {UNIT_LABELS[unit]}  비용 {UNIT_COSTS[unit]}"
            screen.blit(fonts["small"].render(label, True, TEXT_COLOR), (148, y + 7))
        else:
            screen.blit(fonts["small"].render(f"{idx + 1}. 비어 있음", True, SUBTEXT_COLOR), (148, y + 7))

    screen.blit(fonts["body"].render("기물 목록", True, TEXT_COLOR), (482, 194))
    screen.blit(fonts["small"].render("카드를 눌러 기물을 추가하세요. 최소 3기물부터 전투를 시작할 수 있습니다.", True, SUBTEXT_COLOR), (482, 226))

    for unit, rect in unit_rects.items():
        enabled = can_add_unit_fn(roster, unit, selected_difficulty)
        fill = BUTTON_ACTIVE if hovered_unit == unit and enabled else BUTTON_COLOR if enabled else (43, 48, 58)
        pygame.draw.rect(screen, fill, rect, border_radius=14)
        pygame.draw.rect(screen, PANEL_BORDER, rect, width=2, border_radius=14)
        screen.blit(preview_sprites[unit], (rect.x + 14, rect.y + 16))
        screen.blit(fonts["body"].render(UNIT_LABELS[unit], True, TEXT_COLOR), (rect.x + 92, rect.y + 14))
        cost_surface = fonts["small"].render(f"비용 {UNIT_COSTS[unit]}", True, (255, 220, 120))
        screen.blit(cost_surface, (rect.right - cost_surface.get_width() - 16, rect.y + 18))
        draw_wrapped_left(screen, fonts["small"], UNIT_DRAFT_BLURBS_LOCAL[unit], SUBTEXT_COLOR, (rect.x + 92, rect.y + 50), rect.width - 112, 16)
        if unit == selected_unit:
            pygame.draw.rect(screen, (255, 220, 120), rect, width=2, border_radius=14)

    labels = {"undo": "되돌리기", "fill": "자동 채우기", "start": "전투 시작"}
    for key, rect in action_rects.items():
        enabled = (key != "start" or len(roster) >= 3) and (key != "undo" or bool(roster))
        fill = BUTTON_ACTIVE if hover_button == key and enabled else BUTTON_COLOR if enabled else (43, 48, 58)
        pygame.draw.rect(screen, fill, rect, border_radius=14)
        pygame.draw.rect(screen, PANEL_BORDER, rect, width=2, border_radius=14)
        label_surface = fonts["body"].render(labels[key], True, TEXT_COLOR)
        screen.blit(label_surface, label_surface.get_rect(center=rect.center))
