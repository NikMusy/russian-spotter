"""Что уже записано и чего не хватает.

Запусти, чтобы понять, где ты и что делать дальше.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spotter.audio.phrases import (
    BY_ID, GROUP_TITLES, PHRASES, SIM_TITLES, recording_plan,
)

SOUNDS = ROOT / "sounds"
sim = sys.argv[1] if len(sys.argv) > 1 else "lmu"


def have(fid: str) -> bool:
    return (SOUNDS / f"{fid}.wav").exists()


plan = recording_plan(sim=sim)
done = [(f, t, p) for f, t, p in plan if have(f)]

print("=" * 66)
print(f"  БАНК ФРАЗ - {SIM_TITLES.get(sim, sim)}")
print("=" * 66)
print(f"  записано {len(done)} из {len(plan)}   "
      f"({len(done) / len(plan) * 100:.0f}%)")
print()

# --- по группам
print("  ГРУППА                            записано   осталось")
print("  " + "-" * 60)
groups: dict[str, list] = {}
for fid, text, p in plan:
    groups.setdefault(p.group, []).append(fid)

for g, fids in groups.items():
    d = sum(1 for f in fids if have(f))
    bar_len = 16
    filled = int(d / len(fids) * bar_len)
    bar = "#" * filled + "." * (bar_len - filled)
    left = len(fids) - d
    mark = "  ГОТОВО" if left == 0 else ""
    print(f"  {GROUP_TITLES[g]:<32} {bar} {d:>3}/{len(fids):<3}{mark}")

# --- минимум, чтобы споттер заработал в гонке
print()
print("=" * 66)
print("  МИНИМУМ ДЛЯ ГОНКИ")
print("=" * 66)

MUST = {
    "спотит машины рядом": ["car_left", "car_right", "three_wide", "clear"],
    "спасает от штрафа": ["limiter_reminder"],
    "флаги": ["flag_yellow_sector", "flag_blue", "flag_green"],
    "полная жёлтая (LMU)": ["fcy", "fcy_end"],
    "проверка связи": ["radio_check"],
}
ready = True
for what, fids in MUST.items():
    missing = [f for f in fids if not have(f)]
    if missing:
        ready = False
        print(f"  НЕТ  {what:<24} не хватает: {', '.join(missing)}")
    else:
        print(f"  ЕСТЬ {what}")

print()
if ready:
    print("  МОЖНО ЕХАТЬ. Споттер отработает главное.")
else:
    print("  Запиши то, что помечено НЕТ - и можно ехать.")

# --- что записать следующим: самое полезное из незаписанного
print()
print("=" * 66)
print("  ЧТО ЗАПИСАТЬ СЛЕДУЮЩИМ (по важности)")
print("=" * 66)

ORDER = ["spotter", "pit", "flags", "safety_car", "endurance", "classes",
         "numbers", "gaps", "tyres", "fuel", "damage", "weather", "laps",
         "position", "penalties", "tracks", "session", "warmup", "track",
         "drs", "memes", "iracing", "general"]

shown = 0
for g in ORDER:
    fids = groups.get(g)
    if not fids:
        continue
    missing = [f for f in fids if not have(f)]
    if not missing:
        continue
    print(f"\n  {GROUP_TITLES[g]}  - осталось {len(missing)}")
    for f in missing[:6]:
        base = f[:-6] if f.endswith("__hard") else f
        ph = BY_ID.get(base)
        text = (ph.hard if f.endswith("__hard") and ph else
                ph.text if ph else f)
        print(f"     {f:<24} {text}")
    if len(missing) > 6:
        print(f"     ... и ещё {len(missing) - 6}")
    shown += 1
    if shown >= 4:
        break

print()
print("=" * 66)
