"""Окно рекордера: наговорить банк фраз своим голосом."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

import sounddevice as sd

from .audio import radio as radio_fx
from .audio import recording as rec
from .audio.phrases import (
    ALL_SIMS, GROUP_TITLES, SIM_F1, SIM_TITLES, recording_plan,
)
from .audio.radio import RadioConfig

BG = "#1b1e23"
BG_PANEL = "#23272e"
FG = "#e6e8ec"
FG_DIM = "#8b929e"
RED = "#e10600"
GREEN = "#28c76f"
AMBER = "#f0a020"


class RecorderApp(tk.Tk):
    def __init__(self, root_dir: Path) -> None:
        super().__init__()
        self.root_dir = root_dir
        self.sounds = root_dir / "sounds"
        self.sounds.mkdir(parents=True, exist_ok=True)

        self.rec = rec.Recorder()
        self.radio_cfg = self._load_radio_cfg()
        self.plan: list = []
        self.idx = 0
        self._level_job: str | None = None

        self.title("Рекордер фраз")
        self.configure(bg=BG)
        self.geometry("720x600")
        self.minsize(640, 560)

        icon = root_dir / "tools" / "icon.png"
        if icon.exists():
            try:
                self._icon_img = tk.PhotoImage(file=str(icon))
                self.iconphoto(True, self._icon_img)
            except tk.TclError:
                pass

        self._style()
        self._build()
        self._rebuild_plan()

        self.bind("<space>", lambda e: self._toggle_record())
        self.bind("<Right>", lambda e: self._go(1))
        self.bind("<Left>", lambda e: self._go(-1))
        self.bind("<p>", lambda e: self._play())
        self.bind("<r>", lambda e: self._play(radio=True))
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _load_radio_cfg(self) -> RadioConfig:
        """Берём настройки рации из общего конфига, чтобы превью совпадало
        с тем, как споттер потом это скажет."""
        import json
        path = self.root_dir / "config.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return RadioConfig.from_dict(data.get("radio"))
        except (OSError, json.JSONDecodeError):
            return RadioConfig()

    def _style(self) -> None:
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", background=BG, foreground=FG, borderwidth=0)
        s.configure("TFrame", background=BG)
        s.configure("Panel.TFrame", background=BG_PANEL)
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("Dim.TLabel", background=BG, foreground=FG_DIM)
        s.configure("Panel.TLabel", background=BG_PANEL, foreground=FG)
        s.configure("DimPanel.TLabel", background=BG_PANEL, foreground=FG_DIM)
        s.configure("TCheckbutton", background=BG_PANEL, foreground=FG)
        s.map("TCheckbutton", background=[("active", BG_PANEL)])
        s.configure("TCombobox", fieldbackground=BG_PANEL,
                    background=BG_PANEL, foreground=FG, arrowcolor=FG)
        s.configure("Rec.TButton", background=RED, foreground="#ffffff",
                    font=("Segoe UI Semibold", 12), padding=(22, 12))
        s.map("Rec.TButton", background=[("active", "#ff2418")])
        s.configure("Flat.TButton", background=BG_PANEL, foreground=FG,
                    padding=(12, 7))
        s.map("Flat.TButton", background=[("active", "#2e343d")])
        s.configure("Bar.Horizontal.TProgressbar", background=GREEN,
                    troughcolor=BG_PANEL)

    def _build(self) -> None:
        # --- верх: сим, фильтры, микрофон
        top = ttk.Frame(self, style="Panel.TFrame", padding=12)
        top.pack(fill="x", padx=14, pady=(14, 0))

        ttk.Label(top, text="Сим", style="DimPanel.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8))
        self.sim_var = tk.StringVar(value=SIM_TITLES[SIM_F1])
        box = ttk.Combobox(top, textvariable=self.sim_var, width=30,
                           state="readonly",
                           values=[SIM_TITLES[s] for s in ALL_SIMS])
        box.grid(row=0, column=1, sticky="w")
        box.bind("<<ComboboxSelected>>", lambda e: self._rebuild_plan())

        self.core_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="только необходимые",
                        variable=self.core_var,
                        command=self._rebuild_plan).grid(
            row=0, column=2, padx=(18, 0))
        self.swear_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="с матом", variable=self.swear_var,
                        command=self._rebuild_plan).grid(row=0, column=3,
                                                         padx=(14, 0))

        ttk.Label(top, text="Микрофон", style="DimPanel.TLabel").grid(
            row=1, column=0, sticky="w", pady=(10, 0))
        # Держим сам список: выбираем устройство по позиции в нём, а не по
        # названию. Windows показывает один микрофон по разу на каждый
        # звуковой API, имена совпадают, и поиск по имени попадает в
        # случайную копию - обычно в WDM-KS, которая не открывается.
        self.devices = rec.input_devices()
        default = rec.default_input()
        labels = [f"{name}   ·   {api}" for _, name, api in self.devices]
        self.dev_var = tk.StringVar()
        self.dev_box = ttk.Combobox(top, textvariable=self.dev_var, width=52,
                                    state="readonly", values=labels)
        self.dev_box.grid(row=1, column=1, columnspan=3, sticky="w",
                          pady=(10, 0))
        pos = next((n for n, (i, _, _) in enumerate(self.devices)
                    if i == default), 0)
        if labels:
            self.dev_box.current(pos)

        ttk.Label(top, text="Наушники", style="DimPanel.TLabel").grid(
            row=2, column=0, sticky="w", pady=(8, 0))
        self.outputs = rec.output_devices()
        out_default = rec.default_output()
        out_labels = [f"{name}   ·   {api}" for _, name, api in self.outputs]
        self.out_var = tk.StringVar()
        self.out_box = ttk.Combobox(top, textvariable=self.out_var, width=52,
                                    state="readonly", values=out_labels)
        self.out_box.grid(row=2, column=1, columnspan=3, sticky="w",
                          pady=(8, 0))
        pos = next((n for n, (i, _, _) in enumerate(self.outputs)
                    if i == out_default), 0)
        if out_labels:
            self.out_box.current(pos)

        # --- карточка фразы
        card = ttk.Frame(self, style="Panel.TFrame", padding=18)
        card.pack(fill="both", expand=True, padx=14, pady=12)

        self.group_lbl = ttk.Label(card, text="", style="DimPanel.TLabel")
        self.group_lbl.pack(anchor="w")

        ttk.Label(card, text="ГОВОРИ:", style="DimPanel.TLabel").pack(
            anchor="w", pady=(16, 4))
        self.text_lbl = tk.Label(card, text="", bg=BG_PANEL, fg=FG,
                                 font=("Segoe UI Semibold", 26),
                                 wraplength=620, justify="left")
        self.text_lbl.pack(anchor="w", pady=(0, 10))

        self.note_lbl = ttk.Label(card, text="", style="DimPanel.TLabel",
                                  wraplength=620)
        self.note_lbl.pack(anchor="w")

        info = ttk.Frame(card, style="Panel.TFrame")
        info.pack(anchor="w", fill="x", pady=(14, 0))
        self.file_lbl = ttk.Label(info, text="", style="DimPanel.TLabel",
                                  font=("Consolas", 10))
        self.file_lbl.pack(side="left")
        self.have_lbl = tk.Label(info, text="", bg=BG_PANEL, fg=FG_DIM,
                                 font=("Segoe UI Semibold", 9))
        self.have_lbl.pack(side="left", padx=(12, 0))

        # --- запись
        self.rec_btn = ttk.Button(card, text="ЗАПИСАТЬ  (пробел)",
                                  style="Rec.TButton",
                                  command=self._toggle_record)
        self.rec_btn.pack(anchor="w", pady=(20, 10))

        self.level = tk.Canvas(card, height=16, bg=BG, highlightthickness=0)
        self.level.pack(fill="x", pady=(0, 4))
        self.level_lbl = ttk.Label(card, text="", style="DimPanel.TLabel")
        self.level_lbl.pack(anchor="w")

        # --- навигация
        nav = ttk.Frame(card, style="Panel.TFrame")
        nav.pack(anchor="w", pady=(18, 0))
        ttk.Button(nav, text="< Назад", style="Flat.TButton",
                   command=lambda: self._go(-1)).pack(side="left")
        ttk.Button(nav, text="Прослушать (P)", style="Flat.TButton",
                   command=self._play).pack(side="left", padx=8)
        ttk.Button(nav, text="Как в рации (R)", style="Flat.TButton",
                   command=lambda: self._play(radio=True)).pack(side="left")
        ttk.Button(nav, text="Дальше >", style="Flat.TButton",
                   command=lambda: self._go(1)).pack(side="left", padx=8)

        # --- прогресс
        bottom = ttk.Frame(self, padding=(14, 0, 14, 14))
        bottom.pack(fill="x")
        self.bar = ttk.Progressbar(bottom, style="Bar.Horizontal.TProgressbar",
                                   maximum=100)
        self.bar.pack(fill="x")
        self.prog_lbl = ttk.Label(bottom, text="", style="Dim.TLabel")
        self.prog_lbl.pack(anchor="w", pady=(6, 0))

    # ---------------------------------------------------------------- план

    def _sim(self) -> str:
        label = self.sim_var.get()
        for s in ALL_SIMS:
            if SIM_TITLES[s] == label:
                return s
        return SIM_F1

    def _rebuild_plan(self) -> None:
        self.plan = recording_plan(core_only=self.core_var.get(),
                                   swearing=self.swear_var.get(),
                                   sim=self._sim())
        self.idx = min(self.idx, max(0, len(self.plan) - 1))
        # Прыгаем на первую незаписанную - продолжать удобнее, чем начинать.
        for i, (fid, _, _) in enumerate(self.plan):
            if not (self.sounds / f"{fid}.wav").exists():
                self.idx = i
                break
        self._show()

    def _device(self) -> int | None:
        pos = self.dev_box.current()
        if pos < 0 or pos >= len(self.devices):
            return None
        return self.devices[pos][0]

    def _output(self) -> int | None:
        pos = self.out_box.current()
        if pos < 0 or pos >= len(self.outputs):
            return None
        return self.outputs[pos][0]

    def _play_audio(self, audio, rate: int, note: str) -> None:
        """Играет и честно докладывает. Молча глотать ошибку нельзя:
        именно из-за этого кнопки выглядели сломанными."""
        try:
            rec.play(audio, rate, device=self._output())
            self.level_lbl.configure(text=note)
        except Exception as exc:
            self.level_lbl.configure(
                text=f"не могу воспроизвести: {exc}. Выбери другие наушники.")

    def _show(self) -> None:
        if not self.plan:
            return
        fid, text, phrase = self.plan[self.idx]
        path = self.sounds / f"{fid}.wav"

        self.group_lbl.configure(text=GROUP_TITLES[phrase.group])
        self.text_lbl.configure(text=text)
        notes = []
        if phrase.note:
            notes.append(phrase.note)
        if fid.endswith("__hard"):
            notes.append("вариант с матом")
        self.note_lbl.configure(text="   ".join(notes))
        self.file_lbl.configure(text=f"{fid}.wav")
        if path.exists():
            self.have_lbl.configure(text="ЗАПИСАНО", fg=GREEN)
        else:
            self.have_lbl.configure(text="пусто", fg=FG_DIM)

        done = sum(1 for f, _, _ in self.plan
                   if (self.sounds / f"{f}.wav").exists())
        self.bar.configure(value=done / len(self.plan) * 100)
        self.prog_lbl.configure(
            text=f"записано {done} из {len(self.plan)}   "
                 f"|   фраза {self.idx + 1}")

    def _go(self, delta: int) -> None:
        if self.rec.active:
            return
        self.idx = max(0, min(len(self.plan) - 1, self.idx + delta))
        self._show()

    # -------------------------------------------------------------- запись

    def _toggle_record(self) -> None:
        if self.rec.active:
            self._stop_record()
        else:
            self._start_record()

    def _start_record(self) -> None:
        try:
            self.rec.start(device=self._device())
        except Exception:
            # Выбранная копия устройства не открылась - берём системную по
            # умолчанию, она почти всегда рабочая (MME).
            fallback = rec.default_input()
            try:
                self.rec.start(device=fallback)
                pos = next((n for n, (i, _, _) in enumerate(self.devices)
                            if i == fallback), None)
                if pos is not None:
                    self.dev_box.current(pos)
                self.level_lbl.configure(
                    text="тот микрофон не открылся, взял системный")
            except Exception as exc:
                self.level_lbl.configure(
                    text=f"микрофон не открылся: {exc}. "
                         f"Выбери другой в списке сверху.")
                return
        self.rec_btn.configure(text="СТОП  (пробел)")
        self._pump_level()

    def _pump_level(self) -> None:
        if not self.rec.active:
            return
        self._draw_level(self.rec.read_peak())
        self._level_job = self.after(60, self._pump_level)

    def _draw_level(self, peak: float) -> None:
        self.level.delete("all")
        w = max(1, self.level.winfo_width())
        filled = int(min(1.0, peak) * w)
        color = RED if peak > 0.98 else (GREEN if peak > 0.15 else AMBER)
        self.level.create_rectangle(0, 0, w, 16, fill=BG, outline="")
        self.level.create_rectangle(0, 0, filled, 16, fill=color, outline="")
        if peak > 0.98:
            self.level_lbl.configure(text="перегруз, говори тише")
        elif peak > 0.5:
            self.level_lbl.configure(text="отличный уровень")
        elif peak > 0.15:
            self.level_lbl.configure(text="нормально")
        else:
            self.level_lbl.configure(text="тихо, говори ближе к микрофону")

    def _stop_record(self) -> None:
        if self._level_job:
            self.after_cancel(self._level_job)
            self._level_job = None
        rate = self.rec.rate
        audio = self.rec.stop()
        self.rec_btn.configure(text="ЗАПИСАТЬ  (пробел)")
        self._draw_level(0.0)

        if audio.size < rate * rec.MIN_DURATION:
            self.level_lbl.configure(text="слишком коротко, не сохранил")
            return

        # process сам приведёт к 48 кГц, если писали на другой частоте.
        audio = rec.process(audio, rate)
        fid, _, _ = self.plan[self.idx]
        rec.save_wav(self.sounds / f"{fid}.wav", audio)
        self._show()
        self._play_audio(audio, rec.SAMPLE_RATE,
                         f"сохранено, {audio.size / rec.SAMPLE_RATE:.2f} сек")
        # Сразу переходим дальше - так банк наговаривается потоком.
        self.after(400, lambda: self._go(1))

    def _play(self, radio: bool = False) -> None:
        """radio=True - как это прозвучит в игре, через эффект рации."""
        if not self.plan:
            return
        if self.rec.active:
            self.level_lbl.configure(text="идёт запись, останови её пробелом")
            return

        fid, _, _ = self.plan[self.idx]
        path = self.sounds / f"{fid}.wav"
        if not path.exists():
            self.level_lbl.configure(
                text="эта фраза ещё не записана - жми ПРОБЕЛ")
            return

        try:
            audio, rate = rec.load_wav(path)
        except Exception as exc:
            self.level_lbl.configure(text=f"файл не читается: {exc}")
            return

        note = "слушаешь запись"
        if radio:
            audio = radio_fx.apply(audio, rate, self.radio_cfg,
                                   seed=abs(hash(fid)) % (2 ** 32))
            note = "так это прозвучит в игре"
        self._play_audio(audio, rate, note)

    def _on_close(self) -> None:
        if self.rec.active:
            self.rec.stop()
        try:
            sd.stop()
        except Exception:
            pass
        self.destroy()


def run_recorder(root_dir: Path) -> int:
    RecorderApp(root_dir).mainloop()
    return 0
