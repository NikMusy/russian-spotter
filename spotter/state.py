"""Состояние гонки, собранное из UDP-пакетов.

Правила читают только отсюда и ничего не знают про байты.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .udp.packets import (
    CarDamage, CarMotion, CarStatus, Header, LapData, SessionInfo, Telemetry,
    DriverStatus, PitStatus, SessionType,
)


@dataclass
class GameState:
    connected: bool = False
    last_packet_at: float = 0.0
    # Какой сим нас кормит: правила иногда подбирают фразу под него.
    sim: str = "f1"

    header: Header | None = None
    session: SessionInfo | None = None
    motion: list[CarMotion] = field(default_factory=list)
    laps: list[LapData] = field(default_factory=list)
    telemetry: Telemetry | None = None
    status: CarStatus | None = None
    damage: CarDamage | None = None

    player_index: int = 0

    # Заполняет адаптер сима, а не UDP-пакеты.
    track_name: str = ""                       # как его называет сим
    car_classes: list[str] = field(default_factory=list)  # класс каждой машины

    @property
    def my_class(self) -> str:
        if 0 <= self.player_index < len(self.car_classes):
            return self.car_classes[self.player_index]
        return ""

    def update(self, header: Header, payload: object) -> None:
        self.header = header
        self.player_index = header.player_car_index
        self.last_packet_at = time.monotonic()
        self.connected = True

        if isinstance(payload, SessionInfo):
            self.session = payload
        elif isinstance(payload, Telemetry):
            self.telemetry = payload
        elif isinstance(payload, CarStatus):
            self.status = payload
        elif isinstance(payload, CarDamage):
            self.damage = payload
        elif isinstance(payload, list) and payload:
            if isinstance(payload[0], CarMotion):
                self.motion = payload
            elif isinstance(payload[0], LapData):
                self.laps = payload

    # ------------------------------------------------------------ игрок

    @property
    def me(self) -> LapData | None:
        if 0 <= self.player_index < len(self.laps):
            return self.laps[self.player_index]
        return None

    @property
    def my_motion(self) -> CarMotion | None:
        if 0 <= self.player_index < len(self.motion):
            return self.motion[self.player_index]
        return None

    @property
    def speed_kmh(self) -> int:
        return self.telemetry.speed if self.telemetry else 0

    @property
    def in_race(self) -> bool:
        return bool(self.session and self.session.session_type in (
            SessionType.RACE, SessionType.RACE_2, SessionType.RACE_3))

    @property
    def on_track(self) -> bool:
        me = self.me
        if me is None:
            return False
        return me.driver_status != DriverStatus.IN_GARAGE

    @property
    def in_pits(self) -> bool:
        me = self.me
        if me is None:
            return False
        return me.pit_status != PitStatus.NONE

    @property
    def total_laps(self) -> int:
        return self.session.total_laps if self.session else 0

    @property
    def laps_left(self) -> int:
        me = self.me
        if me is None or not self.total_laps:
            return 0
        return max(0, self.total_laps - me.current_lap)

    def is_stale(self, timeout: float = 3.0) -> bool:
        if not self.connected:
            return True
        return (time.monotonic() - self.last_packet_at) > timeout
