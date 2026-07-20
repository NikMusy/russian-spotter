"""Что происходит на трассе впереди: авария, вставшая машина, круговой.

Это то, чем споттер в iRacing полезнее всего: предупредить о стоящей
машине за поворотом, пока ты в неё не приехал.
"""

from __future__ import annotations

from ..state import GameState
from ..udp.packets import DriverStatus, PitStatus
from .base import Cooldown, Say

# Смотрим вперёд по трассе, метры.
LOOK_AHEAD = 400.0
# Машина медленнее этого на трассе - авария или поломка.
STOPPED_KMH = 35
# Заметно медленнее нас, но едет - просто медленный.
SLOW_GAP_KMH = 60
# Ближе этого предупреждаем срочно.
CLOSE = 150.0
MIN_SPEED = 60


def _gap_along(rival_dist: float, my_dist: float, track_len: float) -> float:
    """Метры по трассе вперёд. Круг замкнут - разворачиваем через половину."""
    gap = rival_dist - my_dist
    if track_len > 0:
        if gap > track_len / 2:
            gap -= track_len
        elif gap < -track_len / 2:
            gap += track_len
    return gap


class IncidentRule:
    def __init__(self) -> None:
        self.cd = Cooldown()

    def update(self, state: GameState, say: Say) -> None:
        me = state.me
        if me is None or not state.on_track or state.in_pits:
            return
        if state.speed_kmh < MIN_SPEED or not state.car_speeds:
            return
        track_len = state.session.track_length if state.session else 0

        stopped_at = None
        slow_at = None

        for i, rival in enumerate(state.laps):
            if i == state.player_index or i >= len(state.car_speeds):
                continue
            if rival.driver_status == DriverStatus.IN_GARAGE:
                continue
            if rival.pit_status != PitStatus.NONE:
                continue

            gap = _gap_along(rival.lap_distance, me.lap_distance, track_len)
            if not (0 < gap < LOOK_AHEAD):
                continue

            speed = state.car_speeds[i]
            if speed < STOPPED_KMH:
                if stopped_at is None or gap < stopped_at:
                    stopped_at = gap
            elif state.speed_kmh - speed > SLOW_GAP_KMH:
                if slow_at is None or gap < slow_at:
                    slow_at = gap

        # Вставшая машина важнее просто медленной.
        if stopped_at is not None:
            if self.cd.ready("incident", 20):
                say("incident_ahead")
            return

        if slow_at is not None and slow_at < CLOSE:
            if self.cd.ready("slow_ahead", 25):
                say("slow_car_ahead")


class LappedCarRule:
    """Круговой впереди - его надо обойти, а не бодаться."""

    def __init__(self) -> None:
        self.cd = Cooldown()

    def update(self, state: GameState, say: Say) -> None:
        me = state.me
        if me is None or not state.in_race or not state.on_track:
            return
        if state.in_pits or state.speed_kmh < MIN_SPEED:
            return
        track_len = state.session.track_length if state.session else 0

        for i, rival in enumerate(state.laps):
            if i == state.player_index:
                continue
            if rival.driver_status == DriverStatus.IN_GARAGE:
                continue
            if rival.pit_status != PitStatus.NONE:
                continue
            # Круговой: отстал минимум на круг.
            if me.current_lap - rival.current_lap < 1:
                continue

            gap = _gap_along(rival.lap_distance, me.lap_distance, track_len)
            if 0 < gap < 120:
                if self.cd.ready("lapped", 20):
                    say("lapped_car_ahead")
                return
