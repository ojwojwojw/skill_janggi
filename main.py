from __future__ import annotations

from pathlib import Path
import random
import sys

import pygame

from game.board import Board
from game.constants import (
    AI_BUDGET_BY_DIFFICULTY,
    BACKGROUND_COLOR,
    BOARD_ORIGIN,
    BOARD_PIXEL_SIZE,
    BUTTON_ACTIVE,
    BUTTON_COLOR,
    DRAFT_BUDGET,
    DRAFT_POOL,
    DRAFT_SIZE,
    FPS,
    PANEL_BORDER,
    PANEL_COLOR,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SUBTEXT_COLOR,
    TEXT_COLOR,
    TILE_SIZE,
    UNIT_COSTS,
    UnitType,
)
from game.game_manager import AI_HOME_POSITIONS, BASE_HP, PLAYER_HOME_POSITIONS, PLAYER_KING_POS, GameManager
from game.renderer import Renderer, board_tile_at_pixel
from game.skill import SKILLS
from game.unit import ATTACK_POWER, Unit


MAP_OPTIONS = [
    ("classic", "기본 전장", "중앙 장애물만 있는 균형형 전장입니다."),
    ("wings", "측면 압박", "좌우 통로가 넓어 측면 전개가 중요합니다."),
    ("river", "강 전장", "중앙 강줄기를 사이에 두고 우회해야 합니다."),
    ("fort", "요새 전장", "좁은 입구를 막고 버티기 좋은 전장입니다."),
    ("cross", "십자 전장", "십자 통로를 먼저 장악하면 유리합니다."),
    ("diamond", "마름모 거점", "중앙 대각 거점을 선점하면 압박력이 높아집니다."),
    ("lanes", "양측 차선", "좌우 차선이 길게 열려 측면 전개가 중요합니다."),
    ("chaos", "혼전 전장", "장애물이 많아 교전 각이 자주 바뀝니다."),
]

DIFFICULTY_TITLES = {
    1: "매우 쉬움",
    2: "쉬움",
    3: "보통",
    4: "어려움",
    5: "매우 어려움",
    6: "악몽",
    7: "괴물",
}

UNIT_LABELS = {
    UnitType.KING: "왕",
    UnitType.SWORDMAN: "검사",
    UnitType.ARCHER: "궁수",
    UnitType.MAGE: "술사",
    UnitType.KNIGHT: "기마",
    UnitType.BISHOP: "사제",
    UnitType.LANCER: "창병",
}

UNIT_DRAFT_BLURBS_LOCAL = {
    UnitType.SWORDMAN: "직선 돌진과 압박이 강한 근접 유닛.",
    UnitType.ARCHER: "멀리서 끊어치는 견제형 원거리 유닛.",
    UnitType.MAGE: "범위 피해로 전열을 흔드는 광역 유닛.",
    UnitType.KNIGHT: "기동력으로 측면을 찌르는 돌파 유닛.",
    UnitType.BISHOP: "고 코스트 이지만 대각 공격에 능한 고급 유닛.",
    UnitType.LANCER: "돌진으로 적을 끝까지 밀어내는 유닛.",
    UnitType.KING: "전장의 중심이 되는 핵심 유닛.",
}

UNIT_DRAFT_BLURBS_LOCAL[UnitType.MAGE] = "고 코스트 범위 피해로 전열을 흔드는 광역 유닛."
UNIT_DRAFT_BLURBS_LOCAL[UnitType.BISHOP] = "대각 공격에 능한 고급 유닛."

UNIT_SKILL_TEXT = {
    UnitType.KING: ("왕의 수호", "아군 한 기에게 보호막을 부여합니다."),
    UnitType.SWORDMAN: ("돌진", "직선으로 밀고 들어가 적을 강하게 압박합니다."),
    UnitType.ARCHER: ("관통 사격", "직선 경로를 따라 연속으로 적을 꿰뚫습니다."),
    UnitType.MAGE: ("화염 폭발", "지정한 3x3 범위를 불태웁니다."),
    UnitType.KNIGHT: ("도약 강타", "순간 돌진으로 측면을 파고듭니다."),
    UnitType.BISHOP: ("대각 성광", "대각선 방향으로 긴 광선을 발사합니다."),
    UnitType.LANCER: ("관통 돌진", "직선으로 돌진해 적을 찌르고 끝까지 밀어냅니다."),
}

