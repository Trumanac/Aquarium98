"""splash.py — Startup splash screen for Aquarium 98.

Displays SplashScreen.png in a centred borderless window at half its native
size.  Fades out smoothly after _HOLD_SECS, or immediately on mouse click /
key press.  Caller must ensure pygame.display.init() has been called first.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pygame

SPLASH_PATH = Path(__file__).resolve().parent.parent / "assets" / "icon" / "SplashScreen.png"

_HOLD_SECS = 1.5   # seconds at full opacity before the fade begins
_FADE_SECS = 0.6   # seconds for the dissolve-out


def show_splash() -> None:
    """Show the splash in a temporary centred window, then return.

    The caller should call win_mod.init_window() immediately after so the
    game window replaces the splash.  Silently skips if the image is missing.
    """
    if not SPLASH_PATH.exists():
        return

    # Load WITHOUT .convert() first — we need dimensions before set_mode(),
    # but .convert() requires an active display surface.
    try:
        img_raw = pygame.image.load(str(SPLASH_PATH))
    except Exception:   # noqa: BLE001
        return

    iw, ih = img_raw.get_size()
    # Display at half native size — fits comfortably on any modern desktop
    sw, sh = iw // 2, ih // 2

    # Centre on primary display -----------------------------------------------
    try:
        sizes = pygame.display.get_desktop_sizes()
        desk_w, desk_h = sizes[0] if sizes else (1920, 1080)
    except Exception:   # noqa: BLE001
        info = pygame.display.Info()
        desk_w = info.current_w or 1920
        desk_h = info.current_h or 1080

    cx = max(0, (desk_w - sw) // 2)
    cy = max(0, (desk_h - sh) // 2)

    # Stash whatever SDL_VIDEO_WINDOW_POS the caller had set so we can restore it
    _prev_pos = os.environ.get("SDL_VIDEO_WINDOW_POS")
    os.environ["SDL_VIDEO_WINDOW_POS"] = f"{cx},{cy}"

    surface = pygame.display.set_mode((sw, sh), pygame.NOFRAME)
    pygame.display.set_caption("Aquarium 98")

    # Now that the display surface exists, convert and scale the image
    img = pygame.transform.smoothscale(img_raw.convert(), (sw, sh))

    clock = pygame.time.Clock()
    start = time.monotonic()
    done  = False

    while not done:
        for ev in pygame.event.get():
            if ev.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN, pygame.QUIT):
                done = True
                break

        elapsed = time.monotonic() - start
        if elapsed >= _HOLD_SECS + _FADE_SECS:
            break

        # Full opacity for _HOLD_SECS, then linear dissolve to transparent
        if elapsed < _HOLD_SECS:
            alpha = 255
        else:
            progress = (elapsed - _HOLD_SECS) / _FADE_SECS
            alpha = max(0, int(255 * (1.0 - progress)))

        surface.fill((0, 0, 0))
        img.set_alpha(alpha)
        surface.blit(img, (0, 0))
        pygame.display.flip()
        clock.tick(30)

    # Restore previous window-position env var so init_window() places the
    # game window at the user's saved position.
    if _prev_pos is not None:
        os.environ["SDL_VIDEO_WINDOW_POS"] = _prev_pos
    else:
        os.environ.pop("SDL_VIDEO_WINDOW_POS", None)
