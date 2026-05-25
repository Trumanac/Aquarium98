"""
fish_roster_panel.py — Transparent fish-list overlay on the left side of the tank.

Toggled by the roster toolbar button.  Shows every living fish as a thumbnail
row; click a row to open that fish's FishInfoPanel.  Scroll if the list is long.
"""
from __future__ import annotations

import pygame

WIN_GRAY  = (192, 192, 192)
WIN_LIGHT = (255, 255, 255)
WIN_DARK  = (64,  64,  64)
PANEL_BG  = (0,   20,  50,  195)   # semi-transparent dark blue (RGBA)

# RPG rarity colours (match fish_info_panel)
_COL_UNCOMMON   = (60,  210,  80)
_COL_RARE       = (80,  150, 255)
_COL_SUPER_RARE = (180,  70, 240)
ROW_H     = 30
ROW_SEP   = 2
THUMB_W   = 38
THUMB_H   = 28
PW        = 106   # panel width


class FishRosterPanel:
    """Draws a scrollable list of fish inside the left edge of the tank."""

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
        self._overlay: pygame.Surface | None = None
        self._overlay_size = (0, 0)
        self._row_bg_normal: pygame.Surface | None = None
        self._row_bg_hover: pygame.Surface | None = None
        self._row_bg_size = (0, 0)

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

    # ------------------------------------------------------------------
    def handle_event(self, ev: pygame.event.Event,
                     fish_list: list) -> int | None:
        """Return fish index into fish_list if user clicked a row, else None."""
        if not self.visible:
            return None

        if ev.type == pygame.MOUSEWHEEL:
            self._scroll = max(0, self._scroll - ev.y)
            return None

        if ev.type == pygame.MOUSEMOTION:
            self._hover = self._row_at(ev.pos)
            return None

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            # Close button (top-right of panel header)
            if self._close_btn.collidepoint(ev.pos):
                self.close()
                return None
            row = self._row_at(ev.pos)
            if row is not None:
                idx = self._scroll + row
                if 0 <= idx < len(fish_list):
                    return idx
        return None

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
        max_scroll = max(0, len(fish_list) - visible_rows)
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
        htxt = self.font.render("Fish List", True, WIN_LIGHT)
        surface.blit(htxt, (hbar.left + 5,
                             hbar.top + (header_h - htxt.get_height()) // 2))

        # Close (×) button
        self._close_btn = pygame.Rect(hbar.right - 16, hbar.top + 3, 12, 14)
        pygame.draw.rect(surface, (180, 80, 80), self._close_btn)
        xs = self.font.render("x", True, WIN_LIGHT)
        surface.blit(xs, (self._close_btn.left + (self._close_btn.w - xs.get_width()) // 2,
                           self._close_btn.top  + (self._close_btn.h - xs.get_height()) // 2))

        # Rows
        self._rows = []
        self.tip_regions = []
        ry = py + header_h + 2
        visible_fish = fish_list[self._scroll: self._scroll + visible_rows]
        for i, f in enumerate(visible_fish):
            rr = pygame.Rect(px + 2, ry, PW - 4, ROW_H)
            self._rows.append(rr)
            # Hover highlight
            is_hover = (self._hover == i)
            row_w, row_h = rr.w, rr.h
            if self._row_bg_size != (row_w, row_h):
                self._row_bg_normal = pygame.Surface((row_w, row_h), pygame.SRCALPHA)
                self._row_bg_normal.fill((10, 30, 70, 140))
                self._row_bg_hover = pygame.Surface((row_w, row_h), pygame.SRCALPHA)
                self._row_bg_hover.fill((40, 80, 160, 160))
                self._row_bg_size = (row_w, row_h)
            surface.blit(self._row_bg_hover if is_hover else self._row_bg_normal, rr.topleft)

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
            # Rarity dot (3 px radius) just to right of thumbnail
            dot_x = rr.left + THUMB_W + 5
            dot_y = rr.top + ROW_H // 2
            if rarity_col:
                pygame.draw.circle(surface, rarity_col, (dot_x, dot_y), 3)
                name_off = 8   # offset name past the dot
            else:
                name_off = 0

            # Mood indicator: small filled circle at right edge of row
            # (text emoticons are unreliable in the Win98 bitmap font)
            mood = getattr(f, "mood", "content")
            mood_col = {"happy": (30, 200, 60), "content": (220, 200, 40),
                        "stressed": (220, 60, 60), "hungry": (220, 160, 20)
                        }.get(mood, (128, 128, 128))
            ind_r  = 4
            ind_cx = rr.right - ind_r - 3
            ind_cy = rr.top + ROW_H // 2
            pygame.draw.circle(surface, mood_col, (ind_cx, ind_cy), ind_r)
            pygame.draw.circle(surface, (0, 0, 0),  (ind_cx, ind_cy), ind_r, 1)

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

            ns = self.font.render(name, True, WIN_LIGHT)
            max_name_w = (ind_cx - ind_r) - 3 - dot_x - name_off - 4
            while ns.get_width() > max_name_w and len(name) > 1:
                name = name[:-1]
                ns = self.font.render(name + "..", True, WIN_LIGHT)
            surface.blit(ns, (dot_x + name_off,
                               rr.top + (ROW_H - ns.get_height()) // 2))

            ry += ROW_H + ROW_SEP

        # Scroll indicator
        if len(fish_list) > visible_rows:
            total = max(1, len(fish_list) - visible_rows)
            frac_top = self._scroll / total
            frac_bot = min(1.0, (self._scroll + visible_rows) / len(fish_list))
            bar_x   = px + PW - 5
            bar_top = py + header_h + 2
            bar_bot = py + ph - 2
            bar_h   = bar_bot - bar_top
            ind_top = bar_top + int(frac_top * bar_h)
            ind_bot = bar_top + int(frac_bot * bar_h)
            pygame.draw.rect(surface, (80, 80, 80), (bar_x, bar_top, 3, bar_h))
            pygame.draw.rect(surface, WIN_LIGHT,
                             (bar_x, ind_top, 3, max(4, ind_bot - ind_top)))

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
