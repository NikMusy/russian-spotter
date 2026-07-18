"""Управление энергией гибрида (WEC гиперкары).

В WEC у гиперкаров энергия на стинт лимитирована (BoP): инженер постоянно
держит пилота в курсе, хватает ли виртуальной энергии до пита. Это самое
узнаваемое в радиопереговорах WEC, поэтому вынесено отдельно.

virtual_energy - доля 0..1 оставшейся энергии стинта. Сравниваем с тем,
сколько топлива осталось: если энергия кончается заметно раньше топлива -
надо экономить.
"""

from __future__ import annotations

from ..state import GameState
from .base import Cooldown, Say

# Пороги доли энергии.
LOW = 0.20
CRITICAL = 0.08


class EnergyRule:
    def __init__(self) -> None:
        self.cd = Cooldown()
        self.warned: set[str] = set()
        self.was_in_pits = False

    def update(self, state: GameState, say: Say) -> None:
        # На пите энергию восполняют - начинаем стинт заново.
        if self.was_in_pits and not state.in_pits:
            self.warned.clear()
        self.was_in_pits = state.in_pits

        ve = state.virtual_energy
        # -1 = сим не отдаёт энергию (не гиперкар, не WEC, не LMU).
        if ve < 0 or not state.on_track or state.in_pits:
            return
        if not state.in_race:
            return

        if ve <= CRITICAL:
            if "crit" not in self.warned:
                self.warned.add("crit")
                say("energy_critical")
        elif ve <= LOW:
            if "low" not in self.warned:
                self.warned.add("low")
                say("energy_low")
                say("energy_save")
