"""Устойчивость к битым кадрам LMU.

Память читается без блокировки (спинлок игры из Python не вызвать), так
что рано или поздно попадётся кадр, пойманный посреди записи. Раньше такой
кадр ронял движок: mLocalVel.y = 1e200, потом ** 2 -> OverflowError.
Здесь скармливаем адаптеру заведомый мусор и требуем, чтобы он выжил.
"""

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from _lmu_guard import require_no_live_lmu

require_no_live_lmu("устойчивость к битым кадрам")

from fake_lmu import FakeLMU, hold
from spotter.sims import lmu_structs as S
from spotter.sims.lmu import MAX_COORD, LMUAdapter, _finite, _speed_kmh
from spotter.state import GameState

fails = 0
print("МУСОР В ПОЛЯХ")
print("-" * 62)


class V:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = x, y, z


CASES = [
    ("нормальная скорость 60 м/с", V(0, 0, -60.0), 216),
    ("нули", V(0, 0, 0), 0),
    ("1e200 - раньше ронял OverflowError", V(0, 1e200, 0), 0),
    ("-1e200", V(-1e200, 0, 0), 0),
    ("бесконечность", V(0, float("inf"), 0), 0),
    ("NaN", V(0, float("nan"), 0), 0),
    ("абсурдные 5000 м/с", V(0, 0, 5000.0), 0),
]
for name, vel, want in CASES:
    try:
        got = _speed_kmh(vel)
        ok = got == want
    except Exception as exc:
        got, ok = f"УПАЛ: {type(exc).__name__}", False
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {name:<38} -> {got}")

print()
print("ПРОВЕРКА ЧИСЕЛ")
print("-" * 62)
for name, val, want in [
    ("обычная координата", 1234.5, True),
    ("ноль", 0.0, True),
    ("1e200", 1e200, False),
    ("inf", float("inf"), False),
    ("nan", float("nan"), False),
]:
    got = _finite(val, MAX_COORD)
    ok = got == want
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {name:<24} -> {got}")

# --- адаптер на испорченном кадре
print()
print("АДАПТЕР НА БИТОМ КАДРЕ")
print("-" * 62)

fake = FakeLMU()
fake.scene([(3.0, 0.0)])
adapter = LMUAdapter()
adapter.open()
state = GameState()

ok = adapter.poll(state)
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} целый кадр читается")

# Портим координаты игрока - имитация записи посреди чтения
d = fake.layout.data
d.scoring.vehScoringInfo[0].mPos.x = 1e200
got = adapter.poll(state)
ok = got is False
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} кадр с мусором в координатах отброшен "
      f"(вернул {got})")

# Портим скорость в телеметрии - раньше тут и падало
fake.scene([(3.0, 0.0)])
d.telemetry.telemInfo[0].mLocalVel.y = 1e200
try:
    got = adapter.poll(state)
    ok = True
    print(f"  OK   кадр с мусором в скорости не уронил адаптер "
          f"(вернул {got}, скорость {state.speed_kmh})")
except Exception as exc:
    ok = False
    print(f"  FAIL адаптер упал: {type(exc).__name__}: {exc}")
fails += not ok

# Абсурдное число машин
fake.scene([(3.0, 0.0)])
d.scoring.scoringInfo.mNumVehicles = 9999
got = adapter.poll(state)
ok = got is False
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} абсурдное число машин отброшено")

fake.scene([(3.0, 0.0)])
d.scoring.scoringInfo.mNumVehicles = 0
got = adapter.poll(state)
ok = got is False
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} ноль машин отброшен")

# Восстановление: после мусора нормальный кадр должен читаться
fake.scene([(3.0, 0.0)])
got = adapter.poll(state)
ok = got and state.speed_kmh == 216
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} после мусора нормальный кадр снова "
      f"читается (скорость {state.speed_kmh})")

adapter.close()

# --- движок под потоком битых кадров
print()
print("ДВИЖОК ПОД ПОТОКОМ БИТЫХ КАДРОВ")
print("-" * 62)

from spotter.engine import Engine

said = []
eng = Engine(sounds_dir=ROOT / "sounds", swearing=False, volume=0.0,
             verbose=False, sim="lmu", memes=False,
             on_message=lambda t, m: said.append(t))
th = threading.Thread(target=eng.run, daemon=True)
th.start()
time.sleep(0.5)

# Пишем сцену и параллельно портим её - гарантированный torn read
stop = threading.Event()


def corrupt():
    import random
    while not stop.is_set():
        v = fake.layout.data.scoring.vehScoringInfo[0]
        v.mPos.y = random.choice([1e200, float("inf"), 0.0])
        fake.layout.data.telemetry.telemInfo[0].mLocalVel.y = 1e200
        time.sleep(0.001)


noise = threading.Thread(target=corrupt, daemon=True)
noise.start()
hold(fake, 4.0, [(3.0, 0.0)])
stop.set()
time.sleep(0.3)

alive = th.is_alive()
fails += not alive
print(f"  {'OK  ' if alive else 'FAIL'} движок выжил под битыми кадрами "
      f"(поток {'жив' if alive else 'УПАЛ'})")

eng.stop()
th.join(timeout=3)
eng.shutdown()

print()
print("-" * 62)
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
