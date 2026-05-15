from __future__ import annotations

import random

from game.model.board import Board
from game.model.constants import AI_BUDGET_BY_DIFFICULTY, DRAFT_BUDGET, DRAFT_POOL, DRAFT_SIZE, UNIT_COSTS, UnitType
from game.model.skill import SKILLS
from game.model.unit import ATTACK_POWER, Unit
from game.engine.game_manager import BASE_HP

MAP_OPTIONS = [
    ("classic", "기본 전장", "중앙 장애물만 있는 기본형 전장입니다."),
    ("wings", "측면 회랑", "좌우 통로가 열려 측면 전개가 중요합니다."),
    ("river", "강 전장", "중앙의 강 지형을 피해 우회해야 합니다."),
    ("fort", "요새 전장", "입구를 막고 버티기 좋은 전장입니다."),
    ("cross", "십자 전장", "교차로를 먼저 장악하면 유리합니다."),
    ("diamond", "중앙 거점", "중앙 대각 거점을 선점하면 전개가 빨라집니다."),
    ("lanes", "이중 차선", "좌우 차선을 길게 써야 하는 전장입니다."),
    ("chaos", "혼전 전장", "장애물이 많아 전투 각이 자주 바뀝니다."),
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
    UnitType.SWORDMAN: "검병",
    UnitType.ARCHER: "궁수",
    UnitType.MAGE: "마법사",
    UnitType.KNIGHT: "기사",
    UnitType.BISHOP: "사제",
    UnitType.LANCER: "창병",
}

UNIT_DRAFT_BLURBS_LOCAL = {
    UnitType.SWORDMAN: "직선 돌진과 근접 압박에 강한 기본 전열 유닛.",
    UnitType.ARCHER: "멀리서 적을 견제하는 장거리 유닛.",
    UnitType.MAGE: "범위 피해로 전열을 흔드는 광역 유닛.",
    UnitType.KNIGHT: "기동력으로 측면을 찌르는 돌파 유닛.",
    UnitType.BISHOP: "대각 공격에 특화된 고급 원거리 유닛.",
    UnitType.LANCER: "돌진으로 적을 밀어내는 전진 유닛.",
    UnitType.KING: "전장의 중심이 되는 지휘 유닛.",
}

UNIT_SKILL_TEXT = {
    UnitType.KING: ("왕의 수호", "아군 하나에게 1턴 보호막을 부여합니다."),
    UnitType.SWORDMAN: ("돌진", "직선으로 파고들며 적을 압박합니다."),
    UnitType.ARCHER: ("관통 사격", "직선 경로를 따라 적을 연속으로 꿰뚫습니다."),
    UnitType.MAGE: ("화염 폭발", "지정한 3x3 범위를 불태웁니다."),
    UnitType.KNIGHT: ("도약 강타", "순간 돌진으로 측면을 무너뜨립니다."),
    UnitType.BISHOP: ("대각 성광", "대각선 방향으로 긴 광선을 발사합니다."),
    UnitType.LANCER: ("관통 돌진", "직선으로 돌진하며 적을 밀어냅니다."),
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


def draft_budget_for_difficulty(difficulty: int) -> int | None:
    """난이도에 맞는 드래프트 예산을 반환한다."""
    if difficulty >= 6:
        return AI_BUDGET_BY_DIFFICULTY.get(difficulty, DRAFT_BUDGET)
    return DRAFT_BUDGET
    None
    ##악몽모드랑 괴물모드 예산 다시 있도록
    ##if difficulty >= 6:
        ##return None
    return DRAFT_BUDGET


def can_add_unit(roster: list[UnitType], unit_type: UnitType, difficulty: int = 3) -> bool:
    """현재 로스터와 예산 기준으로 기물을 더 담을 수 있는지 판단한다."""
    if len(roster) >= DRAFT_SIZE:
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
    """남은 슬롯과 예산을 고려해 로스터를 자동으로 채운다."""
    filled = list(roster)
    min_unit_cost = min(UNIT_COSTS[unit] for unit in DRAFT_POOL)
    while len(filled) < DRAFT_SIZE:
        budget = draft_budget_for_difficulty(difficulty)
        spent = sum(UNIT_COSTS[unit] for unit in filled)
        choices = []
        for unit in DRAFT_POOL:
            if not can_add_unit(filled, unit, difficulty):
                continue
            if budget is not None:
                remaining_budget = budget - spent - UNIT_COSTS[unit]
                remaining_slots = DRAFT_SIZE - (len(filled) + 1)
                if remaining_budget < remaining_slots * min_unit_cost:
                    continue
            choices.append(unit)
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
    """도감 패널에 표시할 요약 스탯과 설명 문자열을 구성한다."""
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
    """난이도 성향을 반영해 AI 드래프트 로스터를 생성한다."""
    rng = random.Random(seed)
    if difficulty >= 6:
        budget = draft_budget_for_difficulty(difficulty)
        min_unit_cost = min(UNIT_COSTS[unit] for unit in DRAFT_POOL)
        elite_pool = [UnitType.KNIGHT, UnitType.BISHOP, UnitType.MAGE, UnitType.LANCER]
        weights = {
            UnitType.KNIGHT: 4 if difficulty == 6 else 5,
            UnitType.BISHOP: 4 if difficulty == 6 else 5,
            UnitType.MAGE: 4 if difficulty == 6 else 5,
            UnitType.LANCER: 4 if difficulty == 6 else 5,
        }
        roster: list[UnitType] = []
        while len(roster) < DRAFT_SIZE:
            spent = sum(UNIT_COSTS[unit] for unit in roster)
            choices = []
            for unit in elite_pool:
                if not can_add_unit(roster, unit, difficulty):
                    continue
                if budget is not None:
                    remaining_budget = budget - spent - UNIT_COSTS[unit]
                    remaining_slots = DRAFT_SIZE - (len(roster) + 1)
                    if remaining_budget < remaining_slots * min_unit_cost:
                        continue
                choices.append(unit)
            if not choices:
                break
            roster.append(rng.choices(choices, weights=[weights[unit] for unit in choices], k=1)[0])
        if len(roster) < DRAFT_SIZE:
            roster = auto_fill_roster(roster, rng, difficulty=difficulty)
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
