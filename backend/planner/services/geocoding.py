"""Place search via Photon (OpenStreetMap data, autocomplete-friendly, no API key)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass

from django.conf import settings
from django.core.cache import cache

from .http import ValidationError, get_json

_COORD_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lon: float

    def as_dict(self) -> dict:
        return asdict(self)


def _label(props: dict) -> str:
    name = props.get("name") or " ".join(filter(None, [props.get("housenumber"), props.get("street")]))
    parts = [name, props.get("city") if props.get("city") != name else None, props.get("state"), props.get("country")]
    seen: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.append(part)
    return ", ".join(seen)


def search(query: str, limit: int = 5) -> list[Place]:
    query = query.strip()
    if len(query) < 2:
        return []
    if match := _COORD_RE.match(query):
        lat, lon = float(match.group(1)), float(match.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return [Place(label=f"{lat:.5f}, {lon:.5f}", lat=lat, lon=lon)]

    key = "geo:%d:%s" % (limit, hashlib.sha1(query.lower().encode()).hexdigest())
    if (cached := cache.get(key)) is not None:
        return cached
    data = get_json(f"{settings.PHOTON_URL}/api/", {"q": query, "limit": limit, "lang": "en"}, service="Geocoder")
    places = []
    for feature in data.get("features", []):
        lon, lat = feature["geometry"]["coordinates"][:2]
        places.append(Place(label=_label(feature.get("properties", {})), lat=lat, lon=lon))
    cache.set(key, places, 24 * 3600)
    return places


def resolve(value: object, field: str) -> Place:
    """Accept {"lat","lon","label"} or a free-text string and return a Place."""
    if isinstance(value, dict):
        try:
            lat, lon = float(value["lat"]), float(value["lon"])
        except (KeyError, TypeError, ValueError):
            text = str(value.get("label", "")).strip()
            if not text:
                raise ValidationError(f"{field}: provide a place name or coordinates.")
            return resolve(text, field)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValidationError(f"{field}: coordinates out of range.")
        return Place(label=str(value.get("label") or f"{lat:.4f}, {lon:.4f}"), lat=lat, lon=lon)
    if isinstance(value, str) and value.strip():
        results = search(value, limit=1)
        if not results:
            raise ValidationError(f"{field}: could not find '{value}'.")
        return results[0]
    raise ValidationError(f"{field} is required.")
