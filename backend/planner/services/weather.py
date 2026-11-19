"""Hourly forecasts from Open-Meteo (no API key; many locations per request).

Units requested: wind in mph, precipitation in inches, temperature in °F, times in UTC.
Hourly ``rain``/``showers``/``snowfall`` are totals over the preceding hour, i.e. in/hr.
Liquid precipitation = large-scale ``rain`` + convective ``showers``.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Sequence

from django.conf import settings
from django.core.cache import cache

from ..domain.geo import LatLon
from .http import UpstreamError, get_json

HOURLY_VARS = ("wind_speed_10m", "wind_gusts_10m", "rain", "showers", "snowfall", "temperature_2m", "weather_code")
CHUNK_SIZE = 80
CACHE_SECONDS = 30 * 60
MAX_FORECAST_DAYS = 15


@dataclass(frozen=True)
class WeatherSample:
    time: datetime
    wind_mph: float
    gust_mph: float | None
    rain_in: float
    snow_in: float
    temp_f: float | None
    code: int | None

    def as_dict(self) -> dict:
        return {
            "time": self.time.isoformat(),
            "wind_mph": round(self.wind_mph, 1),
            "gust_mph": None if self.gust_mph is None else round(self.gust_mph, 1),
            "rain_in": round(self.rain_in, 3),
            "snow_in": round(self.snow_in, 3),
            "temp_f": None if self.temp_f is None else round(self.temp_f, 1),
            "code": self.code,
        }


class Forecast:
    """Hourly series for one location, starting at ``start`` (UTC, on the hour)."""

    def __init__(self, start: datetime, hourly: dict[str, list]):
        self.start = start
        self.hourly = hourly
        self.length = len(hourly.get("wind_speed_10m", []))

    def at_index(self, idx: int) -> WeatherSample | None:
        if not 0 <= idx < self.length:
            return None
        h = self.hourly
        wind = h["wind_speed_10m"][idx]
        if wind is None:
            return None
        rain = (h["rain"][idx] or 0.0) + (h["showers"][idx] or 0.0)
        code = h["weather_code"][idx]
        return WeatherSample(
            time=self.start + timedelta(hours=idx),
            wind_mph=wind,
            gust_mph=h["wind_gusts_10m"][idx],
            rain_in=rain,
            snow_in=h["snowfall"][idx] or 0.0,
            temp_f=h["temperature_2m"][idx],
            code=None if code is None else int(code),
        )

    def at(self, when: datetime) -> WeatherSample | None:
        """Sample for the forecast hour nearest to ``when``."""
        return self.at_index(round((when - self.start).total_seconds() / 3600))


def hour_floor(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def _key(point: LatLon) -> tuple[float, float]:
    # ~1 km grid; finer than any global/regional model resolution.
    return (round(point[0], 2), round(point[1], 2))


def _fetch_chunk(points: list[tuple[float, float]], start: datetime, end: datetime) -> list[dict]:
    params = {
        "latitude": ",".join(f"{p[0]:.2f}" for p in points),
        "longitude": ",".join(f"{p[1]:.2f}" for p in points),
        "hourly": ",".join(HOURLY_VARS),
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "temperature_unit": "fahrenheit",
        "timezone": "GMT",
        "start_hour": start.strftime("%Y-%m-%dT%H:00"),
        "end_hour": end.strftime("%Y-%m-%dT%H:00"),
    }
    base = settings.OPEN_METEO_URL
    if settings.OPEN_METEO_API_KEY:
        params["apikey"] = settings.OPEN_METEO_API_KEY
        base = base.replace("://api.", "://customer-api.")
    data = get_json(f"{base}/v1/forecast", params, service="Weather service", timeout=30)
    results = data if isinstance(data, list) else [data]
    if len(results) != len(points):
        raise UpstreamError("Weather service returned an unexpected number of locations.")
    return [r.get("hourly", {}) for r in results]


def fetch_forecasts(points: Sequence[LatLon], start: datetime, end: datetime) -> list[Forecast | None]:
    """Forecasts covering [start, end] (UTC hours) for every point, in input order.

    Hours outside the provider's forecast horizon are simply absent (``at`` returns None).
    """
    start = hour_floor(start)
    horizon = hour_floor(datetime.now(timezone.utc)) + timedelta(days=MAX_FORECAST_DAYS)
    end = min(hour_floor(end) + timedelta(hours=1), horizon)
    if end < start:
        return [None] * len(points)

    window = f"{start:%Y%m%d%H}-{end:%Y%m%d%H}"
    unique = list(dict.fromkeys(_key(p) for p in points))
    found: dict[tuple[float, float], dict] = {}
    missing = []
    for key in unique:
        hit = cache.get(f"wx:{key[0]}:{key[1]}:{window}")
        if hit is not None:
            found[key] = hit
        else:
            missing.append(key)

    chunks = [missing[i : i + CHUNK_SIZE] for i in range(0, len(missing), CHUNK_SIZE)]
    if chunks:
        with ThreadPoolExecutor(max_workers=min(4, len(chunks))) as pool:
            for chunk, hourlies in zip(chunks, pool.map(lambda c: _fetch_chunk(c, start, end), chunks)):
                for key, hourly in zip(chunk, hourlies):
                    found[key] = hourly
                    cache.set(f"wx:{key[0]}:{key[1]}:{window}", hourly, CACHE_SECONDS)

    return [Forecast(start, found[_key(p)]) if found.get(_key(p)) else None for p in points]
