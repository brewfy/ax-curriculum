import random
from constants import SHAPES, COLORS, PIECE_TYPES


class Piece:
    def __init__(self, kind: str = None):
        self.kind  = kind or random.choice(PIECE_TYPES)
        self.rot   = 0
        self.color = COLORS[self.kind]
        self.x     = 3
        self.y     = 0

    @property
    def shape(self) -> list:
        return SHAPES[self.kind][self.rot]

    def rotated(self, dr: int = 1) -> list:
        return SHAPES[self.kind][(self.rot + dr) % 4]
