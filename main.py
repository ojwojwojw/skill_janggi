from __future__ import annotations

from pathlib import Path
import random

import pygame

from game.board import Board
from game.constants import (
    BACKGROUND_COLOR,
    BUTTON_ACTIVE,
    BUTTON_COLOR,
    DRAFT_BUDGET,
    DRAFT_POOL,
    DRAFT_SIZE,
    FPS,
    PANEL_BORDER,
    PANEL_COLOR,
    GameState,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SUBTEXT_COLOR,
    Team,
    TEAM_NAMES,
    TEXT_COLOR,
    UNIT_COSTS,
    UNIT_DISPLAY_NAMES,
    UNIT_DRAFT_BLURBS,
    UnitType,
)
from game.game_manager import GameManager
from game.renderer import Renderer

MAP_OPTIONS = [
    ("classic", "기본 진형", "중앙 장애물만 있는 균형 잡힌 전장입니다."),
    ("wings", "측면 압박", "양옆 통로가 열려 기동전이 강조됩니다."),
    ("river", "강줄기 맵", "중앙 강을 사이에 두고 우회해야 합니다."),
    ("fort", "요새 전장", "좁은 통로를 두고 버티기 좋은 맵입니다."),
    ("cross", "십자 전장", "십자 통로를 먼저 장악하면 유리합니다."),
    ("chaos", "혼전 전장", "장애물이 많아 난전이 자주 벌어집니다."),
]


def load_ui_font(size: int, bold: bool = False) -> pygame.font.Font:
    candidates = [
        "malgungothic",
        "malgun gothic",
        "nanumgothic",
        "applegothic",
        "arialunicode",
        "arial",
    ]
    font_path = None
    for name in candidates:
        font_path = pygame.font.match_font(name)
        if font_path:
            break
    font = pygame.font.Font(font_path, size) if font_path else pygame.font.SysFont(None, size, bold=bold)
    font.set_bold(bold)
    return font


def draw_centered_lines(
    screen: pygame.Surface,
    font: pygame.font.Font,
    lines: list[str],
    color: tuple[int, int, int],
    center_x: int,
    start_y: int,
    gap: int,
) -> None:
    y = start_y
    for line in lines:
        surface = font.render(line, True, color)
        screen.blit(surface, surface.get_rect(center=(center_x, y)))
        y += gap


