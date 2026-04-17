"""Translates pygame events into game actions.

Handles DAS (Delayed Auto Shift) so horizontal movement feels responsive.
Returns True from handle_keydown when a game reset is requested.
"""
import pygame
from constants import DAS_DELAY, DAS_REPEAT
from game import Tetris


class InputHandler:
    def __init__(self):
        self._das_left  = 0
        self._das_right = 0

    def reset(self):
        self._das_left  = 0
        self._das_right = 0

    def handle_keydown(self, event: pygame.event.Event, game: Tetris) -> bool:
        """Process a KEYDOWN event. Returns True if game should reset."""
        if event.key == pygame.K_r:
            return True

        if game.game_over:
            return False

        if event.key == pygame.K_p:
            game.paused = not game.paused
            return False

        if game.paused:
            return False

        if event.key == pygame.K_LEFT:
            game.move(-1)
            self._das_left = -DAS_DELAY   # delay before auto-repeat
        elif event.key == pygame.K_RIGHT:
            game.move(1)
            self._das_right = -DAS_DELAY
        elif event.key in (pygame.K_UP, pygame.K_x):
            game.rotate(1)
        elif event.key == pygame.K_z:
            game.rotate(-1)
        elif event.key == pygame.K_DOWN:
            game.soft_drop()
        elif event.key == pygame.K_SPACE:
            game.hard_drop()
        elif event.key in (pygame.K_c, pygame.K_LSHIFT, pygame.K_RSHIFT):
            game.hold()

        return False

    def handle_keyup(self, event: pygame.event.Event):
        if event.key == pygame.K_LEFT:
            self._das_left  = 0
        elif event.key == pygame.K_RIGHT:
            self._das_right = 0

    def update_das(self, dt: int, game: Tetris):
        """Call once per frame to apply auto-repeat movement."""
        if game.game_over or game.paused:
            return
        keys = pygame.key.get_pressed()

        if keys[pygame.K_LEFT]:
            self._das_left += dt
            if self._das_left >= DAS_REPEAT:
                self._das_left = 0
                game.move(-1)
        else:
            self._das_left = 0

        if keys[pygame.K_RIGHT]:
            self._das_right += dt
            if self._das_right >= DAS_REPEAT:
                self._das_right = 0
                game.move(1)
        else:
            self._das_right = 0
