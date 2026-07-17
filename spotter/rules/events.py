"""Правила на событийных пакетах: флаги, сейфти-кар, штрафы, DRS."""

from __future__ import annotations

from ..state import GameState
from ..udp.packets import Flag, SafetyCar
from .base import Cooldown, Say

# Коды событий F1 25.
E_SESSION_START = "SSTA"
E_SESSION_END = "SEND"
E_FASTEST_LAP = "FTLP"
E_DRS_ENABLED = "DRSE"
E_DRS_DISABLED = "DRSD"
E_CHEQUERED = "CHQF"
E_PENALTY = "PENA"
E_LIGHTS_OUT = "LGOT"
E_RED_FLAG = "RDFL"
E_OVERTAKE = "OVTK"
E_SAFETY_CAR = "SCAR"
E_COLLISION = "COLL"
E_RACE_WINNER = "RCWN"


class EventRule:
    """Реагирует на пакеты событий (packet id 3)."""

    def __init__(self, penalties: "PenaltyRule | None" = None) -> None:
        self.cd = Cooldown()
        # Тип штрафа приходит только в событии, поэтому передаём его туда,
        # где живёт вся логика штрафов.
        self.penalties = penalties

    def on_event(self, code: str, state: GameState, say: Say,
                 raw: bytes = b"") -> None:
        if code == E_LIGHTS_OUT:
            say("green_green_green")
        elif code == E_RED_FLAG:
            say("flag_red")
        elif code == E_CHEQUERED:
            say("flag_chequered")
        elif code == E_FASTEST_LAP:
            if self.cd.ready("ftlp", 20):
                say("fastest_lap")
        elif code == E_DRS_ENABLED:
            if self.cd.ready("drse", 30):
                say("drs_enabled")
        elif code == E_DRS_DISABLED:
            if self.cd.ready("drsd", 30):
                say("drs_disabled")
        elif code == E_PENALTY:
            # Payload: m_penaltyType, m_infringementType, m_vehicleIdx, ...
            if self.penalties is not None and raw:
                self.penalties.on_penalty(raw[0], say)
            elif self.cd.ready("pena", 5):
                say("penalty_pending")
        elif code == E_COLLISION:
            if self.cd.ready("coll", 6):
                say("contact")
        elif code == E_SESSION_END:
            say("session_end")
        elif code == E_RACE_WINNER:
            say("good_race")

    def update(self, state: GameState, say: Say) -> None:
        return


class FlagRule:
    """Флаги из CarStatus (m_vehicleFiaFlags)."""

    def __init__(self) -> None:
        # None = ещё не видели ни одного кадра: первый нельзя принимать за
        # смену флага.
        self.last: int | None = None
        self.cd = Cooldown()

    def update(self, state: GameState, say: Say) -> None:
        if state.status is None or not state.on_track:
            return
        flag = state.status.fia_flag
        if self.last is None:
            self.last = flag
            return
        if flag == self.last:
            return
        prev, self.last = self.last, flag

        if flag == Flag.YELLOW:
            if self.cd.ready("yellow", 8):
                say("flag_yellow_sector")
        elif flag == Flag.BLUE:
            if self.cd.ready("blue", 12):
                say("flag_blue")
        elif flag == Flag.RED:
            say("flag_red")
        elif flag == Flag.GREEN and prev in (Flag.YELLOW, Flag.RED):
            if self.cd.ready("green", 8):
                say("flag_green")


class SafetyCarRule:
    def __init__(self) -> None:
        self.last: int | None = None

    def update(self, state: GameState, say: Say) -> None:
        if state.session is None:
            return
        sc = state.session.safety_car_status
        if self.last is None:
            # Первый кадр: просто запоминаем, иначе заезд под уже
            # висящей жёлтой объявлялся бы как новая.
            self.last = sc
            return
        if sc == self.last:
            return
        prev, self.last = self.last, sc

        # В эндурансе это не машина безопасности, а полная жёлтая по трассе.
        full_course_yellow = state.sim in ("lmu", "iracing", "ams2")

        if sc == SafetyCar.FULL:
            say("fcy" if full_course_yellow else "sc_deployed")
        elif sc == SafetyCar.VIRTUAL:
            say("vsc_deployed")
        elif sc == SafetyCar.NONE and prev in (SafetyCar.FULL, SafetyCar.VIRTUAL):
            say("fcy_end" if full_course_yellow else "race_restart")


# Типы штрафов из спецификации F1 (m_penaltyType в событии PENA).
PEN_DRIVE_THROUGH = 0
PEN_STOP_GO = 1
PEN_TIME_PENALTY = 4
PEN_WARNING = 6
PEN_DISQUALIFIED = 7
PEN_RETIRED = 9

# Что говорить на каждый тип.
PENALTY_PHRASE = {
    PEN_DRIVE_THROUGH: "penalty_drive_through",
    PEN_STOP_GO: "penalty_stop_go",
    PEN_TIME_PENALTY: "penalty_5s",
    PEN_WARNING: "warning_track_limits",
}


class PenaltyRule:
    """Штрафы и предупреждения.

    F1 присылает тип штрафа в событии, у LMU есть только счётчик - там
    отличить стоп-энд-гоу от проезда нельзя, поэтому говорим общее.
    """

    def __init__(self) -> None:
        self.warnings = -1
        self.penalties = -1
        self.unserved = -1
        self.cd = Cooldown()

    def on_penalty(self, penalty_type: int, say: Say) -> None:
        """Событие PENA из F1: тип штрафа известен точно."""
        phrase = PENALTY_PHRASE.get(penalty_type)
        if phrase and self.cd.ready(f"pen_{penalty_type}", 5):
            say(phrase)

    def update(self, state: GameState, say: Say) -> None:
        me = state.me
        if me is None:
            return

        # Границы трассы.
        if self.warnings < 0:
            self.warnings = me.corner_cutting_warnings
        elif me.corner_cutting_warnings > self.warnings:
            say("warning_track_limits")
        self.warnings = me.corner_cutting_warnings

        # Штрафы по счётчику: так их видно и в LMU, где событий нет.
        if self.penalties < 0:
            self.penalties = me.penalties
        elif me.penalties > self.penalties and self.cd.ready("pen_new", 6):
            say("penalty_pending")
        self.penalties = me.penalties

        # Неотбытые штрафы: напоминаем, пока висят.
        unserved = me.num_unserved_drive_through + me.num_unserved_stop_go
        if unserved > 0 and self.cd.ready("unserved", 45):
            if me.num_unserved_stop_go > 0:
                say("penalty_stop_go")
            else:
                say("penalty_drive_through")
            say("serve_penalty_now")
        elif self.unserved > 0 and unserved == 0:
            say("penalty_served")
        self.unserved = unserved
