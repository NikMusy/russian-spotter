"""Детекция разворота: реакция при быстром вращении, тишина на вираже."""

import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from _fixtures import lap, telemetry
from spotter.rules.spin import SpinRule
from spotter.state import GameState
from spotter.udp.packets import CarMotion, PitStatus

fails = 0


def state(yaw, speed=150, pit=0):
    st = GameState()
    st.player_index = 0
    st.motion = [CarMotion(x=0, y=0, z=0, fwd_x=0, fwd_z=1,
                           right_x=1, right_z=0, yaw=yaw)]
    lp = lap(pit=pit)
    st.laps = [lp]
    st.telemetry = telemetry(speed)
    return st


def drive(rule, yaw_series, speed=150, pit=0, dt=0.05):
    """Прогоняет серию углов с шагом dt, копит что сказал споттер."""
    said = []
    for yaw in yaw_series:
        rule.update(state(yaw, speed, pit), lambda *i, **k: said.extend(i))
        time.sleep(dt)
    return said


print("РАЗВОРОТ")
print("-" * 58)

# Волчок: 5 рад/с при dt=0.05 -> шаг 0.25 рад
r = SpinRule()
spin_yaws = [0.25 * i for i in range(8)]
said = drive(r, spin_yaws)
ok = "focus" in said
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} закрутило (5 рад/с) -> {said or 'молчит'}")

# Обычный поворот: ~1 рад/с -> шаг 0.05 рад
r = SpinRule()
said = drive(r, [0.05 * i for i in range(10)])
ok = said == []
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} обычный вираж (1 рад/с) -> молчит {said}")

# Спин на низкой скорости (в боксах крутят) - не реагируем
r = SpinRule()
said = drive(r, spin_yaws, speed=10)
ok = said == []
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} медленно (10 км/ч) -> молчит {said}")

# В пит-лейн - молчит
r = SpinRule()
said = drive(r, spin_yaws, pit=PitStatus.PITTING)
ok = said == []
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} в пит-лейн -> молчит {said}")

# Один разворот - одна реакция, не тараторит
r = SpinRule()
said = drive(r, [0.3 * i for i in range(20)])
ok = said.count("focus") == 1
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} долгое вращение -> один раз "
      f"(сказал {said.count('focus')})")

# Переход угла через pi (перекрут) не даёт ложного гигантского rate
r = SpinRule()
r.update(state(3.10), lambda *i, **k: None)
time.sleep(0.05)
said = []
r.update(state(-3.10), lambda *i, **k: said.extend(i))
# скачок 3.10 -> -3.10 это на самом деле ~0.08 рад через pi, не спин
ok = said == []
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} переход через pi -> не ложный спин {said}")

print()
print("МЕМ ПРИ РАЗВОРОТЕ")
print("-" * 58)
from spotter.audio.phrases import MEME_FOR
memes = MEME_FOR.get("focus", ())
ok = "meme_not_raikkonen" in memes
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} 'focus' -> {memes}")
print(f"       (при развороте с шансом мема сыграет 'ты не Райкконен')")

print()
print("-" * 58)
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
