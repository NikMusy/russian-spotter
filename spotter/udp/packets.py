"""Разбор UDP-пакетов F1 25.

Все структуры little-endian и упакованы без выравнивания - отсюда '<' в
форматах struct. Размеры сверены со спецификацией "Data Output from F1 25":
если игра пришлёт пакет другого размера, parse_packet вернёт None, а не
отдаст мусор в правила.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

MAX_CARS = 22

# ---------------------------------------------------------------- header

HEADER_FMT = struct.Struct("<HBBBBBQfIIBB")
HEADER_SIZE = HEADER_FMT.size  # 29


@dataclass(frozen=True)
class Header:
    packet_format: int
    game_year: int
    game_major: int
    game_minor: int
    packet_version: int
    packet_id: int
    session_uid: int
    session_time: float
    frame: int
    overall_frame: int
    player_car_index: int
    secondary_player_car_index: int


class PacketId:
    MOTION = 0
    SESSION = 1
    LAP_DATA = 2
    EVENT = 3
    PARTICIPANTS = 4
    CAR_SETUPS = 5
    CAR_TELEMETRY = 6
    CAR_STATUS = 7
    FINAL_CLASSIFICATION = 8
    LOBBY_INFO = 9
    CAR_DAMAGE = 10
    SESSION_HISTORY = 11
    TYRE_SETS = 12
    MOTION_EX = 13
    TIME_TRIAL = 14
    LAP_POSITIONS = 15


# Ожидаемые размеры пакетов F1 25 (packet format 2025).
EXPECTED_SIZE = {
    PacketId.MOTION: 1349,
    PacketId.SESSION: 753,
    PacketId.LAP_DATA: 1285,
    PacketId.EVENT: 45,
    PacketId.PARTICIPANTS: 1284,
    PacketId.CAR_SETUPS: 1133,
    PacketId.CAR_TELEMETRY: 1352,
    PacketId.CAR_STATUS: 1239,
    PacketId.FINAL_CLASSIFICATION: 1042,
    PacketId.LOBBY_INFO: 954,
    PacketId.CAR_DAMAGE: 1041,
    PacketId.SESSION_HISTORY: 1460,
    PacketId.TYRE_SETS: 231,
    PacketId.MOTION_EX: 273,
    PacketId.TIME_TRIAL: 101,
    PacketId.LAP_POSITIONS: 1131,
}


def parse_header(data: bytes) -> Header | None:
    if len(data) < HEADER_SIZE:
        return None
    v = HEADER_FMT.unpack_from(data, 0)
    return Header(*v)


# ---------------------------------------------------------------- motion

# 6 float, 6 int16 (направления), 6 float = 60 байт
MOTION_FMT = struct.Struct("<6f6h6f")


@dataclass
class CarMotion:
    x: float
    y: float
    z: float
    fwd_x: float
    fwd_z: float
    right_x: float
    right_z: float
    yaw: float


def parse_motion(data: bytes) -> list[CarMotion]:
    cars = []
    off = HEADER_SIZE
    for _ in range(MAX_CARS):
        (px, py, pz, _vx, _vy, _vz,
         fx, fy, fz, rx, ry, rz,
         _gl, _glon, _gv, yaw, _pitch, _roll) = MOTION_FMT.unpack_from(data, off)
        cars.append(CarMotion(
            x=px, y=py, z=pz,
            fwd_x=fx / 32767.0, fwd_z=fz / 32767.0,
            right_x=rx / 32767.0, right_z=rz / 32767.0,
            yaw=yaw,
        ))
        off += MOTION_FMT.size
    return cars


# -------------------------------------------------------------- lap data

# 15 однобайтовых полей идут подряд, от m_carPosition до
# m_pitLaneTimerActive - считать их в строке формата глазами слишком легко
# ошибиться, поэтому склеиваем явно.
LAP_FMT = struct.Struct("<IIHBHBHBHBfff" + "B" * 15 + "HHBfB")  # 57


class PitStatus:
    NONE = 0
    PITTING = 1
    IN_PIT_AREA = 2


class DriverStatus:
    IN_GARAGE = 0
    FLYING_LAP = 1
    IN_LAP = 2
    OUT_LAP = 3
    ON_TRACK = 4


@dataclass
class LapData:
    last_lap_ms: int
    current_lap_ms: int
    delta_front_ms: int
    delta_leader_ms: int
    lap_distance: float
    total_distance: float
    safety_car_delta: float
    position: int
    current_lap: int
    pit_status: int
    num_pit_stops: int
    sector: int
    lap_invalid: int
    penalties: int
    total_warnings: int
    corner_cutting_warnings: int
    grid_position: int
    driver_status: int
    result_status: int
    pit_lane_timer_active: int


def parse_lap_data(data: bytes) -> list[LapData]:
    cars = []
    off = HEADER_SIZE
    for _ in range(MAX_CARS):
        v = LAP_FMT.unpack_from(data, off)
        (last_ms, cur_ms,
         _s1ms, _s1min, _s2ms, _s2min,
         df_ms, df_min, dl_ms, dl_min,
         lap_dist, total_dist, sc_delta,
         pos, cur_lap, pit_status, num_stops, sector, invalid,
         penalties, warnings, cc_warnings,
         _dt_pens, _sg_pens, grid, drv_status, res_status,
         pit_timer_active, _pit_lane_ms, _pit_stop_ms, _serve_pen,
         _trap_speed, _trap_lap) = v
        cars.append(LapData(
            last_lap_ms=last_ms,
            current_lap_ms=cur_ms,
            delta_front_ms=df_min * 60000 + df_ms,
            delta_leader_ms=dl_min * 60000 + dl_ms,
            lap_distance=lap_dist,
            total_distance=total_dist,
            safety_car_delta=sc_delta,
            position=pos,
            current_lap=cur_lap,
            pit_status=pit_status,
            num_pit_stops=num_stops,
            sector=sector,
            lap_invalid=invalid,
            penalties=penalties,
            total_warnings=warnings,
            corner_cutting_warnings=cc_warnings,
            grid_position=grid,
            driver_status=drv_status,
            result_status=res_status,
            pit_lane_timer_active=pit_timer_active,
        ))
        off += LAP_FMT.size
    return cars


# --------------------------------------------------------- car telemetry

TELEMETRY_FMT = struct.Struct("<HfffBbHBBH4H4B4BH4f4B")  # 60


@dataclass
class Telemetry:
    speed: int
    throttle: float
    steer: float
    brake: float
    gear: int
    rpm: int
    drs: int
    brake_temp: tuple[int, ...]
    tyre_surface_temp: tuple[int, ...]
    tyre_inner_temp: tuple[int, ...]
    engine_temp: int
    tyre_pressure: tuple[float, ...]
    surface_type: tuple[int, ...]


def parse_telemetry(data: bytes, index: int) -> Telemetry:
    off = HEADER_SIZE + index * TELEMETRY_FMT.size
    v = TELEMETRY_FMT.unpack_from(data, off)
    (speed, throttle, steer, brake, _clutch, gear, rpm, drs, _rev_pct, _rev_bits,
     bt0, bt1, bt2, bt3,
     st0, st1, st2, st3,
     it0, it1, it2, it3,
     eng_temp,
     tp0, tp1, tp2, tp3,
     sf0, sf1, sf2, sf3) = v
    return Telemetry(
        speed=speed, throttle=throttle, steer=steer, brake=brake, gear=gear,
        rpm=rpm, drs=drs,
        brake_temp=(bt0, bt1, bt2, bt3),
        tyre_surface_temp=(st0, st1, st2, st3),
        tyre_inner_temp=(it0, it1, it2, it3),
        engine_temp=eng_temp,
        tyre_pressure=(tp0, tp1, tp2, tp3),
        surface_type=(sf0, sf1, sf2, sf3),
    )


# ------------------------------------------------------------ car status

STATUS_FMT = struct.Struct("<BBBBBfffHHBBHBBBbfffBfffB")  # 55


class Flag:
    NONE = 0
    GREEN = 1
    BLUE = 2
    YELLOW = 3
    RED = 4
    INVALID = -1


@dataclass
class CarStatus:
    fuel_mix: int
    pit_limiter: int
    fuel_in_tank: float
    fuel_capacity: float
    fuel_remaining_laps: float
    drs_allowed: int
    drs_activation_distance: int
    actual_tyre_compound: int
    visual_tyre_compound: int
    tyres_age_laps: int
    fia_flag: int
    ers_store: float
    ers_deploy_mode: int


def parse_car_status(data: bytes, index: int) -> CarStatus:
    off = HEADER_SIZE + index * STATUS_FMT.size
    v = STATUS_FMT.unpack_from(data, off)
    (_tc, _abs, fuel_mix, _brake_bias, limiter,
     fuel_tank, fuel_cap, fuel_laps,
     _max_rpm, _idle_rpm, _max_gears, drs_allowed, drs_dist,
     actual_tyre, visual_tyre, tyre_age, fia_flag,
     _ice, _mguk, ers_store, ers_mode,
     _h_mguk, _h_mguh, _deployed, _paused) = v
    return CarStatus(
        fuel_mix=fuel_mix, pit_limiter=limiter,
        fuel_in_tank=fuel_tank, fuel_capacity=fuel_cap,
        fuel_remaining_laps=fuel_laps,
        drs_allowed=drs_allowed, drs_activation_distance=drs_dist,
        actual_tyre_compound=actual_tyre, visual_tyre_compound=visual_tyre,
        tyres_age_laps=tyre_age, fia_flag=fia_flag,
        ers_store=ers_store, ers_deploy_mode=ers_mode,
    )


# ------------------------------------------------------------ car damage

# F1 25: 46 байт. Первые 24 (износ + damage шин + тормоза) стабильны,
# дальше 18 однобайтовых полей навесного и мотора, в конце - блистеры,
# добавленные в F1 25.
DAMAGE_FMT = struct.Struct("<4f4B4B" + "B" * 18 + "4B")  # 46


@dataclass
class CarDamage:
    tyre_wear: tuple[float, ...]
    tyre_damage: tuple[int, ...]
    front_left_wing: int
    front_right_wing: int
    rear_wing: int
    floor: int
    diffuser: int
    sidepod: int
    gearbox: int
    engine: int


def parse_car_damage(data: bytes, index: int) -> CarDamage:
    off = HEADER_SIZE + index * DAMAGE_FMT.size
    v = DAMAGE_FMT.unpack_from(data, off)
    (w0, w1, w2, w3,
     d0, d1, d2, d3,
     _b0, _b1, _b2, _b3,
     fl_wing, fr_wing, rear_wing, floor, diffuser, sidepod,
     _drs_fault, _ers_fault, gearbox, engine,
     _mguh, _es, _ce, _ice, _mguk, _tc, _blown, _seized,
     _bl0, _bl1, _bl2, _bl3) = v
    return CarDamage(
        tyre_wear=(w0, w1, w2, w3),
        tyre_damage=(d0, d1, d2, d3),
        front_left_wing=fl_wing, front_right_wing=fr_wing,
        rear_wing=rear_wing, floor=floor, diffuser=diffuser, sidepod=sidepod,
        gearbox=gearbox, engine=engine,
    )


# --------------------------------------------------------------- session

class SessionType:
    UNKNOWN = 0
    P1 = 1
    P2 = 2
    P3 = 3
    SHORT_P = 4
    Q1 = 5
    Q2 = 6
    Q3 = 7
    SHORT_Q = 8
    OSQ = 9
    RACE = 10
    RACE_2 = 11
    RACE_3 = 12
    TIME_TRIAL = 13


class SafetyCar:
    NONE = 0
    FULL = 1
    VIRTUAL = 2
    FORMATION_LAP = 3


class Weather:
    CLEAR = 0
    LIGHT_CLOUD = 1
    OVERCAST = 2
    LIGHT_RAIN = 3
    HEAVY_RAIN = 4
    STORM = 5


# Префикс Session-пакета. Он не менялся с F1 22, поэтому читаем его
# напрямую, не разбирая весь пакет целиком.
SESSION_PREFIX_FMT = struct.Struct("<BbbBHBbBHHBBBBBB")  # 19
MARSHAL_ZONE_FMT = struct.Struct("<fb")  # 5
NUM_MARSHAL_ZONES = 21
FORECAST_FMT = struct.Struct("<BBBbbbbB")  # 8


@dataclass
class ForecastSample:
    time_offset: int      # минут вперёд
    weather: int
    track_temp: int
    air_temp: int
    rain_percentage: int


@dataclass
class SessionInfo:
    weather: int
    track_temperature: int
    air_temperature: int
    total_laps: int
    track_length: int
    session_type: int
    track_id: int
    session_time_left: int
    session_duration: int
    pit_speed_limit: int
    safety_car_status: int
    network_game: int
    forecast: list[ForecastSample]


def parse_session(data: bytes) -> SessionInfo | None:
    off = HEADER_SIZE
    if len(data) < off + SESSION_PREFIX_FMT.size:
        return None
    (weather, track_t, air_t, total_laps, track_len, s_type, track_id,
     _formula, time_left, duration, pit_limit, _paused, _spectating,
     _spec_idx, _sli, num_zones) = SESSION_PREFIX_FMT.unpack_from(data, off)
    off += SESSION_PREFIX_FMT.size

    # Массив маршальских зон фиксированный, независимо от num_zones.
    off += MARSHAL_ZONE_FMT.size * NUM_MARSHAL_ZONES

    if len(data) < off + 2:
        return None
    safety_car = data[off]
    network = data[off + 1]
    off += 2

    forecast: list[ForecastSample] = []
    if len(data) > off:
        num_forecast = data[off]
        off += 1
        for i in range(min(num_forecast, 64)):
            if len(data) < off + FORECAST_FMT.size:
                break
            (_f_session, t_off, f_weather, f_track_t, _tc,
             f_air_t, _ac, rain_pct) = FORECAST_FMT.unpack_from(data, off)
            forecast.append(ForecastSample(
                time_offset=t_off, weather=f_weather,
                track_temp=f_track_t, air_temp=f_air_t,
                rain_percentage=rain_pct,
            ))
            off += FORECAST_FMT.size

    return SessionInfo(
        weather=weather, track_temperature=track_t, air_temperature=air_t,
        total_laps=total_laps, track_length=track_len, session_type=s_type,
        track_id=track_id, session_time_left=time_left,
        session_duration=duration, pit_speed_limit=pit_limit,
        safety_car_status=safety_car, network_game=network,
        forecast=forecast,
    )


# ----------------------------------------------------------------- event


@dataclass
class Event:
    code: str
    raw: bytes


def parse_event(data: bytes) -> Event | None:
    if len(data) < HEADER_SIZE + 4:
        return None
    code = data[HEADER_SIZE:HEADER_SIZE + 4].decode("ascii", errors="replace")
    return Event(code=code, raw=data[HEADER_SIZE + 4:])


# ------------------------------------------------------------ dispatcher


def parse_packet(data: bytes) -> tuple[Header, object] | None:
    """Разбирает пакет. Возвращает None, если пакет чужой или битый."""
    header = parse_header(data)
    if header is None:
        return None

    expected = EXPECTED_SIZE.get(header.packet_id)
    if expected is not None and len(data) != expected:
        # Не тот формат UDP (или другая игра) - молча пропускаем.
        return None

    pid = header.packet_id
    try:
        if pid == PacketId.MOTION:
            return header, parse_motion(data)
        if pid == PacketId.SESSION:
            return header, parse_session(data)
        if pid == PacketId.LAP_DATA:
            return header, parse_lap_data(data)
        if pid == PacketId.EVENT:
            return header, parse_event(data)
        if pid == PacketId.CAR_TELEMETRY:
            return header, parse_telemetry(data, header.player_car_index)
        if pid == PacketId.CAR_STATUS:
            return header, parse_car_status(data, header.player_car_index)
        if pid == PacketId.CAR_DAMAGE:
            return header, parse_car_damage(data, header.player_car_index)
    except struct.error:
        return None
    return None
