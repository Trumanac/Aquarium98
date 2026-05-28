# Changelog

All notable changes to Aquarium 98 are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

---

## [1.0.11] — 2026-05-27

### Added
- **Sim Speed slider in Settings** — new *Sim Speed* slider (0.25× – 4.00×)
  exposes the `time_scale` config key so players can slow down or speed up the
  simulation without editing JSON.
- **Sell fish from the Fish Profile** — a *Sell (Nc)* button now appears in
  the bottom-left of the Fish Profile popup. Clicking it removes the fish,
  awards coins, and logs the sale — no need to open the Shoppe's sell list.
- **Algae danger warning** — the status bar shows a one-time warning when
  algae reaches 80 %. The warning resets once the tank drops below 70 %.
- **Critical-health fish warning** — the status bar notifies the player when
  any fish's HP falls below 20 %. The warning clears once the fish recovers
  above 40 % HP or is removed from the tank.
- **Panel keyboard shortcuts** — five new hotkeys to quickly toggle overlay
  panels without a mouse:
  - `G` — Graveyard
  - `I` — Encyclopaedia
  - `L` — Event Log
  - `A` — Achievements

### Fixed
- **Cursor hotspot corrected (`hx` 7 → 17)** — the normal-cursor sprite's
  visual fingertip is at pixel 17 from the left edge; the hotspot was set to
  7, causing all click positions to register ~10 px left of the cursor.
  Settings checkboxes were therefore unreachable without the compensating
  hit-area extension also added in this release.
- **Settings checkbox hit area extended 10 px left** — provides a safety
  margin so clicks that land just before the checkbox rect still register.
- **`_persist_state_now` spurious WARNING on every exit** — `surface.get_size()`
  was called via `atexit` after `pygame.quit()` had already torn down the
  display. Now guarded with `pygame.display.get_init()`.
- **`rescale_environment` new-dimension guard** — added `new_w ≤ 0 or new_h ≤ 0`
  guard alongside the existing old-dimension guard; without it an extreme
  resize edge case would zero out all entity positions.
- **`fish_from_dict` species-miss logging** — unknown-species path now logs
  both the species name and fish name at WARNING level instead of silently
  returning `None`.
- **`MIN_H` aligned with config floor (366 → 406)** — the SDL resize minimum
  was 366 but `config.py` clamps loaded `window_h` to 406; any height between
  366–405 set by the user would silently snap taller on next launch.
- **Removed dead `_tint()` helper in `renderer.py`** — defined but never
  called anywhere in the codebase.

---

## [1.0.10] — 2026-05-27

### Added
- **Encyclopedia shoppe discovery** — fish species now unlock in the
  Encyclopaedia when the player opens the Fish Shoppe and sees them in the
  buy slots, rather than only on purchase. Auto-restock while the shoppe is
  open and manual restocks also reveal the newly displayed species.

### Changed
- **`ensure_min_population` respects existing species** — the maintenance
  spawner that keeps the tank above `min_fish` now only spawns species already
  present in the tank. Falls back to common species only when the tank is
  completely empty, preventing unknown fish from appearing uninvited.
- **CPO Crayfish now eats algae and grounded food** — added `algae_eater`
  flag so crawdads feed off algae and sunken food flakes the same way Amano
  Shrimp do (Amano Shrimp already had this flag).
- **`max_food` difficulty cap enforced** — food spawning now respects the
  per-difficulty `max_food` config value (Nightmare: 16 → Easy: 40).
  Previously the active-flake count was only bounded by the hard pool ceiling
  of 90 regardless of difficulty.

### Fixed
- **Solitary-fish mood scan O(n²) → O(1) common case** — neighbor proximity
  checks are now skipped entirely when no solitary-personality fish are in
  the tank (the common case). When solitary fish exist the scan uses a
  symmetric pass, halving comparisons.
- **`fish_from_dict` bare key access** — `d["name"]`, `d["layer"]`, `d["x"]`,
  `d["y"]` changed to safe `.get()` calls with fallbacks so a single
  corrupted field no longer raises `KeyError`.
