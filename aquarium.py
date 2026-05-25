"""
aquarium.py — Aquarium 98 entry point.

Pipeline:
  1. Logging setup
  2. Singleton lock (~/.aquarium98.lock)
  3. Load config + ensure icon files exist
  4. pygame init + window creation
  5. Build initial fish population + environment
  6. Decoupled simulation/render loop (20Hz sim, 30 FPS render target)
  7. Tray + context menu + settings dialog integration
  8. Cleanup: persist config (window pos/size) on exit
"""
from __future__ import annotations

import datetime
import logging
import logging.handlers
import math
import os
import platform
import random
import sys
import time
import traceback
from pathlib import Path

try:
    from importlib.metadata import version as _pkg_version
    APP_VERSION = _pkg_version("aquarium98")
except Exception:  # noqa: BLE001
    APP_VERSION = "1.0.4"

import pygame

# Ensure project root on path (works when launched via `python aquarium.py`).
# In a PyInstaller one-dir bundle, __file__ resolves into sys._MEIPASS, so
# ROOT is the extraction dir — the same place assets/ and config.default.json
# are unpacked.  User-writable data (config, saves, logs) always goes to
# cfg_mod.USER_DIR (~\Documents\Aquarium98 on Win/macOS; ~/.local/share on Linux).
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src import config as cfg_mod
from src import window as win_mod
from src.context_menu import ContextMenu, feed_menu
from src.icon_gen import ensure_icons
from src.renderer import Renderer, PAD_B, fish_screen_rect
from src.settings_dialog import SettingsDialog
from src.confirm_dialog import ConfirmDialog, FullResetDialog, AboutDialog, CrashDialog
from src.how_to_play_panel import HowToPlayPanel
from src.event_log_panel import EventLogPanel, log_event
from src.achievements_panel import ACHIEVEMENTS, AchievementsPanel, check_achievements, unlock, is_unlocked
from src.encyclopedia_panel import EncyclopediaPanel, mark_seen, is_seen
from src.graveyard_panel import GraveyardPanel, log_death
from src.fish_info_panel import FishInfoPanel
from src.fish_roster_panel import FishRosterPanel
from src import startup as startup_mod
from src.splash import show_splash
from src.simulation.environment import (
    add_food, clean_algae, make_environment, pop_bubble_at, spawn_chest_burst,
    spawn_food_at, update_environment,
)
from src.simulation.fish import make_fish, update_biology, update_fish, update_mood
from src.simulation.species import SPECIES
from src.simulation.population import (
    cull_dead, ensure_min_population, maybe_change_layer, try_breed,
)
from src.tray import Tray
from src.coin_system import (
    CoinPopup, ACHIEVEMENT_COIN_REWARDS,
    earn_coins, spend_coins, update_popups, fish_sell_price,
)
from src.treasure_chest import TreasureChest, make_chest
from src.fish_store_panel import FishStorePanel
from src.cursor_manager import CursorManager
from src.tooltip import Tooltip
from src.sound_manager import SoundManager
from src.achievement_popup import AchievementPopup
from src import update_check

# Logs live in the user data dir so they survive app updates / re-installs
# and are writable whether the app is run from source or as a frozen bundle.
LOG_DIR   = cfg_mod.USER_DIR / "logs"
LOCK_FILE = Path.home() / ".aquarium98.lock"

SIM_HZ = 20
RENDER_FPS = 30
IS_WINDOWS = platform.system() == "Windows"
# USE_ABS_CURSOR is set at runtime in run() via win_mod.cursor_available().
# Windows=GetCursorPos, Linux=Xlib, macOS=SDL2 bundled lib; rel-accum fallback.


def _setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    logfile = LOG_DIR / "aquarium.log"
    rotating = logging.handlers.RotatingFileHandler(
        logfile, maxBytes=500_000, backupCount=3, encoding="utf-8"
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[rotating, logging.StreamHandler(sys.stdout)],
    )


def _is_process_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        # Process exists but we lack permission to signal it — still running.
        return True
    except OSError:
        return False


# Windows named-mutex handle — kept alive for the process lifetime.
_WIN_MUTEX_HANDLE: object = None
_WIN_MUTEX_NAME = "Global\\Aquarium98SingleInstance"


def _acquire_lock() -> bool:
    global _WIN_MUTEX_HANDLE
    if IS_WINDOWS:
        try:
            import ctypes
            import ctypes.wintypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.CreateMutexW(None, True, _WIN_MUTEX_NAME)
            err = kernel32.GetLastError()
            if err == 183:          # ERROR_ALREADY_EXISTS
                if handle:
                    kernel32.CloseHandle(handle)
                return False
            _WIN_MUTEX_HANDLE = handle  # keep alive until process exits
            return True
        except Exception:  # ctypes unavailable / unexpected error
            pass            # fall through to lockfile
    # POSIX (and Windows fallback): PID lockfile
    if LOCK_FILE.exists():
        try:
            old = int(LOCK_FILE.read_text(encoding="utf-8").strip())
            if _is_process_running(old) and old != os.getpid():
                return False
        except (ValueError, OSError):
            pass
    try:
        LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except OSError:
        return True   # don't block startup on lock-file failure


def _release_lock() -> None:
    global _WIN_MUTEX_HANDLE
    if IS_WINDOWS and _WIN_MUTEX_HANDLE is not None:
        try:
            import ctypes
            ctypes.windll.kernel32.CloseHandle(_WIN_MUTEX_HANDLE)
        except Exception:
            pass
        _WIN_MUTEX_HANDLE = None
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except OSError:
        pass


def _show_already_running_error() -> None:
    """Display a visible error when a second instance is launched."""
    title = "Aquarium 98 — Already Running"
    msg = (
        "Aquarium 98 is already running.\n\n"
        "Only one instance can run at a time.\n"
        "Check your system tray."
    )
    if IS_WINDOWS:
        try:
            import ctypes
            # MB_OK | MB_ICONERROR | MB_TOPMOST = 0x00040010
            ctypes.windll.user32.MessageBoxW(0, msg, title, 0x00040010)
            return
        except Exception:
            pass
    try:
        import tkinter as tk
        from tkinter import messagebox as _mb
        _root = tk.Tk()
        _root.withdraw()
        _mb.showerror(title, msg)
        _root.destroy()
    except Exception:
        print(f"\n{title}\n{msg}", file=sys.stderr)


