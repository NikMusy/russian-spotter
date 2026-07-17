"""Трафик классов в эндурансе.

Симы отдают класс строкой ("Hyper", "GT3", "LMP2"), поэтому опознаём по
куску названия. Если классов в сессии нет или он один - правило молчит.

Расстояние до соперника считаем ВДОЛЬ ТРАССЫ, а не по прямой. Раньше тут
стояла проверка "не дальше 12 метров вбок", и на дуге поворота она резала
всё подряд: машина в сорока метрах позади по трассе на затяжном повороте
уходит вбок гораздо дальше, и правило молчало почти всю гонку.
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

# Метры по трассе. Сзади - когда уже дышит в спину, впереди - заранее,
# чтобы успеть спланировать обгон.
BEHIND_NEAR = 70.0
AHEAD_NEAR = 90.0
# Вплотную не считаем: там уже работает обычный споттер со своим "слева".
TOO_CLOSE = 4.0
EVERY = 12.0
MIN_SPEED = 40


def classify(name: str) -> tuple[str, int]:
    low = (name or "").strip().lower()
    for keys, phrase, speed in CLASS_MATCH:
        for k in keys:
            if k in low:
                return phrase, speed
    return "", 0


def _gap_along_track(rival_dist: float, my_dist: float,
                     track_len: float) -> float:
    """Метры по трассе: плюс - соперник впереди, минус - сзади.

    Круг замкнут, поэтому машина в десяти метрах впереди может числиться
    почти на круг позади - разворачиваем через половину длины трассы.
    """
    gap = rival_dist - my_dist
    if track_len > 0:
        if gap > track_len / 2:
            gap -= track_len
        elif gap < -track_len / 2:
            gap += track_len
    return gap


class ClassTrafficRule:
    def __init__(self) -> None:
        self.cd = Cooldown()

    def update(self, state: GameState, say: Say) -> None:
        if not state.car_classes or not state.on_track or state.in_pits:
            return
        # В квалификации LMU соперники - призраки, трафика нет.
        if state.cars_are_ghosts:
            return
        me = state.me
        if me is None or state.speed_kmh < MIN_SPEED:
            return

        my_name, my_speed = classify(state.my_class)
        if not my_name:
            return

        track_len = state.session.track_length if state.session else 0

        faster_behind = None
        slower_ahead = None

        for i, rival in enumerate(state.laps):
            if i == state.player_index or i >= len(state.car_classes):
                continue
            if rival.driver_status == DriverStatus.IN_GARAGE:
                continue
            if rival.pit_status != PitStatus.NONE:
                continue

            name, speed = classify(state.car_classes[i])
            if not name or speed == my_speed:
                continue

            gap = _gap_along_track(rival.lap_distance, me.lap_distance,
                                   track_len)

            if speed > my_speed and -BEHIND_NEAR < gap < -TOO_CLOSE:
                # Ближайший из догоняющих - он и важен.
                if faster_behind is None or gap > faster_behind[0]:
                    faster_behind = (gap, name)
            elif speed < my_speed and TOO_CLOSE < gap < AHEAD_NEAR:
                if slower_ahead is None or gap < slower_ahead[0]:
                    slower_ahead = (gap, name)

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
