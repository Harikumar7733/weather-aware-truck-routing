"""Weather heatmap along the trip corridor for the next 48 forecast hours.

A regular lat/lon grid is laid over the routes' bounding box and only nodes
within the corridor (a buffer around any route) are kept. The grid is coarsened
until the node count fits the weather-API budget. The client interpolates the
grid into a smooth raster, so only node values are sent.
"""

from __future__ import annotations

import math
from datetime import timedelta

from ..domain.geo import LatLon, cumulative_miles, sample_every
from ..domain.risk import assess
from . import weather
from .validation import HeatmapRequest

HOURS = 48
MAX_NODES = 220
INITIAL_CELLS_ACROSS = 40
MILES_PER_DEG_LAT = 69.0
MIN_CORRIDOR_MI = 30.0


def _corridor_nodes(polylines: list[list[LatLon]], lat0: float, lon0: float, dlat: float, dlon: float, rows: int, cols: int) -> list[tuple[int, int]]:
    cell_mi = dlat * MILES_PER_DEG_LAT
    corridor_mi = max(MIN_CORRIDOR_MI, 1.5 * cell_mi)
    reach = math.ceil(corridor_mi / cell_mi) + 1
    kept: set[tuple[int, int]] = set()
    for line in polylines:
        for lat, lon in sample_every(line, cumulative_miles(line), cell_mi / 2):
            r0, c0 = round((lat - lat0) / dlat), round((lon - lon0) / dlon)
            kx = math.cos(math.radians(lat)) * MILES_PER_DEG_LAT
            for r in range(max(0, r0 - reach), min(rows, r0 + reach + 1)):
                for c in range(max(0, c0 - reach), min(cols, c0 + reach + 1)):
                    if (r, c) in kept:
                        continue
                    dy = (lat0 + r * dlat - lat) * MILES_PER_DEG_LAT
                    dx = (lon0 + c * dlon - lon) * kx
                    if dx * dx + dy * dy <= corridor_mi * corridor_mi:
                        kept.add((r, c))
    return sorted(kept)


def build_heatmap(req: HeatmapRequest) -> dict:
    pts = [p for line in req.polylines for p in line]
    lats, lons = [p[0] for p in pts], [p[1] for p in pts]
    mid_lat = (min(lats) + max(lats)) / 2
    cos_mid = max(0.2, math.cos(math.radians(mid_lat)))
    span = max(max(lats) - min(lats), (max(lons) - min(lons)) * cos_mid, 0.5)
    pad = max(0.5, span * 0.08)

    dlat = span / INITIAL_CELLS_ACROSS
    while True:
        dlon = dlat / cos_mid
        lat0, lon0 = min(lats) - pad, min(lons) - pad / cos_mid
        rows = math.ceil((max(lats) + pad - lat0) / dlat) + 1
        cols = math.ceil((max(lons) + pad / cos_mid - lon0) / dlon) + 1
        nodes = _corridor_nodes(req.polylines, lat0, lon0, dlat, dlon, rows, cols)
        if len(nodes) <= MAX_NODES:
            break
        dlat *= 1.15

    start = weather.hour_floor(req.departure)
    points = [(lat0 + r * dlat, lon0 + c * dlon) for r, c in nodes]
    forecasts = weather.fetch_forecasts(points, start, start + timedelta(hours=HOURS))

    fields: dict[str, list[list[float | None]]] = {"risk": [], "wind": [], "rain": [], "snow": []}
    for forecast in forecasts:
        series = {k: [] for k in fields}
        for h in range(HOURS + 1):
            s = forecast.at_index(h) if forecast else None
            if s is None:
                for values in series.values():
                    values.append(None)
                continue
            series["risk"].append(int(assess(s.wind_mph, s.rain_in, s.snow_in, req.load_lbs).level))
            series["wind"].append(round(s.wind_mph, 1))
            series["rain"].append(round(s.rain_in, 3))
            series["snow"].append(round(s.snow_in, 3))
        for k, values in series.items():
            fields[k].append(values)

    return {
        "grid": {"lat0": lat0, "lon0": lon0, "dlat": dlat, "dlon": dlon, "rows": rows, "cols": cols},
        "nodes": [[r, c] for r, c in nodes],
        "start": start.isoformat(),
        "hours": HOURS,
        "fields": fields,
    }
