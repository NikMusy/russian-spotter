"""Проигрывание фраз с приоритетами.

Споттерские вызовы (приоритет 0) прерывают любую болтовню - услышать
"слева" важнее, чем дослушать про температуру трассы.

Незаписанные фразы просто пропускаются, поэтому банк можно наговаривать
частями: споттер работает с тем, что уже есть.
"""

from __future__ import annotations

import itertools
import os
import random
import threading
import time
from pathlib import Path

import numpy as np

from . import radio as radio_fx
from .phrases import BY_ID, MEME_FOR, P_SPOTTER
from .radio import RadioConfig

# pygame печатает баннер в stdout при импорте - он тут не нужен.
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

MIXER_RATE = 48000


def _resample(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Линейная интерполяция.

    Нужна на случай, если в sounds/ положили файл не с 48 кГц: микшер
    открыт на фиксированной частоте и иначе воспроизведёт его не с той
    скоростью. Рекордер пишет сразу 48 кГц, так что обычно не срабатывает.
    """
    if src_rate == dst_rate or audio.size == 0:
        return audio
    duration = audio.size / src_rate
    dst_len = int(round(duration * dst_rate))
    src_idx = np.linspace(0, audio.size - 1, dst_len)
    return np.interp(src_idx, np.arange(audio.size), audio).astype(np.float32)


def _text_of(resolved_id: str) -> str:
    """Текст фразы по её id, включая матерные дубли."""
    if resolved_id.endswith("__hard"):
        base = BY_ID.get(resolved_id[: -len("__hard")])
        if base is not None:
            return base.hard or base.text
    phrase = BY_ID.get(resolved_id)
    return phrase.text if phrase else resolved_id


class Item:
    __slots__ = ("priority", "seq", "ids", "gap")

    def __init__(self, priority: int, seq: int, ids: list[str], gap: float):
        self.priority = priority
        self.seq = seq
        self.ids = ids
        self.gap = gap


class Player:
    def __init__(self, sounds_dir: Path, swearing: bool = True,
                 volume: float = 1.0, verbose: bool = True,
                 on_message=None, radio: RadioConfig | None = None,
                 memes: bool = True, meme_chance: float = 0.25,
                 voicepack_dir: Path | None = None) -> None:
        self.sounds_dir = sounds_dir
        # Откуда брать фразу, которую сам не записал. Свои записи всегда
        # в приоритете: банк можно наговаривать по кусочку, а пробелы
        # закрывает чужой голос.
        self.voicepack_dir = voicepack_dir
        self.swearing = swearing
        self.verbose = verbose
        # Куда сообщать, что прозвучало. GUI подставляет сюда свой приёмник.
        self.on_message = on_message
        self.radio = radio or RadioConfig()
        self.memes = memes
        self.meme_chance = meme_chance

        pygame.mixer.init(frequency=MIXER_RATE, size=-16, channels=1,
                          buffer=512)
        pygame.mixer.set_num_channels(4)
        self._channel = pygame.mixer.Channel(0)
        self._channel.set_volume(volume)

        self._cache: dict[str, pygame.mixer.Sound | None] = {}
        self._queue: list[Item] = []
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._counter = itertools.count()
        self._playing_priority = 99
        self._missing: set[str] = set()

        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()


    def _resolve(self, phrase_id: str) -> str:
        """Выбирает, что реально прозвучит: мем, мат или обычная фраза."""
        phrase_id = self._maybe_meme(phrase_id)

        if not self.swearing:
            return phrase_id
        phrase = BY_ID.get(phrase_id)
        if phrase is None or not phrase.hard:
            return phrase_id
        hard_id = f"{phrase_id}__hard"
        if self._find(hard_id) is not None:
            return hard_id
        return phrase_id

    def _maybe_meme(self, phrase_id: str) -> str:
        """Изредка подменяет фразу мемом - если он вообще записан."""
        if not self.memes or random.random() >= self.meme_chance:
            return phrase_id
        options = MEME_FOR.get(phrase_id)
        if not options:
            return phrase_id
        have = [m for m in options if self._find(m) is not None]
        return random.choice(have) if have else phrase_id

    def _find(self, phrase_id: str) -> Path | None:
        """Где лежит фраза: сначала свои записи, потом голосовой пак."""
        own = self.sounds_dir / f"{phrase_id}.wav"
        if own.exists():
            return own
        if self.voicepack_dir is not None:
            shared = self.voicepack_dir / f"{phrase_id}.wav"
            if shared.exists():
                return shared
        return None

    def _sound(self, phrase_id: str) -> pygame.mixer.Sound | None:
        if phrase_id in self._cache:
            return self._cache[phrase_id]
        path = self._find(phrase_id)
        sound: pygame.mixer.Sound | None = None
        if path is not None:
            try:
                sound = self._load(path, phrase_id)
            except (pygame.error, OSError, ValueError, EOFError):
                sound = None
        self._cache[phrase_id] = sound
        return sound

    def _load(self, path: Path, phrase_id: str) -> pygame.mixer.Sound:
        if not self.radio.enabled:
            return pygame.mixer.Sound(str(path))

        from .recording import load_wav

        # Микшер открывается с тем, что дало устройство, а не с тем, что мы
        # просили: моно запросто станет стерео. Спрашиваем факт.
        info = pygame.mixer.get_init()
        rate_out, _size, channels = info if info else (MIXER_RATE, -16, 1)

        audio, rate = load_wav(path)
        if rate != rate_out:
            audio = _resample(audio, rate, rate_out)
        # Seed от имени фразы: шум у каждой свой, но одинаковый от запуска
        # к запуску - иначе кэш давал бы разное звучание.
        processed = radio_fx.apply(audio, rate_out, self.radio,
                                   seed=abs(hash(phrase_id)) % (2 ** 32))
        pcm = (np.clip(processed, -1.0, 1.0) * 32767).astype(np.int16)
        if channels == 2:
            pcm = np.repeat(pcm[:, None], 2, axis=1)
        return pygame.sndarray.make_sound(np.ascontiguousarray(pcm))

    def reload_bank(self) -> None:
        """Сбрасывает кэш - после смены настроек рации или перезаписи фраз."""
        self._cache.clear()
        self._missing.clear()

    def prewarm(self) -> None:
        """Прогревает кэш в фоне.

        Обработка рации стоит несколько миллисекунд на фразу - для
        споттерского "слева" это уже заметно, поэтому греем заранее.
        """
        def work() -> None:
            # Греем всё, что записано, включая матерные дубли: какой из
            # вариантов выпадет в гонке, заранее неизвестно.
            for pid in list(BY_ID):
                if self._stop.is_set():
                    return
                self._sound(pid)
                self._sound(f"{pid}__hard")

        threading.Thread(target=work, daemon=True).start()

    def available(self) -> tuple[int, int]:
        """Сколько фраз доступно (свои + голосовой пак) из скольких всего."""
        have = sum(1 for pid in BY_ID if self._find(pid) is not None)
        return have, len(BY_ID)

    def own_count(self) -> int:
        return sum(1 for pid in BY_ID
                   if (self.sounds_dir / f"{pid}.wav").exists())


    def say(self, *phrase_ids: str, priority: int | None = None,
            gap: float = 0.04) -> None:
        """Ставит фразу (или склейку фраз) в очередь."""
        ids = [p for p in phrase_ids if p]
        if not ids:
            return
        if priority is None:
            first = BY_ID.get(ids[0])
            priority = first.priority if first else 2

        item = Item(priority, next(self._counter), ids, gap)
        with self._lock:
            # Споттер не копится в очереди - важен только свежий вызов.
            if priority == P_SPOTTER:
                self._queue = [i for i in self._queue
                               if i.priority != P_SPOTTER]
            self._queue.append(item)
            interrupt = (priority == P_SPOTTER
                         and self._playing_priority > P_SPOTTER)
        if interrupt:
            self._channel.stop()
        self._wake.set()

    def set_volume(self, volume: float) -> None:
        try:
            self._channel.set_volume(max(0.0, min(1.0, volume)))
        except pygame.error:
            pass

    def busy(self) -> bool:
        with self._lock:
            return bool(self._queue) or self._channel.get_busy()

    def shutdown(self) -> None:
        self._stop.set()
        self._wake.set()
        try:
            self._channel.stop()
            pygame.mixer.quit()
        except pygame.error:
            pass


    def _worker(self) -> None:
        while not self._stop.is_set():
            with self._lock:
                if not self._queue:
                    item = None
                else:
                    self._queue.sort(key=lambda i: (i.priority, i.seq))
                    item = self._queue.pop(0)
                    self._playing_priority = item.priority

            if item is None:
                self._playing_priority = 99
                self._wake.wait(0.05)
                self._wake.clear()
                continue

            self._play(item)
            self._playing_priority = 99

    def _play(self, item: Item) -> None:
        spoken: list[str] = []
        for phrase_id in item.ids:
            if self._stop.is_set():
                return
            resolved = self._resolve(phrase_id)
            sound = self._sound(resolved)
            if sound is None:
                if phrase_id not in self._missing:
                    self._missing.add(phrase_id)
                    self._report(f"[нет файла] {phrase_id}.wav", missing=True)
                continue

            self._channel.play(sound)
            spoken.append(resolved)
            while self._channel.get_busy():
                if self._stop.is_set():
                    return
                # Нас прервал споттер - бросаем остаток склейки.
                with self._lock:
                    preempted = any(i.priority < item.priority
                                    for i in self._queue)
                if preempted:
                    self._channel.stop()
                    return
                time.sleep(0.005)
            if item.gap:
                time.sleep(item.gap)

        if spoken:
            self._report(" ".join(_text_of(s) for s in spoken))

    def _report(self, text: str, missing: bool = False) -> None:
        if self.on_message is not None:
            self.on_message(text, missing)
        elif self.verbose:
            print(f"  {text}" if missing else f"  [радио] {text}")
