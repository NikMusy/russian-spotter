"""Чтение телеметрии Le Mans Ultimate и перевод её в общее состояние.

LMU публикует память сама (объект LMU_Data), плагин ставить не нужно.

Система координат в LMU левосторонняя, +y вверх, а локальные оси машины:
  +x - НАЛЕВО, +y - в крышу, +z - НАЗАД
(так написано в InternalsPlugin.hpp). У F1 наоборот, поэтому при переводе
в наши векторы "вперёд" и "вправо" знаки инвертируются - иначе споттер
кричал бы "слева" про того, кто справа.
"""

from __future__ import annotations

import ctypes
import math
from ctypes import wintypes

from ..state import GameState
from ..udp.packets import (
    CarDamage, CarMotion, CarStatus, Flag, Header, LapData, SessionInfo,
    Telemetry, DriverStatus, PitStatus, SafetyCar, SessionType, Weather,
)
from . import lmu_structs as S


FILE_MAP_READ = 0x0004

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.OpenFileMappingW.restype = wintypes.HANDLE
_k32.OpenFileMappingW.argtypes = [wintypes.DWORD, wintypes.BOOL,
                                  wintypes.LPCWSTR]
_k32.MapViewOfFile.restype = ctypes.c_void_p
_k32.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                               wintypes.DWORD, wintypes.DWORD,
                               ctypes.c_size_t]
_k32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_k32.VirtualQuery.restype = ctypes.c_size_t


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("__alignment1", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("__alignment2", wintypes.DWORD),
    ]


class LMUReader:
    """Открывает разделяемую память LMU и отдаёт снимок.

    Именно OpenFileMapping, а не mmap(-1, tagname=...): второй, не найдя
    объект, молча СОЗДАЁТ свой пустой, и тогда мы читаем нули, считая, что
    подключились к игре.
    """

    def __init__(self) -> None:
        self._handle = None
        self._addr: int | None = None
        self.region_size = 0
        self._buf = S.SharedMemoryLayout()

    @property
    def connected(self) -> bool:
        return self._addr is not None

    def open(self) -> bool:
        if self._addr is not None:
            return True

        handle = _k32.OpenFileMappingW(FILE_MAP_READ, False,
                                       S.SHARED_MEMORY_FILE)
        if not handle:
            return False

        addr = _k32.MapViewOfFile(handle, FILE_MAP_READ, 0, 0, 0)
        if not addr:
            _k32.CloseHandle(handle)
            return False

        self._handle = handle
        self._addr = addr
        self.region_size = self._query_size(addr)
        return True

    def _query_size(self, addr: int) -> int:
        info = MEMORY_BASIC_INFORMATION()
        if _k32.VirtualQuery(ctypes.c_void_p(addr), ctypes.byref(info),
                             ctypes.sizeof(info)):
            return int(info.RegionSize)
        return 0

    def read(self) -> S.SharedMemoryLayout | None:
        """Снимок памяти.

        Без блокировки: спинлок LMU держится на InterlockedCompareExchange,
        которого из Python не вызвать. Порванное чтение возможно, но данные
        обновляются десятки раз в секунду и следующий кадр всё исправит.
        """
        if self._addr is None:
            return None
        # Читаем не больше, чем реально отображено, иначе улетим за границу
        # региона и получим access violation.
        size = min(S.LAYOUT_SIZE, self.region_size or S.LAYOUT_SIZE)
        try:
            ctypes.memmove(ctypes.byref(self._buf), self._addr, size)
        except (OSError, ValueError):
            self.close()
            return None
        return self._buf

    def close(self) -> None:
        if self._addr is not None:
            _k32.UnmapViewOfFile(ctypes.c_void_p(self._addr))
            self._addr = None
        if self._handle is not None:
            _k32.CloseHandle(self._handle)
            self._handle = None
        self.region_size = 0


