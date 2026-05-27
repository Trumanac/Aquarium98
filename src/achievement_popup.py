"""
achievement_popup.py — Win98-style achievement-unlocked notification for Aquarium 98.

Displays a small popup window when an achievement is earned, showing the
achievement name, description, and coin reward.  Multiple unlocks are queued
and shown one at a time.  Each popup auto-dismisses after AUTO_DISMISS seconds,
or immediately when the user clicks OK or the [X] button.

Usage::
    popup = AchievementPopup(font)

    # When an achievement is earned:
    popup.push("Named Them All", "Give every living fish a custom name.", 50)

    # Each frame:
    popup.update(frame_dt)
    result = popup.handle_event(ev)   # returns True to signal event consumed

    # Draw last, so it appears on top of everything:
    popup.draw(surface)
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import NamedTuple

import pygame

# ---------------------------------------------------------------------------
# Win98 palette (matches the rest of the UI)
# ---------------------------------------------------------------------------
WIN_GRAY  = (192, 192, 192)
WIN_LIGHT = (255, 255, 255)
WIN_DARK  = (64,  64,  64)
WIN_MID   = (128, 128, 128)
TITLE_A   = (0,   0,   128)
TITLE_B   = (16, 132, 208)

_TB_H    = 18

_ASSETS_DIR     = Path(__file__).resolve().parent.parent / "assets"
_STAR_ICON_CACHE: dict[int, "pygame.Surface | None"] = {}


def _load_star_icon(size: int) -> "pygame.Surface | None":
    """Load and cache assets/sprites/ui/Star.png scaled to *size* × *size*."""
    if size not in _STAR_ICON_CACHE:
        try:
            raw = pygame.image.load(
                str(_ASSETS_DIR / "sprites" / "ui" / "Star.png")
            ).convert_alpha()
            _STAR_ICON_CACHE[size] = pygame.transform.smoothscale(raw, (size, size))
        except Exception:  # noqa: BLE001
            _STAR_ICON_CACHE[size] = None
    return _STAR_ICON_CACHE[size]
_PW      = 290
_PAD     = 10
_BTN_W   = 70
_BTN_H   = 22
_ICON_SZ = 24

AUTO_DISMISS = 7.0  # seconds before the popup vanishes automatically


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _Entry(NamedTuple):
    name:  str
    desc:  str
    coins: int


def _bevel(surf: pygame.Surface, r: pygame.Rect, pressed: bool = False) -> None:
    tl = WIN_DARK  if pressed else WIN_LIGHT
    br = WIN_LIGHT if pressed else WIN_DARK
    pygame.draw.line(surf, tl, r.topleft,        (r.right - 1, r.top))
    pygame.draw.line(surf, tl, r.topleft,        (r.left,      r.bottom - 1))
    pygame.draw.line(surf, br, (r.right - 1, r.top),    (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, br, (r.left, r.bottom - 1),  (r.right - 1, r.bottom - 1))


def _wrap(font: pygame.font.Font, text: str, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        trial = " ".join(cur + [w])
        if font.size(trial)[0] <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines or [""]


def _draw_star(surf: pygame.Surface, cx: int, cy: int,
               r_outer: float, r_inner: float, color: tuple) -> None:
    """Draw a filled 5-pointed star centred at (cx, cy)."""
    pts: list[tuple[float, float]] = []
    for i in range(10):
        angle = math.pi * i / 5 - math.pi / 2
        r = r_outer if i % 2 == 0 else r_inner
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    pygame.draw.polygon(surf, color, pts)
    pygame.draw.polygon(surf, (0, 0, 0), pts, 1)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class AchievementPopup:
    """Win98 achievement-unlocked notification with an internal queue."""

    def __init__(self, font: pygame.font.Font) -> None:
        self.font       = font
        self._queue:    list[_Entry] = []
        self._timer:    float = 0.0
        self._rect      = pygame.Rect(0, 0, _PW, 10)
        self._ok_btn    = pygame.Rect(0, 0, _BTN_W, _BTN_H)
        self._x_btn     = pygame.Rect(0, 0, 14, 14)
        self._ok_press  = False
        # Title-bar gradient cache
        self._title_surf: pygame.Surface | None = None
        self._title_surf_w: int = 0

    # ------------------------------------------------------------------
    @property
    def visible(self) -> bool:
        return bool(self._queue)

    # ------------------------------------------------------------------
    def push(self, name: str, desc: str, coins: int = 0) -> None:
        """Enqueue an achievement notification."""
        self._queue.append(_Entry(name, desc, coins))
        if len(self._queue) == 1:
            self._timer = AUTO_DISMISS

    # ------------------------------------------------------------------
    def _advance(self) -> None:
        """Dismiss the current entry and show the next one, if any."""
        if self._queue:
            self._queue.pop(0)
        if self._queue:
            self._timer = AUTO_DISMISS
        self._ok_press = False

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        """Call once per frame to advance the auto-dismiss timer."""
        if not self._queue:
            return
        self._timer -= dt
        if self._timer <= 0.0:
            self._advance()

    # ------------------------------------------------------------------
    def handle_event(self, ev: pygame.event.Event) -> bool:
        """Process a pygame event.  Returns True if the event was consumed."""
        if not self._queue:
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self._x_btn.collidepoint(ev.pos):
                self._advance()
                return True
            if self._ok_btn.collidepoint(ev.pos):
                self._ok_press = True
                return True
            # Absorb clicks that land anywhere on the panel
            if self._rect.collidepoint(ev.pos):
                return True
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            if self._ok_press and self._ok_btn.collidepoint(ev.pos):
                self._advance()
                return True
            self._ok_press = False
        elif ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self._advance()
                return True
            if ev.key == pygame.K_ESCAPE:
                self._advance()
                return True
        return False

    # ------------------------------------------------------------------
    def _layout(self, sw: int, sh: int) -> None:
        """Recompute rects for the current top-of-queue entry."""
        entry = self._queue[0]
        fh    = self.font.get_height()
        body_w = _PW - _PAD * 2 - _ICON_SZ - 8

        name_lines = _wrap(self.font, entry.name, body_w)
        desc_lines = _wrap(self.font, entry.desc, body_w)
        coin_lines = 1 if entry.coins > 0 else 0

        n_lines = len(name_lines) + len(desc_lines) + coin_lines
        body_h  = n_lines * (fh + 2) + 4  # small extra padding
        icon_h  = max(_ICON_SZ, n_lines * (fh + 2))

        ph = _TB_H + _PAD + max(body_h, icon_h) + _PAD + _BTN_H + _PAD

        self._rect  = pygame.Rect((sw - _PW) // 2, (sh - ph) // 2, _PW, ph)
        r           = self._rect
        self._ok_btn = pygame.Rect(
            r.centerx - _BTN_W // 2,
            r.bottom - _PAD - _BTN_H,
            _BTN_W, _BTN_H,
        )
        self._x_btn = pygame.Rect(r.right - 3 - 14, r.top + 2, 14, 14)

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        if not self._queue:
            return

        self._layout(*surface.get_size())
        entry = self._queue[0]
        r     = self._rect
        fnt   = self.font
        fh    = fnt.get_height()

        # ── Panel background + outer bevel ──────────────────────────
        pygame.draw.rect(surface, WIN_GRAY, r)
        _bevel(surface, r)

        # ── Title bar gradient (cached per width) ───────────────────────
        tb = pygame.Rect(r.left + 3, r.top + 2, r.w - 6, _TB_H)
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
        ts = fnt.render("Achievement Unlocked!", True, WIN_LIGHT)
        surface.blit(ts, (tb.left + 4, tb.top + (tb.h - ts.get_height()) // 2))

        # ── [X] close button ─────────────────────────────────────────
        pygame.draw.rect(surface, WIN_GRAY, self._x_btn)
        _bevel(surface, self._x_btn)
        xs = fnt.render("x", True, (0, 0, 0))
        surface.blit(xs, (self._x_btn.left + (self._x_btn.w - xs.get_width()) // 2,
                           self._x_btn.top  + (self._x_btn.h - xs.get_height()) // 2))

        # ── Star icon ────────────────────────────────────────────────
        body_top  = r.top + _TB_H + _PAD
        icon_r    = pygame.Rect(r.left + _PAD, body_top, _ICON_SZ, _ICON_SZ)
        star_surf = _load_star_icon(_ICON_SZ)
        if star_surf:
            surface.blit(star_surf, icon_r.topleft)
        else:
            pygame.draw.rect(surface, (255, 220, 40), icon_r)
            _bevel(surface, icon_r)
            _draw_star(surface, icon_r.centerx, icon_r.centery, 9.0, 4.5, (255, 200, 0))

        # ── Text block ───────────────────────────────────────────────
        tx = r.left + _PAD + _ICON_SZ + 8
        ty = body_top
        body_w = _PW - _PAD - _ICON_SZ - 8 - _PAD

        # Achievement name — dark blue, like a section heading
        for ln in _wrap(fnt, entry.name, body_w):
            ns = fnt.render(ln, True, TITLE_A)
            surface.blit(ns, (tx, ty))
            ty += fh + 2

        # Description — black
        for ln in _wrap(fnt, entry.desc, body_w):
            ds = fnt.render(ln, True, (0, 0, 0))
            surface.blit(ds, (tx, ty))
            ty += fh + 2

        # Coin reward — green
        if entry.coins > 0:
            rs = fnt.render(f"+{entry.coins} coins", True, (0, 128, 0))
            surface.blit(rs, (tx, ty + 2))

        # ── Auto-dismiss progress bar ─────────────────────────────────
        bar_r = pygame.Rect(r.left + _PAD, self._ok_btn.top - 5, r.w - _PAD * 2, 3)
        pygame.draw.rect(surface, WIN_MID, bar_r)
        filled = max(0, int(bar_r.w * (self._timer / AUTO_DISMISS)))
        if filled > 0:
            pygame.draw.rect(surface, TITLE_B,
                             pygame.Rect(bar_r.left, bar_r.top, filled, bar_r.h))

        # ── OK button ────────────────────────────────────────────────
        pygame.draw.rect(surface, WIN_GRAY, self._ok_btn)
        _bevel(surface, self._ok_btn, self._ok_press)
        ok_s = fnt.render("OK", True, (0, 0, 0))
        ox = self._ok_btn.left + (self._ok_btn.w - ok_s.get_width()) // 2
        oy = self._ok_btn.top  + (self._ok_btn.h - ok_s.get_height()) // 2
        if self._ok_press:
            ox += 1; oy += 1
        surface.blit(ok_s, (ox, oy))


# ---------------------------------------------------------------------------
# Update-available notification banner
# ---------------------------------------------------------------------------

_UB_W       = 260    # banner width in pixels
_UB_DISMISS = 10.0   # seconds before auto-dismiss


class UpdateBanner:
    """Non-modal Win98 banner shown once per session when a new version is ready.

    The banner appears at the top-centre of the screen and auto-dismisses after
    ``_UB_DISMISS`` seconds.  Clicking ``[x]`` closes it immediately.  All
    other events are *not* consumed so the aquarium stays fully interactive.
    """

    def __init__(self, font: "pygame.font.Font") -> None:
        self.font     = font
        self._version = ""
        self._timer   = 0.0
        self._visible = False
        self._rect    = pygame.Rect(0, 0, 0, 0)
        self._x_btn   = pygame.Rect(0, 0, 14, 14)
        # Title-bar gradient cache
        self._title_surf: pygame.Surface | None = None
        self._title_surf_w: int = 0

    # ------------------------------------------------------------------
    @property
    def visible(self) -> bool:
        return self._visible

    # ------------------------------------------------------------------
    def show(self, version: str) -> None:
        """Display the banner for *version* (e.g. ``'1.2.0'``)."""
        self._version = version
        self._timer   = _UB_DISMISS
        self._visible = True

    def close(self) -> None:
        self._visible = False

    # ------------------------------------------------------------------
    def update(self, dt: float) -> None:
        if not self._visible:
            return
        self._timer -= dt
        if self._timer <= 0.0:
            self._visible = False

    # ------------------------------------------------------------------
    def handle_event(self, ev: "pygame.event.Event") -> bool:
        """Return ``True`` only if the ``[x]`` button was clicked.

        Everything else passes through so the banner is non-modal.
        """
        if not self._visible:
            return False
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self._x_btn.collidepoint(ev.pos):
                self._visible = False
                return True
        return False

    # ------------------------------------------------------------------
    def draw(self, surface: "pygame.Surface") -> None:
        if not self._visible:
            return

        sw, _sh  = surface.get_size()
        fh       = self.font.get_height()
        bw       = min(_UB_W, sw - 20)
        body_w   = bw - _PAD * 2

        hint_lines = _wrap(self.font, "Open Settings to download and install.", body_w)
        ph = _TB_H + _PAD + fh + 4 + len(hint_lines) * (fh + 2) + _PAD + 4

        px = (sw - bw) // 2
        py = 6
        r  = pygame.Rect(px, py, bw, ph)
        self._rect  = r
        self._x_btn = pygame.Rect(r.right - 3 - 14, r.top + 2, 14, 14)

        # ── Panel background + bevel ─────────────────────────────────
        pygame.draw.rect(surface, WIN_GRAY, r)
        _bevel(surface, r)

        # ── Title bar gradient (cached per width) ───────────────────────
        tb = pygame.Rect(r.left + 3, r.top + 2, r.w - 6, _TB_H)
        if self._title_surf is None or self._title_surf_w != tb.w:
            self._title_surf_w = tb.w
            self._title_surf = pygame.Surface((tb.w, tb.h))
            for i in range(tb.h):
                t = i / max(1, tb.h - 1)
                c = (
                    int(TITLE_A[0] + (TITLE_B[0] - TITLE_A[0]) * t),
                    int(TITLE_A[1] + (TITLE_B[1] - TITLE_A[1]) * t),
                    int(TITLE_A[2] + (TITLE_B[2] - TITLE_A[2]) * t),
                )
                pygame.draw.line(self._title_surf, c, (0, i), (tb.w - 1, i))
        surface.blit(self._title_surf, tb.topleft)
        ts = self.font.render("Update Available", True, WIN_LIGHT)
        surface.blit(ts, (tb.left + 4, tb.top + (tb.h - ts.get_height()) // 2))

        # ── [x] close button ─────────────────────────────────────────
        pygame.draw.rect(surface, WIN_GRAY, self._x_btn)
        _bevel(surface, self._x_btn)
        xs = self.font.render("x", True, (0, 0, 0))
        surface.blit(xs, (
            self._x_btn.left + (self._x_btn.w - xs.get_width()) // 2,
            self._x_btn.top  + (self._x_btn.h - xs.get_height()) // 2,
        ))

        # ── Body text ────────────────────────────────────────────────
        ty = r.top + _TB_H + _PAD
        v_surf = self.font.render(f"v{self._version} is available!", True, TITLE_A)
        surface.blit(v_surf, (r.left + _PAD, ty))
        ty += fh + 4
        for line in hint_lines:
            hs = self.font.render(line, True, (0, 0, 0))
            surface.blit(hs, (r.left + _PAD, ty))
            ty += fh + 2

        # ── Auto-dismiss progress bar ─────────────────────────────────
        bar_r = pygame.Rect(r.left + _PAD, r.bottom - 5, r.w - _PAD * 2, 3)
        pygame.draw.rect(surface, WIN_MID, bar_r)
        filled = max(0, int(bar_r.w * (self._timer / _UB_DISMISS)))
        if filled > 0:
            pygame.draw.rect(surface, TITLE_B,
                             pygame.Rect(bar_r.left, bar_r.top, filled, bar_r.h))
