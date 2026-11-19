"""Route risk summaries and the recommendation ordering.

Ordering (from the assignment), most important first:
    1. fewest Severe miles   (No Travel miles are worse than Severe and are compared first)
    2. fewest High miles
    3. lowest average risk   (distance-weighted mean level, 0 = Low … 4 = No Travel)
    4. shortest travel time
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cmp_to_key
from typing import Iterable, Sequence

from .risk import RiskLevel

MILE_TOLERANCE = 0.5  # differences smaller than this are treated as ties
AVG_RISK_TOLERANCE = 0.01


@dataclass
class RiskSegment:
    miles: float
    level: RiskLevel | None  # None = forecast unavailable


@dataclass
class RouteRiskSummary:
    miles_by_level: dict[RiskLevel, float] = field(default_factory=lambda: {lvl: 0.0 for lvl in RiskLevel})
    unknown_miles: float = 0.0
    avg_risk: float | None = None
    max_level: RiskLevel | None = None

    @property
    def no_travel_miles(self) -> float:
        return self.miles_by_level[RiskLevel.NO_TRAVEL]

    @property
    def severe_miles(self) -> float:
        return self.miles_by_level[RiskLevel.SEVERE]

    @property
    def high_miles(self) -> float:
        return self.miles_by_level[RiskLevel.HIGH]


def summarize(segments: Iterable[RiskSegment]) -> RouteRiskSummary:
    summary = RouteRiskSummary()
    weighted = known = 0.0
    for seg in segments:
        if seg.level is None:
            summary.unknown_miles += seg.miles
            continue
        summary.miles_by_level[seg.level] += seg.miles
        weighted += int(seg.level) * seg.miles
        known += seg.miles
        if summary.max_level is None or seg.level > summary.max_level:
            summary.max_level = seg.level
    summary.avg_risk = weighted / known if known > 0 else None
    return summary


@dataclass
class Candidate:
    route_id: str
    name: str
    risk: RouteRiskSummary
    duration_s: float


# (phrase used in explanations, value getter, tie tolerance, value formatter)
_CRITERIA = (
    ("the fewest No Travel miles", lambda c: c.risk.no_travel_miles, MILE_TOLERANCE, lambda v: f"{v:.0f} mi"),
    ("the fewest Severe miles", lambda c: c.risk.severe_miles, MILE_TOLERANCE, lambda v: f"{v:.0f} mi"),
    ("the fewest High miles", lambda c: c.risk.high_miles, MILE_TOLERANCE, lambda v: f"{v:.0f} mi"),
    ("the lowest average risk", lambda c: c.risk.avg_risk or 0.0, AVG_RISK_TOLERANCE, lambda v: f"{v:.2f}"),
    ("equivalent weather risk and the shortest travel time", lambda c: c.duration_s, 0.0, lambda v: format_duration(v)),
)


def _compare(a: Candidate, b: Candidate) -> int:
    for _, getter, tol, _ in _CRITERIA:
        va, vb = getter(a), getter(b)
        if abs(va - vb) > tol:
            return -1 if va < vb else 1
    return 0


def rank(candidates: Sequence[Candidate]) -> list[Candidate]:
    """Stable ranking using the tolerance-aware lexicographic comparison above."""
    return sorted(candidates, key=cmp_to_key(_compare))


def explain(best: Candidate, runner_up: Candidate | None) -> str:
    if runner_up is None:
        return f"{best.name} is the only available route."
    for phrase, getter, tol, fmt in _CRITERIA:
        vb, vr = getter(best), getter(runner_up)
        if abs(vb - vr) > tol:
            return f"{best.name} has {phrase} ({fmt(vb)} vs {fmt(vr)} on {runner_up.name})."
    return f"{best.name} and {runner_up.name} are equivalent on risk and travel time."


def format_duration(seconds: float) -> str:
    minutes = int(round(seconds / 60))
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"
