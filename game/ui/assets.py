from __future__ import annotations

from pathlib import Path

import pygame

from game.model.constants import TEXT_COLOR, UnitType


def load_ui_font(size: int, bold: bool = False) -> pygame.font.Font:
    """한글 우선 후보를 순서대로 시도해 UI 폰트를 만든다."""
    candidates = ["malgungothic", "malgun gothic", "nanumgothic", "applegothic", "arialunicode", "arial"]
    font_path = None
    for name in candidates:
        font_path = pygame.font.match_font(name)
        if font_path:
            break
    font = pygame.font.Font(font_path, size) if font_path else pygame.font.SysFont(None, size, bold=bold)
    font.set_bold(bold)
    return font


def wrap_text(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    """주어진 폭 안에 들어가도록 텍스트를 여러 줄로 나눈다."""
    if not text or font.size(text)[0] <= max_width:
        return [text]
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_wrapped_left(
    screen: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    color: tuple[int, int, int],
    pos: tuple[int, int],
    max_width: int,
    line_gap: int,
) -> None:
    """여러 줄 텍스트를 좌상단 기준으로 순서대로 그린다."""
    x, y = pos
    for line in wrap_text(font, text, max_width):
        screen.blit(font.render(line, True, color), (x, y))
        y += line_gap


class SoundController:
    """효과음과 배경음 재생을 담당하는 얇은 오디오 래퍼."""

    def __init__(self, project_root: Path) -> None:
        """사운드 파일을 로드하고 믹서를 초기화한다."""
        self.enabled = False
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.current_music: str | None = None
        self.sound_dir = project_root / "assets" / "sounds"
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.sounds = {
                "move": pygame.mixer.Sound(self.sound_dir / "sfx_move.wav"),
                "attack": pygame.mixer.Sound(self.sound_dir / "sfx_attack.wav"),
                "skill": pygame.mixer.Sound(self.sound_dir / "sfx_skill.wav"),
                "pick": pygame.mixer.Sound(self.sound_dir / "sfx_pick.wav"),
                "end_turn": pygame.mixer.Sound(self.sound_dir / "sfx_end_turn.wav"),
                "win": pygame.mixer.Sound(self.sound_dir / "sfx_win.wav"),
            }
            self.sounds["move"].set_volume(0.30)
            self.sounds["attack"].set_volume(0.42)
            self.sounds["skill"].set_volume(0.40)
            self.sounds["pick"].set_volume(0.34)
            self.sounds["end_turn"].set_volume(0.32)
            self.sounds["win"].set_volume(0.45)
            self.enabled = True
        except pygame.error:
            self.enabled = False

    def play(self, name: str) -> None:
        """이름으로 등록된 효과음을 한 번 재생한다."""
        if not self.enabled:
            return
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def play_music(self, track_name: str) -> None:
        """지정된 배경음 트랙을 반복 재생한다."""
        if not self.enabled or self.current_music == track_name:
            return
        music_path = self.sound_dir / f"bgm_{track_name}.wav"
        try:
            pygame.mixer.music.load(music_path)
            volume = 0.24 if track_name == "menu" else 0.22 if track_name == "boss" else 0.20
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play(-1)
            self.current_music = track_name
        except pygame.error:
            self.current_music = None

    def stop_music(self) -> None:
        """현재 재생 중인 배경음을 중지한다."""
        if not self.enabled:
            return
        pygame.mixer.music.stop()
        self.current_music = None


def load_preview_sprites(project_root: Path) -> dict[UnitType, pygame.Surface]:
    """드래프트/도감용 축소 프리뷰 스프라이트를 불러온다."""
    sprite_dir = project_root / "assets" / "sprites"
    mapping = {
        UnitType.KING: sprite_dir / "king_blue.png",
        UnitType.SWORDMAN: sprite_dir / "swordman_blue.png",
        UnitType.ARCHER: sprite_dir / "archer_blue.png",
        UnitType.MAGE: sprite_dir / "mage_blue.png",
        UnitType.KNIGHT: sprite_dir / "knight_blue.png",
        UnitType.LANCER: sprite_dir / "lancer_blue.png",
        UnitType.BISHOP: sprite_dir / "bishop_blue.png",
    }
    previews: dict[UnitType, pygame.Surface] = {}
    for unit, path in mapping.items():
        previews[unit] = pygame.transform.scale(pygame.image.load(path).convert_alpha(), (68, 68))
    return previews


def render_button_label(font: pygame.font.Font, text: str) -> pygame.Surface:
    """버튼 텍스트를 UI 기본 색으로 렌더링한다."""
    return font.render(text, True, TEXT_COLOR)
