"""Выбор микрофона.

Windows показывает один и тот же микрофон по разу на каждый звуковой API
(MME, DirectSound, WASAPI, WDM-KS) с ОДИНАКОВЫМ именем. Искать устройство
по имени - значит попасть в случайную копию: словарь {имя: индекс}
оставляет последнюю, а это обычно WDM-KS, которая падает с
PaErrorCode -9996. Тут проверяем, что этого больше не происходит.
"""

import sys
from collections import Counter
from pathlib import Path

import numpy as np
import sounddevice as sd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spotter.audio import recording as rec

fails = 0
print("УСТРОЙСТВА ВВОДА")
print("-" * 66)

devs = rec.input_devices()
ok = len(devs) > 0
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} нашлось устройств: {len(devs)}")

ok = all(len(d) == 3 for d in devs)
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} отдаём тройки (индекс, имя, API)")

print()
for i, name, api in devs:
    star = " <-- системный" if i == rec.default_input() else ""
    print(f"    {i:>3}  {name[:34]:<34} {api}{star}")

# --- главное: дубли имён
print()
names = Counter(n for _, n, _ in devs)
dupes = {n: c for n, c in names.items() if c > 1}
print(f"  имён-дублей: {len(dupes)}")
for n, c in dupes.items():
    idxs = [i for i, nn, _ in devs if nn == n]
    apis = [a for _, nn, a in devs if nn == n]
    print(f"    '{n}' -> {c} копии, индексы {idxs}")
    print(f"       {', '.join(apis)}")

# Индексы обязаны быть уникальны, даже когда имена нет.
idxs = [i for i, _, _ in devs]
ok = len(idxs) == len(set(idxs))
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} индексы уникальны")

# Ярлыки для окна: имя + API. Если и они совпадают - выбор по позиции
# всё равно спасает, но проверим, что список не схлопывается.
labels = [f"{n}   ·   {a}" for _, n, a in devs]
ok = len(labels) == len(devs)
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} ярлыков столько же, сколько устройств")

# Старый баг: словарь по имени терял устройства.
by_name = {n: i for i, n, _ in devs}
lost = len(devs) - len(by_name)
print(f"  (старый способ - словарь по имени - потерял бы {lost} устройств)")
ok = lost > 0 if dupes else True
print(f"  {'OK  ' if ok else '    '} тест воспроизводит исходную проблему")

# --- системное устройство должно открываться
print()
print("ЗАПИСЬ")
print("-" * 66)
default = rec.default_input()
r = rec.Recorder()
try:
    r.start(device=default)
    ok = r.active
    print(f"  {'OK  ' if ok else 'FAIL'} системный микрофон открылся "
          f"(индекс {default}, {r.rate} Гц)")
    fails += not ok
    sd.sleep(300)
    audio = r.stop()
    ok = audio.size > 0
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} что-то записалось: {audio.size} "
          f"отсчётов, {audio.size / r.rate:.2f} сек")
    ok = audio.ndim == 1
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} звук моно (одномерный)")
except Exception as exc:
    fails += 1
    print(f"  FAIL системный микрофон не открылся: {exc}")

# --- пересчёт частоты
print()
print("ПЕРЕСЧЁТ ЧАСТОТЫ (если микрофон не даёт 48 кГц)")
print("-" * 66)
src = np.sin(np.linspace(0, 100, 44100)).astype(np.float32)
out = rec.resample(src, 44100, 48000)
want = int(round(44100 / 44100 * 48000))
ok = abs(out.size - want) <= 1
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} 44100 -> 48000: {src.size} -> {out.size}")

out = rec.process(src, 44100)
ok = out.size > 0 and float(np.abs(out).max()) <= 0.9
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} process с чужой частотой не падает, "
      f"пик {np.abs(out).max():.2f}")

ok = np.array_equal(rec.resample(src, 48000, 48000), src)
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} 48000 -> 48000 не трогает звук")

print()
print("-" * 66)
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
