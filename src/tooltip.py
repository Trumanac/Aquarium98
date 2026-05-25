"""tooltip.py — Win98-style hover tooltip system for Aquarium 98.

Usage:
    tooltip = Tooltip()
    # each frame:
    tooltip.clear_regions()
    tooltip.register(pygame.Rect(...), "Some hint text")
    tooltip.update(dt, mouse_pos)
    tooltip.draw(surface, font)   # call last, drawn on top of everything
"""
from __future__ import annotations

import pygame

_DELAY  = 1.3    # seconds before tooltip appears
_BG     = (255, 255, 225)
_FG     = (0, 0, 0)
_BORDER = (128, 128, 128)


class Tooltip:
    def __init__(self) -> None:
        self._regions: list[tuple[pygame.Rect, str]] = []
        self._active   = ""          # text of hovered region (or "")
        self._timer    = 0.0
        self._show_pos = (0, 0)      # mouse pos when tooltip first triggered

    def clear_regions(self) -> None:
        """Call at the start of each frame before registering new regions."""
        self._regions.clear()

    def register(self, rect: pygame.Rect, text: str) -> None:
        """Register one tooltip zone for this frame."""
        self._regions.append((rect, text))

    def update(self, dt: float, mouse_pos: tuple[int, int]) -> None:
        """Advance hover timer. Call once per frame."""
        found = ""
        for rect, text in self._regions:
            if rect.collidepoint(mouse_pos):
                found = text
                break

        if found != self._active:
            self._active = found
            self._timer  = 0.0
            self._show_pos = mouse_pos
        elif found:
            self._timer += dt

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        """Draw the tooltip if the hover delay has elapsed."""
        if not self._active or self._timer < _DELAY:
            return

        mx, my = pygame.mouse.get_pos()

        pad   = 4
        lines = self._active.split("\n")
        lh    = font.get_height() + 2
        box_w = max(font.size(ln)[0] for ln in lines) + pad * 2
        box_h = lh * len(lines) + pad * 2 - 2

        sw, sh = surface.get_size()
        tx = min(mx + 14, sw - box_w - 2)
        ty = min(my + 18, sh - box_h - 2)
        ty = max(2, ty)
        tx = max(2, tx)

        pygame.draw.rect(surface, _BG,     (tx, ty, box_w, box_h))
        pygame.draw.rect(surface, _BORDER, (tx, ty, box_w, box_h), 1)

        for i, ln in enumerate(lines):
            ts = font.render(ln, True, _FG)
            surface.blit(ts, (tx + pad, ty + pad + i * lh))
