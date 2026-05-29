"""
settings_dialog.py — Win98-styled modal settings panel rendered inside the
pygame window. Sliders + checkboxes for every user-tweakable cfg key.

Returns one of: "save", "cancel", "reset", or None (still open).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pygame

from .config import DIFFICULTY_PRESETS

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
            _Slider("sound_volume",  "Sound Volume",    0.00, 1.00, 0.01),
            _Slider("music_volume",  "Music Volume",    0.00, 1.00, 0.01),
            _Slider("max_bubbles",   "Max Bubbles",     1,    30,   1,   integer=True),
            _Slider("max_fish",      "Max Fish",        4,    30,   1,   integer=True),
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
            _Check("show_moods",       "Show Fish Moods"),
            _Check("sound_muted",      "Mute Sounds"),
            _Check("music_muted",      "Mute Music"),
            _Check("open_on_startup",  "Open on Startup"),
            _Check("performance_mode", "Performance Mode"),
        ]
        self.buttons: list[_Button] = [
            # Laid out right-to-left (last entry = rightmost button).
            # Save/Cancel must be last so they are always visible even when
            # the panel is narrower than the full 5-button row.
            _Button("Reset Defaults", "reset"),
            _Button("Reset Tank...",  "reset_tank"),
            _Button("Full Reset...",  "full_reset"),
            _Button("Cancel",         "cancel"),
            _Button("Save",           "save"),
        ]
        self._panel = pygame.Rect(0, 0, 0, 0)
        self._check_col_x = 0
        self._row_h       = 24
        self._veil: pygame.Surface | None = None
        self._veil_size = (0, 0)
        self._title_surf: pygame.Surface | None = None
        self._title_surf_w = 0
        # Rect for the clickable update-status button (positioned in draw)
        self._update_btn_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        # Optional callback(key: str, value) fired immediately when a
        # live-previewable slider (opacity/sound_volume/music_volume) changes.
        self.on_live_change = None

    def open(self, cfg: dict, screen_size: tuple[int, int]) -> None:
        self.cfg_edit = dict(cfg)
        # Apply caps (nightmare / performance mode) without overriding the
        # user's saved max_fish value — pass default_to_max=False so an
        # already-saved preference is respected.
        self._apply_max_fish_cap(default_to_max=False)
        sw, sh = screen_size
        pw, ph = min(500, sw - 20), min(460, sh - 10)
        self._panel = pygame.Rect((sw - pw) // 2, (sh - ph) // 2, pw, ph)
        self._layout()
        self.visible = True

    def _apply_max_fish_cap(self, *, default_to_max: bool = False) -> None:
        """Keep max_fish consistent with difficulty + performance_mode.

        Nightmare hard-locks max_fish to 10.
        Performance mode caps max_fish at 8.
        Otherwise, when *default_to_max* is True the slider is reset to the
        maximum (30) so settings always opens with a full tank as the default.
        """
        diff = int(self.cfg_edit.get("difficulty", 2))
        if diff == 5:   # Nightmare — hard-lock
            self.cfg_edit["max_fish"] = DIFFICULTY_PRESETS[5]["max_fish"]
        elif self.cfg_edit.get("performance_mode", False):
            self.cfg_edit["max_fish"] = min(int(self.cfg_edit.get("max_fish", 8)), 8)
        elif default_to_max:
            self.cfg_edit["max_fish"] = 30

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
            # Update button — keep settings open so user sees progress
            if self._update_btn_rect.w > 0 and self._update_btn_rect.collidepoint(ev.pos):
                dl  = self.update_info.get("dl_status", "idle")
                if dl == "ready":
                    return "install_update"
                if dl in ("idle", "failed"):
                    ui = self.update_info
                    if not ui:  # check still pending
                        return "check_updates"
                    if ui.get("newer"):
                        return "download_update"
                    return "check_updates"  # re-check when already up to date
            # Sliders checked BEFORE checkboxes: the slider hit-area extends right
            # into the checkbox column, so sliders must win the priority contest.
            for s in self.sliders:
                hit = pygame.Rect(s.rect.left - 6,
                                  s.rect.top - 7,
                                  s.rect.w + 12,
                                  s.rect.h + 14)
                if hit.collidepoint(ev.pos):
                    # Refuse to start drag on a locked slider
                    if s.key == "max_fish" and (
                        int(self.cfg_edit.get("difficulty", 2)) == 5
                        or self.cfg_edit.get("performance_mode", False)
                    ):
                        return None
                    self._dragging = s
                    self._set_from_x(s, ev.pos[0])
                    return None
            for c in self.checks:
                # Extend hitbox left by 10px (clicks often land just before the
                # box rect), across the label text, and to the panel edge.
                # Use the full row height so there are no dead-zones between rows.
                hit_left  = c.rect.left - 10
                hit_width = max(195, self._panel.right - hit_left - 14)
                row_top   = c.rect.top - (self._row_h - 12) // 2
                hit = pygame.Rect(hit_left, row_top,
                                  hit_width, self._row_h)
                if hit.collidepoint(ev.pos):
                    self.cfg_edit[c.key] = not bool(self.cfg_edit.get(c.key, False))
                    # Toggling performance_mode may cap or release the max_fish slider
                    if c.key == "performance_mode":
                        self._apply_max_fish_cap(default_to_max=True)
                    return None
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self._dragging = None
        elif ev.type == pygame.MOUSEMOTION and self._dragging is not None:
            self._set_from_x(self._dragging, ev.pos[0])
        return None

    def _set_from_x(self, s: _Slider, x: int) -> None:
        # max_fish is hard-locked by Nightmare difficulty or Performance Mode
        if s.key == "max_fish" and (
            int(self.cfg_edit.get("difficulty", 2)) == 5
            or self.cfg_edit.get("performance_mode", False)
        ):
            return
        t = (x - s.rect.left) / max(1, s.rect.w)
        t = max(0.0, min(1.0, t))
        val = s.minv + t * (s.maxv - s.minv)
        if s.integer:
            val = round(val)
        else:
            val = round(val / s.step) * s.step
            val = round(val, 4)
        self.cfg_edit[s.key] = val
        if self.on_live_change is not None and s.key in (
            "sound_volume", "music_volume", "opacity"
        ):
            self.on_live_change(s.key, val)
        # When difficulty changes, sync max_fish via the cap helper so that
        # Nightmare locks it to 10 and other difficulties default to 30.
        if s.key == "difficulty":
            self._apply_max_fish_cap(default_to_max=True)

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
        if self._title_surf is None or self._title_surf_w != tb.w:
            self._title_surf = pygame.Surface((tb.w + 1, tb.h), pygame.SRCALPHA)
            for i in range(tb.h):
                t_frac = i / max(1, tb.h - 1)
                c = (int(TITLE_DARK[0] * (1 - t_frac) + TITLE_LIGHT[0] * t_frac),
                     int(TITLE_DARK[1] * (1 - t_frac) + TITLE_LIGHT[1] * t_frac),
                     int(TITLE_DARK[2] * (1 - t_frac) + TITLE_LIGHT[2] * t_frac))
                pygame.draw.line(self._title_surf, c, (0, i), (tb.w, i))
            self._title_surf_w = tb.w
        screen.blit(self._title_surf, (tb.left, tb.top))
        t = self.font.render("Aquarium 98 - Settings", True, (255, 255, 255))
        screen.blit(t, (tb.left + 6, tb.top + (tb.h - t.get_height()) // 2))

        # Sliders
        fh = self.font.get_height()
        _nightmare = int(self.cfg_edit.get("difficulty", 2)) == 5
        _perf_mode = bool(self.cfg_edit.get("performance_mode", False))
        for s in self.sliders:
            _locked = s.key == "max_fish" and (_nightmare or _perf_mode)
            label_col = WIN_MID if _locked else (0, 0, 0)
            label = self.font.render(s.label, True, label_col)
            screen.blit(label, (p.left + 14, s.rect.centery - fh // 2))
            # Trough
            trough_col = (160, 160, 160) if _locked else WIN_MID
            pygame.draw.rect(screen, trough_col, s.rect)
            pygame.draw.line(screen, WIN_DARK, s.rect.topleft, (s.rect.right, s.rect.top))
            pygame.draw.line(screen, WIN_LIGHT, (s.rect.left, s.rect.bottom),
                             (s.rect.right, s.rect.bottom))
            val = float(self.cfg_edit.get(s.key, s.minv))
            t = (val - s.minv) / max(1e-9, s.maxv - s.minv)
            t = max(0.0, min(1.0, t))
            knob_x = s.rect.left + int(t * s.rect.w)
            knob = pygame.Rect(knob_x - 4, s.rect.top - 4, 8, s.rect.h + 8)
            knob_col = (160, 160, 160) if _locked else WIN_GRAY
            pygame.draw.rect(screen, knob_col, knob)
            if not _locked:
                pygame.draw.line(screen, WIN_LIGHT, knob.topleft, (knob.right - 1, knob.top))
                pygame.draw.line(screen, WIN_LIGHT, knob.topleft, (knob.left, knob.bottom - 1))
                pygame.draw.line(screen, WIN_DARK, (knob.right - 1, knob.top),
                                 (knob.right - 1, knob.bottom - 1))
                pygame.draw.line(screen, WIN_DARK, (knob.left, knob.bottom - 1),
                                 (knob.right - 1, knob.bottom - 1))
            # Value text — show name for difficulty, "Locked" for locked sliders
            if _locked:
                vtext = "Locked"
                v = self.font.render(vtext, True, (140, 0, 0))
            elif s.key == "difficulty":
                vtext = _DIFF_NAMES.get(int(val), str(int(val)))
                v = self.font.render(vtext, True, (0, 0, 0))
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

        # Version / update status — interactive button area
        ui = self.update_info
        avail_w = p.right - 14 - check_col_x
        dl_status   = ui.get("dl_status",   "idle")
        dl_progress = float(ui.get("dl_progress", 0.0))

        if dl_status == "downloading":
            # Progress bar replaces version text while downloading
            bar_w  = min(avail_w, 130)
            bar_h  = self.font.get_height() + 2
            bar_r  = pygame.Rect(check_col_x, sy, bar_w, bar_h)
            pygame.draw.rect(screen, WIN_MID, bar_r)
            fill_w = max(2, int(bar_w * dl_progress))
            pygame.draw.rect(screen, (0, 100, 200),
                             pygame.Rect(bar_r.left, bar_r.top, fill_w, bar_h))
            pct_s = self.font.render(f"Downloading {int(dl_progress * 100)}%",
                                     True, WIN_LIGHT)
            screen.blit(pct_s, (bar_r.left + 3,
                                 bar_r.top + (bar_h - pct_s.get_height()) // 2),
                        area=(0, 0, bar_r.w - 3, pct_s.get_height()))
            self._update_btn_rect = pygame.Rect(0, 0, 0, 0)  # not clickable
            sy += bar_h + 3
        else:
            # Determine button label, colour and whether it's interactive
            if dl_status == "ready":
                ver_text = f"v{ui.get('latest','?')} ready — Install & Restart"
                ver_col  = (0, 130, 0)
                clickable = True
            elif dl_status == "failed":
                ver_text = "Download failed — Retry"
                ver_col  = (160, 0, 0)
                clickable = True
            elif ui.get("newer"):
                ver_text = f"v{ui.get('latest','?')} available — Download"
                ver_col  = (0, 0, 160)
                clickable = True
            elif "newer" in ui:
                ver_text = "App is up to date"
                ver_col  = (0, 120, 0)
                clickable = False
            else:
                ver_text = "Check for Updates"
                ver_col  = (80, 80, 80)
                clickable = True
            ver_s = self.font.render(ver_text, True,
                                     ver_col if not clickable else WIN_LIGHT)
            text_w = min(ver_s.get_width() + 8, avail_w)
            text_h = ver_s.get_height() + 4
            btn_r  = pygame.Rect(check_col_x, sy, text_w, text_h)
            if clickable:
                pygame.draw.rect(screen, ver_col, btn_r)
                pygame.draw.line(screen, WIN_LIGHT, btn_r.topleft,
                                 (btn_r.right - 1, btn_r.top))
                pygame.draw.line(screen, WIN_LIGHT, btn_r.topleft,
                                 (btn_r.left, btn_r.bottom - 1))
                pygame.draw.line(screen, WIN_DARK,
                                 (btn_r.right - 1, btn_r.top),
                                 (btn_r.right - 1, btn_r.bottom - 1))
                pygame.draw.line(screen, WIN_DARK,
                                 (btn_r.left, btn_r.bottom - 1),
                                 (btn_r.right - 1, btn_r.bottom - 1))
                screen.blit(ver_s, (btn_r.left + 4,
                                    btn_r.top + (text_h - ver_s.get_height()) // 2))
                self._update_btn_rect = btn_r
            else:
                ver_plain = self.font.render(ver_text, True, ver_col)
                screen.blit(ver_plain, (check_col_x, sy),
                            area=(0, 0, avail_w, ver_plain.get_height()))
                self._update_btn_rect = pygame.Rect(0, 0, 0, 0)
            sy += text_h + 3

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
