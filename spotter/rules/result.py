"""Итог сессии голосом: с какого места стартовал, каким приехал."""

from __future__ import annotations

from ..audio import numbers
from ..history import Entry
from ..udp.packets import SessionType
from .base import Say

QUALI = (SessionType.Q1, SessionType.Q2, SessionType.Q3, SessionType.SHORT_Q,
         SessionType.OSQ)
PRACTICE = (SessionType.P1, SessionType.P2, SessionType.P3,
            SessionType.SHORT_P)

ORDINAL_MAX = 20


def _as(position: int) -> list[str]:
    """Творительный падеж: 3 -> [третьим]."""
    if 1 <= position <= ORDINAL_MAX:
        return [f"as_{position}"]
    return []


def announce(entry: Entry, say: Say) -> None:
    """Проговаривает результат заезда.

    Зовётся, когда сессия закрылась, - оттуда же, откуда запись уходит в
    статистику.
    """
    place = _as(entry.finish)
    if not place:
        return

    if entry.session_type in QUALI:
        say("quali_result", *place)
        return

    if entry.session_type in PRACTICE:
        say("practice_over")
        return

    if not entry.is_race:
        return

    say("race_result", *place)

    if not entry.grid:
        return
    start = _as(entry.grid)
    if start:
        say("started_from", *start)

    moved = entry.gained
    if moved > 0:
        say("gained_places", *numbers.integer(moved))
    elif moved < 0:
        say("lost_places", *numbers.integer(-moved))
    else:
        say("held_position")