MOVE_STYLE_LABELS = {
    UnitType.KING: "상하좌우 1칸",
    UnitType.SWORDMAN: "직선 2칸",
    UnitType.ARCHER: "상하좌우 1칸",
    UnitType.MAGE: "대각 1칸",
    UnitType.KNIGHT: "나이트 점프",
    UnitType.BISHOP: "대각 최대 3칸",
    UnitType.LANCER: "직선 2칸",
}


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


def draft_budget_for_difficulty(difficulty: int) -> int | None:
    if difficulty >= 6:
        return None
    return DRAFT_BUDGET


def can_add_unit(roster: list[UnitType], unit_type: UnitType, difficulty: int = 3) -> bool:
    if len(roster) >= DRAFT_SIZE:
        return False
    if unit_type in {UnitType.KNIGHT, UnitType.BISHOP, UnitType.MAGE, UnitType.LANCER} and roster.count(unit_type) >= 2:
        return False
    budget = draft_budget_for_difficulty(difficulty)
    if budget is None:
        return True
    remaining_budget = budget - sum(UNIT_COSTS[unit] for unit in roster)
    return UNIT_COSTS[unit_type] <= remaining_budget


def auto_fill_roster(
    roster: list[UnitType],
    rng: random.Random,
    difficulty: int = 3,
    preferred_weights: dict[UnitType, int] | None = None,
) -> list[UnitType]:
    filled = list(roster)
    while len(filled) < DRAFT_SIZE:
        choices = [unit for unit in DRAFT_POOL if can_add_unit(filled, unit, difficulty)]
        if not choices:
            break
        weights = [
            preferred_weights.get(unit, 3 if unit in {UnitType.SWORDMAN, UnitType.ARCHER} else 2)
            if preferred_weights
            else (3 if unit in {UnitType.SWORDMAN, UnitType.ARCHER} else 2)
            for unit in choices
        ]
        filled.append(rng.choices(choices, weights=weights, k=1)[0])
    return filled


def codex_detail_lines(unit_type: UnitType) -> list[str]:
    probe = Unit("codex", "codex", unit_type, team=None, hp=BASE_HP[unit_type], max_hp=BASE_HP[unit_type], position=(3, 3))  # type: ignore[arg-type]
    board = Board()
    move_tiles = len(probe.basic_move_targets(board, []))
    attack_tiles = len(probe.attack_preview_tiles(board))
    skill_name, skill_description = UNIT_SKILL_TEXT[unit_type]
    skill_cooldown = SKILLS[unit_type].cooldown
    cost_text = "고정" if unit_type == UnitType.KING else str(UNIT_COSTS.get(unit_type, "-"))
    return [
        f"체력 {BASE_HP[unit_type]}  |  공격력 {ATTACK_POWER[unit_type]}  |  비용 {cost_text}",
        f"이동 {MOVE_STYLE_LABELS[unit_type]}  |  이동 후보 {move_tiles}",
        f"기본 공격 범위 후보 {attack_tiles}",
        f"스킬 {skill_name}  |  쿨다운 {skill_cooldown}",
        skill_description,
    ]


