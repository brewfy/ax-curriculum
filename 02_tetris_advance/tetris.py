import pygame
import random
import sys
import time

# ── Terminal Stylization Constants ──────────────────────────────────────────
COLS, ROWS = 10, 20
CELL = 24                        # smaller cell for terminal feel
BOARD_W = COLS * CELL
BOARD_H = ROWS * CELL
SIDE_W  = 200
WIN_W   = BOARD_W + SIDE_W + 40  # margins
WIN_H   = BOARD_H + 60
FPS     = 60

# Terminal Green Palette
T_GREEN_BRIGHT = (50, 255, 50)
T_GREEN_DIM    = (0, 100, 0)
T_GREEN_MID    = (0, 180, 0)
BLACK          = (0, 0, 0)       # Pure Black

# Tetromino shapes (same as standard)
SHAPES = {
    'I': [[(0,1),(1,1),(2,1),(3,1)], [(2,0),(2,1),(2,2),(2,3)], [(0,2),(1,2),(2,2),(3,2)], [(1,0),(1,1),(1,2),(1,3)]],
    'O': [[(1,0),(2,0),(1,1),(2,1)], [(1,0),(2,0),(1,1),(2,1)], [(1,0),(2,0),(1,1),(2,1)], [(1,0),(2,0),(1,1),(2,1)]],
    'T': [[(1,0),(0,1),(1,1),(2,1)], [(1,0),(1,1),(2,1),(1,2)], [(0,1),(1,1),(2,1),(1,2)], [(1,0),(0,1),(1,1),(1,2)]],
    'S': [[(1,0),(2,0),(0,1),(1,1)], [(1,0),(1,1),(2,1),(2,2)], [(1,1),(2,1),(0,2),(1,2)], [(0,0),(0,1),(1,1),(1,2)]],
    'Z': [[(0,0),(1,0),(1,1),(2,1)], [(2,0),(1,1),(2,1),(1,2)], [(0,1),(1,1),(1,2),(2,2)], [(1,0),(0,1),(1,1),(0,2)]],
    'J': [[(0,0),(0,1),(1,1),(2,1)], [(1,0),(2,0),(1,1),(1,2)], [(0,1),(1,1),(2,1),(2,2)], [(1,0),(1,1),(0,2),(1,2)]],
    'L': [[(2,0),(0,1),(1,1),(2,1)], [(1,0),(1,1),(1,2),(2,2)], [(0,1),(1,1),(2,1),(0,2)], [(0,0),(1,0),(1,1),(1,2)]],
}
PIECE_TYPES = list(SHAPES.keys())

# ── Logic ────────────────────────────────────────────────────────────────────
class Piece:
    def __init__(self, kind=None):
        self.kind = kind or random.choice(PIECE_TYPES)
        self.rot = 0
        self.x = 3
        self.y = 0

    @property
    def shape(self):
        return SHAPES[self.kind][self.rot]

class Tetris:
    def __init__(self):
        self.board = [[None] * COLS for _ in range(ROWS)]
        self.current = Piece()
        self.next = Piece()
        self.score = 0
        self.level = 1
        self.lines = 0
        self.game_over = False
        self.fall_timer = 0

    def move(self, dx, dy):
        if self.is_valid(self.current.shape, self.current.x + dx, self.current.y + dy):
            self.current.x += dx
            self.current.y += dy
            return True
        return False

    def rotate(self):
        old_rot = self.current.rot
        self.current.rot = (self.current.rot + 1) % 4
        if not self.is_valid(self.current.shape, self.current.x, self.current.y):
            # Simple wall kick
            if self.is_valid(self.current.shape, self.current.x - 1, self.current.y):
                self.current.x -= 1
            elif self.is_valid(self.current.shape, self.current.x + 1, self.current.y):
                self.current.x += 1
            else:
                self.current.rot = old_rot

    def is_valid(self, shape, ox, oy):
        for dx, dy in shape:
            x, y = ox + dx, oy + dy
            if x < 0 or x >= COLS or y >= ROWS: return False
            if y >= 0 and self.board[y][x]: return False
        return True

    def lock(self):
        for dx, dy in self.current.shape:
            if self.current.y + dy >= 0:
                self.board[self.current.y + dy][self.current.x + dx] = '█'
        
        self.clear_lines()
        self.current = self.next
        self.next = Piece()
        if not self.is_valid(self.current.shape, self.current.x, self.current.y):
            self.game_over = True

    def clear_lines(self):
        lines_to_clear = [i for i, row in enumerate(self.board) if all(row)]
        for i in lines_to_clear:
            del self.board[i]
            self.board.insert(0, [None] * COLS)
        
        count = len(lines_to_clear)
        if count > 0:
            self.lines += count
            self.score += [0, 100, 300, 500, 800][count] * self.level
            self.level = self.lines // 10 + 1

    def update(self, dt):
        if self.game_over: return
        self.fall_timer += dt
        interval = max(100, 600 - (self.level - 1) * 50)
        if self.fall_timer > interval:
            if not self.move(0, 1):
                self.lock()
            self.fall_timer = 0

# ── Rendering ────────────────────────────────────────────────────────────────
def draw_terminal_text(surf, text, x, y, font, color=T_GREEN_BRIGHT, shadow=True):
    if shadow:
        s_img = font.render(text, True, T_GREEN_DIM)
        surf.blit(s_img, (x+1, y+1))
    img = font.render(text, True, color)
    surf.blit(img, (x, y))

