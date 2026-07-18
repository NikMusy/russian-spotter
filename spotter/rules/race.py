"""Ход гонки: позиция, отрывы, круги."""

from __future__ import annotations

from ..audio import numbers
from ..state import GameState
from ..udp.packets import DriverStatus
from .base import Cooldown, Say

# Говорить отрыв не чаще этого, секунд.
GAP_EVERY = 45.0
# Отрыв больше этого не интересен - соперник вне досягаемости.
GAP_MAX = 25.0
# Зона DRS в F1: игра открывает крыло при отрыве меньше секунды.
DRS_GAP = 1.0
# Слипстрим в эндурансе. Ощутимо тащит примерно с двух корпусов (~10 м),
# сильно - когда ближе. На гоночной скорости это отрыв меньше ~0.7 сек;
# ближе 0.4 сек - уже плотный мешок, можно готовить обгон.
SLIPSTREAM_GAP = 0.7
SLIPSTREAM_CLOSE = 0.4

# У кого DRS, а у кого только слипстрим.
DRS_SIMS = ("f1", "ams2")


class PositionRule:
    def __init__(self) -> None:
        self.last: int | None = None
        self.cd = Cooldown()

    def update(self, state: GameState, say: Say) -> None:
        me = state.me
        if me is None or not state.in_race or not state.on_track:
            return
        if state.in_pits:
            return

        pos = me.position
        if pos <= 0:
            return
        if self.last is None:
            self.last = pos
            return
        if pos == self.last:
            return

        gained = pos < self.last
        prev, self.last = self.last, pos

        # На первом круге позиции скачут - молчим.
        if me.current_lap <= 1:
            return
        if not self.cd.ready("pos", 4):
            return

        say("position_gained" if gained else "position_lost")
        ordinal = numbers.ordinal(pos)
        if ordinal:
            say("you_are", *ordinal)


class LapRule:
    def __init__(self) -> None:
        self.last_lap = 0
        self.told_last_lap = False
        self.told_half = False
        self.best_ms: int | None = None

    def update(self, state: GameState, say: Say) -> None:
        me = state.me
        if me is None or not state.on_track:
            return

        lap = me.current_lap
        if lap == self.last_lap:
            return
        prev, self.last_lap = self.last_lap, lap
        if prev == 0:
            return

        # Круг закрыт - можно оценить прошлый.
        last_ms = me.last_lap_ms
        if last_ms > 0 and not me.lap_invalid:
            if self.best_ms is None or last_ms < self.best_ms:
                if self.best_ms is not None:
                    say("personal_best")
                self.best_ms = last_ms

        if not state.in_race:
            return

        total = state.total_laps
        if not total:
            return

        left = total - lap + 1
        if left == 1 and not self.told_last_lap:
            self.told_last_lap = True
            say("last_lap")
        elif 2 <= left <= 5:
            say("laps_remaining", *numbers.with_word(left, "laps"))
        elif not self.told_half and lap == total // 2 and total >= 10:
            self.told_half = True
            say("half_distance")


class GapRule:
    def __init__(self) -> None:
        self.cd = Cooldown()
        self.told_drs = False

    def update(self, state: GameState, say: Say) -> None:
        me = state.me
        if me is None or not state.in_race or not state.on_track:
            return
        if state.in_pits or me.current_lap < 2:
            return

        gap = me.delta_front_ms / 1000.0

        # Близость к машине впереди - новость посвежее, чем сам отрыв.
        # В F1 это зона DRS, в эндурансе - слипстрим.
        if state.sim in DRS_SIMS:
            if 0 < gap <= DRS_GAP:
                if not self.told_drs and self.cd.ready("drs", 20):
                    self.told_drs = True
                    say("in_drs_range")
                return
            self.told_drs = False
        else:
            if 0 < gap <= SLIPSTREAM_GAP:
                if not self.told_drs and self.cd.ready("slip", 15):
                    self.told_drs = True
                    say("in_slipstream_close" if gap <= SLIPSTREAM_CLOSE
                        else "in_slipstream")
                return
            self.told_drs = False

        if me.position == 1 or gap < 1.0 or gap > GAP_MAX:
            return
        if not self.cd.ready("gap", GAP_EVERY):
            return

        # gap_phrase молчит на отрыве меньше секунды - там слипстрим/DRS.
        say("gap_ahead", *numbers.gap_phrase(gap))
