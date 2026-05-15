from __future__ import annotations

from pathlib import Path
import random
import sys

import pygame

from game.roster import auto_fill_roster, build_ai_roster, can_add_unit, draft_budget_for_difficulty
from game.ui.assets import SoundController, load_preview_sprites, load_ui_font
from game.ui.layout import (
    auto_arrange_player_positions,
    build_codex_unit_rects,
    build_deployment_action_rects,
    build_deployment_slot_rect,
    build_draft_unit_rects,
    build_menu_button_rects,
    build_setup_action_rect,
    build_setup_rects,
    build_tutorial_battle,
)
from game.ui.screens import (
    draw_codex_menu,
    draw_deployment_menu,
    draw_draft_menu,
    draw_exit_button,
    draw_game_over_overlay,
    draw_main_menu,
    draw_setup_menu,
)
from game.engine.game_manager import PLAYER_HOME_POSITIONS, PLAYER_KING_POS, GameManager
from game.engine.renderer import Renderer, board_tile_at_pixel
from game.model.board import Board
from game.model.constants import FPS, SCREEN_HEIGHT, SCREEN_WIDTH, UNIT_COSTS, UnitType


def resolve_app_paths() -> tuple[Path, Path]:
    if getattr(sys, "frozen", False):
        asset_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        data_root = Path(sys.executable).resolve().parent
    else:
        asset_root = Path(__file__).resolve().parent
        data_root = asset_root
    return asset_root, data_root


def hovered_key(rects: dict[object, pygame.Rect], mouse_pos: tuple[int, int]) -> object | None:
    return next((key for key, rect in rects.items() if rect.collidepoint(mouse_pos)), None)


