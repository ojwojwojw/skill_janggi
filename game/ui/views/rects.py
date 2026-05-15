from __future__ import annotations

from pathlib import Path

import pygame

from game.engine.game_manager import PLAYER_HOME_POSITIONS, PLAYER_KING_POS, GameManager
from game.model.constants import DRAFT_POOL, UnitType

DEPLOYMENT_SLOT_START_Y = 190
DEPLOYMENT_SLOT_HEIGHT = 40
DEPLOYMENT_SLOT_GAP = 4


def build_draft_unit_rects() -> dict[UnitType, pygame.Rect]:
    """드래프트 화면의 기물 카드 영역을 계산한다."""
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
    """전투 설정 화면의 맵 카드와 난이도 버튼 영역을 계산한다."""
    map_rects: dict[str, pygame.Rect] = {}
    start_x = 136
    start_y = 384
    card_w = 226
    card_h = 102
    gap_x = 18
    gap_y = 14
    from game.roster import MAP_OPTIONS

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
    """전투 설정 화면의 다음 버튼 영역을 반환한다."""
    return pygame.Rect(776, 602, 232, 40)


def build_codex_button_rect() -> pygame.Rect:
    """도감 화면 진입 버튼 영역을 반환한다."""
    return pygame.Rect(492, 618, 232, 40)


def build_tutorial_button_rect() -> pygame.Rect:
    """튜토리얼 진입 버튼 영역을 반환한다."""
    return pygame.Rect(776, 564, 232, 40)


def build_menu_button_rects() -> dict[str, pygame.Rect]:
    """메인 메뉴의 버튼 영역들을 반환한다."""
    return {
        "start": pygame.Rect(492, 462, 296, 46),
        "tutorial": pygame.Rect(492, 520, 296, 46),
        "codex": pygame.Rect(492, 578, 296, 46),
    }


def build_codex_unit_rects() -> dict[UnitType, pygame.Rect]:
    """도감 화면의 기물 카드 영역을 계산한다."""
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
    """배치 화면의 액션 버튼 영역을 반환한다."""
    return {
        "auto": pygame.Rect(846, 590, 158, 40),
        "clear": pygame.Rect(1022, 590, 158, 40),
        "start": pygame.Rect(846, 636, 334, 38),
    }


def build_deployment_slot_rect(index: int) -> pygame.Rect:
    """배치 화면 우측 슬롯 목록의 영역을 계산한다."""
    return pygame.Rect(
        842,
        DEPLOYMENT_SLOT_START_Y + index * (DEPLOYMENT_SLOT_HEIGHT + DEPLOYMENT_SLOT_GAP),
        360,
        DEPLOYMENT_SLOT_HEIGHT,
    )


def build_tutorial_battle(project_root: Path) -> GameManager:
    """튜토리얼 전투용 고정 전장을 생성한다."""
    tutorial_player_roster = [UnitType.SWORDMAN, UnitType.ARCHER]
    tutorial_ai_roster = [UnitType.SWORDMAN]
    tutorial_player_positions = [(3, 5), (4, 6)]
    tutorial_ai_positions = [(3, 3)]
    game = GameManager(
        project_root,
        blocked_tiles=set(),
        player_roster=tutorial_player_roster,
        ai_roster=tutorial_ai_roster,
        player_positions=tutorial_player_positions,
        ai_positions=tutorial_ai_positions,
        ai_difficulty=1,
        map_name="classic",
        tutorial_mode=True,
    )
    game.last_feedback = "튜토리얼 전투입니다. 적의 움직임을 차근차근 살펴보세요."
    game.logs.append("튜토리얼 전투가 시작되었습니다. 검병과 궁수로 기본 전투 흐름을 익혀보세요.")
    return game


def auto_arrange_player_positions(roster: list[UnitType], blocked_tiles: set[tuple[int, int]]) -> list[tuple[int, int]]:
    """현재 규칙으로 플레이어 기물 자동 배치 결과를 계산한다."""
    temp = GameManager(Path("."), blocked_tiles=blocked_tiles, player_roster=roster, ai_roster=roster)
    return [unit.position for unit in temp.units if unit.team.name == "PLAYER" and unit.unit_type != UnitType.KING]


def deployment_valid_tiles(blocked_tiles: set[tuple[int, int]]) -> set[tuple[int, int]]:
    """플레이어가 배치할 수 있는 유효한 홈 타일 집합을 반환한다."""
    return {tile for tile in PLAYER_HOME_POSITIONS if tile not in blocked_tiles and tile != PLAYER_KING_POS}
