"""
stats_panel.py — Win98-style Tank Statistics panel for Aquarium 98.

Displays session history charts for fish count, algae %, and coin balance,
plus a summary of lifetime stats.  Toggle with the 'stats' toolbar button
or the T hotkey.
"""
from __future__ import annotations

import pygame

WIN_GRAY  = (192, 192, 192)
WIN_LIGHT = (255, 255, 255)
WIN_DARK  = (64,  64,  64)
WIN_MID   = (128, 128, 128)
TITLE_A   = (0,   0,   128)
TITLE_B   = (16, 132, 208)

_TB_H   = 18
_PAD    = 6
PW      = 300
PH      = 240

_LINE_FISH  = (60,  100, 220)
_LINE_ALGAE = (40,  160,  40)
_LINE_COINS = (200, 160,   0)


def _bevel(surf: pygame.Surface, r: pygame.Rect, pressed: bool = False) -> None:
    tl = WIN_DARK  if pressed else WIN_LIGHT
    br = WIN_LIGHT if pressed else WIN_DARK
    pygame.draw.line(surf, tl, r.topleft,       (r.right - 1, r.top))
    pygame.draw.line(surf, tl, r.topleft,       (r.left,      r.bottom - 1))
    pygame.draw.line(surf, br, (r.right - 1, r.top),   (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, br, (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1))


class StatsPanel:
    """Win98-style session statistics panel with history charts."""

    def __init__(self, font: pygame.font.Font) -> None:
        self.font    = font
        self.visible = False

        self._rect      = pygame.Rect(0, 0, PW, PH)
        self._close_btn = pygame.Rect(0, 0, 0, 0)
        self._title_bar = pygame.Rect(0, 0, 0, 0)

        self._dragging    = False
        self._drag_offset = (0, 0)

        # Tab state: 0 = Session history, 1 = All-Time stats
        self._tab: int = 0
        self._tab0_btn  = pygame.Rect(0, 0, 0, 0)
        self._tab1_btn  = pygame.Rect(0, 0, 0, 0)

        # Cached title gradient surface
        self._title_surf: pygame.Surface | None = None
        self._title_surf_w: int = 0

    # ------------------------------------------------------------------
    def toggle(self, anchor: "pygame.Rect | None" = None) -> None:
        if self.visible:
            self.close()
        else:
            self.open(anchor=anchor)

    def open(self, screen_w: int = 800, screen_h: int = 600,
             anchor: "pygame.Rect | None" = None) -> None:
        if not self.visible:
            if anchor is not None:
                self._rect.topleft = (
                    max(0, anchor.right - PW - 4),
                    max(0, anchor.top + 4),
                )
            else:
                self._rect.topleft = (
                    max(0, (screen_w - PW) // 2),
                    max(0, (screen_h - PH) // 2),
                )
        self.visible = True

    def close(self) -> None:
        self.visible = False
        self._dragging = False

    # ------------------------------------------------------------------
    def handle_event(self, ev: pygame.event.Event) -> bool:
        """Return True if the event was consumed."""
        if not self.visible:
            return False

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            pos = ev.pos
            # Close button
            if self._close_btn.inflate(8, 8).collidepoint(pos):
                self.close()
                return True
            # Title-bar drag
            if self._title_bar.collidepoint(pos):
                self._dragging    = True
                self._drag_offset = (pos[0] - self._rect.left,
                                     pos[1] - self._rect.top)
                return True
            # Tab buttons
            if self._tab0_btn.collidepoint(pos):
                self._tab = 0
                return True
            if self._tab1_btn.collidepoint(pos):
                self._tab = 1
                return True
            # Click inside panel
            if self._rect.collidepoint(pos):
                return True
            # Click outside → close
            self.close()
            return False

        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            if self._dragging:
                self._dragging = False
                return True

        if ev.type == pygame.MOUSEMOTION and self._dragging:
            sw, sh = pygame.display.get_surface().get_size()
            nx = max(0, min(sw - PW, ev.pos[0] - self._drag_offset[0]))
            ny = max(0, min(sh - PH, ev.pos[1] - self._drag_offset[1]))
            self._rect.topleft = (nx, ny)
            return True

        return False

    # ------------------------------------------------------------------
    def _draw_chart(
        self,
        surface: pygame.Surface,
        cfg: dict,
        chart_left: int,
        chart_top: int,
        chart_w: int,
        chart_h: int,
        fish_hist: list,
        algae_hist: list,
        coins_hist: list,
    ) -> int:
        """Draw the session history chart and legend. Returns Y below legend."""
        graph_rect = pygame.Rect(chart_left, chart_top, chart_w, chart_h)
        pygame.draw.rect(surface, (210, 210, 210), graph_rect)
        pygame.draw.line(surface, WIN_DARK,
                         graph_rect.topleft, (graph_rect.right - 1, graph_rect.top))
        pygame.draw.line(surface, WIN_DARK,
                         graph_rect.topleft, (graph_rect.left, graph_rect.bottom - 1))
        pygame.draw.line(surface, WIN_LIGHT,
                         (graph_rect.right - 1, graph_rect.top),
                         (graph_rect.right - 1, graph_rect.bottom - 1))
        pygame.draw.line(surface, WIN_LIGHT,
                         (graph_rect.left, graph_rect.bottom - 1),
                         (graph_rect.right - 1, graph_rect.bottom - 1))

        gx = graph_rect.left + 2
        gy = graph_rect.top  + 2
        gw = graph_rect.w - 4
        gh = graph_rect.h - 4
        max_fish_cfg = max(int(cfg.get("max_fish", 25)), 1)

        if len(fish_hist) >= 2:
            n = len(fish_hist)
            pts = [(gx + int(i / max(1, n - 1) * gw),
                    gy + gh - int(min(v, max_fish_cfg) / max_fish_cfg * gh))
                   for i, v in enumerate(fish_hist)]
            pygame.draw.lines(surface, _LINE_FISH, False, pts, 1)
        if len(algae_hist) >= 2:
            n = len(algae_hist)
            pts = [(gx + int(i / max(1, n - 1) * gw),
                    gy + gh - int(min(v, 100) / 100 * gh))
                   for i, v in enumerate(algae_hist)]
            pygame.draw.lines(surface, _LINE_ALGAE, False, pts, 1)
        if len(coins_hist) >= 2:
            max_c = max(max(coins_hist), 1)
            n = len(coins_hist)
            pts = [(gx + int(i / max(1, n - 1) * gw),
                    gy + gh - int(min(v, max_c) / max_c * gh))
                   for i, v in enumerate(coins_hist)]
            pygame.draw.lines(surface, _LINE_COINS, False, pts, 1)

        lx  = graph_rect.left + 4
        ly  = graph_rect.bottom + 3
        fh  = self.font.get_height()
        for col, label in ((_LINE_FISH, "Fish"), (_LINE_ALGAE, "Algae%"), (_LINE_COINS, "Coins")):
            pygame.draw.line(surface, col, (lx, ly + 4), (lx + 8, ly + 4), 1)
            ls = self.font.render(label, True, (40, 40, 60))
            surface.blit(ls, (lx + 10, ly))
            lx += 10 + ls.get_width() + 10
        return ly + fh

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface, cfg: dict) -> None:
        if not self.visible:
            return

        px, py = self._rect.topleft

        # Panel background + outer bevel
        pygame.draw.rect(surface, WIN_GRAY, self._rect)
        _bevel(surface, self._rect)

        # Title bar
        self._title_bar = pygame.Rect(px + 3, py + 3, PW - 6, _TB_H)
        if (self._title_surf is None
                or self._title_surf_w != self._title_bar.w):
            self._title_surf_w = self._title_bar.w
            self._title_surf = pygame.Surface(
                (self._title_bar.w, self._title_bar.h))
            for i in range(self._title_bar.h):
                t = i / max(1, self._title_bar.h - 1)
                c = (int(TITLE_A[0] + (TITLE_B[0] - TITLE_A[0]) * t),
                     int(TITLE_A[1] + (TITLE_B[1] - TITLE_A[1]) * t),
                     int(TITLE_A[2] + (TITLE_B[2] - TITLE_A[2]) * t))
                pygame.draw.line(self._title_surf, c,
                                 (0, i), (self._title_bar.w - 1, i))
        surface.blit(self._title_surf, self._title_bar.topleft)
        ts = self.font.render("Tank Statistics", True, WIN_LIGHT)
        surface.blit(ts, (self._title_bar.left + 5,
                          self._title_bar.top + (self._title_bar.h - ts.get_height()) // 2))

        # Close button
        self._close_btn = pygame.Rect(
            self._rect.right - 3 - _TB_H, py + 3, _TB_H, _TB_H)
        pygame.draw.rect(surface, (180, 80, 80), self._close_btn)
        _bevel(surface, self._close_btn)
        xs = self.font.render("x", True, WIN_LIGHT)
        surface.blit(xs, (
            self._close_btn.left + (self._close_btn.w - xs.get_width()) // 2,
            self._close_btn.top  + (self._close_btn.h - xs.get_height()) // 2))

        # ── Tab buttons ───────────────────────────────────────────────
        _TAB_H  = 20
        _TAB_W  = 82
        tab_y   = py + 3 + _TB_H + 2
        self._tab0_btn = pygame.Rect(px + _PAD,             tab_y, _TAB_W, _TAB_H)
        self._tab1_btn = pygame.Rect(px + _PAD + _TAB_W + 2, tab_y, _TAB_W, _TAB_H)
        for i, (label, btn) in enumerate([("Session", self._tab0_btn),
                                          ("All-Time", self._tab1_btn)]):
            active = (self._tab == i)
            pygame.draw.rect(surface, WIN_GRAY, btn)
            _bevel(surface, btn, pressed=active)
            tl = self.font.render(label, True, (0, 0, 0))
            surface.blit(tl, (btn.centerx - tl.get_width() // 2,
                               btn.centery - tl.get_height() // 2))

        # ── Content area starts below the tab bar ─────────────────────
        content_top = tab_y + _TAB_H + _PAD

        fish_hist  = cfg.get("stat_session_fish_hist")  or []
        algae_hist = cfg.get("stat_session_algae_hist") or []
        coins_hist = cfg.get("stat_session_coins_hist") or []
        chart_left = px + _PAD
        chart_w    = PW - _PAD * 2
        chart_h    = 58
        fh         = self.font.get_height()
        col_val_x  = px + PW - _PAD - 60

        ly = self._draw_chart(surface, cfg, chart_left, content_top,
                              chart_w, chart_h, fish_hist, algae_hist, coins_hist)
        pygame.draw.line(surface, WIN_DARK,
                         (px + _PAD, ly + 3), (px + PW - _PAD - 1, ly + 3))
        sy = ly + 6

        if self._tab == 0:
            # ── Session: current snapshot stats below the chart ────────
            max_fish_cfg = max(int(cfg.get("max_fish", 25)), 1)
            cur_fish  = fish_hist[-1]  if fish_hist  else 0
            cur_algae = algae_hist[-1] if algae_hist else 0
            cur_coins = cfg.get("coins", 0)
            session_stats = [
                ("Fish in tank", f"{cur_fish} / {max_fish_cfg}"),
                ("Algae",        f"{cur_algae:.0f}%"),
                ("Coins",        str(int(cur_coins))),
            ]
            for label, value in session_stats:
                if sy + fh > py + PH - _PAD:
                    break
                lbl_s = self.font.render(label + ":", True, (0, 0, 0))
                val_s = self.font.render(value,         True, (0, 0, 100))
                surface.blit(lbl_s, (px + _PAD + 4, sy))
                surface.blit(val_s, (col_val_x, sy))
                sy += fh + 2

        else:
            # ── All-Time: lifetime stats below the chart ──────────────
            stats_lines = [
                ("Total days survived",   f"{float(cfg.get('stat_total_days', 0)):.1f}"),
                ("Fish ever added",       str(int(cfg.get("stat_total_fish",   0)))),
                ("Peak fish count",       str(int(cfg.get("stat_peak_fish",    0)))),
                ("Total fish deaths",     str(int(cfg.get("stat_deaths",       0)))),
                ("Tank cleans",           str(int(cfg.get("stat_cleans",       0)))),
                ("Coins earned (total)",  str(int(cfg.get("stat_coins_earned", 0)))),
                ("Fish bred in tank",     str(int(cfg.get("stat_bred_fish",    0)))),
            ]
            for label, value in stats_lines:
                if sy + fh > py + PH - _PAD:
                    break
                lbl_s = self.font.render(label + ":", True, (0, 0, 0))
                val_s = self.font.render(value,         True, (0, 0, 100))
                surface.blit(lbl_s, (px + _PAD + 4, sy))
                surface.blit(val_s, (col_val_x, sy))
                sy += fh + 2
