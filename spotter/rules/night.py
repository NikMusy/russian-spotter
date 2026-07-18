"""Ночь в эндурансе: включи фары, темнеет, светает."""

from __future__ import annotations

from ..state import GameState
from .base import Cooldown, Say

# Время суток в секундах с полуночи.
DUSK = 19 * 3600        # темнеет
NIGHT = 20 * 3600       # без фар уже не видно
DAWN = 6 * 3600         # светает
DAY = 7 * 3600          # фары можно гасить


class NightRule:
    """Работает там, где сим отдаёт время суток (LMU)."""

    def __init__(self) -> None:
        self.cd = Cooldown()
        self.told_dusk = False
        self.told_dawn = False

    def update(self, state: GameState, say: Say) -> None:
        tod = state.time_of_day
        if tod < 0 or not state.on_track or state.in_pits:
            return

        dark = tod >= NIGHT or tod < DAWN

        # Стемнело, а фары не горят - напоминаем, пока не включит.
        if dark and not state.headlights_on:
            if self.cd.ready("lights", 20):
                say("headlights_on")
            return

        # Предупреждаем на закате, что скоро понадобятся фары.
        if DUSK <= tod < NIGHT and not self.told_dusk:
            self.told_dusk = True
            say("night_falling")
        elif DAWN <= tod < DAY and not self.told_dawn:
            self.told_dawn = True
            say("sunrise")
