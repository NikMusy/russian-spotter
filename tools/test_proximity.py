"""Проверка геометрии споттера на синтетических позициях."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from spotter.rules.proximity import ProximityRule, BOTH, CLEAR, LEFT, RIGHT
from spotter.state import GameState
from spotter.udp.packets import CarMotion, LapData, Telemetry

CAR_LENGTH = 5.6


def motion_at(x: float, z: float) -> CarMotion:
    # Машина смотрит вдоль +Z, право - вдоль +X.
    return CarMotion(x=x, y=0.0, z=z, fwd_x=0.0, fwd_z=1.0,
                     right_x=1.0, right_z=0.0, yaw=0.0)


def lap(pit: int = 0, status: int = 4, result: int = 2) -> LapData:
    return LapData(
        last_lap_ms=0, current_lap_ms=0, delta_front_ms=0, delta_leader_ms=0,
        lap_distance=0.0, total_distance=0.0, safety_car_delta=0.0,
        position=1, current_lap=1, pit_status=pit, num_pit_stops=0, sector=0,
        lap_invalid=0, penalties=0, total_warnings=0, corner_cutting_warnings=0,
        num_unserved_drive_through=0, num_unserved_stop_go=0,
        grid_position=1, driver_status=status, result_status=result,
        pit_lane_timer_active=0,
    )


def telemetry(speed: int) -> Telemetry:
    return Telemetry(speed=speed, throttle=1.0, steer=0.0, brake=0.0, gear=5,
                     rpm=10000, drs=0, brake_temp=(0,) * 4,
                     tyre_surface_temp=(90,) * 4, tyre_inner_temp=(90,) * 4,
                     engine_temp=90, tyre_pressure=(23.0,) * 4,
                     surface_type=(0,) * 4)


def make_state(rivals: list[tuple[float, float]], speed: int = 200,
               pit: int = 0) -> GameState:
    st = GameState()
    st.player_index = 0
    st.motion = [motion_at(0.0, 0.0)] + [motion_at(x, z) for x, z in rivals]
    st.laps = [lap(pit=pit)] + [lap() for _ in rivals]
    st.telemetry = telemetry(speed)
    return st


def detect(rivals, **kw) -> str:
    return ProximityRule()._detect(make_state(rivals, **kw))


CASES = [
    # описание, соперники (x=поперёк, z=вдоль), ожидание
    ("никого рядом",                 [],                    CLEAR),
    ("справа вплотную",              [(3.0, 0.0)],          RIGHT),
    ("слева вплотную",               [(-3.0, 0.0)],         LEFT),
    ("с двух сторон",                [(3.0, 0.0), (-3.0, 0.0)], BOTH),
    ("справа, слегка впереди",       [(3.0, 3.5)],          RIGHT),
    ("слева, слегка сзади",          [(-3.0, -3.5)],        LEFT),
    ("далеко впереди - не считается", [(3.0, 30.0)],        CLEAR),
    ("далеко сзади - не считается",  [(3.0, -30.0)],        CLEAR),
    ("оторвался вперёд на 10 м",     [(3.0, 10.0)],         CLEAR),
    ("другой ряд, 12 м вбок",        [(12.0, 0.0)],         CLEAR),
    ("через ряд, 8 м вбок",          [(8.0, 0.0)],          CLEAR),
    ("наложение, 0.5 м - игнор",     [(0.5, 0.0)],          CLEAR),
    ("на границе 5.5 м вбок",        [(5.5, 0.0)],          RIGHT),
    ("сзади-сбоку в 6 м (ранняя)",   [(3.0, -6.0)],         RIGHT),
    ("подъезжает сзади в 7 м",       [(2.5, -7.0)],         RIGHT),
    ("мусор в координатах соперника", [(1e200, 0.0)],       CLEAR),
    ("медленно - споттер молчит",    [(3.0, 0.0)],          CLEAR),
    ("игрок в пит-лейн - молчит",    [(3.0, 0.0)],          CLEAR),
]

print("ГЕОМЕТРИЯ")
print("-" * 58)
fails = 0
for i, (name, rivals, want) in enumerate(CASES):
    kw = {}
    if name.startswith("медленно"):
        kw["speed"] = 20
    if name.startswith("игрок в пит"):
        kw["pit"] = 1
    got = detect(rivals, **kw)
    ok = got == want
    fails += not ok
    print(f"  {'OK ' if ok else 'FAIL'} {name:<32} {got:<6} (ждали {want})")

# ------------------------------------------------------------------ повороты
print()
print("МАШИНА ПОВЁРНУТА НА 90 ГРАДУСОВ (едет вдоль +X)")
print("-" * 58)
st = GameState()
st.player_index = 0
me = CarMotion(x=0, y=0, z=0, fwd_x=1.0, fwd_z=0.0, right_x=0.0, right_z=-1.0, yaw=0.0)
# right = (0,-1): соперник на z=-3 должен быть СПРАВА
rival = CarMotion(x=0, y=0, z=-3.0, fwd_x=1.0, fwd_z=0.0, right_x=0.0, right_z=-1.0, yaw=0.0)
st.motion = [me, rival]
st.laps = [lap(), lap()]
st.telemetry = telemetry(200)
got = ProximityRule()._detect(st)
ok = got == RIGHT
fails += not ok
print(f"  {'OK ' if ok else 'FAIL'} {'повёрнут, соперник справа':<32} {got:<6} (ждали {RIGHT})")

# ------------------------------------------------------------- поведение
print()
print("ПОВЕДЕНИЕ (гистерезис, объявления)")
print("-" * 58)

said: list[str] = []
rule = ProximityRule()


def say(pid, **kw):
    said.append(pid)


# соперник появляется справа
rule.update(make_state([(3.0, 0.0)]), say)
ok = len(said) == 1 and said[0].startswith("car_right")
fails += not ok
print(f"  {'OK ' if ok else 'FAIL'} появился справа -> сказал {said}")

# он всё ещё там, но повторно не орём
said.clear()
rule.update(make_state([(3.0, 0.0)]), say)
ok = said == []
fails += not ok
print(f"  {'OK ' if ok else 'FAIL'} всё ещё справа -> молчит {said}")

# уехал: "чисто" не сразу, а после задержки
said.clear()
rule.update(make_state([]), say)
ok = said == []
fails += not ok
print(f"  {'OK ' if ok else 'FAIL'} только пропал -> ещё молчит {said}")

time.sleep(0.8)
rule.update(make_state([]), say)
ok = len(said) == 1 and said[0].startswith("clear")
fails += not ok
print(f"  {'OK ' if ok else 'FAIL'} через 0.8 сек -> сказал {said}")

# "чисто" не говорим, если ничего и не было
said.clear()
fresh = ProximityRule()
fresh.update(make_state([]), say)
time.sleep(0.8)
fresh.update(make_state([]), say)
ok = said == []
fails += not ok
print(f"  {'OK ' if ok else 'FAIL'} чисто с самого начала -> молчит {said}")

# Битый кадр не должен рвать "справа" на "чисто" и обратно
said.clear()
flap = ProximityRule()
flap.update(make_state([(3.0, 0.0)]), say)          # появился справа
said.clear()
flap.update(make_state([]), say)                    # кадр моргнул
flap.update(make_state([(3.0, 0.0)]), say)          # и снова тут
ok = said == []
fails += not ok
print(f"  {'OK ' if ok else 'FAIL'} моргнул один кадр -> не тараторит {said}")

print()
print("-" * 58)
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
