"""Route geometry with a truck-adjusted time profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .geo import LatLon, cumulative_miles, haversine_mi, point_at, value_at


@dataclass
class Route:
    coords: list[LatLon]
    miles: list[float]  # cumulative miles at each vertex
    drive_seconds: list[float]  # cumulative driving seconds at each vertex
    summary: str = ""

    @property
    def distance_mi(self) -> float:
        return self.miles[-1]

    @property
    def drive_duration_s(self) -> float:
        return self.drive_seconds[-1]

    def point_at(self, mile: float) -> LatLon:
        return point_at(self.coords, self.miles, mile)

    def drive_seconds_at(self, mile: float) -> float:
        return value_at(self.drive_seconds, self.miles, mile)

    @classmethod
    def build(
        cls,
        coords: Sequence[LatLon],
        total_duration_s: float,
        segment_durations_s: Sequence[float] | None,
        max_speed_mph: float,
        summary: str = "",
    ) -> "Route":
        """Build a route, never letting the truck go faster than ``max_speed_mph``.

        ``segment_durations_s`` are the router's per-segment times (len == len(coords) - 1).
        If unavailable, the total duration is spread proportionally to distance.
        """
        coords = list(coords)
        miles = cumulative_miles(coords)
        seg_miles = [haversine_mi(a, b) for a, b in zip(coords, coords[1:])]
        if segment_durations_s is None or len(segment_durations_s) != len(seg_miles):
            total_mi = miles[-1] or 1.0
            segment_durations_s = [total_duration_s * m / total_mi for m in seg_miles]

        seconds = [0.0]
        for dist, dur in zip(seg_miles, segment_durations_s):
            min_time = dist / max_speed_mph * 3600.0
            seconds.append(seconds[-1] + max(dur, min_time))
        return cls(coords=coords, miles=miles, drive_seconds=seconds, summary=summary)
