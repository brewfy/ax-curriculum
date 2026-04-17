"""All pygame drawing. Game logic must not live here."""
import pygame
from constants import (
    CELL, COLS, ROWS, BOARD_W, BOARD_H, SIDE_W, WIN_W, WIN_H,
    BLACK, GRAY, DGRAY, WHITE, RED,
)


def _make_font(size: int) -> pygame.font.Font:
    for name in ("malgungothic", "gulim", "nanumgothic", "segoeui", "arial"):
        try:
            f = pygame.font.SysFont(name, size)
            if f:
                return f
        except Exception:
            pass
    return pygame.font.Font(None, size)


class Renderer:
    def __init__(self):
        self.font_xl = _make_font(52)
        self.font_lg = _make_font(28)
        self.font_md = _make_font(22)
        self.font_sm = _make_font(17)

    # ── primitives ────────────────────────────────────────────────────────────
    def _cell(self, surf: pygame.Surface, color, gx: int, gy: int, alpha: int = 255):
        x, y = gx * CELL, gy * CELL
        rect  = pygame.Rect(x, y, CELL - 1, CELL - 1)
        if alpha < 255:
            s = pygame.Surface((CELL - 1, CELL - 1), pygame.SRCALPHA)
            s.fill((*color, alpha))
            surf.blit(s, (x, y))
        else:
            pygame.draw.rect(surf, color, rect)
            light = tuple(min(c + 60, 255) for c in color)
            pygame.draw.line(surf, light, rect.topleft, rect.topright, 2)
            pygame.draw.line(surf, light, rect.topleft, rect.bottomleft, 2)

    def _mini_piece(self, surf: pygame.Surface, piece, ox: int, oy: int,
                    dim: bool = False):
        """Draw a piece preview at pixel offset (ox, oy) using CELL size."""
        color = tuple(c // 3 for c in piece.color) if dim else piece.color
        tmp = pygame.Surface((4 * CELL, 4 * CELL), pygame.SRCALPHA)
        tmp.fill((0, 0, 0, 0))
        for dx, dy in piece.shape:
            self._cell(tmp, color, dx, dy)
        surf.blit(tmp, (ox, oy))

    def _hline(self, surf: pygame.Surface, y: int):
        pygame.draw.line(surf, GRAY,
                         (BOARD_W + 5, y), (BOARD_W + SIDE_W - 10, y), 1)

    # ── board ─────────────────────────────────────────────────────────────────
    def draw_board(self, surf: pygame.Surface, board: list):
        for r in range(ROWS):
            for c in range(COLS):
                pygame.draw.rect(surf, DGRAY,
                                 (c * CELL, r * CELL, CELL - 1, CELL - 1))
        for r in range(ROWS):
            for c in range(COLS):
                if board[r][c]:
                    self._cell(surf, board[r][c], c, r)

    # ── current piece + ghost ─────────────────────────────────────────────────
    def draw_piece(self, surf: pygame.Surface, piece, ghost_y: int = None):
        if ghost_y is not None and ghost_y != piece.y:
            for dx, dy in piece.shape:
                gx, gy = piece.x + dx, ghost_y + dy
                if gy >= 0:
                    self._cell(surf, piece.color, gx, gy, alpha=55)
        for dx, dy in piece.shape:
            gx, gy = piece.x + dx, piece.y + dy
            if gy >= 0:
                self._cell(surf, piece.color, gx, gy)

    # ── side panel ────────────────────────────────────────────────────────────
    def draw_side(self, surf: pygame.Surface, game):
        x = BOARD_W + 10  # left edge of side content

        def lbl(text, y, color=(160, 160, 160)):
            surf.blit(self.font_sm.render(text, True, color), (x, y))

        def val(text, y, color=WHITE):
            surf.blit(self.font_md.render(text, True, color), (x, y))

        # ── NEXT ────────────────────────────────────────────────────────────
        lbl("NEXT", 8)
        self._mini_piece(surf, game.next, x, 28)

        self._hline(surf, 162)

        # ── HOLD ────────────────────────────────────────────────────────────
        lbl("HOLD", 170)
        if game.held:
            self._mini_piece(surf, game.held, x, 190, dim=game.hold_used)
        else:
            lbl("---", 210)

        self._hline(surf, 324)

        # ── STATS ───────────────────────────────────────────────────────────
        y_s = 332
        for title, value in (
            ("SCORE", str(game.score)),
            ("BEST",  str(game.high_score)),
            ("LEVEL", str(game.level)),
            ("LINES", str(game.lines)),
        ):
            lbl(title, y_s)
            val(value,  y_s + 17)
            y_s += 48

        self._hline(surf, y_s + 4)

        # ── CONTROLS ────────────────────────────────────────────────────────
        y_h = y_s + 14
        for hint in (
            "← → : Move",
            "↑ / X : Rotate CW",
            "Z : Rotate CCW",
            "↓ : Soft drop",
            "Space : Hard drop",
            "C : Hold",
            "P : Pause   R : Restart",
        ):
            surf.blit(self.font_sm.render(hint, True, (100, 100, 100)), (x, y_h))
            y_h += 16

    # ── overlay helpers ───────────────────────────────────────────────────────
    def _overlay_bg(self, surf: pygame.Surface):
        bg = pygame.Surface((BOARD_W, BOARD_H), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 170))
        surf.blit(bg, (0, 0))

    def draw_pause_overlay(self, surf: pygame.Surface):
        self._overlay_bg(surf)
        cx = BOARD_W // 2
        for text, font, color, y in (
            ("PAUSED",     self.font_xl, WHITE,           BOARD_H // 2 - 40),
            ("P  to resume", self.font_sm, (180, 180, 180), BOARD_H // 2 + 20),
        ):
            msg = font.render(text, True, color)
            surf.blit(msg, msg.get_rect(center=(cx, y)))

    def draw_gameover_overlay(self, surf: pygame.Surface, score: int):
        self._overlay_bg(surf)
        cx = BOARD_W // 2
        for text, font, color, y in (
            ("GAME OVER",       self.font_xl, RED,            BOARD_H // 2 - 60),
            (f"Score: {score}", self.font_lg, WHITE,          BOARD_H // 2),
            ("R  to restart",   self.font_sm, (180, 180, 180), BOARD_H // 2 + 50),
        ):
            msg = font.render(text, True, color)
            surf.blit(msg, msg.get_rect(center=(cx, y)))

    # ── start screen ──────────────────────────────────────────────────────────
    def draw_start(self, surf: pygame.Surface):
        surf.fill(BLACK)
        cx, cy = WIN_W // 2, WIN_H // 2

        items = [
            ("TETRIS",                self.font_xl, (0, 240, 240)),
            ("",                      self.font_sm, WHITE),
            ("Press  ENTER  to start",self.font_md, WHITE),
            ("",                      self.font_sm, WHITE),
            ("← →   Move",           self.font_sm, (120, 120, 120)),
            ("↑ / X   Rotate CW",     self.font_sm, (120, 120, 120)),
            ("Z       Rotate CCW",    self.font_sm, (120, 120, 120)),
            ("Space   Hard drop",     self.font_sm, (120, 120, 120)),
            ("C       Hold",          self.font_sm, (120, 120, 120)),
            ("P / R   Pause / Restart",self.font_sm,(120, 120, 120)),
        ]
        total_h = len(items) * 30
        y = cy - total_h // 2
        for text, font, color in items:
            msg = font.render(text, True, color)
            surf.blit(msg, msg.get_rect(center=(cx, y)))
            y += 30

    # ── full game frame ───────────────────────────────────────────────────────
    def draw_game(self, surf: pygame.Surface, game):
        surf.fill(BLACK)

        board_surf = pygame.Surface((BOARD_W, BOARD_H))
        board_surf.fill(BLACK)
        self.draw_board(board_surf, game.board)

        if not game.game_over and not game.paused:
            self.draw_piece(board_surf, game.current, ghost_y=game.ghost_y())

        surf.blit(board_surf, (0, 0))
        self.draw_side(surf, game)

        if game.paused and not game.game_over:
            self.draw_pause_overlay(surf)
        elif game.game_over:
            self.draw_gameover_overlay(surf, game.score)
