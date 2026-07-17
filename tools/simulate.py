"""Шлёт синтетические пакеты F1 25 на порт споттера.

Нужен, чтобы проверить споттера без игры: соперник проезжает слева,
потом справа, потом оба сразу; погода портится, крыло ломается.

Запуск: сначала spotter.exe, потом python tools\\simulate.py
"""

from __future__ import annotations

import math
import socket
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spotter.udp import packets as pk

HOST = "127.0.0.1"
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 20777

FRAME = 0


def header(packet_id: int) -> bytes:
    global FRAME
    FRAME += 1
    return pk.HEADER_FMT.pack(
        2025,      # packet format
        25,        # game year
        1, 0,      # major, minor
        1,         # packet version
        packet_id,
        1234567890123456789,  # session uid
        FRAME / 60.0,         # session time
        FRAME, FRAME,
        0,         # player car index
        255,       # secondary
    )


def motion(rivals: list[tuple[float, float]]) -> bytes:
    """Игрок в нуле, смотрит вдоль +Z. rivals: (поперёк, вдоль)."""
    body = b""
    cars = [(0.0, 0.0)] + rivals
    for i in range(pk.MAX_CARS):
        x, z = cars[i] if i < len(cars) else (5000.0, 5000.0)
        body += pk.MOTION_FMT.pack(
            x, 0.0, z,          # позиция
            0.0, 0.0, 0.0,      # скорость
            0, 0, 32767,        # forward = +Z
            32767, 0, 0,        # right = +X
            0.0, 0.0, 0.0,      # g
            0.0, 0.0, 0.0,      # yaw pitch roll
        )
    return header(pk.PacketId.MOTION) + body


def lap_data(position: int = 3, lap: int = 5, pit: int = 0,
             delta_front_ms: int = 2400, warnings: int = 0) -> bytes:
    body = b""
    for i in range(pk.MAX_CARS):
        is_me = i == 0
        body += pk.LAP_FMT.pack(
            92000, 45000,          # last, current lap ms
            30000, 0, 31000, 0,    # sectors
            delta_front_ms if is_me else 0, 0,
            5000, 0,
            1000.0, 5000.0, 0.0,   # distances
            position if is_me else (i + 1),
            lap, pit, 0, 1, 0,
            0, warnings if is_me else 0, warnings if is_me else 0,
            0, 0,
            position if is_me else (i + 1),
            pk.DriverStatus.ON_TRACK,
            2,                     # result: active
            0,
            0, 0, 0,
            0.0, 0,
        )
    body += struct.pack("<BB", 255, 255)  # time trial idx
    return header(pk.PacketId.LAP_DATA) + body


def telemetry(speed: int = 250, tyre_temp: int = 92) -> bytes:
    body = b""
    for _ in range(pk.MAX_CARS):
        body += pk.TELEMETRY_FMT.pack(
            speed, 1.0, 0.0, 0.0, 0, 6, 11000, 0, 50, 0,
            500, 500, 500, 500,
            tyre_temp, tyre_temp, tyre_temp, tyre_temp,
            tyre_temp + 5, tyre_temp + 5, tyre_temp + 5, tyre_temp + 5,
            95,
            23.0, 23.0, 21.0, 21.0,
            0, 0, 0, 0,
        )
    body += struct.pack("<BBb", 0, 255, 6)
    return header(pk.PacketId.CAR_TELEMETRY) + body


def car_status(limiter: int = 0, fuel_laps: float = 12.0,
               flag: int = 0) -> bytes:
    body = b""
    for _ in range(pk.MAX_CARS):
        body += pk.STATUS_FMT.pack(
            0, 0, 1, 50, limiter,
            80.0, 110.0, fuel_laps,
            13000, 3000, 8, 0, 0,
            16, 16, 5, flag,
            0.0, 0.0, 4000000.0, 1,
            0.0, 0.0, 0.0, 0,
        )
    return header(pk.PacketId.CAR_STATUS) + body


def car_damage(front_wing: int = 0, tyre_dmg: int = 0,
               wear: float = 5.0) -> bytes:
    body = b""
    for _ in range(pk.MAX_CARS):
        body += pk.DAMAGE_FMT.pack(
            wear, wear, wear, wear,
            tyre_dmg, tyre_dmg, 0, 0,
            0, 0, 0, 0,
            front_wing, front_wing, 0, 0, 0, 0,
            0, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0,
        )
    return header(pk.PacketId.CAR_DAMAGE) + body


