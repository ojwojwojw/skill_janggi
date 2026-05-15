from __future__ import annotations

from dataclasses import dataclass

from game.model.board import Position


@dataclass(slots=True)
class AIAction:
    """AI가 선택한 행동 하나를 표현하는 경량 데이터 객체."""
    unit_id: str
    move_target: Position | None = None
    action_type: str | None = None
    action_target: Position | None = None
    score: float = 0.0
