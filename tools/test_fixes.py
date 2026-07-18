"""Проверка багфиксов: класс-позиция, ночь, ремонт, преследователь."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from _fixtures import lap, motion_at, telemetry
from spotter.state import GameState
from spotter.udp.packets import (CarDamage, SessionInfo, SessionType)

fails = 0


def ok(cond, label, got=""):
    global fails
    fails += not cond
    print(f"  {'OK  ' if cond else 'FAIL'} {label}{'  -> ' + str(got) if got != '' else ''}")


def session(stype=SessionType.RACE):
    return SessionInfo(weather=0, track_temperature=25, air_temperature=20,
                       total_laps=30, track_length=13600, session_type=stype,
                       track_id=0, session_time_left=600, session_duration=600,
                       pit_speed_limit=60, safety_car_status=0, network_game=0,
                       forecast=[])


print("КЛАСС-ПОЗИЦИЯ В МУЛЬТИКЛАССЕ")
print("-" * 58)
# 5 машин: игрок GT3 15-й общий, но в GT3 впереди только один GT3 (8-й)
st = GameState(sim="lmu")
st.player_index = 0
st.session = session()
st.laps = [lap(position=15, current_lap=5)]      # игрок
st.car_classes = ["GT3"]
for pos, cls in [(1, "Hyper"), (2, "Hyper"), (8, "GT3"), (20, "GT3")]:
    st.laps.append(lap(position=pos, current_lap=5))
    st.car_classes.append(cls)
ok(st.is_multiclass, "мультикласс распознан")
ok(st.my_class_position == 2, "игрок 15-й общий -> 2-й в GT3",
   st.my_class_position)

# одноклассовая гонка: класс-позиция = общая
st2 = GameState(sim="f1")
st2.player_index = 0
st2.session = session()
st2.laps = [lap(position=7, current_lap=5)]
st2.car_classes = ["", ""]
st2.laps.append(lap(position=3, current_lap=5))
ok(not st2.is_multiclass, "F1 - не мультикласс")
ok(st2.my_class_position == 7, "одноклассовая -> общая позиция",
   st2.my_class_position)

print()
print("РЕМОНТ СБРАСЫВАЕТ ДОКЛАД О ПОВРЕЖДЕНИЯХ")
print("-" * 58)
from spotter.rules.car import DamageRule

def dmg(front=0):
    return CarDamage(tyre_wear=(0,)*4, tyre_damage=(0,)*4,
                     front_left_wing=front, front_right_wing=front,
                     rear_wing=0, floor=0, diffuser=0, sidepod=0,
                     gearbox=0, engine=0)

def st_dmg(front=0, in_pits=False):
    s = GameState(sim="lmu")
    s.player_index = 0
    s.laps = [lap(pit=1 if in_pits else 0)]
    s.damage = dmg(front)
    return s

r = DamageRule()
said = []
r.update(st_dmg(front=70), lambda *i, **k: said.extend(i))
ok("damage_front_wing_bad" in said, "крыло разбито -> доклад", said)

said.clear()
r.update(st_dmg(front=70), lambda *i, **k: said.extend(i))
ok(said == [], "то же крыло -> молчит", said)

said.clear()
r.update(st_dmg(front=0, in_pits=True), lambda *i, **k: said.extend(i))   # заезд в бокс
r.update(st_dmg(front=70, in_pits=False), lambda *i, **k: said.extend(i)) # выехал, снова бьём
ok("damage_front_wing_bad" in said, "после ремонта новая поломка -> снова доклад",
   said)

print()
print("НОЧЬ И ФАРЫ")
print("-" * 58)
from spotter.rules.night import NightRule

def st_night(tod, lights=False):
    s = GameState(sim="lmu")
    s.player_index = 0
    s.laps = [lap()]
    s.time_of_day = tod
    s.headlights_on = lights
    return s

r = NightRule()
said = []
r.update(st_night(22 * 3600, lights=False), lambda *i, **k: said.extend(i))
ok(said == ["headlights_on"], "ночь, фары выкл -> включи фары", said)

r = NightRule()
said = []
r.update(st_night(22 * 3600, lights=True), lambda *i, **k: said.extend(i))
ok(said == [], "ночь, фары вкл -> молчит", said)

r = NightRule()
said = []
r.update(st_night(14 * 3600), lambda *i, **k: said.extend(i))
ok(said == [], "день -> молчит", said)

r = NightRule()
said = []
r.update(st_night(-1), lambda *i, **k: said.extend(i))
ok(said == [], "нет данных о времени (F1) -> молчит", said)

r = NightRule()
said = []
r.update(st_night(19 * 3600 + 1800, lights=True), lambda *i, **k: said.extend(i))
ok(said == ["night_falling"], "закат, фары вкл -> темнеет", said)

print()
print("ПРЕСЛЕДОВАТЕЛЬ СЗАДИ (LMU)")
print("-" * 58)
from spotter.rules.race import GapRule

def st_behind(behind, pos=5):
    s = GameState(sim="lmu")
    s.player_index = 0
    s.session = session()
    me = lap(position=pos, current_lap=5)
    me.delta_front_ms = 8000       # впереди далеко, чтобы не мешал
    s.laps = [me]
    s.gap_behind_sec = behind
    s.telemetry = telemetry(200)
    s.motion = [motion_at(0, 0)]
    return s

r = GapRule()
said = []
r.update(st_behind(1.5), lambda *i, **k: said.extend(i))
ok(said and said[0] == "gap_behind", "преследователь в 1.5с -> предупреждение",
   said)

r = GapRule()
said = []
r.update(st_behind(3.0), lambda *i, **k: said.extend(i))
ok("gap_behind" not in said, "преследователь далеко (3с) -> не про него", said)

r = GapRule()
said = []
r.update(st_behind(1.5, pos=1), lambda *i, **k: said.extend(i))
ok("gap_behind" not in said, "лидер -> сзади не важно", said)

print()
print("НЕВАЛИДНЫЙ КРУГ НЕ ИДЁТ В РЕКОРД")
print("-" * 58)
from spotter.rules.race import LapRule

r = LapRule()
s = GameState(sim="lmu")
s.player_index = 0
s.session = session()
# прогрев: первый круг LapRule пропускает (защита от старта)
s.laps = [lap(position=3, current_lap=1)]
r.update(s, lambda *i, **k: None)
# круг 2 закрыт чистым временем 100с
s.laps = [lap(position=3, current_lap=2)]
s.laps[0].last_lap_ms = 100000
s.laps[0].lap_invalid = 0
r.update(s, lambda *i, **k: None)
# круг 3 быстрее (90с), но невалидный
s.laps = [lap(position=3, current_lap=3)]
s.laps[0].last_lap_ms = 90000
s.laps[0].lap_invalid = 1
r.update(s, lambda *i, **k: None)
ok(r.best_ms == 100000, "срезанный быстрый круг не стал рекордом", r.best_ms)

print()
print("ЭНЕРГИЯ ГИБРИДА (WEC)")
print("-" * 58)
from spotter.rules.energy import EnergyRule

def st_energy(ve, in_pits=False):
    s = GameState(sim="lmu")
    s.player_index = 0
    s.session = session()
    s.laps = [lap(position=3, current_lap=5, pit=1 if in_pits else 0)]
    s.virtual_energy = ve
    return s

r = EnergyRule()
said = []
r.update(st_energy(0.5), lambda *i, **k: said.extend(i))
ok(said == [], "энергии половина -> молчит", said)

r = EnergyRule()
said = []
r.update(st_energy(0.15), lambda *i, **k: said.extend(i))
ok("energy_low" in said, "энергия 15% -> экономь", said)

r = EnergyRule()
said = []
r.update(st_energy(0.05), lambda *i, **k: said.extend(i))
ok(said == ["energy_critical"], "энергия 5% -> в обрез", said)

r = EnergyRule()
said = []
r.update(st_energy(-1.0), lambda *i, **k: said.extend(i))
ok(said == [], "нет данных (не гиперкар/не LMU) -> молчит", said)

# после пита энергия восполнена - предупреждаем заново
r = EnergyRule()
r.update(st_energy(0.05), lambda *i, **k: None)          # предупредил
r.update(st_energy(0.9, in_pits=True), lambda *i, **k: None)  # пит
said = []
r.update(st_energy(0.05), lambda *i, **k: said.extend(i))
ok("energy_critical" in said, "новый стинт -> предупреждает заново", said)

print()
print("-" * 58)
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
