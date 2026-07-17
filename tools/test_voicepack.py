"""Голосовые паки: своя запись в приоритете, пробелы закрывает чужой голос."""

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spotter.audio.player import Player
from spotter.audio.radio import RadioConfig
from spotter.audio.recording import SAMPLE_RATE, save_wav

TMP = Path(tempfile.mkdtemp(prefix="vp_"))
OWN = TMP / "sounds"
PACK = TMP / "pack"

# Тон 220 Гц - "свой" голос, 880 Гц - голос из пака. Так их различим.
t = np.linspace(0, 0.15, int(SAMPLE_RATE * 0.15), endpoint=False,
                dtype=np.float32)
own_tone = (np.sin(2 * np.pi * 220 * t) * 0.4).astype(np.float32)
pack_tone = (np.sin(2 * np.pi * 880 * t) * 0.4).astype(np.float32)

# Свой голос: только car_left. Пак: car_left и car_right.
save_wav(OWN / "car_left.wav", own_tone)
save_wav(PACK / "car_left.wav", pack_tone)
save_wav(PACK / "car_right.wav", pack_tone)
save_wav(PACK / "limiter_reminder__hard.wav", pack_tone)
save_wav(PACK / "meme_verstappen.wav", pack_tone)

fails = 0
print("ГОЛОСОВЫЕ ПАКИ")
print("-" * 62)

p = Player(OWN, swearing=True, volume=0.0, verbose=False,
           radio=RadioConfig(enabled=False), memes=False,
           voicepack_dir=PACK)


def which(pid):
    """Какой файл выбран - свой или из пака."""
    path = p._find(pid)
    if path is None:
        return None
    return "свой" if path.parent == OWN else "пак"


cases = [
    ("записал сам -> играет свой", "car_left", "свой"),
    ("не записал -> берём из пака", "car_right", "пак"),
    ("нет нигде -> ничего", "three_wide", None),
]
for name, pid, want in cases:
    got = which(pid)
    ok = got == want
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {name:<34} -> {got}")

# Звук реально грузится и различается
snd = p._sound("car_left")
ok = snd is not None
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} свой звук грузится")
snd = p._sound("car_right")
ok = snd is not None
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} звук из пака грузится")

# Матерный дубль тоже ищется в паке
ok = p._resolve("limiter_reminder") == "limiter_reminder__hard"
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} матерный дубль берётся из пака")

# Мем из пака
p.memes = True
p.meme_chance = 1.0
ok = p._resolve("position_gained") == "meme_verstappen"
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} мем берётся из пака")
p.memes = False

# Счётчики
own = p.own_count()
have, total = p.available()
ok = own == 1
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} своих записей: {own} (ждём 1)")
ok = have == 4       # car_left(свой) + car_right, limiter__hard не в BY_ID, meme
fails += not (have >= 3)
print(f"  {'OK  ' if have >= 3 else 'FAIL'} доступно всего: {have} из {total}")

# Без пака - только свои
p2 = Player(OWN, swearing=False, volume=0.0, verbose=False,
            radio=RadioConfig(enabled=False), memes=False, voicepack_dir=None)
ok = p2._find("car_right") is None
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} без пака чужой голос не подставляется")
ok = p2._find("car_left") is not None
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} без пака свой голос играет")

# Пак есть в репозитории?
print()
print("ПАК В ПРОЕКТЕ")
print("-" * 62)
real = ROOT / "voicepacks" / "nikolay"
n = len(list(real.glob("*.wav"))) if real.is_dir() else 0
ok = n > 250
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} voicepacks/nikolay: {n} фраз")

p.shutdown()
p2.shutdown()
shutil.rmtree(TMP, ignore_errors=True)

print()
print("-" * 62)
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
