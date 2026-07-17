"""Проверяет эффект рации по спектру: что режется, что проходит."""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spotter.audio.radio import RadioConfig, apply, bandpass

SR = 48000
cfg = RadioConfig()


def tone(freq: float, dur: float = 0.5) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False, dtype=np.float64)
    return np.sin(2 * np.pi * freq * t)


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0


def db(x: float) -> float:
    return 20 * np.log10(max(x, 1e-9))


print(f"ПОЛОСА ПРОПУСКАНИЯ  (ждём {cfg.low}-{cfg.high} Гц)")
print("-" * 58)
print(f"  {'частота':>8}  {'после фильтра':>14}   вывод")

fails = 0
CASES = [
    (60, "режем", False),
    (150, "режем", False),
    (300, "край", None),
    (800, "пропускаем", True),
    (1500, "пропускаем", True),
    (3000, "пропускаем", True),
    (5000, "режем", False),
    (9000, "режем", False),
]

for freq, label, should_pass in CASES:
    src = tone(freq)
    out = bandpass(src, SR, cfg.low, cfg.high)
    gain = db(rms(out) / rms(src))
    ok = True
    if should_pass is True:
        ok = gain > -3.0
    elif should_pass is False:
        ok = gain < -20.0
    fails += not ok
    mark = "OK  " if ok else "FAIL"
    print(f"  {mark} {freq:>6} Гц  {gain:>+8.1f} дБ   {label}")

# --------------------------------------------------------------- эффект
print()
print("ЭФФЕКТ ЦЕЛИКОМ")
print("-" * 58)

# «голос»: смесь тонов в речевом диапазоне
voice = (tone(220, 0.8) * 0.5 + tone(900, 0.8) * 0.3
         + tone(2400, 0.8) * 0.2).astype(np.float32)
out = apply(voice, SR, cfg, seed=1)

grew = out.size - voice.size
want = int((cfg.lead + cfg.tail) * SR)
checks = [
    ("длина выросла на lead+tail", abs(grew - want) <= 2),
    ("не клиппит", float(np.abs(out).max()) <= 0.971),
    ("не тишина", rms(out) > 0.02),
    ("тип float32", out.dtype == np.float32),
]

# в хвосте голоса нет - только затухающий шум
tail = out[-int(cfg.tail * SR):]
body = out[int(cfg.lead * SR):int(cfg.lead * SR) + voice.size]
checks.append(("хвост тише голоса", rms(tail) < rms(body) * 0.5))
checks.append(("хвост затухает",
               rms(tail[-200:]) < rms(tail[:200])))

# при выключенном эффекте ничего не трогаем
off = RadioConfig(enabled=False)
checks.append(("выключенный не меняет звук",
               np.array_equal(apply(voice, SR, off), voice)))

# тишина не ломает
checks.append(("пустой вход не падает",
               apply(np.zeros(0, dtype=np.float32), SR, cfg).size == 0))

for name, ok in checks:
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {name}")

print()
print(f"  длина: {voice.size / SR:.2f} сек -> {out.size / SR:.2f} сек")
print(f"  пик:   {np.abs(voice).max():.3f} -> {np.abs(out).max():.3f}")

print()
print("-" * 58)
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