def build_ai_roster(seed: int, difficulty: int) -> list[UnitType]:
    rng = random.Random(seed)
    if difficulty >= 6:
        elite_pool = [
            UnitType.KNIGHT,
            UnitType.BISHOP,
            UnitType.MAGE,
            UnitType.LANCER,
        ]
        limits = {unit: 2 for unit in elite_pool}
        weights = {
            UnitType.KNIGHT: 4 if difficulty == 6 else 5,
            UnitType.BISHOP: 4 if difficulty == 6 else 5,
            UnitType.MAGE: 4 if difficulty == 6 else 5,
            UnitType.LANCER: 4 if difficulty == 6 else 5,
        }
        roster: list[UnitType] = []
        while len(roster) < DRAFT_SIZE:
            choices = [
                unit
                for unit in elite_pool
                if roster.count(unit) < limits[unit]
            ]
            if not choices:
                break
            picked = rng.choices(choices, weights=[weights[unit] for unit in choices], k=1)[0]
            roster.append(picked)
        if len(roster) < DRAFT_SIZE:
            roster.extend(auto_fill_roster(roster, rng, difficulty=difficulty)[: DRAFT_SIZE - len(roster)])
        return roster[:DRAFT_SIZE]

    if difficulty >= 5:
        preferred = {
            UnitType.SWORDMAN: 1,
            UnitType.ARCHER: 2,
            UnitType.KNIGHT: 5,
            UnitType.BISHOP: 6,
        }
    elif difficulty >= 4:
        preferred = {
            UnitType.SWORDMAN: 2,
            UnitType.ARCHER: 2,
            UnitType.KNIGHT: 4,
            UnitType.BISHOP: 4,
        }
    else:
        preferred = None
    return auto_fill_roster([], rng, difficulty=difficulty, preferred_weights=preferred)


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
            volume = 0.24 if track_name == "menu" else 0.22 if track_name == "boss" else 0.20
            pygame.mixer.music.set_volume(volume)
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
        UnitType.KING: sprite_dir / "king_blue.png",
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
    start_y = 266
    card_w = 290
    card_h = 92
    gap_x = 20
    gap_y = 18
    for index, unit in enumerate(DRAFT_POOL):
        col = index % 2
        row = index // 2
        rects[unit] = pygame.Rect(start_x + col * (card_w + gap_x), start_y + row * (card_h + gap_y), card_w, card_h)
    return rects


def build_setup_rects() -> tuple[dict[str, pygame.Rect], dict[int, pygame.Rect]]:
    map_rects: dict[str, pygame.Rect] = {}
    start_x = 136
    start_y = 384
    card_w = 226
    card_h = 102
    gap_x = 18
    gap_y = 14
    for index, (key, _, _) in enumerate(MAP_OPTIONS):
        col = index % 4
        row = index // 4
        map_rects[key] = pygame.Rect(start_x + col * (card_w + gap_x), start_y + row * (card_h + gap_y), card_w, card_h)

    difficulty_rects: dict[int, pygame.Rect] = {}
    diff_start_x = 148
    diff_start_y = 234
    diff_w = 188
    diff_h = 42
    diff_gap_x = 14
    diff_gap_y = 16
    for index, level in enumerate(range(1, 8)):
        col = index % 4
        row = index // 4
        difficulty_rects[level] = pygame.Rect(
            diff_start_x + col * (diff_w + diff_gap_x),
            diff_start_y + row * (diff_h + diff_gap_y),
            diff_w,
            diff_h,
        )
    return map_rects, difficulty_rects


def build_setup_action_rect() -> pygame.Rect:
    return pygame.Rect(772, 604, 288, 56)


def build_codex_button_rect() -> pygame.Rect:
    return pygame.Rect(492, 618, 232, 40)


def build_codex_unit_rects() -> dict[UnitType, pygame.Rect]:
    rects: dict[UnitType, pygame.Rect] = {}
    start_x = 132
    start_y = 196
    card_w = 204
    card_h = 96
    gap_x = 16
    gap_y = 18
    for index, unit in enumerate(UnitType):
        col = index % 4
        row = index // 4
        rects[unit] = pygame.Rect(start_x + col * (card_w + gap_x), start_y + row * (card_h + gap_y), card_w, card_h)
    return rects


def build_deployment_action_rects() -> dict[str, pygame.Rect]:
    return {
        "auto": pygame.Rect(846, 590, 158, 40),
        "clear": pygame.Rect(1022, 590, 158, 40),
        "start": pygame.Rect(846, 636, 334, 38),
    }


def auto_arrange_player_positions(roster: list[UnitType], blocked_tiles: set[tuple[int, int]]) -> list[tuple[int, int]]:
    temp = GameManager(
        Path("."),
        blocked_tiles=blocked_tiles,
        player_roster=roster,
        ai_roster=roster,
    )
    return [unit.position for unit in temp.units if unit.team.name == "PLAYER" and unit.unit_type != UnitType.KING]


