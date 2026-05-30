"""
fish.py — Fish entity with AI state machine and biological lifecycle.

State machine: wander / idle / drift / chase.

Coordinates are in *tank interior* space (0..tank_w, 0..tank_h), not screen.
Renderer converts to screen pixels after applying depth-layer scale.
"""
from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field

from .species import SPECIES, NAMES, RARE_NAMES, common_species, rare_species, super_rare_species, uncommon_species

log = logging.getLogger(__name__)

# Layer config: 1=front (largest, full y-range), 2=mid (behind castle), 3=back (smallest).
LAYER_SCALE     = {1: 1.00, 2: 0.82, 3: 0.66}
LAYER_Y_MAX_FRAC = {1: 0.95, 2: 0.82, 3: 0.58}  # fraction of tank_h fish may reach
LAYER_X_MARGIN   = {1:   66, 2:   56, 3:   48}  # ~half max sprite-width per layer
LAYER_Y_TOP      = {1:   50, 2:   42, 3:   36}  # ~half max sprite-height per layer

# Castle obstacle footprint as fractions of tank interior width.
# Mirrors CASTLE_IX=142, CASTLE_W=116 from renderer.py at _REF_W=448.
_CASTLE_X0_F = 142 / 448   # left edge  ≈ 0.317
_CASTLE_X1_F = 258 / 448   # right edge ≈ 0.576


def _species_size_scale(sp: dict) -> float:
    """Return a sprite draw-size multiplier based on the species' biological size.

    Maps the 'size' key (approximate adult length in cm) to a scale factor so
    that small fish (Neon, Guppy: size 3-4) appear noticeably smaller than
    large ones (Catfish, Algae Eater: size 11-12).

    Reference: size 8 (medium, e.g. Clownfish) → 0.90×.
    Range: 0.50 (tiny) .. 1.35 (large).
    """
    s = sp.get("size", 8)
    return max(0.50, min(1.35, 0.60 + (s - 4) * 0.075))


def pick_random_species() -> dict:
    """Weighted pick: common ~90%, uncommon ~10%.
    Rare and Epic fish are never randomly spawned — they must be purchased
    from the Fish Shoppe or bred from existing rare fish.
    """
    if random.random() < 0.10:
        pool = uncommon_species()
        if pool:
            return random.choice(pool)
    return random.choice(common_species())


@dataclass
class Fish:
    sp: dict
    name: str
    layer: int
    x: float
    y: float
    # Heading-based locomotion
    heading: float
    speed: float
    desired_speed: float
    turn_rate: float
    # Visual orientation: -1 face left, +1 face right
    facing: int = 1
    facing_cd: float = 0.0   # cooldown (s) preventing rapid flip
    # Lifecycle
    age: float = 0.0
    scale: float = 1.0          # 0.35 juvenile → 1.0 adult
    adult: bool = False
    hunger: float = 0.5         # 0 satiated, 1 starving
    health: float = 1.0
    lifespan: float = 1814400.0
    breed_cd: float = 0.0
    # AI state
    state: str = "wander"
    state_time: float = 0.0
    # Animation
    frame: int = 0
    frame_time: float = 0.0
    # Personality (Phase 9): ±15% speed, individual hue offset
    speed_mult: float = 1.0
    hue_offset: tuple[int, int, int] = (0, 0, 0)
    # Layer-transition cooldown
    layer_cd: float = 0.0
    # Render cache invalidation
    cache_key: tuple = ()       # set by renderer
    cached_surfaces: list | None = None
    # Feeding excitement (Phase 9)
    excite: float = 0.0
    # Current chase target (tank-space tuple) — set by update_fish when food spotted
    target: tuple[float, float] | None = None
    # Personality description shown in Fish Profile panel (generated once at creation)
    personality_desc: str = ""
    # Structured personality type: "energetic" | "curious" | "social" | "solitary" | "lazy"
    personality_type: str = "social"
    # Lineage: names of parents if bred, else None
    born_from: tuple[str, str] | None = None
    # Mood: "happy" | "content" | "stressed" | "hungry" (updated each sim step)
    mood: str = "content"
    # Stress accumulator (0-1): rises near others for solitary fish, crowding, dirty water
    stress: float = 0.0
    # Hermit-crab shell cycle (only used when sp.get("hermit_crab"))
    crab_phase: str = "in_shell"  # in_shell | emerging | crawling | retreating
    crab_timer: float = 0.0       # seconds remaining in current phase
    # Frog dive/surface cycle (only used when sp.get("frog"))
    frog_phase: str = "resting"   # resting | burst | surfacing | descending
    frog_timer: float = 0.0       # countdown to next phase transition
    # Whether the player has manually set this fish's name
    custom_name: bool = False
    # True when an algae-seeker is actively feeding on the glass (drives row-2 sprite frames)
    is_grazing: bool = False
    # Which glass surface the algae-seeker is currently grazing on
    graze_wall: str = "bottom"   # "bottom" | "left" | "right"
    # Sprite rotation angle (degrees) for the grazing pose; 0 = horizontal (bottom)
    graze_angle: float = 0.0
    # Cooldown (s) after a graze session ends before the fish will snap to the glass again.
    # Prevents rapid oscillation when algae hovers just above the 2 % stop threshold.
    graze_cd: float = 0.0
    # Seconds of continuous good conditions required before health begins recovering.
    # Resets to ~1 day whenever the fish is hungry or stressed.
    heal_delay: float = 86400.0


