"""Entry point. Owns the game loop; delegates everything else."""
import sys
import pygame
from constants import WIN_W, WIN_H, FPS
from game import Tetris
from renderer import Renderer
from input_handler import InputHandler


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Tetris")
    clock = pygame.time.Clock()

    renderer = Renderer()
    handler  = InputHandler()
    game     = None
    state    = "start"   # "start" | "playing"

    while True:
        dt = clock.tick(FPS)

        # ── events ────────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if state == "start":
                if (event.type == pygame.KEYDOWN
                        and event.key == pygame.K_RETURN):
                    game  = Tetris()
                    handler.reset()
                    state = "playing"

            elif state == "playing":
                if event.type == pygame.KEYDOWN:
                    if handler.handle_keydown(event, game):
                        game = Tetris()
                        handler.reset()
                elif event.type == pygame.KEYUP:
                    handler.handle_keyup(event)

        # ── update ────────────────────────────────────────────────────────────
        if state == "playing":
            handler.update_das(dt, game)
            game.update(dt)

        # ── render ────────────────────────────────────────────────────────────
        if state == "start":
            renderer.draw_start(screen)
        else:
            renderer.draw_game(screen, game)

        pygame.display.flip()


if __name__ == "__main__":
    main()
