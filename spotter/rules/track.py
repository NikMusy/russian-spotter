"""Объявление трассы и типа сессии при заходе.

Играет один раз на сессию: "сегодня едем, Ле-Ман, гонка".
"""

from __future__ import annotations

from ..sims import tracks
from ..state import GameState
from ..udp.packets import SessionType
from .base import Say

SESSION_PHRASE = {
    SessionType.P1: "session_practice",
    SessionType.P2: "session_practice",
    SessionType.P3: "session_practice",
    SessionType.SHORT_P: "session_practice",
    SessionType.Q1: "session_qualifying",
    SessionType.Q2: "session_qualifying",
    SessionType.Q3: "session_qualifying",
    SessionType.SHORT_Q: "session_qualifying",
    SessionType.OSQ: "session_hotlap",
    SessionType.RACE: "session_race",
    SessionType.RACE_2: "session_race",
    SessionType.RACE_3: "session_race",
    SessionType.TIME_TRIAL: "session_hotlap",
}

PRACTICE = (SessionType.P1, SessionType.P2, SessionType.P3,
            SessionType.SHORT_P)
QUALI = (SessionType.Q1, SessionType.Q2, SessionType.Q3, SessionType.SHORT_Q,
         SessionType.OSQ)


class TrackAnnounceRule:
    """Один раз на сессию: где мы и что едем."""

    def __init__(self) -> None:
        self._announced_for: tuple | None = None

    def update(self, state: GameState, say: Say) -> None:
        s = state.session
        if s is None:
            return

        # Ключ сессии: сменилась трасса или тип - объявляем заново.
        key = (s.track_id, state.track_name, s.session_type)
        if key == self._announced_for:
            return
        # Пока не знаем тип сессии, молчим: иначе поймаем мусор на загрузке.
        if s.session_type == SessionType.UNKNOWN:
            return
        self._announced_for = key

        if state.track_name:
            track = tracks.by_name(state.track_name)
        else:
            track = tracks.by_f1_id(s.track_id)

        session = SESSION_PHRASE.get(s.session_type, "session_race")
        say("welcome_to", track, session)

        if s.session_type in QUALI:
            say("quali_push")
        elif s.session_type in PRACTICE:
            say("practice_relax")
        else:
            say("good_luck")