# Быстрее этого не едет никто: всё, что выше - мусор из порванного кадра.
MAX_SPEED_MS = 200.0        # 720 км/ч
# Дальше этого от центра трассы координат не бывает.
MAX_COORD = 100000.0


def _finite(value: float, limit: float) -> bool:
    """Число вменяемое? Ловит мусор до того, как он дойдёт до правил."""
    return math.isfinite(value) and abs(value) <= limit


def _speed_kmh(vel: S.TelemVect3) -> int:
    """Скорость из вектора.

    Память читается без блокировки, поэтому кадр может оказаться
    полуобновлённым, а в поле - мусор вроде 1e200. Возведение такого в
    квадрат роняло движок с OverflowError прямо посреди гонки.
    """
    try:
        speed = math.sqrt(vel.x ** 2 + vel.y ** 2 + vel.z ** 2)
    except (OverflowError, ValueError):
        return 0
    if not math.isfinite(speed) or speed > MAX_SPEED_MS:
        return 0
    return int(round(speed * 3.6))


def _session_type(session: int) -> int:
    """LMU: 0=testday, 1-4=practice, 5-8=qual, 9=warmup, 10-13=race."""
    if session == 0:
        return SessionType.P1
    if 1 <= session <= 4:
        return SessionType.P1
    if 5 <= session <= 8:
        return SessionType.Q1
    if session == 9:
        return SessionType.P3
    return SessionType.RACE


def _weather(raining: float, wetness: float) -> int:
    if raining >= 0.55:
        return Weather.STORM
    if raining >= 0.30:
        return Weather.HEAVY_RAIN
    if raining >= 0.05:
        return Weather.LIGHT_RAIN
    if wetness >= 0.25:
        return Weather.OVERCAST
    return Weather.CLEAR