- **Per-entry save isolation in `load_fish_state`** — a malformed fish entry
  in `fish_state.json` now logs a warning and skips that entry instead of
  causing the entire load to return `[]` and wiping the tank.

---

## [1.0.9] — 2026-05-26

### Added
- **Max Fish slider** — new slider in the Settings dialog (range 4–30) lets
  players set their own fish cap independently of the difficulty preset.
  Changing the difficulty slider resets Max Fish to the preset default as a
  sensible starting point; players can then override it before saving.
  The chosen value survives app updates and reinstalls (lives in the user
  config dir, separate from the install directory).

### Fixed
- **Double castle randomisation on full reset** — `_do_reset` now sets
  `cfg["_tank_initialized"] = True` after randomising decor, preventing a
  second randomisation on the very next startup (previously `_tank_initialized`
  was absent from the post-full-reset config, causing the startup code to
  re-roll the castle choice).
- **macOS DMG build (`hdiutil: create failed — Resource busy`)** — CI runner
  fix: added `.metadata_never_index` sentinel, switched `cp -r` to `ditto`,
  and added a 3-attempt retry loop in `create_dmg.sh`.
- **Fish/bubbles/food cluster in top-left after window resize** — entity
  positions are now proportionally rescaled to the new tank dimensions in the
  `WINDOWRESIZED` handler via `rescale_environment()`.

### Changed
- **Fish caps raised** — difficulty preset maximums increased so larger tanks
  feel alive at bigger window sizes: Peaceful 30 (was 18), Normal 25 (was 16),
  Hard 20 (was 14), Brutal 15 (was 12). Nightmare stays at 10.
  Hard cap (`SLOT_CAPS["max_fish"]`) raised from 18 to 30.
- **Difficulty preset no longer overwrites `max_fish`** — `_validate()` now
  applies only rate variables (hunger, breed, algae, etc.) from the preset.
  `max_fish` is clamped to a valid range but preserves the user's saved value
  across difficulty changes and app updates.
- **`config.default.json`** — added explicit `max_fish: 25` (Normal default)
  so the `_migrate()` path is self-documenting for new config keys.

### Optimised
- Stale `cfg.get("max_fish", 14/16)` fallback defaults updated to `25`
  throughout `aquarium.py`, `achievements_panel.py`, `population.py`, and
  `environment.py` (cosmetic — `_validate()` always sets the key before these
  are reached, but the stale values were misleading).

---

## [1.0.8] — 2026-05-27

### Fixed
- **Full reset now clears all stats** — `stat_nightmare_days`, `stat_profile_opens`,
  and `stat_bred_fish` were not zeroed on a full reset; they now are.
- **Hermit Crab immediately leaves shell on spawn** — `crab_timer` was never
  initialised in `make_fish`, so the crab transitioned from `in_shell` →
  `emerging` on the very first simulation frame.  Fixed by assigning a random
  8–20 s initial timer (mirrors the frog stagger fix).
- **`config.default.json` window height default corrected** — default `window_h`
  was `320` but config validation always clamps to the minimum `366` (needed to
  fit all 8 toolbar buttons plus the status bar).  Default is now `366` so new
  installations open at the intended size without a silent clamp.
- **Stale food-pool comment** in `environment.py` corrected from "15 fixed slots
  (5 back + 5 mid + 5 front)" to "30 fixed slots (10 back + 10 mid + 10 front)".

### Changed
- **Multi-monitor window restore** — window position is now set via
  `sdl_win.position` after SDL window creation, replacing the unreliable
  `SDL_VIDEO_WINDOW_POS` env-var hint.  A `_title_bar_on_screen()` guard using
  `MonitorFromPoint` on Windows prevents restoring to an invisible off-screen
  position on any multi-monitor layout (including left-side monitors with
  negative X coordinates).

### Optimised
- `_MOOD_COLOURS` dict moved from a per-call local to a module-level constant
  in `renderer.py`, eliminating a new dict allocation for every visible fish
  every frame when mood indicators are shown.

