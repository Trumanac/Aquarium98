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
        self._rect   = pygame.Rect(0, 0, _PW, 120)
        self._yes_btn = pygame.Rect(0, 0, _BTN_W, _BTN_H)
        self._no_btn  = pygame.Rect(0, 0, _BTN_W, _BTN_H)
        self._yes_press = False
        self._no_press  = False

    def open(self, title: str, body: str, screen_w: int, screen_h: int) -> None:
        self._title = title
        self._body  = body
        fh = self.font.get_height()
        lines = _wrap(self.font, body, _PW - _PAD * 2 - 32)
        body_h = len(lines) * (fh + 2)
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
            if self._yes_btn.collidepoint(ev.pos):
                self._yes_press = True
            elif self._no_btn.collidepoint(ev.pos):
                self._no_press = True
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            if self._yes_press and self._yes_btn.collidepoint(ev.pos):
                self.close()
                return "yes"
            if self._no_press and self._no_btn.collidepoint(ev.pos):
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

        # Title bar gradient
        tb = pygame.Rect(r.left + 3, r.top + 3, r.w - 6, _TB_H)
        for i in range(tb.h):
            t = i / max(1, tb.h - 1)
            c = (int(TITLE_A[0] + (TITLE_B[0] - TITLE_A[0]) * t),
                 int(TITLE_A[1] + (TITLE_B[1] - TITLE_A[1]) * t),
                 int(TITLE_A[2] + (TITLE_B[2] - TITLE_A[2]) * t))
            pygame.draw.line(surface, c, (tb.left, tb.top + i), (tb.right - 1, tb.top + i))
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
        lines = _wrap(fnt, self._body, r.w - _PAD * 2 - icon_r.w - 8)
        tx = icon_r.right + 8
        ty = icon_r.top
        for ln in lines:
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

    def open(self, screen_w: int, screen_h: int) -> None:
        self._text = ""
        fh = self.font.get_height()
        prompt_lines = _wrap(self.font, self._PROMPT, self._PW - _PAD * 2 - 32)
        content_h = max(24, len(prompt_lines) * (fh + 2))
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

        # Title bar
        tb = pygame.Rect(r.left + 3, r.top + 3, r.w - 6, _TB_H)
        for i in range(tb.h):
            t = i / max(1, tb.h - 1)
            c = (int(TITLE_A[0] + (TITLE_B[0] - TITLE_A[0]) * t),
                 int(TITLE_A[1] + (TITLE_B[1] - TITLE_A[1]) * t),
                 int(TITLE_A[2] + (TITLE_B[2] - TITLE_A[2]) * t))
            pygame.draw.line(surface, c, (tb.left, tb.top + i), (tb.right - 1, tb.top + i))
        ts = fnt.render("Full Reset — Erase All Data", True, WIN_LIGHT)
        surface.blit(ts, (tb.left + 5, tb.top + (tb.h - ts.get_height()) // 2))

        # Warning icon
        icon_r = pygame.Rect(r.left + _PAD, r.top + _TB_H + _PAD, 24, 24)
        pygame.draw.rect(surface, (220, 60, 60), icon_r)
        _bevel(surface, icon_r)
        ws = fnt.render("!", True, WIN_LIGHT)
        surface.blit(ws, (icon_r.left + (icon_r.w - ws.get_width()) // 2,
                          icon_r.top  + (icon_r.h - ws.get_height()) // 2))

        # Prompt text (to the right of the warning icon)
        lines = _wrap(fnt, self._PROMPT, r.w - _PAD * 2 - icon_r.w - 8)
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
    _ICON_PATH = "assets/icon/icon.png"
    _ICON_SIZE = 32

    def __init__(self, font: pygame.font.Font) -> None:
        self.font    = font
        self.visible = False
        self._rect   = pygame.Rect(0, 0, self._PW, 170)
        self._ok_btn = pygame.Rect(0, 0, _BTN_W, _BTN_H)
        self._ok_press = False
        self._icon: pygame.Surface | None = None
        self._icon_loaded = False

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
        content_h = max(self._ICON_SIZE, row * 4)
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

        # Title bar gradient
        tb = pygame.Rect(r.left + 3, r.top + 3, r.w - 6, _TB_H)
        for i in range(tb.h):
            t = i / max(1, tb.h - 1)
            c = (int(TITLE_A[0] + (TITLE_B[0] - TITLE_A[0]) * t),
                 int(TITLE_A[1] + (TITLE_B[1] - TITLE_A[1]) * t),
                 int(TITLE_A[2] + (TITLE_B[2] - TITLE_A[2]) * t))
            pygame.draw.line(surface, c,
                             (tb.left, tb.top + i), (tb.right - 1, tb.top + i))
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
        ty = content_y + (content_h - row * 4) // 2
        for line in ("Aquarium 98", "Version 1.0", "A living desktop companion.",
                     "By trumanac"):
            col = (0, 0, 180) if line.startswith("By ") else (0, 0, 0)
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