def make_fish(tank_w: int, tank_h: int, *,
              species: dict | None = None,
              name: str | None = None,
              layer: int | None = None,
              x: float | None = None,
              y: float | None = None,
              scale: float | None = None,
              existing_names: set[str] | None = None,
              lifespan_base: float = 1814400.0) -> Fish:
    sp = species or pick_random_species()
    if layer is None:
        # All species (including floor dwellers) use layer_pref/random selection
        # so they can be found at different depths and hide behind decorations.
        pref = sp.get("layer_pref", 0)
        if pref and random.random() < 0.70:
            layer = pref
        else:
            layer = random.randint(1, 3)
    ymax = int(tank_h * LAYER_Y_MAX_FRAC[layer])
    if x is None:
        if sp.get("bottom") or sp.get("crawler"):
            # Don't spawn floor fish under the castle
            cxmin = tank_w * _CASTLE_X0_F
            cxmax = tank_w * _CASTLE_X1_F
            for _ in range(12):
                x = random.uniform(20, tank_w - 20)
                if x < cxmin or x > cxmax:
                    break
            else:
                # All attempts landed in the castle zone (extremely unlikely) —
                # place to the left of it as a guaranteed safe fallback.
                x = random.uniform(20, max(21.0, cxmin - 2.0))
        else:
            x = random.uniform(20, tank_w - 20)
    if y is None:
        if sp.get("bottom") or sp.get("crawler"):
            # Approximate floor position — will be corrected each frame by _update_motion
            sp_ss  = _species_size_scale(sp)
            draw_h = max(10, int(110 * LAYER_SCALE[layer] * (scale or 0.70) * sp_ss + 0.5))
            y = float(tank_h) - draw_h // 2 - 3
        else:
            y = random.uniform(15, ymax - 10)
    heading = 0.0 if random.random() < 0.5 else math.pi
    base_speed = float(sp["speed"]) * 0.6
    speed_mult = 0.85 + random.random() * 0.30      # ±15%
    hue = (random.randint(-12, 12), random.randint(-12, 12), random.randint(-12, 12))
    # Pick name: rare fish get from RARE_NAMES pool, others from NAMES.
    # Avoid duplicates by filtering out names already in use.
    if name is None:
        pool = RARE_NAMES if sp.get("rare") else NAMES
        existing = existing_names or set()
        available = [n for n in pool if n not in existing]
        if available:
            name = random.choice(available)
        else:
            # All pool names taken — append a number suffix until unique
            base = random.choice(pool)
            suffix = 2
            while f"{base} {suffix}" in existing:
                suffix += 1
            name = f"{base} {suffix}"
    personality = _gen_personality(sp, speed_mult, layer)
    # Assign structured personality type for behavior wiring.
    # Only truly territorial species (e.g. Betta) become "solitary" — which
    # causes stress near other fish. Non-sociable but non-territorial fish just
    # don't school; they are assigned a calm independent personality instead.
    if speed_mult > 1.10:
        ptype = "energetic"
    elif sp.get("territorial"):
        ptype = "solitary"
    elif not sp.get("sociable", True):
        # Independent fish: won't school, but not stressed by company
        ptype = "lazy" if random.random() < 0.60 else "curious"
    elif random.random() < 0.28:
        ptype = "curious"
    else:
        ptype = "social"
    _f = Fish(
        sp=sp,
        name=name,
        layer=layer,
        x=x, y=y,
        heading=heading,
        speed=base_speed * speed_mult,
        desired_speed=base_speed * speed_mult,
        turn_rate=0.6 if sp.get("crawler") else 2.5,
        facing=1 if math.cos(heading) >= 0 else -1,
        age=0.0,
        scale=scale if scale is not None else (0.45 + random.random() * 0.15),
        adult=(scale is None or scale >= 0.95),
        hunger=0.3 + random.random() * 0.2,
        health=1.0,
        lifespan=lifespan_base * (0.85 + random.random() * 0.30),
        speed_mult=speed_mult,
        hue_offset=hue,
        frame=random.randint(0, 5),
        frame_time=random.random() * 0.2,
        state_time=random.uniform(2.0, 8.0),
        personality_desc=personality,
        personality_type=ptype,
    )
    # Stagger frog initial rest so multiple frogs don't all jump at once
    if sp.get("frog"):
        _f.frog_timer = random.uniform(3.0, 12.0)
    # Stagger hermit crab so it doesn't immediately emerge on first frame
    if sp.get("hermit_crab"):
        _f.crab_timer = random.uniform(8.0, 20.0)
    return _f


def _gen_personality(sp: dict, speed_mult: float, layer: int) -> str:
    """Generate a natural, immersive personality blurb for the fish profile."""

    if speed_mult > 1.12:
        tempo = random.choice([
            "full of restless energy",
            "always on the move",
            "rarely seen sitting still",
        ])
    elif speed_mult < 0.88:
        tempo = random.choice([
            "calm and unhurried",
            "moves at an easy, leisurely pace",
            "takes life at its own slow rhythm",
        ])
    else:
        tempo = random.choice([
            "relaxed and steady",
            "comfortable in its own routine",
            "neither rushed nor restless",
        ])

    if sp.get("sociable"):
        social = random.choice([
            "naturally drawn to the company of others",
            "rarely strays far from its tankmates",
            "seems happiest when part of a group",
        ])
    else:
        social = random.choice([
            "tends to keep to itself",
            "a solitary sort by nature",
            "content to explore the tank alone",
        ])

    if layer == 1:
        habitat = random.choice([
            "often drifts close to the front of the tank",
            "gravitates toward the near side of the tank",
            "tends to patrol the water closest to the glass",
        ])
    elif layer == 3:
        habitat = random.choice([
            "prefers the quieter, shadier back of the tank",
            "keeps close to the background and decorations",
            "most at home in the deeper reaches of the aquarium",
        ])
    else:
        habitat = random.choice([
            "roams comfortably through the middle of the tank",
            "at home in the open water at the heart of the aquarium",
            "favours the open space in the centre of the tank",
        ])

    quirks = [
        "has a fondness for looping around the castle",
        "always seems to return to the same corner",
        "appears to sense feeding time before it arrives",
        "occasionally fixated by its own reflection in the glass",
        "makes a deliberate pause before changing direction",
        "traces slow, lazy loops when undisturbed",
        "noses along the gravel bed from time to time",
        "tucks in near the plants when the light fades",
        "has a habit of shadowing tankmates for no clear reason",
        "will press against the glass as if inspecting visitors",
        "claims a favourite patch of the tank and rarely leaves it",
        "disappears behind the décor for long stretches at a time",
        "darts into cover when startled, then reappears slowly",
        "lingers near the surface for a while after feeding",
        "unusually curious — investigates anything new in the tank",
    ]

    return f"{tempo.capitalize()}, {social}, {habitat}. {random.choice(quirks).capitalize()}."


