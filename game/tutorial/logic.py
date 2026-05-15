from __future__ import annotations

from typing import TypedDict

from game.model.board import Position
from game.model.constants import ActionMode, Team, UnitType
from game.model.unit import Unit

TutorialCard = dict[str, object]


class TutorialAdvanceDecision(TypedDict, total=False):
    """튜토리얼 진행 여부와 안내 문구를 함께 반환하는 결정 객체."""

    action: str
    feedback: str
    next_index: int


class TutorialPendingTick(TypedDict):
    """시간 경과에 따라 처리할 튜토리얼 대기 상태 결과 객체."""

    pending: bool
    timer: float
    should_show_card: bool
    should_complete_observe: bool


_TUTORIAL_STEPS: tuple[TutorialCard, ...] = (
    {
        "title": "1단계: 검병 선택",
        "body": "먼저 아군 검병을 클릭해 보세요. 기물을 선택하면 이동 가능한 칸과 다음 행동 흐름을 읽기 쉬워집니다.",
        "footer": "좌클릭 또는 Space로 튜토리얼 시작",
        "goal": "select_swordman",
        "hint": "왼쪽 아래쪽의 아군 검병을 눌러 선택해 보세요.",
    },
    {
        "title": "2단계: 이동 연습",
        "body": "이제 초록 칸 가운데 하나로 검병을 움직여 보세요. 이 게임은 적을 상대하기 전에 최소 한 번 이동해야 더 이해가 쉬워집니다.",
        "footer": "좌클릭 또는 Space로 튜토리얼 진행",
        "goal": "move_any",
        "hint": "검병 바로 앞의 초록 칸으로 이동해 보세요. 이번 단계는 다음 공격으로 이어지는 칸만 허용됩니다.",
    },
    {
        "title": "3단계: 공격 연습",
        "body": "이동이 끝나면 공격 모드로 이어집니다. 가까운 적을 눌러 실제로 공격해 보세요. 피해 이펙트도 함께 확인할 수 있습니다.",
        "footer": "좌클릭 또는 Space로 튜토리얼 진행",
        "goal": "attack_any",
        "hint": "정면의 적 한 명을 눌러 공격을 마무리하세요.",
    },
    {
        "title": "4단계: 턴 종료 이해하기",
        "body": "이번에는 직접 턴 종료를 눌러 보세요. 오른쪽의 턴 종료 버튼이나 E 키로 턴을 넘길 수 있습니다.",
        "footer": "좌클릭 또는 Space로 튜토리얼 진행",
        "goal": "end_turn",
        "hint": "오른쪽 턴 종료 버튼을 누르거나 E 키를 눌러 턴을 넘겨 보세요.",
    },
    {
        "title": "5단계: 적 AI 턴 관찰",
        "body": "이번에는 적 차례를 천천히 관찰해 보세요. 적은 바로 움직이지 않고 계산을 마친 뒤 어떤 기물을 움직일지 보여준 다음 실제 행동합니다.",
        "footer": "좌클릭 또는 Space로 설명 보기",
        "goal": "observe_ai_turn",
        "hint": "이제 적의 계산 표시부터 실제 행동 순서까지 지켜보세요.",
        "resume_action": "end_player_turn",
    },
    {
        "title": "6단계: 궁수 선택",
        "body": "이제 다른 기물도 살펴보겠습니다. 아군 궁수를 선택해 보세요. 병종마다 공격과 스킬 사용 방식이 다릅니다.",
        "footer": "좌클릭 또는 Space로 튜토리얼 진행",
        "goal": "select_archer",
        "hint": "아군 궁수를 클릭해 선택해 보세요.",
    },
    {
        "title": "7단계: 스킬 사용 연습",
        "body": "궁수를 선택했다면 스킬을 사용해 보세요. Q 키나 행동 바의 스킬 버튼으로 스킬 모드로 바꾼 뒤 금색 대상 칸을 누르면 됩니다.",
        "footer": "좌클릭 또는 Space로 튜토리얼 진행",
        "goal": "skill_any",
        "hint": "Q 키 또는 스킬 버튼을 눌러 금색 칸의 적에게 궁수 스킬을 사용해 보세요.",
    },
)


