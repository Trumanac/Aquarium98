"""
encyclopedia_panel.py — Win98-style Fish Encyclopaedia panel.

Displays every species from SPECIES list. Each entry shows:
  - A live sprite thumbnail  (colour) if ever seen, or a dark silhouette if not.
  - Species name + rarity badge once seen; just "???" if unseen.
  - A fun fact / description snippet once seen.

Entries are organised into rarity sections:
  Common | Uncommon | Rare | Epic

"Seen" is tracked in cfg["seen_species"] — a list of species-name strings.
Call  mark_seen(cfg, species_name)  whenever a fish is first spotted in the tank.

Toggle with the 'encyclopedia' action.
"""
from __future__ import annotations

import pygame

from src.simulation.species import SPECIES

WIN_GRAY  = (192, 192, 192)
WIN_LIGHT = (255, 255, 255)
WIN_DARK  = (64,  64,  64)
WIN_MID   = (128, 128, 128)
TITLE_A   = (0,   0,   128)
TITLE_B   = (16, 132, 208)
PANEL_BG  = (192, 192, 192)
GRID_BG   = (230, 230, 230)

COL_COMMON     = (160, 160, 160)
COL_UNCOMMON   = (60,  210,  80)
COL_RARE       = (80,  150, 255)
COL_SUPER_RARE = (180,  70, 240)

_TB_H  = 18
_PAD   = 6
_THUMB_H = 36   # max thumbnail height (fits within ROW_H=48)
_THUMB_W = 60   # max thumbnail width  (wider for long/wide species)
_ROW_H = 48     # row height per species entry
PW     = 310    # panel width

# Rarity buckets, drawn in order
_BUCKETS: list[tuple[str, tuple]] = [
    ("Common",     COL_COMMON),
    ("Uncommon",   COL_UNCOMMON),
    ("Rare",       COL_RARE),
    ("Epic",       COL_SUPER_RARE),
]


def _rarity_key(sp: dict) -> int:
    if sp.get("super_rare"):  return 3
    if sp.get("rare"):        return 2
    if sp.get("uncommon"):    return 1
    return 0


def mark_seen(cfg: dict, species_name: str) -> None:
    """Record that the player has seen this species."""
    seen: list[str] = cfg.get("seen_species") or []
    if species_name not in seen:
        seen.append(species_name)
        cfg["seen_species"] = seen


def is_seen(cfg: dict, species_name: str) -> bool:
    seen: list[str] = cfg.get("seen_species") or []
    return species_name in seen


