"""Притворяется Le Mans Ultimate: создаёт LMU_Data и разыгрывает сценарий.

Нужен, чтобы проверить споттера без запуска игры.
Запусти spotter.exe (сим: Le Mans Ultimate, СТАРТ), потом это.
"""

import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spotter.sims import lmu_structs as S

PAGE_READWRITE = 0x04
FILE_MAP_ALL = 0x000F001F
ERROR_ALREADY_EXISTS = 183

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.CreateFileMappingW.restype = wintypes.HANDLE
k32.CreateFileMappingW.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                   wintypes.DWORD, wintypes.DWORD,
                                   wintypes.DWORD, wintypes.LPCWSTR]
k32.MapViewOfFile.restype = ctypes.c_void_p
k32.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                              wintypes.DWORD, ctypes.c_size_t]


class LMUAlreadyRunning(RuntimeError):
    """Настоящая игра уже держит LMU_Data."""


class FakeLMU:
    def __init__(self, allow_existing: bool = False) -> None:
        self.handle = k32.CreateFileMappingW(
            wintypes.HANDLE(-1), None, PAGE_READWRITE, 0, S.LAYOUT_SIZE,
            S.SHARED_MEMORY_FILE)
        err = ctypes.get_last_error()
        if not self.handle:
            raise OSError(f"CreateFileMapping: {err}")

        # CreateFileMapping не создаёт второй объект с тем же именем, а
        # отдаёт существующий. Если LMU запущена, мы начнём писать прямо
        # поверх её данных: погода и позиции будут скакать между тем, что
        # пишет игра, и тем, что пишем мы.
        if err == ERROR_ALREADY_EXISTS and not allow_existing:
            k32.CloseHandle(self.handle)
            raise LMUAlreadyRunning(
                "LMU_Data уже занят - похоже, запущена настоящая Le Mans "
                "Ultimate.\nЗакрой игру: иначе симулятор и игра будут "
                "писать в одну память,\nи споттер сойдёт с ума.")

        self.addr = k32.MapViewOfFile(self.handle, FILE_MAP_ALL, 0, 0, 0)
        if not self.addr:
            raise OSError(f"MapViewOfFile: {ctypes.get_last_error()}")
        self.layout = S.SharedMemoryLayout.from_address(self.addr)

    def close(self) -> None:
        if getattr(self, "addr", None):
            k32.UnmapViewOfFile(ctypes.c_void_p(self.addr))
            self.addr = None
        if getattr(self, "handle", None):
            k32.CloseHandle(self.handle)
            self.handle = None

    def scene(self, rivals, speed=60.0, raining=0.0, phase=S.GamePhase.GREEN,
              in_pits=False, limiter=False, place=3, lap=4, flag=0,
              wear=0.95, flat=False, fuel=50.0, tyre_c=90.0,
              sector_yellow=False, wheel_off=False, time_of_day=14 * 3600,
              headlights=False, gap_behind=0.0, virtual_energy=1.0):
        """rivals: (поперёк, вдоль) в метрах. Игрок смотрит вдоль -Z."""
        d = self.layout.data
        sc = d.scoring.scoringInfo
        sc.mTimeOfDay = float(time_of_day)     # по умолчанию день, 14:00
        sc.mSectorFlag[0] = sc.mSectorFlag[1] = sc.mSectorFlag[2] = 0
        if sector_yellow:
            sc.mSectorFlag[1] = 1      # игрок в mSector=1
        sc.mNumVehicles = 1 + len(rivals)
        sc.mTrackName = b"Circuit de la Sarthe"
        sc.mPlayerName = b"Test Driver"
        sc.mSession = 10
        sc.mGamePhase = phase
        sc.mLapDist = 13626.0
        sc.mMaxLaps = 24
        sc.mTrackTemp = 28.0
        sc.mAmbientTemp = 21.0
        sc.mRaining = raining
        sc.mAvgPathWetness = min(1.0, raining * 1.5)
        sc.mCurrentET = time.monotonic()
        sc.mSessionTimeRemaining = 3600.0

        cars = [(0.0, 0.0)] + list(rivals)
        for i, (lat, lon) in enumerate(cars):
            v = d.scoring.vehScoringInfo[i]
            v.mIsPlayer = (i == 0)
            v.mPlace = place if i == 0 else (i + 1)
            v.mTotalLaps = lap - 1
            v.mInPits = in_pits if i == 0 else False
            v.mInGarageStall = False
            v.mControl = 0 if i == 0 else 2
            v.mDriverName = f"Driver{i}".encode()
            # Именно так класс пишет живая LMU: коротко, "Hyper" и "GT3".
            v.mVehicleClass = b"Hyper" if i == 0 else b"GT3"
            v.mTimeBehindNext = 2.4
            v.mTimeBehindLeader = 12.0
            v.mLapDist = 1000.0
            v.mFinishStatus = 0
            v.mSector = 1
            v.mFlag = flag if i == 0 else 0
            v.mUnderYellow = (phase == S.GamePhase.FULL_COURSE_YELLOW)
            v.mTimeIntoLap = 45.0
            v.mLastLapTime = 210.0

            v.mPos.x, v.mPos.y, v.mPos.z = lat, 0.0, -lon
            v.mLocalVel.x = 0.0
            v.mLocalVel.y = 0.0
            v.mLocalVel.z = -speed
            for r in range(3):
                v.mOri[r].x = v.mOri[r].y = v.mOri[r].z = 0.0
            v.mOri[0].x = -1.0
            v.mOri[1].y = 1.0
            v.mOri[2].z = 1.0

        d.telemetry.playerHasVehicle = True
        d.telemetry.playerVehicleIdx = 0
        d.telemetry.activeVehicles = len(cars)
        t = d.telemetry.telemInfo[0]
        # Задаём вектор целиком: иначе оставленный кем-то мусор в x/y
        # переживёт смену сцены.
        t.mLocalVel.x = 0.0
        t.mLocalVel.y = 0.0
        t.mLocalVel.z = -speed
        t.mFuel = fuel
        t.mFuelCapacity = 100.0
        t.mLapNumber = lap
        t.mGear = 4
        t.mEngineRPM = 8000
        t.mEngineMaxRPM = 9000
        t.mFilteredThrottle = 1.0
        t.mSpeedLimiterActive = limiter
        t.mEngineWaterTemp = 95.0
        t.mHeadlights = headlights
        t.mTimeGapCarBehind = gap_behind
        t.mVirtualEnergy = virtual_energy
        for j, w in enumerate(t.mWheel):
            k = tyre_c + 273.15
            w.mTemperature[0] = w.mTemperature[1] = w.mTemperature[2] = k
            w.mTireInnerLayerTemperature[1] = k + 5
            w.mBrakeTemp = 573.15
            w.mPressure = 165.0
            w.mWear = wear
            w.mFlat = flat and j == 0
            w.mDetached = wheel_off and j == 0
        d.generic.gameVersion = 1140
        d.generic.events[S.SME_UPDATE_SCORING] = 1
        d.generic.events[S.SME_UPDATE_TELEMETRY] = 1


