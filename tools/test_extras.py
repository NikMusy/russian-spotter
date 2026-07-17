"""Трассы, тип сессии, классы машин и мемы."""

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spotter.audio.phrases import BY_ID, MEME_FOR
from spotter.audio.player import Player
from spotter.audio.radio import RadioConfig
from spotter.audio.recording import SAMPLE_RATE, save_wav
from spotter.rules.classes import ClassTrafficRule, classify
from spotter.rules.track import TrackAnnounceRule
from spotter.sims import tracks
from spotter.state import GameState
from spotter.udp.packets import SessionInfo, SessionType

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _fixtures import lap, motion_at, telemetry  # noqa: E402

fails = 0

# ----------------------------------------------------------- трассы
print("ОПОЗНАНИЕ ТРАСС")
print("-" * 62)
CASES = [
    ("Circuit de la Sarthe", "track_lemans"),
    ("LE MANS 24H", "track_lemans"),
    ("Sebring International Raceway", "track_sebring"),
    ("Autodromo Nazionale Monza", "track_monza"),
    ("Circuit de Spa-Francorchamps", "track_spa"),
    ("Fuji Speedway", "track_fuji"),
    ("Bahrain International Circuit", "track_bahrain"),
    ("Autodromo Enzo e Dino Ferrari", "track_imola"),
    ("Autódromo José Carlos Pace", "track_interlagos"),
    ("Circuit of the Americas", "track_cota"),
    ("Losail International Circuit", "track_qatar"),
    ("Autódromo Internacional do Algarve", "track_portimao"),
    ("Nürburgring Nordschleife", "track_nurburgring"),
    ("Какая-то неизвестная трасса", "track_unknown"),
    ("", "track_unknown"),
]
for name, want in CASES:
    got = tracks.by_name(name)
    ok = got == want
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {name[:38]:<38} -> {got}")

print()
print("  F1 по id:")
for tid, want in ((5, "track_monaco"), (10, "track_spa"), (11, "track_monza"),
                  (32, "track_qatar"), (99, "track_unknown")):
    got = tracks.by_f1_id(tid)
    ok = got == want
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} id {tid:<3} -> {got}")

# все id ведут на существующие фразы
missing = [p for p in set(tracks.F1_TRACKS.values()) if p not in BY_ID]
missing += [p for _, p in tracks.NAME_MATCH if p not in BY_ID]
ok = not missing
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} все трассы есть в банке фраз "
      f"{missing if missing else ''}")

# ------------------------------------------------- объявление сессии
print()
print("ОБЪЯВЛЕНИЕ СЕССИИ")
print("-" * 62)


def make_session(stype, track_id=0):
    return SessionInfo(
        weather=0, track_temperature=25, air_temperature=20, total_laps=10,
        track_length=5000, session_type=stype, track_id=track_id,
        session_time_left=600, session_duration=600, pit_speed_limit=80,
        safety_car_status=0, network_game=0, forecast=[])


def run_track(stype, track_name="", track_id=0):
    said = []
    st = GameState()
    st.session = make_session(stype, track_id)
    st.track_name = track_name
    r = TrackAnnounceRule()
    r.update(st, lambda *ids, **kw: said.extend(ids))
    # второй раз - молчит
    r.update(st, lambda *ids, **kw: said.append("ПОВТОР"))
    return said


got = run_track(SessionType.RACE, "Circuit de la Sarthe")
ok = got[:3] == ["welcome_to", "track_lemans", "session_race"] and "good_luck" in got
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} LMU гонка -> {got}")

got = run_track(SessionType.Q2, track_id=11)
ok = got[:3] == ["welcome_to", "track_monza", "session_qualifying"] \
    and "quali_push" in got
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} F1 квала Монца -> {got}")

got = run_track(SessionType.P1, track_id=5)
ok = got[:3] == ["welcome_to", "track_monaco", "session_practice"]
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} F1 практика Монако -> {got[:3]}")

ok = "ПОВТОР" not in got
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} второй раз за сессию молчит")

got = run_track(SessionType.UNKNOWN)
ok = got == []
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} тип сессии неизвестен -> молчит")

