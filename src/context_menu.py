"""
context_menu.py — pygame-rendered Win98-style right-click menu.

No native dialogs (would require tkinter/Qt). Stateful: returns the chosen
action string on click, or None if dismissed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pygame

WIN_GRAY = (192, 192, 192)
WIN_LIGHT = (255, 255, 255)
WIN_DARK = (64, 64, 64)
WIN_MID = (128, 128, 128)
HILITE = (0, 0, 128)
HILITE_FG = (255, 255, 255)


@dataclass
class MenuItem:
    label: str
    action: str | None      # None = separator/header
    checked: bool = False
    enabled: bool = True
    submenu: list | None = None   # list[MenuItem]


def feed_menu() -> list[MenuItem]:
    return [
        MenuItem("Pause Simulation",   "pause",         False),
        MenuItem("---", None),
        MenuItem("Feed Fish",          "feed"),
        MenuItem("Clean Tank",         "clean"),
        MenuItem("Fish List",          "fish_list"),
        MenuItem("Fish Shoppe",        "fish_store"),
        MenuItem("---", None),
        MenuItem("Event Log",          "event_log"),
        MenuItem("Achievements",       "achievements"),
        MenuItem("Encyclopaedia",      "encyclopedia"),
        MenuItem("Fish Memorial",      "graveyard"),
        MenuItem("---", None),
        MenuItem("Lock in Place",      "toggle_lock",   False),
        MenuItem("Always on Top",      "toggle_top",    False),
        MenuItem("Pause When Hidden",  "toggle_phide",  True),
        MenuItem("Show Fish Names",    "toggle_names",  False),
        MenuItem("Show Fish Moods",    "toggle_moods",  False),
        MenuItem("Mute Sounds",        "toggle_mute",   False),
        MenuItem("---", None),
        MenuItem("Opacity",            None,            submenu=[
            MenuItem("100%", "op_100"),
            MenuItem(" 90%", "op_90"),
            MenuItem(" 75%", "op_75"),
            MenuItem(" 50%", "op_50"),
            MenuItem(" 30%", "op_30"),
        ]),
        MenuItem("How to Play...",     "how_to_play"),
        MenuItem("About Aquarium 98...", "about"),
        MenuItem("Settings...",        "settings"),
        MenuItem("---", None),
        MenuItem("Minimize to Tray",   "tray"),
        MenuItem("Quit",               "quit"),
    ]


class ContextMenu:
    """Owns its own draw + event handling. Active while .visible is True."""

    def __init__(self, font: pygame.font.Font):
        self.font = font
        self.items: list[MenuItem] = []
        self.x = 0
        self.y = 0
        self.visible = False
        self.hover = -1
        self.open_submenu_idx = -1
        self.submenu_hover = -1
        self._item_h = font.get_height() + 6
        self._padding_x = 18
        self._screen_w = 0
        self._screen_h = 0

    def open(self, items: list[MenuItem], x: int, y: int,
             screen_size: tuple[int, int]) -> None:
        self.items = items
        self.hover = -1
        self.open_submenu_idx = -1
        self.submenu_hover = -1
        w, h = self._measure(items)
        sw, sh = screen_size
        self._screen_w = sw
        self._screen_h = sh
        # Flip left if menu would overflow right edge; flip up if it overflows bottom
        self.x = x if x + w <= sw else max(0, x - w)
        self.y = y if y + h <= sh else max(0, y - h)
        self._w, self._h = w, h
        self.visible = True

    def close(self) -> None:
        self.visible = False

    def _measure(self, items: list[MenuItem]) -> tuple[int, int]:
        max_w = 0
        for it in items:
            if it.action is None and it.label == "---":
                continue
            w = self.font.size(it.label)[0]
            if it.submenu:
                w += 16
            max_w = max(max_w, w)
        w = max_w + self._padding_x * 2 + 14
        h = 0
        for it in items:
            if it.action is None and it.label == "---":
                h += 6
            else:
                h += self._item_h
        h += 6
        return w, h

    def handle_event(self, ev: pygame.event.Event) -> bool | Optional[str]:
        if not self.visible:
            return None
        if ev.type == pygame.MOUSEMOTION:
            self._update_hover(ev.pos)
            return self._point_in_menu(ev.pos)
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if not self._point_in_menu(ev.pos):
                self.close()
                return False
            self._update_hover(ev.pos)
            if self.open_submenu_idx >= 0 and self.submenu_hover >= 0:
                sub = self.items[self.open_submenu_idx].submenu
                if sub:
                    act = sub[self.submenu_hover].action
                    self.close()
                    return act
            if 0 <= self.hover < len(self.items):
                it = self.items[self.hover]
                if it.submenu:
                    self.open_submenu_idx = self.hover
                    return True
                if it.action is not None and it.enabled:
                    self.close()
                    return it.action
            return True
        elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.close()
            return True
        return False

    def _point_in_menu(self, pos) -> bool:
        if self.x <= pos[0] <= self.x + self._w and self.y <= pos[1] <= self.y + self._h:
            return True
        # Check open submenu rect
        if self.open_submenu_idx >= 0:
            sub_rect = self._submenu_rect()
            if sub_rect.collidepoint(pos):
                return True
        return False

    def _submenu_rect(self) -> pygame.Rect:
        sub = self.items[self.open_submenu_idx].submenu or []
        sw, sh = self._measure(sub)
        # Prefer opening to the right; flip left if it would go off-screen
        right_x = self.x + self._w - 2
        left_x  = self.x - sw + 2
        if self._screen_w > 0 and right_x + sw > self._screen_w:
            sx = max(0, left_x)
        else:
            sx = right_x
        # Anchor vertically to the hovered row; clamp so it stays on screen
        row_y = self.y + self._row_y(self.open_submenu_idx)
        if self._screen_h > 0 and row_y + sh > self._screen_h:
            sy = max(0, self._screen_h - sh)
        else:
            sy = row_y
        return pygame.Rect(sx, sy, sw, sh)

    def _row_y(self, idx: int) -> int:
        y = 3
        for i, it in enumerate(self.items):
            if i == idx:
                return y
            if it.action is None and it.label == "---":
                y += 6
            else:
                y += self._item_h
        return y

    def _update_hover(self, pos) -> None:
        self.hover = -1
        self.submenu_hover = -1
        if self.x <= pos[0] <= self.x + self._w:
            rel_y = pos[1] - self.y - 3
            y = 0
            for i, it in enumerate(self.items):
                row_h = 6 if (it.action is None and it.label == "---") else self._item_h
                if y <= rel_y < y + row_h:
                    if it.action is not None or it.submenu:
                        self.hover = i
                    break
                y += row_h
            # Auto-open submenu when hovering its parent
            if self.hover >= 0 and self.items[self.hover].submenu:
                self.open_submenu_idx = self.hover
            elif self.hover >= 0 and not self.items[self.hover].submenu:
                self.open_submenu_idx = -1
        if self.open_submenu_idx >= 0:
            sub_rect = self._submenu_rect()
            if sub_rect.collidepoint(pos):
                sub = self.items[self.open_submenu_idx].submenu or []
                rel_y = pos[1] - sub_rect.top - 3
                y = 0
                for i, it in enumerate(sub):
                    row_h = 6 if (it.action is None and it.label == "---") else self._item_h
                    if y <= rel_y < y + row_h:
                        if it.action is not None:
                            self.submenu_hover = i
                        break
                    y += row_h

    def draw(self, screen: pygame.Surface) -> None:
        if not self.visible:
            return
        rect = pygame.Rect(self.x, self.y, self._w, self._h)
        self._draw_panel(screen, rect, self.items, self.hover)
        if self.open_submenu_idx >= 0:
            sub = self.items[self.open_submenu_idx].submenu or []
            sub_rect = self._submenu_rect()
            self._draw_panel(screen, sub_rect, sub, self.submenu_hover)

    def _draw_panel(self, screen: pygame.Surface, rect: pygame.Rect,
                    items: list[MenuItem], hover_idx: int) -> None:
        pygame.draw.rect(screen, WIN_GRAY, rect)
        pygame.draw.line(screen, WIN_LIGHT, rect.topleft,
                         (rect.right - 1, rect.top))
        pygame.draw.line(screen, WIN_LIGHT, rect.topleft,
                         (rect.left, rect.bottom - 1))
        pygame.draw.line(screen, WIN_DARK,
                         (rect.right - 1, rect.top), (rect.right - 1, rect.bottom - 1))
        pygame.draw.line(screen, WIN_DARK,
                         (rect.left, rect.bottom - 1), (rect.right - 1, rect.bottom - 1))

        y = rect.top + 3
        for i, it in enumerate(items):
            if it.action is None and it.label == "---":
                pygame.draw.line(screen, WIN_MID,
                                 (rect.left + 4, y + 2),
                                 (rect.right - 5, y + 2))
                pygame.draw.line(screen, WIN_LIGHT,
                                 (rect.left + 4, y + 3),
                                 (rect.right - 5, y + 3))
                y += 6
                continue
            row = pygame.Rect(rect.left + 2, y, rect.w - 4, self._item_h)
            if i == hover_idx:
                pygame.draw.rect(screen, HILITE, row)
                fg = HILITE_FG
            else:
                fg = (0, 0, 0) if it.enabled else WIN_MID
            tx = row.left + self._padding_x
            if it.checked:
                # Draw a checkmark glyph
                cx = rect.left + 6
                cy = row.top + self._item_h // 2
                pygame.draw.line(screen, fg, (cx, cy), (cx + 3, cy + 3), 2)
                pygame.draw.line(screen, fg, (cx + 3, cy + 3), (cx + 8, cy - 3), 2)
            lbl = self.font.render(it.label, True, fg)
            screen.blit(lbl, (tx, row.top + (self._item_h - lbl.get_height()) // 2))
            if it.submenu:
                # Right-pointing triangle
                ax = rect.right - 10
                ay = row.top + self._item_h // 2
                pygame.draw.polygon(screen, fg, [(ax, ay - 4), (ax, ay + 4), (ax + 5, ay)])
            y += self._item_h
