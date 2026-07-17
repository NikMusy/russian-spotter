"""Погода и трасса.

F1 25 присылает прогноз сэмплами на 5/10/15/30/60 минут вперёд, с
вероятностью дождя - поэтому про дождь можно предупредить заранее, а не
постфактум.
"""

from __future__ import annotations

from ..audio import numbers
from ..state import GameState
from ..udp.packets import Weather
from .base import Cooldown, Say

WET = (Weather.LIGHT_RAIN, Weather.HEAVY_RAIN, Weather.STORM)

RAIN_SOON_MINUTES = 20      # заглядываем вперёд не дальше
RAIN_PROBABLE = 55          # процентов, ниже - не дёргаем


class WeatherRule:
    def __init__(self) -> None:
        self.cd = Cooldown()
        self.last_weather: int | None = None
        self.announced_rain_for: int | None = None
        self.told_track_temp = False

    def update(self, state: GameState, say: Say) -> None:
        s = state.session
        if s is None or not state.on_track:
            return

        self._current(s, say)
        self._forecast(s, say)


    def _current(self, s, say: Say) -> None:
        w = s.weather
        if self.last_weather is None:
            self.last_weather = w
            self._intro(s, say)
            return
        if w == self.last_weather:
            return

        prev, self.last_weather = self.last_weather, w
        was_wet, is_wet = prev in WET, w in WET

        if not was_wet and is_wet:
            say("weather_rain_starting")
            if w == Weather.HEAVY_RAIN:
                say("weather_rain_heavy")
            elif w == Weather.STORM:
                say("weather_storm")
            say("consider_inters")
        elif was_wet and not is_wet:
            say("weather_rain_stopping")
            say("weather_drying")
            say("consider_slicks")
        elif was_wet and is_wet:
            if w > prev:
                say("weather_rain_heavy")
                if w >= Weather.HEAVY_RAIN:
                    say("consider_wets")
            else:
                say("weather_rain_light")

    def _intro(self, s, say: Say) -> None:
        """Один раз в начале: какая трасса под колёсами."""
        if self.told_track_temp:
            return
        self.told_track_temp = True

        if s.weather in WET:
            say("track_wet_line")
        else:
            say("weather_dry")

        t = s.track_temperature
        if t <= 0:
            return
        say("track_temp", *numbers.with_word(t, "degrees"))
        if t < 22:
            say("track_cold")
        elif t > 45:
            say("track_hot")


    def _forecast(self, s, say: Say) -> None:
        if s.weather in WET or not s.forecast:
            return

        soon = None
        for sample in s.forecast:
            if sample.time_offset <= 0 or sample.time_offset > RAIN_SOON_MINUTES:
                continue
            if sample.weather in WET or sample.rain_percentage >= RAIN_PROBABLE:
                soon = sample
                break

        if soon is None:
            return
        if self.announced_rain_for == soon.time_offset:
            return
        if not self.cd.ready("rain_forecast", 90):
            return

        self.announced_rain_for = soon.time_offset
        say("rain_expected_in",
            *numbers.with_word(soon.time_offset, "minutes"))
        if soon.rain_percentage:
            say("rain_chance",
                *numbers.with_word(soon.rain_percentage, "percent"))
