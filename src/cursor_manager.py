"""
cursor_manager.py — Animated custom cursor for Aquarium 98.

Three cursor modes:
    'normal'  — diving glove (default pointer)
    'feed'    — fish food shaker
    'clean'   — cleaning sponge

Each PNG sprite sheet (384 × 2443 px) contains 5 frames stacked vertically.
  Frame 0 = idle pose.
  Frames 1-4 = click animation (~50 ms per frame → 0.2 s total).

The system cursor is hidden; the custom cursor is drawn last each frame.
"""
from __future__ import annotations

import logging

import pygame

_LOG = logging.getLogger("aquarium")

_FRAME_COUNT = 5
_ANIM_SPF    = 0.05   # seconds per frame during click animation
_CURSOR_H    = 48     # scaled sprite height in pixels

# (hx, hy): pixel offset from sprite top-left to the "active" hotspot point.
# Subtracted from mouse position when blitting so the hotspot lands on the cursor.
_HOTSPOTS: dict[str, tuple[int, int]] = {
    "normal": (17, 9),   # glove fingertip (measured from topmost visible pixel)
    "feed":   (22, 4),   # shaker cap top
    "clean":  (10, 8),   # sponge leading corner
}


class CursorManager:
    """Loads cursor sprite sheets and draws the appropriate animated cursor."""

    def __init__(self, ui_dir: str) -> None:
        """
        Parameters
        ----------
        ui_dir : str
            Path to the folder containing Glove.png, Shaker.png, Sponge.png.
        """
        pygame.mouse.set_visible(False)

        self._frames: dict[str, list[pygame.Surface]] = {}
        self._mode       = "normal"
        self._anim_frame = 0
        self._anim_timer = 0.0
        self._animating  = False

        specs = [
            ("normal", "Glove.png"),
            ("feed",   "Shaker.png"),
            ("clean",  "Sponge.png"),
        ]

        for mode, fname in specs:
            path = f"{ui_dir}/{fname}"
            try:
                sheet = pygame.image.load(path).convert_alpha()
            except Exception:
                try:
                    sheet = pygame.image.load(path).convert()
                except Exception as exc:
                    _LOG.warning("Cursor sheet not found — %s: %s", fname, exc)
                    continue

            # Transparent white BG: set colorkey if image has no real alpha data
            if sheet.get_colorkey() is None and not _has_alpha(sheet):
                sheet.set_colorkey((255, 255, 255))

            fh = sheet.get_height() // _FRAME_COUNT
            fw = sheet.get_width()
            scale_w = max(1, int(fw * _CURSOR_H / fh))

            frames: list[pygame.Surface] = []
            for i in range(_FRAME_COUNT):
                raw = sheet.subsurface(pygame.Rect(0, i * fh, fw, fh)).copy()
                scaled = pygame.transform.smoothscale(raw, (scale_w, _CURSOR_H))
                frames.append(scaled)

            self._frames[mode] = frames

    # ------------------------------------------------------------------
    def set_mode(self, mode: str) -> None:
        """Switch cursor mode ('normal', 'feed', or 'clean')."""
        if mode != self._mode:
            self._mode       = mode
            self._anim_frame = 0
            self._anim_timer = 0.0
            self._animating  = False

    def on_click(self) -> None:
        """Trigger the click animation (call on MOUSEBUTTONDOWN)."""
        self._anim_frame = 1
        self._anim_timer = 0.0
        self._animating  = True

    def update(self, dt: float) -> None:
        """Advance the click animation; call each frame with delta-time in seconds."""
        if self._animating:
            self._anim_timer += dt
            if self._anim_timer >= _ANIM_SPF:
                self._anim_timer -= _ANIM_SPF
                self._anim_frame += 1
                if self._anim_frame >= _FRAME_COUNT:
                    self._anim_frame = 0
                    self._animating  = False

    def draw(self, surface: pygame.Surface) -> None:
        """Blit the current cursor frame at the mouse position (call last each frame)."""
        if not pygame.mouse.get_focused():
            return
        frames = self._frames.get(self._mode) or self._frames.get("normal")
        if not frames:
            return
        idx   = self._anim_frame if self._animating else 0
        frame = frames[min(idx, len(frames) - 1)]
        mx, my = pygame.mouse.get_pos()
        hx, hy = _HOTSPOTS.get(self._mode, (0, 0))
        surface.blit(frame, (mx - hx, my - hy))


# ---------------------------------------------------------------------------

def _has_alpha(surface: pygame.Surface) -> bool:
    """Return True if the surface has a real per-pixel alpha channel."""
    return surface.get_masks()[3] != 0
