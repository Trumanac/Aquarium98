"""
renderer.py — pygame rendering for Aquarium 98.

Exact Z-order matches the original Rainmeter Tank.ini layer stack (back → front):

  1   Win98 chrome frame (outer bevel + title bar)
  2   TankWater          background_water.png, full interior
  3   WaterSurface       surface ripples, top 28 px, tinted (235,250,255) @ alpha 75
  4   TankSand           background_sand.png, full interior
  5   BottomCaustics     caustic floor, bottom 58 px, tinted (255,248,220) @ alpha 65
  6   TankBg             background_tank.png, full interior
  7   SunRay1/2/3        animated light shafts (oscillate + shimmer + alpha pulse)
  8   L3 fish
  9   L3 bubbles
 10   L3 food  (FoodBk1-3)
10.5  FloorMask          re-blit bottom 42 % of static bg to hide below-decor L3 fish
10.6  BottomCaustics     (drawn after FloorMask so not overwritten)
10.7  SunRay1/2/3        (drawn after FloorMask so bright zone visible over sand)
 11   CoralLeft + CoralRight
 12   L2 fish
 13   L2 bubbles
 14   L2 food  (FoodMd1-3)
 15   Castle             exact 116×94 px at interior (142, tank_h-94)
 16   PlantRight         animated 150×84 px at interior (278, tank_h-90), 9 frames @600ms
 17   L1 food  (FoodFr1-2)
 18   L1 fish
 19   L1 bubbles
 20   GlassOverlay       alpha 88
 21   AlgaeOverlay       alpha = floor(algae_pct * 1.7)  →  0–170
 22   Night overlay      (10,20,60) at alpha = int(night_factor * 200)
 23   Toolbar buttons    FoodBtn / CleanBtn in left chrome margin (9,28) and (9,62)
 24   Title bar text + right-aligned stats

Fish sprite: 3×3 sheet, top 6 frames used.
  draw_w = floor(92 * LAYER_SCALE[layer] * fish.scale + 0.5)
  draw_h = floor(68 * LAYER_SCALE[layer] * fish.scale + 0.5)
  No tinting — sheets are pre-coloured art.
  Health < 0.6 → alpha fade.

Light shaft shimmer sequence: shaftSeq = [1,3,2,3,4,6,5,6,1] (9-step, 6 textures).
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import pygame

from .simulation.fish import LAYER_SCALE, _species_size_scale

ROOT = Path(__file__).resolve().parent.parent


def fish_screen_rect(fish, tr: pygame.Rect) -> pygame.Rect:
    """Return the on-screen bounding rect for *fish* within *tr* (tank_rect)."""
    ls = LAYER_SCALE[fish.layer]
    sp_ss = _species_size_scale(fish.sp)
    eff = fish.scale * sp_ss
    draw_w = max(14, int(150 * ls * eff + 0.5))
    draw_h = max(10, int(110 * ls * eff + 0.5))
    sx = tr.left + int(fish.x) - draw_w // 2
    sy = tr.top  + int(fish.y) - draw_h // 2
    return pygame.Rect(sx, sy, draw_w, draw_h)


def toolbar_button_rect(key: str) -> pygame.Rect:
    """Return the clickable rect for a toolbar button key."""
    try:
        idx = TB_BTN_KEYS.index(key)
    except ValueError:
        raise KeyError(f"Unknown toolbar button: {key}") from None
    return pygame.Rect(TB_BTN_X, TB_BTN_Y_START + idx * TB_BTN_SPACING,
                       TB_BTN_SIZE, TB_BTN_SIZE)


def _bevel_rect_surf(surf: pygame.Surface, r: pygame.Rect,
                     pressed: bool = False) -> None:
    tl = WIN_DARK  if pressed else WIN_LIGHT
    br = WIN_LIGHT if pressed else WIN_DARK
    pygame.draw.line(surf, tl, r.topleft, (r.right - 1, r.top))
    pygame.draw.line(surf, tl, r.topleft, (r.left,      r.bottom - 1))
    pygame.draw.line(surf, br, (r.right - 1, r.top),   (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, br, (r.left,      r.bottom - 1), (r.right - 1, r.bottom - 1))
SPRITES = ROOT / "assets" / "sprites"

# ---------------------------------------------------------------------------
# Win98 palette
# ---------------------------------------------------------------------------
WIN_GRAY  = (192, 192, 192)
WIN_LIGHT = (255, 255, 255)
WIN_DARK  = (64,  64,  64)
WIN_MID   = (128, 128, 128)
TITLE_DARK_A    = (0,   0,   128)
TITLE_LIGHT_A   = (64,  128, 200)
TITLE_DARK_I    = (128, 128, 128)
TITLE_LIGHT_I   = (160, 160, 160)

# ---------------------------------------------------------------------------
# Layout constants (Rainmeter Variables.inc)
# ---------------------------------------------------------------------------
PAD_L = 48    # left chrome (toolbar)
PAD_R = 16    # right chrome
PAD_T = 24    # title bar
PAD_B = 22    # status bar

WATER_SURFACE_H  = 28   # top strip for ripple animation
CAUSTICS_FLOOR_H = 58   # bottom strip for caustics animation

# Toolbar geometry
TB_BTN_X        = 6
TB_BTN_Y_START  = 28
TB_BTN_SIZE     = 36
TB_BTN_SPACING  = 40
TB_BTN_KEYS     = (
    'food', 'clean', 'roster', 'event_log',
    'achievements', 'encyclopedia', 'graveyard', 'store'
)

# Decoration geometry at reference interior (448×274)
_REF_W = 448
_REF_H = 274

CASTLE_IX = 142    # interior X of castle left edge
CASTLE_W  = 116    # at reference resolution
CASTLE_H  = 94     # at reference resolution

PLANT_IX  = 278    # interior X of plant left edge
PLANT_OY  = 90     # plant bottom is 90 px above interior floor
PLANT_W   = 150    # at reference resolution
PLANT_H   = 84     # at reference resolution

# Food draw sizes per layer
_FOOD_SIZE  = {3: 4, 2: 5, 1: 6}
_FOOD_ALPHA = {3: 160, 2: 200, 1: 255}

# ---------------------------------------------------------------------------
# Light shaft parameters (from FishPOC.lua)
# ---------------------------------------------------------------------------
# base_x, amp, spd, phase, alpha_base, alpha_range, draw_w, draw_h, shimmer_interval_s
_SHAFT_PARAMS = [
    (60,  9.0, 0.060, 0.0, 48, 12, 108, 260, 0.600),   # SunRay1
    (176, 7.0, 0.050, 1.7, 38, 10,  96, 254, 0.450),   # SunRay2
    (258, 8.0, 0.055, 3.2, 32,  8, 114, 256, 0.900),   # SunRay3
]
_SHAFT_SEQ = [1, 3, 2, 3, 4, 6, 5, 6, 1]   # 1-based, wraps 9→1


# ---------------------------------------------------------------------------
# Asset loading helpers
# ---------------------------------------------------------------------------

def _load(path: Path) -> pygame.Surface | None:
    try:
        return pygame.image.load(str(path)).convert_alpha()
    except (pygame.error, FileNotFoundError, OSError):
        return None


def _load_opaque(path: Path) -> pygame.Surface | None:
    try:
        return pygame.image.load(str(path)).convert()
    except (pygame.error, FileNotFoundError, OSError):
        return None


def _tint(surf: pygame.Surface, color: tuple[int,int,int], alpha: int) -> pygame.Surface:
    """Return a new surface: colour-multiplied and globally alpha-set."""
    result = surf.copy()
    tint_surf = pygame.Surface(result.get_size())
    tint_surf.fill(color)
    result.blit(tint_surf, (0, 0), special_flags=pygame.BLEND_MULT)
    result.set_alpha(alpha)
    return result


# ---------------------------------------------------------------------------
# SpriteAssets
# ---------------------------------------------------------------------------

# Buttons.png frame layout (y_offset, height) — sheet width is always 384 px
_BTN_FRAME_DEFS = [
    (59,  284),   # 0: food
    (350, 276),   # 1: clean
    (633, 269),   # 2: roster
    (909, 251),   # 3: event_log
    (1166, 251),  # 4: achievements
    (1422, 250),  # 5: encyclopedia
    (1675, 252),  # 6: graveyard
    (1930, 251),  # 7: store
    (2203, 138),  # 8: scroll_up
    (2345, 153),  # 9: scroll_dn
    (2504, 98),   # 10: empty
]
_BTN_NAMES = [
    'food', 'clean', 'roster', 'event_log', 'achievements',
    'encyclopedia', 'graveyard', 'store', 'scroll_up', 'scroll_dn', 'empty',
]

class SpriteAssets:
    def __init__(self):
        BG = SPRITES / "background"
        EF = SPRITES / "effects"
        UI = SPRITES / "ui"
        BU = SPRITES / "bubbles"
        FI = SPRITES / "fish"
        PL = SPRITES / "plant_frames"
        CF = SPRITES / "caustics_floor"
        SR = SPRITES / "surface_ripples"

        # Static backgrounds
        # background_new.jpg is the full composited scene (no alpha issues).
        # The individual PNGs are alpha overlays on top — must use _load (convert_alpha)
        # NOT _load_opaque, or their transparent areas render as solid black.
        self.bg_new    = _load_opaque(BG / "background_new.jpg")   # full base scene
        self.bg_water  = _load(BG / "background_water.png")        # alpha overlay
        self.bg_sand   = _load(BG / "background_sand.png")         # alpha overlay
        self.bg_coral_l = _load(BG / "background_coral_left.png")
        self.bg_coral_r = _load(BG / "background_coral_right.png")
        # 4 selectable tank background overlays (bg_choice 1-4)
        self.bg_tanks: list[pygame.Surface | None] = [
            _load(BG / "background_tank.png"),
            _load(BG / "background_tank2.png"),
            _load(BG / "background_tank3.png"),
            _load(BG / "background_tank4.png"),
        ]

        # Overlays
        self.glass          = _load(EF / "glass_front.png")
        # All 4 algae overlays — one is picked randomly on each clean
        self.algae_overlays: list[pygame.Surface | None] = [
            _load(EF / "algae_overlay.png"),
            _load(EF / "algae_overlay2.png"),
            _load(EF / "algae_overlay3.png"),
            _load(EF / "algae_overlay4.png"),
        ]

        # 5 castle/decor skins (choice 1-5: castle_new, castle_new3, Castle2, Ship, Castle3)
        self.castles: list[pygame.Surface | None] = [
            _load(SPRITES / "decor" / "castle_new.png"),
            _load(SPRITES / "decor" / "castle_new3.png"),
            _load(SPRITES / "decor" / "Castle2.png"),
            _load(SPRITES / "decor" / "Ship.png"),
            _load(SPRITES / "decor" / "Castle3.png"),
        ]

        # Buttons.png — unified icon strip (11 frames, 384 px wide, varying heights)
        # Content pixels always occupy x=42..340 (298 px wide) within each frame;
        # we crop to that region before scaling so icons aren't distorted.
        # Pre-scaled to 36×36 for toolbar use; also kept at 14×14 for panel arrows.
        self.btn_icons: dict[str, pygame.Surface] = {}
        self.btn_icons_sm: dict[str, pygame.Surface] = {}   # 14×14 for panel arrows
        _btn_sheet = _load(UI / "Buttons.png")
        if _btn_sheet is not None:
            _BTN_CROP_X, _BTN_CROP_W = 42, 298   # content bounds measured from sheet
            for (_fy, _fh), _name in zip(_BTN_FRAME_DEFS, _BTN_NAMES):
                _frame = _btn_sheet.subsurface(pygame.Rect(_BTN_CROP_X, _fy, _BTN_CROP_W, _fh)).copy()
                self.btn_icons[_name]    = pygame.transform.smoothscale(_frame, (36, 36))
                self.btn_icons_sm[_name] = pygame.transform.smoothscale(_frame, (14, 14))

        # Bubbles (3 sprite variants)
        self.bubbles = [
            _load(BU / "bubble_new.png"),
            _load(BU / "bubble_new2.png"),
            _load(BU / "bubble_new3.png"),
        ]

        # Food flake
        # Food flake spritesheet (3×3 grid of 9 different flakes)
        # Pre-scaled at each layer size so no per-frame scaling cost.
        self.food_flakes: dict[int, list[pygame.Surface]] = {}  # layer → [9 surfaces]
        food_sheet = _load(SPRITES / "Fish_Food.png")
        if food_sheet is not None:
            sw, sh = food_sheet.get_size()
            fw, fh = sw // 3, sh // 3
            raw_flakes = [
                food_sheet.subsurface(pygame.Rect((i % 3) * fw, (i // 3) * fh, fw, fh)).copy()
                for i in range(9)
            ]
            for layer, size in _FOOD_SIZE.items():
                self.food_flakes[layer] = [
                    pygame.transform.smoothscale(f, (size, size)) for f in raw_flakes
                ]
        else:
            # Fallback: empty — draw loop will use plain circles
            self.food_flakes = {}

        # Light shafts (6 textures; used via shimmer sequence)
        self.light_shafts: list[pygame.Surface | None] = [None] * 6
        for i in range(6):
            self.light_shafts[i] = _load(EF / f"light_shaft{i+1}.png")

        # Animated plants — 3 styles, 9 frames each
        self.plant_frames:  list[pygame.Surface] = []
        self.plant2_frames: list[pygame.Surface] = []
        self.plant3_frames: list[pygame.Surface] = []
        for i in range(1, 10):
            s = _load(PL / f"plant_frame_{i:03d}.png")
            if s is not None:
                self.plant_frames.append(s)
        for i in range(1, 10):
            s = _load(PL / f"plant2_frame_{i:03d}.png")
            if s is not None:
                self.plant2_frames.append(s)
        for i in range(1, 10):
            s = _load(PL / f"plant3_frame_{i:03d}.png")
            if s is not None:
                self.plant3_frames.append(s)

        # Animated caustic floor (16 BMP frames)
        self.caustics: list[pygame.Surface] = []
        for i in range(1, 17):
            s = _load_opaque(CF / f"CausticsRender_{i:03d}.bmp")
            if s is not None:
                self.caustics.append(s)

        # Animated surface ripples (16 BMP frames)
        self.surface_ripples: list[pygame.Surface] = []
        for i in range(1, 17):
            s = _load_opaque(SR / f"CausticsRender_{i:03d}.bmp")
            if s is not None:
                self.surface_ripples.append(s)

        # Fish spritesheets — load every known sheet so new species work automatically
        self.fish_sheets: dict[str, pygame.Surface] = {}
        for n in (
            # Generic multi-species sheets (still used by rare species)
            "fish_new.png", "fish2_new.png", "fish3_new.png",
            "fish4_new.png", "fish5_new.png", "fish6_new.png",
            # Dedicated species sheets
            "Angel_Fish.png",    "Betta_Fish.png",   "Butterfly_Fish.png",
            "Cardinal_Fish.png", "Cat_Fish.png",     "Clown_Fish.png",
            "Damsel_Fish.png",   "Emperor_Fish.png", "Goldie_Fish.png",
            "Guppy_Fish.png",    "Lion_Fish.png",    "Neon_Fish.png",
            "Puffer_Fish.png",   "RegalTang_Fish.png", "Tetra_Fish.png",
            "Wrasse_Fish.png",   "YellowTang_Fish.png",
            # Dedicated non-fish creature sheets
            "DragonGoby_Fish.png",
            "Hermit_Crab.png", "Hermit_Crab_Rare.png",
            # New species sheets
            "AlgaeEater_Fish.png",
            "Danio_Fish.png",
            "Rasbora_Fish.png",    "Rasbora_Fish_Rare.png",
            "KuhliLoach_Fish.png",
            "HoneyGourami_Fish.png",
            "Amano_Shrimp.png",
            "DwarfMexican_Frog.png",
            "AfricanDwarf_Frog.png",
        ):
            s = _load(FI / n)
            if s is not None:
                self.fish_sheets[n] = s

        # Treasure chest spritesheet (3×3 grid = 9 frames)
        self.chest_sheet: pygame.Surface | None = _load(
            SPRITES / "decor" / "TreasureChest.png")
        # GoldCoin.png (assets/sprites/ui/) is a wide spritesheet — draw the icon programmatically instead


# ---------------------------------------------------------------------------
# Fish sprite cache
# ---------------------------------------------------------------------------

class FishSpriteCache:
    """Extracts + scales per-fish frame surfaces from a spritesheet.

    Spritesheet is 3 cols × 3 rows; we use the top 6 frames (rows 0-1).
    draw_w = floor(92 * LAYER_SCALE[layer] * fish.scale + 0.5)
    draw_h = floor(68 * LAYER_SCALE[layer] * fish.scale + 0.5)
    No colour tinting — sheets are pre-coloured art.
    health < 0.6 → alpha fade applied at blit time (not cached).
    """

    @staticmethod
    def build(sheet: pygame.Surface, layer: int, scale: float, full_3_rows: bool = False) -> list[pygame.Surface]:
        sw, sh = sheet.get_size()
        fw = sw // 3
        fh = sh // 3
        ls = LAYER_SCALE[layer]
        draw_w = max(14, int(150 * ls * scale + 0.5))   # large, Rainmeter-matched
        draw_h = max(10, int(110 * ls * scale + 0.5))

        right_frames: list[pygame.Surface] = []
        frame_count = 9 if full_3_rows else 6
        for i in range(frame_count):
            col = i % 3
            row = i // 3
            sub = sheet.subsurface(pygame.Rect(col * fw, row * fh, fw, fh)).copy()
            scaled = pygame.transform.smoothscale(sub, (draw_w, draw_h))
            right_frames.append(scaled)
        left_frames = [pygame.transform.flip(s, True, False) for s in right_frames]
        return right_frames + left_frames   # indices 0-5 = right, 6-11 = left

    @staticmethod
    def _get_alpha_bbox(surf: pygame.Surface) -> pygame.Rect:
        """Return the tight bounding rect of non-transparent (alpha>10) pixels."""
        mask = pygame.mask.from_surface(surf, threshold=10)
        rects = mask.get_bounding_rects()
        if rects:
            return rects[0].unionall(rects).clip(surf.get_rect())
        return surf.get_rect()

    @staticmethod
    def build_algae_eater(sheet: pygame.Surface, layer: int, scale: float) -> list[pygame.Surface]:
        """Algae-eater 3×3 sheet — custom mapping because the layout differs from
        every other species sheet.

        Row 0-1 : 6 swimming frames (landscape side-view, ~421×282 px each).
        Row 2   : 3 glass-attached frames (portrait front-view, fish ~220×265 px).

        Swimming frames are normalised so inter-frame position differences
        (different amounts of transparent top/bottom padding per cell) don't
        cause the fish to jump vertically between frames.  Each frame's content
        bbox is centred in a shared canvas sized to the maximum content extent
        across all 6 frames, then the canvas is scaled to draw_w × draw_h.

        Glass frames preserve their portrait aspect ratio to avoid squashing.

        Returns 18 surfaces:
          [0-5]   swimming right-facing
          [6-11]  swimming left-facing
          [12-14] glass-attached (front-on — not direction-dependent)
          [15-17] glass-attached mirrored (unused but keeps index maths simple)
        """
        sw, sh = sheet.get_size()
        fw, fh = sw // 3, sh // 3
        ls = LAYER_SCALE[layer]
        draw_w = max(14, int(150 * ls * scale + 0.5))
        draw_h = max(10, int(110 * ls * scale + 0.5))

        # Extract all 9 raw cells (row-major order)
        cells: list[pygame.Surface] = []
        for row in range(3):
            for col in range(3):
                cells.append(
                    sheet.subsurface(pygame.Rect(col * fw, row * fh, fw, fh)).copy()
                )

        # ── Swimming frames (cells 0-5) ─────────────────────────────────────
        # 1. Find the alpha bbox for each of the 6 swim frames.
        # 2. Build a shared canvas sized to the MAXIMUM content dimensions.
        # 3. Centre each frame's fish art in the shared canvas.
        # Result: all frames rendered with the fish at the same visual position
        # regardless of how much transparent padding the original cell had.
        swim_bboxes = [FishSpriteCache._get_alpha_bbox(cells[i]) for i in range(6)]
        canvas_w = max(b.w for b in swim_bboxes)
        canvas_h = max(b.h for b in swim_bboxes)

        swim_frames: list[pygame.Surface] = []
        for i, bb in enumerate(swim_bboxes):
            canvas = pygame.Surface((canvas_w, canvas_h), pygame.SRCALPHA)
            ox = (canvas_w - bb.w) // 2
            oy = (canvas_h - bb.h) // 2
            canvas.blit(cells[i].subsurface(bb), (ox, oy))
            swim_frames.append(pygame.transform.smoothscale(canvas, (draw_w, draw_h)))

        # ── Glass frames (cells 6-8, row 2) ─────────────────────────────────
        # These are portrait orientation (~220 wide × 265 tall) — very different
        # from the landscape swim frames.  Compute output size from the actual
        # glass content aspect ratio so the fish is not squashed or cut off.
        glass_bboxes = [FishSpriteCache._get_alpha_bbox(cells[6 + j]) for j in range(3)]
        g_cw = max(b.w for b in glass_bboxes)
        g_ch = max(b.h for b in glass_bboxes)
        g_draw_h = draw_h
        g_draw_w = max(14, int(g_draw_h * g_cw / max(1, g_ch) + 0.5))

        glass_frames: list[pygame.Surface] = []
        for j, bb in enumerate(glass_bboxes):
            canvas = pygame.Surface((g_cw, g_ch), pygame.SRCALPHA)
            ox = (g_cw - bb.w) // 2
            oy = (g_ch - bb.h) // 2
            canvas.blit(cells[6 + j].subsurface(bb), (ox, oy))
            glass_frames.append(pygame.transform.smoothscale(canvas, (g_draw_w, g_draw_h)))

        swim_left  = [pygame.transform.flip(s, True, False) for s in swim_frames]
        glass_flip = [pygame.transform.flip(s, True, False) for s in glass_frames]
        return swim_frames + swim_left + glass_frames + glass_flip

    @staticmethod
    def build_hermit(sheet: pygame.Surface, layer: int, scale: float) -> list[pygame.Surface]:
        """Hermit-crab sheet: 3 cols × 3 rows = 9 unique frames.

        Frame layout (by sprite index 0-8):
          0-2  Row 0: tucked in shell → peeking out
          3-5  Row 1: continuing emergence → fully out
          6-8  Row 2: crawling cycle

        Returns 18 surfaces: indices 0-8 = right-facing, 9-17 = left-facing.
        Crawling frames (6-8) are flipped for left-facing; shell/emerge frames
        (0-5) are the same orientation either way.
        """
        sw, sh = sheet.get_size()
        fw = sw // 3
        fh = sh // 3
        ls = LAYER_SCALE[layer]
        draw_w = max(14, int(120 * ls * scale + 0.5))
        draw_h = max(10, int(90  * ls * scale + 0.5))

        right_frames: list[pygame.Surface] = []
        for row in range(3):
            for col in range(3):
                sub = sheet.subsurface(pygame.Rect(col * fw, row * fh, fw, fh)).copy()
                right_frames.append(pygame.transform.smoothscale(sub, (draw_w, draw_h)))
        left_frames = [pygame.transform.flip(s, True, False) for s in right_frames]
        return right_frames + left_frames  # indices 0-8 right, 9-17 left


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

# Mood indicator colours — module-level constant to avoid dict allocation per fish per frame
_MOOD_COLOURS: dict[str, tuple[int, int, int]] = {
    "happy":    (30,  200,  60),
    "content":  (220, 200,  40),
    "stressed": (220,  60,  60),
    "hungry":   (220, 160,  20),
}

class Renderer:
    def __init__(self, surface: pygame.Surface, font: pygame.font.Font):
        self.surface = surface
        self.font = font
        self.assets = SpriteAssets()

        # Static background cache (water + sand + tank_bg; rebuild on resize only)
        self._static_bg: pygame.Surface | None = None
        self._static_bg_size: tuple[int, int] = (0, 0)

        # Scaled decoration cache (rebuild on resize)
        self._decor_size: tuple[int, int] = (0, 0)
        self._coral_l_scaled: pygame.Surface | None = None
        self._coral_r_scaled: pygame.Surface | None = None
        self._castle_scaled:  pygame.Surface | None = None
        # Castle exact screen position (recalculated on resize)
        self._castle_pos: tuple[int, int] = (0, 0)
        # Per-size animation/overlay caches (populated by _rebuild_decor)
        self._surface_ripples_scaled: list[pygame.Surface] = []
        self._caustics_scaled:        list[pygame.Surface] = []
        self._plant_frames_scaled:    list[pygame.Surface] = []
        self._glass_scaled:           pygame.Surface | None = None
        self._algae_overlays_scaled:  list[pygame.Surface | None] = []
        self._shaft_textures_scaled:  list[list[pygame.Surface | None]] = []
        self._scan_lines_surf:        pygame.Surface | None = None
        self._night_surf:             pygame.Surface | None = None

        # Animation counters
        self._plant_frame  = 0;  self._plant_accum  = 0.0
        self._caustic_frame = 0; self._caustic_accum = 0.0
        self._surface_frame = 0; self._surface_accum = 0.0

        # Light shaft animation
        self._sim_t = 0.0
        self._shaft_frames  = [1, 2, 3]   # staggered initial frame indices
        self._shaft_accums  = [0.0, 0.0, 0.0]

        # Mode state (set by aquarium.py)
        self.food_mode         = False
        self.clean_mode        = False
        self.roster_mode       = False
        self.store_mode        = False  # Fish Shoppe panel open
        self.event_log_mode    = False
        self.achievements_mode = False
        self.encyclopedia_mode = False
        self.graveyard_mode    = False

        # Bubble sprite cache: (sprite_idx, size) → scaled Surface
        # Avoids smoothscale on every bubble every frame.
        self._bubble_sprite_cache: dict[tuple[int, int], pygame.Surface] = {}
        # Grounded food sprite cache: (layer, flake_idx) → darkened Surface
        # Avoids copy+fill on every grounded flake every frame.
        self._grounded_food_cache: dict[tuple[int, int], pygame.Surface] = {}
        # Pre-tinted animation frames (built in _rebuild_decor, avoids per-frame copy+fill)
        self._surface_ripples_tinted: list[pygame.Surface] = []
        self._caustics_tinted:        list[pygame.Surface] = []
        # Algae overlay: random index 0-3, re-rolled each time tank is cleaned
        self._algae_idx  = random.randint(0, 3)
        # Castle skin: 1-4, synced from cfg each frame
        self.castle_choice       = 1
        self._last_castle_choice = 1
        # Background style: 1-4, synced from cfg each frame
        self.bg_choice       = 1
        self._last_bg_choice = 1
        # Plant style: 1-3, synced from cfg each frame
        self.plant_choice       = 1
        self._last_plant_choice = 1

    def reset_algae_overlay(self) -> None:
        """Pick a new random algae overlay. Call whenever the tank is cleaned."""
        self._algae_idx = random.randint(0, 3)

    # -----------------------------------------------------------------------
    def compute_tank_rect(self) -> pygame.Rect:
        w, h = self.surface.get_size()
        return pygame.Rect(PAD_L, PAD_T, w - PAD_L - PAD_R, h - PAD_T - PAD_B)

    def tick_animations(self, dt: float) -> None:
        self._sim_t += dt

        # Plant: 600 ms per frame
        self._plant_accum += dt
        if self._plant_accum >= 0.6 and self._plant_frames_scaled:
            self._plant_accum = 0.0
            self._plant_frame = (self._plant_frame + 1) % len(self._plant_frames_scaled)

        # Caustics: 300 ms per frame
        self._caustic_accum += dt
        if self._caustic_accum >= 0.3 and self.assets.caustics:
            self._caustic_accum = 0.0
            self._caustic_frame = (self._caustic_frame + 1) % len(self.assets.caustics)

        # Water surface: 300 ms per frame
        self._surface_accum += dt
        if self._surface_accum >= 0.3 and self.assets.surface_ripples:
            self._surface_accum = 0.0
            self._surface_frame = (self._surface_frame + 1) % len(self.assets.surface_ripples)

        # Shaft shimmer advance
        for i, (_, _, _, _, _, _, _, _, interval_s) in enumerate(_SHAFT_PARAMS):
            self._shaft_accums[i] += dt
            if self._shaft_accums[i] >= interval_s:
                self._shaft_accums[i] = 0.0
                self._shaft_frames[i] = (self._shaft_frames[i] % 9) + 1  # 1-based, wraps 9→1

    # -----------------------------------------------------------------------
    # Static background (water + sand + tank_bg)
    # -----------------------------------------------------------------------
    def _rebuild_static_bg(self, tr: pygame.Rect) -> None:
        w, h = tr.w, tr.h
        bg = pygame.Surface((w, h))   # opaque destination surface
        bg.fill((20, 60, 140))        # fallback deep blue

        # --- Base layer: full composited scene (jpg, no alpha) ---
        if self.assets.bg_new:
            bg.blit(pygame.transform.smoothscale(self.assets.bg_new, (w, h)), (0, 0))

        # --- Alpha overlays: transparent PNG layers on top ---
        # Each layer uses per-pixel alpha; blit directly so transparent areas
        # show through to the layer below.  _load() used convert_alpha() so
        # transparency is preserved.
        bg_tank = self.assets.bg_tanks[max(0, min(3, self.bg_choice - 1))]
        for layer in (self.assets.bg_water, self.assets.bg_sand, bg_tank):
            if layer is not None:
                bg.blit(pygame.transform.smoothscale(layer, (w, h)), (0, 0))

        self._static_bg = bg
        self._static_bg_size = (w, h)

    # -----------------------------------------------------------------------
    # Scaled decorations (coral + castle)
    # -----------------------------------------------------------------------
    def _rebuild_decor(self, tr: pygame.Rect) -> None:
        w, h = tr.w, tr.h
        rx = w / _REF_W
        ry = h / _REF_H

        if self.assets.bg_coral_l:
            self._coral_l_scaled = pygame.transform.smoothscale(
                self.assets.bg_coral_l, (w, h))
        if self.assets.bg_coral_r:
            self._coral_r_scaled = pygame.transform.smoothscale(
                self.assets.bg_coral_r, (w, h))

        if self.assets.castles:
            cidx = max(0, min(4, self.castle_choice - 1))
            castle_tex = self.assets.castles[cidx]
            if castle_tex:
                cw = max(8, int(CASTLE_W * rx))
                ch = max(6, int(CASTLE_H * ry))
                self._castle_scaled = pygame.transform.smoothscale(castle_tex, (cw, ch))

        # Castle position: left edge at interior X = 142, bottom at interior floor
        cx = tr.left + max(0, int(CASTLE_IX * rx))
        cy = tr.bottom - max(1, int(CASTLE_H * ry))
        self._castle_pos = (cx, cy)

        # ── Pre-scale animated frames and static overlays to tank size ────────
        sr_h = max(1, int(WATER_SURFACE_H * h / _REF_H))
        self._surface_ripples_scaled = [
            pygame.transform.smoothscale(f, (w, sr_h))
            for f in self.assets.surface_ripples
        ]
        self._surface_ripples_tinted = []
        for _f in self._surface_ripples_scaled:
            _t = _f.copy()
            _t.fill((56, 62, 72), special_flags=pygame.BLEND_MULT)
            self._surface_ripples_tinted.append(_t)

        cf_h = max(1, int(CAUSTICS_FLOOR_H * h / _REF_H))
        self._caustics_scaled = [
            pygame.transform.smoothscale(f, (w, cf_h))
            for f in self.assets.caustics
        ]
        self._caustics_tinted = []
        for _f in self._caustics_scaled:
            _t = _f.copy()
            _t.fill((110, 100, 72), special_flags=pygame.BLEND_MULT)
            self._caustics_tinted.append(_t)

        if self.assets.plant_frames or self.assets.plant2_frames or self.assets.plant3_frames:
            pidx = max(1, min(3, self.plant_choice))
            if pidx == 2:
                raw_plant = self.assets.plant2_frames
            elif pidx == 3:
                raw_plant = self.assets.plant3_frames
            else:
                raw_plant = self.assets.plant_frames
            if raw_plant:
                pw_p = max(8, int(PLANT_W * rx))
                ph_p = max(6, int(PLANT_H * ry))
                self._plant_frames_scaled = [
                    pygame.transform.smoothscale(f, (pw_p, ph_p))
                    for f in raw_plant
                ]
            else:
                self._plant_frames_scaled = []
        else:
            self._plant_frames_scaled = []

        if self.assets.glass:
            _g = pygame.transform.smoothscale(self.assets.glass, (w, h))
            _g.set_alpha(88)
            self._glass_scaled = _g
        else:
            self._glass_scaled = None

        self._algae_overlays_scaled = [
            pygame.transform.smoothscale(ao, (w, h)) if ao is not None else None
            for ao in self.assets.algae_overlays
        ]

        self._shaft_textures_scaled = []
        for _si, (_, _, _, _, _, _, w_orig, h_orig, _) in enumerate(_SHAFT_PARAMS):
            _sw = max(8, int(w_orig * rx))
            _sh = max(20, int(h_orig * ry))
            self._shaft_textures_scaled.append([
                pygame.transform.smoothscale(tex, (_sw, _sh)) if tex is not None else None
                for tex in self.assets.light_shafts
            ])

        # Scan-lines: static pattern blitted once per frame when enabled
        _sl = pygame.Surface((w, h), pygame.SRCALPHA)
        for _y in range(0, h, 3):
            pygame.draw.line(_sl, (0, 0, 0, 24), (0, _y), (w, _y))
        self._scan_lines_surf = _sl

        # Night overlay: reuse surface, only fill() changes each frame
        self._night_surf = pygame.Surface((w, h), pygame.SRCALPHA)

        self._decor_size = (w, h)

    # -----------------------------------------------------------------------
    # Light shafts (animated per-tick)
    # -----------------------------------------------------------------------
    def _draw_shafts(self, tr: pygame.Rect) -> None:
        t = self._sim_t
        rx = tr.w / _REF_W
        ry = tr.h / _REF_H

        for i, (base, amp, spd, ph, a_base, a_range, w_orig, h_orig, _) in enumerate(_SHAFT_PARAMS):
            # Pick shimmer texture
            seq_idx = self._shaft_frames[i] - 1      # 0-based into _SHAFT_SEQ
            tex_num = _SHAFT_SEQ[seq_idx]             # 1-based shaft texture number
            if self._shaft_textures_scaled:
                scaled = self._shaft_textures_scaled[i][tex_num - 1]
                if scaled is None:
                    continue
            else:
                tex = self.assets.light_shafts[tex_num - 1]
                if tex is None:
                    continue
                scaled = pygame.transform.smoothscale(
                    tex, (max(8, int(w_orig * rx)), max(20, int(h_orig * ry))))

            # Horizontal oscillation
            nx = base + math.sin(t * spd * math.tau + ph) * amp
            sx = tr.left + max(0, int(nx * rx))

            # Gentle vertical bob (0–6 px range scaled)
            ny_frac = 0.5 + 0.5 * math.sin(t * spd * math.tau + ph + 0.5)
            sy = tr.top + int(ny_frac * 6 * ry)

            # Alpha pulse
            pulse = 0.5 + 0.5 * math.sin(t * spd * math.tau + ph + 0.8)
            alpha = max(0, min(255, int(a_base + pulse * a_range)))
            scaled.set_alpha(alpha)

            self.surface.blit(scaled, (sx, sy))

    # -----------------------------------------------------------------------
    # Main draw
    # -----------------------------------------------------------------------
    def draw_coin_popups(self, popups: list) -> None:
        """Render floating '+N coins' popups over the tank."""
        for p in popups:
            t = min(1.0, p.age / p.lifetime)
            alpha = max(0, int(255 * (1.0 - t)))
            dy = int(t * 32)                      # float upward 32px
            txt = self.font.render(p.text, True, (255, 215, 0))
            txt.set_alpha(alpha)
            # Thin dark shadow for readability
            shd = self.font.render(p.text, True, (40, 30, 0))
            shd.set_alpha(max(0, int(alpha * 0.6)))
            ox = int(p.x) - txt.get_width() // 2
            oy = int(p.y) - dy
            self.surface.blit(shd, (ox + 1, oy + 1))
            self.surface.blit(txt, (ox, oy))

    def draw(self, fish_list: list, env, *,
             paused: bool, locked: bool, active: bool,
             show_names: bool, scan_lines: bool,
             show_moods: bool = False,
             encyclopedia_seen: int = 0,
             stats: dict, sprite_cache: dict,
             status_msg: str = "",
             chest=None,
             coin_popups: list | None = None) -> None:

        tr = self.compute_tank_rect()
        s  = self.surface

        # Invalidate decor cache when castle choice changes
        if self.castle_choice != self._last_castle_choice:
            self._last_castle_choice = self.castle_choice
            self._decor_size = (0, 0)
        # Invalidate decor cache when plant choice changes
        if self.plant_choice != self._last_plant_choice:
            self._last_plant_choice = self.plant_choice
            self._plant_frame = 0
            self._decor_size = (0, 0)
        # Invalidate static bg cache when background choice changes
        if self.bg_choice != self._last_bg_choice:
            self._last_bg_choice = self.bg_choice
            self._static_bg = None

        # Rebuild static/decor caches on resize
        if self._static_bg is None or self._static_bg_size != (tr.w, tr.h):
            self._rebuild_static_bg(tr)
        if self._decor_size != (tr.w, tr.h):
            self._rebuild_decor(tr)

        # ---- Win98 chrome fill ----
        s.fill(WIN_GRAY)
        self._draw_title_bar(active, stats.get("fish", 0), int(env.algae),
                             stats.get("coins", 0))
        self._draw_tank_bevel(tr)

        # ---- Z-2: TankWater + TankSand + TankBg (static composite) ----
        s.blit(self._static_bg, tr.topleft)

        # ---- Z-3: WaterSurface (additive shimmer, top strip) ----
        if self._surface_ripples_tinted:
            s.blit(self._surface_ripples_tinted[self._surface_frame],
                   tr.topleft, special_flags=pygame.BLEND_ADD)

        # ---- Z-8 … Z-19: All tank entities, clipped to interior ----
        s.set_clip(tr)

        # ---- Z-8/9/10: Back-layer entities (layer 3) ----
        back  = [f for f in fish_list if f.layer == 3 and not f.is_grazing]
        mid   = [f for f in fish_list if f.layer == 2 and not f.is_grazing]
        front = [f for f in fish_list if f.layer == 1 and not f.is_grazing]

        for f in back:
            self._draw_fish(f, tr, show_names, show_moods)
        self._draw_bubbles_layer(env.bubbles, 3, tr)
        self._draw_food_layer(env.food, 3, tr)

        # ---- Z-10.5: Floor-line mask (hides back-layer fish below decor base) ----
        # Re-blit the bottom 42% of the static background so layer-3 fish that
        # drifted near the rock/sand transition zone are covered before the coral
        # overlay restores the rock textures on top.
        if self._static_bg is not None:
            _fm_h = max(1, int(tr.h * 0.42))
            s.blit(self._static_bg, (tr.left, tr.bottom - _fm_h),
                   pygame.Rect(0, tr.h - _fm_h, tr.w, _fm_h))

        # ---- Z-10.6: BottomCaustics (additive shimmer, bottom strip) ----
        # Drawn AFTER the floor-line mask so the re-blit doesn't erase them;
        # drawn BEFORE coral so caustics appear as floor-level light on sand.
        if self._caustics_tinted:
            cf_h = self._caustics_tinted[0].get_height()
            s.blit(self._caustics_tinted[self._caustic_frame],
                   (tr.left, tr.bottom - cf_h), special_flags=pygame.BLEND_ADD)

        # ---- Z-10.7: SunRays (animated oscillating light shafts) ----
        # Drawn AFTER the floor-line mask so their bright zone (lower half of
        # each shaft texture) is visible over the sand rather than painted over;
        # drawn BEFORE coral so coral appears in front of the light beams.
        self._draw_shafts(tr)

        # ---- Z-11: Coral overlays ----
        if self._coral_l_scaled:
            s.blit(self._coral_l_scaled, tr.topleft)
        if self._coral_r_scaled:
            s.blit(self._coral_r_scaled, tr.topleft)

        # ---- Z-12/13/14: Mid-layer entities (layer 2) ----
        for f in mid:
            self._draw_fish(f, tr, show_names, show_moods)
        self._draw_bubbles_layer(env.bubbles, 2, tr)
        self._draw_food_layer(env.food, 2, tr)

        # ---- Z-15: Castle ----
        if self._castle_scaled:
            s.blit(self._castle_scaled, self._castle_pos)

        # ---- Z-15.5: Treasure Chest (between castle and plant) ----
        if chest is not None:
            chest.draw(s, tr, self.assets.chest_sheet)

        # ---- Z-16: PlantRight (animated, rooted in sand) ----
        if self._plant_frames_scaled:
            plant_s = self._plant_frames_scaled[self._plant_frame % len(self._plant_frames_scaled)]
            _prx = tr.w / _REF_W
            _pry = tr.h / _REF_H
            _ph  = plant_s.get_height()
            px = tr.left + int(PLANT_IX * _prx)
            py = tr.bottom - _ph - int(6 * _pry)   # bottom of plant ≈ sand floor
            s.blit(plant_s, (px, py))

        # ---- Z-17/18/19: Front-layer entities (layer 1) ----
        self._draw_food_layer(env.food, 1, tr)
        for f in front:
            self._draw_fish(f, tr, show_names, show_moods)
        self._draw_bubbles_layer(env.bubbles, 1, tr)

        # ---- Z-19.5: Grazing algae seekers ----
        # Drawn after castle, plants and all fish layers so they always appear
        # pressed against the front glass, never hidden behind decorations.
        for f in fish_list:
            if f.is_grazing:
                self._draw_fish(f, tr, show_names, show_moods)

        s.set_clip(None)   # ---- end tank clip ----

        # ---- Z-20: Glass overlay (alpha 88) ----
        if self._glass_scaled:
            s.blit(self._glass_scaled, tr.topleft)

        # ---- Z-21: Algae overlay (alpha = floor(algae * 1.7)) ----
        algae_alpha = int(env.algae * 1.7)  # 0–170
        if algae_alpha > 0:
            overlays = self.assets.algae_overlays
            _ao_i = self._algae_idx % len(overlays) if overlays else 0
            ao = (self._algae_overlays_scaled[_ao_i]
                  if self._algae_overlays_scaled else None)
            if ao is None and overlays:
                ao_tex = overlays[_ao_i]
                ao = pygame.transform.smoothscale(ao_tex, tr.size) if ao_tex else None
            if ao is not None:
                ao.set_alpha(algae_alpha)
                s.blit(ao, tr.topleft)
            else:
                _ao_fb = pygame.Surface(tr.size, pygame.SRCALPHA)
                _ao_fb.fill((60, 140, 60, algae_alpha))
                s.blit(_ao_fb, tr.topleft)

        # ---- Z-22: Night overlay ----
        night_alpha = int(env.night_factor * 200)
        if night_alpha > 2:
            if self._night_surf is not None:
                self._night_surf.fill((10, 20, 60, night_alpha))
                s.blit(self._night_surf, tr.topleft)
            else:
                _ns = pygame.Surface(tr.size, pygame.SRCALPHA)
                _ns.fill((10, 20, 60, night_alpha))
                s.blit(_ns, tr.topleft)

        # ---- Scan lines (retro effect, optional) ----
        if scan_lines:
            if self._scan_lines_surf is not None:
                s.blit(self._scan_lines_surf, tr.topleft)
            else:
                _sl = pygame.Surface(tr.size, pygame.SRCALPHA)
                for y in range(0, tr.h, 3):
                    pygame.draw.line(_sl, (0, 0, 0, 24), (0, y), (tr.w, y))
                s.blit(_sl, tr.topleft)

        # ---- Z-23: Toolbar buttons ----
        self._draw_toolbar(encyclopedia_seen)

        # ---- Z-24: Status bar ----
        self._draw_status_bar(paused, locked, stats, status_msg)

        # ---- Resize grab handle ----
        if not locked:
            self._draw_grab_handle()

        # ---- Coin popups (on top of everything) ----
        if coin_popups:
            self.draw_coin_popups(coin_popups)

    # -----------------------------------------------------------------------
    # Per-layer entity draws
    # -----------------------------------------------------------------------
    def _draw_bubbles_layer(self, bubbles: list, layer: int,
                            tr: pygame.Rect) -> None:
        for b in bubbles:
            if b.layer != layer:
                continue
            ls = LAYER_SCALE[b.layer]
            size = max(6, int(b.base_size * ls * 1.5))   # 1.5× upscale
            bx = tr.left + int(b.x)
            by = tr.top + int(b.y)
            sprite = self.assets.bubbles[b.sprite_idx % 3]
            if sprite is not None:
                cache_key = (b.sprite_idx % 3, size)
                scaled = self._bubble_sprite_cache.get(cache_key)
                if scaled is None:
                    scaled = pygame.transform.smoothscale(sprite, (size, size))
                    self._bubble_sprite_cache[cache_key] = scaled
                self.surface.blit(scaled, (bx - size // 2, by - size // 2))
            else:
                pygame.draw.circle(self.surface, (200, 230, 255), (bx, by), size // 2, 1)

    def _draw_food_layer(self, food_pool: list, layer: int,
                         tr: pygame.Rect) -> None:
        size  = _FOOD_SIZE[layer]
        alpha = _FOOD_ALPHA[layer]
        layer_flakes = self.assets.food_flakes.get(layer)
        for fd in food_pool:
            if not fd.active or getattr(fd, 'eaten', False) or fd.layer != layer:
                continue
            fx = tr.left + int(fd.x)
            fy = tr.top  + int(fd.y)
            if layer_flakes:
                raw_spr = layer_flakes[fd.flake_idx % 9]
                # Grounded food: darkened/faded tinted copy — built once per (layer, idx)
                if getattr(fd, "grounded", False):
                    gk = (layer, fd.flake_idx % 9)
                    spr = self._grounded_food_cache.get(gk)
                    if spr is None:
                        spr = raw_spr.copy()
                        spr.fill((80, 50, 0, 0), special_flags=pygame.BLEND_RGBA_SUB)
                        spr.set_alpha(max(60, alpha - 60))
                        self._grounded_food_cache[gk] = spr
                else:
                    # Non-grounded: set alpha directly on the cached surface (same
                    # alpha value every time per layer — no pixel data changed).
                    raw_spr.set_alpha(alpha)
                    spr = raw_spr
                self.surface.blit(spr, (fx - size // 2, fy - size // 2))
            else:
                col = (140, 100, 40) if getattr(fd, "grounded", False) else (220, 180, 80)
                pygame.draw.circle(self.surface, col, (fx, fy), max(1, size // 2))

    # -----------------------------------------------------------------------
    # Fish rendering
    # -----------------------------------------------------------------------
    def _draw_fish(self, f, tr: pygame.Rect, show_names: bool, show_moods: bool = False) -> None:
        sheet_name = f.sp.get("sheet", "fish_new.png")
        sheet = self.assets.fish_sheets.get(sheet_name)
        if sheet is None:
            return

        cache_key = (sheet_name, f.layer, int(f.scale * 100))
        is_hermit      = bool(f.sp.get("hermit_crab"))
        is_algae_seeker = bool(f.sp.get("algae_seeker"))
        # Combine biological growth scale with species-size multiplier so that
        # small fish (Neons, Guppies) appear smaller than large ones (Catfish).
        sp_ss     = _species_size_scale(f.sp)
        eff_scale = f.scale * sp_ss
        is_frog = bool(f.sp.get("frog"))
        if f.cached_surfaces is None or f.cache_key != cache_key:
            if is_hermit:
                f.cached_surfaces = FishSpriteCache.build_hermit(sheet, f.layer, eff_scale)
            elif is_algae_seeker:
                f.cached_surfaces = FishSpriteCache.build_algae_eater(sheet, f.layer, eff_scale)
            else:
                f.cached_surfaces = FishSpriteCache.build(sheet, f.layer, eff_scale, full_3_rows=is_frog)
            f.cache_key = cache_key

        if is_hermit:
            # 9 right-facing (0-8) + 9 left-facing (9-17)
            raw_frame = max(0, min(8, f.frame))
            idx = raw_frame + (0 if f.facing >= 0 else 9)
        elif is_algae_seeker and f.is_grazing:
            # Row-2 glass frames: [12-14] right, [15-17] left — cycle through 3
            base = 12 if f.facing > 0 else 15
            idx  = base + (f.frame % 3)
        else:
            # Generic species: use half of cached list for right-facing and mirror for left.
            # This supports both 6-frame species and 9-frame frog sheets.
            right_count = max(1, len(f.cached_surfaces) // 2)
            frame = int(f.frame) % right_count
            idx = frame + (0 if f.facing > 0 else right_count)
        spr = f.cached_surfaces[idx]

        # Rotate side-wall grazers so the fish runs vertically along the glass
        if is_algae_seeker and f.is_grazing and f.graze_angle != 0.0:
            spr = pygame.transform.rotate(spr, f.graze_angle)

        # Health < 0.6: fade toward transparent as the fish declines
        if f.health < 0.6:
            spr.set_alpha(max(30, int(255 * f.health / 0.6)))
        else:
            spr.set_alpha(255)

        sw, sh = spr.get_size()
        sx = tr.left + int(f.x) - sw // 2
        sy = tr.top  + int(f.y) - sh // 2
        self.surface.blit(spr, (sx, sy))

        if show_names:
            label = self.font.render(f.name, True, (180, 220, 255))
            self.surface.blit(label, (sx + sw // 2 - label.get_width() // 2,
                                      sy - label.get_height() - 1))

        if show_moods:
            mood     = getattr(f, "mood", "content")
            mood_col = _MOOD_COLOURS.get(mood, (128, 128, 128))
            if show_names:
                # Sit the dot to the right of the name, vertically centred with it
                name_w = self.font.size(f.name)[0]
                name_h = self.font.get_height()
                dot_x = sx + sw // 2 + name_w // 2 + 7
                dot_y = sy - name_h // 2 - 1
            else:
                dot_x = sx + sw // 2
                dot_y = sy - 6
            pygame.draw.circle(self.surface, mood_col, (dot_x, dot_y), 4)
            pygame.draw.circle(self.surface, (0, 0, 0),   (dot_x, dot_y), 4, 1)

    # -----------------------------------------------------------------------
    # Chrome drawing
    # -----------------------------------------------------------------------
    def _draw_title_bar(self, active: bool, fish_count: int, algae_pct: int,
                        coins: int = 0) -> None:
        w, h = self.surface.get_size()

        # Outer window bevel
        pygame.draw.line(self.surface, WIN_LIGHT, (0, 0), (w - 1, 0))
        pygame.draw.line(self.surface, WIN_LIGHT, (0, 0), (0, h - 1))
        pygame.draw.line(self.surface, WIN_DARK,  (w - 1, 0), (w - 1, h - 1))
        pygame.draw.line(self.surface, WIN_DARK,  (0, h - 1), (w - 1, h - 1))

        # Title bar gradient; ends 4px above PAD_T so separator clears the tank bevel
        tb = pygame.Rect(3, 3, w - 6, PAD_T - 7)
        td = TITLE_DARK_A  if active else TITLE_DARK_I
        tl = TITLE_LIGHT_A if active else TITLE_LIGHT_I
        for i in range(tb.h):
            t = i / max(1, tb.h - 1)
            c = (int(td[0] + (tl[0] - td[0]) * t),
                 int(td[1] + (tl[1] - td[1]) * t),
                 int(td[2] + (tl[2] - td[2]) * t))
            pygame.draw.line(self.surface, c, (tb.left, tb.top + i), (tb.right, tb.top + i))

        # Title separator line at bottom of title gradient
        pygame.draw.line(self.surface, WIN_DARK, (1, tb.bottom), (w - 2, tb.bottom))

        # "Aquarium 98" left-aligned
        title = self.font.render("Aquarium 98", True, (255, 255, 255))
        self.surface.blit(title, (8, tb.top + (tb.h - title.get_height()) // 2))

        # Win98-style close button (top-right, red with white X)
        btn = pygame.Rect(w - 21, 4, 18, 16)
        pygame.draw.rect(self.surface, (200, 40, 40), btn)
        _bevel_rect_surf(self.surface, btn, pressed=False)
        # White X glyph (2 px lines)
        pygame.draw.line(self.surface, (255, 255, 255),
                         (btn.left + 4, btn.top + 3),  (btn.right - 5, btn.bottom - 4), 2)
        pygame.draw.line(self.surface, (255, 255, 255),
                         (btn.right - 5, btn.top + 3), (btn.left + 4,  btn.bottom - 4), 2)

        # Right-aligned stats: "Fish: N   Algae: N%   [coin] N"  (shifted left to clear the X button)
        stats_str  = f"Fish: {fish_count}   Algae: {algae_pct}%"
        # Abbreviate large coin counts to keep the title bar uncluttered
        if coins >= 1_000_000:
            coins_str = f"  {coins / 1_000_000:.1f}M"
        elif coins >= 10_000:
            coins_str = f"  {coins // 1_000}k"
        else:
            coins_str = f"  {coins}"
        stats_surf = self.font.render(stats_str, True, (255, 255, 255))
        coins_surf = self.font.render(coins_str, True, (255, 230, 80))
        stats_surf.set_alpha(220)
        coins_surf.set_alpha(220)
        # Lay out right-to-left starting LEFT of the close button
        coin_count_x = btn.left - 6 - coins_surf.get_width()
        icon_x = coin_count_x - 12
        stats_x = icon_x - 4 - stats_surf.get_width()
        # Prevent stats overlapping "Aquarium 98" title on narrow windows
        stats_x = max(8 + title.get_width() + 8, stats_x)
        ty = tb.top + (tb.h - stats_surf.get_height()) // 2
        self.surface.blit(stats_surf,  (stats_x, ty))
        # Coin icon: small gold circle (drawn, not from sprite)
        pygame.draw.circle(self.surface, (220, 185, 30),
                           (icon_x + 5, tb.centery), 5)
        pygame.draw.circle(self.surface, (180, 140, 0),
                           (icon_x + 5, tb.centery), 5, 1)
        self.surface.blit(coins_surf, (coin_count_x, ty))

    def _draw_tank_bevel(self, tr: pygame.Rect) -> None:
        s = self.surface
        # Outer dark line (Z-4 inset)
        pygame.draw.rect(s, WIN_DARK,  (tr.left - 3, tr.top - 3, tr.w + 6, tr.h + 6), 1)
        # Inner light highlight
        pygame.draw.rect(s, WIN_LIGHT, (tr.left - 2, tr.top - 2, tr.w + 4, tr.h + 4), 1)
        # Innermost dark line
        pygame.draw.rect(s, WIN_DARK,  (tr.left - 1, tr.top - 1, tr.w + 2, tr.h + 2), 1)

    def _draw_tb_btn(self, key: str, x: int, y: int, pressed: bool = False) -> None:
        """Blit a toolbar icon from btn_icons; draw a blue highlight border when pressed."""
        icon = self.assets.btn_icons.get(key)
        if icon:
            self.surface.blit(icon, (x, y))
        else:
            # Fallback: plain raised button
            pygame.draw.rect(self.surface, WIN_GRAY, (x, y, 36, 36))
            _bevel_rect_surf(self.surface, pygame.Rect(x, y, 36, 36), pressed=pressed)
        if pressed:
            pygame.draw.rect(self.surface, (0, 80, 200), (x, y, 36, 36), 2)

    def _draw_toolbar(self, encyclopedia_seen: int = 0) -> None:
        # 36×36 icons, centred in the 48 px left chrome (x=6), spaced by 40 px vertically
        for idx, key in enumerate(TB_BTN_KEYS):
            y = TB_BTN_Y_START + idx * TB_BTN_SPACING
            pressed = getattr(self, f"{key}_mode", False)
            self._draw_tb_btn(key, TB_BTN_X, y, pressed=pressed)

    def _draw_status_bar(self, paused: bool, locked: bool, stats: dict,
                         status_msg: str = "") -> None:
        w, h = self.surface.get_size()
        bar = pygame.Rect(0, h - PAD_B, w, PAD_B)
        pygame.draw.rect(self.surface, WIN_GRAY, bar)
        pygame.draw.line(self.surface, WIN_DARK, (0, bar.top), (w, bar.top))
        pygame.draw.line(self.surface, WIN_LIGHT, (0, bar.top + 1), (w, bar.top + 1))

        if status_msg:
            text = status_msg
        elif paused:
            text = "Paused. Right-click for menu."
        elif self.food_mode:
            text = "Food mode: click inside the tank to drop flakes."
        elif self.clean_mode:
            text = "Cleaning mode: click the tank to scrub algae."
        else:
            fish_n = stats.get("fish", 0)
            algae_pct = stats.get("algae_pct", 0)
            fps = stats.get("fps")
            if fps is not None:
                text = f"{fish_n} fish swimming — {algae_pct}% algae  [{fps:.0f} fps]"
            else:
                text = f"{fish_n} fish swimming — {algae_pct}% algae"

        surf = self.font.render(text, True, (0, 0, 0))
        self.surface.blit(surf, (6, bar.top + (PAD_B - surf.get_height()) // 2))

    def _draw_grab_handle(self) -> None:
        w, h = self.surface.get_size()
        # Diagonal bevel marks the resize corner (dark outer edge, light inner)
        pygame.draw.line(self.surface, WIN_DARK,
                         (w - 20, h - 1), (w - 1, h - 20))
        pygame.draw.line(self.surface, WIN_LIGHT,
                         (w - 19, h - 1), (w - 1, h - 19))
        # Classic Win98 raised-dot grip: triangular staircase of 6 dots
        # Dots at (w-5,h-5), (w-10,h-5)+(w-5,h-10), (w-15,h-5)+(w-10,h-10)+(w-5,h-15)
        S = 5
        for d in range(1, 4):
            for i in range(d):
                gx = w - 5 - (d - i - 1) * S
                gy = h - 5 - i * S
                pygame.draw.rect(self.surface, WIN_LIGHT, (gx - 1, gy - 1, 2, 2))
                pygame.draw.rect(self.surface, WIN_DARK,  (gx,     gy,     2, 2))
