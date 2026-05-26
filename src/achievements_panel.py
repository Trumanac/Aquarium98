"""
achievements_panel.py — Win98-style achievements checklist panel.

25 achievements stored in cfg["achievements_unlocked"] as a list of string IDs.
Locked achievements display as "???" until unlocked.
Toggle with 'achievements' action.
"""
from __future__ import annotations

import datetime
import pygame

WIN_GRAY  = (192, 192, 192)
WIN_LIGHT = (255, 255, 255)
WIN_DARK  = (64,  64,  64)
TITLE_A   = (0,   0,   128)
TITLE_B   = (16, 132, 208)
PANEL_BG  = (192, 192, 192)
COL_CHECK = (30, 160, 30)
COL_LOCK  = (140, 140, 140)

_TB_H = 18
_PAD  = 6
PW    = 270

# ---------------------------------------------------------------------------
# Achievement definitions
# ---------------------------------------------------------------------------
ACHIEVEMENTS: list[dict] = [
    {"id": "first_steps",     "name": "First Steps",       "desc": "Open the aquarium for the first time."},
    {"id": "rare_encounter",  "name": "Rare Encounter",    "desc": "Witness your first rare fish."},
    {"id": "super_rare",      "name": "Epic Find!",         "desc": "An epic fish graced your tank."},
    {"id": "named_them_all",  "name": "Named Them All",    "desc": "Give every living fish a custom name."},
    {"id": "streak_7",        "name": "7-Day Streak",      "desc": "Open the aquarium 7 days in a row."},
    {"id": "streak_30",       "name": "30-Day Streak",     "desc": "Keep a 30-day opening streak."},
    {"id": "tank_full",       "name": "Tank Full",         "desc": "Reach the maximum fish population."},
    {"id": "ancient_one",     "name": "Ancient One",       "desc": "A fish lives to 30 days old."},
    {"id": "master_breeder",  "name": "Master Breeder",    "desc": "Breed 10 fish total."},
    {"id": "clean_freak",     "name": "Clean Freak",       "desc": "Clean the tank 20 times."},
    {"id": "fish_whisperer",  "name": "Fish Whisperer",    "desc": "Open a fish profile 10 times."},
    {"id": "name_changer",    "name": "Name Changer",      "desc": "Rename a fish."},
    {"id": "night_watcher",   "name": "Night Watcher",     "desc": "Have the aquarium open at midnight."},
    {"id": "collector",       "name": "The Collector",     "desc": "Have 5+ different species simultaneously."},
    {"id": "old_friend",      "name": "Old Friend",        "desc": "Keep the same fish alive for 7 days."},
    {"id": "nightmare_survivor", "name": "Nightmare Survivor", "desc": "Maintain a living tank on Nightmare difficulty for 7 in-game days."},
    # --- extended set ---
    {"id": "coin_hoarder",   "name": "Coin Hoarder",   "desc": "Accumulate 500 coins at once."},
    {"id": "bubble_popper",  "name": "Bubble Popper",  "desc": "Pop 25 bubbles in total."},
    {"id": "the_undertaker", "name": "The Undertaker", "desc": "Have 5 fish rest in the graveyard."},
    {"id": "shopaholic",     "name": "Shopaholic",     "desc": "Buy 5 fish from the Fish Shoppe."},
    {"id": "naturalist",     "name": "Naturalist",     "desc": "Discover 8 different species."},
    {"id": "prolific",       "name": "Prolific",       "desc": "Breed 25 fish in total."},
    {"id": "early_bird",     "name": "Early Bird",     "desc": "Open the aquarium before 7 AM."},
    {"id": "overcrowded",    "name": "Overcrowded!",   "desc": "Have 10 or more fish in the tank at once."},
    {"id": "long_haul",      "name": "Long Haul",      "desc": "Keep a fish alive for 14 days."},
]


def _bevel(surf: pygame.Surface, r: pygame.Rect, pressed: bool = False) -> None:
    tl = WIN_DARK  if pressed else WIN_LIGHT
    br = WIN_LIGHT if pressed else WIN_DARK
    pygame.draw.line(surf, tl, r.topleft, (r.right - 1, r.top))
    pygame.draw.line(surf, tl, r.topleft, (r.left, r.bottom - 1))
    pygame.draw.line(surf, br, (r.right - 1, r.top), (r.right - 1, r.bottom - 1))
    pygame.draw.line(surf, br, (r.left, r.bottom - 1), (r.right - 1, r.bottom - 1))


def unlock(cfg: dict, achievement_id: str) -> bool:
    """Mark achievement as unlocked. Returns True if it was newly unlocked."""
    unlocked: list[str] = cfg.get("achievements_unlocked") or []
    if achievement_id not in unlocked:
        unlocked.append(achievement_id)
        cfg["achievements_unlocked"] = unlocked
        return True
    return False


