"""
config.py — load / save / migrate user config.json.

Strategy:
  * config.default.json (shipped, in repo) holds the canonical defaults.
  * config.json (per-user, gitignored) is created from defaults on first run.
  * Corrupted config.json is detected (JSONDecodeError) and reset to defaults.
  * A simple "version" field allows future field migrations.
"""
from __future__ import annotations

import json
import logging
import os
import platform
import shutil
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def _user_data_dir() -> Path:
    """Return the OS-appropriate user data directory for Aquarium 98.

    Windows : ~/Documents/Aquarium98
    macOS   : ~/Documents/Aquarium98
    Linux   : ~/.local/share/Aquarium98  (respects XDG_DATA_HOME)
    """
    home = Path.home()
    if platform.system() == "Linux":
        xdg = os.environ.get("XDG_DATA_HOME", "")
        base = Path(xdg) if xdg else home / ".local" / "share"
        return base / "Aquarium98"
    # Windows and macOS: ~/Documents/Aquarium98 — easy for users to find/back up
    return home / "Documents" / "Aquarium98"


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "config.default.json"
USER_DIR        = _user_data_dir()        # e.g. ~/Documents/Aquarium98/
USER_PATH       = USER_DIR / "config.json"
FISH_STATE_PATH = USER_DIR / "fish_state.json"
_OLD_PATH       = ROOT / "config.json"    # legacy in-app location; migrate on first run

CURRENT_VERSION = "1.0"

# Hard caps that must never be exceeded regardless of user config.
# (Documented in memory: avoid invalid meter-slot loops, keep entity counts sane.)
SLOT_CAPS = {
    "max_fish":    30,
    "max_bubbles": 30,
    "max_food":    40,
}

# ---------------------------------------------------------------------------
# Difficulty presets (1 = Peaceful … 5 = Nightmare)
# ---------------------------------------------------------------------------
DIFFICULTY_PRESETS: dict[int, dict[str, Any]] = {
    1: {  # Peaceful
        "min_fish": 3, "max_fish": 30, "start_fish": 8,
        "hunger_rate": 0.20, "breed_rate": 1.20, "algae_rate": 0.15,
        "growth_rate": 0.80, "age_rate": 0.60, "bubble_rate": 1.0,
        "max_food": 28,
    },
    2: {  # Normal
        "min_fish": 2, "max_fish": 25, "start_fish": 6,
        "hunger_rate": 0.50, "breed_rate": 0.70, "algae_rate": 0.30,
        "growth_rate": 0.50, "age_rate": 1.00, "bubble_rate": 1.0,
        "max_food": 24,
    },
    3: {  # Hard
        "min_fish": 1, "max_fish": 20, "start_fish": 5,
        "hunger_rate": 1.00, "breed_rate": 0.45, "algae_rate": 0.50,
        "growth_rate": 0.40, "age_rate": 1.30, "bubble_rate": 1.0,
        "max_food": 20,
    },
    4: {  # Brutal
        "min_fish": 0, "max_fish": 15, "start_fish": 4,
        "hunger_rate": 1.60, "breed_rate": 0.30, "algae_rate": 0.80,
        "growth_rate": 0.30, "age_rate": 1.60, "bubble_rate": 1.0,
        "max_food": 18,
    },
    5: {  # Nightmare
        "min_fish": 0, "max_fish": 10, "start_fish": 3,
        "hunger_rate": 2.20, "breed_rate": 0.18, "algae_rate": 1.20,
        "growth_rate": 0.25, "age_rate": 2.00, "bubble_rate": 1.0,
        "max_food": 16,
    },
}

DIFFICULTY_NAMES = {1: "Peaceful", 2: "Normal", 3: "Hard", 4: "Brutal", 5: "Nightmare"}

DIFFICULTY_DESCS = {
    1: "Easy — Fish breed freely and a safe minimum pop. is always maintained.",
    2: "Balanced — The classic Aquarium 98 experience.",
    3: "Challenging — Hunger and aging are faster. Keep your tank clean!",
    4: "Unforgiving — No safety net. Lose all fish and you must restart.",
    5: "Near-impossible — Extreme rates. An achievement awaits the survivor.",
}