def wrap_text(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    if not text or font.size(text)[0] <= max_width:
        return [text]
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_wrapped_left(
    screen: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    pos: tuple[int, int],
    max_width: int,
    line_gap: int,
) -> None:
    x, y = pos
    for line in wrap_text(font, text, max_width):
        screen.blit(font.render(line, True, color), (x, y))
        y += line_gap


def can_add_unit(roster: list[UnitType], unit_type: UnitType) -> bool:
    if len(roster) >= DRAFT_SIZE:
        return False
    if unit_type in {UnitType.KNIGHT, UnitType.BISHOP} and roster.count(unit_type) >= 2:
        return False
    remaining_budget = DRAFT_BUDGET - sum(UNIT_COSTS[unit] for unit in roster)
    return UNIT_COSTS[unit_type] <= remaining_budget


def auto_fill_roster(roster: list[UnitType], rng: random.Random) -> list[UnitType]:
    filled = list(roster)
    while len(filled) < DRAFT_SIZE:
        choices = [unit for unit in DRAFT_POOL if can_add_unit(filled, unit)]
        if not choices:
            break
        weights = [3 if unit in {UnitType.SWORDMAN, UnitType.ARCHER} else 2 for unit in choices]
        filled.append(rng.choices(choices, weights=weights, k=1)[0])
    return filled


def build_ai_roster(seed: int) -> list[UnitType]:
    return auto_fill_roster([], random.Random(seed))


class SoundController:
    def __init__(self, project_root: Path) -> None:
        self.enabled = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.current_music: str | None = None
        self.sound_dir = project_root / "assets" / "sounds"
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.sounds = {
                "move": pygame.mixer.Sound(self.sound_dir / "sfx_move.wav"),
                "attack": pygame.mixer.Sound(self.sound_dir / "sfx_attack.wav"),
                "skill": pygame.mixer.Sound(self.sound_dir / "sfx_skill.wav"),
                "pick": pygame.mixer.Sound(self.sound_dir / "sfx_pick.wav"),
                "end_turn": pygame.mixer.Sound(self.sound_dir / "sfx_end_turn.wav"),
                "win": pygame.mixer.Sound(self.sound_dir / "sfx_win.wav"),
            }
            self.sounds["move"].set_volume(0.30)
            self.sounds["attack"].set_volume(0.42)
            self.sounds["skill"].set_volume(0.40)
            self.sounds["pick"].set_volume(0.34)
            self.sounds["end_turn"].set_volume(0.32)
            self.sounds["win"].set_volume(0.45)
            self.enabled = True
        except pygame.error:
            self.enabled = False

    def play(self, name: str) -> None:
        if not self.enabled:
            return
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def play_music(self, track_name: str) -> None:
        if not self.enabled or self.current_music == track_name:
            return
        music_path = self.sound_dir / f"bgm_{track_name}.wav"
        try:
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.set_volume(0.24 if track_name == "menu" else 0.20)
            pygame.mixer.music.play(-1)
            self.current_music = track_name
        except pygame.error:
            self.current_music = None

    def stop_music(self) -> None:
        if not self.enabled:
            return
        pygame.mixer.music.stop()
        self.current_music = None


def load_preview_sprites(project_root: Path) -> dict[UnitType, pygame.Surface]:
    sprite_dir = project_root / "assets" / "sprites"
    mapping = {
        UnitType.SWORDMAN: sprite_dir / "swordman_blue.png",
        UnitType.ARCHER: sprite_dir / "archer_blue.png",
        UnitType.MAGE: sprite_dir / "mage_blue.png",
        UnitType.KNIGHT: sprite_dir / "knight_blue.png",
        UnitType.LANCER: sprite_dir / "lancer_blue.png",
        UnitType.BISHOP: sprite_dir / "bishop_blue.png",
    }
    previews: dict[UnitType, pygame.Surface] = {}
    for unit, path in mapping.items():
        previews[unit] = pygame.transform.scale(pygame.image.load(path).convert_alpha(), (68, 68))
    return previews


def build_draft_unit_rects() -> dict[UnitType, pygame.Rect]:
    rects: dict[UnitType, pygame.Rect] = {}
    start_x = 482
    start_y = 262
    card_w = 290
    card_h = 112
    gap_x = 20
    gap_y = 22
    for index, unit in enumerate(DRAFT_POOL):
        col = index % 2
        row = index // 2
        rects[unit] = pygame.Rect(start_x + col * (card_w + gap_x), start_y + row * (card_h + gap_y), card_w, card_h)
    return rects


def build_setup_rects() -> tuple[dict[str, pygame.Rect], dict[int, pygame.Rect]]:
    map_rects: dict[str, pygame.Rect] = {}
    start_x = 164
    start_y = 334
    card_w = 280
    card_h = 108
    gap_x = 24
    gap_y = 22
    for index, (key, _, _) in enumerate(MAP_OPTIONS):
        col = index % 3
        row = index // 3
        map_rects[key] = pygame.Rect(start_x + col * (card_w + gap_x), start_y + row * (card_h + gap_y), card_w, card_h)

    difficulty_rects: dict[int, pygame.Rect] = {}
    for level in range(1, 6):
        difficulty_rects[level] = pygame.Rect(214 + (level - 1) * 130, 236, 112, 42)
    return map_rects, difficulty_rects


def draw_setup_menu(
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    map_rects: dict[str, pygame.Rect],
    difficulty_rects: dict[int, pygame.Rect],
    hovered_map: str | None,
    hovered_diff: int | None,
    selected_difficulty: int,
    selected_map: str,
) -> None:
    screen.fill(BACKGROUND_COLOR)
    card = pygame.Rect(96, 56, 1088, 608)
    pygame.draw.rect(screen, PANEL_COLOR, card, border_radius=22)
    pygame.draw.rect(screen, PANEL_BORDER, card, width=2, border_radius=22)

    screen.blit(fonts["tiny"].render("새 대국 시작", True, (255, 220, 120)), (132, 84))
    screen.blit(fonts["hero"].render("전장과 난이도 선택", True, TEXT_COLOR), (128, 104))
    screen.blit(fonts["small"].render("AI 난이도와 전장을 먼저 고른 뒤, 편성 드래프트로 넘어가세요.", True, SUBTEXT_COLOR), (132, 176))

    screen.blit(fonts["body"].render("AI 난이도", True, TEXT_COLOR), (132, 224))
    for level, rect in difficulty_rects.items():
        active = level == selected_difficulty
        fill = BUTTON_ACTIVE if active or hovered_diff == level else BUTTON_COLOR
        pygame.draw.rect(screen, fill, rect, border_radius=12)
        pygame.draw.rect(screen, PANEL_BORDER, rect, width=2, border_radius=12)
        title = ["매우 쉬움", "쉬움", "보통", "어려움", "매우 어려움"][level - 1]
        label = fonts["small"].render(title, True, TEXT_COLOR)
        screen.blit(label, label.get_rect(center=rect.center))

    screen.blit(fonts["body"].render("맵 선택", True, TEXT_COLOR), (132, 296))
    for key, title, desc in MAP_OPTIONS:
        rect = map_rects[key]
        active = key == selected_map
        fill = BUTTON_ACTIVE if active else BUTTON_COLOR
        if hovered_map == key:
            fill = (96, 126, 176) if active else (70, 86, 116)
        pygame.draw.rect(screen, fill, rect, border_radius=16)
        border = (255, 220, 120) if active else PANEL_BORDER
        pygame.draw.rect(screen, border, rect, width=2, border_radius=16)
        screen.blit(fonts["body"].render(title, True, TEXT_COLOR), (rect.x + 18, rect.y + 16))
        draw_wrapped_left(screen, fonts["small"], desc, SUBTEXT_COLOR, (rect.x + 18, rect.y + 50), rect.width - 32, 18)


def draw_draft_menu(
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    roster: list[UnitType],
    selected_unit: UnitType,
    hovered_unit: UnitType | None,
    hover_button: str | None,
    unit_rects: dict[UnitType, pygame.Rect],
    action_rects: dict[str, pygame.Rect],
    preview_sprites: dict[UnitType, pygame.Surface],
) -> None:
    screen.fill(BACKGROUND_COLOR)
    card = pygame.Rect(84, 36, 1112, 648)
    pygame.draw.rect(screen, PANEL_COLOR, card, border_radius=22)
    pygame.draw.rect(screen, PANEL_BORDER, card, width=2, border_radius=22)

    remaining = DRAFT_BUDGET - sum(UNIT_COSTS[unit] for unit in roster)
    screen.blit(fonts["title"].render("편성 드래프트", True, TEXT_COLOR), (118, 66))
    screen.blit(fonts["body"].render(f"예산 {remaining}/{DRAFT_BUDGET}", True, (255, 220, 120)), (118, 112))
    screen.blit(fonts["small"].render("왕은 자동 포함입니다. 보조 기물은 3~7개까지 선택할 수 있습니다.", True, SUBTEXT_COLOR), (118, 144))

    summary = pygame.Rect(118, 176, 318, 430)
    pygame.draw.rect(screen, (17, 22, 34), summary, border_radius=16)
    pygame.draw.rect(screen, PANEL_BORDER, summary, width=2, border_radius=16)
    screen.blit(fonts["body"].render("선택한 조합", True, TEXT_COLOR), (138, 194))
    screen.blit(fonts["small"].render("기본 포함: 왕", True, SUBTEXT_COLOR), (138, 226))

    for idx in range(DRAFT_SIZE):
        y = 254 + idx * 39
        slot_rect = pygame.Rect(134, y, 286, 32)
        pygame.draw.rect(screen, (35, 42, 60), slot_rect, border_radius=10)
        if idx < len(roster):
            unit = roster[idx]
            label = f"{idx + 1}. {UNIT_DISPLAY_NAMES[unit]}  비용 {UNIT_COSTS[unit]}"
            screen.blit(fonts["small"].render(label, True, TEXT_COLOR), (148, y + 7))
        else:
            screen.blit(fonts["small"].render(f"{idx + 1}. 빈 슬롯", True, SUBTEXT_COLOR), (148, y + 7))

    preview_box = pygame.Rect(134, 532, 286, 52)
    pygame.draw.rect(screen, (28, 34, 52), preview_box, border_radius=12)
    pygame.draw.rect(screen, PANEL_BORDER, preview_box, width=1, border_radius=12)
    screen.blit(preview_sprites[selected_unit], (140, 524))
    screen.blit(fonts["body"].render(UNIT_DISPLAY_NAMES[selected_unit], True, TEXT_COLOR), (214, 540))
    screen.blit(fonts["small"].render(f"비용 {UNIT_COSTS[selected_unit]}", True, (255, 220, 120)), (214, 565))

    screen.blit(fonts["body"].render("기물 선택", True, TEXT_COLOR), (482, 194))
    screen.blit(fonts["small"].render("카드를 눌러 편성하세요. 기마와 비숍은 각각 최대 2개까지 선택할 수 있습니다.", True, SUBTEXT_COLOR), (482, 226))

    for unit, rect in unit_rects.items():
        enabled = can_add_unit(roster, unit)
        fill = BUTTON_ACTIVE if hovered_unit == unit and enabled else BUTTON_COLOR if enabled else (43, 48, 58)
        pygame.draw.rect(screen, fill, rect, border_radius=14)
        pygame.draw.rect(screen, PANEL_BORDER, rect, width=2, border_radius=14)
        screen.blit(preview_sprites[unit], (rect.x + 14, rect.y + 16))
        screen.blit(fonts["body"].render(UNIT_DISPLAY_NAMES[unit], True, TEXT_COLOR), (rect.x + 92, rect.y + 14))
        cost_surface = fonts["small"].render(f"비용 {UNIT_COSTS[unit]}", True, (255, 220, 120))
        screen.blit(cost_surface, (rect.right - cost_surface.get_width() - 16, rect.y + 18))
        draw_wrapped_left(screen, fonts["small"], UNIT_DRAFT_BLURBS[unit], SUBTEXT_COLOR, (rect.x + 92, rect.y + 50), rect.width - 112, 16)
        if unit == selected_unit:
            pygame.draw.rect(screen, (255, 220, 120), rect, width=2, border_radius=14)

    labels = {"undo": "마지막 제거", "fill": "자동 채우기", "start": "전투 시작"}
    for key, rect in action_rects.items():
        enabled = (key != "start" or len(roster) >= 3) and (key != "undo" or bool(roster))
        fill = BUTTON_ACTIVE if hover_button == key and enabled else BUTTON_COLOR if enabled else (43, 48, 58)
        pygame.draw.rect(screen, fill, rect, border_radius=14)
        pygame.draw.rect(screen, PANEL_BORDER, rect, width=2, border_radius=14)
        screen.blit(fonts["body"].render(labels[key], True, TEXT_COLOR), fonts["body"].render(labels[key], True, TEXT_COLOR).get_rect(center=rect.center))

    footer = "고코스트 기물을 선택할수록 저코스트 기물 수가 줄어듭니다. 예산 안에서 조합을 완성하세요."
    draw_wrapped_left(screen, fonts["small"], footer, SUBTEXT_COLOR, (118, 664), 820, 18)


def draw_game_over_overlay(
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    winner_text: str,
    button_rect: pygame.Rect,
    hovered: bool,
) -> None:
    veil = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    veil.fill((8, 10, 18, 148))
    screen.blit(veil, (0, 0))
    panel = pygame.Rect(414, 252, 452, 204)
    pygame.draw.rect(screen, PANEL_COLOR, panel, border_radius=22)
    pygame.draw.rect(screen, PANEL_BORDER, panel, width=2, border_radius=22)
    screen.blit(fonts["title"].render("대국 종료", True, TEXT_COLOR), (panel.x + 34, panel.y + 26))
    screen.blit(fonts["body"].render(winner_text, True, TEXT_COLOR), (panel.x + 36, panel.y + 86))
    screen.blit(fonts["small"].render("버튼을 누르면 메인 화면으로 돌아갑니다.", True, SUBTEXT_COLOR), (panel.x + 36, panel.y + 118))
    fill = BUTTON_ACTIVE if hovered else BUTTON_COLOR
    pygame.draw.rect(screen, fill, button_rect, border_radius=14)
    pygame.draw.rect(screen, PANEL_BORDER, button_rect, width=2, border_radius=14)
    label = fonts["body"].render("메인 화면", True, TEXT_COLOR)
    screen.blit(label, label.get_rect(center=button_rect.center))


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

    project_root = Path(__file__).resolve().parent
    sounds = SoundController(project_root)
    preview_sprites = load_preview_sprites(project_root)
    map_rects, difficulty_rects = build_setup_rects()
    unit_rects = build_draft_unit_rects()
    action_rects = {
        "undo": pygame.Rect(118, 606, 164, 42),
        "fill": pygame.Rect(300, 606, 164, 42),
        "start": pygame.Rect(916, 606, 166, 42),
    }
    return_button_rect = pygame.Rect(528, 404, 224, 42)

    game: GameManager | None = None
    renderer: Renderer | None = None
    rng = random.Random()
    mode = "setup"
    blocked_tiles = set(Board.default_obstacles())
    selected_map = "classic"
    player_roster: list[UnitType] = []
    selected_preview = UnitType.SWORDMAN
    selected_difficulty = 3
    running = True
    last_music_mode: str | None = None

    while running:
        dt = clock.tick(FPS) / 1000.0
        mouse_pos = pygame.mouse.get_pos()
        hovered_map = next((key for key, rect in map_rects.items() if rect.collidepoint(mouse_pos)), None) if mode == "setup" else None
        hovered_diff = next((level for level, rect in difficulty_rects.items() if rect.collidepoint(mouse_pos)), None) if mode == "setup" else None
        hovered_unit = next((unit for unit, rect in unit_rects.items() if rect.collidepoint(mouse_pos)), None) if mode == "draft" else None
        hovered_action = next((key for key, rect in action_rects.items() if rect.collidepoint(mouse_pos)), None) if mode == "draft" else None
        hovered_return = mode == "game" and game is not None and game.state == GameState.GAME_OVER and return_button_rect.collidepoint(mouse_pos)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif mode == "setup" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked_diff = next((level for level, rect in difficulty_rects.items() if rect.collidepoint(event.pos)), None)
                if clicked_diff is not None:
                    selected_difficulty = clicked_diff
                    continue
                clicked_map = next((key for key, rect in map_rects.items() if rect.collidepoint(event.pos)), None)
                if clicked_map is not None:
                    selected_map = clicked_map
                    blocked_tiles = Board.preset_obstacles(clicked_map, rng)
                    player_roster = []
                    mode = "draft"
            elif mode == "draft" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked_unit = next((unit for unit, rect in unit_rects.items() if rect.collidepoint(event.pos)), None)
                if clicked_unit is not None:
                    selected_preview = clicked_unit
                    if can_add_unit(player_roster, clicked_unit):
                        player_roster.append(clicked_unit)
                        sounds.play("pick")
                elif action_rects["undo"].collidepoint(event.pos) and player_roster:
                    player_roster.pop()
                elif action_rects["fill"].collidepoint(event.pos):
                    player_roster = auto_fill_roster(player_roster, rng)
                elif action_rects["start"].collidepoint(event.pos) and len(player_roster) >= 3:
                    ai_roster = build_ai_roster(rng.randint(0, 1_000_000))
                    game = GameManager(
                        project_root,
                        blocked_tiles=blocked_tiles,
                        player_roster=player_roster,
                        ai_roster=ai_roster,
                        ai_difficulty=selected_difficulty,
                        map_name=selected_map,
                    )
                    renderer = Renderer(screen, project_root)
                    mode = "game"
            elif mode == "game":
                assert game is not None
                if game.state == GameState.GAME_OVER and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and return_button_rect.collidepoint(event.pos):
                    game = None
                    renderer = None
                    player_roster = []
                    mode = "setup"
                    continue
                game.handle_event(event)

        if mode == "game" and game is not None and game.state == GameState.GAME_OVER:
            if last_music_mode is not None:
                sounds.stop_music()
                last_music_mode = None
        else:
            desired_music = "battle" if mode == "game" else "menu"
            if desired_music != last_music_mode:
                sounds.play_music(desired_music)
                last_music_mode = desired_music

        if mode == "setup":
            draw_setup_menu(screen, fonts, map_rects, difficulty_rects, hovered_map, hovered_diff, selected_difficulty, selected_map)
        elif mode == "draft":
            draw_draft_menu(screen, fonts, player_roster, selected_preview, hovered_unit, hovered_action, unit_rects, action_rects, preview_sprites)
        else:
            assert game is not None and renderer is not None
            game.update(dt)
            for sound_name in game.drain_sound_events():
                sounds.play(sound_name)
            renderer.draw(game)
            if game.state == GameState.GAME_OVER:
                winner_text = "승리: 청 진영" if game.winner == Team.PLAYER else "패배: 적 진영"
                draw_game_over_overlay(screen, fonts, winner_text, return_button_rect, bool(hovered_return))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