def is_unlocked(cfg: dict, achievement_id: str) -> bool:
    unlocked: list[str] = cfg.get("achievements_unlocked") or []
    return achievement_id in unlocked


def check_achievements(cfg: dict, fish_list: list) -> list[str]:
    """
    Check all condition-based achievements and unlock them if conditions are met.
    Returns list of newly-unlocked achievement IDs.
    """
    newly: list[str] = []

    def _try(aid: str) -> None:
        if unlock(cfg, aid):
            newly.append(aid)

    # First steps — always on startup (caller should call this at startup)
    _try("first_steps")

    # Daily streak
    streak = int(cfg.get("daily_streak", 0))
    if streak >= 7:
        _try("streak_7")
    if streak >= 30:
        _try("streak_30")

    # Population
    max_fish = int(cfg.get("max_fish", 14))
    if len(fish_list) >= max_fish:
        _try("tank_full")

    # Breeding stat
    if int(cfg.get("stat_bred_fish", 0)) >= 10:
        _try("master_breeder")

    # Cleaning stat
    if int(cfg.get("stat_cleans", 0)) >= 20:
        _try("clean_freak")

    # Profile open stat
    if int(cfg.get("stat_profile_opens", 0)) >= 10:
        _try("fish_whisperer")

    # Name changer — only event-driven (handled in aquarium.py on actual rename)
    # Kept here so it still unlocks correctly if stat_renamed was set legitimately
    if int(cfg.get("stat_renamed", 0)) >= 1:
        _try("name_changer")

    # Named Them All — every adult living fish has a custom name
    adults = [f for f in fish_list if getattr(f, "adult", True)]
    if adults and all(getattr(f, "custom_name", False) for f in adults):
        _try("named_them_all")

    # Night watcher — check if midnight
    now = datetime.datetime.now()
    if now.hour == 0:
        _try("night_watcher")

    # The Collector — 5+ distinct species
    if fish_list:
        # Use name key for proper species comparison
        species_names = {f.sp.get("name", "") for f in fish_list}
        if len(species_names) >= 5:
            _try("collector")

    # Ancient One — any fish >= 30 days
    for f in fish_list:
        if getattr(f, "age", 0) >= 30 * 86400:
            _try("ancient_one")
            break

    # Old Friend — any fish >= 7 days
    for f in fish_list:
        if getattr(f, "age", 0) >= 7 * 86400:
            _try("old_friend")
            break

    # Nightmare Survivor — played 7+ in-game days on Nightmare difficulty
    if int(cfg.get("difficulty", 2)) == 5:
        if float(cfg.get("stat_nightmare_days", 0.0)) >= 7.0:
            _try("nightmare_survivor")

    # Coin Hoarder — 500 coins on hand
    if int(cfg.get("coins", 0)) >= 500:
        _try("coin_hoarder")

    # Bubble Popper — 25 bubbles popped
    if int(cfg.get("stat_bubbles_popped", 0)) >= 25:
        _try("bubble_popper")

    # The Undertaker — 5 fish in the graveyard
    if len(cfg.get("graveyard") or []) >= 5:
        _try("the_undertaker")

    # Shopaholic — bought 5 fish from the shoppe
    if int(cfg.get("stat_shoppe_buys", 0)) >= 5:
        _try("shopaholic")

    # Naturalist — discovered 8 different species
    if len(cfg.get("seen_species") or []) >= 8:
        _try("naturalist")

    # Prolific — bred 25 fish total
    if int(cfg.get("stat_bred_fish", 0)) >= 25:
        _try("prolific")

    # Early Bird — open before 7 AM
    if now.hour < 7:
        _try("early_bird")

    # Overcrowded — 10+ fish at once
    if len(fish_list) >= 10:
        _try("overcrowded")

    # Long Haul — any fish 14+ days
    for f in fish_list:
        if getattr(f, "age", 0) >= 14 * 86400:
            _try("long_haul")
            break

    # Rare Encounter — a rare (or super-rare) fish is in the tank
    for f in fish_list:
        if f.sp.get("rare") or f.sp.get("super_rare"):
            _try("rare_encounter")
            break

    # Epic Find — a super-rare fish is in the tank
    for f in fish_list:
        if f.sp.get("super_rare"):
            _try("super_rare")
            break

    return newly


