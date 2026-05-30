"""
treasure_chest.py — Animated treasure chest decor for Aquarium 98.

The chest sits on the tank floor over the left rocky outcrop, cycling:
  cooldown → opening (9-frame animation) → open (glow + waits for click)
           → closing (reverse animation) → cooldown

Difficulty scales both the cooldown between openings and the coin reward:
  1 (Easy)   : cooldown  90-180 s,  coins 15-35
  2 (Normal) : cooldown 150-300 s,  coins 10-25
  3 (Hard)   : cooldown 240-480 s,  coins  5-15

Sprite sheet: assets/sprites/decor/TreasureChest.png
  3 cols × 3 rows = 9 frames (row-major, left→right, top→bottom)
  Frame 0      : fully closed
  Frames 1-5   : opening animation
  Frames 6-8   : fully open / coin-spill poses (cycled while idle-open)
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import pygame

# ---------------------------------------------------------------------------
# Layout constants (interior reference space: 448 × 274 px)
# ---------------------------------------------------------------------------
CHEST_IX    = 72    # interior X of chest centre  (left rocky outcrop)
CHEST_IY    = 272   # interior Y of chest bottom  (near tank floor)
CHEST_REF_W = 90    # reference draw width  (at 1:1 scale)
CHEST_REF_H = 49    # reference draw height (ratio ≈ 1.84 matches sprite)

# ---------------------------------------------------------------------------
# Animation timing
# ---------------------------------------------------------------------------
_OPEN_FPS   = 7.0   # frames per second during opening
_CLOSE_FPS  = 9.0   # slightly faster on close
OPEN_WAIT   = 28.0  # seconds the chest stays open before auto-closing

# ---------------------------------------------------------------------------
# Economy tables
# ---------------------------------------------------------------------------

# Tiered jackpot table — each entry:
#   (weight, base_min, base_max)
# A random tier is drawn by weighted choice, then the reward is
# randint(base_min, base_max) so no two chests ever give the exact same amount.
# Weights are relative; higher weight = more common.
#   ~"jackpot"   ≈100 coins  weight  1   (≈1.6 %)
#   ~"big"       ≈ 75 coins  weight  3   (≈4.8 %)
#   ~"decent"    ≈ 50 coins  weight  8   (≈12.9%)
#   ~"small"     ≈ 25 coins  weight 16   (≈25.8%)
#   ~"pocket"    ≈ 10 coins  weight 34   (≈54.8%)
_JACKPOT_TIERS: list[tuple[int, int, int]] = [
    ( 1,  90, 110),   # jackpot   ~100
    ( 3,  65,  85),   # big       ~ 75
    ( 8,  42,  58),   # decent    ~ 50
    (16,  18,  32),   # small     ~ 25
    (34,   6,  14),   # pocket    ~ 10
]

# Difficulty scales the pocket-change floor — harder difficulties also
# reduce the effective weight of the top two tiers.
_DIFF_TIER_WEIGHT_MULT: dict[int, list[float]] = {
    # jackpot  big  decent  small  pocket
    1: [1.6,  1.4,  1.2,   1.0,   0.8],   # Easy   — jackpots more likely
    2: [1.0,  1.0,  1.0,   1.0,   1.0],   # Normal — baseline
    3: [0.7,  0.8,  0.9,   1.0,   1.2],   # Hard
    4: [0.4,  0.6,  0.8,   1.0,   1.4],
    5: [0.2,  0.4,  0.7,   1.0,   1.6],
}

# Difficulty also applies a flat coins multiplier to base ranges
_DIFF_COIN_MULT: dict[int, float] = {
    1: 1.20,
    2: 1.00,
    3: 0.80,
    4: 0.60,
    5: 0.45,
}


def _roll_coins(difficulty: int) -> int:
    """Pick a randomised coin reward from the tiered jackpot table."""
    mults = _DIFF_TIER_WEIGHT_MULT.get(difficulty, _DIFF_TIER_WEIGHT_MULT[2])
    coin_mult = _DIFF_COIN_MULT.get(difficulty, 1.0)
    weights   = [max(0.01, _JACKPOT_TIERS[i][0] * mults[i]) for i in range(len(_JACKPOT_TIERS))]
    tier      = random.choices(_JACKPOT_TIERS, weights=weights, k=1)[0]
    lo        = max(1, int(tier[1] * coin_mult))
    hi        = max(lo + 1, int(tier[2] * coin_mult))
    return random.randint(lo, hi)


_COOLDOWN: dict[int, tuple[int, int]] = {
    1: (90,  180),
    2: (150, 300),
    3: (240, 480),
    4: (360, 720),
    5: (480, 900),
}

# How many existing bubbles to redirect to the chest on open
_BURST_COUNT = 6


# ---------------------------------------------------------------------------
# Chest state machine
# ---------------------------------------------------------------------------
@dataclass
class TreasureChest:
    state: str   = "cooldown"   # cooldown | opening | open | closing
    timer: float = 0.0          # seconds until next transition
    frame: float = 0.0          # float frame index (0.0 – 8.9)
    pending_coins: int = 0      # coins to award when clicked

    # Screen rect updated each draw() — used for click detection
    _rect: pygame.Rect = field(default_factory=lambda: pygame.Rect(0, 0, 0, 0))
    # Glow halo surface (SRCALPHA) — reused each frame to avoid per-frame alloc
    _glow_surf: pygame.Surface | None = field(default=None, repr=False)
    _glow_size: tuple[int, int] = (0, 0)
    # Scaled sprite cache: (frame_index, draw_w, draw_h) → Surface
    _frame_cache: dict = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------ #
    def reset_cooldown(self, difficulty: int = 2) -> None:
        lo, hi = _COOLDOWN.get(difficulty, _COOLDOWN[2])
        self.timer = random.uniform(lo, hi)
        self.state = "cooldown"
        self.frame = 0.0

    # ------------------------------------------------------------------ #
    def update(self, dt: float, cfg: dict) -> list[tuple[float, float]]:
        """Advance the state machine one tick.

        Returns a list of interior (x, y) positions for burst bubbles;
        non-empty only during the single tick that enters the 'open' state.
        """
        burst: list[tuple[float, float]] = []
        diff = int(cfg.get("difficulty", 2))

        if self.state == "cooldown":
            self.timer -= dt
            if self.timer <= 0.0:
                self.pending_coins = _roll_coins(diff)
                self.state = "opening"
                self.frame = 0.0

        elif self.state == "opening":
            self.frame += dt * _OPEN_FPS
            if self.frame >= 6.0:
                self.frame = 6.0
                self.state = "open"
                self.timer = OPEN_WAIT
                # Spawn burst bubbles from chest top
                for _ in range(_BURST_COUNT):
                    bx = CHEST_IX + random.uniform(-24, 24)
                    by = CHEST_IY - random.uniform(10, 28)
                    burst.append((bx, by))

        elif self.state == "open":
            # Shimmer: slowly cycle frames 6 / 7 / 8
            self.frame = 6.0 + (int(self.timer * 2.5) % 3)
            self.timer -= dt
            if self.timer <= 0.0:
                # Timed out without a click — close without reward
                self.pending_coins = 0
                self.state = "closing"
                self.frame = 8.0

        elif self.state == "closing":
            self.frame -= dt * _CLOSE_FPS
            if self.frame <= 0.0:
                self.frame = 0.0
                self.reset_cooldown(diff)

        return burst

    # ------------------------------------------------------------------ #
    def handle_click(self, screen_x: int, screen_y: int) -> int:
        """Return coin reward if the chest is open and the click lands on it."""
        if self.state != "open":
            return 0
        if self._rect.collidepoint(screen_x, screen_y):
            reward = self.pending_coins
            self.pending_coins = 0
            self.state = "closing"
            self.frame = 8.0
            return reward
        return 0

    # ------------------------------------------------------------------ #
    def draw(self, surface: pygame.Surface, tr: pygame.Rect,
             sheet: pygame.Surface | None) -> None:
        """Render the chest scaled to the current tank rect."""
        if sheet is None:
            return

        rx = tr.w / 448
        ry = tr.h / 274
        # Use uniform scale to preserve the sprite's natural aspect ratio
        scale = min(rx, ry)
        dw = max(20, int(CHEST_REF_W * scale))
        dh = max(10, int(CHEST_REF_H * scale))
        cx = tr.left + int(CHEST_IX * rx)
        cy = tr.top  + int(CHEST_IY * ry)
        sx = cx - dw // 2
        sy = cy - dh        # top of chest

        # Extract frame from 3×3 sheet — use per-(fi, dw, dh) cache
        fi  = max(0, min(8, int(self.frame)))
        cache_key = (fi, dw, dh)
        if cache_key not in self._frame_cache:
            # Evict stale entries when the cache grows too large (e.g. after
            # many window resizes) to avoid unbounded surface accumulation.
            if len(self._frame_cache) >= 32:
                # LRU eviction: drop oldest 8 entries rather than clearing all 32
                # to avoid a rendering spike after many window resizes.
                self._frame_cache = dict(list(self._frame_cache.items())[8:])
            sw, sh = sheet.get_size()
            fw, fh = sw // 3, sh // 3
            col, row = fi % 3, fi // 3
            frame_surf = sheet.subsurface(pygame.Rect(col * fw, row * fh, fw, fh))
            self._frame_cache[cache_key] = pygame.transform.smoothscale(frame_surf, (dw, dh))
        scaled = self._frame_cache[cache_key]

        # Pulsing glow halo when open (drawn behind chest)
        if self.state == "open":
            pulse = 0.55 + 0.45 * abs(((self.timer * 2.5) % 2.0) - 1.0)
            glow_a = max(0, min(255, int(25 + 50 * pulse)))
            glow_w = dw + 18
            glow_h = dh + 14
            # Reuse the glow surface; rebuild only when size changes
            if self._glow_surf is None or self._glow_size != (glow_w, glow_h):
                self._glow_surf = pygame.Surface((glow_w, glow_h), pygame.SRCALPHA)
                self._glow_size = (glow_w, glow_h)
            self._glow_surf.fill((0, 0, 0, 0))
            pygame.draw.ellipse(self._glow_surf, (255, 215, 50, glow_a),
                                self._glow_surf.get_rect())
            surface.blit(self._glow_surf, (sx - 9, sy - 7))

        surface.blit(scaled, (sx, sy))

        # Cache screen rect for click testing
        self._rect = pygame.Rect(sx, sy, dw, dh)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def make_chest(difficulty: int = 2) -> TreasureChest:
    chest = TreasureChest()
    # First opening is quick so players discover the mechanic early
    chest.timer = random.uniform(20, 45)
    chest.state = "cooldown"
    return chest
