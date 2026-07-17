"""Движок: слушает UDP, кормит состояние, гоняет правила."""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

from .audio.player import Player
from .audio.radio import RadioConfig
from .rules.base import Say
from .rules.car import DamageRule, FuelRule, PitLimiterRule, TyreRule
from .rules.classes import ClassPositionRule, ClassTrafficRule
from .rules.events import (
    EventRule, FlagRule, PenaltyRule, SafetyCarRule,
)
from .rules.proximity import ProximityRule
from .rules.race import GapRule, LapRule, PositionRule
from .rules.track import TrackAnnounceRule
from .rules.weather import WeatherRule
from .state import GameState
from .udp.packets import Event, PacketId, parse_packet

# Обычные правила гоняем реже, чем споттер: телеметрия сыплется до 60 раз
# в секунду, а про топливо думать так часто незачем.
SLOW_RULES_EVERY = 0.2
RECV_BUFFER = 4096

# Сколько ждать, прежде чем считать, что LMU действительно пропала.
# Отдельные битые кадры бывают постоянно - это не потеря связи.
LMU_LOST_AFTER = 2.0


class Engine:
    def __init__(self, sounds_dir: Path, port: int = 20777,
                 swearing: bool = True, volume: float = 1.0,
                 verbose: bool = True, on_message=None,
                 on_status=None, radio: RadioConfig | None = None,
                 sim: str = "f1", memes: bool = True,
                 meme_chance: float = 0.25,
                 voicepack_dir: Path | None = None) -> None:
        self.port = port
        self.sim = sim
        self.verbose = verbose
        self.on_status = on_status
        self.state = GameState(sim=sim)
        self.player = Player(sounds_dir, swearing=swearing, volume=volume,
                             verbose=verbose, on_message=on_message,
                             radio=radio, memes=memes,
                             meme_chance=meme_chance,
                             voicepack_dir=voicepack_dir)
        self.player.prewarm()

        self.proximity = ProximityRule()
        self.events = EventRule()
        self.slow_rules = [
            TrackAnnounceRule(),
            FlagRule(), SafetyCarRule(), PenaltyRule(),
            PitLimiterRule(), TyreRule(), FuelRule(), DamageRule(),
            WeatherRule(), PositionRule(), LapRule(), GapRule(),
            ClassTrafficRule(), ClassPositionRule(),
        ]

        self._sock: socket.socket | None = None
        self._last_slow = 0.0
        self._packets = 0
        self._was_connected = False
        self._stop = threading.Event()

    @property
    def say(self) -> Say:
        return self.player.say

    def _open(self) -> socket.socket:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.settimeout(0.5)
        s.bind(("0.0.0.0", self.port))
        return s

    def _status(self, connected: bool, info: str) -> None:
        if self.on_status is not None:
            self.on_status(connected, info)

    def run(self) -> None:
        self._stop.clear()
        if self.sim == "lmu":
            self._run_lmu()
        else:
            self._run_udp()

    # ------------------------------------------------------------- F1/UDP

    def _run_udp(self) -> None:
        self._sock = self._open()
        if self.verbose:
            print(f"Слушаю UDP на порту {self.port}. Ctrl+C - выход.")
            print()
        self._status(False, f"жду телеметрию на порту {self.port}")

        while not self._stop.is_set():
            try:
                data, _addr = self._sock.recvfrom(RECV_BUFFER)
            except socket.timeout:
                self._tick_idle()
                continue
            except OSError:
                break  # сокет закрыли из stop()

            self._handle(data)

    # ----------------------------------------------------- LMU/shared mem

    def _run_lmu(self) -> None:
        from .sims.lmu import LMUAdapter

        adapter = LMUAdapter()
        self._status(False, "жду Le Mans Ultimate")
        if self.verbose:
            print("Жду Le Mans Ultimate...")

        last_open_try = 0.0
        last_good = 0.0
        while not self._stop.is_set():
            now = time.monotonic()

            if not adapter.reader.connected:
                # Игра могла ещё не стартовать - пробуем раз в секунду.
                if now - last_open_try < 1.0:
                    time.sleep(0.1)
                    continue
                last_open_try = now
                if not adapter.open():
                    if self._was_connected:
                        self._was_connected = False
                        self._status(False, "LMU закрылась")
                    continue

            try:
                got = adapter.poll(self.state)
            except Exception:
                # Кадр не прочитался - пробуем следующий. Ронять споттер
                # посреди гонки из-за одного битого кадра нельзя.
                got = False

            if not got:
                # Одиночный битый кадр - это норма: память читается без
                # блокировки, и мы иногда попадаем в момент записи. Рвать
                # связь из-за него нельзя, иначе на каждом таком кадре
                # споттер заново здоровается ("связь есть...").
                if self._was_connected and now - last_good > LMU_LOST_AFTER:
                    self._was_connected = False
                    self._status(False, "LMU: ты не в сессии")
                time.sleep(1 / 120)
                continue

            last_good = now
            if not self._was_connected:
                self._was_connected = True
                self._status(True, "Le Mans Ultimate")
                if self.verbose:
                    print("Есть телеметрия: Le Mans Ultimate")
                self.player.say("radio_check")

            self._packets += 1
            self.proximity.update(self.state, self.say)

            if now - self._last_slow >= SLOW_RULES_EVERY:
                self._last_slow = now
                for rule in self.slow_rules:
                    rule.update(self.state, self.say)

            time.sleep(1 / 60)

        adapter.close()

    def _handle(self, data: bytes) -> None:
        parsed = parse_packet(data)
        if parsed is None:
            return
        header, payload = parsed

        if not self._was_connected:
            self._was_connected = True
            info = f"F1 {header.game_year}, формат {header.packet_format}"
            if self.verbose:
                print(f"Есть телеметрия: {info}")
            self._status(True, info)
            self.player.say("radio_check")

        self._packets += 1
        self.state.update(header, payload)

        if header.packet_id == PacketId.EVENT and isinstance(payload, Event):
            self.events.on_event(payload.code, self.state, self.say)
            return

        # Споттер - на каждом кадре движения, иначе он опоздает.
        if header.packet_id == PacketId.MOTION:
            self.proximity.update(self.state, self.say)

        now = time.monotonic()
        if now - self._last_slow >= SLOW_RULES_EVERY:
            self._last_slow = now
            for rule in self.slow_rules:
                rule.update(self.state, self.say)

    def _tick_idle(self) -> None:
        if self._was_connected and self.state.is_stale(5.0):
            self._was_connected = False
            self.state.connected = False
            if self.verbose:
                print("Телеметрия пропала. Жду...")
            self._status(False, "телеметрия пропала")

    def stop(self) -> None:
        """Просит цикл run() завершиться. Можно звать из другого потока."""
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass

    def shutdown(self) -> None:
        self._stop.set()
        self.player.shutdown()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
