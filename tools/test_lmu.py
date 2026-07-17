"""Проверка адаптера LMU без запущенной игры.

Живую игру заменяем поддельным блоком памяти: создаём объект LMU_Data сами
и раскладываем в него машины с известными координатами. Так проверяется и
раскладка структур, и знаки осей.
"""

import ctypes
import math
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from _lmu_guard import require_no_live_lmu

require_no_live_lmu("структуры LMU")

from spotter.rules.proximity import LEFT, RIGHT, ProximityRule
from spotter.sims import lmu_structs as S
from spotter.sims.lmu import LMUAdapter
from spotter.state import GameState

PAGE_READWRITE = 0x04
FILE_MAP_ALL = 0x000F001F

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileMappingW.restype = wintypes.HANDLE
k32.CreateFileMappingW.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                   wintypes.DWORD, wintypes.DWORD,
                                   wintypes.DWORD, wintypes.LPCWSTR]
k32.MapViewOfFile.restype = ctypes.c_void_p
k32.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                              wintypes.DWORD, ctypes.c_size_t]


class FakeLMU:
    """Играет роль игры: создаёт LMU_Data и пишет туда сцену."""

    def __init__(self) -> None:
        self.handle = k32.CreateFileMappingW(
            wintypes.HANDLE(-1), None, PAGE_READWRITE, 0, S.LAYOUT_SIZE,
            S.SHARED_MEMORY_FILE)
        if not self.handle:
            raise OSError(f"CreateFileMapping: {ctypes.get_last_error()}")
        self.addr = k32.MapViewOfFile(self.handle, FILE_MAP_ALL, 0, 0, 0)
        if not self.addr:
            raise OSError(f"MapViewOfFile: {ctypes.get_last_error()}")
        self.layout = S.SharedMemoryLayout.from_address(self.addr)

    def scene(self, rivals: list[tuple[float, float]], speed: float = 60.0,
              raining: float = 0.0, phase: int = S.GamePhase.GREEN) -> None:
        """rivals: (поперёк, вдоль) относительно игрока, в метрах.

        Игрок в начале координат смотрит вдоль мирового -Z (у LMU локальный
        +z указывает назад).
        """
        d = self.layout.data
        sc = d.scoring.scoringInfo
        sc.mNumVehicles = 1 + len(rivals)
        sc.mTrackName = b"Circuit de la Sarthe"
        sc.mPlayerName = b"Test"
        sc.mSession = 10                # гонка
        sc.mGamePhase = phase
        sc.mLapDist = 13626.0
        sc.mMaxLaps = 24
        sc.mTrackTemp = 28.0
        sc.mAmbientTemp = 21.0
        sc.mRaining = raining
        sc.mCurrentET = 100.0

        cars = [(0.0, 0.0)] + rivals
        for i, (lat, lon) in enumerate(cars):
            v = d.scoring.vehScoringInfo[i]
            v.mIsPlayer = (i == 0)
            v.mPlace = i + 1
            v.mTotalLaps = 3
            v.mInPits = False
            v.mInGarageStall = False
            v.mControl = 0 if i == 0 else 2
            v.mDriverName = f"Driver{i}".encode()
            v.mVehicleClass = b"Hypercar" if i == 0 else b"LMP2"
            v.mTimeBehindNext = 2.4
            v.mLapDist = 1000.0
            v.mFinishStatus = 0
            v.mSector = 1

            # Мир: X вправо от игрока, Z - вперёд у него за спиной.
            # Игрок смотрит вдоль -Z, значит "вперёд" в мире = -Z.
            v.mPos.x = lat
            v.mPos.y = 0.0
            v.mPos.z = -lon
            v.mLocalVel.x = 0.0
            v.mLocalVel.y = 0.0
            v.mLocalVel.z = -speed      # +z назад, движение вперёд = -z

            # Матрица: world[i] = dot(mOri[i], local).
            # local +x (налево) -> world -X ; local +z (назад) -> world +Z
            for r in range(3):
                v.mOri[r].x = v.mOri[r].y = v.mOri[r].z = 0.0
            v.mOri[0].x = -1.0   # world.x = -local.x
            v.mOri[1].y = 1.0    # world.y =  local.y
            v.mOri[2].z = 1.0    # world.z =  local.z

        d.telemetry.playerHasVehicle = True
        d.telemetry.playerVehicleIdx = 0
        d.telemetry.activeVehicles = len(cars)
        t = d.telemetry.telemInfo[0]
        t.mLocalVel.z = -speed
        t.mFuel = 50.0
        t.mFuelCapacity = 100.0
        t.mLapNumber = 4
        t.mGear = 4
        t.mEngineRPM = 8000
        t.mFilteredThrottle = 1.0
        for w in t.mWheel:
            w.mTemperature[0] = w.mTemperature[1] = w.mTemperature[2] = 363.15
            w.mTireInnerLayerTemperature[1] = 368.15
            w.mBrakeTemp = 573.15
            w.mPressure = 165.0
            w.mWear = 0.95
        d.generic.gameVersion = 1140