def draw_setup_menu(
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    map_rects: dict[str, pygame.Rect],
    difficulty_rects: dict[int, pygame.Rect],
    hovered_map: str | None,
    hovered_diff: int | None,
    selected_difficulty: int,
    selected_map: str,
    start_rect: pygame.Rect,
    hovered_start: bool,
    codex_rect: pygame.Rect,
    hovered_codex: bool,
) -> None:
    screen.fill(BACKGROUND_COLOR)
    card = pygame.Rect(96, 56, 1088, 608)
    pygame.draw.rect(screen, PANEL_COLOR, card, border_radius=22)
    pygame.draw.rect(screen, PANEL_BORDER, card, width=2, border_radius=22)

    screen.blit(fonts["tiny"].render("BATTLE SETUP", True, (255, 220, 120)), (132, 84))
    screen.blit(fonts["hero"].render("전장과 난이도 선택", True, TEXT_COLOR), (128, 104))
    screen.blit(fonts["small"].render("난이도와 맵을 고른 뒤 게임 시작 버튼으로 다음 단계로 이동합니다.", True, SUBTEXT_COLOR), (132, 176))

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

    for rect, label, hovered in (
        (start_rect, "게임 시작", hovered_start),
        (codex_rect, "기물도감", hovered_codex),
    ):
        fill = BUTTON_ACTIVE if hovered else BUTTON_COLOR
        pygame.draw.rect(screen, fill, rect, border_radius=14)
        pygame.draw.rect(screen, PANEL_BORDER, rect, width=2, border_radius=14)
        surface = fonts["body"].render(label, True, TEXT_COLOR)
        screen.blit(surface, surface.get_rect(center=rect.center))

    # Redraw the setup actions so the swapped positions are visually clear and
    # the primary CTA stands out more strongly than the codex shortcut.
    pygame.draw.rect(screen, BUTTON_COLOR, codex_rect, border_radius=14)
    pygame.draw.rect(screen, PANEL_BORDER, codex_rect, width=2, border_radius=14)
    codex_surface = fonts["body"].render("기물도감", True, TEXT_COLOR)
    screen.blit(codex_surface, codex_surface.get_rect(center=codex_rect.center))

    start_glow = start_rect.inflate(18, 14)
    start_glow_color = (112, 166, 255) if hovered_start else (82, 138, 224)
    pygame.draw.rect(screen, start_glow_color, start_glow, border_radius=20)
    start_fill = (104, 148, 224) if hovered_start else (84, 128, 208)
    pygame.draw.rect(screen, start_fill, start_rect, border_radius=14)
    pygame.draw.rect(screen, (255, 230, 150), start_rect, width=2, border_radius=14)
    start_surface = fonts["title"].render("게임 시작", True, TEXT_COLOR)
    screen.blit(start_surface, start_surface.get_rect(center=start_rect.center))