class AchievementsPanel:
    """Win98-style checklist achievements panel."""

    def __init__(self, font: pygame.font.Font):
        self.font    = font
        self.visible = False
        self._scroll = 0
        self._rect   = pygame.Rect(0, 0, PW, 10)
        self._close_btn = pygame.Rect(0, 0, 0, 0)

    def toggle(self) -> None:
        self.visible = not self.visible
        if self.visible:
            self._scroll = 0

    def close(self) -> None:
        self.visible = False

    # ------------------------------------------------------------------
    def handle_event(self, ev: pygame.event.Event) -> bool:
        if not self.visible:
            return False
        if ev.type == pygame.MOUSEWHEEL:
            self._scroll = max(0, self._scroll - ev.y)
            return True
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self._close_btn.inflate(8, 8).collidepoint(ev.pos):
                self.close()
                return True
            if self._rect.collidepoint(ev.pos):
                return True
            self.close()
            return False
        return False

    # ------------------------------------------------------------------
    def draw(self, surface: pygame.Surface,
             cfg: dict,
             tank_rect: pygame.Rect) -> None:
        if not self.visible:
            return

        fh = self.font.get_height()
        row_h = fh * 2 + 6   # two-line rows (name + desc)

        unlocked_set: set[str] = set(cfg.get("achievements_unlocked") or [])
        total = len(ACHIEVEMENTS)

        header_h = _TB_H + 4
        footer_h = 4
        visible_rows = max(3, (tank_rect.h - header_h - footer_h) // row_h)
        ph = header_h + visible_rows * row_h + footer_h

        max_scroll = max(0, total - visible_rows)
        self._scroll = min(self._scroll, max_scroll)

        # Anchor to left side of tank
        px = tank_rect.left + 2
        py = tank_rect.top + 2
        self._rect = pygame.Rect(px, py, PW, ph)

        pygame.draw.rect(surface, PANEL_BG, self._rect)
        _bevel(surface, self._rect)

        # Title bar
        tb = pygame.Rect(px + 3, py + 3, PW - 6, _TB_H)
        for i in range(tb.h):
            t = i / max(1, tb.h - 1)
            c = (int(TITLE_A[0] + (TITLE_B[0] - TITLE_A[0]) * t),
                 int(TITLE_A[1] + (TITLE_B[1] - TITLE_A[1]) * t),
                 int(TITLE_A[2] + (TITLE_B[2] - TITLE_A[2]) * t))
            pygame.draw.line(surface, c, (tb.left, tb.top + i),
                             (tb.right - _TB_H - 2, tb.top + i))
        count_done = sum(1 for a in ACHIEVEMENTS if a["id"] in unlocked_set)
        title_txt = f"Achievements  {count_done}/{total}"
        ts = self.font.render(title_txt, True, WIN_LIGHT)
        surface.blit(ts, (tb.left + 5, tb.top + (tb.h - ts.get_height()) // 2))

        # Close button
        self._close_btn = pygame.Rect(
            self._rect.right - 3 - _TB_H, py + 3, _TB_H, _TB_H)
        pygame.draw.rect(surface, (180, 80, 80), self._close_btn)
        xs = self.font.render("x", True, WIN_LIGHT)
        surface.blit(xs, (
            self._close_btn.left + (self._close_btn.w - xs.get_width()) // 2,
            self._close_btn.top  + (self._close_btn.h - xs.get_height()) // 2))

        # Row clip
        surface.set_clip(pygame.Rect(px + 2, py + header_h,
                                     PW - 4, visible_rows * row_h))
        ry = py + header_h
        for a in ACHIEVEMENTS[self._scroll: self._scroll + visible_rows]:
            aid = a["id"]
            done = aid in unlocked_set

            # Checkbox (10×10)
            cb = pygame.Rect(px + _PAD, ry + (row_h - 10) // 2, 10, 10)
            pygame.draw.rect(surface, WIN_LIGHT, cb)
            _bevel(surface, cb, pressed=True)
            if done:
                # Draw checkmark
                pygame.draw.line(surface, COL_CHECK,
                                 (cb.left + 2, cb.centery),
                                 (cb.centerx - 1, cb.bottom - 2), 2)
                pygame.draw.line(surface, COL_CHECK,
                                 (cb.centerx - 1, cb.bottom - 2),
                                 (cb.right - 1, cb.top + 2), 2)

            if done:
                name_s = self.font.render(a["name"], True, (20, 20, 80))
                desc_s = self.font.render(a["desc"], True, (80, 80, 100))
            else:
                name_s = self.font.render("???", True, COL_LOCK)
                desc_s = self.font.render("Locked", True, COL_LOCK)

            nx = px + _PAD + 14
            surface.blit(name_s, (nx, ry + 2))
            surface.blit(desc_s, (nx, ry + fh + 4))
            ry += row_h

        surface.set_clip(None)

        # Scroll bar
        if total > visible_rows:
            bar_x   = self._rect.right - 5
            bar_top = py + header_h
            bar_h   = visible_rows * row_h
            frac_top = self._scroll / max(1, total)
            frac_bot = min(1.0, frac_top + visible_rows / total)
            pygame.draw.rect(surface, (160, 160, 160), (bar_x, bar_top, 3, bar_h))
            pygame.draw.rect(surface, WIN_DARK,
                             (bar_x, bar_top + int(frac_top * bar_h),
                              3, max(4, int((frac_bot - frac_top) * bar_h))))