---

## [1.0.7] — 2026-05-26

### Added
- **In-app updater** — the version/update area in Settings is now a clickable
  button.  States cycle through: *Check for Updates* → *Download* (with a
  live progress bar) → *Install & Restart*.  The Inno Setup installer is
  downloaded to a temp directory and launched silently (`/SILENT /NORESTART`);
  the app then quits so the installer can replace the previous version.
  Works on Windows (installer .exe), macOS (DMG open), and Linux (AppImage).
  All network errors are swallowed; the feature never blocks or crashes the app.
- `update_check.recheck()` — re-triggers the background GitHub API check so
  the user can manually force a fresh look.
- `update_check.start_download()` / `get_download_state()` / `launch_installer()`
  public API for the download/install flow.

---

## [1.0.6] — 2026-05-26

### Fixed
- **`rare_encounter` / `super_rare` achievements unreachable** — after
  `ensure_min_population` was changed to only spawn common fish (v1.0.5),
  the only code path that fired these achievements became dead code.  Fixed
  by adding rare-fish detection directly to `check_achievements()` (scans
  fish currently in tank) and firing the achievements immediately when a
  rare/epic fish is purchased from the Fish Shoppe.
- **Hermit Crab rarity flag** corrected from `uncommon` → `rare` to match
  its section comment and intended 3 % spawn tier; it now shows as "Rare"
  in the Fish Shoppe and earns the `rare_encounter` achievement.
- `stat_bubbles_popped` and `stat_shoppe_buys` added to `config.default.json`
  (were accessed safely via `cfg.get()` fallback but absent from the defaults
  file).
- Removed dead "log any rare fish that naturally spawned" block from
  `aquarium.py` (unreachable since `ensure_min_population` change).

---

## [1.0.5] — 2026-05-25

### Fixed
- **Drag-to-move / drag-to-resize completely broken on Windows** — `GetCursorPos`
  (via ctypes) was always returning the fixed screen-centre coordinates `(1280, 720)`
  on a 2560×1440 display, regardless of actual cursor position.  Removed the
  broken `USE_ABS_CURSOR` / `get_screen_cursor()` path entirely; all platforms
  now use `ev.rel` accumulation with `pygame.event.clear(MOUSEMOTION)` after each
  `set_position()` call to suppress SDL feedback events.
- `pygame.event.clear(MOUSEMOTION)` also added in the `WINDOWRESIZED` handler so
  spurious events queued by `resize_surface()` do not corrupt the resize accumulator.
- `in_title_bar` and `in_resize_handle` boundary conditions corrected (`<` instead
  of `<=`) to avoid off-by-one at window edges.
- **Breeding offspring downgraded to common** — rare/uncommon fish now breed true;
  offspring are always the same species as the parents.
- **Food clicks silently dropped** when all food slots were active; `spawn_food_at`
  now dynamically expands the slot list so no click is ever lost.
- **Custom cursor hotspots** re-measured after sprite rescaling; glove, food-shaker,
  and cleaning-sponge cursors now track the pointer accurately.

### Changed
- **Fish Shoppe rarity overhaul** — each slot is rolled independently:
  ~1 % epic, ~5 % rare, ~16 % uncommon, ~78 % common.  Prices updated:
  Common 10–30 · Uncommon 40–90 · Rare 200–350 · Epic 600–900 coins.
- Toolbar geometry extracted into named constants (`TB_BTN_X`, `TB_BTN_Y_START`,
  `TB_BTN_SIZE`, `TB_BTN_SPACING`, `TB_BTN_KEYS`) and a helper `toolbar_button_rect(key)`.
- `_draw_toolbar` refactored to iterate `TB_BTN_KEYS` instead of hard-coded coordinates.
- `set_window_size(sdl_win, w, h)` added to `window.py` for OS-level resize without
  touching the pygame surface (step-1 of flash-free resize).

