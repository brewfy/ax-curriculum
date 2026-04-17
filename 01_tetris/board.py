"""Pure functions that operate on the board grid.

The board is a list[list[color | None]] with shape (ROWS, COLS).
No pygame dependency — fully testable without a display.
"""
from constants import COLS, ROWS


def empty_board() -> list:
    return [[None] * COLS for _ in range(ROWS)]


def is_valid(board: list, shape: list, ox: int, oy: int) -> bool:
    for dx, dy in shape:
        x, y = ox + dx, oy + dy
        if x < 0 or x >= COLS or y >= ROWS:
            return False
        if y >= 0 and board[y][x] is not None:
            return False
    return True


def lock_piece(board: list, shape: list, ox: int, oy: int, color) -> None:
    for dx, dy in shape:
        x, y = ox + dx, oy + dy
        if 0 <= y < ROWS and 0 <= x < COLS:
            board[y][x] = color


def clear_lines(board: list) -> tuple:
    """Remove full rows, return (new_board, num_cleared)."""
    new_board = [row for row in board if any(c is None for c in row)]
    cleared   = ROWS - len(new_board)
    new_board = [[None] * COLS for _ in range(cleared)] + new_board
    return new_board, cleared