def _update_hermit_crab(f: Fish, tank_w: int, tank_h: int, dt: float) -> None:
    """Hermit crab shell-cycle state machine.

    Sprite sheet layout (3 cols × 3 rows = 9 frames):
      Row 0 (frames 0-2): tucked in shell → beginning to peek out
      Row 1 (frames 3-5): continuing emergence → fully out
      Row 2 (frames 6-8): crawling cycle
    """
    # Always hug the floor — raised 14 px so sprite feet are not clipped
    f.y = float(tank_h) - 22
    f.heading = 0.0 if f.facing > 0 else math.pi

    if f.crab_phase == "in_shell":
        f.speed = 0.0
        f.desired_speed = 0.0
        # Idle shell animation: slowly breathe between frames 0-1
        f.frame_time += dt
        if f.frame_time >= 1.2:
            f.frame_time = 0.0
            f.frame = 1 if f.frame == 0 else 0
        f.crab_timer -= dt
        if f.crab_timer <= 0:
            f.crab_phase = "emerging"
            f.crab_timer = 0.0
            f.frame = 0

    elif f.crab_phase == "emerging":
        f.speed = 0.0
        f.desired_speed = 0.0
        # Advance through frames 0→5 over ~3 seconds
        f.crab_timer += dt
        f.frame = min(5, int(f.crab_timer / 3.0 * 6))
        if f.crab_timer >= 3.0:
            f.crab_phase = "crawling"
            f.crab_timer = random.uniform(6.0, 14.0)
            f.frame = 6

    elif f.crab_phase == "crawling":
        base = f.sp["speed"] * f.speed_mult * 0.5
        f.desired_speed = base
        f.speed += (f.desired_speed - f.speed) * min(1.0, dt * 1.5)
        f.x += math.cos(f.heading) * f.speed * dt
        f.x = max(8.0, min(tank_w - 8.0, f.x))
        # Crawl animation: loop frames 6-8
        f.frame_time += dt
        if f.frame_time >= 0.22:
            f.frame_time = 0.0
            f.frame = 6 + (f.frame - 6 + 1) % 3
        # Flip direction at walls
        if f.x <= 10.0:
            f.facing = 1
            f.heading = 0.0
        elif f.x >= tank_w - 10.0:
            f.facing = -1
            f.heading = math.pi
        f.crab_timer -= dt
        if f.crab_timer <= 0:
            f.crab_phase = "retreating"
            f.crab_timer = 0.0
            f.frame = 5

    elif f.crab_phase == "retreating":
        f.speed = 0.0
        f.desired_speed = 0.0
        # Reverse through frames 5→0 over ~2.5 seconds
        f.crab_timer += dt
        f.frame = max(0, 5 - int(f.crab_timer / 2.5 * 6))
        if f.crab_timer >= 2.5:
            f.crab_phase = "in_shell"
            f.crab_timer = random.uniform(8.0, 20.0)
            f.frame = 0


def _update_frog(f: Fish, tank_w: int, tank_h: int, dt: float) -> None:
    """African Dwarf Frog state machine.

    resting   — sits on floor, idle animation (frames 0-2)
    burst     — fast horizontal swim along the floor (frames 3-5)
    surfacing — swims straight up to breathe (frames 6-8)
    descending — slowly drifts back to the floor (frames 0-2)
    """
    f.frog_timer -= dt
    margin = LAYER_X_MARGIN.get(f.layer, LAYER_X_MARGIN[1])

    if f.frog_phase == "resting":
        f.y = float(tank_h) - 24
        f.speed = 0.0
        f.desired_speed = 0.0
        # Push out of the castle X zone (frog should not idle in transparent arches)
        _cx0r = _CASTLE_X0_F * tank_w - 10.0
        _cx1r = _CASTLE_X1_F * tank_w + 10.0
        if _cx0r < f.x < _cx1r:
            if f.x - _cx0r <= _cx1r - f.x:
                f.x = _cx0r
            else:
                f.x = _cx1r
        # Idle animation: cycle frames 0-2
        f.frame_time += dt
        if f.frame_time >= 0.9:
            f.frame_time = 0.0
            f.frame = (f.frame % 3 + 1) % 3
        if f.frog_timer <= 0:
            if random.random() < 0.25:
                # Surface to breathe
                f.frog_phase = "surfacing"
                f.frog_timer = 0.0
                f.heading = -math.pi / 2
            else:
                # Burst swim across the bottom
                f.frog_phase = "burst"
                f.frog_timer = random.uniform(2.5, 5.0)
                if f.x < tank_w * 0.5:
                    f.heading = random.uniform(-0.35, 0.35)
                    f.facing = 1
                else:
                    f.heading = math.pi + random.uniform(-0.35, 0.35)
                    f.facing = -1

    elif f.frog_phase == "burst":
        base = f.sp["speed"] * f.speed_mult
        f.desired_speed = base * 1.5
        f.speed += (f.desired_speed - f.speed) * min(1.0, dt * 3.5)
        f.x += math.cos(f.heading) * f.speed * dt
        f.y = float(tank_h) - 24
        f.x = max(float(margin), min(float(tank_w - margin), f.x))
        # Avoid swimming through the castle zone (transparent arches would reveal frog)
        _cx0 = _CASTLE_X0_F * tank_w - 10.0
        _cx1 = _CASTLE_X1_F * tank_w + 10.0
        if _cx0 < f.x < _cx1:
            # Push to nearest castle edge and reverse heading
            if f.x - _cx0 <= _cx1 - f.x:
                f.x = _cx0
                f.facing = -1
                f.heading = math.pi + random.uniform(-0.35, 0.35)
            else:
                f.x = _cx1
                f.facing = 1
                f.heading = random.uniform(-0.35, 0.35)
        if f.x <= float(margin) + 1.0:
            f.facing = 1
            f.heading = random.uniform(-0.35, 0.35)
        elif f.x >= float(tank_w - margin) - 1.0:
            f.facing = -1
            f.heading = math.pi + random.uniform(-0.35, 0.35)
        if math.cos(f.heading) > 0.05:
            f.facing = 1
        elif math.cos(f.heading) < -0.05:
            f.facing = -1
        # Burst animation: frames 3-5
        f.frame_time += dt
        if f.frame_time >= 0.18:
            f.frame_time = 0.0
            f.frame = 3 + (f.frame - 3 + 1) % 3 if 3 <= f.frame <= 5 else 3
        if f.frog_timer <= 0:
            f.frog_phase = "resting"
            f.frog_timer = random.uniform(5.0, 14.0)
            f.frame = 0

    elif f.frog_phase == "surfacing":
        base = f.sp["speed"] * f.speed_mult
        f.desired_speed = base * 1.8
        f.speed += (f.desired_speed - f.speed) * min(1.0, dt * 3.0)
        f.y -= f.speed * dt
        top_y = float(LAYER_Y_TOP[f.layer])
        f.y = max(top_y, f.y)
        # Surface animation: frames 6-8
        f.frame_time += dt
        if f.frame_time >= 0.16:
            f.frame_time = 0.0
            f.frame = 6 + (f.frame - 6 + 1) % 3 if 6 <= f.frame <= 8 else 6
        if f.y <= top_y + 4.0:
            # Reached surface — take a breath
            f.frog_phase = "descending"
            f.frog_timer = random.uniform(0.8, 2.0)
            f.speed = 0.0

    elif f.frog_phase == "descending":
        base = f.sp["speed"] * f.speed_mult
        f.desired_speed = base * 0.6
        f.speed += (f.desired_speed - f.speed) * min(1.0, dt * 2.0)
        f.y += f.speed * dt
        # Gentle idle frames while sinking
        f.frame_time += dt
        if f.frame_time >= 0.25:
            f.frame_time = 0.0
            f.frame = (f.frame % 3 + 1) % 3
        if f.y >= float(tank_h) - 26:
            f.y = float(tank_h) - 24
            f.frog_phase = "resting"
            f.frog_timer = random.uniform(6.0, 15.0)
            f.frame = 0

    f.x = max(float(margin), min(float(tank_w - margin), f.x))