def draw_draft_menu(
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    roster: list[UnitType],
    selected_difficulty: int,
    selected_unit: UnitType,
    hovered_unit: UnitType | None,
    hover_button: str | None,
    unit_rects: dict[UnitType, pygame.Rect],
    action_rects: dict[str, pygame.Rect],
    preview_sprites: dict[UnitType, pygame.Surface],
) -> None:
    screen.fill(BACKGROUND_COLOR)
    card = pygame.Rect(84, 26, 1112, 666)
    pygame.draw.rect(screen, PANEL_COLOR, card, border_radius=22)
    pygame.draw.rect(screen, PANEL_BORDER, card, width=2, border_radius=22)

    draft_budget = draft_budget_for_difficulty(selected_difficulty)
    remaining = None if draft_budget is None else draft_budget - sum(UNIT_COSTS[unit] for unit in roster)
    budget_text = "예산 제한 없음" if draft_budget is None else f"예산 {remaining}/{draft_budget}"
    screen.blit(fonts["title"].render("기물 드래프트", True, TEXT_COLOR), (118, 66))
    screen.blit(fonts["body"].render(budget_text, True, (255, 220, 120)), (118, 112))
    screen.blit(fonts["small"].render("왕은 자동 포함됩니다. 기물 상세 정보는 메인 화면의 기물도감에서 확인할 수 있습니다.", True, SUBTEXT_COLOR), (118, 144))

    summary = pygame.Rect(118, 188, 318, 432)
    pygame.draw.rect(screen, (17, 22, 34), summary, border_radius=16)
    pygame.draw.rect(screen, PANEL_BORDER, summary, width=2, border_radius=16)
    screen.blit(fonts["body"].render("선택한 편성", True, TEXT_COLOR), (138, 194))
    screen.blit(fonts["small"].render("왕은 자동 포함됩니다.", True, SUBTEXT_COLOR), (138, 226))

    for idx in range(DRAFT_SIZE):
        y = 268 + idx * 41
        slot_rect = pygame.Rect(134, y, 286, 32)
        pygame.draw.rect(screen, (35, 42, 60), slot_rect, border_radius=10)
        if idx < len(roster):
            unit = roster[idx]
            label = f"{idx + 1}. {UNIT_LABELS[unit]}  비용 {UNIT_COSTS[unit]}"
            screen.blit(fonts["small"].render(label, True, TEXT_COLOR), (148, y + 7))
        else:
            screen.blit(fonts["small"].render(f"{idx + 1}. 빈 슬롯", True, SUBTEXT_COLOR), (148, y + 7))

    screen.blit(fonts["body"].render("기물 선택", True, TEXT_COLOR), (482, 194))
    screen.blit(fonts["small"].render("카드를 눌러 추가하세요. 악몽과 괴물은 예산 제한이 없고, 7칸 편성만 유지됩니다.", True, SUBTEXT_COLOR), (482, 226))

    for unit, rect in unit_rects.items():
        enabled = can_add_unit(roster, unit, selected_difficulty)
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

    labels = {"undo": "마지막 제거", "fill": "자동 채우기", "start": "전투 시작"}
    for key, rect in action_rects.items():
        enabled = (key != "start" or len(roster) >= 3) and (key != "undo" or bool(roster))
        fill = BUTTON_ACTIVE if hover_button == key and enabled else BUTTON_COLOR if enabled else (43, 48, 58)
        pygame.draw.rect(screen, fill, rect, border_radius=14)
        pygame.draw.rect(screen, PANEL_BORDER, rect, width=2, border_radius=14)
        label_surface = fonts["body"].render(labels[key], True, TEXT_COLOR)
        screen.blit(label_surface, label_surface.get_rect(center=rect.center))

    footer = "악몽과 괴물은 플레이어 예산 제한이 없습니다. 대신 기물 수는 같으니 역할 조합과 배치가 더 중요합니다."
    draw_wrapped_left(screen, fonts["small"], footer, SUBTEXT_COLOR, (118, 632), 600, 16)


