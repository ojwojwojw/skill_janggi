# Skill Janggi

Pygame 기반 2D 턴제 전략 보드게임 프로토타입입니다. 장기/체스 스타일 보드 전투에 유닛별 스킬을 붙인 MVP이며, 플레이어 대 간단 AI 대전을 바로 테스트할 수 있습니다.

## 포함 기능

- 8x8 보드와 턴 기반 게임 루프
- 플레이어 / AI 번갈아 행동
- 유닛 선택, 이동, 기본 공격, 스킬 사용
- King 처치 시 즉시 승리
- 우선순위 기반 간단 AI
- 리소스가 없을 때 도트 스타일 플레이스홀더 그래픽 자동 생성

## 실행 방법

```bash
python -m pip install pygame
python main.py
```

## 조작법

- 좌클릭: 유닛 선택 / 타일 선택
- `A`: 공격 모드
- `Q`: 스킬 모드
- `Esc`: 이동 모드로 복귀
- `End Turn` 버튼: 턴 넘기기

## 프로젝트 구조

```text
skill_janggi/
├── main.py
├── game/
│   ├── board.py
│   ├── unit.py
│   ├── skill.py
│   ├── game_manager.py
│   ├── ai.py
│   ├── renderer.py
│   └── constants.py
├── assets/
│   ├── sprites/
│   ├── ui/
│   └── sounds/
└── README.md
```

## 이번 MVP에서 둔 구현 가정

- King 기본 공격은 상하좌우 1칸입니다.
- Mage 기본 공격은 인접 8방향 1칸입니다.
- Archer 기본 공격과 관통 사격은 직선 3칸 기준입니다.
- Swordman 돌진은 직선 상 적을 맞추면 적 앞칸까지 전진 후 피해를 줍니다.
- 보호막은 다음 아군 턴이 시작될 때까지 유지됩니다.

## 다음 추천 확장

- 행동 이펙트와 간단 애니메이션
- 장애물 / 지형 효과
- 유닛 추가와 상태이상
- AI 판단 고도화
