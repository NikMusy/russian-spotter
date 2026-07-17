"""Запись с микрофона и обработка фразы.

Отдельно от интерфейса, чтобы окно рекордера занималось только кнопками.
"""

from __future__ import annotations

import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 48000
CHANNELS = 1

# Порог тишины для обрезки краёв, в долях от пика.
TRIM_THRESHOLD = 0.02
# Сколько тишины оставить по краям, сек.
TRIM_PAD = 0.06
# К какому пику подтягиваем громкость, чтобы фразы звучали ровно.
TARGET_PEAK = 0.89
# Короче этого - явно промах, а не фраза.
MIN_DURATION = 0.05


class Recorder:
    """Пишет с микрофона, пока не скажут стоп."""

    def __init__(self) -> None:
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self.peak = 0.0
        # На какой частоте реально пишем: не каждое устройство даёт 48 кГц.
        self.rate = SAMPLE_RATE

    @property
    def active(self) -> bool:
        return self._stream is not None

    def _callback(self, indata, frames, time_info, status) -> None:
        with self._lock:
            self._chunks.append(indata.copy())
            self.peak = max(self.peak, float(np.abs(indata).max()))

    def _open(self, device: int | None, rate: int,
              channels: int) -> sd.InputStream:
        stream = sd.InputStream(
            samplerate=rate, channels=channels, dtype="float32",
            callback=self._callback, blocksize=1024, device=device,
        )
        stream.start()
        return stream

    def start(self, device: int | None = None) -> None:
        self._chunks = []
        self.peak = 0.0

        info = sd.query_devices(device) if device is not None else None
        native = int(info["default_samplerate"]) if info else SAMPLE_RATE
        max_ch = int(info["max_input_channels"]) if info else CHANNELS
        channels = 1 if max_ch >= 1 else max_ch

        # Пробуем 48 кГц, а если устройство его не берёт - его родную
        # частоту: пересчитаем при сохранении. Иначе WASAPI-копии
        # микрофона падают с Invalid sample rate.
        attempts = [(SAMPLE_RATE, channels)]
        if native != SAMPLE_RATE:
            attempts.append((native, channels))
        if channels != 1:
            attempts.append((SAMPLE_RATE, 1))

        last: Exception | None = None
        for rate, ch in attempts:
            try:
                self._stream = self._open(device, rate, ch)
                self.rate = rate
                return
            except Exception as exc:      # sd бросает свои типы ошибок
                last = exc
        raise RuntimeError(last)

    def stop(self) -> np.ndarray:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._chunks)
        if audio.ndim > 1 and audio.shape[1] > 1:
            audio = audio.mean(axis=1)      # если дали только стерео
        return audio.flatten()

    def read_peak(self) -> float:
        with self._lock:
            peak, self.peak = self.peak, 0.0
        return peak


def trim_silence(audio: np.ndarray) -> np.ndarray:
    """Срезает тишину по краям, оставляя небольшой запас."""
    if audio.size == 0:
        return audio
    peak = float(np.abs(audio).max())
    if peak <= 0:
        return audio
    loud = np.where(np.abs(audio) > peak * TRIM_THRESHOLD)[0]
    if loud.size == 0:
        return audio
    pad = int(TRIM_PAD * SAMPLE_RATE)
    start = max(0, int(loud[0]) - pad)
    end = min(audio.size, int(loud[-1]) + pad)
    return audio[start:end]


def normalize(audio: np.ndarray) -> np.ndarray:
    """Выравнивает громкость по пику."""
    if audio.size == 0:
        return audio
    peak = float(np.abs(audio).max())
    if peak <= 1e-6:
        return audio
    return audio * (TARGET_PEAK / peak)


def resample(audio: np.ndarray, src_rate: int,
             dst_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Линейная интерполяция - когда микрофон отдал не 48 кГц."""
    if src_rate == dst_rate or audio.size == 0:
        return audio
    dst_len = int(round(audio.size / src_rate * dst_rate))
    src_idx = np.linspace(0, audio.size - 1, dst_len)
    return np.interp(src_idx, np.arange(audio.size), audio).astype(np.float32)


def process(audio: np.ndarray, rate: int = SAMPLE_RATE) -> np.ndarray:
    """Обрезка тишины, выравнивание громкости, приведение к 48 кГц."""
    return normalize(trim_silence(resample(audio, rate)))


def save_wav(path: Path, audio: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())


def load_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32767.0
    return audio, rate


def input_devices() -> list[tuple[int, str, str]]:
    """Микрофоны как (индекс, имя, API).

    Одно и то же железо Windows показывает несколько раз - по разу на
    звуковой API (MME, DirectSound, WASAPI, WDM-KS). Имена при этом
    совпадают, поэтому наружу обязательно отдаём индекс: искать устройство
    по имени - значит попасть в случайную копию, которая может и не
    открыться.
    """
    apis = sd.query_hostapis()
    out = []
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] > 0:
            api = apis[dev["hostapi"]]["name"] if dev["hostapi"] < len(apis) else "?"
            out.append((i, dev["name"], api))
    return out


def output_devices() -> list[tuple[int, str, str]]:
    """Выходы как (индекс, имя, API). Дубли по API - как и у входов."""
    apis = sd.query_hostapis()
    out = []
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_output_channels"] > 0:
            api = apis[dev["hostapi"]]["name"] if dev["hostapi"] < len(apis) else "?"
            out.append((i, dev["name"], api))
    return out


def default_input() -> int | None:
    try:
        return sd.default.device[0]
    except (AttributeError, IndexError):
        return None


def default_output() -> int | None:
    try:
        return sd.default.device[1]
    except (AttributeError, IndexError):
        return None


def play(audio: np.ndarray, rate: int, device: int | None = None) -> None:
    """Играет звук. Бросает исключение, если не вышло - молчать нельзя."""
    sd.stop()
    sd.play(audio, rate, device=device)
