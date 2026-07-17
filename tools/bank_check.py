"""Проверка качества банка: битые, пустые, тихие, слишком длинные файлы."""

import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spotter.audio.phrases import BY_ID
from spotter.audio.recording import SAMPLE_RATE, load_wav

SOUNDS = ROOT / "sounds"

# Короче этого - скорее всего обрезок, а не фраза.
TOO_SHORT = 0.18
# Длиннее - для споттера поздно (он должен успеть до поворота).
SPOTTER_TOO_LONG = 1.6
TOO_LONG = 6.0
# Тише - не расслышишь под гул мотора.
TOO_QUIET = 0.25

wavs = sorted(SOUNDS.glob("*.wav"))
print("=" * 68)
print(f"  ПРОВЕРКА БАНКА - {len(wavs)} файлов")
print("=" * 68)

broken, short, quiet, long_ones, slow_spotter, wrong_rate = [], [], [], [], [], []
total_sec = 0.0

for path in wavs:
    try:
        audio, rate = load_wav(path)
    except (wave.Error, OSError, EOFError, ValueError) as exc:
        broken.append((path.name, str(exc)[:40]))
        continue

    if audio.size == 0:
        broken.append((path.name, "пустой"))
        continue

    dur = audio.size / rate
    peak = float(np.abs(audio).max())
    total_sec += dur

    if rate != SAMPLE_RATE:
        wrong_rate.append((path.name, rate))
    if dur < TOO_SHORT:
        short.append((path.name, dur))
    if peak < TOO_QUIET:
        quiet.append((path.name, peak))
    if dur > TOO_LONG:
        long_ones.append((path.name, dur))

    base = path.stem[:-6] if path.stem.endswith("__hard") else path.stem
    ph = BY_ID.get(base)
    if ph and ph.group == "spotter" and dur > SPOTTER_TOO_LONG:
        slow_spotter.append((path.name, dur))

print(f"  общая длительность: {total_sec / 60:.1f} мин")
print(f"  в среднем на фразу: {total_sec / max(1, len(wavs)):.2f} сек")
print()

problems = 0


def report(title, items, fmt):
    global problems
    if not items:
        print(f"  OK   {title}")
        return
    problems += len(items)
    print(f"  !!   {title}: {len(items)}")
    for name, val in items[:8]:
        print(f"         {name:<34} {fmt(val)}")
    if len(items) > 8:
        print(f"         ... и ещё {len(items) - 8}")


report("файлы читаются", broken, lambda v: v)
report("нет обрезков", short, lambda v: f"{v:.2f} сек - не обрезалось ли?")
report("громкость в норме", quiet, lambda v: f"пик {v:.2f} - очень тихо")
report("нет слишком длинных", long_ones, lambda v: f"{v:.1f} сек")
report("частота 48 кГц", wrong_rate, lambda v: f"{v} Гц")
report("споттер отвечает быстро", slow_spotter,
       lambda v: f"{v:.2f} сек - длинновато для 'слева'")

# --- нет ли лишних файлов, которых нет в банке
known = set()
for pid in BY_ID:
    known.add(f"{pid}.wav")
    known.add(f"{pid}__hard.wav")
extra = [w.name for w in wavs if w.name not in known]
if extra:
    print(f"  !!   файлы не из банка: {len(extra)}")
    for n in extra[:6]:
        print(f"         {n}")
else:
    print("  OK   лишних файлов нет")

print()
print("=" * 68)
if problems == 0:
    print("  БАНК ЧИСТЫЙ. Можно ехать.")
else:
    print(f"  Замечаний: {problems}. Не критично, но глянь список выше -")
    print("  эти фразы можно перезаписать через recorder.exe.")
print("=" * 68)
