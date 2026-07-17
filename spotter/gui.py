"""Окно споттера. Движок крутится в фоне, сюда шлёт сообщения."""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .audio.phrases import (
    ALL_SIMS, PHRASES, SIM_F1, SIM_LMU, SIM_TITLES, recording_plan,
)
from .audio.radio import RadioConfig
from .engine import Engine

# Симы, у которых есть адаптер телеметрии. Для остальных фразы записывать
# можно, но слушать пока нечего.
SUPPORTED = {SIM_F1, SIM_LMU}

# Кому нужен UDP-порт: LMU читается через разделяемую память.
NEEDS_PORT = {SIM_F1}

BG = "#1b1e23"
BG_PANEL = "#23272e"
BG_LOG = "#15171b"
FG = "#e6e8ec"
FG_DIM = "#8b929e"
RED = "#e10600"
GREEN = "#28c76f"
AMBER = "#f0a020"


class App(tk.Tk):
    def __init__(self, root_dir: Path, cfg: dict) -> None:
        super().__init__()
        self.root_dir = root_dir
        self.cfg = cfg
        self.sounds_dir = root_dir / "sounds"

        self.engine: Engine | None = None
        self.thread: threading.Thread | None = None
        self.messages: queue.Queue = queue.Queue()
        self.voicepacks_dir = root_dir / "voicepacks"

        self.title("Русский споттер")
        self.configure(bg=BG)
        self.geometry("760x620")
        self.minsize(680, 540)

        icon = root_dir / "tools" / "icon.png"
        if icon.exists():
            try:
                self._icon_img = tk.PhotoImage(file=str(icon))
                self.iconphoto(True, self._icon_img)
            except tk.TclError:
                pass

        self._style()
        self._build()
        self._refresh_bank()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(80, self._drain)

    # ------------------------------------------------------------- стиль

    def _style(self) -> None:
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", background=BG, foreground=FG,
                    fieldbackground=BG_PANEL, borderwidth=0)
        s.configure("TFrame", background=BG)
        s.configure("Panel.TFrame", background=BG_PANEL)
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("Panel.TLabel", background=BG_PANEL, foreground=FG)
        s.configure("Dim.TLabel", background=BG, foreground=FG_DIM)
        s.configure("DimPanel.TLabel", background=BG_PANEL, foreground=FG_DIM)
        s.configure("Title.TLabel", background=BG, foreground=FG,
                    font=("Segoe UI Semibold", 15))
        s.configure("TCheckbutton", background=BG_PANEL, foreground=FG)
        s.map("TCheckbutton", background=[("active", BG_PANEL)])
        s.configure("TCombobox", fieldbackground=BG_PANEL, background=BG_PANEL,
                    foreground=FG, arrowcolor=FG)
        s.configure("TScale", background=BG_PANEL, troughcolor=BG)
        s.configure("Go.TButton", background=RED, foreground="#ffffff",
                    font=("Segoe UI Semibold", 11), padding=(18, 9))
        s.map("Go.TButton", background=[("active", "#ff2418"),
                                        ("disabled", "#4a2320")])
        s.configure("Flat.TButton", background=BG_PANEL, foreground=FG,
                    padding=(12, 7))
        s.map("Flat.TButton", background=[("active", "#2e343d"),
                                          ("disabled", BG_PANEL)])

    # ------------------------------------------------------------ разметка

    def _build(self) -> None:
        head = ttk.Frame(self, padding=(16, 14, 16, 8))
        head.pack(fill="x")
        ttk.Label(head, text="РУССКИЙ СПОТТЕР", style="Title.TLabel").pack(side="left")
        self.bank_lbl = ttk.Label(head, text="", style="Dim.TLabel")
        self.bank_lbl.pack(side="right")

        # --- панель управления
        top = ttk.Frame(self, style="Panel.TFrame", padding=14)
        top.pack(fill="x", padx=16)

        ttk.Label(top, text="Сим", style="DimPanel.TLabel").grid(
            row=0, column=0, sticky="w", padx=(0, 8))
        self.sim_var = tk.StringVar(value=self._sim_label(SIM_F1))
        self.sim_box = ttk.Combobox(top, textvariable=self.sim_var, width=34,
                                    state="readonly",
                                    values=[self._sim_label(s) for s in ALL_SIMS])
        self.sim_box.grid(row=0, column=1, sticky="w")
        self.sim_box.bind("<<ComboboxSelected>>", self._on_sim)

        ttk.Label(top, text="Порт", style="DimPanel.TLabel").grid(
            row=0, column=2, sticky="e", padx=(18, 8))
        self.port_var = tk.StringVar(value=str(self.cfg.get("port", 20777)))
        tk.Entry(top, textvariable=self.port_var, width=8, bg=BG, fg=FG,
                 insertbackground=FG, relief="flat",
                 highlightthickness=1, highlightbackground="#3a4049").grid(
            row=0, column=3, sticky="w", ipady=4)

        ttk.Label(top, text="Голос", style="DimPanel.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=(10, 0))
        self.packs = self._find_packs()
        self.pack_var = tk.StringVar()
        self.pack_box = ttk.Combobox(top, textvariable=self.pack_var,
                                     width=34, state="readonly",
                                     values=[p[0] for p in self.packs])
        self.pack_box.grid(row=1, column=1, sticky="w", pady=(10, 0))
        self.pack_box.bind("<<ComboboxSelected>>", self._on_pack)
        self.pack_box.current(self._initial_pack())

        # --- кнопки и статус
        row = ttk.Frame(self, padding=(16, 12, 16, 4))
        row.pack(fill="x")
        self.go_btn = ttk.Button(row, text="СТАРТ", style="Go.TButton",
                                 command=self._toggle)
        self.go_btn.pack(side="left")

        self.dot = tk.Canvas(row, width=14, height=14, bg=BG,
                             highlightthickness=0)
        self.dot.pack(side="left", padx=(16, 6))
        self._dot_id = self.dot.create_oval(2, 2, 12, 12, fill=FG_DIM,
                                            outline="")
        self.status_lbl = ttk.Label(row, text="остановлен", style="Dim.TLabel")
        self.status_lbl.pack(side="left")

        # --- настройки
        opts = ttk.Frame(self, style="Panel.TFrame", padding=14)
        opts.pack(fill="x", padx=16, pady=(8, 0))

        self.swear_var = tk.BooleanVar(value=self.cfg.get("swearing", True))
        ttk.Checkbutton(opts, text="Мат", variable=self.swear_var,
                        command=self._on_swear).pack(side="left")

        self.meme_var = tk.BooleanVar(value=self.cfg.get("memes", True))
        ttk.Checkbutton(opts, text="Мемы", variable=self.meme_var,
                        command=self._on_memes).pack(side="left", padx=(16, 0))

        self.radio_cfg = RadioConfig.from_dict(self.cfg.get("radio"))
        self.radio_var = tk.BooleanVar(value=self.radio_cfg.enabled)
        ttk.Checkbutton(opts, text="Рация", variable=self.radio_var,
                        command=self._on_radio).pack(side="left", padx=(16, 0))

        ttk.Label(opts, text="Шипение", style="DimPanel.TLabel").pack(
            side="left", padx=(16, 6))
        self.noise_var = tk.DoubleVar(value=self.radio_cfg.noise)
        noise = ttk.Scale(opts, from_=0.0, to=0.2, variable=self.noise_var,
                          length=110)
        noise.pack(side="left")
        # Пересобирать банк на каждый пиксель ползунка незачем - ждём,
        # пока отпустят.
        noise.bind("<ButtonRelease-1>", self._on_noise)

        ttk.Label(opts, text="Громкость", style="DimPanel.TLabel").pack(
            side="left", padx=(20, 8))
        self.vol_var = tk.DoubleVar(value=self.cfg.get("volume", 1.0))
        ttk.Scale(opts, from_=0.0, to=1.0, variable=self.vol_var,
                  command=self._on_volume, length=130).pack(side="left")
        self.vol_lbl = ttk.Label(opts, text="", style="DimPanel.TLabel")
        self.vol_lbl.pack(side="left", padx=(10, 0))
        self._on_volume()

        # --- лог
        ttk.Label(self, text="Радио", style="Dim.TLabel").pack(
            anchor="w", padx=18, pady=(14, 4))
        wrap = tk.Frame(self, bg="#3a4049", padx=1, pady=1)
        wrap.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        self.log = tk.Text(wrap, bg=BG_LOG, fg=FG, relief="flat",
                           font=("Consolas", 10), wrap="word", padx=10,
                           pady=8, state="disabled", height=12)
        self.log.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(wrap, command=self.log.yview)
        sb.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=sb.set)
        self.log.tag_configure("time", foreground=FG_DIM)
        self.log.tag_configure("spot", foreground="#ff5b52",
                               font=("Consolas", 10, "bold"))
        self.log.tag_configure("miss", foreground=AMBER)
        self.log.tag_configure("sys", foreground=FG_DIM)

        # --- низ
        bottom = ttk.Frame(self, padding=(16, 0, 16, 14))
        bottom.pack(fill="x")
        ttk.Button(bottom, text="Записать фразы", style="Flat.TButton",
                   command=self._open_recorder).pack(side="left")
        ttk.Button(bottom, text="Папка со звуками", style="Flat.TButton",
                   command=self._open_sounds).pack(side="left", padx=8)
        ttk.Button(bottom, text="Очистить лог", style="Flat.TButton",
                   command=self._clear_log).pack(side="right")

    # -------------------------------------------------------------- утиль

    def _sim_label(self, sim: str) -> str:
        tail = "" if sim in SUPPORTED else "   (нет адаптера)"
        return SIM_TITLES[sim] + tail

    def _current_sim(self) -> str:
        label = self.sim_var.get()
        for s in ALL_SIMS:
            if self._sim_label(s) == label:
                return s
        return SIM_F1

    def _find_packs(self) -> list[tuple[str, Path | None]]:
        """Голосовые паки: чем закрывать фразы, которые сам не записал."""
        packs: list[tuple[str, Path | None]] = [("только свой голос", None)]
        if self.voicepacks_dir.is_dir():
            for d in sorted(self.voicepacks_dir.iterdir()):
                if d.is_dir() and any(d.glob("*.wav")):
                    n = len(list(d.glob("*.wav")))
                    packs.append((f"{d.name}  ({n} фраз)", d))
        return packs

    def _initial_pack(self) -> int:
        """Какой голос выбрать при запуске.

        На первом запуске своих записей ещё нет, и вариант "только свой
        голос" означал бы полную тишину. Поэтому по умолчанию берём
        готовый пак - споттер заговорит сразу.
        """
        saved = self.cfg.get("voicepack")
        if saved is None:
            own = any(self.sounds_dir.glob("*.wav"))
            return 0 if own or len(self.packs) < 2 else 1
        return next((i for i, (_, d) in enumerate(self.packs)
                     if (d.name if d else "") == saved), 0)

    def _pack_dir(self) -> Path | None:
        pos = self.pack_box.current()
        if pos < 0 or pos >= len(self.packs):
            return None
        return self.packs[pos][1]

    def _on_pack(self, _e=None) -> None:
        d = self._pack_dir()
        self.cfg["voicepack"] = d.name if d else ""
        if self.engine is not None:
            self.engine.player.voicepack_dir = d
            self.engine.player.reload_bank()
            self.engine.player.prewarm()
        self._refresh_bank()
        self._save_cfg()

    def _refresh_bank(self) -> None:
        sim = self._current_sim()
        plan = recording_plan(sim=sim)
        own = sum(1 for fid, _, _ in plan
                  if (self.sounds_dir / f"{fid}.wav").exists())
        pack = self._pack_dir()
        if pack is None:
            self.bank_lbl.configure(text=f"записано {own} из {len(plan)} фраз")
            return
        total = sum(1 for fid, _, _ in plan
                    if (self.sounds_dir / f"{fid}.wav").exists()
                    or (pack / f"{fid}.wav").exists())
        self.bank_lbl.configure(
            text=f"свои {own}, всего {total} из {len(plan)} фраз")

    def _say(self, text: str, tag: str = "sys") -> None:
        self.messages.put((text, tag))

    # ------------------------------------------------------------ события

    def _on_sim(self, _e=None) -> None:
        sim = self._current_sim()
        self._refresh_bank()
        if sim not in SUPPORTED:
            self._say(f"{SIM_TITLES[sim]}: телеметрию читать пока не умею. "
                      f"Фразы для этого сима записывать уже можно.", "miss")
        if self.engine is not None:
            self._say("Сим сменён - перезапусти споттер.", "sys")

    def _on_swear(self) -> None:
        self.cfg["swearing"] = self.swear_var.get()
        if self.engine is not None:
            self.engine.player.swearing = self.swear_var.get()
        self._save_cfg()

    def _on_memes(self) -> None:
        self.cfg["memes"] = self.meme_var.get()
        if self.engine is not None:
            self.engine.player.memes = self.meme_var.get()
        self._save_cfg()

    def _on_radio(self, _e=None) -> None:
        self.radio_cfg.enabled = self.radio_var.get()
        self._apply_radio()

    def _on_noise(self, _e=None) -> None:
        value = round(self.noise_var.get(), 3)
        if abs(value - self.radio_cfg.noise) < 0.001:
            return
        self.radio_cfg.noise = value
        self._apply_radio()

    def _apply_radio(self) -> None:
        """Новые настройки рации - старый кэш звуков недействителен."""
        self.cfg["radio"] = self.radio_cfg.to_dict()
        if self.engine is not None:
            self.engine.player.radio = self.radio_cfg
            self.engine.player.reload_bank()
            self.engine.player.prewarm()
            self._say("Рация: "
                      + ("включена" if self.radio_cfg.enabled else "выключена")
                      + f", шипение {int(self.radio_cfg.noise * 100)}", "sys")
        self._save_cfg()

    def _on_volume(self, _e=None) -> None:
        v = self.vol_var.get()
        self.vol_lbl.configure(text=f"{int(v * 100)}%")
        self.cfg["volume"] = round(v, 2)
        if self.engine is not None:
            self.engine.player.set_volume(v)

    def _clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _open_recorder(self) -> None:
        exe = self.root_dir / "recorder.exe"
        try:
            if exe.exists():
                subprocess.Popen([str(exe)], cwd=str(self.root_dir))
            else:
                subprocess.Popen([sys.executable,
                                  str(self.root_dir / "tools" / "recorder.py")],
                                 cwd=str(self.root_dir))
        except OSError as exc:
            self._say(f"Не запускается рекордер: {exc}", "miss")

    def _open_sounds(self) -> None:
        self.sounds_dir.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.Popen(["explorer", str(self.sounds_dir)])
        except OSError as exc:
            self._say(f"Не открыть папку: {exc}", "miss")

    # -------------------------------------------------------- старт/стоп

    def _toggle(self) -> None:
        if self.engine is None:
            self._start()
        else:
            self._stop()

    def _start(self) -> None:
        sim = self._current_sim()
        if sim not in SUPPORTED:
            self._say(f"{SIM_TITLES[sim]}: адаптера нет, слушать нечего.",
                      "miss")
            return

        port = 20777
        if sim in NEEDS_PORT:
            try:
                port = int(self.port_var.get())
                if not (1024 <= port <= 65535):
                    raise ValueError
            except ValueError:
                self._say("Порт должен быть числом от 1024 до 65535.", "miss")
                return

        self.sounds_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.engine = Engine(
                sounds_dir=self.sounds_dir, port=port,
                swearing=self.swear_var.get(), volume=self.vol_var.get(),
                verbose=False, radio=self.radio_cfg, sim=sim,
                memes=self.meme_var.get(),
                meme_chance=self.cfg.get("meme_chance", 0.25),
                voicepack_dir=self._pack_dir(),
                on_message=lambda text, missing: self.messages.put(
                    (text, "miss" if missing else "spot")),
                on_status=lambda ok, info: self.messages.put(
                    ("__status__", (ok, info))),
            )
        except Exception as exc:  # порт занят, нет звукового устройства
            self._say(f"Не стартует: {exc}", "miss")
            self.engine = None
            return

        have, _ = self.engine.player.available()
        if have == 0:
            self._say("Ни одной фразы нет - споттер будет молчать. Жми "
                      "«Записать фразы» или выбери голос сверху.", "miss")

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

        self.go_btn.configure(text="СТОП")
        self.sim_box.configure(state="disabled")
        if sim in NEEDS_PORT:
            self._set_dot(AMBER, f"слушаю порт {port}")
        else:
            self._set_dot(AMBER, "жду игру")
        self._save_cfg()

    def _run(self) -> None:
        try:
            self.engine.run()
        except Exception as exc:
            self.messages.put((f"Движок упал: {exc}", "miss"))
            self.messages.put(("__status__", (False, "ошибка")))

    def _stop(self) -> None:
        if self.engine is not None:
            self.engine.shutdown()
            self.engine = None
        if self.thread is not None:
            self.thread.join(timeout=2.0)
            self.thread = None
        self.go_btn.configure(text="СТАРТ")
        self.sim_box.configure(state="readonly")
        self._set_dot(FG_DIM, "остановлен")
        self._refresh_bank()

    def _set_dot(self, color: str, text: str) -> None:
        self.dot.itemconfigure(self._dot_id, fill=color)
        self.status_lbl.configure(text=text)

    # ---------------------------------------------------------- очередь

    def _drain(self) -> None:
        """Тянет сообщения из фонового потока в окно."""
        while True:
            try:
                text, tag = self.messages.get_nowait()
            except queue.Empty:
                break
            if text == "__status__":
                ok, info = tag
                self._set_dot(GREEN if ok else AMBER, info)
                continue
            self._append(text, tag)
        self.after(80, self._drain)

    def _append(self, text: str, tag: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", time.strftime("%H:%M:%S  "), "time")
        self.log.insert("end", text + "\n", tag)
        # Не даём логу расти бесконечно за долгую гонку.
        if int(self.log.index("end-1c").split(".")[0]) > 400:
            self.log.delete("1.0", "100.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ------------------------------------------------------------ выход

    def _save_cfg(self) -> None:
        try:
            self.cfg["port"] = int(self.port_var.get())
        except ValueError:
            pass
        from .__main__ import save_config
        save_config(self.root_dir / "config.json", self.cfg)

    def _on_close(self) -> None:
        self._save_cfg()
        if self.engine is not None:
            self.engine.shutdown()
        self.destroy()


def run_gui(root_dir: Path, cfg: dict) -> int:
    App(root_dir, cfg).mainloop()
    return 0