def session(weather: int = 0, track_temp: int = 30, safety_car: int = 0,
            rain_in: int | None = None, rain_pct: int = 0) -> bytes:
    body = pk.SESSION_PREFIX_FMT.pack(
        weather, track_temp, 22, 20, 5000, pk.SessionType.RACE, 1, 0,
        3600, 3600, 80, 0, 0, 255, 0, 0,
    )
    body += pk.MARSHAL_ZONE_FMT.pack(0.0, 0) * pk.NUM_MARSHAL_ZONES
    body += struct.pack("<BB", safety_car, 0)

    samples = []
    if rain_in is not None:
        samples.append(pk.FORECAST_FMT.pack(
            pk.SessionType.RACE, rain_in, pk.Weather.LIGHT_RAIN,
            track_temp, 0, 20, 0, rain_pct))
    body += struct.pack("<B", len(samples)) + b"".join(samples)

    # Добиваем до размера, который ждёт парсер.
    packet = header(pk.PacketId.SESSION) + body
    need = pk.EXPECTED_SIZE[pk.PacketId.SESSION]
    if len(packet) < need:
        packet += b"\x00" * (need - len(packet))
    return packet[:need]


def event(code: str) -> bytes:
    body = code.encode("ascii") + b"\x00" * 12
    packet = header(pk.PacketId.EVENT) + body
    return packet[:pk.EXPECTED_SIZE[pk.PacketId.EVENT]]


# --------------------------------------------------------------- сценарий

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def send(data: bytes) -> None:
    sock.sendto(data, (HOST, PORT))


def beat(duration: float, rivals: list[tuple[float, float]],
         extra: list[bytes] | None = None) -> None:
    """Держит поток Motion-пакетов, как настоящая игра."""
    end = time.monotonic() + duration
    sent_extra = False
    while time.monotonic() < end:
        send(motion(rivals))
        if not sent_extra and extra:
            for p in extra:
                send(p)
            sent_extra = True
        time.sleep(1 / 60)


def step(text: str) -> None:
    print(f"\n>>> {text}")


print(f"Шлю синтетическую телеметрию F1 25 на {HOST}:{PORT}")
print("Споттер должен реагировать. Ctrl+C - стоп.\n")

try:
    step("подключение, гонка идёт, никого рядом")
    beat(2.0, [], [session(), lap_data(), telemetry(), car_status(),
                   car_damage()])

    step("старт гонки (lights out)")
    beat(2.0, [], [event("LGOT")])

    step("соперник ПОДЪЕЗЖАЕТ СЛЕВА")
    beat(3.0, [(-3.0, 0.0)], [lap_data()])

    step("он ОТСТАЛ - должно быть 'чисто'")
    beat(2.0, [])

    step("соперник СПРАВА")
    beat(3.0, [(3.0, 0.5)])

    step("С ДВУХ СТОРОН")
    beat(3.0, [(3.0, 0.0), (-3.0, 0.0)])

    step("все разъехались")
    beat(2.0, [])

    step("жёлтый флаг")
    beat(2.5, [], [car_status(flag=pk.Flag.YELLOW)])

    step("зелёный флаг")
    beat(2.5, [], [car_status(flag=pk.Flag.GREEN)])

    step("сейфти-кар")
    beat(2.5, [], [session(safety_car=pk.SafetyCar.FULL)])

    step("сейфти-кар уехал")
    beat(2.5, [], [session(safety_car=pk.SafetyCar.NONE)])

    step("прогноз: дождь через 10 минут, 70 процентов")
    beat(3.5, [], [session(rain_in=10, rain_pct=70)])

    step("начался дождь")
    beat(4.0, [], [session(weather=pk.Weather.LIGHT_RAIN)])

    step("сломал переднее крыло")
    beat(3.0, [], [car_damage(front_wing=45)])

    step("прокол")
    beat(3.0, [], [car_damage(front_wing=45, tyre_dmg=90)])

    step("выехал за трассу - предупреждение")
    beat(2.5, [], [lap_data(warnings=1)])

    step("в пит-лейне без лимитера, 90 км/ч")
    beat(3.0, [], [lap_data(pit=1), telemetry(speed=90), car_status(limiter=0)])

    step("включил лимитер")
    beat(2.0, [], [car_status(limiter=1)])

    step("готово")
    time.sleep(1.0)

except KeyboardInterrupt:
    print("\nСтоп.")
