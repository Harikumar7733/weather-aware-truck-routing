"""Driving-time to elapsed-time conversion, optionally honouring FMCSA hours-of-service.

Simplified property-carrying HOS model (driver starts the trip fully rested):
  * at most 11 hours of driving per duty period, followed by a 10-hour rest;
  * a 30-minute break is required after 8 cumulative hours of driving.
"""

from __future__ import annotations

import math

HOUR = 3600.0
MAX_DRIVING_PER_SHIFT_S = 11 * HOUR
BREAK_AFTER_DRIVING_S = 8 * HOUR
BREAK_S = 0.5 * HOUR
REST_S = 10 * HOUR


def elapsed_seconds(driving_s: float, hours_of_service: bool) -> float:
    """Wall-clock seconds needed to accumulate ``driving_s`` seconds behind the wheel."""
    if not hours_of_service or driving_s <= 0:
        return max(0.0, driving_s)
    completed_shifts = math.ceil(driving_s / MAX_DRIVING_PER_SHIFT_S) - 1
    in_shift = driving_s - completed_shifts * MAX_DRIVING_PER_SHIFT_S
    breaks = completed_shifts + (1 if in_shift > BREAK_AFTER_DRIVING_S else 0)
    return driving_s + completed_shifts * REST_S + breaks * BREAK_S
