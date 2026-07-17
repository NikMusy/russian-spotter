"""Движок в режиме LMU против поддельной игры, end-to-end."""

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
sys.path.insert(0, str(ROOT / "tools"))

from _lmu_guard import require_no_live_lmu

require_no_live_lmu("движок LMU end-to-end")

from spotter.audio.recording import SAMPLE_RATE, save_wav
from spotter.engine import Engine

# Банк из пищалок: важно лишь, чтобы плееру было что играть.
TMP = Path(tempfile.mkdtemp(prefix="lmu_bank_"))
tone = (np.sin(2 * np.pi * 440 * np.linspace(0, 0.1, int(SAMPLE_RATE * 0.1),
                                             dtype=np.float32)) * 0.2)
for pid in ("car_left", "car_left_2", "car_right", "car_right_2", "clear",
            "clear_2", "three_wide", "still_there", "radio_check", "fcy",
            "fcy_end", "flag_blue", "weather_rain_starting", "consider_inters",
            "weather_rain_stopping", "weather_drying", "consider_slicks",
            "tyres_overheating", "tyres_worn", "puncture", "limiter_reminder",
            "limiter_on", "weather_dry", "track_temp", "degrees", "num_20",
            "num_8"):
    save_wav(TMP / f"{pid}.wav", tone.astype(np.float32))

messages: list[tuple[str, bool]] = []
statuses: list[tuple[bool, str]] = []

engine = Engine(
    sounds_dir=TMP, port=20777, swearing=False, volume=0.0, verbose=False,
    sim="lmu",
    on_message=lambda t, m: messages.append((t, m)),
    on_status=lambda ok, info: statuses.append((ok, info)),
)
thread = threading.Thread(target=engine.run, daemon=True)
thread.start()
time.sleep(0.8)

print("запускаю поддельную LMU...\n")
sim = subprocess.run([sys.executable, str(ROOT / "tools" / "fake_lmu.py")],
                     capture_output=True, text=True, timeout=180,
                     encoding="utf-8", errors="replace")
time.sleep(1.0)
engine.stop()
thread.join(timeout=3.0)

print("=== СТАТУСЫ ===")
for ok, info in statuses:
    print(f"  {'подключен' if ok else 'нет связи':<12} {info}")

spoken = [t for t, missing in messages if not missing]
print()
print(f"=== ПРОЗВУЧАЛО: {len(spoken)} ===")
for t in spoken[:16]:
    print(f"  {t}")
if len(spoken) > 16:
    print(f"  ... ещё {len(spoken) - 16}")

joined = " | ".join(spoken)
fails = 0
checks = [
    ("движок остановился", not thread.is_alive()),
    ("подключился к LMU", any(ok and "Mans" in i for ok, i in statuses)),
    ("сказал 'слева'", "слева" in joined),
    ("сказал 'справа'", "справа" in joined),
    ("сказал 'с двух сторон'", "с двух сторон" in joined),
    ("сказал 'чисто' или 'свободен'",
     "чисто" in joined or "свободен" in joined),
    ("полная жёлтая, а не сейфти-кар",
     "полная жёлтая" in joined and "машина безопасности" not in joined),
    ("синий флаг", "синий" in joined),
    ("дождь", "дожд" in joined),
    ("шины", "шины" in joined),
    ("лимитер", "лимитер" in joined),
]
print()
for name, ok in checks:
    fails += not ok
    print(f"  {'OK  ' if ok else 'FAIL'} {name}")

engine.shutdown()
shutil.rmtree(TMP, ignore_errors=True)
print()
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