def main() -> int:
    _setup_logging()
    log = logging.getLogger("aquarium")

    if not _acquire_lock():
        log.warning("Another instance is already running; exiting.")
        _show_already_running_error()
        return 0

    try:
        cfg = cfg_mod.load()
        icon_path = ensure_icons()

        # Sync startup state.
        # On first run (first_run flag still true) we read the *actual* registry /
        # launch-agent state so the in-app setting reflects what the user chose
        # during installation rather than blindly overwriting it with a default.
        if cfg.get("first_run", False):
            cfg["open_on_startup"] = startup_mod.is_startup_enabled()
            cfg["first_run"] = False
            cfg_mod.save(cfg)
        else:
            startup_mod.set_startup(bool(cfg.get("open_on_startup", False)))

        # ── Daily streak ─────────────────────────────────────────────
        today_str = datetime.date.today().isoformat()
        last_opened = cfg.get("last_opened_date", "")
        streak = int(cfg.get("daily_streak", 0))
        _welcome_back_msg = ""
        if last_opened == today_str:
            pass  # same session, no change
        else:
            if last_opened:
                try:
                    last_date = datetime.date.fromisoformat(last_opened)
                    gap = (datetime.date.today() - last_date).days
                    if gap == 1:
                        streak += 1
                        _welcome_back_msg = (
                            f"Welcome back! Day {streak} streak ><>"
                        )
                    elif gap > 1:
                        streak = 1
                        _welcome_back_msg = (
                            f"Welcome back — your fish missed you! ({gap} days away)"
                        )
                except ValueError:
                    streak = 1
            else:
                streak = 1
        cfg["daily_streak"] = streak
        cfg["last_opened_date"] = today_str

        # Show startup splash before the main game window is created
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.display.init()
        pygame.mixer.init()
        pygame.font.init()
        show_splash()

        surface, sdl_win, font = win_mod.init_window(cfg)
        # Determine whether absolute screen cursor is available on this platform.
        # Must be called after init_window so pygame/SDL2 is fully initialised.
        USE_ABS_CURSOR = win_mod.cursor_available()
        renderer = Renderer(surface, font)
        context = ContextMenu(font)
        settings = SettingsDialog(font)
        fish_info     = FishInfoPanel(font)
        fish_roster   = FishRosterPanel(font)
        confirm_dlg   = ConfirmDialog(font)
        full_reset_dlg = FullResetDialog(font)
        about_dlg      = AboutDialog(font, APP_VERSION)
        how_to_play    = HowToPlayPanel(font)
        event_log     = EventLogPanel(font)
        achievements  = AchievementsPanel(font)
        encyclopedia  = EncyclopediaPanel(font)
        graveyard_panel = GraveyardPanel(font)
        fish_store    = FishStorePanel(font)
        _pending_reset = False   # set True while waiting for confirm dialog

        # Sound effects (silent no-op if mixer unavailable)
        sound = SoundManager()

        # Achievement unlock notifications
        achievement_popup = AchievementPopup(font)

        def _fire_achievement(aid: str) -> None:
            """Unlock an achievement, then show popup / play sound / award coins."""
            if not unlock(cfg, aid):
                return  # already unlocked — nothing to do
            _ach    = next((a for a in ACHIEVEMENTS if a["id"] == aid),
                           {"name": aid, "desc": ""})
            _name   = _ach["name"]
            _desc   = _ach["desc"]
            _reward = ACHIEVEMENT_COIN_REWARDS.get(aid, 0)
            log_event(cfg, f"[*] Achievement unlocked: {_name}", "info")
            sound.play_achievement()
            if _reward > 0:
                earn_coins(cfg, _reward,
                           float(tr.centerx), float(tr.centery),
                           coin_popups, log_event,
                           f"Achievement reward: +{_reward} coins")
            achievement_popup.push(_name, _desc, _reward)

        # Background version check — result polled lazily in render loop
        update_check.start(APP_VERSION)

        # Custom animated cursors (hides system cursor)
        _ui_dir = str(ROOT / "assets" / "sprites" / "ui")
        cursor_mgr = CursorManager(_ui_dir)

        # Hover tooltips
        tooltip = Tooltip()

        tr = renderer.compute_tank_rect()
        env = make_environment(tr.w, tr.h)
        fish_list = []

        # First-launch: pop the How to Play guide once and remember.
        if not cfg.get("how_to_play_seen", False):
            how_to_play.open(*surface.get_size())
            cfg["how_to_play_seen"] = True
        coin_popups: list[CoinPopup] = []
        chest = make_chest(int(cfg.get("difficulty", 2)))

        # Restore fish from previous session when persist_state is on
        if cfg.get("persist_state", True):
            fish_list = cfg_mod.load_fish_state(tr.w, tr.h)
            max_fish = int(cfg.get("max_fish", 16))
            if len(fish_list) > max_fish:
                fish_list = fish_list[:max_fish]
            for f in fish_list:
                mark_seen(cfg, f.sp.get("name", ""))

        if not fish_list:
            # Fresh start: randomise decor only on the very first ever launch;
            # subsequent empty-tank starts (persist_state off, all fish died, etc.)
            # keep whatever castle/plant the user last chose.
            if not cfg.get("_tank_initialized", False):
                cfg["castle_choice"] = random.randint(1, 5)
            for _ in range(int(cfg.get("start_fish", 6))):
                f = make_fish(tr.w, tr.h,
                              existing_names={g.name for g in fish_list},
                              lifespan_base=float(cfg.get("lifespan_base", 1814400)))
                fish_list.append(f)
                mark_seen(cfg, f.sp.get("name", ""))
                cfg["stat_total_fish"] = int(cfg.get("stat_total_fish", 0)) + 1
        # Remember that the tank has been initialised at least once, so decor
        # is never re-randomised unless the user does a full reset.
        cfg["_tank_initialized"] = True

        # Auto-food drop welcome-back bonus (when returning after a gap)
        if _welcome_back_msg and "missed you" in _welcome_back_msg:
            for _ in range(3):
                spawn_food_at(env, env.tank_w * (0.3 + random.random() * 0.4), env.tank_h * 0.25)

        # Log the welcome-back / streak message
        if _welcome_back_msg:
            log_event(cfg, _welcome_back_msg, "streak")
            # Streak coin bonus: 5 coins × streak day, capped at 50
            # (only when gap == 1, i.e. streak > 1 — not on a reset)
            if streak > 1:
                _streak_bonus = min(streak * 5, 50)
                earn_coins(
                    cfg, _streak_bonus,
                    float(tr.centerx), float(tr.top + 40),
                    coin_popups, log_event,
                    f"Day {streak} streak! +{_streak_bonus} coins",
                )

        # Startup achievement checks — award coins/popup for any newly triggered
        # achievements (e.g. "first_steps" on a brand-new install, streak milestones
        # when the app opens with an already-qualifying streak, etc.).
        for _startup_aid in check_achievements(cfg, fish_list):
            _sa = next((a for a in ACHIEVEMENTS if a["id"] == _startup_aid),
                       {"name": _startup_aid, "desc": ""})
            _sr = ACHIEVEMENT_COIN_REWARDS.get(_startup_aid, 0)
            if _sr > 0:
                earn_coins(cfg, _sr,
                           float(tr.centerx), float(tr.top + 40),
                           coin_popups, log_event,
                           f"Achievement reward: +{_sr} coins")
            achievement_popup.push(_sa["name"], _sa["desc"], _sr)

        sprite_cache: dict = {}
        tray = Tray(icon_path)
        tray.start()

        clock = pygame.time.Clock()
        sim_accum = 0.0
        sim_dt = 1.0 / SIM_HZ
        last_t = time.perf_counter()
        last_pos_save = 0.0

        paused = False
        hidden = False
        fps_smoothed = 0.0
        running = True
        food_mode   = False
        clean_mode  = False
        roster_mode = False
        store_mode  = False
        stat_accum  = 0.0   # real-time seconds; flushed to cfg every minute
        last_resize_t = 0.0  # perf_counter timestamp of last resize drag movement
        pending_resize: tuple[int, int] | None = None  # target size waiting to be applied
        # Streak display: show on first frame
        _streak_display = f"Day {streak} streak ><>" if streak > 1 else ""
        status_msg   = _welcome_back_msg or _streak_display or "Aquarium 98 ready."
        status_timer = 180   # frames at 30 FPS

        def set_status(msg: str, frames: int = 120) -> None:
            nonlocal status_msg, status_timer
            status_msg   = msg
            status_timer = frames

        # Rotating idle tips shown when the status bar has been quiet a while
        _TIPS = [
            "Right-click anywhere for a quick action menu.",
            "Press Space to pause/unpause the simulation.",
            "Press F to instantly drop food at the centre of the tank.",
            "Press C to instantly scrub algae from the tank.",
            "Press E to open the Settings dialog.",
            "Pop bubbles with a click — you might earn a coin!",
            "Fish need food to breed. Keep them well-fed!",
            "Check the Achievements panel for coin rewards.",
            "Click the treasure chest when it appears — don't miss it!",
            "The Graveyard honours every fish that has passed.",
            "Open the Encyclopedia to browse all known species.",
            "Hard difficulty removes the safety-net respawn. Careful!",
            "Drag the window by its title bar to reposition it.",
            "The Fish Shoppe restocks with new species over time.",
            "Click a fish to view its full profile and rename it.",
            "Daily login streaks add to your progress. Come back tomorrow!",
        ]
        tip_countdown = 450   # frames until first idle tip (~15 s at 30 FPS)
        _tip_idx      = -1    # cycles through _TIPS sequentially

        # --- helpers ---
        def apply_opacity(value: float):
            cfg["opacity"] = max(0.30, min(1.0, value))
            win_mod.set_opacity(sdl_win, cfg["opacity"])

        def do_action(action: str):
            nonlocal paused, hidden, running, fish_list, env, sprite_cache, _pending_reset, roster_mode, food_mode, clean_mode
            if action == "quit":
                running = False
            elif action == "pause":
                paused = not paused
            elif action == "feed":
                n = spawn_food_at(env, env.tank_w * 0.5, env.tank_h * 0.3)
                set_status(f"Dropped {n} food flakes!")
            elif action == "clean":
                clean_algae(env)
                if env.algae <= 0:
                    renderer.reset_algae_overlay()
                cfg["stat_cleans"] = int(cfg.get("stat_cleans", 0)) + 1
                log_event(cfg, "Tank cleaned.", "info")
                set_status(f"Scrub! ({int(env.algae)}% algae remaining.)")
            elif action == "reset":
                # Show confirmation dialog first
                _pending_reset = True
                confirm_dlg.open(
                    "Reset Tank",
                    "All fish will be lost and the tank restarted. Are you sure?",
                    *surface.get_size()
                )
            elif action == "_do_reset":
                # Actual reset after confirmation
                fish_list = []
                cfg_mod.clear_fish_state()  # prevent stale state from reloading
                env = make_environment(tr.w, tr.h)
                sprite_cache.clear()
                fish_info.close()
                fish_roster.close()
                fish_roster.invalidate_all()
                # Close all secondary panels so stale content never bleeds through
                event_log.close()
                achievements.close()
                encyclopedia.close()
                graveyard_panel.close()
                fish_store.close()
                context.close()
                roster_mode = False
                food_mode = False
                clean_mode = False
                cursor_mgr.set_mode("normal")
                added = ensure_min_population(fish_list, tr.w, tr.h, cfg)
                cfg["stat_total_fish"] = int(cfg.get("stat_total_fish", 0)) + added
                extra = int(cfg.get("start_fish", 6)) - len(fish_list)
                for _ in range(max(0, extra)):
                    f_new = make_fish(tr.w, tr.h,
                                      existing_names={g.name for g in fish_list},
                                      lifespan_base=float(cfg.get("lifespan_base", 1814400)))
                    fish_list.append(f_new)
                    cfg["stat_total_fish"] = int(cfg.get("stat_total_fish", 0)) + 1
                for f_reset in fish_list:
                    mark_seen(cfg, f_reset.sp.get("name", ""))
                # Randomise decor for the freshly reset tank
                cfg["castle_choice"] = random.randint(1, 5)
                # Persist immediately — don't wait for the 5-second periodic save.
                # This ensures a crash or fast-close can never leave fish_state.json
                # empty/missing while config.json still reflects the pre-reset state.
                cfg_mod.save(cfg)
                cfg_mod.save_fish_state(fish_list)
            elif action == "toggle_lock":
                cfg["locked"] = not bool(cfg.get("locked", False))
            elif action == "toggle_top":
                cfg["always_on_top"] = not bool(cfg.get("always_on_top", False))
                win_mod.set_always_on_top(sdl_win, cfg["always_on_top"])
            elif action == "toggle_phide":
                cfg["pause_when_hidden"] = not bool(cfg.get("pause_when_hidden", True))
            elif action == "toggle_names":
                cfg["show_names"] = not bool(cfg.get("show_names", False))
            elif action == "toggle_moods":
                cfg["show_moods"] = not bool(cfg.get("show_moods", False))
            elif action == "toggle_mute":
                cfg["sound_muted"] = not bool(cfg.get("sound_muted", False))
                sound.set_muted(bool(cfg["sound_muted"]))
            elif action.startswith("op_"):
                apply_opacity(int(action[3:]) / 100.0)
            elif action == "settings":
                settings.open(cfg, surface.get_size())
            elif action == "about":
                about_dlg.open(*surface.get_size())
            elif action == "how_to_play":
                how_to_play.open(*surface.get_size())
            elif action == "event_log":
                event_log.toggle()
            elif action == "achievements":
                achievements.toggle()
            elif action == "encyclopedia":
                encyclopedia.toggle()
            elif action == "graveyard":
                graveyard_panel.toggle()
            elif action == "tray":
                if tray.started and sdl_win is not None:
                    hidden = True
                    try:
                        sdl_win.hide()
                    except Exception:   # noqa: BLE001
                        pass
                elif sdl_win is not None:
                    # Fallback for platforms/backends without a working tray.
                    # Keep the app discoverable via taskbar/dock.
                    hidden = False
                    try:
                        sdl_win.minimize()
                    except Exception:   # noqa: BLE001
                        pass
            elif action == "show":
                hidden = False
                if sdl_win is not None:
                    try:
                        sdl_win.show()
                    except Exception:   # noqa: BLE001
                        pass
            elif action == "hide":
                if tray.started and sdl_win is not None:
                    hidden = True
                    try:
                        sdl_win.hide()
                    except Exception:   # noqa: BLE001
                        pass
                elif sdl_win is not None:
                    hidden = False
                    try:
                        sdl_win.minimize()
                    except Exception:   # noqa: BLE001
                        pass

        # Drag/resize state
        drag_mode   = None      # "move" or "resize"
        # For move: offset from window top-left to cursor in screen space
        drag_offset = (0, 0)
        # For resize: screen cursor position and surface size at drag start
        drag_screen_start = (0, 0)
        drag_orig         = (0, 0)
        # Non-Windows drag baseline/accumulator to avoid position feedback loops.
        drag_win_start    = (0, 0)
        drag_rel_accum    = (0, 0)

        while running:
            now = time.perf_counter()
            frame_dt = now - last_t
            last_t = now

            # Periodic config save (for window position/size)
            if now - last_pos_save > 5.0:
                pos = win_mod.get_position(sdl_win)
                if pos is not None:
                    cfg["window_x"], cfg["window_y"] = pos
                w, h = surface.get_size()
                cfg["window_w"], cfg["window_h"] = w, h
                cfg_mod.save(cfg)
                if cfg.get("persist_state", True):
                    cfg_mod.save_fish_state(fish_list)
                last_pos_save = now

            # -------- events --------
            for ev in pygame.event.get():
                # Trigger click animation for any left-click, regardless of what it hits
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    cursor_mgr.on_click()

                # Confirm dialog eats all events while open
                if confirm_dlg.visible:
                    result = confirm_dlg.handle_event(ev)
                    if result == "yes":
                        do_action("_do_reset")
                    continue

                # Full-reset dialog eats all events while open
                if about_dlg.visible:
                    about_dlg.handle_event(ev)
                    continue

                if how_to_play.visible:
                    how_to_play.handle_event(ev)
                    continue

                # Achievement popup eats events while a notification is showing
                if achievement_popup.visible:
                    achievement_popup.handle_event(ev)
                    continue

                if full_reset_dlg.visible:
                    result = full_reset_dlg.handle_event(ev)
                    if result == "confirmed":
                        # Wipe everything to a clean slate
                        cfg.clear()
                        cfg.update(cfg_mod.reset_defaults())
                        cfg["seen_species"]          = []
                        cfg["achievements_unlocked"] = []
                        cfg["graveyard"]             = []
                        cfg["event_log"]       = []
                        cfg["coins"]           = 0
                        cfg["daily_streak"]    = 1
                        cfg["stat_total_days"] = 0.0
                        cfg["stat_total_fish"] = 0
                        cfg["stat_peak_fish"]  = 0
                        cfg["stat_cleans"]          = 0
                        cfg["stat_renamed"]          = 0
                        cfg["stat_bubbles_popped"]   = 0
                        cfg["stat_shoppe_buys"]      = 0
                        cfg_mod.save(cfg)
                        cfg_mod.clear_fish_state()  # wipe persisted fish on full reset
                        win_mod.set_opacity(sdl_win, cfg.get("opacity", 1.0))
                        win_mod.set_always_on_top(sdl_win, bool(cfg.get("always_on_top", False)))
                        do_action("_do_reset")
                        settings.close()
                        log_event(cfg, "Full reset performed — tank wiped clean.", "info")
                        set_status("Full reset complete. Fresh start!")
                    continue

                if settings.visible:
                    result = settings.handle_event(ev)
                    if result == "save":
                        settings.commit_into(cfg)
                        # Re-validate after slider changes
                        cfg.update(cfg_mod.validate(cfg))
                        win_mod.set_opacity(sdl_win, cfg.get("opacity", 1.0))
                        win_mod.set_always_on_top(sdl_win, bool(cfg.get("always_on_top", False)))
                        startup_mod.set_startup(bool(cfg.get("open_on_startup", False)))
                        cfg_mod.save(cfg)
                    elif result == "reset":
                        cfg.clear()
                        cfg.update(cfg_mod.reset_defaults())
                        win_mod.set_opacity(sdl_win, cfg.get("opacity", 1.0))
                        win_mod.set_always_on_top(sdl_win, bool(cfg.get("always_on_top", False)))
                    elif result == "full_reset":
                        full_reset_dlg.open(*surface.get_size())
                    elif result == "reset_tank":
                        do_action("reset")
                    continue

                if fish_info.visible:
                    result = fish_info.handle_event(ev)
                    if result == "renamed":
                        # Only count and unlock when the name was actually changed
                        cfg["stat_renamed"] = int(cfg.get("stat_renamed", 0)) + 1
                        _fire_achievement("name_changer")
                    # Panel handles its own drag/close; keep consuming events while visible
                    continue

                # Roster toolbar button (9,96)-(36,123) always toggles — even
                # when the roster panel is currently open.
                if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1
                        and 6 <= ev.pos[0] <= 42 and 108 <= ev.pos[1] <= 144):
                    food_mode = False; clean_mode = False; cursor_mgr.set_mode("normal")
                    roster_mode = not roster_mode
                    if roster_mode:
                        fish_roster.open()
                    else:
                        fish_roster.close()
                    continue

                # Event log toolbar button (6,148)-(42,184)
                if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1
                        and 6 <= ev.pos[0] <= 42 and 148 <= ev.pos[1] <= 184):
                    food_mode = False; clean_mode = False; cursor_mgr.set_mode("normal")
                    event_log.toggle()
                    continue

                # Event log panel consumes scroll/click while visible
                if event_log.visible:
                    if event_log.handle_event(ev):
                        continue

                # Achievements toolbar button (6,188)-(42,224)
                if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1
                        and 6 <= ev.pos[0] <= 42 and 188 <= ev.pos[1] <= 224):
                    food_mode = False; clean_mode = False; cursor_mgr.set_mode("normal")
                    achievements.toggle()
                    continue

                if achievements.visible:
                    if achievements.handle_event(ev):
                        continue

                # Encyclopedia toolbar button (6,228)-(42,264)
                if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1
                        and 6 <= ev.pos[0] <= 42 and 228 <= ev.pos[1] <= 264):
                    food_mode = False; clean_mode = False; cursor_mgr.set_mode("normal")
                    encyclopedia.toggle()
                    continue

                if encyclopedia.visible:
                    if encyclopedia.handle_event(ev):
                        continue

                # Graveyard toolbar button (6,268)-(42,304)
                if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1
                        and 6 <= ev.pos[0] <= 42 and 268 <= ev.pos[1] <= 304):
                    food_mode = False; clean_mode = False; cursor_mgr.set_mode("normal")
                    graveyard_panel.toggle()
                    continue

                if graveyard_panel.visible:
                    if graveyard_panel.handle_event(ev):
                        continue

                # Fish Shoppe toolbar button (6,308)-(42,344)
                if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1
                        and 6 <= ev.pos[0] <= 42 and 308 <= ev.pos[1] <= 344):
                    food_mode = False; clean_mode = False; cursor_mgr.set_mode("normal")
                    fish_store.toggle(cfg, surface.get_size())
                    store_mode = fish_store.visible
                    continue

                if fish_store.visible:
                    store_action = fish_store.handle_event(ev, cfg, fish_list)
                    if store_action is not None:
                        action_type, *action_args = store_action
                        if action_type == "buy":
                            sp_buy, price_buy = action_args
                            if spend_coins(cfg, price_buy):
                                new_f = make_fish(
                                    env.tank_w, env.tank_h,
                                    species=sp_buy,
                                    existing_names={f.name for f in fish_list},
                                    lifespan_base=float(cfg.get("lifespan_base", 1814400)),
                                )
                                fish_list.append(new_f)
                                fish_store.mark_slot_bought(sp_buy)
                                mark_seen(cfg, sp_buy.get("name", ""))
                                cfg["stat_total_fish"]  = int(cfg.get("stat_total_fish", 0)) + 1
                                cfg["stat_shoppe_buys"] = int(cfg.get("stat_shoppe_buys", 0)) + 1
                                log_event(cfg, f"Bought {sp_buy.get('name','?')} for {price_buy} coins", "coin")
                                set_status(f"Bought {sp_buy.get('name','?')}! ({int(cfg.get('coins',0))} coins left)")
                                # Persist immediately so a crash won't lose the new fish
                                cfg_mod.save(cfg)
                                cfg_mod.save_fish_state(fish_list)
                            else:
                                set_status(f"Not enough coins! Need {price_buy}.")
                        elif action_type == "sell":
                            fish_to_sell = action_args[0]
                            if fish_to_sell in fish_list:
                                price_sell = fish_sell_price(fish_to_sell)
                                scx = tr.left + int(getattr(fish_to_sell, 'x', tr.w // 2))
                                scy = tr.top  + int(getattr(fish_to_sell, 'y', tr.h // 2))
                                fish_roster.invalidate_thumb(fish_to_sell)
                                fish_list.remove(fish_to_sell)
                                earn_coins(cfg, price_sell, float(scx), float(scy),
                                           coin_popups, log_event,
                                           f"Sold {fish_to_sell.name} for {price_sell} coins")
                                set_status(f"Sold {fish_to_sell.name} for {price_sell} coins!")
                                # Persist immediately so a crash won't lose the sale
                                cfg_mod.save(cfg)
                                cfg_mod.save_fish_state(fish_list)
                        elif action_type == "restock":
                            restock_cost = action_args[0]
                            if spend_coins(cfg, restock_cost):
                                fish_store._restock_slots(cfg)
                                log_event(cfg, f"Restocked Fish Shoppe for {restock_cost} coins", "coin")
                                set_status("Fish Shoppe restocked!")
                            else:
                                set_status(f"Not enough coins to restock! Need {restock_cost}.")
                        continue

                if fish_roster.visible:
                    idx = fish_roster.handle_event(ev, fish_list)
                    roster_mode = fish_roster.visible
                    if idx is not None and 0 <= idx < len(fish_list):
                        sel = fish_list[idx]
                        fish_info.open(sel, *surface.get_size(),
                                       ev.pos[0], ev.pos[1],
                                       renderer.assets.fish_sheets)
                        cfg["stat_profile_opens"] = int(cfg.get("stat_profile_opens", 0)) + 1
                        fish_roster.close()
                        roster_mode = False
                    continue

                if context.visible:
                    act = context.handle_event(ev)
                    if act:
                        do_action(act)
                    continue

                if ev.type == pygame.QUIT:
                    # Intercept window-close: hide to tray when available
                    # so the app keeps running. Only actually quit if no tray.
                    if tray.started:
                        do_action("tray")
                    else:
                        running = False
                elif ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_SPACE:
                        paused = not paused
                    elif ev.key == pygame.K_f:
                        n = spawn_food_at(env, env.tank_w * 0.5, env.tank_h * 0.3)
                        set_status(f"Dropped {n} food flakes!")
                    elif ev.key == pygame.K_c:
                        do_action("clean")
                    elif ev.key == pygame.K_r:
                        do_action("reset")
                    elif ev.key == pygame.K_e:
                        settings.open(cfg, surface.get_size())
                    elif ev.key == pygame.K_ESCAPE:
                        do_action("tray")
                    elif ev.key == pygame.K_q and (ev.mod & pygame.KMOD_CTRL):
                        running = False
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    if ev.button == 1:
                        mx, my = ev.pos
                        # Toolbar: FoodBtn (6,28)-(42,64), CleanBtn (6,68)-(42,104)
                        if 6 <= mx <= 42 and 28 <= my <= 64:
                            food_mode = not food_mode
                            if food_mode:
                                clean_mode = False
                                cursor_mgr.set_mode("feed")
                                set_status("Food mode: click inside the tank to drop flakes.")
                            else:
                                cursor_mgr.set_mode("normal")
                                set_status("Food mode off.")
                        elif 6 <= mx <= 42 and 68 <= my <= 104:
                            clean_mode = not clean_mode
                            if clean_mode:
                                food_mode = False
                                cursor_mgr.set_mode("clean")
                                set_status("Cleaning mode: click the tank to scrub algae.")
                            else:
                                cursor_mgr.set_mode("normal")
                                set_status("Cleaning mode off.")
                        elif tr.collidepoint(mx, my):
                            ix = float(mx - tr.left)
                            iy = float(my - tr.top)
                            if food_mode:
                                n = spawn_food_at(env, ix, iy)
                                set_status(f"Dropped {n} food flakes!")
                            elif clean_mode:
                                do_action("clean")
                            else:
                                # Chest click (only when open)
                                chest_coins = chest.handle_click(mx, my)
                                if chest_coins > 0:
                                    earn_coins(cfg, chest_coins,
                                               float(chest._rect.centerx),
                                               float(chest._rect.top),
                                               coin_popups, log_event,
                                               f"Treasure chest! +{chest_coins} coins")
                                    set_status(f"Treasure chest! +{chest_coins} coins!")
                                    sound.play_coin_chest()
                                else:
                                    clicked = None
                                    for f in reversed(fish_list):
                                        if fish_screen_rect(f, tr).collidepoint(mx, my):
                                            clicked = f
                                            break
                                    if clicked is not None:
                                        fish_info.open(clicked, *surface.get_size(),
                                                       mx, my,
                                                       renderer.assets.fish_sheets)
                                        cfg["stat_profile_opens"] = int(cfg.get("stat_profile_opens", 0)) + 1
                                    else:
                                        # Try popping a bubble (rare coin reward ~1-in-5)
                                        bubble_pos = pop_bubble_at(env, mx, my, tr.left, tr.top)
                                        if bubble_pos is not None:
                                            cfg["stat_bubbles_popped"] = int(cfg.get("stat_bubbles_popped", 0)) + 1
                                            sound.play_bubble_pop()
                                            if random.random() < 0.20:
                                                earn_coins(cfg, 1,
                                                           float(bubble_pos[0]),
                                                           float(bubble_pos[1]),
                                                           coin_popups)
                                                sound.play_single_coin()
                        else:
                            # Drag/resize zones (only when not interacting with interior)
                            locked = bool(cfg.get("locked", False))
                            if not locked and win_mod.in_resize_handle(mx, my, *surface.get_size()):
                                drag_mode = "resize"
                                drag_screen_start = win_mod.get_screen_cursor() if USE_ABS_CURSOR else (mx, my)
                                drag_orig = surface.get_size()
                                drag_rel_accum = (0, 0)
                            elif not locked and win_mod.in_title_bar(mx, my, *surface.get_size()):
                                drag_mode = "move"
                                if USE_ABS_CURSOR:
                                    sc = win_mod.get_screen_cursor()
                                    wp = win_mod.get_position(sdl_win) or (0, 0)
                                    drag_offset = (sc[0] - wp[0], sc[1] - wp[1])
                                else:
                                    # macOS fallback: anchor to window position at drag start.
                                    drag_win_start = win_mod.get_position(sdl_win) or (0, 0)
                                    drag_rel_accum = (0, 0)
                    if ev.button == 3:
                        items = feed_menu()
                        # Reflect current toggle state
                        toggles = {
                            "pause": paused,
                            "toggle_lock": bool(cfg.get("locked", False)),
                            "toggle_top": bool(cfg.get("always_on_top", False)),
                            "toggle_phide": bool(cfg.get("pause_when_hidden", True)),
                            "toggle_names": bool(cfg.get("show_names", False)),
                            "toggle_moods": bool(cfg.get("show_moods", False)),
                            "toggle_mute": bool(cfg.get("sound_muted", False)),
                        }
                        for it in items:
                            if it.action in toggles:
                                it.checked = toggles[it.action]
                        context.open(items, ev.pos[0], ev.pos[1], surface.get_size())
                elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
                    drag_mode = None
                    drag_rel_accum = (0, 0)
                elif ev.type == pygame.MOUSEMOTION:
                    # Safety: MOUSEBUTTONUP may not be delivered if the cursor
                    # leaves the window while dragging.  Cancel drag when we
                    # detect the button is no longer held.
                    if drag_mode and not pygame.mouse.get_pressed()[0]:
                        drag_mode = None
                        drag_rel_accum = (0, 0)
                    if drag_mode:
                        if drag_mode == "move":
                            if USE_ABS_CURSOR:
                                cx, cy = win_mod.get_screen_cursor()
                                win_mod.set_position(sdl_win,
                                                     cx - drag_offset[0],
                                                     cy - drag_offset[1])
                                if IS_WINDOWS:
                                    pygame.event.clear(pygame.MOUSEMOTION)
                            else:
                                # macOS fallback: accumulate bounded rel movement.
                                rx = max(-40, min(40, int(ev.rel[0])))
                                ry = max(-40, min(40, int(ev.rel[1])))
                                drag_rel_accum = (
                                    drag_rel_accum[0] + rx,
                                    drag_rel_accum[1] + ry,
                                )
                                win_mod.set_position(sdl_win,
                                                     drag_win_start[0] + drag_rel_accum[0],
                                                     drag_win_start[1] + drag_rel_accum[1])
                        elif drag_mode == "resize":
                            if USE_ABS_CURSOR:
                                cx, cy = win_mod.get_screen_cursor()
                                dx = cx - drag_screen_start[0]
                                dy = cy - drag_screen_start[1]
                            else:
                                # macOS fallback: bounded rel accumulation.
                                rx = max(-40, min(40, int(ev.rel[0])))
                                ry = max(-40, min(40, int(ev.rel[1])))
                                drag_rel_accum = (
                                    drag_rel_accum[0] + rx,
                                    drag_rel_accum[1] + ry,
                                )
                                dx, dy = drag_rel_accum
                            pending_resize = (
                                max(win_mod.MIN_W, min(win_mod.MAX_W, drag_orig[0] + dx)),
                                max(win_mod.MIN_H, min(win_mod.MAX_H, drag_orig[1] + dy)),
                            )
                            last_resize_t = time.perf_counter()
                    elif pygame.mouse.get_pressed()[0] and not food_mode and not clean_mode:
                        # Drag-pickup: recover from activation-click MOUSEBUTTONDOWN
                        # being absorbed by Windows before the window gained focus.
                        # If the left button is still held while the mouse is in the
                        # title bar, start a move drag now.
                        mx2, my2 = ev.pos
                        locked = bool(cfg.get("locked", False))
                        if not locked and win_mod.in_title_bar(mx2, my2, *surface.get_size()):
                            drag_mode = "move"
                            if USE_ABS_CURSOR:
                                sc = win_mod.get_screen_cursor()
                                wp = win_mod.get_position(sdl_win) or (0, 0)
                                drag_offset = (sc[0] - wp[0], sc[1] - wp[1])
                            else:
                                drag_win_start = win_mod.get_position(sdl_win) or (0, 0)
                                drag_rel_accum = (0, 0)
                elif ev.type == pygame.WINDOWFOCUSGAINED:
                    pass
                elif ev.type == pygame.WINDOWFOCUSLOST:
                    pass

            # -------- tray --------
            ta = tray.poll()
            if ta:
                do_action(ta)

            # -------- pending resize (debounce: apply once, 50 ms after drag pauses) --------
            if pending_resize is not None and now - last_resize_t >= 0.05:
                _rw, _rh = pending_resize
                pending_resize = None
                _saved_pos = win_mod.get_position(sdl_win)
                surface = win_mod.resize_surface(_rw, _rh)
                # set_mode() recreates the SDL window — must refresh the handle.
                sdl_win = win_mod.get_sdl_window()
                if sdl_win and _saved_pos:
                    win_mod.set_position(sdl_win, *_saved_pos)
                renderer.surface = surface
                renderer._static_bg = None
                tr = renderer.compute_tank_rect()
                env.tank_w = tr.w
                env.tank_h = tr.h

            # -------- simulation --------
            should_sim = not paused and not (hidden and cfg.get("pause_when_hidden", True))
            if should_sim:
                sim_accum += frame_dt * float(cfg.get("time_scale", 1.0))
                steps = 0
                # Compute once per frame; fish rarely die mid-frame, and even
                # if one does the count being off by 1 for one step is harmless.
                algae_eater_count = sum(1 for f in fish_list if f.sp.get("algae_eater"))
                while sim_accum >= sim_dt and steps < 6:
                    sim_accum -= sim_dt
                    steps += 1
                    update_environment(env, sim_dt, cfg, fish_count=len(fish_list),
                                       algae_eater_count=algae_eater_count)
                    for f in fish_list:
                        update_fish(f, env.tank_w, env.tank_h, sim_dt, env.food, env,
                                    fish_list=fish_list)
                        update_biology(f, sim_dt,
                                       float(cfg.get("hunger_rate", 0.5)),
                                       float(cfg.get("growth_rate", 0.5)),
                                       float(cfg.get("age_rate", 1.0)))
                        maybe_change_layer(f, env.tank_h, sim_dt)
                    # Mood update: count near-fish for each fish (solitary stress)
                    max_fish_cap = int(cfg.get("max_fish", 14))
                    for f in fish_list:
                        near = sum(
                            1 for g in fish_list
                            if g is not f
                            and abs(g.x - f.x) < 50 and abs(g.y - f.y) < 50
                        )
                        update_mood(f, sim_dt, float(env.algae),
                                    len(fish_list), max_fish_cap, near)
                    # Track deaths for event log + graveyard memorial
                    _dead = [f for f in fish_list if f.health <= 0.01]
                    for fd in _dead:
                        age_d = fd.age / 86400.0
                        log_event(cfg,
                                  f"{fd.name} has died (age {age_d:.1f}d)",
                                  "death")
                        log_death(cfg, fd)
                        fish_roster.invalidate_thumb(fd)
                    cull_dead(fish_list)
                    juvenile = try_breed(fish_list, env.tank_w, env.tank_h, cfg, sim_dt)
                    if juvenile is not None:
                        fish_list.append(juvenile)
                        mark_seen(cfg, juvenile.sp.get("name", ""))
                        cfg["stat_total_fish"] = int(cfg.get("stat_total_fish", 0)) + 1
                        cfg["stat_bred_fish"]  = int(cfg.get("stat_bred_fish", 0)) + 1
                        log_event(cfg,
                                  f"{juvenile.name} was born"
                                  + (f" (child of {juvenile.born_from[0]} & {juvenile.born_from[1]})"
                                     if juvenile.born_from else ""),
                                  "birth")
                    prev_count = len(fish_list)
                    added = ensure_min_population(fish_list, env.tank_w, env.tank_h, cfg)
                    cfg["stat_total_fish"] = int(cfg.get("stat_total_fish", 0)) + added
                    # Mark newly spawned fish as seen
                    for new_f in fish_list[prev_count:]:
                        mark_seen(cfg, new_f.sp.get("name", ""))
                    # Log any rare fish that naturally spawned
                    for new_f in fish_list[prev_count:]:
                        if new_f.sp.get("super_rare"):
                            log_event(cfg,
                                      f"[**] An epic {new_f.sp['name']} appeared: {new_f.name}!",
                                      "rare")
                            _fire_achievement("super_rare")
                            _fire_achievement("rare_encounter")
                        elif new_f.sp.get("rare"):
                            log_event(cfg,
                                      f"[*] A rare {new_f.sp['name']} appeared: {new_f.name}!",
                                      "rare")
                            _fire_achievement("rare_encounter")

            # -------- real-time day/night override --------
            if cfg.get("night_cycle", True):
                _wall_time = datetime.datetime.now()
                hour = _wall_time.hour + _wall_time.minute / 60.0 + _wall_time.second / 3600.0
                # Smooth sine: 0 at noon, peaks at midnight; cap at 0.28
                phase = (hour - 12.0) / 24.0
                raw = (1.0 - math.cos(phase * math.tau)) * 0.5   # 0-1
                env.night_factor = min(0.28, raw * 0.45)          # gentle dark

            # -------- status bar TTL countdown ------------
            if status_timer > 0:
                status_timer -= 1
                if status_timer == 0:
                    status_msg = ""
            else:
                # Idle: count down to next rotating tip
                tip_countdown -= 1
                if tip_countdown <= 0:
                    _tip_idx = (_tip_idx + 1) % len(_TIPS)
                    set_status(_TIPS[_tip_idx], 240)
                    tip_countdown = 450

            # -------- stats accumulation --------
            stat_accum += frame_dt
            if stat_accum >= 60.0:
                cfg["stat_total_days"] = float(cfg.get("stat_total_days", 0)) + stat_accum / 86400.0
                cfg["stat_peak_fish"]  = max(int(cfg.get("stat_peak_fish", 0)), len(fish_list))
                if int(cfg.get("difficulty", 2)) == 5 and len(fish_list) > 0:
                    cfg["stat_nightmare_days"] = float(cfg.get("stat_nightmare_days", 0.0)) + stat_accum / 86400.0
                stat_accum = 0.0
                # Run full achievement checks once per minute
                newly_unlocked = check_achievements(cfg, fish_list)
                for aid in newly_unlocked:
                    _ach  = next((a for a in ACHIEVEMENTS if a["id"] == aid),
                                 {"name": aid, "desc": ""})
                    name  = _ach["name"]
                    desc  = _ach["desc"]
                    log_event(cfg, f"[*] Achievement unlocked: {name}", "info")
                    sound.play_achievement()
                    # Award coins for each newly unlocked achievement
                    reward = ACHIEVEMENT_COIN_REWARDS.get(aid, 0)
                    if reward > 0:
                        earn_coins(cfg, reward, float(tr.centerx), float(tr.centery),
                                   coin_popups, log_event,
                                   f"Achievement reward: +{reward} coins")
                    achievement_popup.push(name, desc, reward)

            # Update chest, fish store, and coin popups (every frame)
            burst_positions = chest.update(frame_dt, cfg)
            if burst_positions:
                spawn_chest_burst(env, burst_positions)
                sound.play_chest_creak()
            fish_store.update(frame_dt, cfg)
            update_popups(coin_popups, frame_dt)

            renderer.tick_animations(frame_dt)
            cursor_mgr.update(frame_dt)
            full_reset_dlg.update(frame_dt)
            achievement_popup.update(frame_dt)
            sound.update()
            sound.set_volume(float(cfg.get("sound_volume", 0.7)))
            sound.set_muted(bool(cfg.get("sound_muted", False)))
            # Poll update check result so settings panel can display it
            settings.update_info = update_check.get_result()
            renderer.food_mode   = food_mode
            renderer.clean_mode  = clean_mode
            roster_mode              = fish_roster.visible
            renderer.roster_mode        = roster_mode
            renderer.event_log_mode    = event_log.visible
            renderer.achievements_mode = achievements.visible
            renderer.encyclopedia_mode = encyclopedia.visible
            renderer.graveyard_mode = graveyard_panel.visible
            store_mode = fish_store.visible
            renderer.store_mode    = store_mode
            renderer.castle_choice = int(cfg.get("castle_choice", 1))
            renderer.bg_choice     = int(cfg.get("bg_choice", 1))
            renderer.plant_choice  = int(cfg.get("plant_choice", 1))
            tr = renderer.compute_tank_rect()
            stats = {
                "fish": len(fish_list),
                "food": sum(1 for fd in env.food if fd.active and not fd.eaten),
                "fps": fps_smoothed,
                "algae_pct": int(env.algae),
                "coins": int(cfg.get("coins", 0)),
            }
            renderer.draw(fish_list, env,
                          paused=paused,
                          locked=bool(cfg.get("locked", False)),
                          active=True,
                          show_names=bool(cfg.get("show_names", False)),
                          show_moods=bool(cfg.get("show_moods", False)),
                          scan_lines=bool(cfg.get("scan_lines", True)),
                          stats=stats,
                          sprite_cache=sprite_cache,
                          status_msg=status_msg,
                          chest=chest,
                          coin_popups=coin_popups,
                          encyclopedia_seen=sum(
                              1 for sp in SPECIES
                              if is_seen(cfg, sp.get("name", ""))
                          ))
            context.draw(surface)
            settings.draw(surface)
            fish_roster.draw(surface, fish_list, tr, renderer.assets.fish_sheets)
            fish_info.draw(surface)
            event_log.draw(surface, cfg, tr)
            achievements.draw(surface, cfg, tr)
            encyclopedia.draw(surface, cfg, tr, renderer.assets.fish_sheets)
            graveyard_panel.draw(surface, cfg, tr)
            fish_store.draw(surface, cfg, tr, renderer.assets.fish_sheets, fish_list,
                            btn_icons=renderer.assets.btn_icons_sm)
            confirm_dlg.draw(surface)
            full_reset_dlg.draw(surface)
            about_dlg.draw(surface)
            how_to_play.draw(surface)
            achievement_popup.draw(surface)

            # ── Tooltips ──────────────────────────────────────────
            tooltip.clear_regions()
            # Toolbar buttons (fixed positions in left chrome)
            _tb_tips = [
                (pygame.Rect(6,  28, 36, 36), "Feed fish  [F]"),
                (pygame.Rect(6,  68, 36, 36), "Clean algae  [C]"),
                (pygame.Rect(6, 108, 36, 36), "Fish List"),
                (pygame.Rect(6, 148, 36, 36), "Event Log"),
                (pygame.Rect(6, 188, 36, 36), "Achievements"),
                (pygame.Rect(6, 228, 36, 36), "Encyclopaedia"),
                (pygame.Rect(6, 268, 36, 36), "Graveyard"),
                (pygame.Rect(6, 308, 36, 36), "Fish Shoppe"),
            ]
            for _r, _t in _tb_tips:
                tooltip.register(_r, _t)
            # Title-bar stats (right-aligned area)
            _w, _h = surface.get_size()
            tooltip.register(pygame.Rect(_w // 3, 3, _w // 3, 14),
                             "Fish: living fish in tank")
            tooltip.register(pygame.Rect(_w * 2 // 3, 3, _w // 6, 14),
                             "Algae % — clean before it reaches 100%")
            tooltip.register(pygame.Rect(_w * 5 // 6, 3, _w // 6 - 2, 14),
                             "Coins — earned from fish care & achievements")
            # Resize handle (bottom-right corner)
            tooltip.register(pygame.Rect(_w - 20, _h - 20, 20, 20),
                             "Drag to resize")
            # Dynamic panel regions (mood/rarity dots)
            for _tr_r, _tr_t in fish_roster.tip_regions:
                tooltip.register(_tr_r, _tr_t)
            for _tr_r, _tr_t in fish_store.tip_regions:
                tooltip.register(_tr_r, _tr_t)
            tooltip.update(frame_dt, pygame.mouse.get_pos())
            tooltip.draw(surface, renderer.font)

            cursor_mgr.draw(surface)
            pygame.display.flip()

            clock.tick(RENDER_FPS)
            actual_fps = clock.get_fps()
            fps_smoothed = fps_smoothed * 0.9 + actual_fps * 0.1

        # ---- shutdown ----
        pos = win_mod.get_position(sdl_win)
        if pos is not None:
            cfg["window_x"], cfg["window_y"] = pos
        w, h = surface.get_size()
        cfg["window_w"], cfg["window_h"] = w, h
        cfg_mod.save(cfg)
        if cfg.get("persist_state", True):
            cfg_mod.save_fish_state(fish_list)
        tray.stop()
        pygame.quit()
        return 0
    except Exception:
        log = logging.getLogger("aquarium")
        log.exception("Fatal error in main loop")
        tb_text = traceback.format_exc()
        log_path = str(LOG_DIR / "aquarium.log")
        try:
            dlg = CrashDialog(tb_text, log_path)
            dlg.run()
        except Exception:  # noqa: BLE001 — crash dialog itself failed; just exit
            pass
        return 1
    finally:
        _release_lock()


if __name__ == "__main__":
    raise SystemExit(main())
