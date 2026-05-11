from pathlib import Path
import random

import pygame

from game.board import Board
from game.constants import (
    BACKGROUND_COLOR,
    BUTTON_ACTIVE,
    BUTTON_COLOR,
    PANEL_BORDER,
    PANEL_COLOR,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SUBTEXT_COLOR,
    TEXT_COLOR,
    FPS,
)
from game.game_manager import GameManager
from game.renderer import Renderer


def draw_centered_lines(screen: pygame.Surface, font: pygame.font.Font, lines: list[str], color: tuple[int, int, int], center_x: int, start_y: int, gap: int) -> None:
    y = start_y
    for line in lines:
        surface = font.render(line, True, color)
        screen.blit(surface, surface.get_rect(center=(center_x, y)))
        y += gap


def draw_menu(screen: pygame.Surface, fonts: dict[str, pygame.font.Font], button_rects: dict[str, pygame.Rect], hovered: str | None) -> None:
    screen.fill(BACKGROUND_COLOR)

    card = pygame.Rect(212, 118, 856, 462)
    pygame.draw.rect(screen, PANEL_COLOR, card, border_radius=22)
    pygame.draw.rect(screen, PANEL_BORDER, card, width=2, border_radius=22)

    title = fonts['title'].render('Skill Janggi', True, TEXT_COLOR)
    screen.blit(title, title.get_rect(center=(SCREEN_WIDTH // 2, 202)))

    draw_centered_lines(
        screen,
        fonts['body'],
        ['시작 맵을 선택하세요'],
        TEXT_COLOR,
        SCREEN_WIDTH // 2,
        252,
        24,
    )
    draw_centered_lines(
        screen,
        fonts['small'],
        ['장애물 맵은 대칭적으로 배치되며,', '중앙 통로를 완전히 막지 않습니다.'],
        SUBTEXT_COLOR,
        SCREEN_WIDTH // 2,
        290,
        20,
    )

    options = {
        'open': ('장애물 없는 맵', ['순수한 전투 흐름으로', '바로 시작합니다.']),
        'random': ('대칭 랜덤 장애물 맵', ['측면 통로에 바위가 생기며', '매판 지형이 달라집니다.']),
    }

    for key, rect in button_rects.items():
        color = BUTTON_ACTIVE if hovered == key else BUTTON_COLOR
        pygame.draw.rect(screen, color, rect, border_radius=18)
        pygame.draw.rect(screen, PANEL_BORDER, rect, width=2, border_radius=18)
        label, caption_lines = options[key]
        label_surface = fonts['body'].render(label, True, TEXT_COLOR)
        screen.blit(label_surface, label_surface.get_rect(center=(rect.centerx, rect.y + 42)))
        draw_centered_lines(screen, fonts['small'], caption_lines, SUBTEXT_COLOR, rect.centerx, rect.y + 78, 18)

    footer = fonts['small'].render('클릭한 맵으로 바로 게임을 시작합니다.', True, SUBTEXT_COLOR)
    screen.blit(footer, footer.get_rect(center=(SCREEN_WIDTH // 2, 544)))


def main() -> None:
    pygame.init()
    pygame.display.set_caption('Skill Janggi')
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()

    fonts = {
        'title': pygame.font.SysFont('malgungothic', 38, bold=True),
        'body': pygame.font.SysFont('malgungothic', 18, bold=True),
        'small': pygame.font.SysFont('malgungothic', 14),
    }
    button_rects = {
        'open': pygame.Rect(282, 338, 300, 144),
        'random': pygame.Rect(698, 338, 300, 144),
    }

    project_root = Path(__file__).resolve().parent
    game: GameManager | None = None
    renderer: Renderer | None = None
    menu_mode = True
    running = True

    while running:
        dt = clock.tick(FPS) / 1000.0
        hovered = None
        if menu_mode:
            mouse_pos = pygame.mouse.get_pos()
            for key, rect in button_rects.items():
                if rect.collidepoint(mouse_pos):
                    hovered = key
                    break

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif menu_mode:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    blocked_tiles: set[tuple[int, int]] = set()
                    if button_rects['open'].collidepoint(event.pos):
                        blocked_tiles = set()
                    elif button_rects['random'].collidepoint(event.pos):
                        blocked_tiles = Board.symmetric_random_obstacles(random.Random())
                    else:
                        continue
                    game = GameManager(project_root, blocked_tiles=blocked_tiles)
                    renderer = Renderer(screen, project_root)
                    menu_mode = False
            else:
                assert game is not None
                game.handle_event(event)

        if menu_mode:
            draw_menu(screen, fonts, button_rects, hovered)
        else:
            assert game is not None and renderer is not None
            game.update(dt)
            renderer.draw(game)

        pygame.display.flip()

    pygame.quit()


if __name__ == '__main__':
    main()
