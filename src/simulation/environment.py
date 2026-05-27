"""
environment.py — bubbles, food flakes, algae growth, day/night cycle.

Follows FishPOC.lua (active Rainmeter path):
  - 6 fixed bubble objects, never added/removed; reset on reaching surface.
  - 30 fixed food slots (10 back + 10 mid + 10 front), layer-fixed.
  - Algae 0–100 percentage scale; density-based growth; 8% removed per scrub.
  - Day/night: 20-minute full cycle (modular path feature).

Bubble pool Y-caps (prevent spawning inside decorations):
  - Layer 2: castleTopY = tank_h - 94
  - Layer 3: coralTopY  = floor(251/768 * tank_h)
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def castle_top_y(tank_h: int) -> int:
    """Y above which layer-2 bubbles spawn (castle roof cap)."""
    return tank_h - 94


def coral_top_y(tank_h: int) -> int:
    """Y above which layer-3 bubbles spawn (coral canopy cap)."""
    return int(251 / 768 * tank_h)


# ---------------------------------------------------------------------------
# Bubble pool  (6 fixed objects, from FishPOC.lua)
# ---------------------------------------------------------------------------

_BUBBLE_BASE_SIZES = [16, 12, 18, 10, 14, 11]
_BUBBLE_INIT_LAYERS = [1, 2, 3, 1, 2, 3]


@dataclass
class Bubble:
    x: float
    y: float
    vy: float           # negative = rising
    sway: float         # current sway phase (rad)
    sway_spd: float     # oscillation speed (rad/s)
    base_size: int      # nominal diameter (px); render size = base_size * layerScale
    layer: int          # 1/2/3
    sprite_idx: int     # 0/1/2 → bubble_new.png / bubble_new2.png / bubble_new3.png


def _reset_bubble(b: Bubble, tank_w: int, tank_h: int) -> None:
    b.x = float(random.randint(14, max(15, tank_w - 14)))
    b.vy = -(16.0 + random.randint(0, 16))
    b.sway = random.randint(0, 628) / 100.0
    b.layer = random.randint(1, 3)
    b.sprite_idx = random.randint(0, 2)
    ctop = castle_top_y(tank_h)
    corp = coral_top_y(tank_h)
    if b.layer == 2:
        max_y = ctop
    elif b.layer == 3:
        max_y = corp
    else:
        max_y = tank_h
    b.y = float(max(4, max_y - random.randint(4, 20)))


# ---------------------------------------------------------------------------
# Food pool  (30 fixed slots: 10 back + 10 mid + 10 front)
# ---------------------------------------------------------------------------

_FOOD_LAYERS = [3]*10 + [2]*10 + [1]*10  # 30 total slots


@dataclass
class Food:
    active: bool
    layer: int          # 1/2/3 — fixed for the lifetime of this slot
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    eaten: bool = False  # set True by fish AI; cleared when slot deactivates
    flake_idx: int = 0   # which of the 9 flake sprites to draw (randomised on spawn)
    grounded: bool = False    # True once food settles on the floor
    ground_timer: float = 0.0  # seconds sitting on floor; >30s → algae boost + remove


def _init_food(food: Food, ix: float, iy: float) -> None:
    food.active = True
    food.eaten = False
    food.grounded = False
    food.ground_timer = 0.0
    food.x = ix + (random.random() - 0.5) * 32.0
    food.y = iy + (random.random() - 0.5) * 12.0
    food.vy = 9.0 + random.random() * 7.0
    food.vx = (random.random() - 0.5) * 3.0
    food.flake_idx = random.randint(0, 8)


# ---------------------------------------------------------------------------
# Environment container
# ---------------------------------------------------------------------------

@dataclass
class Environment:
    tank_w: int
    tank_h: int
    bubbles: list[Bubble] = field(default_factory=list)
    food: list[Food] = field(default_factory=list)
    algae: float = 0.0          # 0–100 (percentage)
    day_time: float = 0.0       # 0.0–1.0 cycle position
    night_factor: float = 0.0   # 0=full day, 1=full night (cached for renderer)


def make_environment(tank_w: int, tank_h: int) -> Environment:
    env = Environment(tank_w=tank_w, tank_h=tank_h)

    # 6 fixed bubbles, staggered across the water column on init
    for i in range(6):
        b = Bubble(
            x=float(random.randint(14, max(15, tank_w - 14))),
            y=0.0,
            vy=0.0,
            sway=random.randint(0, 628) / 100.0,
            sway_spd=1.2 + random.randint(0, 22) / 10.0,
            base_size=_BUBBLE_BASE_SIZES[i],
            layer=_BUBBLE_INIT_LAYERS[i],
            sprite_idx=random.randint(0, 2),
        )
        _reset_bubble(b, tank_w, tank_h)
        b.y = random.uniform(tank_h * 0.05, tank_h * 0.90)  # stagger initial heights
        env.bubbles.append(b)

    # 30 fixed food slots (10 back + 10 mid + 10 front)
    for layer in _FOOD_LAYERS:
        env.food.append(Food(active=False, layer=layer))

    return env


# ---------------------------------------------------------------------------
# Food spawning
# ---------------------------------------------------------------------------

def spawn_food_at(env: Environment, ix: float, iy: float,
                  count: int | None = None) -> int:
    """Drop 3–5 food flakes centred on interior coords (ix, iy).

    First pass fills a random preferred layer; second fills any free slot.
    If all existing food slots are active, create extra slots so clicks never
    fail due to a hard food cap.
    Returns number of flakes actually spawned.
    """
    if count is None:
        count = random.randint(3, 5)
    target_layer = random.randint(1, 3)
    spawned = 0
    for food in env.food:
        if not food.active and food.layer == target_layer and spawned < count:
            _init_food(food, ix, iy)
            spawned += 1
    for food in env.food:
        if not food.active and spawned < count:
            _init_food(food, ix, iy)
            spawned += 1
    _FOOD_HARD_CAP = 90  # never exceed 3× the nominal 30-slot pool
    while spawned < count and len(env.food) < _FOOD_HARD_CAP:
        extra = Food(active=False, layer=target_layer)
        _init_food(extra, ix, iy)
        env.food.append(extra)
        spawned += 1
    return spawned


def add_food(env: Environment, x: float, count: int = 4) -> None:
    """Backward-compat shim: drop food at interior-x from near the top."""
    spawn_food_at(env, x, 4.0, count)


def clean_algae(env: Environment) -> None:
    """Scrub: remove 8% algae per click (FishPOC.lua ScrubAt)."""
    env.algae = max(0.0, env.algae - 8.0)


# ---------------------------------------------------------------------------
# Bubble screen-hit helper
# ---------------------------------------------------------------------------

# Scaled bubble sizes mirror renderer._draw_bubbles_layer
_BUBBLE_LAYER_SCALE = {1: 1.0, 2: 0.82, 3: 0.66}


def pop_bubble_at(env: Environment, screen_x: int, screen_y: int,
                  tr_left: int, tr_top: int) -> tuple[int, int] | None:
    """Check if (screen_x, screen_y) hits any bubble; pop+respawn it.

    Returns the (screen_x, screen_y) of the popped bubble if one was hit,
    else None.  Callers can use the returned coords for coin popup placement.
    """
    for b in env.bubbles:
        ls   = _BUBBLE_LAYER_SCALE.get(b.layer, 1.0)
        size = max(6, int(b.base_size * ls * 1.5))
        bx   = tr_left + int(b.x)
        by   = tr_top  + int(b.y)
        if abs(screen_x - bx) <= size // 2 + 2 and \
           abs(screen_y - by) <= size // 2 + 2:
            _reset_bubble(b, env.tank_w, env.tank_h)
            return (bx, by)
    return None


def spawn_chest_burst(env: Environment, burst_positions: list[tuple[float, float]]) -> None:
    """Redirect a handful of existing bubbles to rise from the chest opening.

    *burst_positions* is a list of (interior_x, interior_y) tuples returned
    by TreasureChest.update().  We pick that many bubbles from the pool
    (capped by pool size) and snap them to the supplied coordinates so they
    rise up through the tank naturally — no structural changes needed.
    """
    count = min(len(burst_positions), len(env.bubbles))
    if count == 0:
        return
    chosen = random.sample(env.bubbles, count)
    for b, (ix, iy) in zip(chosen, burst_positions[:count]):
        b.x = float(max(4, min(env.tank_w - 4, ix)))
        b.y = float(max(4, min(env.tank_h - 4, iy)))
        b.vy = -(28.0 + random.uniform(0, 14))   # faster than normal
        b.layer = 1                                # front layer — most visible
        b.sprite_idx = random.randint(0, 2)

# ---------------------------------------------------------------------------

def update_environment(env: Environment, dt: float, cfg: dict,
                       fish_count: int = 0,
                       algae_eater_count: int = 0) -> None:
    # ---- Bubbles (6 fixed objects) ----
    for b in env.bubbles:
        b.sway += dt * b.sway_spd
        b.y += b.vy * dt                       # vy is negative → rises
        b.x += math.sin(b.sway) * 0.9
        b.x = max(4.0, min(float(env.tank_w - 4), b.x))
        if b.y < 4.0:
            _reset_bubble(b, env.tank_w, env.tank_h)

    # ---- Food (fixed slots) ----
    for food in env.food:
        if not food.active:
            continue
        if food.eaten:
            food.active = False
            food.eaten = False
            food.grounded = False
            food.ground_timer = 0.0
            continue
        if food.grounded:
            # Rotting on floor: accumulate timer and slow algae bleed
            food.ground_timer += dt
            if food.ground_timer >= 30.0:
                # Uneaten food rots → boosts algae and deactivates
                env.algae = min(100.0, env.algae + 0.6)
                food.active = False
                food.grounded = False
                food.ground_timer = 0.0
        else:
            food.y += food.vy * dt
            food.x += food.vx * dt
            food.x = max(0.0, min(float(env.tank_w), food.x))
            food.vx = food.vx * 0.97 + (random.random() - 0.5) * 0.25
            # Hit tank floor → settle instead of disappearing
            if food.y >= env.tank_h - 6:
                food.y = float(env.tank_h - 6)
                food.vy = 0.0
                food.vx = 0.0
                food.grounded = True

    # ---- Algae growth (FishPOC.lua formula) ----
    rate = max(0.0, float(cfg.get("algae_rate", 0.30)))
    max_fish = max(1, int(cfg.get("max_fish", 14)))
    density = fish_count / max_fish
    # Each algae eater suppresses background growth ~18 %; capped at 75 % total
    growth_suppression = min(0.75, algae_eater_count * 0.18)
    effective_rate = rate * (1.0 - growth_suppression)
    # Real-time algae growth: ~13 days to 100% at default rate=0.30, density=0
    env.algae = min(100.0, env.algae + dt * (0.0003 * effective_rate + density * 0.002 * effective_rate))

    # ---- Day/night cycle (20-minute full cycle at time_scale=1.0) ----
    # day_time advances the in-game clock.  night_factor is overridden each
    # render frame by the wall-clock path in aquarium.py, so only day_time
    # needs updating here.
    if cfg.get("night_cycle", True):
        period = 20.0 * 60.0 / max(0.1, float(cfg.get("time_scale", 1.0)))
        env.day_time = (env.day_time + dt / period) % 1.0
    else:
        env.day_time = 0.0
        env.night_factor = 0.0
