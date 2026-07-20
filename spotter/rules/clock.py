"""Время до конца сессии.

В WEC и ELMS гонка идёт по часам, а не по кругам, поэтому "осталось
двадцать минут" - основная точка отсчёта для стратегии.
"""

from __future__ import annotations

from ..audio import numbers
from ..state import GameState
from .base import Say

# На каких отметках говорить, минуты.
MARKS = (60, 30, 20, 15, 10, 5, 2)


class SessionClockRule:
    def __init__(self) -> None:
        self.said: set[int] = set()
        self._last_left = -1.0

    def update(self, state: GameState, say: Say) -> None:
        s = state.session
        if s is None or not state.on_track:
            return
        left = s.session_time_left
        if left <= 0:
            return

        # Время пошло вверх - новая сессия, отметки заново.
        if self._last_left >= 0 and left > self._last_left + 60:
            self.said.clear()
        self._last_left = left

        minutes = left / 60.0
        for mark in MARKS:
            if mark in self.said:
                continue
            # Отметку берём, когда только что её прошли.
            if mark - 0.5 <= minutes <= mark:
                self.said.add(mark)
                if mark == 60:
                    say("hour_to_go")
                else:
                    say("time_left", *numbers.with_word(mark, "minutes"))
                return