def _bevel(surf: pygame.Surface, r: pygame.Rect, pressed: bool = False) -> None:
    tl = WIN_DARK  if pressed else WIN_LIGHT
    br = WIN_LIGHT if pressed else WIN_DARK
    pygame.draw.line(surf, tl, r.topleft, (r.right - 1, r.top))
    pygame.draw.line(surf, tl, r.topleft, (r.left, r.bottom - 1))
    pygame.draw.line(surf, br, (r.right - 1, r.top), (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, br, (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1))


class EncyclopediaPanel:
    """Scrollable species encyclopaedia panel."""

    def __init__(self, font: pygame.font.Font):
        self.font    = font
        self.visible = False
        self._scroll = 0        # lines scrolled (1 unit = 1 row-height px)
        self._rect   = pygame.Rect(0, 0, PW, 10)
        self._close_btn = pygame.Rect(0, 0, 0, 0)
        # Sorted species list: build once
        self._sorted: list[dict] = sorted(SPECIES, key=_rarity_key)
        # Thumbnail cache: name → Surface  (built lazily)
        self._thumb_cache: dict[str, pygame.Surface] = {}
        # Which species rows are expanded (show full fact)
        self._expanded: set[str] = set()
        # Row rects from last draw, used for click detection
        self._row_rects: dict[str, pygame.Rect] = {}

    # ------------------------------------------------------------------
    def toggle(self) -> None:
        self.visible = not self.visible
        if self.visible:
            self._scroll = 0

    def close(self) -> None:
        self.visible = False

    # ------------------------------------------------------------------
    def handle_event(self, ev: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if ev.type == pygame.MOUSEWHEEL:
            self._scroll = max(0, self._scroll - ev.y * _ROW_H)
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self._close_btn.collidepoint(ev.pos):
                self.close()
                return True
            # Toggle row expansion on click
            for sp_name, row_r in self._row_rects.items():
                if row_r.collidepoint(ev.pos):
                    if sp_name in self._expanded:
                        self._expanded.discard(sp_name)
                    else:
                        self._expanded.add(sp_name)
                    return True
            if self._rect.collidepoint(ev.pos):
                return True
        return False

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface,
             cfg: dict,
             tank_rect: pygame.Rect,
             fish_sheets: dict[str, pygame.Surface]) -> None:
        if not self.visible:
            return

        fh = self.font.get_height()

        # Panel height: fill the tank interior
        header_h = _TB_H + 6
        footer_h = 4
        ph = tank_rect.h - 4
        content_h = ph - header_h - footer_h

        # Anchor to right side of tank
        px = tank_rect.right - PW - 2
        py = tank_rect.top + 2
        self._rect = pygame.Rect(px, py, PW, ph)

        pygame.draw.rect(surface, PANEL_BG, self._rect)
        _bevel(surface, self._rect)

        # Title bar
        tb = pygame.Rect(px + 3, py + 3, PW - 6, _TB_H)
        for i in range(tb.h):
            t = i / max(1, tb.h - 1)
            c = (int(TITLE_A[0] + (TITLE_B[0] - TITLE_A[0]) * t),
                 int(TITLE_A[1] + (TITLE_B[1] - TITLE_A[1]) * t),
                 int(TITLE_A[2] + (TITLE_B[2] - TITLE_A[2]) * t))
            pygame.draw.line(surface, c,
                             (tb.left, tb.top + i),
                             (self._close_btn.left - 2 if self._close_btn.w else tb.right - 1,
                              tb.top + i))

        seen_count = sum(1 for sp in SPECIES if is_seen(cfg, sp["name"]))
        title_txt = f"Fish Encyclopaedia  {seen_count}/{len(SPECIES)}"
        ts = self.font.render(title_txt, True, WIN_LIGHT)
        surface.blit(ts, (tb.left + 5, tb.top + (tb.h - ts.get_height()) // 2))

        # Close button
        self._close_btn = pygame.Rect(self._rect.right - 3 - _TB_H, py + 3, _TB_H, _TB_H)
        pygame.draw.rect(surface, (180, 80, 80), self._close_btn)
        xs = self.font.render("x", True, WIN_LIGHT)
        surface.blit(xs, (
            self._close_btn.left + (self._close_btn.w - xs.get_width()) // 2,
            self._close_btn.top  + (self._close_btn.h - xs.get_height()) // 2))

        # ── content area ────────────────────────────────────────────
        content_rect = pygame.Rect(px + 2, py + header_h, PW - 4, content_h)
        surface.set_clip(content_rect)

        # Build a flat list of items to draw: section headers + species rows
        # Pre-build so we know total height for scrollbar
        items: list[tuple] = []   # ("header", label, col) | ("row", sp)
        prev_bucket = -1
        for sp in self._sorted:
            bk = _rarity_key(sp)
            if bk != prev_bucket:
                prev_bucket = bk
                label, col = _BUCKETS[bk]
                items.append(("header", label, col))
            items.append(("row", sp))

        HEADER_H = fh + 4
        _TEXT_MAX_W = PW - _THUMB_W - _PAD * 3 - 6

        def _wrap(text: str) -> list[str]:
            words = text.split()
            lines: list[str] = []
            cur = ""
            for w in words:
                test = (cur + " " + w).strip()
                if self.font.size(test)[0] <= _TEXT_MAX_W:
                    cur = test
                else:
                    if cur:
                        lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)
            return lines

        def item_h(it: tuple) -> int:
            if it[0] == "header":
                return HEADER_H
            _, sp = it
            if sp["name"] in self._expanded:
                facts = sp.get("fun_facts", [])
                if facts:
                    nlines = len(_wrap(facts[0]))
                    return max(_ROW_H, 4 + fh + 2 + fh + 4 + nlines * (fh + 2) + 8)
            return _ROW_H

        _sp_row_idx = {id(sp_): i for i, sp_ in enumerate(self._sorted)}
        self._row_rects = {}
        total_h = sum(item_h(it) for it in items)
        max_scroll = max(0, total_h - content_h)
        self._scroll = min(self._scroll, max_scroll)

        ry = py + header_h - self._scroll
        for item in items:
            ih = item_h(item)
            # Skip fully off-screen items
            if ry + ih <= py + header_h:
                ry += ih
                continue
            if ry >= py + header_h + content_h:
                break

            if item[0] == "header":
                _, label, col = item
                # Section header bar
                hr = pygame.Rect(px + 2, ry, PW - 4, HEADER_H)
                pygame.draw.rect(surface, col, hr)
                hs = self.font.render(f"── {label} ──", True, WIN_LIGHT)
                surface.blit(hs, (px + _PAD + 2, ry + (HEADER_H - fh) // 2))
            else:
                _, sp = item
                row_r = pygame.Rect(px + 2, ry, PW - 4, ih)
                # Alternating row tint
                pygame.draw.rect(surface, GRID_BG if _sp_row_idx.get(id(sp), 0) % 2 == 0
                                 else PANEL_BG, row_r)

                seen = is_seen(cfg, sp["name"])

                # Thumbnail (left) — centred both axes within the _THUMB_W×_THUMB_H cell
                thumb = self._get_thumb(sp, fish_sheets, seen)
                if thumb:
                    tw = thumb.get_width()
                    th = thumb.get_height()
                    tx = px + _PAD + (_THUMB_W - tw) // 2  # centre horizontally
                    ty = ry + (ih - th) // 2               # centre vertically
                    surface.blit(thumb, (tx, ty))
                else:
                    pygame.draw.rect(surface, WIN_MID,
                                     (px + _PAD, ry + (ih - _THUMB_H) // 2,
                                      _THUMB_W, _THUMB_H))

                # Text (right of thumbnail)
                tx_right = px + _PAD + _THUMB_W + 5
                max_w    = PW - _THUMB_W - _PAD * 3 - 6

                if seen:
                    # Name + rarity badge
                    name_s = self.font.render(sp["name"], True, (10, 10, 60))
                    surface.blit(name_s, (tx_right, ry + 4))

                    badge_y = ry + 4 + fh + 2
                    bk = _rarity_key(sp)
                    if bk == 3:
                        badge_col, badge_txt = COL_SUPER_RARE, "★ EPIC"
                    elif bk == 2:
                        badge_col, badge_txt = COL_RARE, "★ RARE"
                    elif bk == 1:
                        badge_col, badge_txt = COL_UNCOMMON, "◆ UNCOMMON"
                    else:
                        badge_col, badge_txt = COL_COMMON, "● COMMON"
                    badge_s = self.font.render(badge_txt, True, badge_col)
                    surface.blit(badge_s, (tx_right, badge_y))

                    # Fun fact — snippet (collapsed) or full wrapped text (expanded)
                    facts = sp.get("fun_facts", [])
                    if facts:
                        expanded = sp["name"] in self._expanded
                        if expanded:
                            wrapped_lines = _wrap(facts[0])
                            fy = ry + 4 + fh + 2 + fh + 4
                            for line in wrapped_lines:
                                fact_s = self.font.render(line, True, (80, 80, 100))
                                surface.blit(fact_s, (tx_right, fy))
                                fy += fh + 2
                            # Collapse arrow
                            arr = self.font.render("▲", True, (140, 120, 170))
                            surface.blit(arr, (self._rect.right - _PAD - arr.get_width() - 6,
                                               ry + 4))
                        else:
                            snippet = facts[0]
                            fact_s = self.font.render(snippet, True, (80, 80, 100))
                            clip_r = pygame.Rect(tx_right, ry + 4 + fh * 2 + 4, max_w, fh)
                            surface.set_clip(clip_r.clip(content_rect))
                            surface.blit(fact_s, (tx_right, ry + 4 + fh * 2 + 4))
                            surface.set_clip(content_rect)
                            # Expand arrow
                            arr = self.font.render("▼", True, (140, 120, 170))
                            surface.blit(arr, (self._rect.right - _PAD - arr.get_width() - 6,
                                               ry + 4))
                else:
                    # Unseen: show "???"
                    unk_s = self.font.render("???", True, WIN_MID)
                    surface.blit(unk_s, (tx_right, ry + (_ROW_H - fh) // 2))

                # Store row rect for click detection (full row height)
                self._row_rects[sp["name"]] = row_r
                _bevel(surface, row_r, pressed=False)
            ry += ih

        surface.set_clip(None)

        # Scroll bar
        if total_h > content_h:
            bar_x   = self._rect.right - 5
            bar_top = py + header_h
            bar_h   = content_h
            frac_top = self._scroll / max(1, total_h)
            frac_bot = min(1.0, frac_top + content_h / total_h)
            pygame.draw.rect(surface, (160, 160, 160), (bar_x, bar_top, 3, bar_h))
            pygame.draw.rect(surface, WIN_DARK,
                             (bar_x, bar_top + int(frac_top * bar_h),
                              3, max(4, int((frac_bot - frac_top) * bar_h))))

    # ------------------------------------------------------------------
    def _get_thumb(self, sp: dict, fish_sheets: dict,
                   seen: bool) -> pygame.Surface | None:
        """Return a scaled thumbnail (up to _THUMB_W×_THUMB_H), coloured if seen, silhouette if not."""
        key = sp["name"] + ("_seen" if seen else "_sil")
        if key in self._thumb_cache:
            return self._thumb_cache[key]

        sheet_name = sp.get("sheet", "fish_new.png")
        sheet = fish_sheets.get(sheet_name)
        if sheet is None:
            return None

        sw_full = sheet.get_width()
        sh_full = sheet.get_height()
        # 3×3 grid; top-left frame = [0,0]
        cell_w = sw_full // 3
        cell_h = sh_full // 3
        if cell_w < 1 or cell_h < 1:
            return None

        frame = sheet.subsurface(pygame.Rect(0, 0, cell_w, cell_h)).copy()

        # Scale to fit _THUMB_W × _THUMB_H preserving the ACTUAL cell aspect ratio.
        # Do NOT use sp["aspect"] here — that is the in-tank physics aspect, not
        # the sprite-cell shape, and using it produces smushed thumbnails for
        # eel-like / crab-like species whose cells are still landscape-oriented.
        cell_aspect = cell_w / max(1, cell_h)
        tw_by_h = int(_THUMB_H * cell_aspect)
        if tw_by_h <= _THUMB_W:
            tw, th = max(1, tw_by_h), _THUMB_H
        else:
            tw = _THUMB_W
            th = max(1, int(_THUMB_W / cell_aspect))
        frame = pygame.transform.smoothscale(frame, (tw, th))

        if not seen:
            # Convert to silhouette: keep alpha, fill colour dark grey
            sil = frame.copy()
            sil.fill((40, 40, 50), special_flags=pygame.BLEND_RGBA_MULT)
            frame = sil

        self._thumb_cache[key] = frame
        return frame