def main() -> None:
    pygame.mixer.pre_init(44100, -16, 1, 512)
    pygame.init()
    pygame.display.set_caption("스킬 장기")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    clock = pygame.time.Clock()
    fonts = {
        "hero": load_ui_font(40, bold=True),
        "title": load_ui_font(32, bold=True),
        "body": load_ui_font(18, bold=True),
        "small": load_ui_font(15, bold=False),
        "tiny": load_ui_font(13, bold=True),
    }

    asset_root, data_root = resolve_app_paths()
    sounds = SoundController(asset_root)
    preview_sprites = load_preview_sprites(asset_root)

    menu_button_rects = build_menu_button_rects()
    map_rects, difficulty_rects = build_setup_rects()
    setup_start_rect = build_setup_action_rect()
    codex_unit_rects = build_codex_unit_rects()
    codex_back_rect = pygame.Rect(916, 648, 164, 40)
    unit_rects = build_draft_unit_rects()
    action_rects = {
        "undo": pygame.Rect(786, 598, 146, 40),
        "fill": pygame.Rect(944, 598, 146, 40),
        "start": pygame.Rect(786, 646, 304, 40),
    }
    deployment_action_rects = build_deployment_action_rects()
    return_button_rect = pygame.Rect(528, 404, 224, 42)
    tutorial_exit_rect = pygame.Rect(1036, 26, 164, 38)

    game: GameManager | None = None
    renderer: Renderer | None = None
    ai_roster: list[UnitType] = []
    rng = random.Random()
    mode = "menu"
    blocked_tiles = set(Board.default_obstacles())
    selected_map = "classic"
    player_roster: list[UnitType] = []
    player_placements: dict[int, tuple[int, int]] = {}
    selected_deploy_index: int | None = None
    selected_preview = UnitType.SWORDMAN
    selected_codex_unit = UnitType.KING
    selected_difficulty = 3
    running = True
    last_music_mode: str | None = None

    def reset_match_state() -> None:
        nonlocal game, renderer, player_roster, player_placements, selected_deploy_index
        game = None
        renderer = None
        player_roster = []
        player_placements = {}
        selected_deploy_index = None

    while running:
        dt = clock.tick(FPS) / 1000.0
        mouse_pos = pygame.mouse.get_pos()
        hovered_menu = hovered_key(menu_button_rects, mouse_pos) if mode == "menu" else None
        hovered_map = hovered_key(map_rects, mouse_pos) if mode == "setup" else None
        hovered_diff = hovered_key(difficulty_rects, mouse_pos) if mode == "setup" else None
        hovered_setup_start = mode == "setup" and setup_start_rect.collidepoint(mouse_pos)
        hovered_codex_unit = hovered_key(codex_unit_rects, mouse_pos) if mode == "codex" else None
        hovered_codex_back = mode == "codex" and codex_back_rect.collidepoint(mouse_pos)
        hovered_unit = hovered_key(unit_rects, mouse_pos) if mode == "draft" else None
        hovered_action = hovered_key(action_rects, mouse_pos) if mode == "draft" else None
        hovered_deploy_action = hovered_key(deployment_action_rects, mouse_pos) if mode == "deployment" else None
        hovered_return = mode == "game" and game is not None and game.state.name == "GAME_OVER" and return_button_rect.collidepoint(mouse_pos)
        hovered_exit = mode == "game" and game is not None and game.state.name != "GAME_OVER" and tutorial_exit_rect.collidepoint(mouse_pos)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif mode == "menu" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if menu_button_rects["start"].collidepoint(event.pos):
                    mode = "setup"
                elif menu_button_rects["tutorial"].collidepoint(event.pos):
                    game = build_tutorial_battle(data_root)
                    renderer = Renderer(screen, asset_root)
                    mode = "game"
                elif menu_button_rects["codex"].collidepoint(event.pos):
                    mode = "codex"
            elif mode == "setup" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked_diff = hovered_key(difficulty_rects, event.pos)
                if clicked_diff is not None:
                    selected_difficulty = clicked_diff
                    continue
                clicked_map = hovered_key(map_rects, event.pos)
                if clicked_map is not None:
                    selected_map = clicked_map
                    blocked_tiles = Board.preset_obstacles(clicked_map, rng)
                    continue
                if setup_start_rect.collidepoint(event.pos):
                    player_roster = []
                    player_placements = {}
                    selected_deploy_index = None
                    mode = "draft"
            elif mode == "codex" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked_codex_unit = hovered_key(codex_unit_rects, event.pos)
                if clicked_codex_unit is not None:
                    selected_codex_unit = clicked_codex_unit
                elif codex_back_rect.collidepoint(event.pos):
                    mode = "menu"
            elif mode == "draft" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked_unit = hovered_key(unit_rects, event.pos)
                if clicked_unit is not None:
                    selected_preview = clicked_unit
                    if can_add_unit(player_roster, clicked_unit, selected_difficulty):
                        player_roster.append(clicked_unit)
                        sounds.play("pick")
                elif action_rects["undo"].collidepoint(event.pos) and player_roster:
                    player_roster.pop()
                elif action_rects["fill"].collidepoint(event.pos):
                    player_roster = auto_fill_roster(player_roster, rng, difficulty=selected_difficulty)
                elif action_rects["start"].collidepoint(event.pos) and len(player_roster) >= 3:
                    ai_roster = build_ai_roster(rng.randint(0, 1_000_000), selected_difficulty)
                    player_placements = {}
                    selected_deploy_index = 0 if player_roster else None
                    mode = "deployment"
            elif mode == "deployment" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                selected_slot = None
                for idx in range(len(player_roster)):
                    rect = build_deployment_slot_rect(idx)
                    if rect.collidepoint(event.pos):
                        selected_slot = idx
                        break
                if selected_slot is not None:
                    selected_deploy_index = selected_slot
                    continue

                clicked_tile = board_tile_at_pixel(event.pos)
                if clicked_tile is not None and selected_deploy_index is not None:
                    valid_tiles = {tile for tile in PLAYER_HOME_POSITIONS if tile not in blocked_tiles and tile != PLAYER_KING_POS}
                    if clicked_tile in valid_tiles:
                        taken = {idx: pos for idx, pos in player_placements.items() if pos == clicked_tile}
                        for idx in taken:
                            del player_placements[idx]
                        player_placements[selected_deploy_index] = clicked_tile
                        remaining = [idx for idx in range(len(player_roster)) if idx not in player_placements]
                        selected_deploy_index = remaining[0] if remaining else None
                        continue

                if deployment_action_rects["auto"].collidepoint(event.pos):
                    auto_positions = auto_arrange_player_positions(player_roster, blocked_tiles)
                    player_placements = {idx: pos for idx, pos in enumerate(auto_positions)}
                    selected_deploy_index = None
                elif deployment_action_rects["clear"].collidepoint(event.pos):
                    player_placements = {}
                    selected_deploy_index = 0 if player_roster else None
                elif deployment_action_rects["start"].collidepoint(event.pos) and len(player_placements) == len(player_roster):
                    ordered_positions = [player_placements[idx] for idx in range(len(player_roster))]
                    game = GameManager(
                        data_root,
                        blocked_tiles=blocked_tiles,
                        player_roster=player_roster,
                        ai_roster=ai_roster,
                        player_positions=ordered_positions,
                        ai_difficulty=selected_difficulty,
                        map_name=selected_map,
                    )
                    game.tutorial_visible = False
                    renderer = Renderer(screen, asset_root)
                    mode = "game"
            elif mode == "game":
                assert game is not None
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and game.state.name != "GAME_OVER" and tutorial_exit_rect.collidepoint(event.pos):
                    reset_match_state()
                    mode = "menu"
                    continue
                if game.state.name == "GAME_OVER" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and return_button_rect.collidepoint(event.pos):
                    reset_match_state()
                    mode = "menu"
                    continue
                game.handle_event(event)

        if mode == "game" and game is not None and game.state.name == "GAME_OVER":
            if last_music_mode is not None:
                sounds.stop_music()
                last_music_mode = None
        else:
            desired_music = "boss" if mode == "game" and game is not None and game.ai_difficulty >= 7 else "battle" if mode == "game" else "menu"
            if desired_music != last_music_mode:
                sounds.play_music(desired_music)
                last_music_mode = desired_music

        if mode == "menu":
            draw_main_menu(screen, fonts, menu_button_rects, hovered_menu)
        elif mode == "setup":
            draw_setup_menu(
                screen,
                fonts,
                map_rects,
                difficulty_rects,
                hovered_map,
                hovered_diff,
                selected_difficulty,
                selected_map,
                setup_start_rect,
                hovered_setup_start,
            )
        elif mode == "codex":
            draw_codex_menu(
                screen,
                fonts,
                codex_unit_rects,
                selected_codex_unit,
                hovered_codex_unit,
                preview_sprites,
                codex_back_rect,
                hovered_codex_back,
            )
        elif mode == "draft":
            budget = draft_budget_for_difficulty(selected_difficulty)
            remaining = None if budget is None else budget - sum(UNIT_COSTS[unit] for unit in player_roster)
            budget_text = "예산 제한 없음" if budget is None else f"예산 {remaining}/{budget}"
            draw_draft_menu(
                screen,
                fonts,
                player_roster,
                selected_difficulty,
                selected_preview,
                hovered_unit,
                hovered_action,
                unit_rects,
                action_rects,
                preview_sprites,
                budget_text,
                can_add_unit,
            )
        elif mode == "deployment":
            draw_deployment_menu(
                screen,
                fonts,
                asset_root,
                player_roster,
                player_placements,
                selected_deploy_index,
                blocked_tiles,
                selected_map,
                preview_sprites,
                deployment_action_rects,
                hovered_deploy_action,
            )
        else:
            assert game is not None and renderer is not None
            game.update(dt)
            for sound_name in game.drain_sound_events():
                sounds.play(sound_name)
            renderer.draw(game)
            if game.state.name != "GAME_OVER":
                exit_label = "튜토리얼 나가기" if game.tutorial_completed and not game.tutorial_mode else "게임 나가기"
                draw_exit_button(screen, fonts, tutorial_exit_rect, hovered_exit, exit_label)
            if game.state.name == "GAME_OVER":
                winner_text = "승리: 청팀" if game.winner is not None and game.winner.name == "PLAYER" else "패배: 적팀"
                draw_game_over_overlay(screen, fonts, winner_text, return_button_rect, hovered_return)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
