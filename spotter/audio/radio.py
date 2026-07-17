"""Эффект рации: голос как из шлема, а не из микрофона в комнате.

Что делает настоящая радиосвязь и что мы повторяем:
  - режет всё вне 300-3200 Гц (узкая полоса, нет низа и воздуха);
  - поджимает динамику и слегка перегружает - речь звучит плоско и плотно;
  - подмешивает шипение эфира;
  - оставляет короткий хвост шума после конца фразы - тангенту отпустили.

Фильтр - FIR на numpy: свёртка векторизована, а рекурсивный IIR пришлось бы
гонять питоновским циклом на 48000 отсчётов. Тащить scipy ради одной
функции - это десятки мегабайт в exe.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

# Окно Блэкмана даёт переход шириной примерно 5.5*sr/TAPS. Чтобы честно
# срезать низ на 300 Гц, переход должен быть уже ~200 Гц - отсюда и длина.
# Короткое ядро (201) заваливало 60 Гц всего на 14 дБ вместо 40+.
TAPS = 1301


@dataclass
class RadioConfig:
    enabled: bool = True
    low: int = 300          # нижний срез, Гц
    high: int = 3200        # верхний срез, Гц
    drive: float = 2.2      # насыщение: больше - грязнее
    noise: float = 0.055    # уровень шипения
    tail: float = 0.14      # хвост шума после фразы, сек
    lead: float = 0.05      # шум перед фразой - тангенту нажали
    click: float = 0.35     # щелчок тангенты, 0 - выключить
    crackle: float = 0.15   # вероятность треска в фразе

    @classmethod
    def from_dict(cls, data: dict | None) -> "RadioConfig":
        cfg = cls()
        if not data:
            return cfg
        for field in ("enabled", "low", "high", "drive", "noise", "tail",
                      "lead", "click", "crackle"):
            if field in data:
                setattr(cfg, field, data[field])
        return cfg

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled, "low": self.low, "high": self.high,
            "drive": self.drive, "noise": self.noise, "tail": self.tail,
            "lead": self.lead, "click": self.click, "crackle": self.crackle,
        }


def _lowpass_kernel(sr: int, cutoff: float, taps: int) -> np.ndarray:
    """Окно синка. Коэффициент 2*fc/sr держит усиление на нуле равным 1."""
    n = np.arange(taps) - (taps - 1) / 2.0
    fc = cutoff / sr
    return (2 * fc * np.sinc(2 * fc * n)).astype(np.float64)


@lru_cache(maxsize=8)
def _kernel(sr: int, low: float, high: float, taps: int) -> np.ndarray:
    """Полосовое ядро = ФНЧ(high) минус ФНЧ(low). Кэшируем: оно одно на всех."""
    high = min(high, sr / 2 * 0.98)
    k = _lowpass_kernel(sr, high, taps) - _lowpass_kernel(sr, low, taps)
    return k * np.blackman(taps)


def _convolve_same(x: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Свёртка через FFT.

    Прямая свёртка с ядром в 1301 отсчёт стоила бы ~60 млн умножений на
    фразу и заметно тормозила бы первый вызов споттера.
    """
    n = x.size + h.size - 1
    fft_size = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, fft_size) * np.fft.rfft(h, fft_size),
                     fft_size)[:n]
    start = (h.size - 1) // 2
    return y[start:start + x.size]


def bandpass(x: np.ndarray, sr: int, low: float, high: float,
             taps: int = TAPS) -> np.ndarray:
    if x.size == 0:
        return x
    return _convolve_same(x.astype(np.float64), _kernel(sr, low, high, taps))


def _noise(size: int, sr: int, cfg: RadioConfig,
           rng: np.random.Generator) -> np.ndarray:
    """Шипение эфира - тот же полосовой, что и у голоса."""
    if size <= 0:
        return np.zeros(0)
    raw = rng.standard_normal(size)
    return bandpass(raw, sr, cfg.low, cfg.high)


def _saturate(x: np.ndarray, drive: float) -> np.ndarray:
    """Мягкое ограничение. Делим на tanh(drive), чтобы пик остался на месте."""
    if drive <= 0:
        return x
    return np.tanh(x * drive) / np.tanh(drive)


def apply(audio: np.ndarray, sr: int, cfg: RadioConfig,
          seed: int | None = None) -> np.ndarray:
    """Превращает чистую запись в радиопередачу."""
    if not cfg.enabled or audio.size == 0:
        return audio

    rng = np.random.default_rng(seed)
    voice = bandpass(audio, sr, cfg.low, cfg.high)

    # Подтягиваем уровень назад: полосовой срезал часть энергии.
    peak = float(np.abs(voice).max())
    if peak > 1e-6:
        voice = voice / peak * 0.85
    voice = _saturate(voice, cfg.drive)

    lead = int(cfg.lead * sr)
    tail = int(cfg.tail * sr)
    total = lead + voice.size + tail

    out = np.zeros(total)
    out[lead:lead + voice.size] = voice

    # Шипение по всей длине: эфир открыт всё это время.
    bed = _noise(total, sr, cfg, rng) * cfg.noise
    # Хвост затухает - связь закрывается.
    if tail > 0:
        bed[-tail:] *= np.linspace(1.0, 0.0, tail) ** 0.6
    if lead > 0:
        bed[:lead] *= np.linspace(0.0, 1.0, lead) ** 0.5
    out += bed

    # Щелчок тангенты в начале.
    if cfg.click > 0 and lead > 4:
        n = min(lead, int(0.006 * sr))
        spike = rng.standard_normal(n) * cfg.click
        spike *= np.linspace(1.0, 0.0, n) ** 2
        out[:n] += bandpass(spike, sr, cfg.low, cfg.high)

    # Редкий треск в эфире.
    if cfg.crackle > 0 and rng.random() < cfg.crackle and voice.size > sr * 0.2:
        pos = int(rng.integers(lead, lead + voice.size - 1))
        n = min(int(0.004 * sr), total - pos)
        if n > 2:
            burst = rng.standard_normal(n) * 0.25
            burst *= np.linspace(1.0, 0.0, n) ** 2
            out[pos:pos + n] += burst

    peak = float(np.abs(out).max())
    if peak > 0.97:
        out = out / peak * 0.97
    return out.astype(np.float32)
