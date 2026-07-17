"""Заготовки состояния для тестов.

Отдельным модулем, а не импортом из соседнего теста: тот при импорте
выполнился бы целиком и завершил процесс своим sys.exit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spotter.udp.packets import CarMotion, LapData, Telemetry


def motion_at(x: float, z: float) -> CarMotion:
    """Машина в точке (x, z), смотрит вдоль +Z, право - вдоль +X."""
    return CarMotion(x=x, y=0.0, z=z, fwd_x=0.0, fwd_z=1.0,
                     right_x=1.0, right_z=0.0, yaw=0.0)


def lap(pit: int = 0, status: int = 4, result: int = 2,
        position: int = 1, current_lap: int = 5) -> LapData:
    return LapData(
        last_lap_ms=0, current_lap_ms=0, delta_front_ms=0, delta_leader_ms=0,
        lap_distance=0.0, total_distance=0.0, safety_car_delta=0.0,
        position=position, current_lap=current_lap, pit_status=pit,
        num_pit_stops=0, sector=0, lap_invalid=0, penalties=0,
        total_warnings=0, corner_cutting_warnings=0, grid_position=1,
        driver_status=status, result_status=result, pit_lane_timer_active=0,
    )


def telemetry(speed: int) -> Telemetry:
    return Telemetry(speed=speed, throttle=1.0, steer=0.0, brake=0.0, gear=5,
                     rpm=10000, drs=0, brake_temp=(0,) * 4,
                     tyre_surface_temp=(90,) * 4, tyre_inner_temp=(90,) * 4,
                     engine_temp=90, tyre_pressure=(23.0,) * 4,
                     surface_type=(0,) * 4)