def build_tutorial_steps() -> list[TutorialCard]:
    """튜토리얼 단계 정의를 복사해 호출 측에서 수정 가능하게 만든다."""
    return [dict(step) for step in _TUTORIAL_STEPS]


def tutorial_goal_text(tutorial_mode: bool, tutorial_index: int, tutorial_steps: list[TutorialCard]) -> str:
    """현재 튜토리얼 단계의 힌트 문구를 반환한다."""
    if not tutorial_mode or tutorial_index >= len(tutorial_steps):
        return "튜토리얼 연습이 끝났습니다."
    return str(tutorial_steps[tutorial_index].get("hint", "안내에 따라 행동해 보세요."))


def tutorial_current_goal(tutorial_mode: bool, tutorial_index: int, tutorial_steps: list[TutorialCard]) -> str | None:
    """현재 튜토리얼 단계의 goal 값을 반환한다."""
    if not tutorial_mode or tutorial_index >= len(tutorial_steps):
        return None
    return str(tutorial_steps[tutorial_index].get("goal"))


def tutorial_allows_action_mode(
    mode: ActionMode,
    tutorial_mode: bool,
    tutorial_waiting_for_action: bool,
    current_goal: str | None,
) -> bool:
    """튜토리얼 단계가 현재 행동 모드를 허용하는지 판단한다."""
    if not tutorial_mode or not tutorial_waiting_for_action:
        return True
    if current_goal == "move_any":
        return mode == ActionMode.MOVE
    if current_goal == "attack_any":
        return mode == ActionMode.ATTACK
    if current_goal == "skill_any":
        return mode == ActionMode.SKILL
    if current_goal in {"select_swordman", "select_archer", "end_turn", "observe_ai_turn"}:
        return False
    return True


def tutorial_forced_unit(
    living_units: list[Unit],
    tutorial_mode: bool,
    tutorial_waiting_for_action: bool,
    current_goal: str | None,
) -> Unit | None:
    """현재 단계에서 강제로 선택해야 하는 아군 기물을 반환한다."""
    if not tutorial_mode or not tutorial_waiting_for_action:
        return None
    if current_goal not in {"select_swordman", "move_any", "attack_any", "select_archer", "skill_any"}:
        return None
    wanted_type = UnitType.SWORDMAN if current_goal in {"select_swordman", "move_any", "attack_any"} else UnitType.ARCHER
    return next(
        (
            unit
            for unit in living_units
            if unit.team == Team.PLAYER and unit.unit_type == wanted_type
        ),
        None,
    )


def tutorial_forced_move_tiles(
    unit: Unit,
    tutorial_mode: bool,
    tutorial_waiting_for_action: bool,
    current_goal: str | None,
) -> set[Position] | None:
    """이동 연습 단계에서만 허용되는 대상 칸 집합을 반환한다."""
    if not tutorial_mode or not tutorial_waiting_for_action or current_goal != "move_any":
        return None
    if unit.team != Team.PLAYER or unit.unit_type != UnitType.SWORDMAN:
        return None
    return {(3, 4)}


def tutorial_forced_attack_tiles(
    unit: Unit,
    tutorial_mode: bool,
    tutorial_waiting_for_action: bool,
    current_goal: str | None,
) -> set[Position] | None:
    """공격 연습 단계에서만 허용되는 대상 칸 집합을 반환한다."""
    if not tutorial_mode or not tutorial_waiting_for_action or current_goal != "attack_any":
        return None
    if unit.team != Team.PLAYER or unit.unit_type != UnitType.SWORDMAN:
        return None
    return {(3, 3)}


def tutorial_forced_skill_tiles(
    unit: Unit,
    tutorial_mode: bool,
    tutorial_waiting_for_action: bool,
    current_goal: str | None,
) -> set[Position] | None:
    """스킬 연습 단계에서만 허용되는 대상 칸 집합을 반환한다."""
    if not tutorial_mode or not tutorial_waiting_for_action or current_goal != "skill_any":
        return None
    if unit.team != Team.PLAYER or unit.unit_type != UnitType.ARCHER:
        return None
    return {(4, 3)}