def _pick_state(f: Fish) -> str:
    if f.sp.get("crawler"):
        return "drift"
    r = random.random()
    if r < 0.55:
        return "wander"
    if r < 0.80:
        return "idle"
    return "drift"


def _update_motion(f: Fish, tank_w: int, tank_h: int, dt: float) -> None:
    sp = f.sp
    base = sp["speed"] * f.speed_mult
    crawler = sp.get("crawler", False)
    bottom = sp.get("bottom", False)

    if crawler:
        # Snail/hermit: shuffle along sand floor
        f.desired_speed = base * 0.6
        f.y = tank_h - 8
        f.heading = 0.0 if f.facing > 0 else math.pi
    elif f.state == "wander":
        # Periodic heading nudge
        if random.random() < dt * 1.2:
            f.heading += (random.random() - 0.5) * 0.8
        f.desired_speed = base * (0.55 + random.random() * 0.9)
    elif f.state == "idle":
        f.desired_speed = base * 0.18
        f.heading += (random.random() - 0.5) * 0.15 * dt
    elif f.state == "drift":
        f.desired_speed = base * 0.42
        if random.random() < dt * 0.6:
            f.heading += (random.random() - 0.5) * 0.3
    elif f.state == "chase" and f.target is not None:
        f.desired_speed = base * 2.2 * (1 + 0.5 * f.excite)
        tx, ty = f.target
        ang = math.atan2(ty - f.y, tx - f.x)
        # Steer toward target
        delta = ((ang - f.heading + math.pi) % (2 * math.pi)) - math.pi
        f.heading += max(-f.turn_rate * dt * 2.0,
                         min(f.turn_rate * dt * 2.0, delta))

    # Personality: energetic fish swim 30% faster
    if f.personality_type == "energetic":
        f.desired_speed *= 1.30

    # Castle-lurking species: gently bias heading toward the castle sides when wandering.
    # They bounce off the castle exclusion zone naturally, creating a patrol effect.
    if sp.get("lurk_castle") and f.state in ("wander", "drift") and random.random() < dt * 0.06:
        castle_cx = tank_w * (_CASTLE_X0_F + _CASTLE_X1_F) * 0.5
        # Aim for the nearer castle edge (they'll bounce off the exclusion zone wall)
        if f.x < castle_cx:
            target_x = tank_w * _CASTLE_X0_F - 8.0
        else:
            target_x = tank_w * _CASTLE_X1_F + 8.0
        ang_to = math.atan2(0.0, target_x - f.x)   # purely horizontal
        delta = ((ang_to - f.heading + math.pi) % (2 * math.pi)) - math.pi
        f.heading += delta * 0.40

    # Hunger surface drift: when hungry, add upward velocity bias
    hunger_drift_vy = 0.0
    if not bottom and not crawler and f.hunger > 0.65:
        intensity = (f.hunger - 0.65) / 0.35   # 0..1 as hunger goes 0.65→1.0
        hunger_drift_vy = -base * intensity * 0.55

    # Excitement decay
    if f.excite > 0:
        f.excite = max(0.0, f.excite - dt * 0.5)

    # Smooth speed approach
    f.speed += (f.desired_speed - f.speed) * min(1.0, dt * 2.0)

    # Velocity & position integration (fish swim mostly horizontal)
    vx = math.cos(f.heading) * f.speed
    vy = math.sin(f.heading) * f.speed * 0.30 + hunger_drift_vy
    f.x += vx * dt
    f.y += vy * dt

    # Facing direction: ±6 px/s deadband + cooldown to prevent rapid flips
    f.facing_cd = max(0.0, f.facing_cd - dt)
    if f.facing_cd <= 0.0:
        new_facing = f.facing
        if vx > 6.0:
            new_facing = 1
        elif vx < -6.0:
            new_facing = -1
        if new_facing != f.facing:
            f.facing = new_facing
            f.facing_cd = 0.75   # 5 ticks × 150 ms

    # Wall bounce — reflect heading so fish turn naturally at edges
    margin = LAYER_X_MARGIN.get(f.layer, LAYER_X_MARGIN[1])
    ymax = tank_h * LAYER_Y_MAX_FRAC.get(f.layer, LAYER_Y_MAX_FRAC[1])
    if f.x < margin:
        f.x = margin
        # For bottom/lurk fish use a wider scatter angle so they don't hug the wall
        scatter = 0.6 if (bottom or crawler or sp.get("lurk_castle")) else 0.3
        f.heading = math.pi - f.heading + (random.random() - 0.5) * scatter
        f.facing_cd = 0.0   # allow immediate facing update after bounce
        # Crawlers: heading is overridden from facing at the top of the next
        # frame, so we must update facing NOW or the bounce will be undone.
        if crawler:
            f.facing = 1   # bounced off left wall → face right
    elif f.x > tank_w - margin:
        f.x = tank_w - margin
        scatter = 0.6 if (bottom or crawler or sp.get("lurk_castle")) else 0.3
        f.heading = math.pi - f.heading + (random.random() - 0.5) * scatter
        f.facing_cd = 0.0
        if crawler:
            f.facing = -1  # bounced off right wall → face left
    top_margin = LAYER_Y_TOP[f.layer]
    # Compute accurate sprite half-height from species size + biological scale
    sp_ss  = _species_size_scale(f.sp)
    half_h = max(10, int(110 * LAYER_SCALE[f.layer] * f.scale * sp_ss + 0.5)) // 2
    if bottom or crawler:
        # Bounce floor fish off the castle base so they never slide under it
        cxmin = tank_w * _CASTLE_X0_F
        cxmax = tank_w * _CASTLE_X1_F
        if cxmin <= f.x <= cxmax:
            if f.x - cxmin < cxmax - f.x:
                f.x = cxmin - 1.0
                f.heading = math.pi + (random.random() - 0.5) * 0.3
                f.facing = -1
            else:
                f.x = cxmax + 1.0
                f.heading = (random.random() - 0.5) * 0.3
                f.facing = 1
            f.facing_cd = 0.0
        # Pin centre so the sprite sits on the sand without being clipped
        f.y = float(tank_h) - half_h - 3
    else:
        if f.y < top_margin:
            f.y = top_margin
            f.heading = -f.heading + (random.random() - 0.5) * 0.2
        elif f.y > ymax - half_h:
            f.y = ymax - half_h
            f.heading = -f.heading + (random.random() - 0.5) * 0.2

    # Hard clamp: safety net when the window is resized smaller so that fish
    # are never stuck outside the new tank bounds waiting for a bounce event.
    f.x = max(2.0, min(float(tank_w) - 2.0, f.x))
    if not (bottom or crawler):
        f.y = max(2.0, min(float(tank_h) - 2.0, f.y))