def draw_deployment_menu(
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
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
    king_label = fonts["tiny"].render("KING", True, (255, 230, 160))
    screen.blit(king_label, (king_px + 8, king_py + 8))

    for idx, tile in placements.items():
        unit = roster[idx]
        px = BOARD_ORIGIN[0] + tile[0] * TILE_SIZE
        py = BOARD_ORIGIN[1] + tile[1] * TILE_SIZE
        screen.blit(preview_sprites[unit], (px, py))
        if selected_index == idx:
            pygame.draw.rect(screen, (255, 220, 120), (px + 3, py + 3, TILE_SIZE - 6, TILE_SIZE - 6), width=3, border_radius=10)

    panel = pygame.Rect(820, 42, 404, 636)
    pygame.draw.rect(screen, PANEL_COLOR, panel, border_radius=18)
    pygame.draw.rect(screen, PANEL_BORDER, panel, width=2, border_radius=18)
    screen.blit(fonts["title"].render("배치 단계", True, TEXT_COLOR), (846, 64))
    draw_wrapped_left(
        screen,
        fonts["small"],
        "전투 시작 전에 아군 기물을 원하는 칸에 배치하세요. 왕은 고정 배치입니다.",
        SUBTEXT_COLOR,
        (846, 106),
        340,
        18,
    )
    screen.blit(fonts["small"].render("파란 칸 안에서만 배치할 수 있습니다.", True, (160, 214, 255)), (846, 154))

    for idx, unit in enumerate(roster):
        rect = pygame.Rect(842, 190 + idx * 54, 360, 44)
        active = idx == selected_index
        filled = idx in placements
        fill = BUTTON_ACTIVE if active else (56, 68, 92) if filled else (40, 46, 58)
        pygame.draw.rect(screen, fill, rect, border_radius=12)
        pygame.draw.rect(screen, PANEL_BORDER, rect, width=2, border_radius=12)
        thumb = pygame.transform.scale(preview_sprites[unit], (38, 38))
        screen.blit(thumb, (rect.x + 8, rect.y + 3))
        state = f"{placements[idx]}" if filled else "미배치"
        screen.blit(fonts["body"].render(UNIT_LABELS[unit], True, TEXT_COLOR), (rect.x + 54, rect.y + 9))
        screen.blit(fonts["small"].render(state, True, SUBTEXT_COLOR), (rect.right - 102, rect.y + 13))

    help_text = "보드 칸을 누르면 선택한 기물이 그 위치에 배치됩니다." if selected_index is not None else "오른쪽 목록에서 먼저 기물을 선택하세요."
    draw_wrapped_left(screen, fonts["small"], help_text, SUBTEXT_COLOR, (252, 654), 544, 18)

    labels = {"auto": "자동 배치", "clear": "초기화", "start": "전투 시작"}
    ready = len(placements) == len(roster)
    for key, rect in action_rects.items():
        enabled = key != "start" or ready
        fill = BUTTON_ACTIVE if hover_action == key and enabled else BUTTON_COLOR if enabled else (43, 48, 58)
        pygame.draw.rect(screen, fill, rect, border_radius=12)
        pygame.draw.rect(screen, PANEL_BORDER, rect, width=2, border_radius=12)
        label = fonts["body"].render(labels[key], True, TEXT_COLOR)
        screen.blit(label, label.get_rect(center=rect.center))


def draw_codex_menu(
    screen: pygame.Surface,
    fonts: dict[str, pygame.font.Font],
    unit_rects: dict[UnitType, pygame.Rect],
    selected_unit: UnitType,
    hovered_unit: UnitType | None,
    preview_sprites: dict[UnitType, pygame.Surface],
    back_rect: pygame.Rect,
    hovered_back: bool,
) -> None:
    screen.fill(BACKGROUND_COLOR)
    card = pygame.Rect(84, 30, 1112, 660)
    pygame.draw.rect(screen, PANEL_COLOR, card, border_radius=22)
    pygame.draw.rect(screen, PANEL_BORDER, card, width=2, border_radius=22)

    screen.blit(fonts["tiny"].render("UNIT CODEX", True, (255, 220, 120)), (122, 64))
    screen.blit(fonts["title"].render("기물도감", True, TEXT_COLOR), (118, 88))
    screen.blit(fonts["small"].render("기물을 선택해 체력, 공격력, 이동, 스킬 정보를 자세히 확인하세요.", True, SUBTEXT_COLOR), (118, 130))

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
    pygame.draw.rect(screen, (17, 22, 34), detail, border_radius=18)
    pygame.draw.rect(screen, PANEL_BORDER, detail, width=2, border_radius=18)
    screen.blit(preview_sprites[selected_unit], (142, 458))
    screen.blit(fonts["title"].render(UNIT_LABELS[selected_unit], True, TEXT_COLOR), (232, 458))
    y = 504
    for index, line in enumerate(codex_detail_lines(selected_unit)):
        color = (255, 220, 120) if index in {0, 3} else SUBTEXT_COLOR
        draw_wrapped_left(screen, fonts["small"], line, color, (232, y), 814, 18)
        y += 30 if index == 4 else 22

    shortcut_title = fonts["small"].render("전투 단축키", True, (255, 220, 120))
    screen.blit(shortcut_title, (720, 454))
    shortcut_text = "Q: 스킬 선택  |  A: 공격 선택  |  M / Esc: 이동 선택"
    draw_wrapped_left(screen, fonts["small"], shortcut_text, SUBTEXT_COLOR, (720, 480), 320, 18)

    back_fill = BUTTON_ACTIVE if hovered_back else BUTTON_COLOR
    pygame.draw.rect(screen, back_fill, back_rect, border_radius=14)
    pygame.draw.rect(screen, PANEL_BORDER, back_rect, width=2, border_radius=14)
    back_label = fonts["body"].render("뒤로 가기", True, TEXT_COLOR)
    screen.blit(back_label, back_label.get_rect(center=back_rect.center))


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
    screen.blit(fonts["title"].render("게임 종료", True, TEXT_COLOR), (panel.x + 34, panel.y + 26))
    screen.blit(fonts["body"].render(winner_text, True, TEXT_COLOR), (panel.x + 36, panel.y + 86))
    screen.blit(fonts["small"].render("버튼을 누르면 메인 화면으로 돌아갑니다.", True, SUBTEXT_COLOR), (panel.x + 36, panel.y + 118))
    fill = BUTTON_ACTIVE if hovered else BUTTON_COLOR
    pygame.draw.rect(screen, fill, button_rect, border_radius=14)
    pygame.draw.rect(screen, PANEL_BORDER, button_rect, width=2, border_radius=14)
    label = fonts["body"].render("메인 화면", True, TEXT_COLOR)
    screen.blit(label, label.get_rect(center=button_rect.center))


def resolve_app_paths() -> tuple[Path, Path]:
    if getattr(sys, "frozen", False):
        asset_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        data_root = Path(sys.executable).resolve().parent
    else:
        asset_root = Path(__file__).resolve().parent
        data_root = asset_root
    return asset_root, data_root


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
    map_rects, difficulty_rects = build_setup_rects()
    setup_start_rect = build_setup_action_rect()
    codex_button_rect = build_codex_button_rect()
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

    game: GameManager | None = None
    renderer: Renderer | None = None
    ai_roster: list[UnitType] = []
    rng = random.Random()
    mode = "setup"
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

    while running:
        dt = clock.tick(FPS) / 1000.0
        mouse_pos = pygame.mouse.get_pos()
        hovered_map = next((key for key, rect in map_rects.items() if rect.collidepoint(mouse_pos)), None) if mode == "setup" else None
        hovered_diff = next((level for level, rect in difficulty_rects.items() if rect.collidepoint(mouse_pos)), None) if mode == "setup" else None
        hovered_setup_start = mode == "setup" and setup_start_rect.collidepoint(mouse_pos)
        hovered_setup_codex = mode == "setup" and codex_button_rect.collidepoint(mouse_pos)
        hovered_codex_unit = next((unit for unit, rect in codex_unit_rects.items() if rect.collidepoint(mouse_pos)), None) if mode == "codex" else None
        hovered_codex_back = mode == "codex" and codex_back_rect.collidepoint(mouse_pos)
        hovered_unit = next((unit for unit, rect in unit_rects.items() if rect.collidepoint(mouse_pos)), None) if mode == "draft" else None
        hovered_action = next((key for key, rect in action_rects.items() if rect.collidepoint(mouse_pos)), None) if mode == "draft" else None
        hovered_deploy_action = next((key for key, rect in deployment_action_rects.items() if rect.collidepoint(mouse_pos)), None) if mode == "deployment" else None
        hovered_return = mode == "game" and game is not None and game.state.name == "GAME_OVER" and return_button_rect.collidepoint(mouse_pos)

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
                    continue
                if setup_start_rect.collidepoint(event.pos):
                    player_roster = []
                    player_placements = {}
                    selected_deploy_index = None
                    mode = "draft"
                elif codex_button_rect.collidepoint(event.pos):
                    mode = "codex"
            elif mode == "codex" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked_codex_unit = next((unit for unit, rect in codex_unit_rects.items() if rect.collidepoint(event.pos)), None)
                if clicked_codex_unit is not None:
                    selected_codex_unit = clicked_codex_unit
                elif codex_back_rect.collidepoint(event.pos):
                    mode = "setup"
            elif mode == "draft" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked_unit = next((unit for unit, rect in unit_rects.items() if rect.collidepoint(event.pos)), None)
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
                    rect = pygame.Rect(842, 190 + idx * 54, 360, 44)
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
                    renderer = Renderer(screen, asset_root)
                    mode = "game"
            elif mode == "game":
                assert game is not None
                if game.state.name == "GAME_OVER" and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and return_button_rect.collidepoint(event.pos):
                    game = None
                    renderer = None
                    player_roster = []
                    player_placements = {}
                    selected_deploy_index = None
                    mode = "setup"
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

        if mode == "setup":
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
                codex_button_rect,
                hovered_setup_codex,
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
            if game.state.name == "GAME_OVER":
                winner_text = "승리: 청팀" if game.winner is not None and game.winner.name == "PLAYER" else "패배: 적팀"
                draw_game_over_overlay(screen, fonts, winner_text, return_button_rect, hovered_return)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
