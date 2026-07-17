"""Проверяет, что движок отдаёт сообщения и статус наружу - на этом
держится окно GUI.

Банк подсовываем свой, из коротких тонов: настоящие фразы тут не нужны,
нужно лишь чтобы плееру было что играть и он отчитался текстом.
"""

import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spotter.audio.recording import SAMPLE_RATE, save_wav
from spotter.engine import Engine

# Пищалки вместо голоса - только чтобы файлы существовали.
TMP = Path(tempfile.mkdtemp(prefix="spotter_bank_"))
tone = (np.sin(2 * np.pi * 440 * np.linspace(0, 0.12, int(SAMPLE_RATE * 0.12),
                                             dtype=np.float32)) * 0.2)
for pid in ("car_left", "car_left_2", "car_right", "car_right_2", "clear",
            "clear_2", "three_wide", "still_there", "radio_check",
            "limiter_reminder", "puncture", "flag_yellow_sector"):
    save_wav(TMP / f"{pid}.wav", tone.astype(np.float32))
print(f"временный банк: {TMP}\n")

messages: list[tuple[str, bool]] = []
statuses: list[tuple[bool, str]] = []

engine = Engine(
    sounds_dir=TMP, port=20779, swearing=True, volume=0.0,
    verbose=False,
    on_message=lambda text, missing: messages.append((text, missing)),
    on_status=lambda ok, info: statuses.append((ok, info)),
)

thread = threading.Thread(target=engine.run, daemon=True)
thread.start()
time.sleep(1.0)

sim = subprocess.run(
    [sys.executable, str(ROOT / "tools" / "simulate.py"), "20779"],
    capture_output=True, text=True, timeout=120,
)

time.sleep(1.0)
engine.stop()
thread.join(timeout=3.0)

print("=== СТАТУСЫ ===")
for ok, info in statuses:
    print(f"  {'подключен' if ok else 'нет связи':<12} {info}")

print()
print(f"=== СООБЩЕНИЙ: {len(messages)} ===")
for text, missing in messages[:12]:
    print(f"  {'[нет wav]' if missing else '[радио]  '} {text}")
if len(messages) > 12:
    print(f"  ... ещё {len(messages) - 12}")

spoken = [t for t, missing in messages if not missing]

print()
fails = 0
checks = [
    ("движок остановился", not thread.is_alive()),
    ("статус 'подключен' пришёл", any(ok for ok, _ in statuses)),
    ("статус про формат F1 25", any("25" in i for _, i in statuses)),
    ("сообщения дошли", len(messages) > 10),
    ("что-то реально прозвучало", len(spoken) > 3),
    ("споттер сказал 'слева'", any("слева" in t for t in spoken)),
    ("споттер сказал 'справа'", any("справа" in t for t in spoken)),
    ("сказал 'чисто' или 'свободен'",
     any("чисто" in t or "свободен" in t for t in spoken)),
    ("в тексте нет сырых id", not any("_" in t for t in spoken)),
]
for name, ok in checks:
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {name}")

shutil.rmtree(TMP, ignore_errors=True)

print()
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