def _apply_schooling(f: Fish, fish_list: list, dt: float) -> None:
    """Steer a sociable fish toward nearby same-species schoolmates.

    Applies gentle alignment (match average heading) and cohesion (drift
    toward group centre).  Only activates when `count >= school_size`.
    Skipped entirely for bottom/crawler fish and while chasing food.
    """
    if f.state == "chase" or f.sp.get("bottom") or f.sp.get("crawler"):
        return
    min_count = f.sp.get("school_size", 1)
    radius_sq = 150.0 * 150.0
    align_x = align_y = cx = cy = 0.0
    count = 0
    for other in fish_list:
        if other is f or other.sp["name"] != f.sp["name"] or other.layer != f.layer:
            continue
        dx = other.x - f.x
        dy = other.y - f.y
        if dx * dx + dy * dy < radius_sq:
            align_x += math.cos(other.heading)
            align_y += math.sin(other.heading)
            cx += other.x
            cy += other.y
            count += 1
    if count < min_count:
        return
    # Alignment: steer toward average heading of schoolmates
    align_ang = math.atan2(align_y, align_x)
    # Cohesion: steer toward centre of the group
    coh_ang = math.atan2(cy / count - f.y, cx / count - f.x)
    align_delta = ((align_ang - f.heading + math.pi) % (2 * math.pi)) - math.pi
    coh_delta   = ((coh_ang   - f.heading + math.pi) % (2 * math.pi)) - math.pi
    total_delta = align_delta * 0.30 + coh_delta * 0.15
    strength = min(1.0, 0.25 + count * 0.20)
    max_turn = f.turn_rate * dt * strength
    f.heading += max(-max_turn, min(max_turn, total_delta))


