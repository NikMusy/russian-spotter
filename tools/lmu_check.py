"""Диагностика связи с Le Mans Ultimate.

Запусти LMU, зайди в сессию (лучше в гонку с соперниками) и запусти это.
Показывает, читается ли память и осмысленны ли данные.
"""

import ctypes
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spotter.sims import lmu_structs as S
from spotter.sims.lmu import LMUAdapter, LMUReader
from spotter.state import GameState

print("=" * 62)
print("  ПРОВЕРКА СВЯЗИ С LE MANS ULTIMATE")
print("=" * 62)
print(f"  объект памяти : {S.SHARED_MEMORY_FILE}")
print(f"  ждём размер   : {S.LAYOUT_SIZE:,} байт")
print()

reader = LMUReader()
if not reader.open():
    print("  НЕ ВИЖУ ИГРУ.")
    print()
    print("  Проверь:")
    print("   1. Le Mans Ultimate запущена")
    print("   2. Ты зашёл в сессию (не в главном меню)")
    print("   3. Споттер и игра запущены от одного пользователя")
    print()
    print("  Если игра точно в сессии, а связи нет - пришли мне этот вывод.")
    sys.exit(1)

print("  СВЯЗЬ ЕСТЬ.")
print(f"  реальный блок : {reader.region_size:,} байт")
if reader.region_size and reader.region_size < S.LAYOUT_SIZE:
    print()
    print("  ВНИМАНИЕ: блок МЕНЬШЕ, чем ждут наши структуры.")
    print("  Значит у этой версии LMU другая раскладка. Пришли вывод.")
print()

snap = reader.read()
s = snap.data.scoring.scoringInfo
g = snap.data.generic

print("--- общее ---")
print(f"  версия игры    : {g.gameVersion}")
print(f"  трасса         : {s.mTrackName.decode('utf-8', 'replace')}")
print(f"  игрок          : {s.mPlayerName.decode('utf-8', 'replace')}")
print(f"  сессия         : {s.mSession}   фаза: {s.mGamePhase}")
print(f"  машин в сессии : {s.mNumVehicles}")
print(f"  круг трассы    : {s.mLapDist:.0f} м")
print(f"  макс. кругов   : {s.mMaxLaps}")
print()

print("--- погода ---")
print(f"  дождь          : {s.mRaining:.2f}")
print(f"  трасса         : {s.mTrackTemp:.1f} C")
print(f"  воздух         : {s.mAmbientTemp:.1f} C")
print(f"  мокрота (сред) : {s.mAvgPathWetness:.2f}")
print(f"  жёлтый флаг    : {s.mYellowFlagState}")
print()

n = min(s.mNumVehicles, S.MAX_VEHICLES)
print(f"--- машины ({n}) ---")
print(f"  {'поз':>3} {'кто':<20} {'класс':<10} {'X':>9} {'Z':>9} {'км/ч':>6}  пит")
for i in range(min(n, 12)):
    v = snap.data.scoring.vehScoringInfo[i]
    import math
    speed = math.sqrt(v.mLocalVel.x ** 2 + v.mLocalVel.y ** 2
                      + v.mLocalVel.z ** 2) * 3.6
    me = " <-- ТЫ" if v.mIsPlayer else ""
    print(f"  {v.mPlace:>3} {v.mDriverName.decode('utf-8', 'replace')[:20]:<20} "
          f"{v.mVehicleClass.decode('utf-8', 'replace')[:10]:<10} "
          f"{v.mPos.x:>9.1f} {v.mPos.z:>9.1f} {speed:>6.0f}  "
          f"{'да' if v.mInPits else '  '}{me}")
print()

# --- проверка вменяемости ------------------------------------------
print("--- ПРОВЕРКИ ---")
fails = 0
checks = []

checks.append(("число машин в пределах разумного", 0 < s.mNumVehicles <= 104))
checks.append(("длина круга похожа на трассу (1-30 км)",
               1000 < s.mLapDist < 30000))
checks.append(("температура трассы в пределах -20..80",
               -20 < s.mTrackTemp < 80))
checks.append(("температура воздуха в пределах -20..60",
               -20 < s.mAmbientTemp < 60))
checks.append(("дождь в диапазоне 0..1", 0.0 <= s.mRaining <= 1.0))
checks.append(("имя трассы читается",
               len(s.mTrackName.decode("utf-8", "ignore").strip()) > 0))

player = None
for i in range(n):
    if snap.data.scoring.vehScoringInfo[i].mIsPlayer:
        player = snap.data.scoring.vehScoringInfo[i]
        break
checks.append(("нашлась машина игрока", player is not None))

if player is not None:
    checks.append(("позиция игрока 1..104", 1 <= player.mPlace <= 104))
    pos_ok = all(abs(getattr(player.mPos, ax)) < 100000 for ax in "xyz")
    checks.append(("координаты игрока правдоподобны", pos_ok))

    # Матрица ориентации обязана быть ортонормальной - лучший признак
    # того, что структура не разъехалась.
    import math
    for r in range(3):
        row = player.mOri[r]
        length = math.sqrt(row.x ** 2 + row.y ** 2 + row.z ** 2)
        checks.append((f"строка ориентации {r} единичной длины "
                       f"({length:.3f})", 0.9 < length < 1.1))

for name, ok in checks:
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {name}")

print()
if fails:
    print(f"  ПРОВАЛОВ: {fails} - структура читается неверно, пришли вывод.")
    sys.exit(1)

print("  Данные осмысленные. Структуры совпадают.")
print()

# --- живой поток ----------------------------------------------------
print("--- ЖИВОЙ ПОТОК (5 сек), поезди по трассе ---")
adapter = LMUAdapter()
adapter.open()
state = GameState()
seen = 0
moved = set()
t0 = time.monotonic()
while time.monotonic() - t0 < 5.0:
    if adapter.poll(state):
        seen += 1
        m = state.my_motion
        if m:
            moved.add((round(m.x, 1), round(m.z, 1)))
    time.sleep(1 / 60)

print(f"  кадров прочитано : {seen}")
print(f"  разных позиций   : {len(moved)}  "
      f"{'(машина двигалась)' if len(moved) > 5 else '(машина стояла)'}")
me = state.me
if me:
    print(f"  позиция в гонке  : {me.position}")
    print(f"  круг             : {me.current_lap}")
    print(f"  скорость         : {state.speed_kmh} км/ч")
    print(f"  до впереди       : {me.delta_front_ms / 1000:.1f} сек")
adapter.close()
print()
print("  Готово.")
