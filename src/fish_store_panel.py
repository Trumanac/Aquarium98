"""
fish_store_panel.py — Win98-style Fish Shoppe panel.

Layout
------
The panel shows:
  • 4 fish-bowl slots (species, price, Buy button)
  • Restock row — auto countdown + manual Restock button
  • ─── Sell Your Fish ─── scrollable list

Prices scale by difficulty:
  Easy   (1) × 1.00
  Normal (2) × 1.25
  Hard   (3) × 1.60

Rarity base buy prices:
  Common     :  10-30 coins
  Uncommon   :  40-90 coins
  Rare       : 200-350 coins  (~5% per slot)
  Super-rare : 600-900 coins  (~1% per slot)

Manual restock cost:
  Easy 25 / Normal 40 / Hard 65 / Brutal 90 / Nightmare 120

Auto-restock: every 300 s (5 minutes)
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional

import pygame

from .simulation.species import common_species, uncommon_species, rare_species, super_rare_species
from .coin_system import fish_sell_price

# ---------------------------------------------------------------------------
# Win98 palette (mirrors renderer.py)
# ---------------------------------------------------------------------------
WIN_GRAY  = (192, 192, 192)
WIN_LIGHT = (255, 255, 255)
WIN_DARK  = (64, 64, 64)
WIN_MID   = (128, 128, 128)
TITLE_A   = (0, 0, 128)
TITLE_B   = (16, 132, 208)

PAD_L = 48
PAD_T = 24
PAD_B = 22

# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------
_TB_H  = 18       # title-bar height
_PAD   = 8        # inner content padding
_SLOT_W = 112     # width of each fish-bowl column  (4 cols × 112 = 448 inside 468 pw)
_BOWL_D = 64      # diameter of the fish bowl ellipse
_ROW_H  = 26      # sell-list row height
_RESTOCK_H = 28   # restock row height

_SELL_SORT_MODES  = ["recent", "rarity", "species", "name", "age"]
_SELL_SORT_LABELS = {"recent": "↓ Newest", "rarity": "★ Rarity",
                     "species": "Species", "name": "Name A-Z", "age": "Age ↓"}

_BUYBACK_MAX = 5   # max fish held in the buy-back tab (FIFO, oldest falls off)

# Difficulty price multipliers
_PRICE_MULT  = {1: 1.0, 2: 1.25, 3: 1.60, 4: 2.10, 5: 2.70}
_RESTOCK_COST = {1: 25, 2: 40, 3: 65, 4: 90, 5: 120}

RESTOCK_INTERVAL = 300.0   # seconds between auto-restocks

NUM_SLOTS = 4


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@dataclass
class StoreSlot:
    species: dict
    price: int
    bought: bool = False


# ---------------------------------------------------------------------------
# Helper: draw a Win98-style bevel
# ---------------------------------------------------------------------------
def _bevel(surf: pygame.Surface, r: pygame.Rect, pressed: bool = False) -> None:
    tl = WIN_DARK  if pressed else WIN_LIGHT
    br = WIN_LIGHT if pressed else WIN_DARK
    pygame.draw.line(surf, tl, r.topleft,     (r.right - 1, r.top))
    pygame.draw.line(surf, tl, r.topleft,     (r.left, r.bottom - 1))
    pygame.draw.line(surf, br, (r.right - 1, r.top),    (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, br, (r.left, r.bottom - 1),  (r.right - 1, r.bottom - 1))


def _btn(surf: pygame.Surface, r: pygame.Rect, label: str,
         font: pygame.font.Font, pressed: bool = False,
         enabled: bool = True) -> None:
    """Draw a Win98 push-button."""
    bg = (160, 160, 160) if pressed else WIN_GRAY
    pygame.draw.rect(surf, bg, r)
    _bevel(surf, r, pressed)
    col = WIN_MID if not enabled else (WIN_DARK if pressed else (0, 0, 0))
    txt = font.render(label, True, col)
    ox = 1 if pressed else 0
    surf.blit(txt, (r.centerx - txt.get_width() // 2 + ox,
                    r.centery - txt.get_height() // 2 + ox))


# ---------------------------------------------------------------------------
# Fish-bowl renderer
# ---------------------------------------------------------------------------
_BOWL_WATER_SURF: dict[int, pygame.Surface] = {}  # diam -> cached water ellipse

def _get_bowl_water(diam: int) -> pygame.Surface:
    """Return a cached semi-transparent water ellipse surface for the given diameter."""
    if diam not in _BOWL_WATER_SURF:
        s = pygame.Surface((diam, diam), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (18, 52, 148, 175), s.get_rect())
        _BOWL_WATER_SURF[diam] = s
    return _BOWL_WATER_SURF[diam]

def _draw_bowl(surf: pygame.Surface, cx: int, cy: int, diam: int,
               fish_surf: pygame.Surface | None) -> None:
    """Draw a round fish bowl centred at (cx, cy).

    Bowl interior: water-tinted ellipse, fish sprite inside.
    Bowl rim: thick dark ellipse outline.
    Glass highlight: thin white arc top-left.
    Stand: small brown pedestal.
    """
    r = diam // 2

    # Water interior (semi-transparent blue-green) — blit cached surface
    surf.blit(_get_bowl_water(diam), (cx - r, cy - r))

    # Fish sprite centred and slightly lowered inside bowl
    if fish_surf is not None:
        fw, fh = fish_surf.get_size()
        fx = diam // 2 - fw // 2
        fy = diam // 2 - fh // 2 + 6
        fy = max(2, min(diam - fh - 2, fy))
        surf.blit(fish_surf, (cx - r + fx, cy - r + fy))

    # Rim
    pygame.draw.ellipse(surf, (90, 70, 45), (cx - r, cy - r, diam, diam), 3)
    # Inner rim highlight
    pygame.draw.ellipse(surf, WIN_MID, (cx - r + 1, cy - r + 1, diam - 2, diam - 2), 1)

    # Glass highlight (arc, top-left quadrant)
    try:
        pygame.draw.arc(surf, (200, 220, 255, 200),
                        (cx - r + 5, cy - r + 3, diam - 10, diam // 2),
                        math.pi * 0.25, math.pi * 0.75, 2)
    except Exception:
        pass

    # Stand base
    pygame.draw.rect(surf, (110, 90, 60),  (cx - 9,  cy + r,      18, 5))
    pygame.draw.rect(surf, (90,  72, 48),  (cx - 13, cy + r + 5,  26, 4))


# ---------------------------------------------------------------------------
# Main panel class
# ---------------------------------------------------------------------------
class FishStorePanel:
    """Win98-style fish shoppe — buy and sell fish."""

    def __init__(self, font: pygame.font.Font):
        self.font    = font
        self.visible = False
        self.slots: list[StoreSlot] = []
        self._restock_timer = 0.0      # seconds since last restock (counts up)
        self._scroll = 0               # sell-list scroll offset (rows)
        self._sell_sort_mode: str = "recent"   # sell list sort mode
        self._sell_sort_btn = pygame.Rect(0, 0, 0, 0)
        # Buy-back tab
        self._active_tab: str = "sell"            # "sell" | "buyback"
        self._buyback: list[dict] = []             # [{"fish": Fish, "price": int}, ...]
        self._scroll_bb: int = 0                   # buy-back list scroll offset
        self._tab_rects: list[tuple[pygame.Rect, str]] = []
        self._buyback_rows: list[tuple[pygame.Rect, dict]] = []

        # Rects populated in draw() for hit-testing
        self._panel_rect  = pygame.Rect(0, 0, 0, 0)
        self._close_rect  = pygame.Rect(0, 0, 0, 0)
        self._buy_rects:  list[pygame.Rect] = []
        self._restock_btn = pygame.Rect(0, 0, 0, 0)
        self._sell_rows:  list[tuple[pygame.Rect, object]] = []   # (rect, fish)
        self._sell_thumb_cache: dict[int, pygame.Surface | None] = {}   # id(fish) → thumbnail
        self._sell_row_areas: list[tuple[pygame.Rect, object]] = []     # (full-row rect, fish)
        self._scroll_up   = pygame.Rect(0, 0, 0, 0)
        self._scroll_dn   = pygame.Rect(0, 0, 0, 0)
        self._slot_previews: list[pygame.Surface | None] = []   # cached per-slot fish previews
        self.tip_regions: list[tuple[pygame.Rect, str]] = []    # for tooltips
        # Title-bar gradient cache
        self._title_surf: pygame.Surface | None = None
        self._title_surf_w: int = 0

    # ------------------------------------------------------------------ #
    def open(self, cfg: dict, screen_size: tuple[int, int]) -> None:
        self.visible = True
        if not self.slots:
            self._restock_slots(cfg)

    def close(self) -> None:
        self.visible = False

    def toggle(self, cfg: dict, screen_size: tuple[int, int]) -> None:
        if self.visible:
            self.close()
        else:
            self.open(cfg, screen_size)

    # ------------------------------------------------------------------ #
    def update(self, dt: float, cfg: dict) -> bool:
        """Advance restock timer (call every frame regardless of visibility).
        Returns True if an auto-restock occurred this frame."""
        self._restock_timer += dt
        if self._restock_timer >= RESTOCK_INTERVAL:
            self._restock_slots(cfg)
            return True
        return False

    # ------------------------------------------------------------------ #
    def _restock_slots(self, cfg: dict) -> None:
        diff = int(cfg.get("difficulty", 2))
        mult = _PRICE_MULT.get(diff, 1.25)
        _common   = common_species()
        _uncommon = uncommon_species()
        _rare     = rare_species()
        _epic     = super_rare_species()
        self.slots = []
        for _ in range(NUM_SLOTS):
            r = random.random()
            if r < 0.01 and _epic:          # ~1 %  — super-rare / epic
                sp   = random.choice(_epic)
                base = random.randint(600, 900)
            elif r < 0.06 and _rare:        # ~5 %  — rare
                sp   = random.choice(_rare)
                base = random.randint(200, 350)
            elif r < 0.22 and _uncommon:    # ~16 % — uncommon
                sp   = random.choice(_uncommon)
                base = random.randint(40, 90)
            else:                           # ~78 % — common
                sp   = random.choice(_common)
                base = random.randint(10, 30)
            price = max(1, round(base * mult))
            self.slots.append(StoreSlot(species=sp, price=price))
        self._restock_timer = 0.0
        self._slot_previews = []   # invalidate preview cache on restock

    def mark_slot_bought(self, slot_idx: int) -> None:
        """Mark the slot at *slot_idx* as sold."""
        if 0 <= slot_idx < len(self.slots):
            self.slots[slot_idx].bought = True

    # ------------------------------------------------------------------ #
    def record_sale(self, fish, price: int) -> None:
        """Add a just-sold fish to the buy-back queue (most-recent first, capped at _BUYBACK_MAX)."""
        self._buyback = [e for e in self._buyback if e["fish"] is not fish]
        self._buyback.insert(0, {"fish": fish, "price": price})
        if len(self._buyback) > _BUYBACK_MAX:
            self._buyback = self._buyback[:_BUYBACK_MAX]
        self._scroll_bb = 0  # always show newest entry at top

    def remove_buyback(self, fish) -> None:
        """Remove *fish* from the buy-back queue (called after a successful buy-back)."""
        self._buyback = [e for e in self._buyback if e["fish"] is not fish]

    def clear_buyback(self) -> None:
        """Discard all buy-back entries (called on tank reset)."""
        self._buyback = []
        self._scroll_bb = 0

    # ------------------------------------------------------------------ #
    def _sorted_sell_fish(self, fish_list: list) -> list:
        """Return sell list sorted by current sort mode."""
        mode = self._sell_sort_mode
        if mode == "rarity":
            def _rk(f):
                if f.sp.get("super_rare"): return 0
                if f.sp.get("rare"):       return 1
                if f.sp.get("uncommon"):   return 2
                return 3
            return sorted(fish_list, key=_rk)
        if mode == "species":
            return sorted(fish_list, key=lambda f: f.sp.get("name", ""))
        if mode == "name":
            return sorted(fish_list, key=lambda f: getattr(f, "name", ""))
        if mode == "age":
            return sorted(fish_list, key=lambda f: -getattr(f, "age", 0.0))
        # "recent": newest first
        return list(reversed(fish_list))

    # ------------------------------------------------------------------ #
    def _panel_geom(self, screen_w: int, screen_h: int) -> pygame.Rect:
        pw = min(468, screen_w - PAD_L - 4)
        ph = min(460, screen_h - PAD_T - PAD_B - 4)
        px = PAD_L + 2
        py = PAD_T + 2
        return pygame.Rect(px, py, pw, ph)

    # ------------------------------------------------------------------ #
    def handle_event(self, ev: pygame.Event, cfg: dict,
                     fish_list: list) -> tuple | None:
        """Return one of:
          ("buy",     species, price) — purchase a slot
          ("sell",    fish)           — sell a fish
          ("restock", cost)           — manual restock
          None                        — nothing happened / panel closed
        """
        if not self.visible:
            return None

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            mx, my = ev.pos

            # Close button
            if self._close_rect.inflate(8, 8).collidepoint(mx, my):
                self.close()
                return ("consume",)

            if not self._panel_rect.collidepoint(mx, my):
                self.close()
                return None

            # Buy buttons
            for i, r in enumerate(self._buy_rects):
                if r.collidepoint(mx, my) and i < len(self.slots):
                    slot = self.slots[i]
                    if not slot.bought:
                        return ("buy", i, slot.species, slot.price)

            # Restock button
            if self._restock_btn.collidepoint(mx, my):
                cost = _RESTOCK_COST.get(int(cfg.get("difficulty", 2)), 15)
                return ("restock", cost)

            # Tab strip
            for tab_r, tab_key in self._tab_rects:
                if tab_r.collidepoint(mx, my):
                    if self._active_tab != tab_key:
                        self._active_tab = tab_key
                    return ("consume",)

            # Buy-back rows (only when buy-back tab is active)
            if self._active_tab == "buyback":
                for rect, entry in self._buyback_rows:
                    if rect.collidepoint(mx, my):
                        return ("buyback", entry["fish"], entry["price"])

            # Sell rows (only when sell tab is active)
            if self._active_tab == "sell":
                for rect, fish in self._sell_rows:
                    if rect.collidepoint(mx, my):
                        return ("sell", fish)

                # Row area click (outside sell button) -> view fish profile
                for row_r, fish in self._sell_row_areas:
                    if row_r.collidepoint(mx, my):
                        return ("profile", fish)

                # Sell sort button
                if self._sell_sort_btn.collidepoint(mx, my):
                    idx = _SELL_SORT_MODES.index(self._sell_sort_mode)
                    self._sell_sort_mode = _SELL_SORT_MODES[(idx + 1) % len(_SELL_SORT_MODES)]
                    self._scroll = 0
                    return ("consume",)

            # Scroll arrows (shared between both tabs)
            if self._scroll_up.collidepoint(mx, my):
                if self._active_tab == "buyback":
                    self._scroll_bb = max(0, self._scroll_bb - 1)
                else:
                    self._scroll = max(0, self._scroll - 1)
                return ("consume",)
            if self._scroll_dn.collidepoint(mx, my):
                if self._active_tab == "buyback":
                    max_scroll = max(0, len(self._buyback) - self._visible_sell_rows())
                    self._scroll_bb = min(max_scroll, self._scroll_bb + 1)
                else:
                    max_scroll = max(0, len(fish_list) - self._visible_sell_rows())
                    self._scroll = min(max_scroll, self._scroll + 1)
                return ("consume",)

            # Absorb all unhandled clicks that land inside the panel so they
            # don't fall through to fish or bubbles rendered behind it.
            return ("consume",)

        if ev.type == pygame.MOUSEWHEEL:
            if self._panel_rect.collidepoint(pygame.mouse.get_pos()):
                if self._active_tab == "buyback":
                    self._scroll_bb = max(0, self._scroll_bb - ev.y)
                    max_scroll = max(0, len(self._buyback) - self._visible_sell_rows())
                    self._scroll_bb = min(max_scroll, self._scroll_bb)
                else:
                    self._scroll = max(0, self._scroll - ev.y)
                    max_scroll = max(0, len(fish_list) - self._visible_sell_rows())
                    self._scroll = min(max_scroll, self._scroll)
                return ("consume",)

        return None

    def _visible_sell_rows(self) -> int:
        return getattr(self, "_sell_rows_capacity", 3)

    # ------------------------------------------------------------------ #
    def draw(self, surface: pygame.Surface, cfg: dict, tr: pygame.Rect,
             fish_sheets: dict, fish_list: list,
             btn_icons: dict | None = None) -> None:
        if not self.visible:
            return

        p = self._panel_geom(*surface.get_size())
        self._panel_rect = p

        # ── Panel background ──────────────────────────────────────
        pygame.draw.rect(surface, WIN_GRAY, p)
        _bevel(surface, p)

        # ── Title bar (gradient cached per width) ────────────────────────
        tb = pygame.Rect(p.left + 2, p.top + 2, p.w - 4, _TB_H)
        if self._title_surf is None or self._title_surf_w != tb.w:
            self._title_surf_w = tb.w
            self._title_surf = pygame.Surface((tb.w, tb.h))
            for i in range(tb.h):
                t = i / max(1, tb.h - 1)
                c = (int(TITLE_A[0] + (TITLE_B[0] - TITLE_A[0]) * t),
                     int(TITLE_A[1] + (TITLE_B[1] - TITLE_A[1]) * t),
                     int(TITLE_A[2] + (TITLE_B[2] - TITLE_A[2]) * t))
                pygame.draw.line(self._title_surf, c, (0, i), (tb.w - 1, i))
        surface.blit(self._title_surf, tb.topleft)

        title_surf = self.font.render("Fish Shoppe", True, WIN_LIGHT)
        surface.blit(title_surf, (tb.left + 4, tb.top + (tb.h - title_surf.get_height()) // 2))

        # Close button (X)
        x_rect = pygame.Rect(tb.right - _TB_H + 1, tb.top + 1, _TB_H - 2, _TB_H - 2)
        self._close_rect = x_rect
        pygame.draw.rect(surface, (180, 80, 80), x_rect)
        _bevel(surface, x_rect)
        xf = self.font.render("x", True, WIN_LIGHT)
        surface.blit(xf, (x_rect.centerx - xf.get_width() // 2,
                           x_rect.centery - xf.get_height() // 2))

        # ── Coin balance + tank fill indicator ───────────────────────────────
        self.tip_regions = []
        coins_str = f"Coins: {int(cfg.get('coins', 0))}"
        cs = self.font.render(coins_str, True, (180, 140, 0))
        surface.blit(cs, (tb.left + 4, tb.bottom + 4))
        _fish_count = len(fish_list)
        _max_fish_c = int(cfg.get("max_fish", 30))
        _fill_str = f"Tank: {_fish_count}/{_max_fish_c}"
        _fill_col = (200, 60, 60) if _fish_count >= _max_fish_c else (60, 140, 60)
        _fs = self.font.render(_fill_str, True, _fill_col)
        surface.blit(_fs, (p.right - _PAD - _fs.get_width(), tb.bottom + 4))

        # ── Fish-bowl slots ──────────────────────────────────────
        # Layout per slot (top to bottom):
        #   species name  (12 px)
        #   rarity tag    (12 px)
        #   bowl (circle) (_BOWL_D px)
        #   stand          (9 px below bowl)
        #   price         (12 px)
        #   Buy button    (22 px)
        #   gap            (8 px)
        # Total slot height (slot_area_h):
        _LABEL_H = 12    # one text line
        _BUY_H   = 22
        _GAP     = 8
        _STAND_H = 9     # bowl stand extends this many px below bowl circle
        slot_area_h = _LABEL_H * 2 + _BOWL_D + _STAND_H + _LABEL_H + _BUY_H + _GAP + 4

        # slot_y: first pixel below title-bar + coin-balance line
        slot_y = p.top + _TB_H + 2 + 18
        content_x = p.left + _PAD

        self._buy_rects = []
        for i, slot in enumerate(self.slots):
            sx = content_x + i * _SLOT_W
            col_cx = sx + _SLOT_W // 2

            # ── Name ─────────────────────────────────────────────
            name = slot.species.get("name", "?")
            name_surf = self.font.render(name[:14], True, (0, 0, 0))
            name_y = slot_y
            surface.blit(name_surf, (col_cx - name_surf.get_width() // 2, name_y))

            # ── Rarity tag ────────────────────────────────────────
            _sp_r = slot.species
            if _sp_r.get("super_rare"):
                tag = "Epic"
                tag_col = (180, 70, 240)    # purple
            elif _sp_r.get("rare"):
                tag = "Rare"
                tag_col = (80, 150, 255)    # blue
            elif _sp_r.get("uncommon"):
                tag = "Uncommon"
                tag_col = (60, 210, 80)     # green
            else:
                tag = "Common"
                tag_col = (120, 120, 120)   # gray
            tag_surf = self.font.render(tag, True, tag_col)
            tag_y = slot_y + _LABEL_H
            surface.blit(tag_surf, (col_cx - tag_surf.get_width() // 2, tag_y))

            # ── Bowl (below name + rarity) ────────────────────────
            bowl_top = slot_y + _LABEL_H * 2
            bowl_cy  = bowl_top + _BOWL_D // 2

            if slot.bought:
                # Greyed-out sold slot
                sold_surf = self.font.render("SOLD", True, WIN_MID)
                surface.blit(sold_surf, (col_cx - sold_surf.get_width() // 2,
                                          bowl_cy - sold_surf.get_height() // 2))
                buy_r = pygame.Rect(sx + 6, bowl_top + _BOWL_D + _STAND_H + _LABEL_H + 6, _SLOT_W - 12, _BUY_H)
                self._buy_rects.append(buy_r)
                _btn(surface, buy_r, "Sold", self.font, enabled=False)
                continue

            # Fish preview sprite — cached on first draw after each restock
            if len(self._slot_previews) != len(self.slots):
                self._slot_previews = [None] * len(self.slots)
            fish_preview = self._slot_previews[i]
            if fish_preview is None:
                _sp = slot.species
                _sh = fish_sheets.get(_sp.get("sheet", "fish_new.png"))
                if _sh is not None:
                    _sw, _sh2 = _sh.get_size()
                    _fw, _fh = _sw // 3, _sh2 // 3
                    if _fw < 1 or _fh < 1:
                        self._slot_previews[i] = None
                    else:
                        _frame0 = _sh.subsurface(pygame.Rect(0, 0, _fw, _fh)).copy()
                        _ph = min(32, _BOWL_D - 14)
                        _pw = max(10, int(_ph * _fw / _fh))
                        fish_preview = pygame.transform.smoothscale(_frame0, (_pw, _ph))
                        self._slot_previews[i] = fish_preview

            _draw_bowl(surface, col_cx, bowl_cy, _BOWL_D, fish_preview)
            # Bowl tooltip — species fun fact or diet
            _sp_tip = slot.species
            _tip_text = _sp_tip.get("diet", "")
            if not _tip_text:
                _facts = _sp_tip.get("fun_facts", [])
                _tip_text = _facts[0] if _facts else ""
            if _tip_text:
                _bowl_tip_r = pygame.Rect(col_cx - _BOWL_D // 2, bowl_top, _BOWL_D, _BOWL_D + _STAND_H)
                self.tip_regions.append((_bowl_tip_r, _tip_text[:100]))
            # ── Price ─────────────────────────────────────────────
            price_str  = f"{slot.price} coins"
            price_surf = self.font.render(price_str, True, (140, 110, 0))
            price_y    = bowl_top + _BOWL_D + _STAND_H + 4
            surface.blit(price_surf, (col_cx - price_surf.get_width() // 2, price_y))

            # ── Buy button ────────────────────────────────────────
            buy_r = pygame.Rect(sx + 6, price_y + _LABEL_H + 2, _SLOT_W - 12, _BUY_H)
            self._buy_rects.append(buy_r)
            tank_full = len(fish_list) >= int(cfg.get("max_fish", 30))
            enough = int(cfg.get("coins", 0)) >= slot.price
            if tank_full:
                _btn(surface, buy_r, "Tank Full", self.font, enabled=False)
            else:
                _btn(surface, buy_r, "Buy", self.font, enabled=enough)

        # ── Restock row ──────────────────────────────────────────
        restock_y = slot_y + slot_area_h + 6
        remaining = max(0.0, RESTOCK_INTERVAL - self._restock_timer)
        if remaining == 0.0:
            auto_str = "Ready to Restock!"
            auto_col = (0, 160, 40)
        else:
            mins = int(remaining) // 60
            secs = int(remaining) % 60
            auto_str = f"Auto-restock in {mins}:{secs:02d}"
            auto_col = WIN_DARK
        auto_surf = self.font.render(auto_str, True, auto_col)
        surface.blit(auto_surf, (p.left + _PAD, restock_y + 6))

        diff = int(cfg.get("difficulty", 2))
        rcost = _RESTOCK_COST.get(diff, 15)
        rbtn_w = max(60, self.font.size(f"Restock ({rcost})")[0] + 10)
        rbtn = pygame.Rect(p.right - _PAD - rbtn_w, restock_y + 2, rbtn_w, 22)
        self._restock_btn = rbtn
        enough_r = int(cfg.get("coins", 0)) >= rcost
        _btn(surface, rbtn, f"Restock ({rcost})", self.font, enabled=enough_r)

        # ── Separator ────────────────────────────────────────────
        sep_y = restock_y + _RESTOCK_H + 4
        pygame.draw.line(surface, WIN_DARK,  (p.left + _PAD, sep_y),
                         (p.right - _PAD, sep_y))
        pygame.draw.line(surface, WIN_LIGHT, (p.left + _PAD, sep_y + 1),
                         (p.right - _PAD, sep_y + 1))
        # ── Tab strip (Sell / Buy Back) ──────────────────────────
        _TAB_H = 18
        tab_y  = sep_y + 3
        _tab_sell_lbl = "Sell"
        _bb_count = len(self._buyback)
        _tab_bb_lbl = f"Buy Back ({_bb_count})" if _bb_count else "Buy Back"
        _tab_sell_w = max(38, self.font.size(_tab_sell_lbl)[0] + 10)
        _tab_bb_w   = max(60, self.font.size(_tab_bb_lbl)[0] + 10)

        self._tab_rects = []
        _tx = p.left + _PAD
        for _t_lbl, _t_key, _t_w in (
            (_tab_sell_lbl, "sell",    _tab_sell_w),
            (_tab_bb_lbl,   "buyback", _tab_bb_w),
        ):
            _tr = pygame.Rect(_tx, tab_y, _t_w, _TAB_H)
            _active = self._active_tab == _t_key
            # Active tab: panel colour, open at bottom; inactive: slightly darker
            pygame.draw.rect(surface, WIN_GRAY if _active else (172, 172, 172), _tr)
            if _active:
                pygame.draw.line(surface, WIN_LIGHT, _tr.topleft,     (_tr.right - 1, _tr.top))
                pygame.draw.line(surface, WIN_LIGHT, _tr.topleft,     (_tr.left, _tr.bottom - 1))
                pygame.draw.line(surface, WIN_DARK,  (_tr.right - 1, _tr.top), (_tr.right - 1, _tr.bottom - 1))
                # No bottom line — merges with content area
            else:
                pygame.draw.rect(surface, WIN_DARK, _tr, 1)
            _tc = (0, 0, 0) if _active else WIN_MID
            _ts = self.font.render(_t_lbl, True, _tc)
            surface.blit(_ts, (_tr.centerx - _ts.get_width() // 2,
                                _tr.centery - _ts.get_height() // 2))
            self._tab_rects.append((_tr, _t_key))
            _tx += _t_w + 2

        # Sort button (sell tab only, right-aligned)
        if self._active_tab == "sell":
            _sort_lbl = _SELL_SORT_LABELS[self._sell_sort_mode]
            _sort_w   = max(58, self.font.size(_sort_lbl)[0] + 10)
            _sort_btn_r = pygame.Rect(p.right - _PAD - 16 - 4 - _sort_w, tab_y, _sort_w, _TAB_H)
            self._sell_sort_btn = _sort_btn_r
            _btn(surface, _sort_btn_r, _sort_lbl, self.font)

        # ── List area (sell or buy-back) ─────────────────────────
        sell_list_y = tab_y + _TAB_H + 2
        avail_h = p.bottom - sell_list_y - 4
        capacity = max(1, avail_h // _ROW_H)
        self._sell_rows_capacity = capacity

        # Shared scroll arrows
        arrow_x = p.right - 16
        self._scroll_up = pygame.Rect(arrow_x, sell_list_y,      14, 14)
        self._scroll_dn = pygame.Rect(arrow_x, sell_list_y + 16, 14, 14)
        up_icon = btn_icons.get('scroll_up') if btn_icons else None
        dn_icon = btn_icons.get('scroll_dn') if btn_icons else None
        if up_icon:
            surface.blit(up_icon, self._scroll_up.topleft)
        else:
            _btn(surface, self._scroll_up, "+", self.font)
        if dn_icon:
            surface.blit(dn_icon, self._scroll_dn.topleft)
        else:
            _btn(surface, self._scroll_dn, "-", self.font)

        # ── Sell tab content ──────────────────────────────────────
        if self._active_tab == "sell":
            self._sell_rows = []
            self._sell_row_areas = []
            if not fish_list:
                no_fish = self.font.render("No fish to sell.", True, WIN_MID)
                surface.blit(no_fish, (p.left + _PAD, sell_list_y + 4))
            else:
                sorted_fish = self._sorted_sell_fish(fish_list)
                max_scroll = max(0, len(sorted_fish) - capacity)
                self._scroll = min(max_scroll, max(0, self._scroll))
                visible = sorted_fish[self._scroll: self._scroll + capacity]
                for ri, fish in enumerate(visible):
                    ry2   = sell_list_y + ri * _ROW_H
                    row_r = pygame.Rect(p.left + _PAD, ry2, p.w - _PAD * 2 - 22, _ROW_H)
                    if ri % 2 == 0:
                        pygame.draw.rect(surface, (182, 182, 190), row_r)
                    # Health stripe (left edge, 3px wide, green -> red)
                    _hpct = max(0.0, min(1.0, fish.health))
                    _hcol = (int(220 * (1.0 - _hpct)), int(200 * _hpct), 30)
                    pygame.draw.rect(surface, _hcol, (row_r.left, row_r.top, 3, row_r.h))
                    # Thumbnail
                    _fid = id(fish)
                    if _fid not in self._sell_thumb_cache:
                        _sp2 = fish.sp
                        _tsh = fish_sheets.get(_sp2.get("sheet", "fish_new.png"))
                        if _tsh is not None:
                            _tsw, _tshh = _tsh.get_size()
                            _tfw, _tfh = _tsw // 3, _tshh // 3
                            if _tfw > 0 and _tfh > 0:
                                _tf0 = _tsh.subsurface(pygame.Rect(0, 0, _tfw, _tfh)).copy()
                                _tph = min(16, _ROW_H - 6)
                                _tpw = max(8, int(_tph * _tfw / _tfh))
                                self._sell_thumb_cache[_fid] = pygame.transform.smoothscale(_tf0, (_tpw, _tph))
                            else:
                                self._sell_thumb_cache[_fid] = None
                        else:
                            self._sell_thumb_cache[_fid] = None
                    thumb = self._sell_thumb_cache.get(_fid)
                    _th_x = row_r.left + 5
                    _th_h = thumb.get_height() if thumb else 16
                    _th_y = row_r.top + (row_r.h - _th_h) // 2
                    if thumb:
                        surface.blit(thumb, (_th_x, _th_y))
                    else:
                        pygame.draw.rect(surface, (30, 60, 120), (_th_x, _th_y, 22, 16))
                    # Rarity dot
                    _sp = fish.sp
                    if _sp.get("super_rare"):   _rdot = (180, 70, 240)
                    elif _sp.get("rare"):        _rdot = (80, 150, 255)
                    elif _sp.get("uncommon"):    _rdot = (60, 210, 80)
                    else:                        _rdot = (160, 160, 160)
                    _dot_x = row_r.left + 5 + 24 + 5
                    pygame.draw.circle(surface, _rdot,   (_dot_x, row_r.centery), 5)
                    pygame.draw.circle(surface, (0, 0, 0), (_dot_x, row_r.centery), 5, 1)
                    _rarity_label = ("Epic" if _sp.get("super_rare") else "Rare" if _sp.get("rare")
                                     else "Uncommon" if _sp.get("uncommon") else "Common")
                    self.tip_regions.append((
                        pygame.Rect(_dot_x - 7, row_r.centery - 7, 14, 14),
                        f"Rarity: {_rarity_label}",
                    ))
                    # Sell button -- wider, shows price
                    price    = fish_sell_price(fish)
                    sell_lbl = f"Sell {price}c"
                    sell_w   = max(56, self.font.size(sell_lbl)[0] + 10)
                    sell_r   = pygame.Rect(row_r.right - sell_w, ry2 + 3, sell_w - 2, _ROW_H - 6)
                    # Age text (right-aligned before sell button)
                    _age_secs = getattr(fish, "age", 0.0)
                    if _age_secs >= 86400:   _age_str = f"{_age_secs / 86400:.1f}d"
                    elif _age_secs >= 3600:  _age_str = f"{_age_secs / 3600:.1f}h"
                    else:                    _age_str = f"{int(_age_secs / 60)}m"
                    age_s = self.font.render(_age_str, True, (80, 80, 140))
                    age_x = sell_r.left - 4 - age_s.get_width()
                    # Name label (truncated)
                    nm    = getattr(fish, "name", "?")
                    sp_nm = fish.sp.get("name", "?")
                    label = f"{nm} ({sp_nm})"
                    _name_x   = _dot_x + 12
                    _max_nm_w = age_x - 4 - _name_x
                    lbl_surf  = self.font.render(label, True, (0, 0, 0))
                    if lbl_surf.get_width() > _max_nm_w and len(label) > 5:
                        while lbl_surf.get_width() > _max_nm_w and len(label) > 5:
                            label    = label[:-1]
                            lbl_surf = self.font.render(label + "..", True, (0, 0, 0))
                    surface.blit(lbl_surf, (_name_x, row_r.top + (row_r.h - lbl_surf.get_height()) // 2))
                    surface.blit(age_s,    (age_x,   row_r.top + (row_r.h - age_s.get_height())   // 2))
                    _btn(surface, sell_r, sell_lbl, self.font)
                    self._sell_rows.append((sell_r, fish))
                    self._sell_row_areas.append((row_r, fish))

        # ── Buy-back tab content ──────────────────────────────────
        else:
            self._sell_rows = []
            self._sell_row_areas = []
            self._buyback_rows = []
            coins = int(cfg.get("coins", 0))
            if not self._buyback:
                msg = self.font.render("No recently sold fish.", True, WIN_MID)
                surface.blit(msg, (p.left + _PAD, sell_list_y + 4))
            else:
                max_scroll = max(0, len(self._buyback) - capacity)
                self._scroll_bb = min(max_scroll, max(0, self._scroll_bb))
                visible = self._buyback[self._scroll_bb: self._scroll_bb + capacity]
                for ri, entry in enumerate(visible):
                    fish  = entry["fish"]
                    price = entry["price"]
                    ry2   = sell_list_y + ri * _ROW_H
                    row_r = pygame.Rect(p.left + _PAD, ry2, p.w - _PAD * 2 - 22, _ROW_H)
                    if ri % 2 == 0:
                        pygame.draw.rect(surface, (182, 190, 182), row_r)
                    _sp = fish.sp
                    if _sp.get("super_rare"):   _rdot = (180, 70, 240)
                    elif _sp.get("rare"):        _rdot = (80, 150, 255)
                    elif _sp.get("uncommon"):    _rdot = (60, 210, 80)
                    else:                        _rdot = (160, 160, 160)
                    pygame.draw.circle(surface, _rdot,   (row_r.left + 8, row_r.centery), 5)
                    pygame.draw.circle(surface, (0, 0, 0),(row_r.left + 8, row_r.centery), 5, 1)
                    nm    = getattr(fish, "name", "?")
                    sp_nm = fish.sp.get("name", "?")
                    label = f"{nm} ({sp_nm})"
                    lbl_surf = self.font.render(label[:24], True, (0, 0, 0))
                    surface.blit(lbl_surf, (row_r.left + 18, row_r.top + (row_r.h - lbl_surf.get_height()) // 2))
                    # Buy-back button + price, right-aligned
                    enough   = coins >= price
                    bb_r     = pygame.Rect(row_r.right - 52, ry2 + 3, 50, _ROW_H - 6)
                    price_s  = self.font.render(f"{price}c", True, (120, 90, 0))
                    price_x  = bb_r.left - 4 - price_s.get_width()
                    surface.blit(price_s, (price_x, row_r.top + (row_r.h - price_s.get_height()) // 2))
                    _btn(surface, bb_r, "Buy Back", self.font, enabled=enough)
                    self._buyback_rows.append((bb_r, entry))

        # ── Panel border clamp line ──────────────────────────────
        pygame.draw.rect(surface, WIN_DARK, p, 1)