def _start_grazing(f: Fish, tank_w: int, tank_h: int,
                   fish_list: list | None) -> None:
    """Called when an algae seeker transitions to active grazing.

    Picks an unoccupied wall surface (bottom, left, or right glass), sets
    the fish position/angle for that surface, and forces it to the front
    layer so it renders on top of all decorations.

    The wall nearest to the fish's *current* position is tried first to
    avoid a visible teleport; only a small nudge is applied if another
    grazer is already too close.
    """
    f.layer    = 1
    f.layer_cd = random.uniform(30.0, 60.0)   # stay front after grazing ends

    other_grazers = [g for g in (fish_list or []) if g is not f and g.is_grazing]
    _GAP = 40   # minimum pixel gap between two grazers on the same surface
    mx   = LAYER_X_MARGIN[1] + 24

    # Rank walls by proximity to current fish position (nearest first).
    # This means the transition never picks a distant random wall.
    wall_order = sorted(
        [("bottom", tank_h - f.y),
         ("left",   f.x),
         ("right",  tank_w - f.x)],
        key=lambda w: w[1],
    )

    for wall, _ in wall_order:
        if wall == "bottom":
            occupied = [g.x for g in other_grazers if g.graze_wall == "bottom"]
            # Try current x first (clamped to valid range)
            candidate = max(float(mx), min(float(tank_w - mx), f.x))
            if all(abs(candidate - ox) >= _GAP for ox in occupied):
                f.graze_wall  = "bottom"
                f.graze_angle = 0.0
                f.x = candidate
                return
            # Small nudges around current x if a neighbour is too close
            for _ in range(10):
                gx = candidate + random.uniform(-_GAP * 2, _GAP * 2)
                gx = max(float(mx), min(float(tank_w - mx), gx))
                if all(abs(gx - ox) >= _GAP for ox in occupied):
                    f.graze_wall  = "bottom"
                    f.graze_angle = 0.0
                    f.x = gx
                    return
        elif wall == "left":
            occupied = [g.y for g in other_grazers if g.graze_wall == "left"]
            candidate = max(float(LAYER_Y_TOP[1] + 20), min(float(tank_h * 0.70), f.y))
            if all(abs(candidate - oy) >= _GAP for oy in occupied):
                f.graze_wall  = "left"
                f.graze_angle = -90.0   # CW: belly faces right (into tank)
                f.y = candidate
                return
            for _ in range(10):
                gy = candidate + random.uniform(-_GAP * 2, _GAP * 2)
                gy = max(float(LAYER_Y_TOP[1] + 20), min(float(tank_h * 0.70), gy))
                if all(abs(gy - oy) >= _GAP for oy in occupied):
                    f.graze_wall  = "left"
                    f.graze_angle = -90.0
                    f.y = gy
                    return
        elif wall == "right":
            occupied = [g.y for g in other_grazers if g.graze_wall == "right"]
            candidate = max(float(LAYER_Y_TOP[1] + 20), min(float(tank_h * 0.70), f.y))
            if all(abs(candidate - oy) >= _GAP for oy in occupied):
                f.graze_wall  = "right"
                f.graze_angle = 90.0    # CCW: belly faces left (into tank)
                f.y = candidate
                return
            for _ in range(10):
                gy = candidate + random.uniform(-_GAP * 2, _GAP * 2)
                gy = max(float(LAYER_Y_TOP[1] + 20), min(float(tank_h * 0.70), gy))
                if all(abs(gy - oy) >= _GAP for oy in occupied):
                    f.graze_wall  = "right"
                    f.graze_angle = 90.0
                    f.y = gy
                    return

    # Fallback: bottom at clamped current x — no teleport
    f.graze_wall  = "bottom"
    f.graze_angle = 0.0
    f.x = max(float(mx), min(float(tank_w - mx), f.x))