def build_tutorial_transition_card(step_title: str, next_title: str) -> TutorialCard:
    """현재 단계를 마치고 다음 단계로 넘어갈 때의 안내 카드를 만든다."""
    return {
        "title": f"{step_title} 완료",
        "body": f"잘했습니다. 다음 연습으로 넘어가겠습니다. 다음 단계는 {next_title}입니다.",
        "footer": "좌클릭 또는 Space로 다음 설명 보기",
    }


def build_tutorial_complete_card() -> TutorialCard:
    """튜토리얼 종료 시 보여줄 완료 카드 데이터를 만든다."""
    return {
        "title": "튜토리얼 완료",
        "body": "이제 기물 선택, 이동, 공격, 그리고 적 AI 턴 흐름까지 모두 확인했습니다. 이어서 자유롭게 전투를 진행해 보세요.",
        "footer": "좌클릭 또는 Space로 튜토리얼 닫기",
    }


def advance_tutorial_decision(
    tutorial_visible: bool,
    tutorial_summary_card: TutorialCard | None,
    tutorial_pending_step_index: int | None,
    tutorial_mode: bool,
    tutorial_index: int,
    tutorial_steps: list[TutorialCard],
) -> TutorialAdvanceDecision:
    """현재 카드 상태를 보고 다음 튜토리얼 전환 액션을 결정한다."""
    if not tutorial_visible:
        return {"action": "noop"}

    if tutorial_summary_card is not None:
        if tutorial_pending_step_index is not None:
            next_index = tutorial_pending_step_index
            return {
                "action": "show_pending_step",
                "next_index": next_index,
                "feedback": str(tutorial_steps[next_index]["title"]),
            }
        return {
            "action": "complete_tutorial",
            "feedback": "튜토리얼이 마무리되었습니다. 이제 자유롭게 전투를 진행해 보세요.",
        }

    if tutorial_mode:
        step = tutorial_steps[tutorial_index]
        if step.get("kind") == "info":
            if tutorial_index < len(tutorial_steps) - 1:
                next_index = tutorial_index + 1
                return {
                    "action": "advance_info_step",
                    "next_index": next_index,
                    "feedback": str(tutorial_steps[next_index]["title"]),
                }
            return {"action": "noop"}
        action = "wait_for_action_and_resume_turn" if step.get("resume_action") == "end_player_turn" else "wait_for_action"
        return {
            "action": action,
            "feedback": tutorial_goal_text(tutorial_mode, tutorial_index, tutorial_steps),
        }

    if tutorial_index >= len(tutorial_steps) - 1:
        return {
            "action": "close_reference",
            "feedback": "튜토리얼이 마무리되었습니다. F1 또는 H로 다시 볼 수 있습니다.",
        }

    next_index = tutorial_index + 1
    return {
        "action": "advance_reference",
        "next_index": next_index,
        "feedback": str(tutorial_steps[next_index]["title"]),
    }


def tick_tutorial_summary_pending(summary_pending: bool, timer: float, dt: float, effects_present: bool) -> TutorialPendingTick:
    """요약 카드 대기 상태를 갱신하고 표시 시점을 계산한다."""
    if not summary_pending:
        return {
            "pending": False,
            "timer": timer,
            "should_show_card": False,
            "should_complete_observe": False,
        }
    if effects_present:
        return {
            "pending": True,
            "timer": max(timer, 0.4),
            "should_show_card": False,
            "should_complete_observe": False,
        }
    timer -= dt
    return {
        "pending": timer > 0,
        "timer": timer,
        "should_show_card": timer <= 0,
        "should_complete_observe": False,
    }


def tick_tutorial_ai_observe_pending(observe_pending: bool, timer: float, dt: float, effects_present: bool) -> TutorialPendingTick:
    """AI 관찰 단계 완료 대기 상태를 갱신한다."""
    if not observe_pending:
        return {
            "pending": False,
            "timer": timer,
            "should_show_card": False,
            "should_complete_observe": False,
        }
    if effects_present:
        return {
            "pending": True,
            "timer": max(timer, 0.45),
            "should_show_card": False,
            "should_complete_observe": False,
        }
    timer -= dt
    return {
        "pending": timer > 0,
        "timer": timer,
        "should_show_card": False,
        "should_complete_observe": timer <= 0,
    }
