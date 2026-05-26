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
def _draw_bowl(surf: pygame.Surface, cx: int, cy: int, diam: int,
               fish_surf: pygame.Surface | None) -> None:
    """Draw a round fish bowl centred at (cx, cy).

    Bowl interior: water-tinted ellipse, fish sprite inside.
    Bowl rim: thick dark ellipse outline.
    Glass highlight: thin white arc top-left.
    Stand: small brown pedestal.
    """
    r = diam // 2

    # Water interior (semi-transparent blue-green)
    water = pygame.Surface((diam, diam), pygame.SRCALPHA)
    pygame.draw.ellipse(water, (18, 52, 148, 175), water.get_rect())

    # Fish sprite centred and slightly lowered inside bowl
    if fish_surf is not None:
        fw, fh = fish_surf.get_size()
        fx = diam // 2 - fw // 2
        fy = diam // 2 - fh // 2 + 6
        fy = max(2, min(diam - fh - 2, fy))
        water.blit(fish_surf, (fx, fy))

    surf.blit(water, (cx - r, cy - r))

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

        # Rects populated in draw() for hit-testing
        self._panel_rect  = pygame.Rect(0, 0, 0, 0)
        self._close_rect  = pygame.Rect(0, 0, 0, 0)
        self._buy_rects:  list[pygame.Rect] = []
        self._restock_btn = pygame.Rect(0, 0, 0, 0)
        self._sell_rows:  list[tuple[pygame.Rect, object]] = []   # (rect, fish)
        self._scroll_up   = pygame.Rect(0, 0, 0, 0)
        self._scroll_dn   = pygame.Rect(0, 0, 0, 0)
        self._slot_previews: list[pygame.Surface | None] = []   # cached per-slot fish previews
        self.tip_regions: list[tuple[pygame.Rect, str]] = []    # for tooltips

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
    def update(self, dt: float, cfg: dict) -> None:
        """Advance restock timer (call every frame regardless of visibility)."""
        self._restock_timer += dt
        if self._restock_timer >= RESTOCK_INTERVAL:
            self._restock_slots(cfg)

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

    def mark_slot_bought(self, species: dict) -> None:
        """Mark the slot for *species* as sold."""
        want = species.get("name", "")
        for slot in self.slots:
            if slot.species.get("name", "") == want:
                slot.bought = True
                return

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
                        return ("buy", slot.species, slot.price)

            # Restock button
            if self._restock_btn.collidepoint(mx, my):
                cost = _RESTOCK_COST.get(int(cfg.get("difficulty", 2)), 15)
                return ("restock", cost)

            # Sell rows
            for rect, fish in self._sell_rows:
                if rect.collidepoint(mx, my):
                    return ("sell", fish)

            # Scroll arrows
            if self._scroll_up.collidepoint(mx, my):
                self._scroll = max(0, self._scroll - 1)
                return ("consume",)
            if self._scroll_dn.collidepoint(mx, my):
                max_scroll = max(0, len(fish_list) - self._visible_sell_rows())
                self._scroll = min(max_scroll, self._scroll + 1)
                return ("consume",)

            if self._panel_rect.collidepoint(mx, my):
                return ("consume",)

        if ev.type == pygame.MOUSEWHEEL:
            if self._panel_rect.collidepoint(pygame.mouse.get_pos()):
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

        # ── Title bar ────────────────────────────────────────────
        tb = pygame.Rect(p.left + 2, p.top + 2, p.w - 4, _TB_H)
        for i in range(tb.h):
            t = i / max(1, tb.h - 1)
            c = (int(TITLE_A[0] + (TITLE_B[0] - TITLE_A[0]) * t),
                 int(TITLE_A[1] + (TITLE_B[1] - TITLE_A[1]) * t),
                 int(TITLE_A[2] + (TITLE_B[2] - TITLE_A[2]) * t))
            pygame.draw.line(surface, c, (tb.left, tb.top + i), (tb.right, tb.top + i))

        title_surf = self.font.render("Fish Shoppe", True, WIN_LIGHT)
        surface.blit(title_surf, (tb.left + 4, tb.top + (tb.h - title_surf.get_height()) // 2))

        # Close button (X)
        x_rect = pygame.Rect(tb.right - _TB_H + 1, tb.top + 1, _TB_H - 2, _TB_H - 2)
        self._close_rect = x_rect
        pygame.draw.rect(surface, WIN_GRAY, x_rect)
        _bevel(surface, x_rect)
        xf = self.font.render("X", True, (0, 0, 0))
        surface.blit(xf, (x_rect.centerx - xf.get_width() // 2,
                           x_rect.centery - xf.get_height() // 2))

        # ── Coin balance ─────────────────────────────────────────
        coins_str = f"Coins: {int(cfg.get('coins', 0))}"
        cs = self.font.render(coins_str, True, (180, 140, 0))
        surface.blit(cs, (tb.left + 4, tb.bottom + 4))

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
            tag = "Uncommon" if slot.species.get("uncommon") else "Common"
            tag_col = (120, 60, 180) if slot.species.get("uncommon") else (60, 140, 60)
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
                    _frame0 = _sh.subsurface(pygame.Rect(0, 0, _fw, _fh)).copy()
                    _ph = min(32, _BOWL_D - 14)
                    _pw = max(10, int(_ph * _fw / max(1, _fh)))
                    fish_preview = pygame.transform.smoothscale(_frame0, (_pw, _ph))
                    self._slot_previews[i] = fish_preview

            _draw_bowl(surface, col_cx, bowl_cy, _BOWL_D, fish_preview)

            # ── Price ─────────────────────────────────────────────
            price_str  = f"{slot.price} coins"
            price_surf = self.font.render(price_str, True, (140, 110, 0))
            price_y    = bowl_top + _BOWL_D + _STAND_H + 4
            surface.blit(price_surf, (col_cx - price_surf.get_width() // 2, price_y))

            # ── Buy button ────────────────────────────────────────
            buy_r = pygame.Rect(sx + 6, price_y + _LABEL_H + 2, _SLOT_W - 12, _BUY_H)
            self._buy_rects.append(buy_r)
            enough = int(cfg.get("coins", 0)) >= slot.price
            _btn(surface, buy_r, "Buy", self.font, enabled=enough)

        # ── Restock row ──────────────────────────────────────────
        restock_y = slot_y + slot_area_h + 6
        remaining = max(0.0, RESTOCK_INTERVAL - self._restock_timer)
        mins = int(remaining) // 60
        secs = int(remaining) % 60
        auto_str = f"Auto-restock in {mins}:{secs:02d}"
        auto_surf = self.font.render(auto_str, True, WIN_DARK)
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
        sell_hdr = self.font.render("Sell Your Fish", True, WIN_DARK)
        surface.blit(sell_hdr, (p.left + _PAD, sep_y + 4))

        # ── Sell list ────────────────────────────────────────────
        sell_list_y = sep_y + 18
        avail_h = p.bottom - sell_list_y - 4
        capacity = max(1, avail_h // _ROW_H)
        self._sell_rows_capacity = capacity

        # Scroll arrows — use sprite icons when available, else plain ASCII buttons
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

        self._sell_rows = []
        self.tip_regions = []
        if not fish_list:
            no_fish = self.font.render("No fish to sell.", True, WIN_MID)
            surface.blit(no_fish, (p.left + _PAD, sell_list_y + 4))
        else:
            # Clamp scroll
            max_scroll = max(0, len(fish_list) - capacity)
            self._scroll = min(max_scroll, max(0, self._scroll))

            visible = fish_list[self._scroll: self._scroll + capacity]
            for ri, fish in enumerate(visible):
                ry2 = sell_list_y + ri * _ROW_H
                row_r = pygame.Rect(p.left + _PAD, ry2, p.w - _PAD * 2 - 22, _ROW_H)

                # Row background (alternating)
                if ri % 2 == 0:
                    pygame.draw.rect(surface, (182, 182, 190), row_r)

                # Rarity dot (matches Fish List panel colours)
                _sp = fish.sp
                if _sp.get("super_rare"):
                    _rdot = (180, 70, 240)   # purple
                elif _sp.get("rare"):
                    _rdot = (80, 150, 255)   # blue
                elif _sp.get("uncommon"):
                    _rdot = (60, 210, 80)    # green
                else:
                    _rdot = (160, 160, 160)  # gray — common
                pygame.draw.circle(surface, _rdot,
                                   (row_r.left + 8, row_r.centery), 5)
                pygame.draw.circle(surface, (0, 0, 0),
                                   (row_r.left + 8, row_r.centery), 5, 1)
                # Tooltip for rarity dot
                _rarity_label = ("Epic" if _sp.get("super_rare")
                                 else "Rare" if _sp.get("rare")
                                 else "Uncommon" if _sp.get("uncommon")
                                 else "Common")
                self.tip_regions.append((
                    pygame.Rect(row_r.left, row_r.centery - 8, 16, 16),
                    f"Rarity: {_rarity_label}",
                ))

                # Name + species
                nm = getattr(fish, "name", "?")
                sp_name = fish.sp.get("name", "?")
                label = f"{nm} ({sp_name})"
                lbl_surf = self.font.render(label[:28], True, (0, 0, 0))
                surface.blit(lbl_surf, (row_r.left + 18, row_r.top + (row_r.h - lbl_surf.get_height()) // 2))

                # Sell price + button — lay out right-to-left to avoid overlap
                price = fish_sell_price(fish)
                sell_r = pygame.Rect(row_r.right - 34, ry2 + 3, 32, _ROW_H - 6)
                price_s = self.font.render(f"{price}c", True, (120, 90, 0))
                price_x = sell_r.left - 4 - price_s.get_width()
                surface.blit(price_s, (price_x, row_r.top + (row_r.h - price_s.get_height()) // 2))
                _btn(surface, sell_r, "Sell", self.font)
                self._sell_rows.append((sell_r, fish))

        # ── Panel border clamp line ──────────────────────────────
        pygame.draw.rect(surface, WIN_DARK, p, 1)
