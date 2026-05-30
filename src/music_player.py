"""
music_player.py — Background music player for Aquarium 98.

Streams 8 ambient MP3 tracks via pygame.mixer.music in a shuffled rotation.
Exposes a compact Win98-style mini player widget that floats just above the
status bar when toggled, plus a small ♪ toggle button in the status bar.

Usage::
    player = MusicPlayer(font)
    player.start()               # begin playback (call after pygame.init)

    # Each frame:
    consumed = player.handle_event(ev)
    player.draw(surface)         # draws toggle btn + (if visible) player panel

    # Sync settings from cfg each frame:
    player.set_volume(cfg.get("music_volume", 0.25))
    player.set_muted(cfg.get("music_muted", False))
    player.player_visible = cfg.get("music_player_visible", False)
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import pygame

_AUDIO = Path(__file__).resolve().parent.parent / "assets" / "audio"
_MC_SPRITES = Path(__file__).resolve().parent.parent / "assets" / "sprites" / "ui" / "Music_Controls.png"

# Source rects (x, y, w, h) inside Music_Controls.png  (2048 × 1623)
# Row 1 (y 113..583): Prev, Play, Pause
# Row 2 (y 605..1055): Next, Loop, Speaker-muted + thumb knob at right
# Row 3 (y 1075..1525): Speaker-waves, Slider track
_MC_PREV  = (73,   113,  471,  470)  # row 1 col 0 – Prev
_MC_PLAY  = (564,  113,  452,  470)  # row 1 col 1 – Play
_MC_PAUSE = (1036, 113,  471,  470)  # row 1 col 2 – Pause
_MC_NEXT  = (73,   605,  471,  450)  # row 2 col 0 – Next
_MC_LOOP  = (564,  605,  452,  450)  # row 2 col 1 – Loop
_MC_MOFF  = (1036, 605,  471,  450)  # row 2 col 2 – Speaker silent (muted)
_MC_MON   = (73,   1075, 471,  450)  # row 3 col 0 – Speaker + waves (playing)
_MC_SLBG  = (564,  1075, 1437, 450) # row 3, slider track
_MC_THUMB = (1692, 766,  123,  163)  # row 2 far-right – thumb knob

MUSIC_TRACKS: list[str] = [
    "Sunken_Corridor_View.mp3",
    "Ten_Fathoms_Down.mp3",
    "Sunken_Grotto.mp3",
    "Sunken_Disco_Floor.mp3",
    "Driftwood_and_Glass.mp3",
    "Lobby_Reef.mp3",
    "Aquarium_Hours.mp3",
    "Blue_Hour_Atrium.mp3",
]

# Custom event fired by pygame when a music track ends.
MUSIC_END_EVENT: int = pygame.USEREVENT + 10

# Win98 palette
_GRAY  = (192, 192, 192)
_LIGHT = (255, 255, 255)
_DARK  = (64,  64,  64)
_MID   = (128, 128, 128)
_PANEL = (180, 180, 180)
_BLUE        = (0,   0,   100)
_DIM         = (100, 100, 100)
_TITLE_DARK  = (0,   0,   128)
_TITLE_LIGHT = (16, 132,  208)


def _bevel(surf: pygame.Surface, r: pygame.Rect, pressed: bool = False) -> None:
    tl = _DARK  if pressed else _LIGHT
    br = _LIGHT if pressed else _DARK
    pygame.draw.line(surf, tl, r.topleft, (r.right - 1, r.top))
    pygame.draw.line(surf, tl, r.topleft, (r.left, r.bottom - 1))
    pygame.draw.line(surf, br, (r.right - 1, r.top), (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, br, (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1))


class MusicPlayer:
    """Streams background music with a compact mini-player HUD.

    All public methods are safe to call even when the mixer is unavailable or
    no tracks exist — they silently become no-ops.
    """

    _BTN = 26   # button width/height in the player panel
    _PAD = 4    # inner padding between controls

    def __init__(self, font: pygame.font.Font) -> None:
        self._font          = font
        self._ok            = False
        self._volume        = 0.25
        self._muted         = False
        self._playing       = False
        self._loop          = False
        self._order: list[int] = list(range(len(MUSIC_TRACKS)))
        random.shuffle(self._order)
        self._idx           = 0   # index into self._order

        self.player_visible = False

        # Computed rects (updated in draw / handle_event)
        self._close_btn   = pygame.Rect(0, 0, 0, 0)
        self._panel_rect  = pygame.Rect(0, 0, 0, 0)
        self._prev_btn    = pygame.Rect(0, 0, 0, 0)
        self._pp_btn      = pygame.Rect(0, 0, 0, 0)
        self._next_btn    = pygame.Rect(0, 0, 0, 0)
        self._loop_btn    = pygame.Rect(0, 0, 0, 0)
        self._mute_btn    = pygame.Rect(0, 0, 0, 0)
        self._vol_rect    = pygame.Rect(0, 0, 0, 0)
        self._vol_dragging = False
        self._held_btn: str | None = None          # button held on mousedown
        self._press_overlay: pygame.Surface | None = None  # semi-transparent press overlay

        # Panel drag state (user can reposition the player by dragging its title bar)
        self._panel_dragging   = False
        self._panel_drag_off   = (0, 0)   # mouse offset from panel topleft at drag start
        self._panel_user_pos: tuple[int, int] | None = None  # None = use default anchor

        # Track-name marquee scroll
        self._name_scroll_x    = 0.0      # current left-scroll offset in pixels
        self._name_last_ms     = 0        # pygame.time.get_ticks() at last draw
        self._name_scroll_wait = 2.0      # seconds idle before scrolling starts
        self._name_idle_accum  = 0.0      # time accumulated in idle phase

        # Sprite-based controls (loaded lazily on first draw)
        self._ctrl_prev:  pygame.Surface | None = None
        self._ctrl_play:  pygame.Surface | None = None
        self._ctrl_pause: pygame.Surface | None = None
        self._ctrl_next:  pygame.Surface | None = None
        self._ctrl_loop:  pygame.Surface | None = None
        self._ctrl_moff:  pygame.Surface | None = None
        self._ctrl_mon:   pygame.Surface | None = None
        self._ctrl_slbg:  pygame.Surface | None = None
        self._ctrl_thumb: pygame.Surface | None = None
        self._ctrl_loaded = False

        self._init()

    # ------------------------------------------------------------------ init

    def _init(self) -> None:
        if not pygame.mixer.get_init():
            return
        available = [i for i, t in enumerate(MUSIC_TRACKS) if (_AUDIO / t).exists()]
        if not available:
            return
        self._order = available
        random.shuffle(self._order)
        self._idx = 0
        try:
            pygame.mixer.music.set_endevent(MUSIC_END_EVENT)
        except Exception:
            return
        self._ok = True
        self._apply_volume()

    def _load_ctrl_sprites(self, btn_h: int) -> None:
        """Load and scale music-control sprites from music_controls.png."""
        self._ctrl_loaded = True
        self._thumb_h = btn_h  # default; updated below if sheet loads
        try:
            sheet = pygame.image.load(str(_MC_SPRITES)).convert_alpha()
        except Exception:
            return

        def _sq(rx, ry, rw, rh) -> pygame.Surface:
            sub = sheet.subsurface(pygame.Rect(rx, ry, rw, rh)).copy()
            return pygame.transform.smoothscale(sub, (btn_h, btn_h))

        self._ctrl_prev  = _sq(*_MC_PREV)
        self._ctrl_play  = _sq(*_MC_PLAY)
        self._ctrl_pause = _sq(*_MC_PAUSE)
        self._ctrl_next  = _sq(*_MC_NEXT)
        self._ctrl_loop  = _sq(*_MC_LOOP)
        self._ctrl_moff  = _sq(*_MC_MOFF)
        self._ctrl_mon   = _sq(*_MC_MON)
        # Slider background: scale height to btn_h, keep aspect ratio for width
        slbg_sub = sheet.subsurface(pygame.Rect(*_MC_SLBG)).copy()
        sl_w = max(24, int(_MC_SLBG[2] * btn_h / max(1, _MC_SLBG[3])))
        self._ctrl_slbg = pygame.transform.smoothscale(slbg_sub, (sl_w, btn_h))
        # Thumb knob: scale to ~60% of btn_h to look proportionate on the slider
        thumb_sub = sheet.subsurface(pygame.Rect(*_MC_THUMB)).copy()
        th_h = max(4, int(btn_h * 0.60))
        th_w = max(4, int(_MC_THUMB[2] * th_h / max(1, _MC_THUMB[3])))
        self._ctrl_thumb = pygame.transform.smoothscale(thumb_sub, (th_w, th_h))
        self._thumb_h = th_h  # store for vertical centering in draw()

    # ------------------------------------------------------------------ volume

    def _apply_volume(self) -> None:
        v = 0.0 if self._muted else self._volume
        try:
            pygame.mixer.music.set_volume(v)
        except Exception:
            pass

    def set_volume(self, v: float) -> None:
        v = max(0.0, min(1.0, float(v)))
        if v != self._volume:
            self._volume = v
            self._apply_volume()

    def set_muted(self, muted: bool) -> None:
        muted = bool(muted)
        if muted != self._muted:
            self._muted = muted
            self._apply_volume()

    # ------------------------------------------------------------------ playback

    def _load_and_play(self) -> None:
        """Load and play the current track (by self._idx into self._order)."""
        if not self._ok:
            return
        # Iterate instead of recurse so missing tracks can't overflow the stack.
        for _ in range(len(self._order)):
            path = _AUDIO / MUSIC_TRACKS[self._order[self._idx]]
            if path.exists():
                try:
                    pygame.mixer.music.load(str(path))
                    pygame.mixer.music.play()
                    self._playing = True
                except Exception:
                    pass
                return
            # Skip missing track — advance to next
            self._idx = (self._idx + 1) % len(self._order)

    def start(self) -> None:
        """Start playing from the beginning.  Call once after pygame is ready."""
        if not self._ok or self._playing:
            return
        self._load_and_play()

    def play_pause(self) -> None:
        if not self._ok:
            return
        if self._playing:
            try:
                pygame.mixer.music.pause()
            except Exception:
                pass
            self._playing = False
        else:
            try:
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.unpause()
                else:
                    self._load_and_play()
                    return
            except Exception:
                pass
            self._playing = True

    def next_track(self) -> None:
        if not self._ok:
            return
        self._idx = (self._idx + 1) % len(self._order)
        if self._idx == 0:
            random.shuffle(self._order)
        self._name_scroll_x = 0.0
        self._name_idle_accum = 0.0
        self._load_and_play()

    def prev_track(self) -> None:
        if not self._ok:
            return
        self._idx = (self._idx - 1) % len(self._order)
        self._name_scroll_x = 0.0
        self._name_idle_accum = 0.0
        self._load_and_play()

    def on_track_end(self) -> None:
        """Call when MUSIC_END_EVENT fires."""
        if not self._ok or not self._playing:
            return
        if self._loop:
            self._load_and_play()
        else:
            self._idx = (self._idx + 1) % len(self._order)
            if self._idx == 0:
                random.shuffle(self._order)
            self._load_and_play()

    def current_track_name(self) -> str:
        """Return current track name with underscores replaced by spaces, no extension."""
        if not self._order:
            return "No tracks"
        name = MUSIC_TRACKS[self._order[self._idx]]
        if name.lower().endswith(".mp3"):
            name = name[:-4]
        return name.replace("_", " ")

    def now_playing_text(self) -> str:
        """Return '\u266a Track Name' when audibly playing, else empty string."""
        if self._playing and not self._muted and self._ok:
            return f"\u266a {self.current_track_name()}"
        return ""

    # ------------------------------------------------------------------ events

    def handle_event(self, ev: pygame.event.Event) -> bool:
        """Handle a pygame event.  Returns True if the event was consumed."""
        # Track-end notification (not a user-initiated event — don't consume it)
        if ev.type == MUSIC_END_EVENT:
            self.on_track_end()
            return False

        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            pos = ev.pos
            if not self.player_visible:
                return False
            if self._close_btn.inflate(4, 4).collidepoint(pos):
                self.player_visible = False
                return True
            # Title-bar drag (area between left edge and close button)
            _tb = pygame.Rect(self._panel_rect.left, self._panel_rect.top,
                              self._panel_rect.w - 24, 22)
            if _tb.collidepoint(pos):
                self._panel_dragging = True
                self._panel_drag_off = (pos[0] - self._panel_rect.left,
                                        pos[1] - self._panel_rect.top)
                return True
            if not self._panel_rect.inflate(4, 4).collidepoint(pos):
                return False
            if self._pp_btn.collidepoint(pos):
                self._held_btn = "pp"
                self.play_pause()
                return True
            if self._prev_btn.collidepoint(pos):
                self._held_btn = "prev"
                self.prev_track()
                return True
            if self._next_btn.collidepoint(pos):
                self._held_btn = "next"
                self.next_track()
                return True
            if self._loop_btn.collidepoint(pos):
                self._held_btn = "loop"
                self._loop = not self._loop
                return True
            if self._mute_btn.collidepoint(pos):
                self._held_btn = "mute"
                self.set_muted(not self._muted)
                return True
            if self._vol_rect.inflate(0, 10).collidepoint(pos):
                self._vol_dragging = True
                self._set_vol_from_x(pos[0])
                return True
            return True  # consume interior clicks

        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            self._held_btn = None
            consumed = False
            if self._vol_dragging:
                self._vol_dragging = False
                consumed = True
            if self._panel_dragging:
                self._panel_dragging = False
                consumed = True
            return consumed

        if ev.type == pygame.MOUSEMOTION:
            if self._vol_dragging:
                self._set_vol_from_x(ev.pos[0])
                return True
            if self._panel_dragging:
                sw, sh = pygame.display.get_surface().get_size()
                from .renderer import PAD_B  # deferred import
                nx = max(0, min(sw - 310, ev.pos[0] - self._panel_drag_off[0]))
                ny = max(0, min(sh - 54 - PAD_B, ev.pos[1] - self._panel_drag_off[1]))
                self._panel_user_pos = (nx, ny)
                return True

        return False

    def _set_vol_from_x(self, x: int) -> None:
        t = (x - self._vol_rect.left) / max(1, self._vol_rect.w)
        self.set_volume(max(0.0, min(1.0, t)))

    # ------------------------------------------------------------------ draw

    def draw(self, surface: pygame.Surface) -> None:
        """Draw the floating Win98 music player panel (when visible)."""
        if not self.player_visible:
            return
        from .renderer import PAD_B, PAD_R   # deferred to avoid circular import
        w, h = surface.get_size()

        _TB_H = 18   # title bar height
        PW    = 310  # panel width
        PH    = 54   # panel total height
        B     = self._BTN   # button size (36)
        PAD   = self._PAD   # inner gap (4)

        # Default anchor: bottom-right above status bar
        default_px = max(0, w - PAD_R - PW)
        default_py = h - PAD_B - PH - 2
        # Use user-dragged position if set, clamped to screen
        if self._panel_user_pos is not None:
            px = max(0, min(w - PW, self._panel_user_pos[0]))
            py = max(0, min(h - PH, self._panel_user_pos[1]))
            self._panel_user_pos = (px, py)
        else:
            px, py = default_px, default_py
        self._panel_rect = pygame.Rect(px, py, PW, PH)

        # ── Panel chrome ────────────────────────────────────────────────
        pygame.draw.rect(surface, _GRAY, self._panel_rect)
        _bevel(surface, self._panel_rect)

        # ── Title bar gradient ───────────────────────────────────────────
        tb = pygame.Rect(px + 2, py + 2, PW - 4, _TB_H)
        for i in range(tb.w):
            t  = i / max(1, tb.w - 1)
            rc = int(_TITLE_DARK[0] + (_TITLE_LIGHT[0] - _TITLE_DARK[0]) * t)
            gc = int(_TITLE_DARK[1] + (_TITLE_LIGHT[1] - _TITLE_DARK[1]) * t)
            bc = int(_TITLE_DARK[2] + (_TITLE_LIGHT[2] - _TITLE_DARK[2]) * t)
            pygame.draw.line(surface, (rc, gc, bc),
                             (tb.left + i, tb.top), (tb.left + i, tb.bottom - 1))
        if self._font is not None:
            ts = self._font.render("\u266a Music Player", True, _LIGHT)
            surface.blit(ts, (tb.left + 3, tb.top + (tb.h - ts.get_height()) // 2))

        # Close button — red Win98 style matching other panels
        cbw = _TB_H - 4
        self._close_btn = pygame.Rect(tb.right - cbw - 2,
                                      tb.top + (_TB_H - cbw) // 2, cbw, cbw)
        pygame.draw.rect(surface, (180, 80, 80), self._close_btn)
        _bevel(surface, self._close_btn)
        if self._font is not None:
            xs = self._font.render("x", True, _LIGHT)
            surface.blit(xs, (
                self._close_btn.left + (cbw - xs.get_width()) // 2,
                self._close_btn.top  + (cbw - xs.get_height()) // 2))

        # ── Controls body ────────────────────────────────────────────────
        body_top = py + 2 + _TB_H + 2
        body_h   = PH - 2 - _TB_H - 4
        cy       = body_top + body_h // 2
        sl_top   = cy - B // 2

        # Load sprites on first draw call
        if not self._ctrl_loaded:
            self._load_ctrl_sprites(B)

        # Semi-transparent pressed overlay (created/resized as needed)
        if self._press_overlay is None or self._press_overlay.get_size() != (B, B):
            self._press_overlay = pygame.Surface((B, B), pygame.SRCALPHA)
            self._press_overlay.fill((0, 0, 0, 80))

        # Layout controls right-to-left from panel right edge ───────────────

        # Volume slider background sprite (or fallback)
        vol_w = self._ctrl_slbg.get_width() if self._ctrl_slbg else 44
        bx = self._panel_rect.right - 2 - PAD - vol_w
        self._vol_rect = pygame.Rect(bx, sl_top, vol_w, B)
        if self._ctrl_slbg:
            surface.blit(self._ctrl_slbg, self._vol_rect.topleft)
        else:
            tr_r = pygame.Rect(bx, cy - 4, vol_w, 8)
            pygame.draw.rect(surface, _MID, tr_r)
            pygame.draw.line(surface, _DARK, tr_r.topleft, (tr_r.right, tr_r.top))
            pygame.draw.line(surface, _LIGHT, (tr_r.left, tr_r.bottom), (tr_r.right, tr_r.bottom))
        # Thumb knob (vertically centred on slider)
        vol_t = self._volume if not self._muted else 0.0
        if self._ctrl_thumb:
            th_h = getattr(self, '_thumb_h', B)
            th_w = self._ctrl_thumb.get_width()
            kx = bx + int(vol_t * max(1, vol_w - th_w))
            ky = sl_top + (B - th_h) // 2
            surface.blit(self._ctrl_thumb, (kx, ky))
        else:
            kx = bx + int(vol_t * vol_w)
            k = pygame.Rect(kx - 3, sl_top - 2, 6, B + 4)
            pygame.draw.rect(surface, _GRAY, k)
            _bevel(surface, k)

        # Mute button
        bx -= PAD + B
        self._mute_btn = pygame.Rect(bx, sl_top, B, B)
        mute_spr = self._ctrl_moff if self._muted else self._ctrl_mon
        if mute_spr:
            surface.blit(mute_spr, self._mute_btn.topleft)
            if self._muted or self._held_btn == "mute":
                surface.blit(self._press_overlay, self._mute_btn.topleft)
        else:
            pygame.draw.rect(surface, _GRAY, self._mute_btn)
            _bevel(surface, self._mute_btn, pressed=self._muted)
            self._draw_speaker(surface, self._mute_btn.centerx, self._mute_btn.centery,
                               muted=self._muted)

        # Loop button
        bx -= PAD + B
        self._loop_btn = pygame.Rect(bx, sl_top, B, B)
        if self._ctrl_loop:
            surface.blit(self._ctrl_loop, self._loop_btn.topleft)
            if self._loop or self._held_btn == "loop":
                surface.blit(self._press_overlay, self._loop_btn.topleft)
        else:
            pygame.draw.rect(surface, _GRAY, self._loop_btn)
            _bevel(surface, self._loop_btn, pressed=self._loop)
            lc = (0, 0, 160) if self._loop else (80, 80, 80)
            lx, ly = self._loop_btn.centerx, self._loop_btn.centery
            try:
                pygame.draw.arc(surface, lc, (lx - 4, ly - 4, 9, 9),
                                math.radians(20), math.radians(170), 1)
                pygame.draw.arc(surface, lc, (lx - 4, ly - 4, 9, 9),
                                math.radians(200), math.radians(350), 1)
            except Exception:
                pass
            pygame.draw.line(surface, lc, (lx + 4, ly - 1), (lx + 4, ly + 3), 1)
            pygame.draw.line(surface, lc, (lx - 4, ly - 3), (lx - 4, ly + 1), 1)

        # Next track button
        bx -= PAD + B
        self._next_btn = pygame.Rect(bx, sl_top, B, B)
        if self._ctrl_next:
            surface.blit(self._ctrl_next, self._next_btn.topleft)
            if self._held_btn == "next":
                surface.blit(self._press_overlay, self._next_btn.topleft)
        else:
            pygame.draw.rect(surface, _GRAY, self._next_btn)
            _bevel(surface, self._next_btn, pressed=self._held_btn == "next")
            nx = self._next_btn.centerx - 2
            ny = self._next_btn.centery
            pygame.draw.polygon(surface, _DARK, [(nx - 3, ny - 4), (nx + 1, ny), (nx - 3, ny + 4)])
            pygame.draw.line(surface, _DARK, (nx + 2, ny - 4), (nx + 2, ny + 4), 1)

        # Play / Pause button
        bx -= PAD + B
        self._pp_btn = pygame.Rect(bx, sl_top, B, B)
        pp_spr = self._ctrl_pause if self._playing else self._ctrl_play
        if pp_spr:
            surface.blit(pp_spr, self._pp_btn.topleft)
            if self._held_btn == "pp":
                surface.blit(self._press_overlay, self._pp_btn.topleft)
        else:
            pygame.draw.rect(surface, _GRAY, self._pp_btn)
            _bevel(surface, self._pp_btn, pressed=self._held_btn == "pp")
            pc  = self._pp_btn.centerx
            pcy = self._pp_btn.centery
            if self._playing:
                pygame.draw.rect(surface, _DARK, (pc - 4, pcy - 4, 3, 8))
                pygame.draw.rect(surface, _DARK, (pc + 1, pcy - 4, 3, 8))
            else:
                pygame.draw.polygon(surface, _DARK,
                                    [(pc - 3, pcy - 5), (pc + 4, pcy), (pc - 3, pcy + 5)])

        # Prev track button
        bx -= PAD + B
        self._prev_btn = pygame.Rect(bx, sl_top, B, B)
        if self._ctrl_prev:
            surface.blit(self._ctrl_prev, self._prev_btn.topleft)
            if self._held_btn == "prev":
                surface.blit(self._press_overlay, self._prev_btn.topleft)
        else:
            pygame.draw.rect(surface, _GRAY, self._prev_btn)
            _bevel(surface, self._prev_btn, pressed=self._held_btn == "prev")
            prx = self._prev_btn.centerx + 2
            pry = self._prev_btn.centery
            pygame.draw.polygon(surface, _DARK, [(prx + 3, pry - 4), (prx - 1, pry), (prx + 3, pry + 4)])
            pygame.draw.line(surface, _DARK, (prx - 2, pry - 4), (prx - 2, pry + 4), 1)

        # Track name in remaining left area — scrolling marquee if too wide
        name_area_right = bx - PAD
        name_area_left  = px + PAD + 4
        name_w = name_area_right - name_area_left
        if name_w > 10:
            name = self.current_track_name() if self._ok else "No tracks"
            ns = self._font.render(name, True, (0, 0, 60))
            clip = pygame.Rect(name_area_left, body_top, name_w, body_h)
            old_clip = surface.get_clip()
            surface.set_clip(clip)
            text_y = cy - ns.get_height() // 2

            if ns.get_width() <= name_w:
                # Text fits — no scroll needed; reset scroll state
                self._name_scroll_x = 0.0
                self._name_idle_accum = 0.0
                surface.blit(ns, (name_area_left, text_y))
            else:
                # Text wider than area — scroll marquee
                now_ms = pygame.time.get_ticks()
                dt_ms  = now_ms - self._name_last_ms if self._name_last_ms else 0
                dt_s   = min(0.1, dt_ms / 1000.0)   # cap to avoid large jumps after resume

                if self._name_idle_accum < self._name_scroll_wait:
                    # Idle pause before scrolling begins
                    self._name_idle_accum += dt_s
                    self._name_scroll_x = 0.0
                else:
                    scroll_speed = 40.0   # pixels per second
                    self._name_scroll_x += scroll_speed * dt_s
                    # When the text has scrolled fully past, reset with a pause
                    if self._name_scroll_x > ns.get_width() + 20:
                        self._name_scroll_x = 0.0
                        self._name_idle_accum = 0.0

                surface.blit(ns, (name_area_left - int(self._name_scroll_x), text_y))

            self._name_last_ms = pygame.time.get_ticks()
            surface.set_clip(old_clip)

    @staticmethod
    def _draw_speaker(surf: pygame.Surface, cx: int, cy: int,
                      muted: bool = False) -> None:
        """Minimal pixel-art speaker icon."""
        col = (160, 0, 0) if muted else (0, 0, 80)
        # Speaker cone body (triangle pointing right → left)
        pygame.draw.polygon(surf, col,
                            [(cx - 4, cy - 2), (cx - 1, cy - 2),
                             (cx + 1, cy - 4), (cx + 1, cy + 4),
                             (cx - 1, cy + 2), (cx - 4, cy + 2)])
        if muted:
            pygame.draw.line(surf, (200, 0, 0), (cx + 1, cy - 3), (cx + 5, cy + 3), 1)
        else:
            # Sound wave arc
            try:
                pygame.draw.arc(surf, col, (cx, cy - 3, 5, 6),
                                math.radians(-60), math.radians(60), 1)
            except Exception:
                pass
