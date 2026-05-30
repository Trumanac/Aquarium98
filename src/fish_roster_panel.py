"""
fish_roster_panel.py — Transparent fish-list overlay on the left side of the tank.

Toggled by the roster toolbar button.  Shows every living fish as a thumbnail
row; click a row to open that fish's FishInfoPanel.  Scroll if the list is long.
"""
from __future__ import annotations

import pygame
from .coin_system import fish_sell_price

WIN_GRAY  = (192, 192, 192)
WIN_LIGHT = (255, 255, 255)
WIN_DARK  = (64,  64,  64)
PANEL_BG  = (0,   20,  50,  195)   # semi-transparent dark blue (RGBA)


def _bevel(surf: pygame.Surface, r: pygame.Rect, pressed: bool = False) -> None:
    tl = WIN_DARK  if pressed else WIN_LIGHT
    br = WIN_LIGHT if pressed else WIN_DARK
    pygame.draw.line(surf, tl, r.topleft, (r.right - 1, r.top))
    pygame.draw.line(surf, tl, r.topleft, (r.left, r.bottom - 1))
    pygame.draw.line(surf, br, (r.right - 1, r.top), (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, br, (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1))

# RPG rarity colours (match fish_info_panel)
_COL_UNCOMMON   = (60,  210,  80)
_COL_RARE       = (80,  150, 255)
_COL_SUPER_RARE = (180,  70, 240)


def _draw_mood_dot(surf: pygame.Surface, cx: int, cy: int, r: int,
                  mood: str, col: tuple) -> None:
    """Draw a mood indicator circle; 'happy' gets a pixel smiley face."""
    pygame.draw.circle(surf, col, (cx, cy), r)
    pygame.draw.circle(surf, (0, 0, 0), (cx, cy), r, 1)
    if mood == "happy":
        e  = max(1, r // 3)
        pygame.draw.circle(surf, (0, 0, 0), (cx - e, cy - e), 1)
        pygame.draw.circle(surf, (0, 0, 0), (cx + e, cy - e), 1)
        sm = max(2, r // 2)
        pygame.draw.line(surf, (0, 0, 0),
                         (cx - sm, cy + sm // 2), (cx, cy + sm), 1)
        pygame.draw.line(surf, (0, 0, 0),
                         (cx, cy + sm), (cx + sm, cy + sm // 2), 1)
ROW_H     = 30
ROW_SEP   = 2
THUMB_W   = 38
THUMB_H   = 28
PW        = 172   # panel width
_SC_W           = 158   # quick-stats side card width
_SC_PAD         = 5     # side card inner padding
_SC_BTN_FLASH_MS = 300  # ms a side card button stays visually pressed


def _draw_stat_bar(surf: pygame.Surface, r: pygame.Rect,
                   pct: float, color: tuple) -> None:
    """Compact sunken progress bar for the roster side card."""
    pygame.draw.rect(surf, (25, 55, 100), r)
    if pct > 0:
        pygame.draw.rect(surf, color,
                         pygame.Rect(r.left, r.top, max(1, int(r.w * pct)), r.h))
    pygame.draw.line(surf, WIN_DARK,  r.topleft, (r.right - 1, r.top))
    pygame.draw.line(surf, WIN_DARK,  r.topleft, (r.left,      r.bottom - 1))
    pygame.draw.line(surf, WIN_LIGHT, (r.right - 1, r.top), (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, WIN_LIGHT, (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1))


def _hp_color_sc(pct: float) -> tuple:
    """Green when high (full/healthy) → red when low (empty/critical).  Shared by HP, Fed, and Life bars."""
    return (int(220 * (1.0 - pct)), int(200 * pct), 30)


class FishRosterPanel:
    """Draws a scrollable list of fish inside the left edge of the tank."""

    # Sort modes cycle order and labels
    _SORT_MODES = ["recent", "rarity", "species", "name", "age", "mood"]
    _SORT_LABELS = {"recent": "\u2193 Newest", "rarity": "\u2605 Rarity", "species": "Species",
                   "name": "Name A-Z", "age": "Age \u2193", "mood": "\u263A Mood"}

    def __init__(self, font: pygame.font.Font):
        self.font    = font
        self.visible = False
        self._scroll = 0          # top row index
        self._hover  = -1         # hovered row index
        self._rect   = pygame.Rect(0, 0, PW, 200)   # updated each draw
        self._rows: list[pygame.Rect] = []           # screen rects per row
        self.tip_regions: list[tuple[pygame.Rect, str]] = []  # for tooltips
        self._fish_sheets: dict[str, pygame.Surface] = {}
        # Thumbnail cache: fish id → small Surface
        self._thumb_cache: dict[int, pygame.Surface] = {}
        # Surface caches for semi-transparent overlays (avoid per-frame alloc)
        self._close_btn  = pygame.Rect(0, 0, 0, 0)
        self._sort_btn   = pygame.Rect(0, 0, 0, 0)
        self._sort_mode: str = "recent"   # current sort mode
        self._overlay: pygame.Surface | None = None
        self._overlay_size = (0, 0)
        self._row_bg_normal: pygame.Surface | None = None
        self._row_bg_hover: pygame.Surface | None = None
        self._row_bg_size = (0, 0)
        # Quick-stats side card state
        self._selected_fish              = None
        self._sc_rect      = pygame.Rect(0, 0, 0, 0)
        self._sc_feed_btn    = pygame.Rect(0, 0, 0, 0)
        self._sc_sell_btn    = pygame.Rect(0, 0, 0, 0)
        self._sc_profile_btn = pygame.Rect(0, 0, 0, 0)
        self._sc_close_btn   = pygame.Rect(0, 0, 0, 0)
        self._sc_overlay: pygame.Surface | None = None
        self._sc_overlay_size = (0, 0)
        self._sc_btn_flash: dict[str, int] = {}   # "feed"/"sell" → ticks at press
        self._sort_press: bool = False             # sort button held state

    # ------------------------------------------------------------------
    def toggle(self) -> None:
        self.visible = not self.visible
        if self.visible:
            self._scroll = 0

    def open(self) -> None:
        self.visible = True
        self._scroll = 0

    def close(self) -> None:
        self.visible = False
        self._selected_fish = None
        self._sort_press = False

    def deselect(self) -> None:
        self._selected_fish = None

    # ------------------------------------------------------------------
    def handle_event(self, ev: pygame.event.Event,
                     fish_list: list) -> int | None:
        """Return fish index into fish_list if user clicked a row, else None."""
        if not self.visible:
            return None

        if ev.type == pygame.MOUSEWHEEL:
            self._scroll = max(0, self._scroll - ev.y)
            self._hover = -1
            return None

        if ev.type == pygame.MOUSEMOTION:
            self._hover = self._row_at(ev.pos)
            return None

        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_UP, pygame.K_DOWN):
            if self._selected_fish is not None:
                sorted_fish = self._sorted_fish(fish_list)
                try:
                    cur_idx = sorted_fish.index(self._selected_fish)
                except ValueError:
                    return True
                delta = -1 if ev.key == pygame.K_UP else 1
                new_idx = max(0, min(len(sorted_fish) - 1, cur_idx + delta))
                self._selected_fish = sorted_fish[new_idx]
                # Scroll to keep the selected fish visible
                _hdr_h = 20
                vis_rows = max(1, (self._rect.h - _hdr_h - 4) // (ROW_H + ROW_SEP))
                if new_idx < self._scroll:
                    self._scroll = new_idx
                elif new_idx >= self._scroll + vis_rows:
                    self._scroll = new_idx - vis_rows + 1
                self._hover = -1
                return True
            return None

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            # ── Side card buttons (checked before roster to avoid overlap issues) ──
            if self._selected_fish is not None:
                if self._sc_close_btn.inflate(8, 8).collidepoint(ev.pos):
                    self._selected_fish = None
                    return True
                if self._sc_feed_btn.inflate(0, 8).collidepoint(ev.pos):
                    self._sc_btn_flash["feed"] = pygame.time.get_ticks()
                    return ("feed", self._selected_fish)
                if self._sc_sell_btn.inflate(0, 8).collidepoint(ev.pos):
                    self._sc_btn_flash["sell"] = pygame.time.get_ticks()
                    fish_to_sell = self._selected_fish
                    self._selected_fish = None
                    return ("sell", fish_to_sell)
                if self._sc_profile_btn.inflate(0, 8).collidepoint(ev.pos):
                    return ("profile", self._selected_fish)
                if self._sc_rect.collidepoint(ev.pos):
                    return True  # inside card but not a button — consume
            # ── Roster panel ──────────────────────────────────────────────────────
            # Close button (top-right of panel header) — inflated hitbox
            if self._close_btn.inflate(8, 8).collidepoint(ev.pos):
                self.close()
                return True
            # Sort button — press state, fires on MOUSEUP
            if self._sort_btn.inflate(4, 8).collidepoint(ev.pos):
                self._sort_press = True
                return True
            row = self._row_at(ev.pos)
            if row is not None:
                sorted_fish = self._sorted_fish(fish_list)
                idx = self._scroll + row
                if 0 <= idx < len(sorted_fish):
                    target = sorted_fish[idx]
                    # Toggle: click same row to close the side card
                    if self._selected_fish is target:
                        self._selected_fish = None
                    else:
                        self._selected_fish = target
                return True
            if self._rect.collidepoint(ev.pos):
                return True
            self.close()
            return None

        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            if self._sort_press:
                self._sort_press = False
                if self._sort_btn.inflate(4, 8).collidepoint(ev.pos):
                    idx = self._SORT_MODES.index(self._sort_mode)
                    self._sort_mode = self._SORT_MODES[(idx + 1) % len(self._SORT_MODES)]
                    self._scroll = 0
            return None

        return None

    def _sorted_fish(self, fish_list: list) -> list:
        """Return a view of fish_list sorted by current _sort_mode."""
        def _rarity(f):
            if f.sp.get("super_rare"): return 0
            if f.sp.get("rare"):       return 1
            if f.sp.get("uncommon"):   return 2
            return 3
        if self._sort_mode == "recent":
            return list(reversed(fish_list))    # newest (last-appended) first
        if self._sort_mode == "rarity":
            return sorted(fish_list, key=lambda f: (_rarity(f), f.name.lower()))
        if self._sort_mode == "species":
            return sorted(fish_list, key=lambda f: (f.sp["name"].lower(), f.name.lower()))
        if self._sort_mode == "name":
            return sorted(fish_list, key=lambda f: f.name.lower())
        if self._sort_mode == "age":
            return sorted(fish_list, key=lambda f: -getattr(f, "age", 0.0))
        if self._sort_mode == "mood":
            _mood_order = {"stressed": 0, "hungry": 1, "content": 2, "happy": 3}
            return sorted(fish_list, key=lambda f: _mood_order.get(getattr(f, "mood", "content"), 2))
        return list(fish_list)   # fallback

    def _row_at(self, pos: tuple[int, int]) -> int | None:
        for i, rr in enumerate(self._rows):
            if rr.collidepoint(pos):
                return i
        return None

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface,
             fish_list: list,
             tank_rect: pygame.Rect,
             fish_sheets: dict[str, pygame.Surface]) -> None:
        if not self.visible:
            return

        self._fish_sheets = fish_sheets

        # Panel height: fit all rows or tank height, whichever is smaller
        header_h = 20
        visible_rows = max(1, (tank_rect.h - header_h - 4) // (ROW_H + ROW_SEP))
        ph = header_h + visible_rows * (ROW_H + ROW_SEP) + 4

        px = tank_rect.left + 2
        py = tank_rect.top  + 2
        self._rect = pygame.Rect(px, py, PW, ph)

        # Clamp scroll
        sorted_fish = self._sorted_fish(fish_list)
        max_scroll = max(0, len(sorted_fish) - visible_rows)
        self._scroll = min(self._scroll, max_scroll)

        # Draw semi-transparent background (cached to avoid per-frame alloc)
        if self._overlay is None or self._overlay_size != (PW, ph):
            self._overlay = pygame.Surface((PW, ph), pygame.SRCALPHA)
            self._overlay.fill(PANEL_BG)
            self._overlay_size = (PW, ph)
        surface.blit(self._overlay, (px, py))

        # Header bar
        hbar = pygame.Rect(px, py, PW, header_h)
        pygame.draw.rect(surface, (0, 40, 100), hbar)
        htxt = self.font.render(f"Fish List ({len(sorted_fish)})", True, WIN_LIGHT)
        surface.blit(htxt, (hbar.left + 5,
                             hbar.top + (header_h - htxt.get_height()) // 2))

        # Close (×) button
        self._close_btn = pygame.Rect(hbar.right - 20, hbar.top + 3, 16, 14)
        pygame.draw.rect(surface, (180, 80, 80), self._close_btn)
        _bevel(surface, self._close_btn)
        xs = self.font.render("x", True, WIN_LIGHT)
        surface.blit(xs, (self._close_btn.left + (self._close_btn.w - xs.get_width()) // 2,
                           self._close_btn.top  + (self._close_btn.h - xs.get_height()) // 2))

        # Sort button — compact, just left of close
        sort_lbl = self._SORT_LABELS[self._sort_mode]
        slbl_surf = self.font.render(sort_lbl, True, (220, 220, 80))
        sort_btn_w = slbl_surf.get_width() + 6
        sort_btn_h = header_h - 4
        self._sort_btn = pygame.Rect(hbar.right - 20 - 2 - sort_btn_w,
                                     hbar.top + 2, sort_btn_w, sort_btn_h)
        _sort_bg = (15, 45, 110) if self._sort_press else (30, 70, 150)
        _sort_border = (50, 90, 160) if self._sort_press else (80, 120, 200)
        pygame.draw.rect(surface, _sort_bg, self._sort_btn)
        pygame.draw.rect(surface, _sort_border, self._sort_btn, 1)
        _sox = 1 if self._sort_press else 0
        surface.blit(slbl_surf, (self._sort_btn.left + 3 + _sox,
                                  self._sort_btn.top + (sort_btn_h - slbl_surf.get_height()) // 2 + _sox))

        # Rows
        self._rows = []
        self.tip_regions = []
        self.tip_regions.append((
            self._sort_btn.inflate(4, 8),
            f"Sort: {self._sort_mode.capitalize()} — click to cycle (Recent/Rarity/Species/Name/Age/Mood)",
        ))
        ry = py + header_h + 2
        visible_fish = sorted_fish[self._scroll: self._scroll + visible_rows]
        for i, f in enumerate(visible_fish):
            rr = pygame.Rect(px + 2, ry, PW - 4, ROW_H)
            self._rows.append(rr)
            # Hover / selection highlight
            is_hover = (self._hover == i)
            is_sel   = (self._selected_fish is f)
            row_w, row_h = rr.w, rr.h
            if self._row_bg_size != (row_w, row_h):
                self._row_bg_normal = pygame.Surface((row_w, row_h), pygame.SRCALPHA)
                self._row_bg_normal.fill((10, 30, 70, 140))
                self._row_bg_hover = pygame.Surface((row_w, row_h), pygame.SRCALPHA)
                self._row_bg_hover.fill((40, 80, 160, 160))
                self._row_bg_size = (row_w, row_h)
            surface.blit(self._row_bg_hover if (is_hover or is_sel) else self._row_bg_normal, rr.topleft)
            if is_sel:
                pygame.draw.rect(surface, (100, 160, 255), rr, 1)

            # Nemo easter egg: orange glow border for player-renamed fish called "Nemo"
            if getattr(f, "custom_name", False) and f.name.lower() == "nemo":
                pygame.draw.rect(surface, (255, 120, 0), rr, 2)
                pygame.draw.rect(surface, (255, 200, 80), rr.inflate(-2, -2), 1)

            # Thumbnail
            thumb = self._get_thumb(f)
            if thumb:
                surface.blit(thumb, (rr.left + 2, rr.top + (ROW_H - THUMB_H) // 2))
            else:
                pygame.draw.rect(surface, (30, 60, 120),
                                 (rr.left + 2, rr.top + (ROW_H - THUMB_H) // 2,
                                  THUMB_W, THUMB_H))

            # Name (truncated) + rarity dot + mood face
            name = f.name
            # Pick rarity colour for dot
            if f.sp.get("super_rare"):
                rarity_col: tuple | None = _COL_SUPER_RARE
            elif f.sp.get("rare"):
                rarity_col = _COL_RARE
            elif f.sp.get("uncommon"):
                rarity_col = _COL_UNCOMMON
            else:
                rarity_col = None
            # Rarity dot (6 px radius) just to right of thumbnail
            dot_x = rr.left + THUMB_W + 8
            dot_y = rr.top + ROW_H // 2
            if rarity_col:
                pygame.draw.circle(surface, rarity_col, (dot_x, dot_y), 6)
                pygame.draw.circle(surface, (0, 0, 0),  (dot_x, dot_y), 6, 1)
                name_off = 14   # offset name past the dot
            else:
                name_off = 0

            # Mood indicator: filled circle at right edge of row
            # (text emoticons are unreliable in the Win98 bitmap font)
            mood = getattr(f, "mood", "content")
            mood_col = {"happy": (30, 200, 60), "content": (80, 200, 80),
                        "stressed": (220, 60, 60), "hungry": (220, 160, 20)
                        }.get(mood, (128, 128, 128))
            ind_r  = 6
            ind_cx = rr.right - ind_r - 4
            ind_cy = rr.top + ROW_H // 2
            _draw_mood_dot(surface, ind_cx, ind_cy, ind_r, mood, mood_col)

            # Register tooltip regions for rarity and mood dots
            _mood_tips = {"happy": "Happy — well-fed and thriving",
                          "content": "Content — healthy normal state",
                          "stressed": "Stressed — overcrowded or dirty water",
                          "hungry": "Hungry — feed soon or health will drop"}
            self.tip_regions.append((
                pygame.Rect(ind_cx - 8, ind_cy - 8, 16, 16),
                _mood_tips.get(mood, f"Mood: {mood}"),
            ))
            if rarity_col:
                if rarity_col == _COL_SUPER_RARE:
                    _rarity_text = "Epic — extremely rare find"
                elif rarity_col == _COL_RARE:
                    _rarity_text = "Rare — hard to find"
                else:
                    _rarity_text = "Uncommon — appears less often"
                self.tip_regions.append((
                    pygame.Rect(dot_x - 8, dot_y - 8, 16, 16),
                    _rarity_text,
                ))

            # Age text (shown between name and mood dot)
            _age_secs = getattr(f, "age", 0.0)
            if _age_secs >= 86400:
                _age_str = f"{_age_secs / 86400:.1f}d"
            elif _age_secs >= 3600:
                _age_str = f"{_age_secs / 3600:.1f}h"
            else:
                _age_str = f"{int(_age_secs / 60)}m"
            age_ns = self.font.render(_age_str, True, (160, 180, 220))
            age_text_w = age_ns.get_width() + 4

            ns = self.font.render(name, True, WIN_LIGHT)
            max_name_w = (ind_cx - ind_r) - 3 - dot_x - name_off - 4 - age_text_w
            while ns.get_width() > max_name_w and len(name) > 1:
                name = name[:-1]
                ns = self.font.render(name + "..", True, WIN_LIGHT)
            surface.blit(ns, (dot_x + name_off,
                               rr.top + (ROW_H - ns.get_height()) // 2))
            # Age text right-aligned before mood dot
            age_blit_x = ind_cx - ind_r - 4 - age_ns.get_width()
            surface.blit(age_ns, (age_blit_x,
                                   rr.top + (ROW_H - age_ns.get_height()) // 2))

            ry += ROW_H + ROW_SEP

        # Scroll indicator
        if len(sorted_fish) > visible_rows:
            total_fish = len(sorted_fish)
            frac_top = self._scroll / total_fish
            frac_bot = (self._scroll + visible_rows) / total_fish
            bar_x   = px + PW - 5
            bar_top = py + header_h + 2
            bar_bot = py + ph - 2
            bar_h   = bar_bot - bar_top
            ind_top = bar_top + int(frac_top * bar_h)
            ind_bot = bar_top + int(frac_bot * bar_h)
            pygame.draw.rect(surface, (80, 80, 80), (bar_x, bar_top, 3, bar_h))
            pygame.draw.rect(surface, WIN_LIGHT,
                             (bar_x, ind_top, 3, max(4, ind_bot - ind_top)))

        # Draw quick-stats side card if a fish is selected and still alive
        if self._selected_fish is not None:
            if self._selected_fish not in fish_list:
                self._selected_fish = None
            else:
                self._draw_side_card(surface, self._selected_fish, surface.get_width())

    # ------------------------------------------------------------------
    def _draw_side_card(self, surface: pygame.Surface, fish, screen_w: int = 9999) -> None:
        """Draw the compact quick-stats card attached to the right of the roster."""
        fnt   = self.font
        fh    = fnt.get_height()
        pad   = _SC_PAD
        hdr_h = 16
        _TW   = THUMB_W   # reuse roster thumbnail size
        _TH   = THUMB_H

        # Height calculation: top block + stats + buttons
        has_rarity = fish.sp.get("super_rare") or fish.sp.get("rare") or fish.sp.get("uncommon")
        rc_lines   = 2 + (1 if has_rarity else 0)   # species + mood [+ rarity]
        top_h      = max(_TH, rc_lines * (fh + 3) - 3)
        stats_h    = 11 + 3 + 11 + 3 + fh + 3 + 11  # hp + hunger + age + lifespan bars
        sc_h       = hdr_h + pad + top_h + pad + 4 + stats_h + 4 + 20 + 4 + 22 + pad

        sx = min(self._rect.right, screen_w - _SC_W - 2)
        sy = self._rect.top
        self._sc_rect = pygame.Rect(sx, sy, _SC_W, sc_h)

        # Background
        if self._sc_overlay is None or self._sc_overlay_size != (_SC_W, sc_h):
            self._sc_overlay = pygame.Surface((_SC_W, sc_h), pygame.SRCALPHA)
            self._sc_overlay.fill(PANEL_BG)
            self._sc_overlay_size = (_SC_W, sc_h)
        surface.blit(self._sc_overlay, (sx, sy))

        # ── Header ────────────────────────────────────────────────────────
        hdr = pygame.Rect(sx, sy, _SC_W, hdr_h)
        pygame.draw.rect(surface, (0, 40, 100), hdr)
        name = fish.name
        max_name_w = _SC_W - 22
        ns = fnt.render(name, True, WIN_LIGHT)
        while ns.get_width() > max_name_w and len(name) > 1:
            name = name[:-1]
            ns = fnt.render(name + "..", True, WIN_LIGHT)
        surface.blit(ns, (sx + 4, sy + (hdr_h - ns.get_height()) // 2))

        self._sc_close_btn = pygame.Rect(sx + _SC_W - 18, sy + 1, 14, hdr_h - 2)
        pygame.draw.rect(surface, (180, 80, 80), self._sc_close_btn)
        xs = fnt.render("x", True, WIN_LIGHT)
        surface.blit(xs, (self._sc_close_btn.left + (self._sc_close_btn.w - xs.get_width()) // 2,
                           self._sc_close_btn.top  + (self._sc_close_btn.h - xs.get_height()) // 2))

        # ── Top block: thumbnail + species/rarity/mood ────────────────────
        cy  = sy + hdr_h + pad
        tf  = pygame.Rect(sx + pad, cy, _TW, _TH)
        pygame.draw.rect(surface, (20, 50, 100), tf)
        pygame.draw.line(surface, WIN_DARK,  tf.topleft,          (tf.right - 1, tf.top))
        pygame.draw.line(surface, WIN_DARK,  tf.topleft,          (tf.left,      tf.bottom - 1))
        pygame.draw.line(surface, WIN_LIGHT, (tf.right - 1, tf.top),   (tf.right - 1, tf.bottom - 1))
        pygame.draw.line(surface, WIN_LIGHT, (tf.left, tf.bottom - 1), (tf.right - 1, tf.bottom - 1))
        thumb = self._get_thumb(fish)
        if thumb:
            surface.blit(thumb, (tf.left + 1, tf.top + 1))

        rx = sx + pad + _TW + 5
        rw = sx + _SC_W - pad - rx
        ry = cy

        sp_s = fnt.render(fish.sp.get("name", "?"), True, (180, 210, 255))
        surface.set_clip(pygame.Rect(rx, ry, rw, fh))
        surface.blit(sp_s, (rx, ry))
        surface.set_clip(None)
        ry += fh + 3

        if fish.sp.get("super_rare"):
            badge = fnt.render("\u2605 EPIC", True, _COL_SUPER_RARE)
        elif fish.sp.get("rare"):
            badge = fnt.render("\u2605 RARE", True, _COL_RARE)
        elif fish.sp.get("uncommon"):
            badge = fnt.render("\u25c6 UNCOM", True, _COL_UNCOMMON)
        else:
            badge = None
        if badge is not None:
            surface.set_clip(pygame.Rect(rx, ry, rw, fh))
            surface.blit(badge, (rx, ry))
            surface.set_clip(None)
            ry += fh + 3

        mood     = getattr(fish, "mood", "content")
        mood_col = {"happy": (30, 200, 60), "content": (80, 200, 80),
                    "stressed": (220, 60, 60), "hungry": (220, 160, 20)}.get(mood, (128, 128, 128))
        _draw_mood_dot(surface, rx + 5, ry + fh // 2, 5, mood, mood_col)
        surface.blit(fnt.render(mood.capitalize(), True, mood_col), (rx + 13, ry))

        # ── Divider ───────────────────────────────────────────────────────
        div_y = max(tf.bottom, ry + fh) + pad
        dx1, dx2 = sx + pad, sx + _SC_W - pad
        pygame.draw.line(surface, WIN_DARK,  (dx1, div_y),     (dx2, div_y))
        pygame.draw.line(surface, WIN_LIGHT, (dx1, div_y + 1), (dx2, div_y + 1))
        sy2 = div_y + 3

        # ── Stats ─────────────────────────────────────────────────────────
        # All bars: full (100%) = good/green, empty (0%) = bad/red.
        lbl_w = fnt.size("Life")[0] + 3
        pct_w = fnt.size("100%")[0]  + 3
        bar_x = sx + pad + lbl_w
        bar_w = sx + _SC_W - pad - bar_x - pct_w

        hpct = max(0.0, min(1.0, fish.health))
        surface.blit(fnt.render("HP", True, WIN_LIGHT), (sx + pad, sy2 + 1))
        hp_r = pygame.Rect(bar_x, sy2, bar_w, 11)
        _draw_stat_bar(surface, hp_r, hpct, _hp_color_sc(hpct))
        surface.blit(fnt.render(f"{int(hpct * 100)}%", True, WIN_LIGHT), (hp_r.right + 2, sy2 + 1))
        sy2 += 14

        hg = max(0.0, min(1.0, 1.0 - fish.hunger))   # invert: 1.0 = full stomach, 0.0 = starving
        surface.blit(fnt.render("Fed", True, WIN_LIGHT), (sx + pad, sy2 + 1))
        hg_r = pygame.Rect(bar_x, sy2, bar_w, 11)
        _draw_stat_bar(surface, hg_r, hg, _hp_color_sc(hg))
        surface.blit(fnt.render(f"{int(hg * 100)}%", True, WIN_LIGHT), (hg_r.right + 2, sy2 + 1))
        sy2 += 14

        age_s = fish.age
        if age_s >= 86400:
            age_str = f"Age: {age_s / 86400:.1f}d"
        elif age_s >= 3600:
            age_str = f"Age: {age_s / 3600:.1f}h"
        else:
            age_str = f"Age: {int(age_s / 60)}m"
        surface.blit(fnt.render(age_str, True, (160, 200, 230)), (sx + pad, sy2))
        sy2 += fh + 4
        # Life bar (full = young/lots of lifespan remaining, empty = near natural end)
        life_pct = max(0.0, min(1.0, 1.0 - fish.age / max(1.0, fish.lifespan)))
        surface.blit(fnt.render("Life", True, WIN_LIGHT), (sx + pad, sy2 + 1))
        life_r = pygame.Rect(bar_x, sy2, bar_w, 11)
        _draw_stat_bar(surface, life_r, life_pct, _hp_color_sc(life_pct))
        surface.blit(fnt.render(f"{int(life_pct * 100)}%", True, WIN_LIGHT),
                     (life_r.right + 2, sy2 + 1))
        sy2 += 14
        # ── Divider ───────────────────────────────────────────────────────
        pygame.draw.line(surface, WIN_DARK,  (dx1, sy2),     (dx2, sy2))
        pygame.draw.line(surface, WIN_LIGHT, (dx1, sy2 + 1), (dx2, sy2 + 1))
        sy2 += 3

        # ── View Profile button (full width) ──────────────────────────────
        self._sc_profile_btn = pygame.Rect(sx + pad, sy2, _SC_W - pad * 2, 20)
        pygame.draw.rect(surface, (20, 60, 120), self._sc_profile_btn)
        pygame.draw.rect(surface, (60, 120, 200), self._sc_profile_btn, 1)
        ps = fnt.render("View Profile", True, WIN_LIGHT)
        surface.blit(ps, (self._sc_profile_btn.centerx - ps.get_width() // 2,
                           self._sc_profile_btn.top + (self._sc_profile_btn.h - ps.get_height()) // 2))
        sy2 += 24

        # ── Feed / Sell buttons ───────────────────────────────────────────
        half_w = (_SC_W - pad * 3) // 2
        self._sc_feed_btn = pygame.Rect(sx + pad,              sy2, half_w, 22)
        self._sc_sell_btn = pygame.Rect(sx + pad * 2 + half_w, sy2, _SC_W - pad * 3 - half_w, 22)
        sell_price = fish_sell_price(fish)
        _now = pygame.time.get_ticks()
        for btn, label, btn_key in (
                (self._sc_feed_btn, "Feed", "feed"),
                (self._sc_sell_btn, f"Sell ({sell_price}c)", "sell")):
            pressed = _now - self._sc_btn_flash.get(btn_key, 0) < _SC_BTN_FLASH_MS
            bg_col  = (8, 25, 60)      if pressed else (20, 60, 120)
            bd_col  = (180, 220, 255)  if pressed else (60, 120, 200)
            pygame.draw.rect(surface, bg_col, btn)
            pygame.draw.rect(surface, bd_col, btn, 1)
            toff = 1 if pressed else 0
            bs = fnt.render(label, True, WIN_LIGHT)
            surface.blit(bs, (btn.left + max(0, (btn.w - bs.get_width()) // 2) + toff,
                               btn.top  + (btn.h - bs.get_height()) // 2 + toff))

    # ------------------------------------------------------------------
    def _get_thumb(self, fish) -> pygame.Surface | None:
        fid = id(fish)
        if fid in self._thumb_cache:
            return self._thumb_cache[fid]
        sheet = self._fish_sheets.get(fish.sp.get("sheet", "fish_new.png"))
        if sheet is None:
            return None
        sw, sh = sheet.get_size()
        fw, fh = sw // 3, sh // 3
        sub = sheet.subsurface(pygame.Rect(0, 0, fw, fh)).copy()
        thumb = pygame.transform.smoothscale(sub, (THUMB_W, THUMB_H))
        self._thumb_cache[fid] = thumb
        return thumb

    def invalidate_thumb(self, fish) -> None:
        """Call when a fish dies or changes species so stale thumb is removed."""
        self._thumb_cache.pop(id(fish), None)

    def invalidate_all(self) -> None:
        """Clear the entire thumbnail cache (e.g. after a tank reset)."""
        self._thumb_cache.clear()