class LMUAdapter:
    """Наполняет GameState данными LMU, чтобы правила работали как есть."""

    def __init__(self) -> None:
        self.reader = LMUReader()
        self.frame = 0
        self.last_class: int = S.VehicleClass.UNKNOWN
        # Жёлтый на нашем участке или где-то на трассе - решается в _flag.
        self.yellow_is_mine = False

    def open(self) -> bool:
        return self.reader.open()

    def close(self) -> None:
        self.reader.close()

    def poll(self, state: GameState) -> bool:
        """Читает кадр в состояние. False - кадра нет или он битый.

        Всё завёрнуто в защиту: игра пишет память параллельно с нашим
        чтением, поэтому кадр может попасться полуобновлённым. Лучше
        пропустить его и взять следующий через 16 мс, чем уронить споттер
        посреди гонки.
        """
        try:
            return self._poll(state)
        except (OverflowError, ValueError, OSError, UnicodeDecodeError):
            return False

    def _poll(self, state: GameState) -> bool:
        snap = self.reader.read()
        if snap is None:
            return False

        scoring = snap.data.scoring.scoringInfo
        vehicles = snap.data.scoring.vehScoringInfo
        telemetry = snap.data.telemetry

        count = scoring.mNumVehicles
        if not (0 < count <= S.MAX_VEHICLES):
            return False

        player = -1
        for i in range(count):
            if vehicles[i].mIsPlayer:
                player = i
                break
        if player < 0:
            return False

        # Координаты игрока - лучший индикатор целого кадра: если они
        # поехали, значит поймали момент записи.
        me = vehicles[player]
        if not all(_finite(getattr(me.mPos, ax), MAX_COORD) for ax in "xyz"):
            return False

        self.frame += 1
        header = Header(
            packet_format=2025, game_year=0, game_major=0, game_minor=0,
            packet_version=1, packet_id=0,
            session_uid=0, session_time=scoring.mCurrentET,
            frame=self.frame, overall_frame=self.frame,
            player_car_index=player, secondary_player_car_index=255,
        )

        motion = [self._motion(vehicles[i]) for i in range(count)]
        laps = [self._lap(vehicles[i], scoring) for i in range(count)]

        state.track_name = scoring.mTrackName.decode("utf-8", "replace")
        state.car_classes = [
            vehicles[i].mVehicleClass.decode("utf-8", "replace")
            for i in range(count)
        ]
        state.car_speeds = [_speed_kmh(vehicles[i].mLocalVel)
                            for i in range(count)]

        state.update(header, motion)
        state.update(header, laps)
        state.update(header, self._session(scoring))

        # Телеметрия игрока есть не всегда (например, в мониторе).
        state.time_of_day = float(scoring.mTimeOfDay)

        idx = telemetry.playerVehicleIdx
        if telemetry.playerHasVehicle and idx < S.MAX_VEHICLES:
            tele = telemetry.telemInfo[idx]
            state.update(header, self._telemetry(tele))
            state.update(header, self._status(tele, vehicles[player], scoring))
            state.yellow_is_mine = self.yellow_is_mine
            state.update(header, self._damage(tele))
            state.wheels_detached = tuple(bool(w.mDetached)
                                          for w in tele.mWheel)
            state.rival_lost_wheel_ahead = self._rival_wheel_off(
                snap, me.mLapDist, scoring.mLapDist)
            state.gap_behind_sec = max(0.0, float(tele.mTimeGapCarBehind))
            state.headlights_on = bool(tele.mHeadlights)
            # Виртуальная энергия стинта (WEC гиперкары). Поле может
            # приходить как доля 0..1 или в процентах - нормализуем.
            ve = float(tele.mVirtualEnergy)
            state.virtual_energy = ve / 100.0 if ve > 1.5 else ve
            # LMU не кладёт валидность круга в scoring - только в телеметрию
            # игрока. Без этого срезанный круг шёл бы в личный рекорд.
            if 0 <= player < len(laps):
                laps[player].lap_invalid = 1 if tele.mLapInvalidated else 0
        return True

    def _rival_wheel_off(self, snap, my_dist: float,
                         track_len: float) -> bool:
        """Есть ли впереди в пределах ста метров машина с отвалившимся колесом.

        Телеметрия и таблица позиций - разные массивы, связаны через mID,
        поэтому сперва строим карту слот -> дистанция.
        """
        tel = snap.data.telemetry
        veh = snap.data.scoring.vehScoringInfo
        n = snap.data.scoring.scoringInfo.mNumVehicles
        dist_by_id = {veh[i].mID: veh[i].mLapDist for i in range(min(n, S.MAX_VEHICLES))}

        for i in range(min(tel.activeVehicles, S.MAX_VEHICLES)):
            car = tel.telemInfo[i]
            if not any(w.mDetached for w in car.mWheel):
                continue
            d = dist_by_id.get(car.mID)
            if d is None:
                continue
            gap = d - my_dist
            if track_len > 0 and gap < -track_len / 2:
                gap += track_len
            if 0 < gap < 100:
                return True
        return False


    def _motion(self, v: S.VehicleScoringInfoV01) -> CarMotion:
        # mOri - строки матрицы: world[i] = dot(mOri[i], local).
        # Локальный "вперёд" = (0,0,-1), "вправо" = (-1,0,0) - из-за того,
        # что у LMU +z смотрит назад, а +x налево.
        ori = v.mOri
        fwd_x, fwd_z = -ori[0].z, -ori[2].z
        right_x, right_z = -ori[0].x, -ori[2].x
        return CarMotion(
            x=v.mPos.x, y=v.mPos.y, z=v.mPos.z,
            fwd_x=fwd_x, fwd_z=fwd_z,
            right_x=right_x, right_z=right_z,
            yaw=math.atan2(fwd_x, fwd_z),
        )

    def _lap(self, v: S.VehicleScoringInfoV01,
             scoring: S.ScoringInfoV01) -> LapData:
        if v.mInPits or v.mPitState in (S.PitState.ENTERING,
                                        S.PitState.STOPPED,
                                        S.PitState.EXITING):
            pit = PitStatus.PITTING
        else:
            pit = PitStatus.NONE

        if v.mInGarageStall:
            driver = DriverStatus.IN_GARAGE
        elif v.mInPits:
            driver = DriverStatus.IN_LAP
        else:
            driver = DriverStatus.ON_TRACK

        # mSector: 0=третий, 1=первый, 2=второй.
        sector = {1: 0, 2: 1, 0: 2}.get(v.mSector, 0)

        return LapData(
            last_lap_ms=int(max(0.0, v.mLastLapTime) * 1000),
            current_lap_ms=int(max(0.0, v.mTimeIntoLap) * 1000),
            delta_front_ms=int(max(0.0, v.mTimeBehindNext) * 1000),
            delta_leader_ms=int(max(0.0, v.mTimeBehindLeader) * 1000),
            lap_distance=v.mLapDist,
            total_distance=v.mLapDist + v.mTotalLaps * max(1.0, scoring.mLapDist),
            safety_car_delta=0.0,
            position=v.mPlace,
            current_lap=v.mTotalLaps + 1,
            pit_status=pit,
            num_pit_stops=v.mNumPitstops,
            sector=sector,
            lap_invalid=0,
            penalties=v.mNumPenalties,
            total_warnings=0,
            corner_cutting_warnings=0,
            # LMU не раскладывает штрафы по типам - только общий счётчик.
            num_unserved_drive_through=0,
            num_unserved_stop_go=0,
            grid_position=v.mQualification if v.mQualification > 0 else 0,
            driver_status=driver,
            # 2 = активен; для нас важно лишь, что машина в игре.
            result_status=3 if v.mFinishStatus == 1 else 2,
            pit_lane_timer_active=1 if v.mInPits else 0,
        )

    def _session(self, s: S.ScoringInfoV01) -> SessionInfo:
        if s.mGamePhase == S.GamePhase.FULL_COURSE_YELLOW:
            safety = SafetyCar.FULL
        elif s.mGamePhase == S.GamePhase.FORMATION:
            safety = SafetyCar.FORMATION_LAP
        else:
            safety = SafetyCar.NONE

        return SessionInfo(
            weather=_weather(s.mRaining, s.mAvgPathWetness),
            track_temperature=int(s.mTrackTemp),
            air_temperature=int(s.mAmbientTemp),
            total_laps=max(0, s.mMaxLaps) if s.mMaxLaps < 1000 else 0,
            track_length=int(s.mLapDist),
            session_type=_session_type(s.mSession),
            track_id=0,
            session_time_left=int(max(0.0, s.mSessionTimeRemaining)),
            session_duration=int(max(0.0, s.mEndET)),
            pit_speed_limit=60,      # у LMU в разных сериях по-разному
            safety_car_status=safety,
            network_game=1 if s.mGameMode else 0,
            forecast=[],             # LMU прогноз наружу не отдаёт
        )

    def _flag(self, v: S.VehicleScoringInfoV01,
              scoring: S.ScoringInfoV01) -> int:
        """Какой флаг показывают лично нам.

        LMU раскладывает флаги по нескольким полям, и надёжного одного
        нет - поэтому смотрим все:

        * mIndividualPhase - фаза конкретной машины, 10 = идёт под жёлтым,
          11 = под синим. Самый точный сигнал, раньше не использовался;
        * mFlag - в заголовке сказано "только 0=зелёный или 6=синий";
        * mSectorFlag - локальные жёлтые по секторам. В заголовке честно
          написано, что порядок секторов авторы сами не помнят ("not sure
          if sector 0 is first or last"), поэтому привязываться к своему
          сектору нельзя: раньше из-за этого индекс уезжал на единицу и
          жёлтый молчал. Берём флаг, если он поднят хоть где-то;
        * mYellowFlagState / mUnderYellow - полная жёлтая по трассе.
        """
        if scoring.mGamePhase == S.GamePhase.STOPPED:
            return Flag.RED

        phase = v.mIndividualPhase
        if phase == 11 or v.mFlag == S.VehFlag.BLUE:
            return Flag.BLUE
        # Под жёлтым именно мы - можно сказать "в твоём секторе".
        if phase == 10 or v.mUnderYellow:
            self.yellow_is_mine = True
            return Flag.YELLOW

        self.yellow_is_mine = False
        if any(scoring.mSectorFlag[i] for i in range(3)):
            return Flag.YELLOW
        if scoring.mYellowFlagState > S.YellowState.NONE:
            return Flag.YELLOW
        return Flag.GREEN

    def _telemetry(self, t: S.TelemInfoV01) -> Telemetry:
        # Температуры в Кельвинах, наружу отдаём Цельсий.
        surface = []
        inner = []
        brakes = []
        pressure = []
        for w in t.mWheel:
            surface.append(int(sum(w.mTemperature) / 3 - 273.15))
            inner.append(int(w.mTireInnerLayerTemperature[1] - 273.15))
            brakes.append(int(w.mBrakeTemp - 273.15))
            pressure.append(w.mPressure)

        return Telemetry(
            speed=_speed_kmh(t.mLocalVel),
            throttle=t.mFilteredThrottle,
            steer=t.mFilteredSteering,
            brake=t.mFilteredBrake,
            gear=t.mGear,
            rpm=int(t.mEngineRPM),
            drs=1 if t.mRearFlapActivated else 0,
            brake_temp=tuple(brakes),
            tyre_surface_temp=tuple(surface),
            tyre_inner_temp=tuple(inner),
            engine_temp=int(t.mEngineWaterTemp),
            tyre_pressure=tuple(pressure),
            surface_type=tuple(w.mSurfaceType for w in t.mWheel),
        )

    def _status(self, t: S.TelemInfoV01, v: S.VehicleScoringInfoV01,
                scoring: S.ScoringInfoV01) -> CarStatus:
        flag = self._flag(v, scoring)

        # Сколько кругов проедем на остатке топлива - считаем сами.
        laps_left = 0.0
        if t.mFuelCapacity > 0 and t.mLapNumber > 1:
            used = max(0.001, t.mFuelCapacity - t.mFuel)
            per_lap = used / max(1, t.mLapNumber - 1)
            laps_left = t.mFuel / per_lap if per_lap > 0 else 0.0

        return CarStatus(
            fuel_mix=1,
            pit_limiter=1 if t.mSpeedLimiterActive else 0,
            fuel_in_tank=t.mFuel,
            fuel_capacity=t.mFuelCapacity,
            fuel_remaining_laps=laps_left,
            drs_allowed=1 if t.mRearFlapLegalStatus == 2 else 0,
            drs_activation_distance=0,
            actual_tyre_compound=t.mFrontTireCompoundIndex,
            visual_tyre_compound=t.mFrontTireCompoundIndex,
            tyres_age_laps=0,
            fia_flag=flag,
            ers_store=t.mBatteryChargeFraction,
            ers_deploy_mode=t.mElectricBoostMotorState,
        )

    def _damage(self, t: S.TelemInfoV01) -> CarDamage:
        # У LMU нет процентов по деталям - есть вмятины 0/1/2 в 8 точках.
        dents = list(t.mDentSeverity)
        front = max(dents[0], dents[1]) * 40 if len(dents) > 1 else 0
        rear = max(dents[4], dents[5]) * 40 if len(dents) > 5 else 0
        wear = [int((1.0 - w.mWear) * 100) for w in t.mWheel]
        flat = [100 if w.mFlat else 0 for w in t.mWheel]
        return CarDamage(
            tyre_wear=tuple(float(x) for x in wear),
            tyre_damage=tuple(flat),
            front_left_wing=front, front_right_wing=front,
            rear_wing=rear, floor=0, diffuser=0, sidepod=0,
            gearbox=0, engine=0,
        )
