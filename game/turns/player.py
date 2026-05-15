from __future__ import annotations

import pygame

from game.model.constants import ActionMode


def action_mode_for_key(key: int) -> ActionMode | None:
    """키 입력을 행동 모드 enum으로 변환한다."""
    if key == pygame.K_q:
        return ActionMode.SKILL
    if key == pygame.K_a:
        return ActionMode.ATTACK
    if key in {pygame.K_m, pygame.K_ESCAPE}:
        return ActionMode.MOVE
    return None


def mode_help_text(selected_unit_exists: bool, action_mode: ActionMode) -> str:
    """현재 선택/행동 상태에 맞는 하단 안내 문구를 만든다."""
    if not selected_unit_exists:
        return "먼저 청 진영 유닛을 선택하세요."
    if action_mode == ActionMode.MOVE:
        return "이동 가능한 칸을 눌러 자리를 잡으세요."
    if action_mode == ActionMode.ATTACK:
        return "공격 가능한 적 유닛을 선택하세요."
    if action_mode == ActionMode.SKILL:
        return "금색 강조 칸이 스킬 대상입니다."
    return "행동 방식을 선택하세요."


def selected_unit_action_mode(unit_id: str, activation_unit_id: str | None, activation_move_used: bool) -> ActionMode:
    """행동을 이미 시작한 유닛인지 보고 기본 모드를 결정한다."""
    if activation_unit_id == unit_id and activation_move_used:
        return ActionMode.ATTACK
    return ActionMode.MOVE


def blocked_selection_feedback(forced_unit_name: str | None) -> str:
    """선택이 막힌 상황에서 보여줄 피드백 문구를 만든다."""
    if forced_unit_name is not None:
        return f"이번 실습에서는 {forced_unit_name}만 선택하세요."
    return "이미 행동한 유닛은 다시 선택할 수 없습니다."


def move_completion_state(has_follow_up_actions: bool) -> tuple[ActionMode, str] | tuple[None, str]:
    """이동 후 자동 전환할 모드와 피드백 문구를 돌려준다."""
    if has_follow_up_actions:
        return (ActionMode.ATTACK, "이동 완료. 이어서 공격하거나 스킬을 사용할 수 있습니다.")
    return (None, "이동 완료. 이 유닛은 더 할 수 있는 행동이 없습니다.")


def should_auto_end_turn_after_action(action_kind: str, tutorial_mode: bool, tutorial_goal: str | None) -> bool:
    """행동 직후 턴을 자동 종료할지 튜토리얼 예외까지 반영해 판단한다."""
    if action_kind == "skill":
        return not (tutorial_mode and tutorial_goal == "skill_any")
    if action_kind == "attack":
        return not (tutorial_mode and tutorial_goal == "attack_any")
    return True
