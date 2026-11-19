"""Weather checkpoints placed every N miles along a route, with the truck's ETA at each."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .eta import elapsed_seconds
from .route import Route

ALLOWED_INTERVALS_MI = (10, 25, 50)


@dataclass
class Checkpoint:
    index: int
    mile: float
    lat: float
    lon: float
    eta: datetime
    # The stretch of road this checkpoint "represents" (half-way to each neighbour).
    # Summed over all checkpoints these ranges cover the route exactly once.
    start_mile: float
    end_mile: float

    @property
    def covered_miles(self) -> float:
        return self.end_mile - self.start_mile


def checkpoint_miles(total_mi: float, interval_mi: float) -> list[float]:
    """0, N, 2N, ... plus the destination."""
    marks: list[float] = []
    mile = 0.0
    while mile < total_mi - 1e-6:
        marks.append(mile)
        mile += interval_mi
    marks.append(total_mi)
    return marks


def build_checkpoints(route: Route, interval_mi: float, departure: datetime, hours_of_service: bool) -> list[Checkpoint]:
    marks = checkpoint_miles(route.distance_mi, interval_mi)
    checkpoints: list[Checkpoint] = []
    for i, mile in enumerate(marks):
        lat, lon = route.point_at(mile)
        elapsed = elapsed_seconds(route.drive_seconds_at(mile), hours_of_service)
        start = 0.0 if i == 0 else (marks[i - 1] + mile) / 2
        end = route.distance_mi if i == len(marks) - 1 else (mile + marks[i + 1]) / 2
        checkpoints.append(
            Checkpoint(
                index=i,
                mile=mile,
                lat=lat,
                lon=lon,
                eta=departure + timedelta(seconds=elapsed),
                start_mile=start,
                end_mile=end,
            )
        )
    return checkpoints
