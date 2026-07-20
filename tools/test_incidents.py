"""Авария впереди, круговой, время до конца сессии."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from _fixtures import lap, motion_at, telemetry
from spotter.rules.clock import SessionClockRule
from spotter.rules.incidents import IncidentRule, LappedCarRule
from spotter.state import GameState
from spotter.udp.packets import SessionInfo, SessionType

fails = 0


def ok(cond, label, got=""):
    global fails
    fails += not cond
    print(f"  {'OK  ' if cond else 'FAIL'} {label}{'  -> ' + str(got) if got != '' else ''}")


def session(left=3600):
    return SessionInfo(weather=0, track_temperature=25, air_temperature=20,
                       total_laps=0, track_length=5000,
                       session_type=SessionType.RACE, track_id=0,
                       session_time_left=left, session_duration=3600,
                       pit_speed_limit=60, safety_car_status=0,
                       network_game=0, forecast=[])


def scene(rivals, my_speed=200, my_dist=1000.0, my_lap=5):
    """rivals: (дистанция впереди, скорость, круг)."""
    st = GameState(sim="lmu")
    st.player_index = 0
    st.session = session()
    me = lap(position=3, current_lap=my_lap)
    me.lap_distance = my_dist
    st.laps = [me]
    st.car_speeds = [float(my_speed)]
    st.motion = [motion_at(0, 0)]
    st.telemetry = telemetry(my_speed)
    for ahead, spd, lp in rivals:
        r = lap(position=4, current_lap=lp)
        r.lap_distance = my_dist + ahead
        st.laps.append(r)
        st.car_speeds.append(float(spd))
        st.motion.append(motion_at(0, 0))
    return st


print("АВАРИЯ ВПЕРЕДИ")
print("-" * 58)

r = IncidentRule()
said = []
r.update(scene([(150.0, 5, 5)]), lambda *i, **k: said.extend(i))
ok(said == ["incident_ahead"], "машина стоит в 150 м впереди", said)

r = IncidentRule()
said = []
r.update(scene([(150.0, 200, 5)]), lambda *i, **k: said.extend(i))
ok(said == [], "машина едет нормально -> молчит", said)

r = IncidentRule()
said = []
r.update(scene([(100.0, 120, 5)]), lambda *i, **k: said.extend(i))
ok(said == ["slow_car_ahead"], "медленная (120 против 200) в 100 м", said)

r = IncidentRule()
said = []
r.update(scene([(800.0, 5, 5)]), lambda *i, **k: said.extend(i))
ok(said == [], "авария за 800 м -> ещё далеко, молчит", said)

r = IncidentRule()
said = []
r.update(scene([(-100.0, 5, 5)]), lambda *i, **k: said.extend(i))
ok(said == [], "авария позади -> молчит", said)

# стоящий в боксе не авария
st = scene([(150.0, 5, 5)])
st.laps[1].pit_status = 1
r = IncidentRule()
said = []
r.update(st, lambda *i, **k: said.extend(i))
ok(said == [], "стоит в боксе -> не авария", said)

# сами еле едем (за сейфти-каром) - не паникуем
r = IncidentRule()
said = []
r.update(scene([(150.0, 5, 5)], my_speed=40), lambda *i, **k: said.extend(i))
ok(said == [], "мы сами медленно -> молчит", said)

print()
print("КРУГОВОЙ ВПЕРЕДИ")
print("-" * 58)

r = LappedCarRule()
said = []
r.update(scene([(80.0, 190, 3)], my_lap=5), lambda *i, **k: said.extend(i))
ok(said == ["lapped_car_ahead"], "отстал на 2 круга, в 80 м впереди", said)

r = LappedCarRule()
said = []
r.update(scene([(80.0, 190, 5)], my_lap=5), lambda *i, **k: said.extend(i))
ok(said == [], "тот же круг -> не круговой", said)

r = LappedCarRule()
said = []
r.update(scene([(300.0, 190, 3)], my_lap=5), lambda *i, **k: said.extend(i))
ok(said == [], "круговой далеко -> молчит", said)

print()
print("ВРЕМЯ ДО КОНЦА")
print("-" * 58)

def clock_at(seconds):
    st = GameState(sim="lmu")
    st.player_index = 0
    st.session = session(left=seconds)
    st.laps = [lap()]
    return st

r = SessionClockRule()
said = []
r.update(clock_at(3600), lambda *i, **k: said.extend(i))
ok(said == ["hour_to_go"], "остался час", said)

r = SessionClockRule()
said = []
r.update(clock_at(20 * 60), lambda *i, **k: said.extend(i))
ok(said and said[0] == "time_left", "20 минут -> до конца осталось", said)

r = SessionClockRule()
said = []
r.update(clock_at(45 * 60), lambda *i, **k: said.extend(i))
ok(said == [], "45 минут - не отметка, молчит", said)

# одна отметка - один раз
r = SessionClockRule()
said = []
r.update(clock_at(10 * 60), lambda *i, **k: said.extend(i))
r.update(clock_at(10 * 60 - 5), lambda *i, **k: said.extend(i))
ok(said.count("time_left") == 1, "отметка звучит один раз", said)

print()
print("-" * 58)
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
