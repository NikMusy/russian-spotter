"""Сверяет размеры struct-форматов со спецификацией F1 25."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spotter.udp import packets as pk

CHECKS = [
    # имя, фактический размер, ожидаемый, как считается полный пакет
    ("Header", pk.HEADER_FMT.size, 29, None),
    ("CarMotionData", pk.MOTION_FMT.size, 60, (pk.PacketId.MOTION, 22, 0)),
    ("LapData", pk.LAP_FMT.size, 57, (pk.PacketId.LAP_DATA, 22, 2)),
    ("CarTelemetryData", pk.TELEMETRY_FMT.size, 60, (pk.PacketId.CAR_TELEMETRY, 22, 3)),
    ("CarStatusData", pk.STATUS_FMT.size, 55, (pk.PacketId.CAR_STATUS, 22, 0)),
    ("CarDamageData", pk.DAMAGE_FMT.size, 46, (pk.PacketId.CAR_DAMAGE, 22, 0)),
    ("SessionPrefix", pk.SESSION_PREFIX_FMT.size, 19, None),
    ("MarshalZone", pk.MARSHAL_ZONE_FMT.size, 5, None),
    ("ForecastSample", pk.FORECAST_FMT.size, 8, None),
]

ok = True
print(f"{'структура':<20} {'факт':>5} {'ожид':>5}   пакет")
print("-" * 60)
for name, actual, expected, pack in CHECKS:
    good = actual == expected
    note = ""
    if pack:
        pid, count, tail = pack
        total = pk.HEADER_SIZE + actual * count + tail
        want = pk.EXPECTED_SIZE[pid]
        pgood = total == want
        good = good and pgood
        note = f"{total} vs {want} {'OK' if pgood else 'РАСХОЖДЕНИЕ'}"
    status = "OK" if good else "ОШИБКА"
    print(f"{name:<20} {actual:>5} {expected:>5}   {note:<22} {status}")
    ok = ok and good

print("-" * 60)
print("ВСЁ СОШЛОСЬ" if ok else "ЕСТЬ РАСХОЖДЕНИЯ")
sys.exit(0 if ok else 1)