def draw_scanlines(surf):
    """Adds a CRT scanline effect."""
    for y in range(0, WIN_H, 4):
        pygame.draw.line(surf, (0, 20, 0, 100), (0, y), (WIN_W, y))

def main():
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("TERMINAL_TETRIS_ADVANCE")
    clock = pygame.time.Clock()

    # Try to find a monospace font
    try:
        font_mono = pygame.font.SysFont("Consolas, Lucida Console, monospace", 20)
        font_big  = pygame.font.SysFont("Consolas, Lucida Console, monospace", 40)
    except:
        font_mono = pygame.font.Font(None, 24)
        font_big  = pygame.font.Font(None, 48)

    game = Tetris()
    
    # Pre-render CRT overlay
    crt_overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
    for y in range(0, WIN_H, 2):
        pygame.draw.line(crt_overlay, (0, 0, 0, 50), (0, y), (WIN_W, y))

    start_time = time.time()

    while True:
        dt = clock.tick(FPS)
        current_time = time.time()
        
        # Flicker effect calculation
        flicker = 230 + random.randint(0, 25)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN:
                if game.game_over:
                    if event.key == pygame.K_r: game = Tetris()
                    continue
                if event.key == pygame.K_LEFT: game.move(-1, 0)
                if event.key == pygame.K_RIGHT: game.move(1, 0)
                if event.key == pygame.K_DOWN: game.move(0, 1)
                if event.key == pygame.K_UP: game.rotate()
                if event.key == pygame.K_SPACE:
                    while game.move(0, 1): pass
                    game.lock()

        game.update(dt)

        # Clear Screen
        screen.fill(BLACK)
        
        # Main UI Margin
        ox, oy = 20, 20
        
        # Draw Border
        border_color = T_GREEN_MID
        pygame.draw.rect(screen, border_color, (ox-5, oy-5, BOARD_W+10, BOARD_H+10), 1)
        
        # Display "System Status" text
        draw_terminal_text(screen, f"[SYSTEM STATUS: ONLINE]", ox, oy - 25, font_mono)
        
        # Draw Board Blocks
        for r in range(ROWS):
            for c in range(COLS):
                if game.board[r][c]:
                    draw_terminal_text(screen, "█", ox + c*CELL, oy + r*CELL, font_mono)
                else:
                    # Faint grid dots for terminal look (very subtle)
                    pygame.draw.circle(screen, (0, 15, 0), (ox + c*CELL + CELL//2, oy + r*CELL + CELL//2), 1)

        # Draw Current Piece
        for dx, dy in game.current.shape:
            px, py = game.current.x + dx, game.current.y + dy
            if py >= 0:
                # Blinking effect for the active piece
                color = T_GREEN_BRIGHT if (int(current_time*4) % 2 == 0) else T_GREEN_MID
                draw_terminal_text(screen, "█", ox + px*CELL, oy + py*CELL, font_mono, color)

        # Side Panel Info
        sx = ox + BOARD_W + 30
        draw_terminal_text(screen, "┌──────────────┐", sx, oy, font_mono)
        draw_terminal_text(screen, "│ DATA MONITOR │", sx, oy + 20, font_mono)
        draw_terminal_text(screen, "├──────────────┤", sx, oy + 40, font_mono)
        draw_terminal_text(screen, f"│ SCORE: {game.score:06d}│", sx, oy + 70, font_mono)
        draw_terminal_text(screen, f"│ LEVEL: {game.level:02d}    │", sx, oy + 95, font_mono)
        draw_terminal_text(screen, f"│ LINES: {game.lines:03d}   │", sx, oy + 120, font_mono)
        draw_terminal_text(screen, "└──────────────┘", sx, oy + 145, font_mono)

        # Next Piece Preview
        draw_terminal_text(screen, "NEXT SEQUENCE:", sx, oy + 185, font_mono)
        pygame.draw.rect(screen, T_GREEN_DIM, (sx, oy + 210, 100, 80), 1)
        for dx, dy in game.next.shape:
            draw_terminal_text(screen, "█", sx + 20 + dx*CELL, oy + 225 + dy*CELL, font_mono)

        # Controls Hint
        draw_terminal_text(screen, "COMMANDS:", sx, oy + 320, font_mono, T_GREEN_MID)
        draw_terminal_text(screen, " < > : MOVE", sx, oy + 345, font_mono, T_GREEN_MID)
        draw_terminal_text(screen, "  ^  : ROTATE", sx, oy + 365, font_mono, T_GREEN_MID)
        draw_terminal_text(screen, " SPC : DROP", sx, oy + 385, font_mono, T_GREEN_MID)

        # CRT Post-processing
        # Apply scanlines overlay (pure black lines for contrast)
        screen.blit(crt_overlay, (0, 0))
        
        # Subtle Flicker (White flicker for brightness variation without color tint)
        overlay = pygame.Surface((WIN_W, WIN_H))
        overlay.set_alpha(max(0, 255 - flicker))
        overlay.fill((10, 10, 10)) # Very faint gray pulse
        screen.blit(overlay, (0,0), special_flags=pygame.BLEND_RGB_ADD)

        # Game Over Overlay
        if game.game_over:
            s = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
            s.fill((0, 20, 0, 180))
            screen.blit(s, (0, 0))
            draw_terminal_text(screen, "FATAL ERROR: SYSTEM CRASH", WIN_W//2 - 140, WIN_H//2 - 40, font_mono, (255, 50, 50))
            draw_terminal_text(screen, "PRESS 'R' TO REBOOT", WIN_W//2 - 100, WIN_H//2, font_mono)

        pygame.display.flip()

if __name__ == "__main__":
    main()
