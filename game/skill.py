from __future__ import annotations

from dataclasses import dataclass

from game.constants import UnitType


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    cooldown: int
    range: int
    description: str

    def can_use(self, current_cooldown: int) -> bool:
        return current_cooldown <= 0


SKILLS = {
    UnitType.KING: Skill(
        name="보호막",
        cooldown=3,
        range=0,
        description="자신에게 1턴 보호막을 부여합니다. 다음 아군 턴 전까지 받는 피해가 1 감소합니다.",
    ),
    UnitType.SWORDMAN: Skill(
        name="돌진",
        cooldown=2,
        range=3,
        description="직선으로 최대 3칸 돌진합니다. 경로 끝에 적이 있으면 즉시 공격합니다.",
    ),
    UnitType.ARCHER: Skill(
        name="관통 사격",
        cooldown=3,
        range=3,
        description="직선 방향으로 화살을 발사해 경로상의 모든 적에게 피해를 줍니다.",
    ),
    UnitType.MAGE: Skill(
        name="화염 폭발",
        cooldown=4,
        range=3,
        description="지정한 위치 중심 3x3 범위의 모든 적에게 피해를 줍니다.",
    ),
}
