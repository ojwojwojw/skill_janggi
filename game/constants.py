from __future__ import annotations

from enum import Enum, auto

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

BOARD_SIZE = 8
TILE_SIZE = 68
BOARD_PIXEL_SIZE = BOARD_SIZE * TILE_SIZE
BOARD_ORIGIN = (252, 66)

SIDEBAR_X = 812
SIDEBAR_Y = 42
SIDEBAR_WIDTH = 440
SIDEBAR_HEIGHT = 568

INFO_PANEL_RECT = (SIDEBAR_X + 16, SIDEBAR_Y + 124, 408, 268)
ACTION_PANEL_RECT = (SIDEBAR_X + 16, SIDEBAR_Y + 434, 408, 124)
LOG_PANEL_RECT = (28, 66, 210, 544)

MOVE_BUTTON = (SIDEBAR_X + 22, SIDEBAR_Y + 474, 92, 36)
ATTACK_BUTTON = (SIDEBAR_X + 122, SIDEBAR_Y + 474, 92, 36)
SKILL_BUTTON = (SIDEBAR_X + 222, SIDEBAR_Y + 474, 92, 36)
END_TURN_BUTTON = (SIDEBAR_X + 322, SIDEBAR_Y + 474, 92, 36)

BACKGROUND_COLOR = (15, 19, 30)
PANEL_COLOR = (24, 30, 46)
PANEL_BORDER = (62, 76, 104)
TEXT_COLOR = (235, 240, 255)
SUBTEXT_COLOR = (165, 176, 204)
GRID_LIGHT = (70, 82, 102)
GRID_DARK = (48, 58, 75)
MOVE_HIGHLIGHT = (74, 200, 141, 170)
ATTACK_HIGHLIGHT = (233, 92, 92, 180)
SKILL_HIGHLIGHT = (247, 196, 88, 180)
SELECT_HIGHLIGHT = (255, 255, 255, 180)
BLUE_TEAM = (76, 150, 255)
RED_TEAM = (255, 104, 104)
BUTTON_COLOR = (55, 68, 92)
BUTTON_ACTIVE = (87, 115, 160)
BUTTON_DISABLED = (45, 50, 58)
LOG_PANEL_BG = (18, 23, 36)
LOG_SCROLLBAR_BG = (44, 52, 72)
LOG_SCROLLBAR_FG = (120, 144, 196)
HP_BAR_BG = (35, 40, 52)
HP_BAR_FILL = (82, 211, 128)
HP_BAR_LOW = (228, 95, 95)
OBSTACLE_COLOR = (88, 96, 116)
OBSTACLE_EDGE = (138, 148, 176)
RIVER_TILE = (56, 118, 190)
RIVER_TILE_DARK = (35, 82, 144)

DRAFT_BUDGET = 17
DRAFT_SIZE = 7


class Team(Enum):
    PLAYER = auto()
    AI = auto()


class GameState(Enum):
    PLAYER_TURN = auto()
    AI_TURN = auto()
    GAME_OVER = auto()


class ActionMode(Enum):
    MOVE = auto()
    ATTACK = auto()
    SKILL = auto()


class UnitType(Enum):
    KING = auto()
    SWORDMAN = auto()
    ARCHER = auto()
    MAGE = auto()
    KNIGHT = auto()
    BISHOP = auto()
    LANCER = auto()


TEAM_NAMES = {
    Team.PLAYER: "청",
    Team.AI: "흑",
}

UNIT_DISPLAY_NAMES = {
    UnitType.KING: "왕",
    UnitType.SWORDMAN: "검사",
    UnitType.ARCHER: "궁수",
    UnitType.MAGE: "술사",
    UnitType.KNIGHT: "기마",
    UnitType.BISHOP: "비숍",
    UnitType.LANCER: "창병",
}

UNIT_COSTS = {
    UnitType.SWORDMAN: 2,
    UnitType.ARCHER: 2,
    UnitType.MAGE: 3,
    UnitType.KNIGHT: 4,
    UnitType.LANCER: 3,
    UnitType.BISHOP: 5,
}

UNIT_DRAFT_BLURBS = {
    UnitType.SWORDMAN: "직선 이동과 돌진.",
    UnitType.ARCHER: "후방 견제 사격.",
    UnitType.MAGE: "광역 폭발 제압.",
    UnitType.KNIGHT: "도약 진입과 밀치기.",
    UnitType.LANCER: "직선 돌파와 찌르기.",
    UnitType.BISHOP: "대각 장거리 압박.",
}

UNIT_GLYPHS = {
    UnitType.KING: "K",
    UnitType.SWORDMAN: "S",
    UnitType.ARCHER: "A",
    UnitType.MAGE: "M",
    UnitType.KNIGHT: "N",
    UnitType.BISHOP: "B",
    UnitType.LANCER: "L",
}

DRAFT_POOL = [
    UnitType.SWORDMAN,
    UnitType.ARCHER,
    UnitType.KNIGHT,
    UnitType.BISHOP,
]
