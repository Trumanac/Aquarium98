"""
event_log_panel.py — Win98-style scrollable event log panel.

Displays timestamped game events: fish deaths, births, rare appearances, feeding.
Events are stored in cfg["event_log"] as a JSON list (capped at MAX_ENTRIES).
Toggle with 'event_log' action.
"""
from __future__ import annotations

import datetime

import pygame

WIN_GRAY  = (192, 192, 192)
WIN_LIGHT = (255, 255, 255)
WIN_DARK  = (64,  64,  64)
TITLE_A   = (0,   0,   128)
TITLE_B   = (16, 132, 208)
PANEL_BG  = (240, 240, 240)

_TB_H = 18
_PAD  = 4
PW    = 260
PH    = 220   # initial height; adjusts to tank

MAX_ENTRIES = 200

# Category colours
_CAT_COLORS = {
    "death":  (180,  40,  40),
    "birth":  ( 40, 160,  40),
    "rare":   (180,  70, 240),
    "feed":   ( 40, 120, 220),
    "info":   ( 80,  80, 100),
    "streak": (220, 160,  20),
}


def log_event(cfg: dict, message: str, category: str = "info") -> None:
    """Append a timestamped event to cfg["event_log"]."""
    log: list[dict] = cfg.get("event_log") or []
    ts = datetime.datetime.now().strftime("%H:%M")
    log.append({"t": ts, "m": message, "c": category})
    if len(log) > MAX_ENTRIES:
        log = log[-MAX_ENTRIES:]
    cfg["event_log"] = log


def _bevel(surf: pygame.Surface, r: pygame.Rect, pressed: bool = False) -> None:
    tl = WIN_DARK  if pressed else WIN_LIGHT
    br = WIN_LIGHT if pressed else WIN_DARK
    pygame.draw.line(surf, tl, r.topleft,        (r.right - 1, r.top))
    pygame.draw.line(surf, tl, r.topleft,        (r.left,      r.bottom - 1))
    pygame.draw.line(surf, br, (r.right - 1, r.top),    (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, br, (r.left, r.bottom - 1),  (r.right - 1, r.bottom - 1))


class EventLogPanel:
    """Scrollable Win98-style event log."""

    def __init__(self, font: pygame.font.Font):
        self.font    = font
        self.visible = False
        self._scroll = 0          # scroll offset in lines
        self._rect   = pygame.Rect(0, 0, PW, PH)
        self._close_btn = pygame.Rect(0, 0, 0, 0)
        self._rows: list[pygame.Rect] = []
        self._hover = -1
        # Title-bar gradient cache
        self._title_surf: pygame.Surface | None = None
        self._title_surf_w: int = 0

    def toggle(self) -> None:
        self.visible = not self.visible
        if self.visible:
            self._scroll = 0   # scroll=0 shows newest events; scroll up for older

    def open(self) -> None:
        self.visible = True

    def close(self) -> None:
        self.visible = False

    # ------------------------------------------------------------------
    def handle_event(self, ev: pygame.event.Event) -> bool:
        """Return True if event was consumed."""
        if not self.visible:
            return False
        if ev.type == pygame.MOUSEWHEEL:
            self._scroll = max(0, self._scroll - ev.y)
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
        row_h = fh + 3

        # Panel height: fit inside tank
        header_h = _TB_H + 4
        footer_h = 4
        visible_rows = max(3, (tank_rect.h - header_h - footer_h) // row_h)
        ph = header_h + visible_rows * row_h + footer_h

        # Anchor to right side of tank
        px = tank_rect.right - PW - 2
        py = tank_rect.top + 2
        self._rect = pygame.Rect(px, py, PW, ph)

        log: list[dict] = cfg.get("event_log") or []
        total = len(log)
        max_scroll = max(0, total - visible_rows)
        self._scroll = min(self._scroll, max_scroll)

        # Panel background
        pygame.draw.rect(surface, WIN_GRAY, self._rect)
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
        ts = self.font.render("Event Log", True, WIN_LIGHT)
        surface.blit(ts, (tb.left + 5, tb.top + (tb.h - ts.get_height()) // 2))

        # Close button
        self._close_btn = pygame.Rect(
            self._rect.right - 3 - _TB_H, py + 3, _TB_H, _TB_H)
        pygame.draw.rect(surface, (180, 80, 80), self._close_btn)
        xs = self.font.render("x", True, WIN_LIGHT)
        surface.blit(xs, (
            self._close_btn.left + (self._close_btn.w - xs.get_width()) // 2,
            self._close_btn.top  + (self._close_btn.h - xs.get_height()) // 2))

        # Log rows (newest at bottom: show log[-visible_rows-scroll : -scroll or None])
        surface.set_clip(pygame.Rect(px + 2, py + header_h, PW - 4,
                                     visible_rows * row_h))
        ry = py + header_h
        # Determine which slice to show (newest last)
        start = max(0, total - visible_rows - self._scroll)
        end   = max(0, total - self._scroll)
        visible_entries = log[start:end]
        for entry in visible_entries:
            cat = entry.get("c", "info")
            col = _CAT_COLORS.get(cat, _CAT_COLORS["info"])
            ts_s = self.font.render(entry.get("t", ""), True, (100, 100, 100))
            surface.blit(ts_s, (px + _PAD, ry + 1))
            msg_x = px + _PAD + ts_s.get_width() + 3
            msg_s = self.font.render(entry.get("m", ""), True, col)
            # Clip message to panel width
            surface.blit(msg_s, (msg_x, ry + 1))
            ry += row_h
        surface.set_clip(None)

        # Scroll indicator (right strip)
        if total > visible_rows:
            bar_x   = self._rect.right - 5
            bar_top = py + header_h
            bar_bot = py + header_h + visible_rows * row_h
            bar_h   = bar_bot - bar_top
            frac_top = (total - visible_rows - self._scroll) / max(1, total)
            frac_bot = min(1.0, frac_top + visible_rows / total)
            ind_top = bar_top + int(frac_top * bar_h)
            ind_bot = bar_top + int(frac_bot * bar_h)
            pygame.draw.rect(surface, (160, 160, 160), (bar_x, bar_top, 3, bar_h))
            pygame.draw.rect(surface, WIN_DARK,
                             (bar_x, ind_top, 3, max(4, ind_bot - ind_top)))

        # "Empty" label
        if total == 0:
            empty_s = self.font.render("No events yet.", True, (120, 120, 120))
            ey = py + header_h + (visible_rows * row_h) // 2 - fh // 2
            surface.blit(empty_s, (px + (PW - empty_s.get_width()) // 2, ey))
