"""Окно статистики: список заездов, откуда стартовал, куда приехал."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from . import history
from .audio.phrases import ALL_SIMS, SIM_TITLES

BG = "#1b1e23"
BG_PANEL = "#23272e"
BG_ROW = "#20242a"
FG = "#e6e8ec"
FG_DIM = "#8b929e"
RED = "#e10600"
GREEN = "#28c76f"
AMBER = "#f0a020"
GOLD = "#d4af37"


class StatsWindow(tk.Toplevel):
    def __init__(self, master, path: Path) -> None:
        super().__init__(master)
        self.path = path
        self.title("Статистика")
        self.configure(bg=BG)
        self.geometry("880x600")
        self.minsize(700, 420)

        self.filter_var = tk.StringVar(value="все симы")
        self.only_races = tk.BooleanVar(value=False)

        self._style()
        self._build()
        self.reload()

    def _style(self) -> None:
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("S.TFrame", background=BG)
        s.configure("SP.TFrame", background=BG_PANEL)
        s.configure("S.TLabel", background=BG, foreground=FG)
        s.configure("SDim.TLabel", background=BG, foreground=FG_DIM)
        s.configure("SPDim.TLabel", background=BG_PANEL, foreground=FG_DIM)
        s.configure("SBig.TLabel", background=BG_PANEL, foreground=FG,
                    font=("Segoe UI Semibold", 20))
        s.configure("STitle.TLabel", background=BG, foreground=FG,
                    font=("Segoe UI Semibold", 15))
        s.configure("S.TCheckbutton", background=BG, foreground=FG)
        s.map("S.TCheckbutton", background=[("active", BG)])
        s.configure("S.TCombobox", fieldbackground=BG_PANEL,
                    background=BG_PANEL, foreground=FG, arrowcolor=FG)
        s.configure("SFlat.TButton", background=BG_PANEL, foreground=FG,
                    padding=(10, 6))
        s.map("SFlat.TButton", background=[("active", "#2e343d")])

    def _build(self) -> None:
        head = ttk.Frame(self, style="S.TFrame", padding=(16, 14, 16, 8))
        head.pack(fill="x")
        ttk.Label(head, text="СТАТИСТИКА", style="STitle.TLabel").pack(side="left")

        ttk.Button(head, text="Обновить", style="SFlat.TButton",
                   command=self.reload).pack(side="right")
        ttk.Checkbutton(head, text="только гонки", variable=self.only_races,
                        style="S.TCheckbutton",
                        command=self.reload).pack(side="right", padx=10)
        box = ttk.Combobox(head, textvariable=self.filter_var, width=24,
                           state="readonly", style="S.TCombobox",
                           values=["все симы"] + [SIM_TITLES[s] for s in ALL_SIMS])
        box.pack(side="right")
        box.bind("<<ComboboxSelected>>", lambda e: self.reload())

        # --- плитки итогов
        self.cards = ttk.Frame(self, style="S.TFrame", padding=(16, 0, 16, 8))
        self.cards.pack(fill="x")

        # --- таблица
        wrap = tk.Frame(self, bg="#3a4049", padx=1, pady=1)
        wrap.pack(fill="both", expand=True, padx=16, pady=(6, 8))
        self.canvas = tk.Canvas(wrap, bg=BG_PANEL, highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(wrap, command=self.canvas.yview)
        sb.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=sb.set)
        self.rows = tk.Frame(self.canvas, bg=BG_PANEL)
        self.canvas.create_window((0, 0), window=self.rows, anchor="nw",
                                  tags="rows")
        self.rows.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            "rows", width=e.width))
        self.canvas.bind_all("<MouseWheel>", self._wheel)

        self.empty_lbl = ttk.Label(self, text="", style="SDim.TLabel")
        self.empty_lbl.pack(anchor="w", padx=18, pady=(0, 10))

    def _wheel(self, e) -> None:
        try:
            self.canvas.yview_scroll(int(-e.delta / 120), "units")
        except tk.TclError:
            pass

    # ---------------------------------------------------------------- данные

    def _selected(self) -> list[history.Entry]:
        entries = history.load(self.path)
        label = self.filter_var.get()
        if label != "все симы":
            sim = next((s for s in ALL_SIMS if SIM_TITLES[s] == label), None)
            entries = [e for e in entries if e.sim == sim]
        if self.only_races.get():
            entries = [e for e in entries if e.is_race]
        return list(reversed(entries))      # свежие сверху

    def reload(self) -> None:
        entries = self._selected()
        for w in self.cards.winfo_children():
            w.destroy()
        for w in self.rows.winfo_children():
            w.destroy()

        races = [e for e in entries if e.is_race and e.finish]
        wins = sum(1 for e in races if e.finish == 1)
        podiums = sum(1 for e in races if 1 <= e.finish <= 3)
        gained = sum(e.gained for e in races)
        best = min((e.finish for e in races), default=0)

        self._card("заездов", str(len(entries)), FG)
        self._card("гонок", str(len(races)), FG)
        self._card("побед", str(wins), GOLD if wins else FG_DIM)
        self._card("подиумов", str(podiums), GREEN if podiums else FG_DIM)
        self._card("лучший финиш", f"P{best}" if best else "-",
                   GOLD if best == 1 else FG)
        self._card("мест отыграно", f"{gained:+d}" if races else "-",
                   GREEN if gained > 0 else (RED if gained < 0 else FG_DIM))

        if not entries:
            self.empty_lbl.configure(
                text="Пока пусто. Проедь сессию со споттером - она появится "
                     "здесь сама.")
            return
        self.empty_lbl.configure(text=f"записей: {len(entries)}")

        self._header()
        for i, e in enumerate(entries):
            self._row(e, i)

    def _card(self, title: str, value: str, color: str) -> None:
        f = tk.Frame(self.cards, bg=BG_PANEL, padx=14, pady=8)
        f.pack(side="left", padx=(0, 8))
        tk.Label(f, text=value, bg=BG_PANEL, fg=color,
                 font=("Segoe UI Semibold", 18)).pack(anchor="w")
        tk.Label(f, text=title, bg=BG_PANEL, fg=FG_DIM,
                 font=("Segoe UI", 8)).pack(anchor="w")

    def _header(self) -> None:
        h = tk.Frame(self.rows, bg=BG_PANEL)
        h.pack(fill="x", pady=(6, 2))
        cols = [("когда", 90), ("", 26), ("трасса", 130), ("сим", 90),
                ("сессия", 92), ("старт", 52), ("финиш", 56), ("+/-", 46),
                ("кругов", 54), ("лучший круг", 90)]
        for name, w in cols:
            tk.Label(h, text=name, bg=BG_PANEL, fg=FG_DIM,
                     font=("Segoe UI", 8), width=w // 8, anchor="w").pack(
                side="left", padx=2)

    def _row(self, e: history.Entry, i: int) -> None:
        bg = BG_ROW if i % 2 else BG_PANEL
        r = tk.Frame(self.rows, bg=bg)
        r.pack(fill="x")

        def cell(text, w, color=FG, font=("Segoe UI", 9)):
            tk.Label(r, text=text, bg=bg, fg=color, font=font,
                     width=w // 8, anchor="w").pack(side="left", padx=2)

        cell(e.when, 90, FG_DIM)
        # Флаг отдельным шрифтом: Segoe UI Emoji рисует их цветными.
        tk.Label(r, text=e.flag, bg=bg, fg=FG,
                 font=("Segoe UI Emoji", 11), width=3, anchor="w").pack(
            side="left", padx=2)
        cell(e.track_title, 130)
        cell(e.sim_title.split(" /")[0], 90, FG_DIM)
        cell(e.session_title, 92, FG_DIM)
        cell(f"P{e.grid}" if e.grid else "-", 52, FG_DIM)

        fin_color = GOLD if e.finish == 1 else (
            GREEN if 2 <= e.finish <= 3 else FG)
        cell(f"P{e.finish}" if e.finish else "-", 56, fin_color,
             ("Segoe UI Semibold", 9))

        if e.is_race and e.grid and e.finish:
            g = e.gained
            cell(f"{g:+d}" if g else "0", 46,
                 GREEN if g > 0 else (RED if g < 0 else FG_DIM))
        else:
            cell("", 46)

        cell(str(e.laps), 54, FG_DIM)
        cell(e.best_lap, 90, FG_DIM)


def open_stats(master, path: Path) -> StatsWindow:
    return StatsWindow(master, path)
