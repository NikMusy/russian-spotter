"""Статистика заездов и озвучка штрафов."""

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from _fixtures import lap, telemetry
from spotter import history
from spotter.audio.phrases import BY_ID
from spotter.rules.events import PenaltyRule, EventRule
from spotter.sims import tracks
from spotter.state import GameState
from spotter.udp.packets import SessionInfo, SessionType

fails = 0
TMP = Path(tempfile.mkdtemp(prefix="hist_"))
PATH = TMP / "history.json"


def session(stype=SessionType.RACE, track_id=0):
    return SessionInfo(
        weather=0, track_temperature=25, air_temperature=20, total_laps=10,
        track_length=5000, session_type=stype, track_id=track_id,
        session_time_left=600, session_duration=600, pit_speed_limit=80,
        safety_car_status=0, network_game=0, forecast=[])


def state_at(stype, track_name="", track_id=0, pos=5, grid=8, lap_num=3,
             last_ms=0, invalid=0):
    st = GameState(sim="lmu")
    st.session = session(stype, track_id)
    st.track_name = track_name
    st.laps = [lap(position=pos, current_lap=lap_num)]
    st.laps[0].grid_position = grid
    st.laps[0].last_lap_ms = last_ms
    st.laps[0].lap_invalid = invalid
    st.telemetry = telemetry(200)
    st.car_classes = ["Hyper"]
    return st


print("ЗАПИСЬ ЗАЕЗДА")
print("-" * 62)

t = history.SessionTracker()
st = state_at(SessionType.RACE, "Circuit de la Sarthe", pos=3, grid=8,
              lap_num=5, last_ms=212345)
done = t.update(st)
ok = done is None
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} первая сессия - закрывать нечего")

cur = t.current
ok = cur is not None and cur.track == "track_lemans"
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} трасса опознана: {cur.track}")
ok = cur.grid == 8 and cur.finish == 3
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} старт P{cur.grid} -> финиш P{cur.finish}")
ok = cur.gained == 5
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} отыграно мест: {cur.gained:+d} (ждём +5)")
ok = cur.best_lap == "3:32.345"
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} лучший круг: {cur.best_lap}")
ok = cur.flag == "🇫🇷" and cur.track_title == "Ле-Ман"
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} флаг и название: {cur.flag} {cur.track_title}")

# Битый круг в лучшие не идёт
t.update(state_at(SessionType.RACE, "Circuit de la Sarthe", pos=3, grid=8,
                  lap_num=6, last_ms=100000, invalid=1))
ok = t.current.best_lap_ms == 212345
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} незасчитанный круг не стал лучшим")

# Смена сессии закрывает предыдущую
done = t.update(state_at(SessionType.Q2, "Autodromo Nazionale Monza",
                         pos=2, grid=0, lap_num=4))
ok = done is not None and done.track == "track_lemans" and done.is_race
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} смена сессии закрыла гонку на Ле-Мане")
ok = t.current.track == "track_monza" and not t.current.is_race
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} началась квала на Монце")

# Пустой заход не сохраняем
t2 = history.SessionTracker()
t2.update(state_at(SessionType.RACE, "Fuji Speedway", pos=0, lap_num=0))
ok = t2.finish() is None
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} заход в меню без кругов не сохраняется")

# --- файл
print()
print("ФАЙЛ ИСТОРИИ")
print("-" * 62)
ok = history.load(PATH) == []
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} нет файла -> пустой список")

history.append(PATH, done)
entries = history.load(PATH)
ok = len(entries) == 1 and entries[0].track == "track_lemans"
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} запись сохранилась и читается")

e = entries[0]
ok = e.flag == "🇫🇷" and e.sim_title.startswith("Le Mans")
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} после чтения: {e.flag} {e.track_title}, "
      f"{e.sim_title}, {e.session_title}")

PATH.write_text("{битый json", encoding="utf-8")
ok = history.load(PATH) == []
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} битый файл не роняет программу")

# Лимит
PATH.unlink()
for i in range(12):
    history.append(PATH, history.Entry(date="2026-07-17T12:00:00",
                                       track="track_spa", laps=5, finish=1),
                   limit=10)
ok = len(history.load(PATH)) == 10
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} старые записи вытесняются (лимит 10)")

# --- флаги для всех трасс
print()
print("ФЛАГИ ТРАСС")
print("-" * 62)
missing = [p for p in set(tracks.F1_TRACKS.values()) | {p for _, p in tracks.NAME_MATCH}
           if p not in tracks.TRACK_INFO]
ok = not missing
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} у всех трасс есть флаг "
      f"{missing if missing else ''}")
for pid in ("track_lemans", "track_monza", "track_interlagos", "track_qatar",
            "track_unknown"):
    print(f"       {tracks.flag(pid)}  {tracks.title(pid)}")

# --- штрафы
print()
print("ШТРАФЫ")
print("-" * 62)

said = []
pen = PenaltyRule()
st = state_at(SessionType.RACE)
pen.update(st, lambda *ids, **kw: said.extend(ids))
ok = said == []
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} первый кадр молчит {said}")

# Событие F1 с типом штрафа
for ptype, want in ((0, "penalty_drive_through"), (1, "penalty_stop_go"),
                    (4, "penalty_5s"), (6, "warning_track_limits")):
    said.clear()
    p = PenaltyRule()
    p.on_penalty(ptype, lambda *ids, **kw: said.extend(ids))
    ok = said == [want]
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} тип {ptype} -> {said}")

# Неотбытый штраф напоминает
said.clear()
p = PenaltyRule()
st = state_at(SessionType.RACE)
p.update(st, lambda *i, **k: None)
st.laps[0].num_unserved_stop_go = 1
p.update(st, lambda *ids, **kw: said.extend(ids))
ok = "penalty_stop_go" in said and "serve_penalty_now" in said
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} висит стоп-энд-гоу -> {said}")

# Отбыл - сказали
said.clear()
st.laps[0].num_unserved_stop_go = 0
p.update(st, lambda *ids, **kw: said.extend(ids))
ok = said == ["penalty_served"]
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} отбыл штраф -> {said}")

# Все фразы существуют
need = ["penalty_stop_go", "penalty_stop_go_10", "penalty_drive_through",
        "serve_penalty_now", "penalty_pending", "penalty_served",
        "penalty_speeding", "penalty_10s"]
missing = [p for p in need if p not in BY_ID]
ok = not missing
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} фразы штрафов в банке {missing or ''}")
hard = [p for p in need if BY_ID[p].hard]
print(f"       с матом: {len(hard)} из {len(need)}")

shutil.rmtree(TMP, ignore_errors=True)
print()
print("-" * 62)
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