def update_fish(f: Fish, tank_w: int, tank_h: int, dt: float,
                food_list: list | None = None,
                env: "object | None" = None,
                fish_list: list | None = None) -> None:
    """Advance one fish by dt seconds."""
    # Hermit crabs use a completely separate state machine
    if f.sp.get("hermit_crab"):
        _update_hermit_crab(f, tank_w, tank_h, dt)
        return
    if f.sp.get("frog"):
        _update_frog(f, tank_w, tank_h, dt)
        # Frogs eat food that lands near them on the floor
        if food_list:
            for p in food_list:
                if p.active and not p.eaten:
                    dx = p.x - f.x
                    dy = p.y - f.y
                    if dx * dx + dy * dy < 28 * 28:
                        p.eaten = True
                        f.hunger = max(0.0, f.hunger - 0.45)
        return
    f.state_time -= dt
    if f.state_time <= 0:
        f.state = _pick_state(f)
        f.state_time = random.uniform(2.0, 8.0)

    # Algae eaters: graze proportionally to algae level; hunger penalty when tank is clean
    if f.sp.get("algae_eater") and env is not None:
        # Drain re-graze cooldown regardless of current algae level
        if f.graze_cd > 0:
            f.graze_cd = max(0.0, f.graze_cd - dt)
        algae_lvl = env.algae
        if algae_lvl > 2.0:
            # Graze rate scales with how fouled the tank is
            # At algae=100 %: ~0.0058/s  |  At algae=10 %: ~0.0022/s
            graze_rate = 0.0018 + 0.004 * (algae_lvl / 100.0)
            env.algae = max(0.0, algae_lvl - dt * graze_rate)
            # Actively grazing → slowly suppress hunger
            if algae_lvl > 10.0:
                f.hunger = max(0.0, f.hunger - dt * 0.007)
            if f.sp.get("algae_seeker"):
                # Hysteresis: only START grazing when algae >= 5 % and cooldown
                # has expired; once grazing, continue until algae drops to 2 %.
                can_start = (algae_lvl >= 5.0) and (f.graze_cd <= 0)
                new_grazing = (f.state != "chase") and (f.is_grazing or can_start)
                if new_grazing and not f.is_grazing:
                    # Transition: pick wall, position, force to front layer
                    _start_grazing(f, tank_w, tank_h, fish_list)
                elif f.is_grazing and not new_grazing:
                    # Session interrupted (e.g. spotted food); short cooldown
                    # prevents immediate re-snap to the glass next tick.
                    f.graze_cd = random.uniform(8.0, 20.0)
                f.is_grazing = new_grazing
        else:
            # No algae to eat — hunger rises faster (missing natural food source)
            f.hunger = min(1.0, f.hunger + dt * 0.004)
            if f.sp.get("algae_seeker"):
                if f.is_grazing:
                    # Session ended; impose cooldown before next wall-snap
                    f.graze_cd = random.uniform(20.0, 40.0)
                f.is_grazing = False
        # Eat grounded food nearby (fallback when algae is scarce)
        if food_list:
            for p in food_list:
                if p.active and p.grounded and not p.eaten:
                    dx = p.x - f.x
                    dy = p.y - f.y
                    if dx * dx + dy * dy < 30 * 30:
                        p.eaten = True
                        f.hunger = max(0.0, f.hunger - 0.40)

    # Algae seekers freeze on the glass while actively grazing.
    # Only the 3 glass animation frames cycle (slowly); no motion.
    if f.is_grazing:
        f.layer = 1   # always topmost layer while on the glass
        # Pin to the chosen glass surface each frame so physics can't drift it
        sp_ss  = _species_size_scale(f.sp)
        half_h = max(10, int(110 * LAYER_SCALE[1] * f.scale * sp_ss + 0.5)) // 2
        if f.graze_wall == "bottom":
            f.y = float(tank_h) - half_h - 3
        elif f.graze_wall == "left":
            f.x = float(half_h) + 3        # half_h ≈ half_w for this body shape
        elif f.graze_wall == "right":
            f.x = float(tank_w) - half_h - 3
        f.frame_time += dt
        if f.frame_time >= 0.35:      # ~2.9 fps — subtle tail flick
            f.frame_time -= 0.35
            f.frame = (f.frame + 1) % 3
        if f.layer_cd > 0:
            f.layer_cd = max(0.0, f.layer_cd - dt)
        return

    # Hunt food when hungry; curious fish have 1.5× detection radius
    if food_list and f.hunger > 0.35 and not f.sp.get("crawler"):
        base_range = 220.0
        if f.personality_type == "curious":
            base_range = 330.0
        nearest = None
        ndist = 1e9
        for p in food_list:
            if not p.active or p.eaten:
                continue
            if p.grounded and not f.sp.get("bottom") and not f.sp.get("crawler"):
                continue  # mid/top-water fish ignore grounded food
            dx = p.x - f.x
            dy = p.y - f.y
            # Cross-layer penalty (600 px² per layer step)
            d2 = dx * dx + dy * dy + abs(p.layer - f.layer) * 600
            if d2 < ndist:
                ndist = d2
                nearest = p
        if nearest is not None and ndist < base_range * base_range:
            f.state = "chase"
            f.target = (nearest.x, nearest.y)
            f.excite = min(1.0, f.excite + dt * 1.5)
            if ndist < 22 * 22:
                nearest.eaten = True
                f.hunger = max(0.0, f.hunger - 0.45)
                f.state = "wander"
                f.target = None
                f.state_time = random.uniform(1.5, 4.0)
        else:
            # No reachable food — if we were chasing a now-gone pellet, snap out
            if f.state == "chase":
                f.state = "wander"
                f.target = None
                f.state_time = random.uniform(1.5, 3.0)
    elif f.state == "chase":
        # In chase state but food hunt is inactive (no food list or not hungry)
        f.state = "wander"
        f.target = None
        f.state_time = random.uniform(1.5, 3.0)

    # Non-algae-eater crawlers (e.g. Kuhli Loach) eat nearby grounded food
    if f.sp.get("crawler") and not f.sp.get("algae_eater") and food_list and f.hunger > 0.45:
        for p in food_list:
            if p.active and p.grounded and not p.eaten:
                dx = p.x - f.x
                dy = p.y - f.y
                if dx * dx + dy * dy < 32 * 32:
                    p.eaten = True
                    f.hunger = max(0.0, f.hunger - 0.40)
                    break

    # Schooling: sociable fish with same-species neighbors align + cohere
    if f.sp.get("sociable") and fish_list:
        _apply_schooling(f, fish_list, dt)

    _update_motion(f, tank_w, tank_h, dt)

    # Frame animation (decoupled per-fish so they don't synchronize)
    f.frame_time += dt
    fps = 6 + (f.speed_mult - 1.0) * 6
    interval = 1.0 / max(2.0, fps)
    while f.frame_time >= interval:
        f.frame_time -= interval
        f.frame = (f.frame + 1) % 6

    # Layer cooldown decay
    if f.layer_cd > 0:
        f.layer_cd = max(0.0, f.layer_cd - dt)


def update_biology(f: Fish, dt: float, hunger_rate: float, growth_rate: float,
                   age_rate: float) -> None:
    """Age, grow, hunger, health."""
    f.age += dt * age_rate
    if not f.adult:
        # Growth: juvenile (0.45) → adult (0.95) in ~2 days at growth_rate=0.5
        f.scale = min(1.0, f.scale + dt * 0.00000029 * growth_rate * 20)
        if f.scale >= 0.95:
            f.adult = True

    # Real-time biological rates: hunger critical ~2 days, starvation death ~3 days,
    # old-age death ~7 days past lifespan, recovery ~6 days.
    f.hunger = min(1.0, f.hunger + dt * 0.000012 * hunger_rate)
    if f.hunger > 0.85:
        f.health = max(0.0, f.health - dt * 0.0000040)
    elif f.hunger < 0.3 and f.stress < 0.20 and f.health < 1.0:
        # Healing only begins after ~1 day of sustained good conditions.
        # Any lapse (hunger spike, stress) resets the delay.
        f.heal_delay = max(0.0, f.heal_delay - dt)
        if f.heal_delay <= 0:
            f.health = min(1.0, f.health + dt * 0.0000015)
    else:
        f.heal_delay = 86400.0  # reset — consistent care required to heal

    if f.adult and f.age > f.lifespan:
        f.health = max(0.0, f.health - dt * 0.0000016)

    if f.breed_cd > 0:
        f.breed_cd = max(0.0, f.breed_cd - dt)