### UI Polish
- All panel close buttons have hitboxes inflated by 8 px for easier clicking.
- Clicking outside an open panel (Achievements, Encyclopaedia, Event Log, Graveyard)
  now closes it.
- `FishRosterPanel`: close button returns `True`; row click returns fish index;
  click outside panel closes it.
- `FishInfoPanel`: returns `"close_inside"` vs `"close_outside"` so callers can
  distinguish dismissal source.
- `ContextMenu.handle_event` returns a proper bool for `MOUSEMOTION` and
  `MOUSEBUTTONDOWN` (correct event-consumption contract).
- `ConfirmDialog`, `SettingsDialog`, and `FishStorePanel` buttons all have
  inflated hitboxes; store returns `("consume",)` tuple on handled events.

---

## [1.0.4] — 2026-05-25

### Added
- **Ambient audio** — bubble pops (3 randomised variants), treasure-chest coin sound,
  single-coin reward sound, and sparse ambient water splashes (15–60 min interval).
- **Show Fish Moods** — right-click context menu toggle (like Show Fish Names).
  Renders a small colour-coded dot above each fish: green = happy, yellow = content,
  orange = hungry, red = stressed.
- **New-version notification** — silent background check against the GitHub Releases
  API on startup; shows a banner in the status bar when an update is available.
  Settings panel also displays current version and update status.
- **Quick Reference page** in the How to Play guide — full keyboard shortcut and
  mouse control cheat sheet accessible from inside the app (now 9 pages total).
- **Startup crash-report dialog** — Win98-style error popup with “Copy Details”
  button and log file path on any fatal exception instead of silent exit.

### Changed
- Castle/decor slider range reduced from 7 → 5 (two deleted variants removed).
- Castle randomisation on fresh tank uses the correct 1–5 range.

### Fixed
- **Full reset — old tank reappeared**: two root causes fixed.
  1. `roster_mode`, `food_mode`, `clean_mode` were missing from the `nonlocal`
     declaration inside `_do_reset`; assignments were silently discarded.
  2. New fish list and new `castle_choice` now persisted to disk **immediately**
     after reset, preventing a stale `fish_state.json` from loading on next start.
- **All panels now close on tank reset** — Event Log, Achievements, Encyclopaedia,
  Graveyard, Fish Shoppe, and context menu are all closed during `_do_reset` so
  stale content never bleeds through after a reset.
- **Startup achievement rewards** — first-launch achievements (e.g. “First Steps”)
  now correctly award their coin bonus and popup notification.
- **Sound volume/mute no longer called every frame** — `set_volume` and `set_muted`
  short-circuit when the value is unchanged, avoiding redundant `set_volume` calls
  on all 10 sounds at 30 Hz.
- Fish bought or sold are now persisted to disk **immediately**, closing the
  5-second data-loss window on forced-quit.
- `config.json` and `fish_state.json` both written atomically (temp + rename).
- `castle_choice`, `bg_choice`, `plant_choice` are now clamped in `_validate()`
  so stale out-of-range values in existing configs are silently corrected.
- Floor fish spawn loop now uses a `for…else` fallback so the castle-zone
  exclusion can never leave a fish without a valid spawn position.

---

## [1.0.3] — 2026-05-13

### Added
- macOS absolute-cursor drag via bundled SDL2 library; `USE_ABS_CURSOR` is now
  detected at runtime so the same binary works on Windows, macOS, and Linux.

---

## [1.0.2] — 2026-05-10

### Fixed
- Linux/macOS drag-resize snap and feedback loop eliminated.
- `sdl_win` handle refreshed after `resize_surface` to prevent stale window
  reference on subsequent moves.
- Drag cancelled correctly when mouse button released outside the window.

---

## [1.0.1] — 2026-05-08

### Fixed
- Startup and system-tray compatibility on Linux and macOS.
- Linux drag/resize uses Xlib for absolute screen cursor coordinates.

---

## [1.0.0] — 2026-05-25

