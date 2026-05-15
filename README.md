# Skill Janggi

Pygame 기반 2D 턴제 전략 보드게임 프로토타입입니다. 장기/체스 느낌의 8x8 전장 위에서 드래프트, 배치, 턴 전투, 튜토리얼, 난이도별 AI 대전을 한 흐름으로 묶은 프로젝트입니다.

## 실행 방법

```bash
python -m pip install pygame
python main.py
```

## 조작법

- 좌클릭: 유닛 선택 / 타일 선택 / 버튼 클릭
- `A`: 공격 모드
- `Q`: 스킬 모드
- `M` 또는 `Esc`: 이동 모드
- `E`: 턴 종료

## 현재 포함 기능

- 메인 메뉴, 난이도 선택, 맵 선택
- 유닛 드래프트와 자동 편성
- 9기물 배치 화면
- 장애물/강 조합이 있는 보드 프리셋
- 유닛별 기본 공격과 스킬
- 튜토리얼 진행 및 가이드 카드
- 난이도별 AI 편성, 턴 연출, 행동 선택
- 전투 로그, 사운드, UI 오버레이

## 프로젝트 구조

```text
skill janggi/
├── main.py
├── assets/
│   ├── sounds/
│   ├── sprites/
│   └── ui/
├── game/
│   ├── ai/
│   ├── engine/
│   ├── model/
│   ├── turns/
│   ├── tutorial/
│   ├── ui/
│   └── roster.py
└── README.md
```

## 디렉터리별 역할

### `main.py`
- 게임 실행 진입점입니다.
- 메뉴, 드래프트, 배치, 전투 화면 사이를 전환합니다.
- `GameManager`, `Renderer`, UI 빌더들을 조합해 전체 런타임을 묶습니다.

### `game/model`
- 게임의 순수 데이터 모델을 모아둔 곳입니다.
- `board.py`: 좌표계, 보드 경계, 장애물, 거리 계산
- `constants.py`: 화면 크기, 색상, 버튼 위치, enum, 드래프트 상수
- `skill.py`: 유닛별 스킬 메타데이터
- `unit.py`: 유닛 상태, 이동/공격/스킬 타겟 계산

### `game/ai`
- AI 판단 로직 전용 영역입니다.
- `brain.py`: 행동 후보 생성과 최종 선택
- `scoring.py`: 이동/공격/스킬 점수 계산
- `defense.py`: 왕 보호용 패닉/방어 가중치
- `helpers.py`: 위협 계산, 거리/압박 보조 함수
- `types.py`: AI 액션 데이터 구조

### `game/engine`
- 실제 전투를 굴리는 런타임 계층입니다.
- `game_manager.py`: 턴 상태, 입력 반응, 승패 판정, 로그, 튜토리얼 상태
- `gameplay.py`: 공격/스킬 해상도와 전투 연출 처리
- `renderer.py`: 보드/유닛/UI 패널 렌더링

### `game/turns`
- 턴별 규칙 보조 함수입니다.
- `player.py`: 플레이어 입력 모드와 행동 후 상태 전환 규칙
- `ai.py`: AI 턴 연출, 튜토리얼용 scripted action

### `game/tutorial`
- 튜토리얼 단계와 진행 제약을 정의합니다.
- 어떤 유닛/타일만 허용할지, 카드 전환을 언제 보여줄지 관리합니다.

### `game/ui`
- UI 렌더링에 필요한 공용 레이어입니다.
- `assets.py`: 폰트, 사운드, 프리뷰 스프라이트, 텍스트 줄바꿈
- `layout.py`: 화면별 rect/배치 계산 진입점
- `screens.py`: 화면 draw 함수 진입점
- `views/`: 실제 메뉴/드래프트/배치/도감/오버레이 구현

### `game/roster.py`
- 드래프트 예산, 자동 편성, AI 로스터 생성, 도감 텍스트를 담당합니다.

## 소스별 빠른 읽기 가이드

- 전투 흐름부터 보려면: `main.py` → `game/engine/game_manager.py` → `game/engine/gameplay.py`
- 유닛 규칙부터 보려면: `game/model/unit.py` → `game/model/skill.py`
- AI부터 보려면: `game/ai/brain.py` → `game/ai/scoring.py` → `game/ai/defense.py`
- UI부터 보려면: `game/ui/screens.py` → `game/ui/views/`
- 드래프트/편성부터 보려면: `game/roster.py`

## 구현 가정

- King 기본 공격은 상하좌우 1칸입니다.
- Mage 기본 공격은 인접 8방향 1칸입니다.
- Archer 기본 공격과 관통 사격은 직선 3칸 기준입니다.
- 현재 기본 편성 수는 9기물입니다.
- 난이도 6, 7에서는 유저 드래프트 예산도 AI 기준표와 동일하게 맞춰집니다.
- Knight, Bishop, Mage, Lancer는 중복 선택 제한 없이 편성 가능합니다.

## 문서화 기준

- 함수 역할 설명은 코드 안에 짧은 `docstring`으로 정리합니다.
- UI 쪽 함수는 “무슨 화면을 그리는지”, AI 쪽 함수는 “무슨 판단 보조인지”, 엔진 쪽 함수는 “어떤 전투/턴 상태를 처리하는지” 위주로 보면 됩니다.
