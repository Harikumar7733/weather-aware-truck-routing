"""Weather risk classification — a direct encoding of the assignment's rule tables.

Thresholds (lower bound inclusive, unless the table states ">"):

    Condition  Low        Moderate    High        Severe      No Travel
    Wind       <25 mph    25–34       35–44       45–54       >=55 mph
    Rain       <0.10 in/h 0.10–0.25   0.25–0.50   0.50–1.00   >1.00
    Snow       <0.5 in/h  0.5–1.0     1.0–2.0     2.0–3.0     >3.0

Load rules (applied to wind):
    >=55 mph                  -> No Travel for any load
    45–54 mph and >30,000 lb  -> No Travel
    35–44 mph and >40,000 lb  -> Severe

A checkpoint's level is the worst of its wind / rain / snow levels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return _LABELS[self]

    @property
    def key(self) -> str:
        return self.name.lower()


_LABELS = {
    RiskLevel.LOW: "Low",
    RiskLevel.MODERATE: "Moderate",
    RiskLevel.HIGH: "High",
    RiskLevel.SEVERE: "Severe",
    RiskLevel.NO_TRAVEL: "No Travel",
}

# (upper bound, upper bound inclusive?) for LOW, MODERATE, HIGH, SEVERE. Anything beyond is NO_TRAVEL.
Bands = tuple[tuple[float, bool], ...]
WIND_BANDS_MPH: Bands = ((25, False), (35, False), (45, False), (55, False))
RAIN_BANDS_IN_HR: Bands = ((0.10, False), (0.25, False), (0.50, False), (1.00, True))
SNOW_BANDS_IN_HR: Bands = ((0.5, False), (1.0, False), (2.0, False), (3.0, True))

HEAVY_LOAD_NO_TRAVEL_LBS = 30_000  # with 45–54 mph wind
HEAVY_LOAD_SEVERE_LBS = 40_000  # with 35–44 mph wind


def classify(value: float, bands: Bands) -> RiskLevel:
    for level, (bound, inclusive) in enumerate(bands):
        if value < bound or (inclusive and value == bound):
            return RiskLevel(level)
    return RiskLevel.NO_TRAVEL


def classify_wind(wind_mph: float, load_lbs: float) -> tuple[RiskLevel, str | None]:
    """Wind level after load rules, plus a note when a load rule escalated it."""
    base = classify(wind_mph, WIND_BANDS_MPH)
    if base == RiskLevel.SEVERE and load_lbs > HEAVY_LOAD_NO_TRAVEL_LBS:
        return RiskLevel.NO_TRAVEL, "45–54 mph wind with load > 30,000 lb"
    if base == RiskLevel.HIGH and load_lbs > HEAVY_LOAD_SEVERE_LBS:
        return RiskLevel.SEVERE, "35–44 mph wind with load > 40,000 lb"
    return base, None


@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    wind: RiskLevel
    rain: RiskLevel
    snow: RiskLevel
    factors: list[str] = field(default_factory=list)


def assess(wind_mph: float, rain_in_hr: float, snow_in_hr: float, load_lbs: float) -> RiskAssessment:
    wind_level, load_note = classify_wind(wind_mph, load_lbs)
    rain_level = classify(rain_in_hr, RAIN_BANDS_IN_HR)
    snow_level = classify(snow_in_hr, SNOW_BANDS_IN_HR)
    level = max(wind_level, rain_level, snow_level)

    factors: list[str] = []
    if level > RiskLevel.LOW:
        if wind_level == level:
            factors.append(load_note or f"Wind {wind_mph:.0f} mph")
        if rain_level == level:
            factors.append(f"Rain {rain_in_hr:.2f} in/hr")
        if snow_level == level:
            factors.append(f"Snow {snow_in_hr:.2f} in/hr")
    return RiskAssessment(level=level, wind=wind_level, rain=rain_level, snow=snow_level, factors=factors)
