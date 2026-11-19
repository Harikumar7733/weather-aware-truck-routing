"""Small geodesy toolkit for polylines expressed as (lat, lon) tuples."""

from __future__ import annotations

import math
from bisect import bisect_right
from typing import Sequence

LatLon = tuple[float, float]

EARTH_RADIUS_MI = 3958.7613
METERS_PER_MILE = 1609.344


def haversine_mi(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(h)))


def cumulative_miles(coords: Sequence[LatLon]) -> list[float]:
    """Cumulative distance (miles) from the first vertex to every vertex."""
    cum = [0.0]
    for prev, cur in zip(coords, coords[1:]):
        cum.append(cum[-1] + haversine_mi(prev, cur))
    return cum


def locate(cum: Sequence[float], mile: float) -> tuple[int, float]:
    """Return (segment index, fraction along that segment) for a distance along the line."""
    if len(cum) < 2 or mile <= 0:
        return 0, 0.0
    if mile >= cum[-1]:
        return len(cum) - 2, 1.0
    i = bisect_right(cum, mile) - 1
    seg = cum[i + 1] - cum[i]
    return i, (mile - cum[i]) / seg if seg > 0 else 0.0


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def point_at(coords: Sequence[LatLon], cum: Sequence[float], mile: float) -> LatLon:
    if len(coords) == 1:
        return coords[0]
    i, t = locate(cum, mile)
    a, b = coords[i], coords[i + 1]
    return (lerp(a[0], b[0], t), lerp(a[1], b[1], t))


def value_at(values: Sequence[float], cum: Sequence[float], mile: float) -> float:
    """Linearly interpolate a per-vertex quantity (e.g. cumulative seconds) at a distance."""
    if len(values) == 1:
        return values[0]
    i, t = locate(cum, mile)
    return lerp(values[i], values[i + 1], t)


def slice_polyline(coords: Sequence[LatLon], cum: Sequence[float], start: float, end: float) -> list[LatLon]:
    """Sub-polyline between two distances, with interpolated end points."""
    out = [point_at(coords, cum, start)]
    lo = bisect_right(cum, start)
    for idx in range(lo, len(coords)):
        if cum[idx] >= end:
            break
        out.append(coords[idx])
    out.append(point_at(coords, cum, end))
    return out


def simplify_indices(coords: Sequence[LatLon], tolerance_deg: float) -> list[int]:
    """Douglas-Peucker simplification; returns indices of the vertices to keep."""
    n = len(coords)
    if n < 3:
        return list(range(n))
    k = math.cos(math.radians(coords[0][0]))
    xs = [c[1] * k for c in coords]
    ys = [c[0] for c in coords]
    keep = [False] * n
    keep[0] = keep[-1] = True
    tol2 = tolerance_deg * tolerance_deg
    stack = [(0, n - 1)]
    while stack:
        s, e = stack.pop()
        ax, ay = xs[s], ys[s]
        dx, dy = xs[e] - ax, ys[e] - ay
        seg2 = dx * dx + dy * dy
        max_d, idx = -1.0, -1
        for i in range(s + 1, e):
            px, py = xs[i] - ax, ys[i] - ay
            if seg2 > 0:
                t = max(0.0, min(1.0, (px * dx + py * dy) / seg2))
                px, py = px - t * dx, py - t * dy
            d = px * px + py * py
            if d > max_d:
                max_d, idx = d, i
        if max_d > tol2:
            keep[idx] = True
            stack.append((s, idx))
            stack.append((idx, e))
    return [i for i in range(n) if keep[i]]


def initial_bearing(a: LatLon, b: LatLon) -> float:
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlon = math.radians(b[1] - a[1])
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def destination_point(origin: LatLon, bearing_deg: float, distance_mi: float) -> LatLon:
    lat1, lon1 = math.radians(origin[0]), math.radians(origin[1])
    brg = math.radians(bearing_deg)
    d = distance_mi / EARTH_RADIUS_MI
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(brg))
    lon2 = lon1 + math.atan2(math.sin(brg) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2))
    return (math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180)


def sample_every(coords: Sequence[LatLon], cum: Sequence[float], step_mi: float) -> list[LatLon]:
    """Evenly spaced points along a polyline (always includes both ends)."""
    total = cum[-1] if cum else 0.0
    if total <= 0:
        return [coords[0]]
    count = max(1, math.ceil(total / step_mi))
    return [point_at(coords, cum, total * i / count) for i in range(count + 1)]
