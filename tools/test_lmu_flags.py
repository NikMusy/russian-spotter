"""Флаги LMU и отвалившееся колесо.

Структуры собираем прямо в памяти, без разделяемого блока - поэтому тест
не конфликтует с запущенной игрой.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spotter.sims import lmu_structs as S
from spotter.sims.lmu import LMUAdapter
from spotter.udp.packets import Flag

fails = 0
a = LMUAdapter()


def veh(sector=1, flag=0, under_yellow=False):
    v = S.VehicleScoringInfoV01()
    v.mSector = sector
    v.mFlag = flag
    v.mUnderYellow = under_yellow
    return v


def scoring(phase=S.GamePhase.GREEN, yellow_state=0, sector_flags=(0, 0, 0)):
    s = S.ScoringInfoV01()
    s.mGamePhase = phase
    s.mYellowFlagState = yellow_state
    for i, f in enumerate(sector_flags):
        s.mSectorFlag[i] = f
    return s


print("ФЛАГИ LMU")
print("-" * 58)
CASES = [
    ("чисто -> зелёный", veh(), scoring(), Flag.GREEN),
    ("синий флаг", veh(flag=S.VehFlag.BLUE), scoring(), Flag.BLUE),
    ("жёлтый в СЕКТОРЕ игрока (mSector=1)",
     veh(sector=1), scoring(sector_flags=(0, 1, 0)), Flag.YELLOW),
    ("жёлтый в ДРУГОМ секторе - нам зелёный",
     veh(sector=1), scoring(sector_flags=(1, 0, 0)), Flag.GREEN),
    ("полная жёлтая (mUnderYellow)",
     veh(under_yellow=True), scoring(), Flag.YELLOW),
    ("жёлтая в scoring.mYellowFlagState",
     veh(), scoring(yellow_state=S.YellowState.PENDING), Flag.YELLOW),
    ("сессия остановлена -> красный",
     veh(), scoring(phase=S.GamePhase.STOPPED), Flag.RED),
    ("синий важнее жёлтого в секторе",
     veh(sector=1, flag=S.VehFlag.BLUE), scoring(sector_flags=(0, 1, 0)),
     Flag.BLUE),
]
for name, v, s, want in CASES:
    got = a._flag(v, s)
    ok = got == want
    fails += not ok
    names = {0: "зелёный", 2: "синий", 3: "жёлтый", 4: "красный"}
    print(f"  {'OK  ' if ok else 'FAIL'} {name:<40} -> {names.get(got, got)}")

print()
print("ОТВАЛИВШЕЕСЯ КОЛЕСО (правило)")
print("-" * 58)
from spotter.rules.car import DamageRule
from spotter.state import GameState
from spotter.udp.packets import CarDamage

st = GameState(sim="lmu")
st.laps = []
st.damage = CarDamage(tyre_wear=(0,) * 4, tyre_damage=(0,) * 4,
                      front_left_wing=0, front_right_wing=0, rear_wing=0,
                      floor=0, diffuser=0, sidepod=0, gearbox=0, engine=0)
# on_track нужен, подсунем минимальный lap
from _fixtures import lap
st.laps = [lap()]
st.player_index = 0

r = DamageRule()
said = []
r.update(st, lambda *ids, **kw: said.extend(ids))
ok = "wheel_lost" not in said
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} колёса целы -> молчит про колесо")

said.clear()
st.wheels_detached = (True, False, False, False)
r.update(st, lambda *ids, **kw: said.extend(ids))
ok = said == ["wheel_lost"]
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} колесо отвалилось -> {said}")

said.clear()
r.update(st, lambda *ids, **kw: said.extend(ids))
ok = said == []
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} то же колесо -> не повторяет {said}")

said.clear()
r2 = DamageRule()
r2.update(st, lambda *i, **k: None)          # первый кадр запоминает
st.rival_lost_wheel_ahead = True
r2.update(st, lambda *ids, **kw: said.extend(ids))
ok = "rival_wheel_off" in said
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} у соперника впереди -> {said}")

print()
print("КВАЛИФИКАЦИЯ LMU - СОПЕРНИКИ ПРИЗРАКИ")
print("-" * 58)
from spotter.rules.proximity import ProximityRule
from spotter.udp.packets import SessionInfo, SessionType


def make_session(stype):
    return SessionInfo(weather=0, track_temperature=25, air_temperature=20,
                       total_laps=10, track_length=5000, session_type=stype,
                       track_id=0, session_time_left=600, session_duration=600,
                       pit_speed_limit=80, safety_car_status=0, network_game=0,
                       forecast=[])


from _fixtures import motion_at, telemetry

for stype, sim, want_silent, label in [
    (SessionType.Q2, "lmu", True, "квала LMU -> молчит"),
    (SessionType.RACE, "lmu", False, "гонка LMU -> спотит"),
    (SessionType.Q2, "f1", False, "квала F1 -> спотит (там машины реальны)"),
]:
    st = GameState(sim=sim)
    st.session = make_session(stype)
    st.player_index = 0
    st.motion = [motion_at(0, 0), motion_at(3.0, 0)]
    st.laps = [lap(), lap()]
    st.telemetry = telemetry(200)
    got = ProximityRule()._detect(st)
    silent = got == "clear"
    ok = silent == want_silent
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {label:<42} -> {got}")

print()
print("СЛИПСТРИМ vs DRS")
print("-" * 58)
from spotter.rules.race import GapRule


def gap_state(sim, gap_sec):
    st = GameState(sim=sim)
    st.session = make_session(SessionType.RACE)
    st.player_index = 0
    me = lap(position=3, current_lap=5)
    me.delta_front_ms = int(gap_sec * 1000)
    st.laps = [me]
    st.motion = [motion_at(0, 0)]
    st.telemetry = telemetry(250)
    return st


SLIP = {"in_slipstream", "in_slipstream_close", "in_drs_range"}
CASES = [
    ("f1", 0.8, "in_drs_range", "F1, отрыв 0.8 -> зона DRS"),
    ("lmu", 0.6, "in_slipstream", "LMU, отрыв 0.6 -> слипстрим"),
    ("lmu", 0.3, "in_slipstream_close", "LMU, отрыв 0.3 -> плотно в мешке"),
    ("lmu", 1.2, "gap_ahead", "LMU, отрыв 1.2 -> далеко, называет отрыв"),
    ("f1", 0.6, "in_drs_range", "F1 не говорит про слипстрим"),
]
for sim, g, want, label in CASES:
    said = []
    GapRule().update(gap_state(sim, g), lambda *ids, **kw: said.extend(ids))
    got = said[0] if said else None
    ok = got == want
    # на далёком отрыве не должно быть слипстрим-фраз вообще
    if g > 1.0:
        ok = ok and not (SLIP & set(said))
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {label:<42} -> {got}")

# слипстрим-фразы не предлагаются F1, DRS - не предлагается LMU
from spotter.audio.phrases import BY_ID, SIM_F1, SIM_LMU
ok = not BY_ID["in_slipstream"].for_sim(SIM_F1)
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} слипстрим не в плане F1")
ok = not BY_ID["in_drs_range"].for_sim(SIM_LMU)
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} DRS не в плане LMU")

print()
print("-" * 58)
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