### Added
- **35 unique species** across four rarity tiers (Common 16 · Uncommon 10 · Rare 8 · Epic 1).
- **25 achievements** ranging from "First Steps" to "Nightmare Survivor".
- **Coin economy** — earn coins by feeding, cleaning, popping bubbles, opening
  treasure chests, and unlocking achievements; spend in the Fish Shoppe.
- **Fish Shoppe** — buy new species, sell fish you no longer want, restock the
  daily selection with coins.
- **Fish Encyclopaedia** — tracks all 35 species; unseen entries appear as
  silhouettes until first discovered. Progress shown in title bar (X/35).
- **Fish Roster** — live table of every fish with health bar, hunger, age, and
  colour-coded mood/rarity dots with tooltips.
- **Fish Profile** — click any fish to open a detailed panel with stats,
  rename field, and species fun facts.
- **Event Log** — timestamped history of every notable tank event.
- **Achievements panel** — 25 milestones with coin bonuses on first unlock.
  Achievements renamed "Epic Find!" (was "Super Rare!") to match rarity branding.
- **Graveyard** — memorial log for every fish that has died, with cause of death.
- **How to Play guide** — 8-page illustrated in-app tutorial (auto-shown on first
  launch): Welcome · Controls · Feed & Clean · Fish & Mood · Coins & Shoppe ·
  Toolbar Panels · Window & Tray · Tips.
- **Tooltip system** — Win98-style delayed tooltips on all toolbar buttons, mood
  dots, and rarity dots.
- **Tray minimise** — minimise to system tray via Esc or right-click menu; restore
  on tray icon click.
- **Settings dialog** — sliders and checkboxes for opacity, fish cap, time scale,
  hunger/breed/algae/bubble rates, background (4), plant (3), castle (5), and
  difficulty (1–5 with named presets).
- **Day/night cycle** — tank dims and fish become less active at night.
- **5 castle / decor options**, 4 backgrounds, 3 plant styles — all persist
  across sessions and app updates via `config.json`.
- **Custom animated cursors** — diving glove (default), food shaker (Feed mode),
  cleaning sponge (Clean mode); 5-frame click animation on each.
- **Win98 aesthetic** — authentic title bar gradients, bevelled panels, scan-line
  overlay, retro system tray icon, and splash screen on every launch.
- **Performance mode** — reduces render overhead for low-end machines.
- **Atomic saves** — `config.json` and `fish_state.json` written via temp-file
  rename to prevent corruption on power loss.
- **Config migration** — `_migrate()` fills missing keys from defaults;
  `_validate()` clamps all values so future changes never leave an invalid config.
- **Startup singleton lock** — prevents duplicate instances.
- **Logging** — rotating log file (`aquarium.log`, 500 KB × 3 backups) plus
  stdout, written to `~/Documents/Aquarium98/logs/`.
- **Cross-platform packaging** — GitHub Actions CI builds Windows installer
  (Inno Setup), macOS DMG, and Linux AppImage on every tagged release.

### Species highlights
Fish breed naturally, age, and eventually pass on.  Bottom-dwellers crawl the
sand, algae eaters cling to the glass, schooling fish flock together, and the
elusive Moonshell Hermit (Epic) is a tank highlight when it appears.

---

[Unreleased]: https://github.com/trumanac/Aquarium98/compare/v1.0.7...HEAD
[1.0.7]:      https://github.com/trumanac/Aquarium98/releases/tag/v1.0.7
[1.0.6]:      https://github.com/trumanac/Aquarium98/releases/tag/v1.0.6
[1.0.5]:      https://github.com/trumanac/Aquarium98/releases/tag/v1.0.5
[1.0.4]:      https://github.com/trumanac/Aquarium98/releases/tag/v1.0.4
[1.0.3]:      https://github.com/trumanac/Aquarium98/releases/tag/v1.0.3
[1.0.2]:      https://github.com/trumanac/Aquarium98/releases/tag/v1.0.2
[1.0.1]:      https://github.com/trumanac/Aquarium98/releases/tag/v1.0.1
[1.0.0]:      https://github.com/trumanac/Aquarium98/releases/tag/v1.0.0
