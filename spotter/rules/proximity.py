"""Споттер: кто едет рядом.

Мировые координаты соперников переводим в систему координат игрока через
векторы m_worldForwardDir и m_worldRightDir из Motion-пакета. Они уже
нормализованы игрой, поэтому скалярное произведение сразу даёт метры:
вдоль машины и поперёк.
"""

from __future__ import annotations

import math
import random
import time

from ..state import GameState
from ..udp.packets import DriverStatus, PitStatus
from .base import Say


def _sane(value: float) -> bool:
    """Координата вменяемая? Битый кадр приносит 1e200 и inf."""
    return math.isfinite(value) and abs(value) < SANE_COORD

# Габариты болида, метры.
CAR_LENGTH = 5.6
CAR_WIDTH = 2.0

# Перекрытие вдоль машины: если |вдоль| меньше - машины бок о бок.
OVERLAP_ENTER = CAR_LENGTH * 1.05    # ~5.9 м
OVERLAP_EXIT = CAR_LENGTH * 1.40     # ~7.8 м, шире - чтобы не дребезжало

# Поперёк: ближе MIN - это та же машина/наложение, дальше MAX - другой ряд.
# 9 метров, как было раньше, - это уже противоположный край трассы:
# споттер орал про машины, которых рядом нет. Реально бок о бок - это 2-6 м.
LATERAL_MIN = CAR_WIDTH * 0.62       # ~1.24 м
LATERAL_MAX_ENTER = 6.0
LATERAL_MAX_EXIT = 7.5

# Общее расстояние до соперника: отсекает диагональ, когда он и вбок далеко,
# и вперёд далеко, но по каждой оси вроде бы проходит. 5 м вбок плюс 5 м
# вперёд - это 7.1 м по прямой, никакой не "бок о бок".
NEAR_RADIUS = 6.5

# Дальше этого даже не считаем проекции.
SCAN_RADIUS = 25.0
# Координаты больше этого - мусор из порванного кадра.
SANE_COORD = 1e6

# Ниже этой скорости споттер молчит (пит-лейн, гараж, старт).
MIN_SPEED_KMH = 45

# Сколько держать "рядом" после пропадания, прежде чем сказать "чисто".
# С запасом: на битом кадре соперник пропадает на мгновение, и без задержки
# споттер тараторил бы "чисто - справа - чисто".
CLEAR_DELAY = 0.7
# Как часто напоминать, что соперник всё ещё рядом. В плотном трафике это
# главный источник болтовни, поэтому редко.
STILL_THERE_EVERY = 6.0
# Минимум времени между сменами стороны - защита от трепыхания.
MIN_CALL_GAP = 0.45

CLEAR = "clear"
LEFT = "left"
RIGHT = "right"
BOTH = "both"


class ProximityRule:
    def __init__(self) -> None:
        self.state = CLEAR
        self._pending_clear_at: float | None = None
        self._last_call_at = 0.0
        self._side_since = 0.0
        self._last_still_at = 0.0
        self._announced = False

    def update(self, state: GameState, say: Say) -> None:
        raw = self._detect(state)
        now = time.monotonic()

        if raw == CLEAR:
            # Не тараторим "чисто" сразу - соперник мог мигнуть на кочке.
            if self.state != CLEAR:
                if self._pending_clear_at is None:
                    self._pending_clear_at = now
                elif now - self._pending_clear_at >= CLEAR_DELAY:
                    if self._announced:
                        say(random.choice(("clear", "clear_2")))
                    self._reset()
            return

        self._pending_clear_at = None

        if raw != self.state:
            if now - self._last_call_at < MIN_CALL_GAP:
                return
            self._call(raw, say)
            self.state = raw
            self._last_call_at = now
            self._side_since = now
            self._last_still_at = now
            self._announced = True
            return

        # Сторона та же - напоминаем, что он никуда не делся.
        if now - self._last_still_at >= STILL_THERE_EVERY:
            say("still_there")
            self._last_still_at = now

    def _call(self, side: str, say: Say) -> None:
        if side == BOTH:
            say("three_wide")
        elif side == LEFT:
            say(random.choice(("car_left", "car_left_2")))
        elif side == RIGHT:
            say(random.choice(("car_right", "car_right_2")))

    def _reset(self) -> None:
        self.state = CLEAR
        self._pending_clear_at = None
        self._announced = False

    # ------------------------------------------------------------------

    def _detect(self, state: GameState) -> str:
        me_motion = state.my_motion
        me_lap = state.me
        if me_motion is None or me_lap is None:
            return CLEAR
        if state.speed_kmh < MIN_SPEED_KMH:
            return CLEAR
        if me_lap.pit_status != PitStatus.NONE:
            return CLEAR

        # Свои координаты тоже могут прийти битыми - тогда не считаем ничего.
        if not _sane(me_motion.x) or not _sane(me_motion.z):
            return CLEAR

        # Пороги шире, пока кто-то уже рядом - гистерезис.
        engaged = self.state != CLEAR
        overlap = OVERLAP_EXIT if engaged else OVERLAP_ENTER
        lat_max = LATERAL_MAX_EXIT if engaged else LATERAL_MAX_ENTER
        radius = NEAR_RADIUS * (1.25 if engaged else 1.0)

        left = right = False
        for i, other in enumerate(state.motion):
            if i == state.player_index:
                continue
            if i >= len(state.laps):
                continue
            rival = state.laps[i]
            if rival.driver_status == DriverStatus.IN_GARAGE:
                continue
            if rival.result_status in (0, 1):  # invalid / inactive
                continue
            if rival.pit_status != PitStatus.NONE:
                continue
            # Мусор в координатах соперника: без этой проверки вычитание
            # даёт 1e200, а возведение в квадрат ниже - OverflowError.
            if not _sane(other.x) or not _sane(other.z):
                continue

            dx = other.x - me_motion.x
            dz = other.z - me_motion.z

            # Быстрый отсев, чтобы не считать проекции для всего поля.
            gap_sq = dx * dx + dz * dz
            if gap_sq > SCAN_RADIUS * SCAN_RADIUS:
                continue
            # И сразу отсекаем диагональ: далеко и вбок, и вперёд.
            if gap_sq > radius * radius:
                continue

            longitudinal = dx * me_motion.fwd_x + dz * me_motion.fwd_z
            lateral = dx * me_motion.right_x + dz * me_motion.right_z

            if abs(longitudinal) > overlap:
                continue
            dist = abs(lateral)
            if dist < LATERAL_MIN or dist > lat_max:
                continue

            if lateral < 0:
                left = True
            else:
                right = True
            if left and right:
                break

        if left and right:
            return BOTH
        if left:
            return LEFT
        if right:
            return RIGHT
        return CLEAR
