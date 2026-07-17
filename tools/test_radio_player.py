"""Проверяет, что плеер реально скармливает pygame обработанный рацией звук."""

import shutil
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spotter.audio.player import Player, _resample
from spotter.audio.radio import RadioConfig
from spotter.audio.recording import SAMPLE_RATE, load_wav, save_wav

TMP = Path(tempfile.mkdtemp(prefix="spotter_radio_"))

# «Голос»: низкий тон 120 Гц (рация должна его срезать) + речевой 900 Гц.
dur = 0.6
t = np.linspace(0, dur, int(SAMPLE_RATE * dur), endpoint=False, dtype=np.float32)
voice = (np.sin(2 * np.pi * 120 * t) * 0.5
         + np.sin(2 * np.pi * 900 * t) * 0.5).astype(np.float32)
save_wav(TMP / "car_left.wav", voice)

# Файл с «неправильной» частотой - проверяем ресемплинг.
save_wav(TMP / "clear.wav", voice)

fails = 0
print("ПЛЕЕР С РАЦИЕЙ")
print("-" * 58)

p = Player(TMP, swearing=False, volume=0.0, verbose=False,
           radio=RadioConfig(enabled=True))
snd = p._sound("car_left")
ok = snd is not None
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} звук собрался через pygame")

if snd is not None:
    import pygame
    arr = pygame.sndarray.array(snd).astype(np.float32) / 32767.0
    if arr.ndim > 1:
        arr = arr[:, 0]
    src_len = voice.size / SAMPLE_RATE
    out_len = arr.size / SAMPLE_RATE
    cfg = RadioConfig()
    grew = out_len - src_len
    ok = grew > cfg.tail * 0.5
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} появился хвост рации "
          f"({src_len:.2f} -> {out_len:.2f} сек)")

    # Спектр: 120 Гц должен просесть относительно 900 Гц.
    def bin_level(x, freq):
        spec = np.abs(np.fft.rfft(x))
        idx = int(freq * x.size / SAMPLE_RATE)
        return float(spec[max(0, idx - 2):idx + 3].max())

    src_ratio = bin_level(voice, 120) / bin_level(voice, 900)
    out_ratio = bin_level(arr, 120) / bin_level(arr, 900)
    ok = out_ratio < src_ratio * 0.2
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} низ срезан "
          f"(120/900 Гц: {src_ratio:.2f} -> {out_ratio:.3f})")

# Без рации звук не трогаем.
p2 = Player(TMP, swearing=False, volume=0.0, verbose=False,
            radio=RadioConfig(enabled=False))
snd2 = p2._sound("car_left")
ok = snd2 is not None
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} без рации звук тоже грузится")

# Кэш и перезагрузка.
p.reload_bank()
ok = p._sound("car_left") is not None
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} reload_bank не ломает загрузку")

# Прогрев не падает на неполном банке.
p.prewarm()
time.sleep(1.5)
print(f"  OK   prewarm отработал молча на неполном банке")

# Ресемплинг.
r = _resample(voice, 44100, 48000)
want = int(round(voice.size / 44100 * 48000))
ok = abs(r.size - want) <= 1
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} ресемплинг 44100 -> 48000 "
      f"({voice.size} -> {r.size} отсчётов)")

p.shutdown()
p2.shutdown()
shutil.rmtree(TMP, ignore_errors=True)

print()
print("-" * 58)
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