def hold(fake, seconds, rivals, **kw):
    """Держит сцену, обновляя её как живая игра."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        fake.scene(rivals, **kw)
        time.sleep(1 / 60)


def step(text):
    print(f"\n>>> {text}")


def main() -> None:
    fake = FakeLMU()
    print("Притворяюсь Le Mans Ultimate. Объект LMU_Data создан.")
    print("В споттере выбери 'Le Mans Ultimate' и жми СТАРТ.")
    print("Ctrl+C - стоп.\n")

    step("зашли в сессию - споттер объявит трассу")
    hold(fake, 6.0, [])

    step("гонка идёт, никого рядом")
    hold(fake, 3.0, [])

    step("соперник ПОДЪЕЗЖАЕТ СЛЕВА")
    hold(fake, 3.0, [(-3.0, 0.0)])

    step("отстал - должно быть 'чисто'")
    hold(fake, 2.5, [])

    step("соперник СПРАВА")
    hold(fake, 3.0, [(3.0, 0.5)])

    step("С ДВУХ СТОРОН")
    hold(fake, 3.0, [(3.0, 0.0), (-3.0, 0.0)])

    step("разъехались")
    hold(fake, 2.5, [])

    step("синий флаг - пропусти прототип")
    hold(fake, 3.0, [], flag=S.VehFlag.BLUE)

    step("ПОЛНАЯ ЖЁЛТАЯ (Full Course Yellow)")
    hold(fake, 3.5, [], phase=S.GamePhase.FULL_COURSE_YELLOW)

    step("жёлтая снята, гонка")
    hold(fake, 3.0, [], phase=S.GamePhase.GREEN)

    step("начался дождь")
    hold(fake, 4.0, [], raining=0.4)

    step("дождь кончился, трасса сохнет")
    hold(fake, 4.0, [], raining=0.0)

    step("шины перегрелись")
    hold(fake, 3.0, [], tyre_c=125.0)

    step("шины на исходе")
    hold(fake, 3.0, [], wear=0.2)

    step("жёлтый в твоём секторе")
    hold(fake, 3.0, [], sector_yellow=True)

    step("прокол")
    hold(fake, 3.0, [], flat=True)

    step("ОТВАЛИЛОСЬ КОЛЕСО")
    hold(fake, 3.0, [], wheel_off=True)

    step("в пит-лейне на 90 км/ч без лимитера")
    hold(fake, 3.5, [], in_pits=True, speed=25.0, limiter=False)

    step("включил лимитер")
    hold(fake, 2.5, [], in_pits=True, speed=22.0, limiter=True)

    step("готово")
    time.sleep(1.0)


if __name__ == "__main__":
    # Только по прямому запуску: иначе импорт этого модуля из теста
    # запускал бы весь сценарий.
    try:
        main()
    except LMUAlreadyRunning as exc:
        print()
        print("=" * 62)
        print("  НЕ ЗАПУСКАЮСЬ")
        print("=" * 62)
        print(f"  {exc}")
        print()
        print("  Симулятор нужен, чтобы проверить споттера БЕЗ игры.")
        print("  Если игра запущена - он и не нужен: слушай настоящую.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nСтоп.")
