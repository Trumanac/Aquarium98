"""
population.py — births, deaths, layer transitions, school formation.
"""
from __future__ import annotations

import random

from .fish import Fish, make_fish, LAYER_Y_MAX_FRAC
from .species import common_species


def cull_dead(fish_list: list[Fish]) -> int:
    before = len(fish_list)
    fish_list[:] = [f for f in fish_list if f.health > 0.01]
    return before - len(fish_list)


def try_breed(fish_list: list[Fish], tank_w: int, tank_h: int, cfg: dict,
              dt: float) -> Fish | None:
    """Adult pairs of same species with low hunger may produce one juvenile."""
    if len(fish_list) >= int(cfg.get("max_fish", 25)):
        return None
    rate = float(cfg.get("breed_rate", 0.70))
    if rate <= 0:
        return None
    # Per-frame probability scaled to roughly one attempt per 30s at rate=1
    p = dt * 0.033 * rate
    if random.random() > p:
        return None

    candidates = [f for f in fish_list if f.adult and f.hunger < 0.5
                  and f.health > 0.7 and f.breed_cd <= 0]
    if len(candidates) < 2:
        return None
    a = random.choice(candidates)
    same_sp = [f for f in candidates if f.sp["name"] == a.sp["name"] and f is not a]
    if not same_sp:
        return None
    b = random.choice(same_sp)
    a.breed_cd = 120.0
    b.breed_cd = 120.0
    # Offspring are always the same species as the parents — no random downgrade.
    breed_sp = a.sp
    juvenile = make_fish(tank_w, tank_h, species=breed_sp,
                         x=(a.x + b.x) / 2, y=(a.y + b.y) / 2,
                         scale=0.45,
                         existing_names={f.name for f in fish_list},
                         lifespan_base=float(cfg.get("lifespan_base", 1814400)))
    juvenile.adult = False
    juvenile.born_from = (a.name, b.name)
    return juvenile


def ensure_min_population(fish_list: list[Fish], tank_w: int, tank_h: int,
                          cfg: dict) -> int:
    """Auto-spawn common fish to maintain min_fish.

    Only common species are used here so that rare and uncommon species can
    only be discovered intentionally (starting tank, store purchases, breeding)
    rather than silently appearing as maintenance fish in the background.
    """
    target = int(cfg.get("min_fish", 5))
    added = 0
    while len(fish_list) < target:
        new_f = make_fish(tank_w, tank_h,
                          species=random.choice(common_species()),
                          existing_names={f.name for f in fish_list},
                          lifespan_base=float(cfg.get("lifespan_base", 1814400)))
        fish_list.append(new_f)
        added += 1
    return added


def maybe_change_layer(f: Fish, tank_h: int, dt: float) -> None:
    """Occasionally have fish swap depth layers (all species, including floor dwellers).

    Floor fish can change layer to move in front of or behind decorations; their
    y-coordinate is re-pinned to the sand automatically each frame by _update_motion
    so it does not need adjusting here.  Bottom/crawler species change layer ~3×
    less often than pelagic fish.

    Fish with a layer_pref are twice as likely to drift *back* toward their
    preferred layer than to move away from it.
    """
    if f.layer_cd > 0:
        return
    is_floor = f.sp.get("bottom") or f.sp.get("crawler")
    rate = 0.0033 if is_floor else 0.01   # bottom fish: ~once per 300 s
    if random.random() >= dt * rate:
        return

    pref = f.sp.get("layer_pref", 0)
    if pref and f.layer != pref and random.random() < 0.65:
        # Drift back toward preferred layer
        new_layer = pref
    else:
        new_layer = random.choice([1, 2, 3])

    if new_layer != f.layer:
        f.layer = new_layer
        if not is_floor:
            ymax = tank_h * LAYER_Y_MAX_FRAC[new_layer]
            f.y = min(f.y, ymax - 12)
        f.layer_cd = 60.0
