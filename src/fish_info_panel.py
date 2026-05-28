"""
fish_info_panel.py — Win98-style Fish Profile popup.

Opened by clicking on a fish in the tank.  Shows species facts, personality,
health/age stats, and a rename field.  Draggable by title bar.
Closes via X button or Close button.
"""
from __future__ import annotations

import random
import time
import pygame
from .coin_system import fish_sell_price

WIN_GRAY  = (192, 192, 192)
WIN_LIGHT = (255, 255, 255)
WIN_DARK  = (64,  64,  64)
WIN_MID   = (128, 128, 128)
TITLE_A   = (0,   0,   128)
TITLE_B   = (16,  132, 208)
# RPG-style rarity tier colours
COL_UNCOMMON   = (60,  210,  80)   # green
COL_RARE       = (80,  150, 255)   # blue
COL_SUPER_RARE = (180,  70, 240)   # purple

# Panel dimensions
PW = 300
PH = 338   # expanded to fit HP + Hunger + Age stats block

# Fixed layout offsets (relative to panel top-left)
_TB_H    = 18   # title bar height
_PAD     = 6    # outer content padding
_THUMB_W = 66   # thumbnail width
_THUMB_H = 50   # thumbnail height
_INPUT_H = 18   # rename input height


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


def _bevel(surf: pygame.Surface, r: pygame.Rect, pressed: bool = False) -> None:
    tl = WIN_DARK  if pressed else WIN_LIGHT
    br = WIN_LIGHT if pressed else WIN_DARK
    pygame.draw.line(surf, tl, r.topleft,        (r.right - 1, r.top))
    pygame.draw.line(surf, tl, r.topleft,        (r.left,      r.bottom - 1))
    pygame.draw.line(surf, br, (r.right - 1, r.top),    (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, br, (r.left, r.bottom - 1),  (r.right - 1, r.bottom - 1))


def _input_box(surf: pygame.Surface, r: pygame.Rect) -> None:
    """White sunken input field — fills the interior only, no outside fill."""
    pygame.draw.rect(surf, WIN_LIGHT, r)
    pygame.draw.line(surf, WIN_DARK,  r.topleft,        (r.right - 1, r.top))
    pygame.draw.line(surf, WIN_DARK,  r.topleft,        (r.left,      r.bottom - 1))
    pygame.draw.line(surf, WIN_MID,   (r.right - 1, r.top), (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, WIN_MID,   (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1))


def _thumb_frame(surf: pygame.Surface, r: pygame.Rect) -> None:
    """Sunken thumbnail frame with dark blue interior."""
    pygame.draw.rect(surf, (20, 50, 100), r)
    pygame.draw.line(surf, WIN_DARK,  r.topleft,        (r.right - 1, r.top))
    pygame.draw.line(surf, WIN_DARK,  r.topleft,        (r.left,      r.bottom - 1))
    pygame.draw.line(surf, WIN_LIGHT, (r.right - 1, r.top), (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, WIN_LIGHT, (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1))


def _divider(surf: pygame.Surface, x1: int, x2: int, y: int) -> None:
    pygame.draw.line(surf, WIN_DARK,  (x1, y),     (x2, y))
    pygame.draw.line(surf, WIN_LIGHT, (x1, y + 1), (x2, y + 1))


def _draw_bar(surf: pygame.Surface, r: pygame.Rect,
              pct: float, color: tuple) -> None:
    """Win98 sunken progress bar: grey trough + coloured fill + bevel."""
    pygame.draw.rect(surf, (160, 160, 160), r)
    if pct > 0:
        pygame.draw.rect(surf, color,
                         pygame.Rect(r.left, r.top, max(1, int(r.w * pct)), r.h))
    pygame.draw.line(surf, WIN_DARK,  r.topleft, (r.right - 1, r.top))
    pygame.draw.line(surf, WIN_DARK,  r.topleft, (r.left,      r.bottom - 1))
    pygame.draw.line(surf, WIN_LIGHT, (r.right - 1, r.top), (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, WIN_LIGHT, (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1))


def _hp_color(pct: float) -> tuple:
    """Green when healthy → yellow → red when critical."""
    return (int(220 * (1.0 - pct)), int(200 * pct), 30)


def _hunger_color(pct: float) -> tuple:
    """Green when full (hunger=0) → orange/red when starving (hunger=1)."""
    return (int(220 * pct), int(180 * (1.0 - pct)), 20)


class FishInfoPanel:
    """Win98 fish profile popup.  Draggable by title bar.
    Caller must route events here first while ``visible`` is True."""

    def __init__(self, font: pygame.font.Font):
        self.font    = font
        self.visible = False
        self.fish    = None
        self._fact:          str  = ""
        self._rename:        str  = ""
        self._rename_active: bool = False
        self._rect       = pygame.Rect(0, 0, PW, PH)
        self._screen_w   = 800
        self._screen_h   = 600
        self._fish_sheets: dict[str, pygame.Surface] = {}
        # Drag state
        self._dragging    = False
        self._drag_offset = (0, 0)
        # Cached sub-rects (rebuilt by _layout)
        self._title_bar  = pygame.Rect(0, 0, 0, 0)
        self._close_btn  = pygame.Rect(0, 0, 0, 0)
        self._input_rect = pygame.Rect(0, 0, 0, 0)
        self._save_btn   = pygame.Rect(0, 0, 0, 0)
        self._close2_btn = pygame.Rect(0, 0, 0, 0)
        self._sell_btn   = pygame.Rect(0, 0, 0, 0)
        # Thumbnail cache
        self._thumb: pygame.Surface | None = None
        self._thumb_fid: int = -1
        # Pre-wrapped text (rebuilt in open())
        self._fact_lines: list[str] = []
        self._personality_lines: list[str] = []
        # Title-bar gradient surface cache
        self._title_surf: pygame.Surface | None = None
        self._title_surf_w: int = 0

    # ------------------------------------------------------------------
    def open(self, fish, screen_w: int, screen_h: int,
             click_x: int, click_y: int,
             fish_sheets: dict[str, pygame.Surface]) -> None:
        self.fish = fish
        self._screen_w = screen_w
        self._screen_h = screen_h
        self._rename = fish.name
        self._rename_active = False
        self._dragging = False
        facts = fish.sp.get("fun_facts", [])
        self._fact = random.choice(facts) if facts else "A remarkable fish."
        self._fish_sheets = fish_sheets
        self._thumb = None
        self._thumb_fid = -1
        # Pre-wrap static text so draw() doesn't call font.size() every frame
        _wrap_w = PW - _PAD * 2
        self._fact_lines = _wrap(self.font, self._fact, _wrap_w)[:4]
        self._personality_lines = _wrap(self.font, fish.personality_desc, _wrap_w)[:3]
        # Position near click, clamped to window
        px = max(0, min(screen_w - PW, click_x - PW // 2))
        py = max(0, min(screen_h - PH, click_y - 32))
        self._rect = pygame.Rect(px, py, PW, PH)
        self._layout()
        self.visible = True

    def close(self) -> None:
        self.visible   = False
        self.fish      = None
        self._dragging = False

    def _layout(self) -> None:
        r = self._rect
        fh = self.font.get_height()
        # Title bar
        self._title_bar = pygame.Rect(r.left + 3, r.top + 3, r.w - 6, _TB_H)
        # X close button
        self._close_btn = pygame.Rect(r.right - 3 - _TB_H, r.top + 3, _TB_H, _TB_H)
        # Content area starts below title bar
        cy = r.top + 3 + _TB_H + 4          # y=29
        # Right column x (after thumbnail + gap)
        rx = r.left + _PAD + _THUMB_W + 6   # x=78
        rw = r.right - rx - _PAD            # width of right column
        # Name input: one font-height label row + input
        name_lbl_y = cy
        input_y    = cy + fh + 3
        self._input_rect = pygame.Rect(rx, input_y, rw, _INPUT_H)
        # Bottom buttons
        self._save_btn   = pygame.Rect(r.right - _PAD - 144, r.bottom - _PAD - 22, 68, 22)
        self._close2_btn = pygame.Rect(r.right - _PAD - 70,  r.bottom - _PAD - 22, 64, 22)
        self._sell_btn   = pygame.Rect(r.left  + _PAD,        r.bottom - _PAD - 22, 80, 22)

    # ------------------------------------------------------------------
    def handle_event(self, ev: pygame.event.Event) -> str | None:
        if not self.visible:
            return None

        if ev.type == pygame.KEYDOWN:
            if not self._rename_active:
                return None
            if ev.key == pygame.K_ESCAPE:
                self._rename_active = False
            elif ev.key == pygame.K_RETURN:
                self._apply_rename()
                self._rename_active = False
            elif ev.key == pygame.K_BACKSPACE:
                self._rename = self._rename[:-1]
            else:
                ch = ev.unicode
                if ch and ch.isprintable() and len(self._rename) < 24:
                    self._rename += ch
            return None

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            # X button — inflated hitbox for easier clicking
            if self._close_btn.inflate(8, 8).collidepoint(ev.pos):
                self.close(); return "close_inside"
            # Bottom buttons
            if self._close2_btn.inflate(0, 8).collidepoint(ev.pos):
                self.close(); return "close_inside"
            if self._sell_btn.inflate(0, 8).collidepoint(ev.pos):
                return "sell"
            if self._save_btn.inflate(0, 8).collidepoint(ev.pos):
                old_name = self.fish.name if self.fish else ""
                self._apply_rename()
                new_name = self.fish.name if self.fish else ""
                self.close()
                return "renamed" if new_name != old_name else "close_inside"
            # Name input activate
            if self._input_rect.collidepoint(ev.pos):
                self._rename_active = True; return True
            # Title bar → start drag
            if self._title_bar.collidepoint(ev.pos):
                self._dragging    = True
                self._drag_offset = (ev.pos[0] - self._rect.left,
                                     ev.pos[1] - self._rect.top)
                return True
            # Click outside panel → close
            if not self._rect.collidepoint(ev.pos):
                self.close(); return "close_outside"
            self._rename_active = False
            return True

        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self._dragging = False

        elif ev.type == pygame.MOUSEMOTION and self._dragging:
            nx = ev.pos[0] - self._drag_offset[0]
            ny = ev.pos[1] - self._drag_offset[1]
            # Clamp to window
            nx = max(0, min(self._screen_w - PW, nx))
            ny = max(0, min(self._screen_h - PH, ny))
            self._rect.topleft = (nx, ny)
            self._layout()

        return None

    def _apply_rename(self) -> None:
        nm = self._rename.strip()
        if nm and self.fish is not None and nm != self.fish.name:
            self.fish.name = nm
            self.fish.custom_name = True

    # ------------------------------------------------------------------
    def _get_thumb(self, fish) -> pygame.Surface | None:
        fid = id(fish)
        if self._thumb is not None and self._thumb_fid == fid:
            return self._thumb
        sheet = self._fish_sheets.get(fish.sp.get("sheet", "fish_new.png"))
        if sheet is None:
            return None
        sw, sh = sheet.get_size()
        fw, fh = sw // 3, sh // 3
        sub = sheet.subsurface(pygame.Rect(0, 0, fw, fh)).copy()
        self._thumb    = pygame.transform.smoothscale(sub, (_THUMB_W - 2, _THUMB_H - 2))
        self._thumb_fid = fid
        return self._thumb

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        if not self.visible or self.fish is None:
            return

        r   = self._rect
        f   = self.fish
        fnt = self.font
        fh  = fnt.get_height()

        # ── Panel background + outer bevel ────────────────────────
        pygame.draw.rect(surface, WIN_GRAY, r)
        _bevel(surface, r)

        # ── Title bar gradient (cached per width) ────────────────
        tb = self._title_bar
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
        title_s = fnt.render("Fish Profile", True, WIN_LIGHT)
        surface.blit(title_s, (tb.left + 5,
                                tb.top + (tb.h - title_s.get_height()) // 2))

        # ── X close button ────────────────────────────────────────
        cb = self._close_btn
        # Fill X btn with a slightly reddish background for visibility
        pygame.draw.rect(surface, (180, 80, 80), cb)
        _bevel(surface, cb)
        xs = fnt.render("x", True, WIN_LIGHT)
        surface.blit(xs, (cb.left + (cb.w - xs.get_width()) // 2,
                           cb.top  + (cb.h - xs.get_height()) // 2))

        # ── Content layout y-cursor ───────────────────────────────
        cy = r.top + 3 + _TB_H + 4   # y=29
        rx = r.left + _PAD + _THUMB_W + 6   # right-column x
        rw = r.right - rx - _PAD

        # ── Fish thumbnail ────────────────────────────────────────
        tf = pygame.Rect(r.left + _PAD, cy, _THUMB_W, _THUMB_H)
        _thumb_frame(surface, tf)
        thumb = self._get_thumb(f)
        if thumb:
            surface.blit(thumb, (tf.left + 1, tf.top + 1))

        # ── Name label + input box ────────────────────────────────
        lbl = fnt.render("Name:", True, (0, 0, 0))
        surface.blit(lbl, (rx, cy))

        ir = self._input_rect
        _input_box(surface, ir)
        disp = self._rename
        if self._rename_active and int(time.time() * 2) % 2 == 0:
            disp = disp + "|"
        # Clip rendered name to box width
        name_s = fnt.render(disp, True, (0, 0, 0))
        clip_r = pygame.Rect(ir.left + 2, ir.top, ir.w - 4, ir.h)
        surface.set_clip(clip_r)
        surface.blit(name_s, (ir.left + 3,
                               ir.top + (ir.h - name_s.get_height()) // 2))
        surface.set_clip(None)

        # ── Species + rarity badge ─────────────────────────────────────────
        sp_y = ir.bottom + 4
        sp_name = f.sp.get("name", "Unknown")
        sp_s    = fnt.render(sp_name, True, (0, 0, 100))
        surface.blit(sp_s, (rx, sp_y))
        if f.sp.get("super_rare"):
            badge_s = fnt.render(" ★ EPIC", True, COL_SUPER_RARE)
            surface.blit(badge_s, (rx + sp_s.get_width(), sp_y))
        elif f.sp.get("rare"):
            badge_s = fnt.render(" ★ RARE", True, COL_RARE)
            surface.blit(badge_s, (rx + sp_s.get_width(), sp_y))
        elif f.sp.get("uncommon"):
            badge_s = fnt.render(" ◆ UNCOMMON", True, COL_UNCOMMON)
            surface.blit(badge_s, (rx + sp_s.get_width(), sp_y))

        # ── Mood indicator ────────────────────────────────────────
        mood = getattr(f, "mood", "content")
        mood_face  = {"happy": "☺", "content": "—", "stressed": "☹", "hungry": "o"}.get(mood, "—")
        mood_color = {"happy": (30, 200, 60), "content": (80, 200, 80),
                      "stressed": (220, 60, 60), "hungry": (220, 160, 20)}.get(mood, (128, 128, 128))
        mood_s = fnt.render(f"{mood_face} {mood.capitalize()}", True, mood_color)
        surface.blit(mood_s, (rx, sp_y + fh + 2))

        # ── Lineage ───────────────────────────────────────────────
        born_from = getattr(f, "born_from", None)
        if born_from:
            lin_s = fnt.render(f"Offspring of {born_from[0]} & {born_from[1]}",
                               True, (80, 80, 120))
            # Clip to right column width
            clip_r2 = pygame.Rect(rx, sp_y + fh * 2 + 4, r.right - rx - _PAD, fh)
            surface.set_clip(clip_r2)
            surface.blit(lin_s, (rx, sp_y + fh * 2 + 4))
            surface.set_clip(None)
            lineage_extra = fh + 2
        else:
            lineage_extra = 0

        # Row bottom is the taller of thumbnail or name/species/mood block
        top_section_bottom = max(tf.bottom, sp_y + fh * 2 + 4 + lineage_extra + 2)
        dy = top_section_bottom + 5

        # ── Divider ───────────────────────────────────────────────
        _divider(surface, r.left + _PAD, r.right - _PAD, dy)
        dy += 4

        # ── Fun fact ──────────────────────────────────────────────
        hdr_s = fnt.render("Did you know?", True, (0, 0, 140))
        surface.blit(hdr_s, (r.left + _PAD, dy))
        dy += fh + 2
        for ln in self._fact_lines:
            ls = fnt.render(ln, True, (20, 20, 20))
            surface.blit(ls, (r.left + _PAD, dy))
            dy += fh + 1

        # ── Divider ───────────────────────────────────────────────
        dy += 3
        _divider(surface, r.left + _PAD, r.right - _PAD, dy)
        dy += 4

        # ── Personality ───────────────────────────────────────────
        phdr_s = fnt.render("Personality:", True, (0, 0, 140))
        surface.blit(phdr_s, (r.left + _PAD, dy))
        dy += fh + 2
        for ln in self._personality_lines:
            ls = fnt.render(ln, True, (40, 40, 40))
            surface.blit(ls, (r.left + _PAD, dy))
            dy += fh + 1

        # ── Stats block: HP · Hunger · Age/Lifespan ───────────────
        # Anchored from bottom so it never overlaps content above.
        # Layout (bottom-up): buttons(22)+gap(4)+age_row(fh)+gap(3)
        #                     +hunger_bar(11)+gap(3)+hp_bar(11)+gap(4)+divider(2)
        stats_y = r.bottom - _PAD - 22 - 4 - fh - 3 - 11 - 3 - 11 - 4
        _divider(surface, r.left + _PAD, r.right - _PAD, stats_y)
        sy = stats_y + 4

        # Align both bar labels to same column
        lbl_w = fnt.size("Hunger")[0] + 4
        pct_w = fnt.size("100%")[0] + 4
        bar_x = r.left + _PAD + lbl_w
        bar_w = r.right - _PAD - bar_x - pct_w

        # HP bar
        hpct   = max(0.0, min(1.0, f.health))
        surface.blit(fnt.render("HP", True, (0, 0, 0)), (r.left + _PAD, sy + 1))
        hp_r   = pygame.Rect(bar_x, sy, bar_w, 11)
        _draw_bar(surface, hp_r, hpct, _hp_color(hpct))
        surface.blit(fnt.render(f"{int(hpct * 100)}%", True, (0, 0, 0)),
                     (hp_r.right + 2, sy + 1))
        sy += 14   # bar(11) + gap(3)

        # Hunger bar  (0 = full/green  →  1 = starving/red)
        hg   = max(0.0, min(1.0, f.hunger))
        surface.blit(fnt.render("Hunger", True, (0, 0, 0)), (r.left + _PAD, sy + 1))
        hg_r = pygame.Rect(bar_x, sy, bar_w, 11)
        _draw_bar(surface, hg_r, hg, _hunger_color(hg))
        surface.blit(fnt.render(f"{int(hg * 100)}%", True, (0, 0, 0)),
                     (hg_r.right + 2, sy + 1))
        sy += 14   # bar(11) + gap(3)

        # Age / lifespan text  (format as days / hours / minutes as appropriate)
        def _fmt_time(secs: float) -> str:
            if secs >= 86400:
                return f"{secs / 86400:.1f}d"
            if secs >= 3600:
                return f"{secs / 3600:.1f}h"
            return f"{secs / 60:.0f}m"
        age_str = f"Age: {_fmt_time(f.age)}  /  Life: {_fmt_time(f.lifespan)}"
        surface.blit(fnt.render(age_str, True, (40, 40, 60)), (r.left + _PAD, sy))

        # ── Bottom buttons ────────────────────────────────────────
        for btn, label in ((self._save_btn, "Save Name"),
                           (self._close2_btn, "Close")):
            pygame.draw.rect(surface, WIN_GRAY, btn)
            _bevel(surface, btn)
            bs = fnt.render(label, True, (0, 0, 0))
            surface.blit(bs, (btn.left + (btn.w - bs.get_width()) // 2,
                               btn.top  + (btn.h - bs.get_height()) // 2))

        # Sell button (left side of button row)
        sell_price = fish_sell_price(f)
        sell_label = f"Sell ({sell_price}c)"
        pygame.draw.rect(surface, WIN_GRAY, self._sell_btn)
        _bevel(surface, self._sell_btn)
        ss = fnt.render(sell_label, True, (0, 100, 0))
        surface.blit(ss, (self._sell_btn.left + (self._sell_btn.w - ss.get_width()) // 2,
                          self._sell_btn.top  + (self._sell_btn.h - ss.get_height()) // 2))

