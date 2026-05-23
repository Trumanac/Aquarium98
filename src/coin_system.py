"""
coin_system.py — Gold coin economy for Aquarium 98.

Coins are earned by:
  - Clicking the treasure chest when open    (5-35 coins, scaled by difficulty)
  - Popping a bubble                         (1 coin per pop)
  - Unlocking achievements                   (per-achievement bonus below)

Coins are spent in the Fish Shoppe (buying fish, restocking stock).
"""
from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Per-achievement coin bonuses (awarded once on first unlock)
# ---------------------------------------------------------------------------
ACHIEVEMENT_COIN_REWARDS: dict[str, int] = {
    "first_fish":     5,
    "fish_fan":       10,
    "fish_hoarder":   20,
    "name_changer":   5,
    "named_them_all": 25,
    "old_friend":     15,
    "ancient_one":    50,
    "collector":      20,
    "rare_encounter": 30,
    "super_rare":     75,
    "clean_freak":    10,
    "fish_whisperer": 20,
    "night_watcher":  10,
    "diner":          10,
    "breeder":        25,
}


# ---------------------------------------------------------------------------
# Floating "+N coins" popup
# ---------------------------------------------------------------------------
@dataclass
class CoinPopup:
    text: str
    x: float          # screen x (centre)
    y: float          # screen y (start of float)
    age: float = 0.0
    lifetime: float = 1.8   # seconds before disappearing


# ---------------------------------------------------------------------------
# Economy helpers
# ---------------------------------------------------------------------------
def earn_coins(cfg: dict, amount: int, x: float, y: float,
               popups: list[CoinPopup],
               log_fn=None, label: str | None = None) -> None:
    """Add *amount* coins, spawn a popup at (x, y), and optionally log."""
    cfg["coins"] = int(cfg.get("coins", 0)) + amount
    text = f"+{amount} coin" + ("" if amount == 1 else "s")
    popups.append(CoinPopup(text, x, y))
    if log_fn is not None:
        log_fn(cfg, label or text, "coin")


def spend_coins(cfg: dict, amount: int) -> bool:
    """Deduct *amount* from cfg["coins"]. Returns False if insufficient."""
    current = int(cfg.get("coins", 0))
    if current < amount:
        return False
    cfg["coins"] = current - amount
    return True


def update_popups(popups: list[CoinPopup], dt: float) -> None:
    """Age all popups; remove expired ones in-place."""
    for p in popups:
        p.age += dt
    popups[:] = [p for p in popups if p.age < p.lifetime]


# ---------------------------------------------------------------------------
# Fish sell-price calculation
# ---------------------------------------------------------------------------
def fish_sell_price(f) -> int:
    """Calculate fair sell price for *f* based on its current state."""
    sp = f.sp
    # Base by rarity — set well below buy price to create a buy/sell spread
    base = 40.0 if sp.get("uncommon") else 15.0

    # Mood multiplier
    mood_mult = {
        "happy":    1.3,
        "content":  1.0,
        "stressed": 0.7,
        "hungry":   0.5,
    }.get(getattr(f, "mood", "content"), 1.0)

    # Health fraction (clamped to avoid near-zero results)
    health_frac = max(0.3, getattr(f, "health", 1.0))

    # Age bonus: older fish are worth more (nostalgia premium)
    age_days = getattr(f, "age", 0.0) / 86400.0
    if age_days < 2:
        age_bonus = 0.8
    elif age_days < 10:
        age_bonus = 1.0
    elif age_days < 30:
        age_bonus = 1.2
    else:
        age_bonus = 1.5

    return max(1, round(base * mood_mult * health_frac * age_bonus))
