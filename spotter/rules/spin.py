"""Разворот (спин). Когда машину закрутило - соберись, ты не Райкконен."""

from __future__ import annotations

import math
import time

from ..state import GameState
from ..udp.packets import PitStatus
from .base import Say

# Волчок крутит быстро. На обычном вираже даже в шпильке рыскание редко
# выше ~1.5 рад/с; 3.5 рад/с (200 град/сек) - это уже потеря машины.
SPIN_RATE = 3.5
# На месте в боксах машину тоже можно крутить - это не спин.
MIN_SPEED = 25
# Один разворот - одна реакция, не тараторить на каждом кадре вращения.
QUIET_AFTER = 6.0


def _yaw_delta(a: float, b: float) -> float:
    """Кратчайшая разница углов, с учётом перехода через pi."""
    d = a - b
    while d > math.pi:
        d -= 2 * math.pi
    while d < -math.pi:
        d += 2 * math.pi
    return d


class SpinRule:
    def __init__(self) -> None:
        self._prev_yaw: float | None = None
        self._prev_t = 0.0
        self._quiet_until = 0.0

    def update(self, state: GameState, say: Say) -> None:
        me = state.my_motion
        lap = state.me
        now = time.monotonic()

        if (me is None or lap is None or not state.on_track
                or lap.pit_status != PitStatus.NONE):
            self._prev_yaw = None
            return

        prev_yaw, prev_t = self._prev_yaw, self._prev_t
        self._prev_yaw, self._prev_t = me.yaw, now
        if prev_yaw is None:
            return

        dt = now - prev_t
        if dt <= 0 or dt > 0.5:      # пропуск кадров - скорость не считаем
            return

        rate = abs(_yaw_delta(me.yaw, prev_yaw)) / dt
        if state.speed_kmh >= MIN_SPEED and rate >= SPIN_RATE:
            if now >= self._quiet_until:
                self._quiet_until = now + QUIET_AFTER
                # "соберись" - в мемах у него "ты не Райкконен, успокойся".
                say("focus")