# ----------------------------------------------------------- классы
print()
print("КЛАССЫ МАШИН")
print("-" * 62)
for name, want in (("Hypercar", "hypercar"),
                   ("Hyper", "hypercar"),      # так пишет живая LMU
                   ("LMDh", "hypercar"), ("GTP", "hypercar"),
                   ("LMP2", "lmp2"), ("LMP3", "lmp3"), ("LMGTE Am", "gte"),
                   ("GT3", "gt3"), ("LMGT3", "gt3"), ("", "")):
    got, _ = classify(name)
    ok = got == want
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {name or '(пусто)':<12} -> "
          f"{got or '(не класс)'}")


def class_state(my_class, rivals):
    """rivals: (класс, вдоль по трассе, метры) - минус значит сзади."""
    st = GameState(sim="lmu")
    st.player_index = 0
    st.session = make_session(SessionType.RACE)
    st.session.track_length = 5000
    me = lap()
    me.lap_distance = 2000.0
    laps = [me]
    for _, gap in rivals:
        r = lap()
        r.lap_distance = 2000.0 + gap
        laps.append(r)
    st.laps = laps
    st.motion = [motion_at(0.0, 0.0) for _ in range(len(rivals) + 1)]
    st.telemetry = telemetry(200)
    st.car_classes = [my_class] + [c for c, _ in rivals]
    return st


said = []
rule = ClassTrafficRule()
rule.update(class_state("GT3", [("Hypercar", -20.0)]),
            lambda *ids, **kw: said.extend(ids))
ok = said == ["hypercar_behind"]
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} я GT3, гиперкар в 20 м сзади -> {said}")

said = []
rule = ClassTrafficRule()
rule.update(class_state("Hypercar", [("GT3", 25.0)]),
            lambda *ids, **kw: said.extend(ids))
ok = said == ["gt3_ahead"]
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} я гиперкар, GT3 в 25 м впереди -> {said}")

said = []
rule = ClassTrafficRule()
rule.update(class_state("GT3", [("GT3", -20.0)]),
            lambda *ids, **kw: said.extend(ids))
ok = said == []
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} свой класс сзади -> молчит {said}")

said = []
rule = ClassTrafficRule()
rule.update(class_state("GT3", [("Hypercar", -300.0)]),
            lambda *ids, **kw: said.extend(ids))
ok = said == []
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} гиперкар далеко сзади -> молчит {said}")

# ------------------------------------------------------------ мемы
print()
print("МЕМЫ")
print("-" * 62)

TMP = Path(tempfile.mkdtemp(prefix="meme_"))
tone = np.zeros(int(SAMPLE_RATE * 0.05), dtype=np.float32)
for pid in ("position_gained", "meme_verstappen", "meme_get_in_there",
            "meme_easy", "fastest_lap"):
    save_wav(TMP / f"{pid}.wav", tone)

p = Player(TMP, swearing=False, volume=0.0, verbose=False,
           radio=RadioConfig(enabled=False), memes=True, meme_chance=1.0)
got = {p._resolve("position_gained") for _ in range(40)}
ok = got <= {"meme_verstappen", "meme_get_in_there", "meme_easy"}
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} шанс 100% -> всегда мем {sorted(got)}")

p.meme_chance = 0.0
ok = p._resolve("position_gained") == "position_gained"
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} шанс 0% -> обычная фраза")

p.memes = False
p.meme_chance = 1.0
ok = p._resolve("position_gained") == "position_gained"
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} мемы выключены -> обычная фраза")

# незаписанный мем не должен глотать фразу
p.memes = True
ok = p._resolve("fastest_lap") == "fastest_lap"
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} мем не записан -> играет обычную "
      f"(не молчит)")

bad = [m for opts in MEME_FOR.values() for m in opts if m not in BY_ID]
ok = not bad
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} все мемы есть в банке {bad if bad else ''}")

bad = [k for k in MEME_FOR if k not in BY_ID]
ok = not bad
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} все заменяемые фразы существуют "
      f"{bad if bad else ''}")

p.shutdown()
shutil.rmtree(TMP, ignore_errors=True)

print()
print("-" * 62)
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
