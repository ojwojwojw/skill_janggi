from __future__ import annotations

import random

from game.ai.brain import AIAction, SimpleAI
from game.model.board import Board, Position
from game.model.constants import Team, UnitType
from game.model.unit import Unit


def choose_ai_action(
    ai: SimpleAI,
    board: Board,
    living_units: list[Unit],
    tutorial_mode: bool,
    tutorial_waiting_for_action: bool,
    tutorial_goal: str | None,
) -> AIAction | None:
    """튜토리얼 scripted action이 있으면 우선 적용하고, 없으면 일반 AI를 호출한다."""
    scripted_action = build_scripted_tutorial_ai_action(
        board,
        living_units,
        tutorial_mode,
        tutorial_waiting_for_action,
        tutorial_goal,
    )
    if scripted_action is not None:
        return scripted_action
    return ai.choose_action(board, living_units)


def build_scripted_tutorial_ai_action(
    board: Board,
    living_units: list[Unit],
    tutorial_mode: bool,
    tutorial_waiting_for_action: bool,
    tutorial_goal: str | None,
) -> AIAction | None:
    """튜토리얼 관찰 단계에서만 사용할 고정 AI 행동을 만든다."""
    if not tutorial_mode or not tutorial_waiting_for_action or tutorial_goal != "observe_ai_turn":
        return None
    enemy = next(
        (
            unit
            for unit in living_units
            if unit.team == Team.AI and unit.unit_type == UnitType.SWORDMAN
        ),
        None,
    )
    if enemy is None:
        return None
    for destination in ((4, 3), (2, 3), (3, 4)):
        if destination in enemy.basic_move_targets(board, living_units):
            return AIAction(unit_id=enemy.id, move_target=destination, action_type=None, action_target=None, score=999.0)
    return AIAction(unit_id=enemy.id, action_type=None, action_target=None, score=999.0)


def ai_phase_delay(phase: str, rng: random.Random) -> float:
    """AI 연출 단계별 대기 시간을 난수 범위로 계산한다."""
    if phase == "thinking":
        return rng.uniform(0.55, 1.05)
    if phase == "acting":
        return rng.uniform(0.28, 0.52)
    return 0.0


def ai_preview_effects(action: AIAction, phase_delay: float) -> list[dict[str, object]]:
    """AI가 실제 행동하기 전 보여줄 프리뷰 이펙트 목록을 만든다."""
    effects: list[dict[str, object]] = []
    effects.append({"type": "select", "target": "unit", "duration": 0.28})
    effects.append({"type": "thinking", "target": "unit", "duration": phase_delay + 0.08})
    if action.move_target is not None:
        effects.append({"type": "ghost_move", "target": "move_target", "duration": 0.36})
    if action.action_target is not None:
        preview_type = "ghost_attack" if action.action_type == "attack" else "ghost_skill"
        effects.append({"type": preview_type, "target": "action_target", "duration": 0.36})
    return effects


def ai_feedback_text(unit: Unit, action: AIAction) -> str | None:
    """AI가 공격/스킬/이동을 준비할 때 사용할 안내 문구를 만든다."""
    if action.action_type == "attack":
        return f"{unit.name}이 공격 각을 재고 있습니다."
    if action.action_type == "skill":
        return f"{unit.name}이 스킬 타이밍을 계산 중입니다."
    if action.move_target is not None:
        return f"{unit.name}이 이동 경로를 계산 중입니다."
    return None


def ai_move_only_feedback(unit: Unit, action: AIAction) -> str | None:
    """AI가 이동만 하고 턴을 마치는 경우의 피드백 문구를 만든다."""
    if action.action_type is None and action.move_target is not None:
        return f"{unit.name}이 이동만 하고 턴을 마쳤습니다."
    return None
