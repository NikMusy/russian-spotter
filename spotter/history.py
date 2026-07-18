"""История заездов.

Пишется в history.json рядом с exe. Одна запись - одна сессия: где, что за
сессия, с какого места стартовал и каким приехал.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from .audio.phrases import SIM_TITLES
from .sims import tracks
from .udp.packets import SessionType

SESSION_TITLES = {
    SessionType.P1: "Практика",
    SessionType.P2: "Практика",
    SessionType.P3: "Практика",
    SessionType.SHORT_P: "Практика",
    SessionType.Q1: "Квалификация",
    SessionType.Q2: "Квалификация",
    SessionType.Q3: "Квалификация",
    SessionType.SHORT_Q: "Квалификация",
    SessionType.OSQ: "Квалификация",
    SessionType.RACE: "Гонка",
    SessionType.RACE_2: "Гонка",
    SessionType.RACE_3: "Гонка",
    SessionType.TIME_TRIAL: "Хотлап",
}

RACE_SESSIONS = (SessionType.RACE, SessionType.RACE_2, SessionType.RACE_3)


@dataclass
class Entry:
    """Одна сессия."""
    date: str = ""
    sim: str = "lmu"
    track: str = "track_unknown"   # id фразы
    session_type: int = 0
    grid: int = 0                  # стартовая позиция (итог квалификации)
    finish: int = 0                # финишная
    laps: int = 0
    best_lap_ms: int = 0
    car_class: str = ""
    penalties: int = 0

    # --- как показать в окне

    @property
    def when(self) -> str:
        try:
            return datetime.fromisoformat(self.date).strftime("%d.%m %H:%M")
        except ValueError:
            return self.date[:16]

    @property
    def sim_title(self) -> str:
        return SIM_TITLES.get(self.sim, self.sim)

    @property
    def track_title(self) -> str:
        return tracks.title(self.track)

    @property
    def flag(self) -> str:
        return tracks.flag(self.track)

    @property
    def session_title(self) -> str:
        return SESSION_TITLES.get(self.session_type, "Заезд")

    @property
    def is_race(self) -> bool:
        return self.session_type in RACE_SESSIONS

    @property
    def gained(self) -> int:
        """Сколько мест отыграл: плюс - обогнал, минус - потерял."""
        if not self.grid or not self.finish:
            return 0
        return self.grid - self.finish

    @property
    def best_lap(self) -> str:
        if self.best_lap_ms <= 0:
            return "-"
        total = self.best_lap_ms / 1000
        return f"{int(total // 60)}:{total % 60:06.3f}"


def load(path: Path) -> list[Entry]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    out = []
    for item in raw:
        try:
            out.append(Entry(**item))
        except TypeError:
            continue     # запись из старой версии - пропускаем
    return out


def save(path: Path, entries: list[Entry]) -> None:
    try:
        path.write_text(
            json.dumps([asdict(e) for e in entries], ensure_ascii=False,
                       indent=1),
            encoding="utf-8")
    except OSError:
        pass


def append(path: Path, entry: Entry, limit: int = 200) -> list[Entry]:
    entries = load(path)
    entries.append(entry)
    entries = entries[-limit:]
    save(path, entries)
    return entries


@dataclass
class SessionTracker:
    """Следит за текущей сессией и отдаёт запись, когда она закончилась.

    Конца сессии как события нет ни в F1, ни в LMU (там просто меняется
    трасса или тип), поэтому пишем результат при смене сессии и при
    остановке движка.
    """

    current: Entry | None = None
    _key: tuple = field(default_factory=tuple)

    def update(self, state) -> Entry | None:
        """Возвращает завершённую запись, если сессия сменилась."""
        s = state.session
        me = state.me
        if s is None or me is None:
            return None
        if s.session_type == SessionType.UNKNOWN:
            return None

        track = (tracks.by_name(state.track_name) if state.track_name
                 else tracks.by_f1_id(s.track_id))
        key = (state.sim, track, s.session_type)

        finished = None
        if key != self._key:
            finished = self.finish()      # сессия сменилась - закрываем ту
            self._key = key
            self.current = Entry(
                date=datetime.now().isoformat(timespec="seconds"),
                sim=state.sim, track=track, session_type=s.session_type,
            )

        if self.current is not None:
            # Держим свежими: сессия может оборваться в любой момент.
            # В мультиклассе считаем позицию в классе, а не общую.
            self.current.finish = state.my_class_position
            self.current.laps = max(self.current.laps, me.current_lap)
            self.current.penalties = me.penalties
            self.current.car_class = state.my_class
            # Старт: в одноклассовой гонке - реальная решётка; в
            # мультиклассе её из API не вытащить, поэтому фиксируем
            # классовую позицию с первого кадра как ориентир.
            if self.current.grid == 0:
                if state.is_multiclass:
                    self.current.grid = state.my_class_position
                elif me.grid_position:
                    self.current.grid = me.grid_position
            if me.last_lap_ms > 0 and not me.lap_invalid:
                if (self.current.best_lap_ms == 0
                        or me.last_lap_ms < self.current.best_lap_ms):
                    self.current.best_lap_ms = me.last_lap_ms

        return finished

    def finish(self) -> Entry | None:
        """Закрывает текущую сессию. Пустые заезды не сохраняем."""
        entry, self.current = self.current, None
        if entry is None:
            return None
        if entry.laps < 1 or entry.finish < 1:
            return None      # заглянул в меню и вышел - это не заезд
        return entry