def update_mood(f: Fish, dt: float, algae_pct: float,
                tank_fish_count: int, max_fish: int,
                near_fish_count: int) -> None:
    """Recompute f.mood from biological + social conditions."""
    # Stress decay toward calm
    f.stress = max(0.0, f.stress - dt * 0.15)

    # Overcrowding stress
    if tank_fish_count > max_fish * 0.75:
        f.stress = min(1.0, f.stress + dt * 0.08)

    # Dirty water stress
    if algae_pct > 65:
        excess = (algae_pct - 65) / 35.0
        f.stress = min(1.0, f.stress + dt * 0.06 * excess)

    # Solitary fish get stressed near other fish.
    # Exception: lurk_castle species (Dragon Goby, Kuhli Loach etc.) coexist
    # with other bottom-dwellers near the castle by nature — proximity there
    # is expected, not threatening.
    if (f.personality_type == "solitary"
            and not f.sp.get("lurk_castle")
            and near_fish_count > 0):
        f.stress = min(1.0, f.stress + dt * 0.12 * near_fish_count)

    # Derive final mood
    if f.hunger > 0.72:
        f.mood = "hungry"
    elif f.stress > 0.55 or f.health < 0.55:
        f.mood = "stressed"
    elif f.hunger < 0.35 and f.stress < 0.20 and f.health > 0.75:
        f.mood = "happy"
    else:
        f.mood = "content"


# ---------------------------------------------------------------------------
# Serialization helpers (persist_state feature)
# ---------------------------------------------------------------------------

def fish_to_dict(f: Fish) -> dict:
    """Serialize a Fish to a JSON-safe dict for persistent storage."""
    return {
        "species_name":     f.sp.get("name", ""),
        "name":             f.name,
        "layer":            f.layer,
        "x":                f.x,
        "y":                f.y,
        "heading":          f.heading,
        "speed":            f.speed,
        "desired_speed":    f.desired_speed,
        "turn_rate":        f.turn_rate,
        "facing":           f.facing,
        "age":              f.age,
        "scale":            f.scale,
        "adult":            f.adult,
        "hunger":           f.hunger,
        "health":           f.health,
        "lifespan":         f.lifespan,
        "breed_cd":         f.breed_cd,
        "state":            f.state,
        "state_time":       f.state_time,
        "speed_mult":       f.speed_mult,
        "hue_offset":       list(f.hue_offset),
        "personality_desc": f.personality_desc,
        "personality_type": f.personality_type,
        "born_from":        list(f.born_from) if f.born_from else None,
        "mood":             f.mood,
        "stress":           f.stress,
        "custom_name":      f.custom_name,
        "crab_phase":       f.crab_phase,
        "crab_timer":       f.crab_timer,
        "frog_phase":       f.frog_phase,
        "frog_timer":       f.frog_timer,
        "graze_wall":       f.graze_wall,
        "graze_angle":      f.graze_angle,
        "is_grazing":       f.is_grazing,
        "graze_cd":         f.graze_cd,
        "heal_delay":       f.heal_delay,
    }


def fish_from_dict(d: dict, tank_w: int, tank_h: int) -> "Fish | None":
    """Reconstruct a Fish from a saved dict. Returns None if species unknown."""
    sp_name = d.get("species_name", "")
    # Migrate renamed species so existing saves don't lose their fish
    _SPECIES_RENAMES = {
        "Crimson Fanveil": "Royal Fanveil",
        "Algae Eater": "Siamese Algae Eater",
    }
    sp_name = _SPECIES_RENAMES.get(sp_name, sp_name)
    sp = next((s for s in SPECIES if s.get("name") == sp_name), None)
    if sp is None:
        log.warning("fish_from_dict: unknown species %r (fish %r) — skipping",
                    sp_name, d.get("name", "<unnamed>"))
        return None
    f = make_fish(tank_w, tank_h,
                  species=sp,
                  name=d.get("name", ""),
                  layer=int(d.get("layer", sp.get("layer_pref", 0))),
                  x=float(d.get("x", tank_w / 2)),
                  y=float(d.get("y", tank_h / 2)),
                  scale=float(d.get("scale", 1.0)))
    f.heading       = float(d.get("heading", f.heading))
    f.speed         = float(d.get("speed", f.speed))
    f.desired_speed = float(d.get("desired_speed", f.desired_speed))
    f.turn_rate     = float(d.get("turn_rate", f.turn_rate))
    f.facing        = int(d.get("facing", f.facing))
    f.age           = float(d.get("age", 0.0))
    f.adult         = bool(d.get("adult", f.adult))
    f.hunger        = float(d.get("hunger", 0.5))
    f.health        = float(d.get("health", 1.0))
    f.lifespan      = float(d.get("lifespan", f.lifespan))
    f.breed_cd      = float(d.get("breed_cd", 0.0))
    f.state         = str(d.get("state", "wander"))
    f.state_time    = float(d.get("state_time", 0.0))
    f.speed_mult    = float(d.get("speed_mult", 1.0))
    hue             = d.get("hue_offset", [0, 0, 0])
    f.hue_offset    = (int(hue[0]), int(hue[1]), int(hue[2]))
    f.personality_desc = str(d.get("personality_desc", ""))
    f.personality_type = str(d.get("personality_type", "social"))
    # Migration: all non-territorial species that previously gained "solitary" via
    # sociable=False should not stress near other fish.  Only species with
    # territorial=True (currently only Betta) keep the solitary personality type.
    if f.personality_type == "solitary" and not f.sp.get("territorial"):
        f.personality_type = random.choice(["lazy", "lazy", "curious"])
    born            = d.get("born_from")
    f.born_from     = (str(born[0]), str(born[1])) if born else None
    f.mood          = str(d.get("mood", "content"))
    f.stress        = float(d.get("stress", 0.0))
    f.custom_name   = bool(d.get("custom_name", False))
    f.crab_phase    = str(d.get("crab_phase", "in_shell"))
    f.crab_timer    = float(d.get("crab_timer", 0.0))
    f.frog_phase    = str(d.get("frog_phase", "resting"))
    f.frog_timer    = float(d.get("frog_timer", 0.0))
    f.graze_wall    = str(d.get("graze_wall", "bottom"))
    f.graze_angle   = float(d.get("graze_angle", 0.0))
    f.is_grazing    = bool(d.get("is_grazing", False))
    f.graze_cd      = float(d.get("graze_cd", 0.0))
    f.heal_delay    = float(d.get("heal_delay", 86400.0))
    return f