def _load_defaults() -> dict[str, Any]:
    with DEFAULT_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _migrate(cfg: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    """Add any missing keys from defaults; bump version."""
    changed = False
    for k, v in defaults.items():
        if k not in cfg:
            cfg[k] = v
            changed = True
    if cfg.get("version") != CURRENT_VERSION:
        cfg["version"] = CURRENT_VERSION
        changed = True
    if changed:
        log.info("Config migrated to v%s", CURRENT_VERSION)
    return cfg


def _validate(cfg: dict[str, Any]) -> dict[str, Any]:
    """Clamp values to safe ranges; coerce types; apply difficulty presets."""
    # Night cycle and persist state are always on — not user-configurable
    cfg["night_cycle"]    = True
    cfg["persist_state"]  = True

    cfg["difficulty"] = max(1, min(5, int(cfg.get("difficulty", 2))))

    # Apply difficulty preset for all gameplay-rate variables.
    # max_fish is intentionally NOT overwritten here — it is user-configurable
    # via the Max Fish slider and must survive both difficulty changes and
    # app updates.  The preset value is only used as the fallback default when
    # no user preference has been saved yet (handled by cfg.get() below).
    preset = DIFFICULTY_PRESETS[cfg["difficulty"]]
    cfg["min_fish"]    = preset["min_fish"]
    cfg["start_fish"]  = preset["start_fish"]
    cfg["max_food"]    = preset["max_food"]
    cfg["hunger_rate"] = preset["hunger_rate"]
    cfg["breed_rate"]  = preset["breed_rate"]
    cfg["algae_rate"]  = preset["algae_rate"]
    cfg["growth_rate"] = preset["growth_rate"]
    cfg["age_rate"]    = preset["age_rate"]
    cfg["bubble_rate"] = preset["bubble_rate"]
    # max_fish: clamp user's saved value to a valid range; fall back to the
    # difficulty preset default when no user value is present.
    cfg["max_fish"] = max(
        preset["min_fish"],
        min(SLOT_CAPS["max_fish"], int(cfg.get("max_fish", preset["max_fish"])))
    )

    # Performance mode: cap fish and food to reduce rendering load
    if cfg.get("performance_mode", False):
        cfg["max_fish"] = min(cfg["max_fish"], 8)
        cfg["max_food"] = min(cfg["max_food"], 14)

    # Clamp max_bubbles
    cfg["max_bubbles"] = max(1, min(SLOT_CAPS["max_bubbles"], int(cfg.get("max_bubbles", 30))))

    cfg["start_fish"] = max(0, min(cfg["max_fish"], int(cfg.get("start_fish", 6))))

    op = float(cfg.get("opacity", 1.0))
    cfg["opacity"] = max(0.3, min(1.0, op))

    cfg["window_w"] = max(384, min(1200, int(cfg.get("window_w", 512))))
    cfg["window_h"] = max(366, min(800, int(cfg.get("window_h", 320))))

    cfg["bubble_rate"] = max(0.0, min(4.0, float(cfg.get("bubble_rate", 1.0))))

    cfg["castle_choice"] = max(1, min(5, int(cfg.get("castle_choice", 1))))
    cfg["bg_choice"]     = max(1, min(4, int(cfg.get("bg_choice", 1))))
    cfg["plant_choice"]  = max(1, min(3, int(cfg.get("plant_choice", 1))))

    cfg["sound_volume"] = max(0.0, min(1.0, float(cfg.get("sound_volume", 0.7))))

    cfg["coins"] = max(0, int(cfg.get("coins", 0)))

    return cfg


def load() -> dict[str, Any]:
    defaults = _load_defaults()
    USER_DIR.mkdir(parents=True, exist_ok=True)

    # One-time migration: move config from old in-app location to user dir
    if not USER_PATH.exists() and _OLD_PATH.exists() and _OLD_PATH != USER_PATH:
        try:
            shutil.copy(_OLD_PATH, USER_PATH)
            log.info("Migrated config from %s to %s", _OLD_PATH, USER_PATH)
        except OSError as exc:
            log.warning("Could not migrate old config: %s", exc)

    if not USER_PATH.exists():
        log.info("Creating config.json at %s", USER_PATH)
        shutil.copy(DEFAULT_PATH, USER_PATH)
        return _validate(_migrate(dict(defaults), defaults))

    try:
        with USER_PATH.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("config.json corrupted (%s); resetting to defaults", e)
        cfg = dict(defaults)
        try:
            USER_PATH.replace(USER_PATH.with_suffix(".broken.json"))
        except OSError:
            pass

    cfg = _migrate(cfg, defaults)
    cfg = _validate(cfg)
    return cfg


def save(cfg: dict[str, Any]) -> None:
    try:
        USER_DIR.mkdir(parents=True, exist_ok=True)
        tmp = USER_PATH.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        tmp.replace(USER_PATH)
    except OSError as e:
        log.error("Failed to save config: %s", e)


def validate(cfg: dict[str, Any]) -> dict[str, Any]:
    """Public wrapper — apply difficulty presets and clamp all config values."""
    return _validate(cfg)


def reset_defaults() -> dict[str, Any]:
    """Overwrite config.json with shipped defaults and return them."""
    defaults = _load_defaults()
    save(defaults)
    return _validate(_migrate(dict(defaults), defaults))


# ---------------------------------------------------------------------------
# Fish-state persistence (persist_state feature)
# ---------------------------------------------------------------------------

def save_fish_state(fish_list: list) -> None:
    """Persist the current fish list to fish_state.json."""
    from .simulation.fish import fish_to_dict  # lazy to avoid circular import at module load
    USER_DIR.mkdir(parents=True, exist_ok=True)
    data = [fish_to_dict(f) for f in fish_list]
    try:
        tmp = FISH_STATE_PATH.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fp:
            json.dump(data, fp, indent=2)
        tmp.replace(FISH_STATE_PATH)
    except OSError as exc:
        log.warning("Could not save fish state: %s", exc)


def load_fish_state(tank_w: int, tank_h: int) -> list:
    """Load fish from fish_state.json. Returns [] if missing or corrupt."""
    from .simulation.fish import fish_from_dict  # lazy to avoid circular import
    if not FISH_STATE_PATH.exists():
        return []
    try:
        with FISH_STATE_PATH.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
        result = []
        for d in data:
            f = fish_from_dict(d, tank_w, tank_h)
            if f is not None:
                result.append(f)
        return result
    except (json.JSONDecodeError, KeyError, TypeError, OSError) as exc:
        log.warning("Could not load fish state: %s", exc)
        return []


def clear_fish_state() -> None:
    """Delete fish_state.json (called on tank reset / full reset)."""
    try:
        FISH_STATE_PATH.unlink(missing_ok=True)
    except OSError as exc:
        log.warning("Could not delete fish state: %s", exc)
