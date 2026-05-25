"""test_smoke.py — Smoke tests for Aquarium 98.

Tests the audio subsystem end-to-end and version-check helper.

Run with:
    .venv\\Scripts\\python test_smoke.py          (Windows)
    .venv/bin/python test_smoke.py              (macOS / Linux)

Exit code 0 = all tests passed.  Non-zero = failures printed above.
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PASSED: list[str] = []
_FAILED: list[tuple[str, str]] = []


def _run(fn):
    name = fn.__name__
    print(f"[TEST] {name}")
    try:
        fn()
        _PASSED.append(name)
    except AssertionError as exc:
        print(f"       FAIL: {exc}")
        _FAILED.append((name, str(exc)))
    except Exception as exc:  # noqa: BLE001
        print(f"       ERROR: {type(exc).__name__}: {exc}")
        _FAILED.append((name, f"{type(exc).__name__}: {exc}"))


# ---------------------------------------------------------------------------
# Audio tests
# ---------------------------------------------------------------------------

def _make_sound_manager():
    """Initialize pygame.mixer and return a fresh SoundManager."""
    import pygame  # type: ignore[import]
    if not pygame.mixer.get_init():
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()
    # Re-import to avoid cached module state between test functions
    from src.sound_manager import SoundManager  # noqa: PLC0415
    return SoundManager()


def test_sound_manager_loads_all_sounds():
    """SoundManager._ok should be True and all nine sounds should load."""
    snd = _make_sound_manager()

    assert snd._ok, (
        "SoundManager._ok is False after init — "
        "mixer may not be available or an audio file is missing"
    )
    assert snd._coin_chest  is not None, "CoinChest.mp3 failed to load"
    assert snd._single_coin is not None, "SingleCoin.mp3 failed to load"
    assert snd._achievement is not None, "Achievement.wav failed to load"
    assert len(snd._bubble_pops) == 3, (
        f"Expected 3 bubble-pop sounds, got {len(snd._bubble_pops)}"
    )
    assert len(snd._splashes) == 3, (
        f"Expected 3 splash sounds, got {len(snd._splashes)}"
    )
    assert len(snd._all_sounds) == 10, (
        f"Expected 10 total sounds in _all_sounds, got {len(snd._all_sounds)}"
    )
    print("       OK — all 10 audio files loaded")

    import pygame  # type: ignore[import]
    pygame.mixer.quit()


def test_sound_play_methods_do_not_raise():
    """Every public play_* method should execute without raising."""
    snd = _make_sound_manager()

    if not snd._ok:
        print("       SKIP — audio device unavailable, play methods not tested")
        return

    snd.set_volume(0.0)          # silent during testing

    snd.play_coin_chest()
    snd.play_single_coin()
    snd.play_bubble_pop()
    snd.play_achievement()
    snd.update()                 # ambient splash timer — should not fire immediately

    print("       OK — play_coin_chest / play_single_coin / play_bubble_pop / play_achievement / update")

    import pygame  # type: ignore[import]
    pygame.mixer.stop()
    pygame.mixer.quit()


def test_volume_clamps_correctly():
    """set_volume() must clamp values outside 0.0–1.0."""
    snd = _make_sound_manager()

    snd.set_volume(0.5)
    assert snd._volume == 0.5, f"Expected 0.5, got {snd._volume}"

    snd.set_volume(1.5)
    assert snd._volume == 1.0, f"Expected 1.0 (clamped), got {snd._volume}"

    snd.set_volume(-0.5)
    assert snd._volume == 0.0, f"Expected 0.0 (clamped), got {snd._volume}"

    print("       OK — volume clamped to [0.0, 1.0]")

    import pygame  # type: ignore[import]
    pygame.mixer.quit()


def test_mute_sets_effective_volume_to_zero():
    """When muted, every Sound's channel volume should be 0.0."""
    snd = _make_sound_manager()

    snd.set_volume(0.7)
    snd.set_muted(True)
    assert snd._muted is True

    # All loaded sounds should have been updated to 0.0
    for s in snd._all_sounds:
        v = s.get_volume()
        assert v == 0.0, f"Expected 0.0 while muted, got {v}"

    snd.set_muted(False)
    for s in snd._all_sounds:
        v = s.get_volume()
        assert abs(v - 0.7) < 0.01, f"Expected ~0.7 after unmute, got {v}"

    print("       OK — mute/unmute adjusts all Sound volumes correctly")

    import pygame  # type: ignore[import]
    pygame.mixer.quit()


# ---------------------------------------------------------------------------
# update_check tests
# ---------------------------------------------------------------------------

def test_parse_version_formats():
    """_parse_version must handle typical semver tags and bad input."""
    from src.update_check import _parse_version  # noqa: PLC0415

    assert _parse_version("1.0.0") == (1, 0, 0)
    assert _parse_version("v1.2.3") == (1, 2, 3)
    assert _parse_version("2.0")    == (2, 0)
    assert _parse_version("10.3")   == (10, 3)
    assert _parse_version("v0.9")   == (0, 9)
    assert _parse_version("bad")    == (0,)    # error fallback
    assert _parse_version("")       == (0,)

    # Comparison: tagged version newer than current
    assert _parse_version("1.0.1") > _parse_version("1.0.0")
    assert _parse_version("2.0.0") > _parse_version("1.9.9")
    # Stale tag scenario: wildly higher tag is numerically "newer"
    assert _parse_version("10.3")  > _parse_version("1.0.0")

    print("       OK — _parse_version comparisons correct")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _run(test_sound_manager_loads_all_sounds)
    _run(test_sound_play_methods_do_not_raise)
    _run(test_volume_clamps_correctly)
    _run(test_mute_sets_effective_volume_to_zero)
    _run(test_parse_version_formats)

    print()
    print("=" * 50)
    print(f"Results: {len(_PASSED)} passed, {len(_FAILED)} failed")
    if _FAILED:
        print("Failed tests:")
        for name, msg in _FAILED:
            print(f"  - {name}: {msg}")
    sys.exit(1 if _FAILED else 0)
