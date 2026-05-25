# Changelog

All notable changes to Aquarium 98 are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

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

[Unreleased]: https://github.com/trumanac/Aquarium98/compare/v1.0.4...HEAD
[1.0.4]:      https://github.com/trumanac/Aquarium98/releases/tag/v1.0.4
[1.0.3]:      https://github.com/trumanac/Aquarium98/releases/tag/v1.0.3
[1.0.2]:      https://github.com/trumanac/Aquarium98/releases/tag/v1.0.2
[1.0.1]:      https://github.com/trumanac/Aquarium98/releases/tag/v1.0.1
[1.0.0]:      https://github.com/trumanac/Aquarium98/releases/tag/v1.0.0
