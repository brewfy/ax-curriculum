"""Game state — no pygame, no rendering."""
from board import empty_board, is_valid, lock_piece, clear_lines
from piece import Piece
from highscore import load as load_high, save as save_high
from constants import SCORE_TABLE


class Tetris:
    def __init__(self):
        self.reset()

    def reset(self):
        self.board       = empty_board()
        self.current     = Piece()
        self.next        = Piece()
        self.held        = None      # Piece | None
        self.hold_used   = False     # one hold per placed piece
        self.score       = 0
        self.high_score  = load_high()
        self.level       = 1
        self.lines       = 0
        self.game_over   = False
        self.paused      = False
        self._fall_timer = 0

    # ── timing ────────────────────────────────────────────────────────────────
    def fall_interval(self) -> int:
        """Gravity interval in ms. Decreases with level."""
        return max(80, 600 - (self.level - 1) * 50)

    # ── spawn ─────────────────────────────────────────────────────────────────
    def _spawn(self):
        self.current   = self.next
        self.next      = Piece()
        self.hold_used = False
        if not is_valid(self.board, self.current.shape,
                        self.current.x, self.current.y):
            self.game_over = True
            save_high(self.score)
            if self.score > self.high_score:
                self.high_score = self.score

    # ── player actions ────────────────────────────────────────────────────────
    def move(self, dx: int):
        nx = self.current.x + dx
        if is_valid(self.board, self.current.shape, nx, self.current.y):
            self.current.x = nx

    def rotate(self, dr: int = 1):
        new_shape = self.current.rotated(dr)
        for kick in (0, -1, 1, -2, 2):
            nx = self.current.x + kick
            if is_valid(self.board, new_shape, nx, self.current.y):
                self.current.x   = nx
                self.current.rot = (self.current.rot + dr) % 4
                break

    def hold(self):
        if self.hold_used:
            return
        if self.held is None:
            self.held = Piece(self.current.kind)
            self._spawn()
        else:
            incoming      = Piece(self.held.kind)
            self.held     = Piece(self.current.kind)
            self.current  = incoming
        self.hold_used = True

    def soft_drop(self):
        ny = self.current.y + 1
        if is_valid(self.board, self.current.shape, self.current.x, ny):
            self.current.y = ny
            self.score    += 1
        else:
            self._lock()

    def hard_drop(self):
        while is_valid(self.board, self.current.shape,
                       self.current.x, self.current.y + 1):
            self.current.y += 1
            self.score     += 2
        self._lock()

    # ── internal ──────────────────────────────────────────────────────────────
    def _lock(self):
        lock_piece(self.board, self.current.shape,
                   self.current.x, self.current.y, self.current.color)
        self.board, cleared = clear_lines(self.board)
        if cleared:
            self.score += SCORE_TABLE.get(cleared, 0) * self.level
            self.lines += cleared
            self.level  = self.lines // 10 + 1
        self._spawn()

    def update(self, dt: int):
        if self.game_over or self.paused:
            return
        self._fall_timer += dt
        if self._fall_timer >= self.fall_interval():
            self._fall_timer = 0
            ny = self.current.y + 1
            if is_valid(self.board, self.current.shape, self.current.x, ny):
                self.current.y = ny
            else:
                self._lock()

    def ghost_y(self) -> int:
        gy = self.current.y
        while is_valid(self.board, self.current.shape, self.current.x, gy + 1):
            gy += 1
        return gy
