from __future__ import annotations

from dataclasses import dataclass

from game.model.constants import UnitType


@dataclass(frozen=True, slots=True)
class Skill:
    """스킬의 사거리, 쿨다운, 범위 정보를 담는 데이터 객체."""
    name: str
    cooldown: int
    range: int
    description: str

    def can_use(self, current_cooldown: int) -> bool:
        """현재 쿨다운 기준으로 스킬 사용 가능 여부를 반환한다."""
        return current_cooldown <= 0


SKILLS = {
    UnitType.KING: Skill(
        name="왕의 수호",
        cooldown=3,
        range=0,
        description="아군 1명에게 1턴 보호막을 부여합니다.",
    ),
    UnitType.SWORDMAN: Skill(
        name="돌진",
        cooldown=2,
        range=3,
        description="직선으로 파고들어 적을 강하게 압박합니다.",
    ),
    UnitType.ARCHER: Skill(
        name="관통 사격",
        cooldown=3,
        range=3,
        description="직선 경로를 따라 적을 연속으로 꿰뚫습니다.",
    ),
    UnitType.MAGE: Skill(
        name="화염 폭발",
        cooldown=4,
        range=3,
        description="지정한 3x3 범위를 불태웁니다.",
    ),
    UnitType.KNIGHT: Skill(
        name="도약 강타",
        cooldown=3,
        range=2,
        description="순간 돌진해 적을 강하게 밀어냅니다.",
    ),
    UnitType.BISHOP: Skill(
        name="대각 광선",
        cooldown=3,
        range=4,
        description="대각선 방향으로 긴 광선을 발사합니다.",
    ),
    UnitType.LANCER: Skill(
        name="관통 돌진",
        cooldown=3,
        range=3,
        description="직선으로 돌진해 적을 찌르고, 막힐 때까지 끝으로 밀어냅니다.",
    ),
}
