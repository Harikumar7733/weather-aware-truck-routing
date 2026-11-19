"""Parsing and validation of API request bodies."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..domain.checkpoints import ALLOWED_INTERVALS_MI
from ..domain.geo import LatLon
from . import geocoding
from .http import ValidationError

MAX_LOAD_LBS = 150_000
MAX_DAYS_AHEAD = 7
MAX_HOURS_PAST = 24
MAX_ROUTES = 3
MAX_POLYLINE_POINTS = 2000


def parse_departure(value: object) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        raise ValidationError("departure must be an ISO-8601 date/time.") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if dt < now - timedelta(hours=MAX_HOURS_PAST):
        raise ValidationError("departure cannot be more than 24 hours in the past.")
    if dt > now + timedelta(days=MAX_DAYS_AHEAD):
        raise ValidationError(f"departure must be within the next {MAX_DAYS_AHEAD} days (forecast horizon).")
    return dt


def parse_load(value: object) -> float:
    try:
        load = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValidationError("load_lbs must be a number.") from None
    if not 0 <= load <= MAX_LOAD_LBS:
        raise ValidationError(f"load_lbs must be between 0 and {MAX_LOAD_LBS:,}.")
    return load


@dataclass(frozen=True)
class PlanRequest:
    origin: geocoding.Place
    destination: geocoding.Place
    departure: datetime
    load_lbs: float
    interval_mi: int
    hours_of_service: bool

    @classmethod
    def parse(cls, body: dict) -> "PlanRequest":
        try:
            interval = int(body.get("interval_mi", 25))
        except (TypeError, ValueError):
            interval = -1
        if interval not in ALLOWED_INTERVALS_MI:
            raise ValidationError(f"interval_mi must be one of {ALLOWED_INTERVALS_MI}.")
        departure = parse_departure(body.get("departure"))
        load = parse_load(body.get("load_lbs"))
        with ThreadPoolExecutor(max_workers=2) as pool:
            origin = pool.submit(geocoding.resolve, body.get("origin"), "origin")
            destination = pool.submit(geocoding.resolve, body.get("destination"), "destination")
            places = (origin.result(), destination.result())
        return cls(
            origin=places[0],
            destination=places[1],
            departure=departure,
            load_lbs=load,
            interval_mi=interval,
            hours_of_service=bool(body.get("hours_of_service", True)),
        )


@dataclass(frozen=True)
class HeatmapRequest:
    polylines: list[list[LatLon]]
    departure: datetime
    load_lbs: float

    @classmethod
    def parse(cls, body: dict) -> "HeatmapRequest":
        raw = body.get("routes")
        if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_ROUTES:
            raise ValidationError(f"routes must be a list of 1–{MAX_ROUTES} polylines.")
        polylines: list[list[LatLon]] = []
        for line in raw:
            if not isinstance(line, list) or not 2 <= len(line) <= MAX_POLYLINE_POINTS:
                raise ValidationError(f"each route must have 2–{MAX_POLYLINE_POINTS} [lat, lon] points.")
            try:
                polylines.append([(float(p[0]), float(p[1])) for p in line])
            except (TypeError, ValueError, IndexError):
                raise ValidationError("route points must be [lat, lon] pairs.") from None
        return cls(polylines=polylines, departure=parse_departure(body.get("departure")), load_lbs=parse_load(body.get("load_lbs")))