print("АДАПТЕР LMU (на поддельном блоке памяти)")
print("-" * 58)

fails = 0
fake = FakeLMU()
print(f"  создал фальшивый LMU_Data, {S.LAYOUT_SIZE:,} байт")

adapter = LMUAdapter()
ok = adapter.open()
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} адаптер открыл память")
print(f"       регион: {adapter.reader.region_size:,} байт")

state = GameState()

# --- сцена: соперник справа
fake.scene([(3.0, 0.0)])
ok = adapter.poll(state)
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} прочитал кадр")

checks = [
    ("нашёл игрока", state.player_index == 0),
    ("машин в состоянии 2", len(state.motion) == 2),
    ("позиция игрока 1", state.me.position == 1 if state.me else False),
    ("круг 4", state.me.current_lap == 4 if state.me else False),
    ("скорость ~216 км/ч", abs(state.speed_kmh - 216) <= 2),
    ("трасса 13626 м", state.session.track_length == 13626),
    ("температура трассы 28", state.session.track_temperature == 28),
    ("гонка распознана", state.in_race),
    ("на трассе", state.on_track),
    ("не в пите", not state.in_pits),
    ("отрыв 2.4 сек",
     abs(state.me.delta_front_ms - 2400) <= 5 if state.me else False),
    ("шины ~90 C", abs(state.telemetry.tyre_surface_temp[0] - 90) <= 1),
]
for name, ok in checks:
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {name}")

# --- ГЛАВНОЕ: знаки осей
print()
print("СТОРОНЫ (тут легче всего перепутать лево и право)")
print("-" * 58)
rule = ProximityRule()

fake.scene([(3.0, 0.0)])
adapter.poll(state)
got = rule._detect(state)
ok = got == RIGHT
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} соперник в +3 м вбок -> {got} (ждём {RIGHT})")

fake.scene([(-3.0, 0.0)])
adapter.poll(state)
got = rule._detect(state)
ok = got == LEFT
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} соперник в -3 м вбок -> {got} (ждём {LEFT})")

fake.scene([(3.0, 30.0)])
adapter.poll(state)
got = rule._detect(state)
ok = got == "clear"
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} соперник далеко впереди -> {got} (ждём clear)")

# --- погода и FCY
print()
print("ПОГОДА И ФЛАГИ")
print("-" * 58)
from spotter.udp.packets import SafetyCar, Weather

fake.scene([], raining=0.4)
adapter.poll(state)
ok = state.session.weather == Weather.HEAVY_RAIN
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} дождь 0.4 -> сильный дождь")

fake.scene([], raining=0.0)
adapter.poll(state)
ok = state.session.weather == Weather.CLEAR
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} без дождя -> ясно")

fake.scene([], phase=S.GamePhase.FULL_COURSE_YELLOW)
adapter.poll(state)
ok = state.session.safety_car_status == SafetyCar.FULL
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} фаза 6 -> полная жёлтая (сейфти-кар)")

adapter.close()
print()
print("-" * 58)
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
