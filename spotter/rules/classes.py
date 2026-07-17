"""Трафик классов в эндурансе.

Симы отдают класс строкой ("Hypercar", "LMP2", "GTE"...), поэтому
опознаём по куску названия. Если классов в сессии нет или он один -
правило молчит.
"""

from __future__ import annotations

from ..state import GameState
from ..udp.packets import DriverStatus, PitStatus
from .base import Cooldown, Say

# Класс -> (id фразы, насколько быстрый). Чем больше число, тем быстрее.
# Ищем по куску: LMU пишет класс коротко ("Hyper", "GT3"), другие симы -
# полностью ("Hypercar", "LMGT3"). Проверено на живой LMU: там именно
# "Hyper", так что искать "hypercar" целиком было бесполезно.
CLASS_MATCH: list[tuple[tuple[str, ...], str, int]] = [
    (("hypercar", "hyper", "lmh", "lmdh", "gtp"), "hypercar", 4),
    (("lmp2", "p2"), "lmp2", 3),
    (("lmp3", "p3"), "lmp3", 2),
    (("lmgte", "gte"), "gte", 1),
    (("lmgt3", "gt3"), "gt3", 1),
]

# Насколько близко сзади, чтобы предупредить, метры.
BEHIND_NEAR = 45.0
# Впереди - дальше, обгон готовится заранее.
AHEAD_NEAR = 60.0
# Не тараторить.
EVERY = 12.0


def classify(name: str) -> tuple[str, int]:
    low = (name or "").strip().lower()
    for keys, phrase, speed in CLASS_MATCH:
        for k in keys:
            if k in low:
                return phrase, speed
    return "", 0


class ClassTrafficRule:
    def __init__(self) -> None:
        self.cd = Cooldown()

    def update(self, state: GameState, say: Say) -> None:
        if not state.car_classes or not state.on_track or state.in_pits:
            return
        me_motion = state.my_motion
        me_lap = state.me
        if me_motion is None or me_lap is None:
            return
        if state.speed_kmh < 40:
            return

        my_name, my_speed = classify(state.my_class)
        if not my_name:
            return

        faster_behind = None
        slower_ahead = None

        for i, motion in enumerate(state.motion):
            if i == state.player_index or i >= len(state.laps):
                continue
            if i >= len(state.car_classes):
                continue
            rival = state.laps[i]
            if rival.driver_status == DriverStatus.IN_GARAGE:
                continue
            if rival.pit_status != PitStatus.NONE:
                continue

            name, speed = classify(state.car_classes[i])
            if not name or speed == my_speed:
                continue

            dx = motion.x - me_motion.x
            dz = motion.z - me_motion.z
            if dx * dx + dz * dz > 6400:      # дальше 80 м не интересует
                continue

            lon = dx * me_motion.fwd_x + dz * me_motion.fwd_z
            lat = dx * me_motion.right_x + dz * me_motion.right_z
            if abs(lat) > 12:                 # соседний ряд, не наш трафик
                continue

            if speed > my_speed and -BEHIND_NEAR < lon < -3:
                # Быстрее и догоняет - самое важное.
                if faster_behind is None or lon > faster_behind[0]:
                    faster_behind = (lon, name)
            elif speed < my_speed and 3 < lon < AHEAD_NEAR:
                if slower_ahead is None or lon < slower_ahead[0]:
                    slower_ahead = (lon, name)

        if faster_behind is not None:
            _, name = faster_behind
            if self.cd.ready(f"behind_{name}", EVERY):
                if name == "hypercar":
                    say("hypercar_behind")
                elif name == "lmp2":
                    say("lmp2_behind")
                else:
                    say("faster_class_behind")
            return

        if slower_ahead is not None:
            _, name = slower_ahead
            if self.cd.ready(f"ahead_{name}", EVERY):
                if name in ("gt3", "gte"):
                    say("gt3_ahead")
                else:
                    say("traffic_ahead")


class ClassPositionRule:
    """Лидерство в своём классе - в эндурансе это и есть результат."""

    def __init__(self) -> None:
        self.was_leader = False
        self.cd = Cooldown()

    def update(self, state: GameState, say: Say) -> None:
        if not state.car_classes or not state.in_race or not state.on_track:
            return
        me = state.me
        if me is None or me.current_lap < 2:
            return

        my_name, _ = classify(state.my_class)
        if not my_name:
            return

        ahead = 0
        for i, rival in enumerate(state.laps):
            if i == state.player_index or i >= len(state.car_classes):
                continue
            name, _ = classify(state.car_classes[i])
            if name != my_name:
                continue
            if 0 < rival.position < me.position:
                ahead += 1

        leader = ahead == 0
        if leader and not self.was_leader and self.cd.ready("cls_lead", 30):
            say("class_leader")
        self.was_leader = leader
