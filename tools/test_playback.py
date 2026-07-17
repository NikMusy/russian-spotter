"""Кнопки «Прослушать» и «Как в рации».

Раньше обе молчали в двух случаях: фраза не записана (был голый return) и
воспроизведение упало (ошибку глотал except: pass). Со стороны это
выглядело как сломанная кнопка. Тут проверяем, что теперь кнопка всегда
что-то отвечает.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from spotter.audio import recording as rec
from spotter.recorder_gui import RecorderApp

fails = 0
print("УСТРОЙСТВА ВЫВОДА")
print("-" * 62)
outs = rec.output_devices()
ok = len(outs) > 0 and all(len(o) == 3 for o in outs)
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} нашлось выходов: {len(outs)}")
for i, name, api in outs[:6]:
    star = " <-- системный" if i == rec.default_output() else ""
    print(f"    {i:>3}  {name[:32]:<32} {api}{star}")

idxs = [i for i, _, _ in outs]
ok = len(idxs) == len(set(idxs))
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} индексы выходов уникальны")

# --- окно на временной папке, чтобы не трогать реальные записи
TMP = Path(tempfile.mkdtemp(prefix="rec_gui_"))
(TMP / "tools").mkdir()
shutil.copy(ROOT / "tools" / "icon.png", TMP / "tools" / "icon.png")

app = RecorderApp(TMP)
app.withdraw()

print()
print("КНОПКИ")
print("-" * 62)

ok = hasattr(app, "out_box") and app.out_box.current() >= 0
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} наушники выбраны в окне: "
      f"'{app.out_var.get()[:40]}'")

ok = app._output() == rec.default_output()
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} по умолчанию системные "
      f"(индекс {app._output()})")

# 1. Фраза не записана - кнопка обязана сказать об этом
fid, _, _ = app.plan[app.idx]
app.level_lbl.configure(text="")
app._play()
msg = app.level_lbl.cget("text")
ok = "не записана" in msg
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} нет файла -> '{msg}'")

app.level_lbl.configure(text="")
app._play(radio=True)
msg = app.level_lbl.cget("text")
ok = "не записана" in msg
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} нет файла, рация -> '{msg}'")

# 2. Файл есть - должно играть и отчитаться
tone = (np.sin(2 * np.pi * 440 * np.linspace(0, 0.25, int(48000 * 0.25),
                                             dtype=np.float32)) * 0.3)
rec.save_wav(TMP / "sounds" / f"{fid}.wav", tone.astype(np.float32))

app.level_lbl.configure(text="")
app._play()
msg = app.level_lbl.cget("text")
ok = msg == "слушаешь запись"
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} файл есть -> '{msg}'")

app.level_lbl.configure(text="")
app._play(radio=True)
msg = app.level_lbl.cget("text")
ok = msg == "так это прозвучит в игре"
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} файл есть, рация -> '{msg}'")

# 3. Идёт запись - кнопка объясняет, а не молчит
class FakeRec:
    active = True
real, app.rec = app.rec, FakeRec()
app.level_lbl.configure(text="")
app._play()
msg = app.level_lbl.cget("text")
ok = "запись" in msg
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} во время записи -> '{msg}'")
app.rec = real

# 4. Кривой выход - ошибка наружу, а не тишина
class BadBox:
    def current(self):
        return 999
real_box, app.out_box = app.out_box, BadBox()
ok = app._output() is None
fails += not ok
print(f"  {'OK  ' if ok else 'FAIL'} несуществующий выход -> None "
      f"(играем в системный, не падаем)")
app.out_box = real_box

import sounddevice as sd
sd.stop()
app.destroy()
shutil.rmtree(TMP, ignore_errors=True)

print()
print("-" * 62)
print("ВСЁ ПРОШЛО" if fails == 0 else f"ПРОВАЛОВ: {fails}")
sys.exit(1 if fails else 0)
