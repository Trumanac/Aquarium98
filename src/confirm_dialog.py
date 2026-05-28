"""
confirm_dialog.py — Win98-style yes/no confirmation popup.

Usage::
    dlg = ConfirmDialog(font)
    dlg.open("Reset Tank?",
             "All fish will be lost and the tank restarted.")
    # each frame:
    result = dlg.handle_event(ev)  # returns "yes", "no", or None
    dlg.draw(surface)
"""
from __future__ import annotations

from pathlib import Path

import pygame

WIN_GRAY  = (192, 192, 192)
WIN_LIGHT = (255, 255, 255)
WIN_DARK  = (64,  64,  64)
WIN_MID   = (128, 128, 128)
TITLE_A   = (0,   0,   128)
TITLE_B   = (16, 132, 208)

_TB_H = 18
_PW   = 310
_PAD  = 10
_BTN_W = 70
_BTN_H = 22


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


class ConfirmDialog:
    """Blocking-style Win98 confirm dialog.  Returns "yes"/"no" from handle_event."""

    def __init__(self, font: pygame.font.Font):
        self.font    = font
        self.visible = False
        self._title  = ""
        self._body   = ""
        self._body_lines: list[str] = []
        self._rect   = pygame.Rect(0, 0, _PW, 120)
        self._yes_btn = pygame.Rect(0, 0, _BTN_W, _BTN_H)
        self._no_btn  = pygame.Rect(0, 0, _BTN_W, _BTN_H)
        self._yes_press = False
        self._no_press  = False
        self._title_surf: pygame.Surface | None = None
        self._title_surf_w: int = 0

    def open(self, title: str, body: str, screen_w: int, screen_h: int) -> None:
        self._title = title
        self._body  = body
        fh = self.font.get_height()
        self._body_lines = _wrap(self.font, body, _PW - _PAD * 2 - 32)
        body_h = len(self._body_lines) * (fh + 2)
        ph = _TB_H + _PAD * 3 + 24 + body_h + _BTN_H + _PAD
        self._rect = pygame.Rect(
            (screen_w - _PW) // 2,
            (screen_h - ph) // 2,
            _PW, ph
        )
        r = self._rect
        self._yes_btn = pygame.Rect(
            r.right - _PAD - _BTN_W * 2 - 8,
            r.bottom - _PAD - _BTN_H,
            _BTN_W, _BTN_H
        )
        self._no_btn = pygame.Rect(
            r.right - _PAD - _BTN_W,
            r.bottom - _PAD - _BTN_H,
            _BTN_W, _BTN_H
        )
        self._yes_press = False
        self._no_press  = False
        self.visible = True

    def close(self) -> None:
        self.visible = False

    def handle_event(self, ev: pygame.event.Event) -> str | None:
        if not self.visible:
            return None
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self._yes_btn.inflate(8, 8).collidepoint(ev.pos):
                self._yes_press = True
            elif self._no_btn.inflate(8, 8).collidepoint(ev.pos):
                self._no_press = True
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            if self._yes_press and self._yes_btn.inflate(8, 8).collidepoint(ev.pos):
                self.close()
                return "yes"
            if self._no_press and self._no_btn.inflate(8, 8).collidepoint(ev.pos):
                self.close()
                return "no"
            self._yes_press = False
            self._no_press  = False
        elif ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_RETURN, pygame.K_y):
                self.close()
                return "yes"
            if ev.key in (pygame.K_ESCAPE, pygame.K_n):
                self.close()
                return "no"
        return None

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        r   = self._rect
        fnt = self.font
        fh  = fnt.get_height()

        # Panel background + bevel
        pygame.draw.rect(surface, WIN_GRAY, r)
        _bevel(surface, r)

        # Title bar gradient (cached per width)
        tb = pygame.Rect(r.left + 3, r.top + 3, r.w - 6, _TB_H)
        if self._title_surf is None or self._title_surf_w != tb.w:
            self._title_surf = pygame.Surface((tb.w, tb.h))
            for i in range(tb.h):
                t = i / max(1, tb.h - 1)
                c = (int(TITLE_A[0] + (TITLE_B[0] - TITLE_A[0]) * t),
                     int(TITLE_A[1] + (TITLE_B[1] - TITLE_A[1]) * t),
                     int(TITLE_A[2] + (TITLE_B[2] - TITLE_A[2]) * t))
                pygame.draw.line(self._title_surf, c, (0, i), (tb.w - 1, i))
            self._title_surf_w = tb.w
        surface.blit(self._title_surf, (tb.left, tb.top))
        ts = fnt.render(self._title, True, WIN_LIGHT)
        surface.blit(ts, (tb.left + 5, tb.top + (tb.h - ts.get_height()) // 2))

        # Warning icon area
        icon_r = pygame.Rect(r.left + _PAD, r.top + _TB_H + 6 + _PAD, 24, 24)
        pygame.draw.rect(surface, (255, 220, 40), icon_r)
        _bevel(surface, icon_r)
        warn_s = fnt.render("!", True, (0, 0, 0))
        surface.blit(warn_s, (icon_r.left + (icon_r.w - warn_s.get_width()) // 2,
                               icon_r.top  + (icon_r.h - warn_s.get_height()) // 2))

        # Body text
        tx = icon_r.right + 8
        ty = icon_r.top
        for ln in self._body_lines:
            ls = fnt.render(ln, True, (0, 0, 0))
            surface.blit(ls, (tx, ty))
            ty += fh + 2

        # Buttons
        for btn, label, pressed in (
            (self._yes_btn, "Yes", self._yes_press),
            (self._no_btn,  "No",  self._no_press),
        ):
            pygame.draw.rect(surface, WIN_GRAY, btn)
            _bevel(surface, btn, pressed)
            ls = fnt.render(label, True, (0, 0, 0))
            surface.blit(ls, (btn.left + (btn.w - ls.get_width()) // 2,
                               btn.top  + (btn.h - ls.get_height()) // 2))


# ---------------------------------------------------------------------------

class FullResetDialog:
    """Dialog that requires the user to type 'RESET' before wiping all data.

    Returns 'confirmed' from handle_event when the user types RESET and
    clicks OK (or presses Enter), or 'cancel' on Cancel / Escape.
    """

    _PROMPT = "Type  RESET  (all caps) to permanently erase all progress:"
    _PW     = 360
    _INP_W  = 180

    def __init__(self, font: pygame.font.Font) -> None:
        self.font    = font
        self.visible = False
        self._text   = ""
        self._rect   = pygame.Rect(0, 0, self._PW, 140)
        self._ok_btn  = pygame.Rect(0, 0, _BTN_W, _BTN_H)
        self._no_btn  = pygame.Rect(0, 0, _BTN_W, _BTN_H)
        self._ok_press  = False
        self._no_press  = False
        self._input_rect = pygame.Rect(0, 0, self._INP_W, 20)
        self._cursor_blink = 0.0
        self._cursor_vis   = True
        self._title_surf: pygame.Surface | None = None
        self._title_surf_w: int = 0
        self._prompt_lines: list[str] = []

    def open(self, screen_w: int, screen_h: int) -> None:
        self._text = ""
        fh = self.font.get_height()
        self._prompt_lines = _wrap(self.font, self._PROMPT, self._PW - _PAD * 2 - 32)
        content_h = max(24, len(self._prompt_lines) * (fh + 2))
        ph = _TB_H + _PAD * 2 + content_h + 8 + 22 + _PAD + _BTN_H + _PAD
        self._rect = pygame.Rect(
            (screen_w - self._PW) // 2,
            (screen_h - ph) // 2,
            self._PW, ph,
        )
        r = self._rect
        inp_y = r.top + _TB_H + _PAD + content_h + 6
        self._input_rect = pygame.Rect(
            r.left + (r.w - self._INP_W) // 2, inp_y,
            self._INP_W, 22,
        )
        self._ok_btn = pygame.Rect(
            r.right - _PAD - _BTN_W * 2 - 8,
            r.bottom - _PAD - _BTN_H,
            _BTN_W, _BTN_H,
        )
        self._no_btn = pygame.Rect(
            r.right - _PAD - _BTN_W,
            r.bottom - _PAD - _BTN_H,
            _BTN_W, _BTN_H,
        )
        self._ok_press  = False
        self._no_press  = False
        self._cursor_blink = 0.0
        self._cursor_vis   = True
        self.visible = True

    def close(self) -> None:
        self.visible = False
        self._text   = ""

    def update(self, dt: float) -> None:
        if not self.visible:
            return
        self._cursor_blink += dt
        if self._cursor_blink >= 0.5:
            self._cursor_blink = 0.0
            self._cursor_vis = not self._cursor_vis

    def handle_event(self, ev: pygame.event.Event) -> str | None:
        if not self.visible:
            return None
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.close()
                return "cancel"
            elif ev.key == pygame.K_RETURN:
                if self._text == "RESET":
                    self.close()
                    return "confirmed"
            elif ev.key == pygame.K_BACKSPACE:
                self._text = self._text[:-1]
            else:
                ch = ev.unicode
                if ch and len(self._text) < 8:
                    self._text += ch
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self._ok_btn.collidepoint(ev.pos):
                self._ok_press = True
            elif self._no_btn.collidepoint(ev.pos):
                self._no_press = True
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            if self._ok_press and self._ok_btn.collidepoint(ev.pos):
                self._ok_press = False
                if self._text == "RESET":
                    self.close()
                    return "confirmed"
            if self._no_press and self._no_btn.collidepoint(ev.pos):
                self.close()
                return "cancel"
            self._ok_press = False
            self._no_press = False
        return None

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        r   = self._rect
        fnt = self.font
        fh  = fnt.get_height()

        # Dim veil
        veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 100))
        surface.blit(veil, (0, 0))

        # Panel
        pygame.draw.rect(surface, WIN_GRAY, r)
        _bevel(surface, r)

        # Title bar (cached per width)
        tb = pygame.Rect(r.left + 3, r.top + 3, r.w - 6, _TB_H)
        if self._title_surf is None or self._title_surf_w != tb.w:
            self._title_surf = pygame.Surface((tb.w, tb.h))
            for i in range(tb.h):
                t = i / max(1, tb.h - 1)
                c = (int(TITLE_A[0] + (TITLE_B[0] - TITLE_A[0]) * t),
                     int(TITLE_A[1] + (TITLE_B[1] - TITLE_A[1]) * t),
                     int(TITLE_A[2] + (TITLE_B[2] - TITLE_A[2]) * t))
                pygame.draw.line(self._title_surf, c, (0, i), (tb.w - 1, i))
            self._title_surf_w = tb.w
        surface.blit(self._title_surf, (tb.left, tb.top))
        ts = fnt.render("Full Reset — Erase All Data", True, WIN_LIGHT)
        surface.blit(ts, (tb.left + 5, tb.top + (tb.h - ts.get_height()) // 2))

        # Warning icon
        icon_r = pygame.Rect(r.left + _PAD, r.top + _TB_H + _PAD, 24, 24)
        pygame.draw.rect(surface, (220, 60, 60), icon_r)
        _bevel(surface, icon_r)
        ws = fnt.render("!", True, WIN_LIGHT)
        surface.blit(ws, (icon_r.left + (icon_r.w - ws.get_width()) // 2,
                          icon_r.top  + (icon_r.h - ws.get_height()) // 2))

        # Prompt text (pre-wrapped in open())
        lines = self._prompt_lines
        ty = icon_r.top
        for ln in lines:
            ls = fnt.render(ln, True, (140, 20, 20))
            surface.blit(ls, (icon_r.right + 8, ty))
            ty += fh + 2

        # Input box (sunken)
        inp = self._input_rect
        pygame.draw.rect(surface, WIN_LIGHT, inp)
        pygame.draw.line(surface, WIN_DARK,  inp.topleft, (inp.right - 1, inp.top))
        pygame.draw.line(surface, WIN_DARK,  inp.topleft, (inp.left, inp.bottom - 1))
        pygame.draw.line(surface, WIN_LIGHT, (inp.right - 1, inp.top),
                         (inp.right - 1, inp.bottom - 1))
        pygame.draw.line(surface, WIN_LIGHT, (inp.left, inp.bottom - 1),
                         (inp.right - 1, inp.bottom - 1))
        # Text in box
        ok_color = (0, 140, 0) if self._text == "RESET" else (180, 0, 0)
        ts2 = fnt.render(self._text, True, ok_color)
        surface.blit(ts2, (inp.left + 4, inp.top + (inp.h - ts2.get_height()) // 2))
        # Blinking cursor
        if self._cursor_vis:
            cx = inp.left + 4 + ts2.get_width() + 1
            pygame.draw.line(surface, (0, 0, 0),
                             (cx, inp.top + 3), (cx, inp.bottom - 3))

        # OK / Cancel buttons
        ok_enabled = self._text == "RESET"
        for btn, label, pressed, enabled in (
            (self._ok_btn,  "OK",     self._ok_press,  ok_enabled),
            (self._no_btn,  "Cancel", self._no_press,  True),
        ):
            col = WIN_GRAY if enabled else (210, 210, 210)
            pygame.draw.rect(surface, col, btn)
            _bevel(surface, btn, pressed)
            lc = (0, 0, 0) if enabled else WIN_MID
            ls = fnt.render(label, True, lc)
            surface.blit(ls, (btn.left + (btn.w - ls.get_width()) // 2,
                               btn.top  + (btn.h - ls.get_height()) // 2))


# ---------------------------------------------------------------------------

class AboutDialog:
    """Win98-style About box for Aquarium 98.

    Usage::
        dlg = AboutDialog(font)
        # each frame:
        dlg.handle_event(ev)   # closes itself on OK / Enter / Escape
        dlg.draw(surface)
    """

    _PW = 300
    _ICON_PATH = str(Path(__file__).resolve().parent.parent / "assets" / "icon" / "icon.png")
    _ICON_SIZE = 32

    def __init__(self, font: pygame.font.Font, app_version: str = "1.0.0") -> None:
        self.font    = font
        self._app_version = app_version
        self.visible = False
        self._rect   = pygame.Rect(0, 0, self._PW, 170)
        self._ok_btn = pygame.Rect(0, 0, _BTN_W, _BTN_H)
        self._ok_press = False
        self._icon: pygame.Surface | None = None
        self._icon_loaded = False
        self._title_surf: pygame.Surface | None = None
        self._title_surf_w: int = 0

    def _ensure_icon(self) -> None:
        if self._icon_loaded:
            return
        self._icon_loaded = True
        try:
            raw = pygame.image.load(self._ICON_PATH).convert_alpha()
            self._icon = pygame.transform.smoothscale(
                raw, (self._ICON_SIZE, self._ICON_SIZE)
            )
        except Exception:
            self._icon = None

    def open(self, screen_w: int, screen_h: int) -> None:
        self._ensure_icon()
        fh  = self.font.get_height()
        row = fh + 4
        content_h = max(self._ICON_SIZE, row * 5)
        ph = (_TB_H + 6 + _PAD          # top: title bar + gap + padding
              + content_h               # icon + text rows
              + _PAD + 1 + _PAD         # separator gap + line + gap
              + fh                      # copyright line
              + _PAD + _BTN_H + _PAD)   # bottom padding + button + padding
        self._rect = pygame.Rect(
            (screen_w - self._PW) // 2,
            (screen_h - ph) // 2,
            self._PW, ph,
        )
        r = self._rect
        self._ok_btn = pygame.Rect(
            r.left + (r.w - _BTN_W) // 2,
            r.bottom - _PAD - _BTN_H,
            _BTN_W, _BTN_H,
        )
        self._ok_press = False
        self.visible   = True

    def close(self) -> None:
        self.visible = False

    def handle_event(self, ev: pygame.event.Event) -> None:
        if not self.visible:
            return
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_ESCAPE):
            self.close()
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self._ok_btn.collidepoint(ev.pos):
                self._ok_press = True
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            if self._ok_press and self._ok_btn.collidepoint(ev.pos):
                self.close()
            self._ok_press = False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        self._ensure_icon()
        r   = self._rect
        fnt = self.font
        fh  = fnt.get_height()
        row = fh + 4

        # Dim veil
        veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 100))
        surface.blit(veil, (0, 0))

        # Panel background + bevel
        pygame.draw.rect(surface, WIN_GRAY, r)
        _bevel(surface, r)

        # Title bar gradient (cached per width)
        tb = pygame.Rect(r.left + 3, r.top + 3, r.w - 6, _TB_H)
        if self._title_surf is None or self._title_surf_w != tb.w:
            self._title_surf = pygame.Surface((tb.w, tb.h))
            for i in range(tb.h):
                t = i / max(1, tb.h - 1)
                c = (int(TITLE_A[0] + (TITLE_B[0] - TITLE_A[0]) * t),
                     int(TITLE_A[1] + (TITLE_B[1] - TITLE_A[1]) * t),
                     int(TITLE_A[2] + (TITLE_B[2] - TITLE_A[2]) * t))
                pygame.draw.line(self._title_surf, c, (0, i), (tb.w - 1, i))
            self._title_surf_w = tb.w
        surface.blit(self._title_surf, (tb.left, tb.top))
        ts = fnt.render("About Aquarium 98", True, WIN_LIGHT)
        surface.blit(ts, (tb.left + 5, tb.top + (tb.h - ts.get_height()) // 2))

        # Content area starts below title bar
        content_y = r.top + _TB_H + 6 + _PAD
        content_h = max(self._ICON_SIZE, row * 4)

        # App icon (left of text)
        ix = r.left + _PAD
        if self._icon:
            surface.blit(self._icon, (ix, content_y))
        else:
            # Fallback: coloured square
            fb = pygame.Rect(ix, content_y, self._ICON_SIZE, self._ICON_SIZE)
            pygame.draw.rect(surface, (0, 80, 180), fb)

        # Text block (right of icon)
        tx = ix + self._ICON_SIZE + 10
        ty = content_y + (content_h - row * 5) // 2
        for line in ("Aquarium 98", f"Version {self._app_version}", "A living desktop companion.",
                     "By trumanac", "superbirdy.itch.io"):
            if line.startswith("By ") or line.endswith(".itch.io"):
                col = (0, 0, 180)
            else:
                col = (0, 0, 0)
            ls = fnt.render(line, True, col)
            surface.blit(ls, (tx, ty))
            ty += row

        # Separator line
        sep_y = content_y + content_h + _PAD
        pygame.draw.line(surface, WIN_DARK,
                         (r.left + _PAD, sep_y), (r.right - _PAD, sep_y))
        pygame.draw.line(surface, WIN_LIGHT,
                         (r.left + _PAD, sep_y + 1), (r.right - _PAD, sep_y + 1))

        # Copyright line (centred)
        copy_s = fnt.render("\xa9 2026 trumanac \u2014 github.com/trumanac", True, (0, 0, 0))
        surface.blit(copy_s,
                     (r.left + (r.w - copy_s.get_width()) // 2,
                      sep_y + 4))

        # OK button
        pygame.draw.rect(surface, WIN_GRAY, self._ok_btn)
        _bevel(surface, self._ok_btn, self._ok_press)
        ok_s = fnt.render("OK", True, (0, 0, 0))
        surface.blit(ok_s, (self._ok_btn.left + (self._ok_btn.w - ok_s.get_width()) // 2,
                             self._ok_btn.top  + (self._ok_btn.h - ok_s.get_height()) // 2))


# ---------------------------------------------------------------------------
# InfoDialog — simple read-only message box with OK
# ---------------------------------------------------------------------------

class InfoDialog:
    """Win98-style informational message box with a single OK button.

    Usage::
        dlg = InfoDialog(font)
        dlg.open("Title", "Message text.", screen_w, screen_h)
        # each frame:
        result = dlg.handle_event(ev)  # returns "ok" or None
        dlg.draw(surface)
    """

    _PW = 280

    def __init__(self, font: pygame.font.Font) -> None:
        self.font    = font
        self.visible = False
        self._title  = ""
        self._body_lines: list[str] = []
        self._rect   = pygame.Rect(0, 0, self._PW, 100)
        self._ok_btn = pygame.Rect(0, 0, _BTN_W, _BTN_H)
        self._ok_press = False
        self._title_surf: pygame.Surface | None = None
        self._title_surf_w: int = 0

    def open(self, title: str, body: str, screen_w: int, screen_h: int) -> None:
        self._title = title
        fh = self.font.get_height()
        self._body_lines = _wrap(self.font, body, self._PW - _PAD * 2)
        body_h = len(self._body_lines) * (fh + 2)
        ph = _TB_H + _PAD * 2 + body_h + _PAD + _BTN_H + _PAD
        self._rect = pygame.Rect(
            (screen_w - self._PW) // 2,
            (screen_h - ph) // 2,
            self._PW, ph,
        )
        r = self._rect
        self._ok_btn = pygame.Rect(
            r.left + (r.w - _BTN_W) // 2,
            r.bottom - _PAD - _BTN_H,
            _BTN_W, _BTN_H,
        )
        self._ok_press = False
        self.visible   = True

    def close(self) -> None:
        self.visible = False

    def handle_event(self, ev: pygame.event.Event) -> str | None:
        if not self.visible:
            return None
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_ESCAPE):
            self.close()
            return "ok"
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self._ok_btn.inflate(8, 8).collidepoint(ev.pos):
                self._ok_press = True
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            if self._ok_press and self._ok_btn.inflate(8, 8).collidepoint(ev.pos):
                self.close()
                return "ok"
            self._ok_press = False
        return None

    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible:
            return
        r   = self._rect
        fnt = self.font
        fh  = fnt.get_height()

        # Dim veil
        veil = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        veil.fill((0, 0, 0, 80))
        surface.blit(veil, (0, 0))

        # Panel background + bevel
        pygame.draw.rect(surface, WIN_GRAY, r)
        _bevel(surface, r)

        # Title bar (cached per width)
        tb = pygame.Rect(r.left + 3, r.top + 3, r.w - 6, _TB_H)
        if self._title_surf is None or self._title_surf_w != tb.w:
            self._title_surf = pygame.Surface((tb.w, tb.h))
            for i in range(tb.h):
                t = i / max(1, tb.h - 1)
                c = (int(TITLE_A[0] + (TITLE_B[0] - TITLE_A[0]) * t),
                     int(TITLE_A[1] + (TITLE_B[1] - TITLE_A[1]) * t),
                     int(TITLE_A[2] + (TITLE_B[2] - TITLE_A[2]) * t))
                pygame.draw.line(self._title_surf, c, (0, i), (tb.w - 1, i))
            self._title_surf_w = tb.w
        surface.blit(self._title_surf, (tb.left, tb.top))
        ts = fnt.render(self._title, True, WIN_LIGHT)
        surface.blit(ts, (tb.left + 5, tb.top + (tb.h - ts.get_height()) // 2))

        # Body text (centred)
        ty = r.top + _TB_H + _PAD
        for ln in self._body_lines:
            ls = fnt.render(ln, True, (0, 0, 0))
            surface.blit(ls, (r.left + (r.w - ls.get_width()) // 2, ty))
            ty += fh + 2

        # OK button
        pygame.draw.rect(surface, WIN_GRAY, self._ok_btn)
        _bevel(surface, self._ok_btn, self._ok_press)
        ok_s = fnt.render("OK", True, (0, 0, 0))
        surface.blit(ok_s, (self._ok_btn.left + (self._ok_btn.w - ok_s.get_width()) // 2,
                             self._ok_btn.top  + (self._ok_btn.h - ok_s.get_height()) // 2))


# ---------------------------------------------------------------------------
# CrashDialog — fatal-error reporter
# ---------------------------------------------------------------------------

class CrashDialog:
    """Win98-style crash-report popup.

    Shows a brief error summary, full traceback, and a *Copy Details* button
    that copies the report to the clipboard.  Also displays the log file path.

    Attempts to open its own minimal pygame window so it works even when the
    main window has been destroyed.  Falls back silently on any further error.

    Usage::
        dlg = CrashDialog(traceback_text, log_path)
        dlg.run()  # blocks until OK
    """

    _W, _H = 480, 340

    def __init__(self, tb_text: str, log_path: str) -> None:
        self._tb   = tb_text
        self._log  = log_path

    def run(self) -> None:
        """Open a blocking window, returning when the user dismisses it."""
        try:
            self._run()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    def _run(self) -> None:
        import textwrap

        if not pygame.get_init():
            pygame.init()
        pygame.display.set_mode((self._W, self._H))
        pygame.display.set_caption("Aquarium 98 \u2014 Application Error")
        screen = pygame.display.get_surface()
        try:
            font = pygame.font.SysFont("Tahoma", 11)
        except Exception:  # noqa: BLE001
            font = pygame.font.Font(None, 14)

        fh  = font.get_height()
        pad = 8
        btn_w, btn_h = 90, 22

        ok_rect   = pygame.Rect(self._W - pad - btn_w,     self._H - pad - btn_h, btn_w, btn_h)
        copy_rect = pygame.Rect(self._W - pad*2 - btn_w*2, self._H - pad - btn_h, btn_w, btn_h)

        copy_available = True
        try:
            import pyperclip as _pc  # noqa: F401
        except ImportError:
            copy_available = False

        # Wrap traceback text for display
        lines: list[str] = []
        for raw_line in self._tb.splitlines():
            lines.extend(textwrap.wrap(raw_line or " ", width=72) or [" "])

        detail_text = (
            f"Aquarium 98 crashed unexpectedly.\n\n"
            f"{self._tb}\n"
            f"Log file: {self._log}"
        )

        scroll_y   = 0
        ok_press   = False
        copy_press = False
        running    = True
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                    running = False
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if ok_rect.collidepoint(ev.pos):
                        ok_press = True
                    if copy_rect.collidepoint(ev.pos) and copy_available:
                        copy_press = True
                elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                    if ok_press and ok_rect.collidepoint(ev.pos):
                        running = False
                    if copy_press and copy_rect.collidepoint(ev.pos) and copy_available:
                        try:
                            import pyperclip
                            pyperclip.copy(detail_text)
                        except Exception:  # noqa: BLE001
                            pass
                    ok_press = copy_press = False
                elif ev.type == pygame.MOUSEWHEEL:
                    max_scroll = max(0, len(lines) * (fh + 1) - (self._H - 130))
                    scroll_y   = max(0, min(max_scroll, scroll_y - ev.y * (fh + 1) * 3))

            screen.fill((192, 192, 192))

            # Title bar
            tb_r = pygame.Rect(3, 3, self._W - 6, 20)
            for i in range(tb_r.h):
                blue = int(128 + 80 * (1 - i / max(1, tb_r.h - 1)))
                pygame.draw.line(screen, (0, 0, blue),
                                 (tb_r.left, tb_r.top + i),
                                 (tb_r.right - 1, tb_r.top + i))
            ts = font.render("Aquarium 98 \u2014 Application Error", True, (255, 255, 255))
            screen.blit(ts, (tb_r.left + 5, tb_r.top + (tb_r.h - ts.get_height()) // 2))

            # Error message + log path
            msg_y = tb_r.bottom + pad
            msg_s = font.render("Aquarium 98 encountered an error and needs to close.", True, (0, 0, 0))
            screen.blit(msg_s, (pad, msg_y))
            msg_y += fh + 4
            log_s = font.render(f"Log: {self._log}", True, (0, 0, 100))
            screen.blit(log_s, (pad, msg_y))
            msg_y += fh + 8

            # Traceback text area (sunken box)
            box_h = self._H - msg_y - btn_h - pad * 3
            box   = pygame.Rect(pad, msg_y, self._W - pad * 2, box_h)
            pygame.draw.rect(screen, (255, 255, 255), box)
            pygame.draw.rect(screen, (128, 128, 128), box, 1)
            inner = box.inflate(-4, -4)
            text_area = pygame.Surface((inner.w, inner.h))
            text_area.fill((255, 255, 255))
            for i, line in enumerate(lines):
                y_pos = i * (fh + 1) - scroll_y
                if -fh <= y_pos <= inner.h:
                    ls = font.render(line, True, (30, 30, 30))
                    text_area.blit(ls, (2, y_pos))
            screen.blit(text_area, (inner.left, inner.top))

            # Buttons
            if copy_available:
                pygame.draw.rect(screen, (192, 192, 192), copy_rect)
                edge = (128, 128, 128) if copy_press else (255, 255, 255)
                pygame.draw.rect(screen, edge, copy_rect, 1)
                cs = font.render("Copy Details", True, (0, 0, 0))
                screen.blit(cs, (copy_rect.left + (copy_rect.w - cs.get_width()) // 2,
                                 copy_rect.top  + (copy_rect.h - cs.get_height()) // 2))

            pygame.draw.rect(screen, (192, 192, 192), ok_rect)
            edge = (128, 128, 128) if ok_press else (255, 255, 255)
            pygame.draw.rect(screen, edge, ok_rect, 1)
            ok_s2 = font.render("OK", True, (0, 0, 0))
            screen.blit(ok_s2, (ok_rect.left + (ok_rect.w - ok_s2.get_width()) // 2,
                                ok_rect.top  + (ok_rect.h - ok_s2.get_height()) // 2))

            pygame.display.flip()
            pygame.time.delay(16)

        pygame.display.quit()
