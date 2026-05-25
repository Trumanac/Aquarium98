"""
sound_manager.py — Thin wrapper around pygame.mixer for Aquarium 98 SFX.

If pygame.mixer is unavailable, or any audio file is missing, every method
silently becomes a no-op so the game always runs even without audio.

Sound files expected under assets/audio/:
  CoinChest.mp3         — multi-coin reward (treasure chest / big haul)
  SingleCoin.mp3        — single-coin reward (bubble pop earn)
  Achievement.wav       — achievement unlocked fanfare
  ChestCreak.wav        — chest lid creak when the chest opens
  BubblePop_1.mp3       — bubble pop (randomised, one of three)
  BubblePop_2.wav
  BubblePop_3.wav
  Water Splash_1.mp3    — ambient water splash (sparse, randomised)
  Water Splash_2.mp3
  Water Splash_3.mp3

Usage::
    snd = SoundManager()           # call after pygame.init()
    snd.set_volume(0.7)            # 0.0 – 1.0  (default 0.7)
    snd.set_muted(True)            # silence everything
    snd.play_coin_chest()          # treasure chest opened
    snd.play_single_coin()         # one coin earned
    snd.play_bubble_pop()          # bubble popped (random variant)
    snd.play_achievement()         # achievement unlocked
    snd.play_chest_creak()         # chest lid opening creak
    snd.update()                   # call once per frame — fires ambient splashes
"""
from __future__ import annotations

import random
import time
from pathlib import Path

import pygame

_AUDIO_DIR = Path(__file__).resolve().parent.parent / "assets" / "audio"

# Ambient water splashes play every 15–60 minutes at random (gentle reminder).
_SPLASH_MIN = 900.0
_SPLASH_MAX = 3600.0


def _load(path: Path) -> pygame.mixer.Sound | None:
    """Load a sound file, returning None on any error."""
    try:
        return pygame.mixer.Sound(str(path))
    except Exception:  # noqa: BLE001
        return None


class SoundManager:
    """Load and play game SFX.  All methods are safe to call even when
    the mixer failed to initialise."""

    def __init__(self) -> None:
        self._ok             = False
        self._volume         = 0.7    # 0.0 – 1.0
        self._muted          = False
        self._coin_chest:    pygame.mixer.Sound | None = None
        self._single_coin:   pygame.mixer.Sound | None = None
        self._achievement:   pygame.mixer.Sound | None = None
        self._chest_creak:   pygame.mixer.Sound | None = None
        self._bubble_pops:   list[pygame.mixer.Sound]  = []
        self._splashes:      list[pygame.mixer.Sound]  = []
        self._all_sounds:    list[pygame.mixer.Sound]  = []  # every loaded sound
        self._next_splash    = 0.0
        self._init()

    # ------------------------------------------------------------------
    def _init(self) -> None:
        # Initialize mixer if not already done (handles dev mode where only
        # pygame.display.init() was called — pygame.get_init() stays False).
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.pre_init(44100, -16, 2, 512)
                pygame.mixer.init()
            except Exception:  # noqa: BLE001
                return  # no audio device — stay silent

        self._coin_chest  = _load(_AUDIO_DIR / "CoinChest.mp3")
        self._single_coin = _load(_AUDIO_DIR / "SingleCoin.mp3")
        self._achievement = _load(_AUDIO_DIR / "Achievement.wav")
        self._chest_creak = _load(_AUDIO_DIR / "ChestCreak.wav")

        for name in ("BubblePop_1.mp3", "BubblePop_2.wav", "BubblePop_3.wav"):
            s = _load(_AUDIO_DIR / name)
            if s is not None:
                self._bubble_pops.append(s)

        for i in range(1, 4):
            s = _load(_AUDIO_DIR / f"Water Splash_{i}.mp3")
            if s is not None:
                self._splashes.append(s)

        # Build master list so _apply_volume() touches every sound at once
        self._all_sounds = [
            s for s in (
                self._coin_chest, self._single_coin, self._achievement,
                self._chest_creak, *self._bubble_pops, *self._splashes,
            ) if s is not None
        ]

        self._ok = True
        self._apply_volume()
        self._schedule_next_splash()

    # ------------------------------------------------------------------
    # Volume / mute control
    # ------------------------------------------------------------------

    def set_volume(self, volume: float) -> None:
        """Set master volume (0.0 – 1.0).  Applied immediately to all sounds."""
        volume = max(0.0, min(1.0, float(volume)))
        if volume == self._volume:
            return
        self._volume = volume
        self._apply_volume()

    def set_muted(self, muted: bool) -> None:
        """Mute or unmute all sounds without changing the stored volume."""
        muted = bool(muted)
        if muted == self._muted:
            return
        self._muted = muted
        self._apply_volume()

    def _apply_volume(self) -> None:
        """Push current effective volume to every loaded Sound object."""
        effective = 0.0 if self._muted else self._volume
        for s in self._all_sounds:
            s.set_volume(effective)

    def _schedule_next_splash(self) -> None:
        self._next_splash = time.monotonic() + random.uniform(_SPLASH_MIN, _SPLASH_MAX)

    # ------------------------------------------------------------------
    # Public playback API
    # ------------------------------------------------------------------

    def play_coin_chest(self) -> None:
        """Play the treasure-chest / multi-coin reward sound."""
        if self._ok and self._coin_chest:
            self._coin_chest.play()

    def play_single_coin(self) -> None:
        """Play the single-coin earned sound (bubble pop reward)."""
        if self._ok and self._single_coin:
            self._single_coin.play()

    def play_bubble_pop(self) -> None:
        """Play a random bubble-pop variant."""
        if self._ok and self._bubble_pops:
            random.choice(self._bubble_pops).play()

    def play_achievement(self) -> None:
        """Play the achievement-unlocked fanfare."""
        if self._ok and self._achievement:
            self._achievement.play()

    def play_chest_creak(self) -> None:
        """Play the chest-lid creak when the treasure chest opens."""
        if self._ok and self._chest_creak:
            self._chest_creak.play()

    def update(self) -> None:
        """Call once per frame.  Fires ambient water splashes on a random timer."""
        if not self._ok or not self._splashes:
            return
        if time.monotonic() >= self._next_splash:
            random.choice(self._splashes).play()
            self._schedule_next_splash()
