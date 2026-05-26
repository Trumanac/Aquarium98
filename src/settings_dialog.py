"""
settings_dialog.py — Win98-styled modal settings panel rendered inside the
pygame window. Sliders + checkboxes for every user-tweakable cfg key.

Returns one of: "save", "cancel", "reset", or None (still open).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pygame

WIN_GRAY = (192, 192, 192)
WIN_LIGHT = (255, 255, 255)
WIN_DARK = (64, 64, 64)
WIN_MID = (128, 128, 128)
TITLE_DARK = (0, 0, 128)
TITLE_LIGHT = (64, 128, 200)

# Difficulty descriptions (1-5) — shown below the difficulty slider
_DIFF_DESCS = {
    1: "Easy \u2014 Fish breed freely; a safe minimum pop. is always kept.",
    2: "Balanced \u2014 The classic Aquarium 98 experience.",
    3: "Challenging \u2014 Faster hunger and aging. Keep the tank clean!",
    4: "Unforgiving \u2014 No safety net. Lose all fish and you restart.",
    5: "Nightmare \u2014 Extreme rates. An achievement awaits the survivor.",
}
_DIFF_NAMES = {1: "Peaceful", 2: "Normal", 3: "Hard", 4: "Brutal", 5: "Nightmare"}


@dataclass
class _Slider:
    key: str
    label: str
    minv: float
    maxv: float
    step: float
    rect: pygame.Rect = field(default_factory=lambda: pygame.Rect(0, 0, 0, 0))
    integer: bool = False


@dataclass
class _Check:
    key: str
    label: str
    rect: pygame.Rect = field(default_factory=lambda: pygame.Rect(0, 0, 0, 0))


@dataclass
class _Button:
    label: str
    action: str
    rect: pygame.Rect = field(default_factory=lambda: pygame.Rect(0, 0, 0, 0))
    pressed: bool = False


class SettingsDialog:
    """Modal dialog. Edits a *copy* of cfg; commits on Save."""

    def __init__(self, font: pygame.font.Font):
        self.font = font
        self.visible = False
        self.cfg_edit: dict = {}
        self._dragging: _Slider | None = None
        self._diff_desc_y: int = 0   # y position for difficulty description line
        self.update_info: dict = {}   # populated by aquarium.py from update_check.get_result()
        self.sliders: list[_Slider] = [
            _Slider("opacity",       "Window Opacity",  0.30, 1.00, 0.05),
            _Slider("sound_volume",  "Sound Volume",    0.00, 1.00, 0.05),
            _Slider("max_bubbles",   "Max Bubbles",     1,    30,   1,   integer=True),
            _Slider("castle_choice", "Castle Style",    1,    5,    1,   integer=True),
            _Slider("bg_choice",     "Background",      1,    4,    1,   integer=True),
            _Slider("plant_choice",  "Plant Style",     1,    3,    1,   integer=True),
            _Slider("difficulty",    "Difficulty",      1,    5,    1,   integer=True),
        ]
        self.checks: list[_Check] = [
            _Check("always_on_top",    "Always on Top"),
            _Check("locked",           "Lock In Place"),
            _Check("pause_when_hidden","Pause When Hidden"),
            _Check("scan_lines",       "Retro Scan Lines"),
            _Check("show_names",       "Show Fish Names"),
            _Check("sound_muted",      "Mute Sounds"),
            _Check("open_on_startup",  "Open on Startup"),
            _Check("performance_mode", "Performance Mode"),
        ]
        self.buttons: list[_Button] = [
            _Button("Save",           "save"),
            _Button("Cancel",         "cancel"),
            _Button("Reset Defaults", "reset"),
            _Button("Reset Tank...",  "reset_tank"),
            _Button("Full Reset...",  "full_reset"),
        ]
        self._panel = pygame.Rect(0, 0, 0, 0)
        self._check_col_x = 0
        self._row_h       = 24
        self._veil: pygame.Surface | None = None
        self._veil_size = (0, 0)

    def open(self, cfg: dict, screen_size: tuple[int, int]) -> None:
        self.cfg_edit = dict(cfg)
        sw, sh = screen_size
        pw, ph = min(500, sw - 20), min(520, sh - 10)
        self._panel = pygame.Rect((sw - pw) // 2, (sh - ph) // 2, pw, ph)
        self._layout()
        self.visible = True

    def close(self) -> None:
        self.visible = False
        self._dragging = None

    def _layout(self) -> None:
        p = self._panel
        ROW_H    = 24    # px per row
        LABEL_W  = 120   # label text column
        SLIDER_W = 140   # slider track width
        VAL_W    = 44    # reserved for value text right of slider
        SEP      = 14    # gap between slider section and check section

        slider_sec_w       = LABEL_W + 6 + SLIDER_W + VAL_W
        self._check_col_x  = p.left + 14 + slider_sec_w + SEP
        self._row_h        = ROW_H

        y = p.top + 30
        for s in self.sliders:
            s.rect = pygame.Rect(p.left + 14 + LABEL_W + 6,
                                 y + (ROW_H - 10) // 2,
                                 SLIDER_W, 10)
            y += ROW_H
            if s.key == "difficulty":
                self._diff_desc_y = y   # extra line for difficulty description
                y += ROW_H

        cy = p.top + 30
        for c in self.checks:
            c.rect = pygame.Rect(self._check_col_x,
                                 cy + (ROW_H - 12) // 2,
                                 12, 12)
            cy += ROW_H

        # Buttons row at bottom
        bx = p.right - 14 - 90
        by = p.bottom - 30
        for b in reversed(self.buttons):
            b.rect = pygame.Rect(bx, by, 84, 22)
            bx -= 92

    # ---------- events ----------
    def handle_event(self, ev: pygame.event.Event) -> Optional[str]:
        if not self.visible:
            return None
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.close()
            return "cancel"
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for b in self.buttons:
                if b.rect.inflate(0, 8).collidepoint(ev.pos):
                    # "full_reset" and "reset_tank" keep settings open — caller handles
                    if b.action not in ("full_reset", "reset_tank"):
                        self.close()
                    return b.action
            # Sliders checked BEFORE checkboxes: the slider hit-area extends right
            # into the checkbox column, so sliders must win the priority contest.
            for s in self.sliders:
                hit = s.rect.inflate(6, 14)
                if hit.collidepoint(ev.pos):
                    self._dragging = s
                    self._set_from_x(s, ev.pos[0])
                    return None
            for c in self.checks:
                # Extend hitbox rightward only (covers the label text).
                # inflate() expands both sides equally, so build the rect manually
                # to avoid the left edge bleeding into the slider area.
                hit = pygame.Rect(c.rect.left, c.rect.top - 2, 185, c.rect.h + 4)
                if hit.collidepoint(ev.pos):
                    self.cfg_edit[c.key] = not bool(self.cfg_edit.get(c.key, False))
                    return None
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self._dragging = None
        elif ev.type == pygame.MOUSEMOTION and self._dragging is not None:
            self._set_from_x(self._dragging, ev.pos[0])
        return None

    def _set_from_x(self, s: _Slider, x: int) -> None:
        t = (x - s.rect.left) / max(1, s.rect.w)
        t = max(0.0, min(1.0, t))
        val = s.minv + t * (s.maxv - s.minv)
        if s.integer:
            val = round(val)
        else:
            val = round(val / s.step) * s.step
            val = round(val, 4)
        self.cfg_edit[s.key] = val

    def commit_into(self, cfg: dict) -> None:
        cfg.update(self.cfg_edit)

    # ---------- draw ----------
    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return
        sw, sh = screen.get_size()
        if self._veil is None or self._veil_size != (sw, sh):
            self._veil = pygame.Surface((sw, sh), pygame.SRCALPHA)
            self._veil.fill((0, 0, 0, 90))
            self._veil_size = (sw, sh)
        screen.blit(self._veil, (0, 0))

        p = self._panel
        pygame.draw.rect(screen, WIN_GRAY, p)
        pygame.draw.line(screen, WIN_LIGHT, p.topleft, (p.right - 1, p.top))
        pygame.draw.line(screen, WIN_LIGHT, p.topleft, (p.left, p.bottom - 1))
        pygame.draw.line(screen, WIN_DARK, (p.right - 1, p.top), (p.right - 1, p.bottom - 1))
        pygame.draw.line(screen, WIN_DARK, (p.left, p.bottom - 1), (p.right - 1, p.bottom - 1))

        # Title bar
        tb = pygame.Rect(p.left + 3, p.top + 3, p.w - 6, 20)
        for i in range(tb.h):
            t = i / max(1, tb.h - 1)
            c = (int(TITLE_DARK[0] * (1 - t) + TITLE_LIGHT[0] * t),
                 int(TITLE_DARK[1] * (1 - t) + TITLE_LIGHT[1] * t),
                 int(TITLE_DARK[2] * (1 - t) + TITLE_LIGHT[2] * t))
            pygame.draw.line(screen, c, (tb.left, tb.top + i), (tb.right, tb.top + i))
        t = self.font.render("Aquarium 98 - Settings", True, (255, 255, 255))
        screen.blit(t, (tb.left + 6, tb.top + (tb.h - t.get_height()) // 2))

        # Sliders
        fh = self.font.get_height()
        for s in self.sliders:
            label = self.font.render(s.label, True, (0, 0, 0))
            screen.blit(label, (p.left + 14, s.rect.centery - fh // 2))
            # Trough
            pygame.draw.rect(screen, WIN_MID, s.rect)
            pygame.draw.line(screen, WIN_DARK, s.rect.topleft, (s.rect.right, s.rect.top))
            pygame.draw.line(screen, WIN_LIGHT, (s.rect.left, s.rect.bottom),
                             (s.rect.right, s.rect.bottom))
            val = float(self.cfg_edit.get(s.key, s.minv))
            t = (val - s.minv) / max(1e-9, s.maxv - s.minv)
            t = max(0.0, min(1.0, t))
            knob_x = s.rect.left + int(t * s.rect.w)
            knob = pygame.Rect(knob_x - 4, s.rect.top - 4, 8, s.rect.h + 8)
            pygame.draw.rect(screen, WIN_GRAY, knob)
            pygame.draw.line(screen, WIN_LIGHT, knob.topleft, (knob.right - 1, knob.top))
            pygame.draw.line(screen, WIN_LIGHT, knob.topleft, (knob.left, knob.bottom - 1))
            pygame.draw.line(screen, WIN_DARK, (knob.right - 1, knob.top),
                             (knob.right - 1, knob.bottom - 1))
            pygame.draw.line(screen, WIN_DARK, (knob.left, knob.bottom - 1),
                             (knob.right - 1, knob.bottom - 1))
            # Value text — show name for difficulty, number for others
            if s.key == "difficulty":
                vtext = _DIFF_NAMES.get(int(val), str(int(val)))
            else:
                vtext = (f"{int(val)}" if s.integer else f"{val:.2f}")
            v = self.font.render(vtext, True, (0, 0, 0))
            screen.blit(v, (s.rect.right + 6, s.rect.top - 2))
            # Difficulty description rendered on the reserved line below
            if s.key == "difficulty":
                desc = _DIFF_DESCS.get(int(val), "")
                ds = self.font.render(desc, True, (0, 0, 100))
                screen.blit(ds, (p.left + 14, self._diff_desc_y + 3))

        # Checks
        for c in self.checks:
            r = c.rect
            pygame.draw.rect(screen, WIN_LIGHT, r)
            pygame.draw.line(screen, WIN_DARK, r.topleft, (r.right - 1, r.top))
            pygame.draw.line(screen, WIN_DARK, r.topleft, (r.left, r.bottom - 1))
            pygame.draw.line(screen, WIN_LIGHT, (r.right - 1, r.top),
                             (r.right - 1, r.bottom - 1))
            pygame.draw.line(screen, WIN_LIGHT, (r.left, r.bottom - 1),
                             (r.right - 1, r.bottom - 1))
            if self.cfg_edit.get(c.key, False):
                pygame.draw.line(screen, (0, 0, 0), (r.left + 2, r.top + 5),
                                 (r.left + 5, r.top + 9), 2)
                pygame.draw.line(screen, (0, 0, 0), (r.left + 5, r.top + 9),
                                 (r.right - 2, r.top + 1), 2)
            lbl = self.font.render(c.label, True, (0, 0, 0))
            screen.blit(lbl, (r.right + 6, r.centery - fh // 2))

        # ── Tank Stats section ──────────────────────────────────────────
        # Positioned below the checks column
        check_col_x = self._check_col_x
        stats_y = p.top + 30 + len(self.checks) * self._row_h + 6
        # Divider
        pygame.draw.line(screen, WIN_DARK,  (check_col_x - 2, stats_y),
                         (p.right - 14,    stats_y))
        pygame.draw.line(screen, WIN_LIGHT, (check_col_x - 2, stats_y + 1),
                         (p.right - 14,    stats_y + 1))
        hdr = self.font.render("Tank Stats", True, (0, 0, 128))
        screen.blit(hdr, (check_col_x, stats_y + 4))
        sy = stats_y + 4 + hdr.get_height() + 3

        total_days  = float(self.cfg_edit.get("stat_total_days",  0))
        total_fish  = int(self.cfg_edit.get("stat_total_fish",  0))
        peak_fish   = int(self.cfg_edit.get("stat_peak_fish",   0))

        for label, value_str in (
            ("Total Time:",  f"{total_days:.1f} days"),
            ("Fish Seen:",   str(total_fish)),
            ("Peak Count:",  str(peak_fish)),
        ):
            lbl_s = self.font.render(label, True, (0, 0, 0))
            val_s = self.font.render(value_str, True, (0, 0, 80))
            screen.blit(lbl_s, (check_col_x, sy))
            screen.blit(val_s, (check_col_x + lbl_s.get_width() + 4, sy))
            sy += lbl_s.get_height() + 3

        # Version / update status line
        ui = self.update_info
        if ui.get("newer"):
            ver_text = f"v{ui.get('latest', '?')} available \u2014 see GitHub"
            ver_col  = (160, 0, 0)
        elif "newer" in ui:
            ver_text = "App is up to date"
            ver_col  = (0, 120, 0)
        else:
            ver_text = "Checking for updates..."
            ver_col  = (80, 80, 80)
        ver_s   = self.font.render(ver_text, True, ver_col)
        avail_w = p.right - 14 - check_col_x
        screen.blit(ver_s, (check_col_x, sy),
                    area=(0, 0, min(ver_s.get_width(), avail_w), ver_s.get_height()))
        sy += ver_s.get_height() + 3

        # Buttons
        for b in self.buttons:
            r = b.rect
            if b.action == "full_reset":
                bg = (210, 160, 160)
            elif b.action == "reset_tank":
                bg = (215, 200, 155)
            else:
                bg = WIN_GRAY
            pygame.draw.rect(screen, bg, r)
            pygame.draw.line(screen, WIN_LIGHT, r.topleft, (r.right - 1, r.top))
            pygame.draw.line(screen, WIN_LIGHT, r.topleft, (r.left, r.bottom - 1))
            pygame.draw.line(screen, WIN_DARK, (r.right - 1, r.top),
                             (r.right - 1, r.bottom - 1))
            pygame.draw.line(screen, WIN_DARK, (r.left, r.bottom - 1),
                             (r.right - 1, r.bottom - 1))
            if b.action == "full_reset":
                tc = (120, 0, 0)
            elif b.action == "reset_tank":
                tc = (90, 55, 0)
            else:
                tc = (0, 0, 0)
            t = self.font.render(b.label, True, tc)
            screen.blit(t, (r.left + (r.w - t.get_width()) // 2,
                            r.top + (r.h - t.get_height()) // 2))
