"""
graveyard_panel.py — Win98-style Fish Memorial panel.

Shows a scrollable list of every fish that has ever died in the tank.
Records are stored in cfg["graveyard"] as a list of dicts, newest last:
  {"name": str, "species": str, "age_days": float, "cause": str}

Call log_death(cfg, fish) whenever a fish's health drops to zero.
Toggle with the 'graveyard' action.
"""
from __future__ import annotations

import pygame

WIN_GRAY  = (192, 192, 192)
WIN_LIGHT = (255, 255, 255)
WIN_DARK  = (64,  64,  64)
WIN_MID   = (128, 128, 128)
TITLE_A   = (0,   0,   128)
TITLE_B   = (16, 132, 208)
PANEL_BG  = (192, 192, 192)
ROW_A     = (212, 204, 210)
ROW_B     = (228, 220, 226)
STONE     = (120, 110, 118)

_TB_H  = 18
_PAD   = 6
_ROW_H = 54
PW     = 286


def _bevel(surf: pygame.Surface, r: pygame.Rect, pressed: bool = False) -> None:
    tl = WIN_DARK  if pressed else WIN_LIGHT
    br = WIN_LIGHT if pressed else WIN_DARK
    pygame.draw.line(surf, tl, r.topleft, (r.right - 1, r.top))
    pygame.draw.line(surf, tl, r.topleft, (r.left, r.bottom - 1))
    pygame.draw.line(surf, br, (r.right - 1, r.top), (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, br, (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1))


def log_death(cfg: dict, fish) -> None:
    """Record a fish's death.  Determines cause from fish state automatically."""
    if fish.hunger > 0.85:
        cause = "Starvation"
    elif fish.adult and fish.age >= fish.lifespan:
        cause = "Old age"
    else:
        cause = "Unknown"
    record = {
        "name":     fish.name,
        "species":  fish.sp.get("name", "Unknown"),
        "age_days": round(fish.age / 86400.0, 1),
        "cause":    cause,
    }
    graveyard: list = cfg.get("graveyard") or []
    graveyard.append(record)
    if len(graveyard) > 200:
        graveyard = graveyard[-200:]
    cfg["graveyard"] = graveyard


def _draw_tombstone(surf: pygame.Surface, cx: int, cy: int) -> None:
    """Draw a tiny pixel-art tombstone centred at (cx, cy)."""
    dark  = STONE
    light = tuple(min(255, c + 50) for c in STONE)
    # Base slab
    pygame.draw.rect(surf, dark,  (cx - 8, cy + 5, 16, 4))
    # Body
    pygame.draw.rect(surf, dark,  (cx - 5, cy - 4, 10, 9))
    # Arch top
    pygame.draw.rect(surf, dark,  (cx - 4, cy - 7,  8, 3))
    pygame.draw.rect(surf, dark,  (cx - 3, cy - 9,  6, 2))
    pygame.draw.rect(surf, dark,  (cx - 2, cy -11,  4, 2))
    # Highlights
    pygame.draw.line(surf, light, (cx - 5, cy - 4), (cx - 5, cy + 4))
    pygame.draw.line(surf, light, (cx - 5, cy - 4), (cx + 4, cy - 4))
    # RIP text (2px)
    for ox, oy in [(-1, 1), (0, 1), (1, 1), (-1, -1), (0, -1), (1, -1)]:
        pygame.draw.rect(surf, light, (cx + ox - 1, cy + oy, 2, 1))


class GraveyardPanel:
    """Scrollable fish memorial panel."""

    def __init__(self, font: pygame.font.Font):
        self.font       = font
        self.visible    = False
        self._scroll    = 0
        self._rect      = pygame.Rect(0, 0, PW, 10)
        self._close_btn = pygame.Rect(0, 0, 0, 0)
        # Reversed-list cache: rebuilt only when graveyard length changes
        self._graveyard_cache: list = []
        self._graveyard_len: int = -1
        # Title-bar gradient surface cache
        self._title_surf: pygame.Surface | None = None
        self._title_surf_w: int = 0

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
            if self._close_btn.inflate(8, 8).collidepoint(ev.pos):
                self.close()
                return True
            if self._rect.collidepoint(ev.pos):
                return True
            self.close()
            return False
        return False

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface,
             cfg: dict,
             tank_rect: pygame.Rect) -> None:
        if not self.visible:
            return

        fh = self.font.get_height()
        header_h = _TB_H + 6
        footer_h = 4
        ph        = tank_rect.h - 4
        content_h = ph - header_h - footer_h

        px = tank_rect.right - PW - 2
        py = tank_rect.top  + 2
        self._rect = pygame.Rect(px, py, PW, ph)

        pygame.draw.rect(surface, PANEL_BG, self._rect)
        _bevel(surface, self._rect)

        # Title bar gradient (cached per width)
        tb = pygame.Rect(px + 3, py + 3, PW - 6, _TB_H)
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

        raw = cfg.get("graveyard") or []
        if len(raw) != self._graveyard_len:
            self._graveyard_cache = list(reversed(raw))
            self._graveyard_len = len(raw)
        graveyard: list[dict] = self._graveyard_cache
        title_txt = f"Fish Memorial  \u2014  {len(graveyard)} lost"
        ts = self.font.render(title_txt, True, WIN_LIGHT)
        surface.blit(ts, (tb.left + 5, tb.top + (tb.h - ts.get_height()) // 2))

        # Close button
        self._close_btn = pygame.Rect(self._rect.right - 3 - _TB_H, py + 3, _TB_H, _TB_H)
        pygame.draw.rect(surface, (180, 80, 80), self._close_btn)
        xs = self.font.render("x", True, WIN_LIGHT)
        surface.blit(xs, (
            self._close_btn.left + (self._close_btn.w - xs.get_width()) // 2,
            self._close_btn.top  + (self._close_btn.h - xs.get_height()) // 2))

        # Content area
        content_rect = pygame.Rect(px + 2, py + header_h, PW - 4, content_h)
        surface.set_clip(content_rect)

        total_h = len(graveyard) * _ROW_H
        max_scroll = max(0, total_h - content_h)
        self._scroll = min(self._scroll, max_scroll)

        if not graveyard:
            msg = self.font.render("No fish have died yet.", True, WIN_MID)
            surface.blit(msg, (px + _PAD + 4, py + header_h + (content_h - fh) // 2))
        else:
            ry = py + header_h - self._scroll
            for i, rec in enumerate(graveyard):
                if ry + _ROW_H <= py + header_h:
                    ry += _ROW_H
                    continue
                if ry >= py + header_h + content_h:
                    break

                row_r = pygame.Rect(px + 2, ry, PW - 4, _ROW_H)
                pygame.draw.rect(surface, ROW_A if i % 2 == 0 else ROW_B, row_r)

                # Tombstone icon
                _draw_tombstone(surface, px + _PAD + 14, ry + _ROW_H // 2)

                # Name (bold via rendering twice offset by 1px)
                tx    = px + _PAD + 32
                name  = rec.get("name", "?")
                name_s = self.font.render(name, True, (25, 15, 35))
                surface.blit(name_s, (tx + 1, ry + 6))   # shadow
                surface.blit(name_s, (tx,     ry + 5))

                # Detail line: species · age · cause
                species_txt = rec.get("species", "")
                age_days    = rec.get("age_days", 0.0)
                cause_txt   = rec.get("cause", "")
                detail = f"{species_txt}  \u00b7  {age_days:.1f}d  \u00b7  {cause_txt}"
                det_s  = self.font.render(detail, True, (90, 70, 88))
                det_w  = PW - 4 - 32 - _PAD * 2
                clip_r = pygame.Rect(tx, ry + 5 + fh + 3, det_w, fh)
                surface.set_clip(clip_r.clip(content_rect))
                surface.blit(det_s, (tx, ry + 5 + fh + 3))
                surface.set_clip(content_rect)

                # Row separator
                pygame.draw.line(surface, (180, 168, 175),
                                 (px + 3, ry + _ROW_H - 1),
                                 (px + PW - 4, ry + _ROW_H - 1))
                ry += _ROW_H

        surface.set_clip(None)

        # Scrollbar
        if total_h > content_h:
            bar_x   = self._rect.right - 5
            bar_top = py + header_h
            bar_h   = content_h
            frac_top = self._scroll / max(1, total_h)
            frac_bot = min(1.0, frac_top + content_h / total_h)
            pygame.draw.rect(surface, (160, 150, 156), (bar_x, bar_top, 3, bar_h))
            pygame.draw.rect(surface, WIN_DARK,
                             (bar_x, bar_top + int(frac_top * bar_h),
                              3, max(4, int((frac_bot - frac_top) * bar_h))))
