from __future__ import annotations

"""
High-level runtime systems.

Use this package for the main game manager and rendering systems.
"""

from game.engine.game_manager import AI_HOME_POSITIONS, AI_KING_POS, BASE_HP, PLAYER_HOME_POSITIONS, PLAYER_KING_POS, GameManager
from game.engine.renderer import Renderer, board_tile_at_pixel

__all__ = [
    "AI_HOME_POSITIONS",
    "AI_KING_POS",
    "BASE_HP",
    "GameManager",
    "PLAYER_HOME_POSITIONS",
    "PLAYER_KING_POS",
    "Renderer",
    "board_tile_at_pixel",
]
