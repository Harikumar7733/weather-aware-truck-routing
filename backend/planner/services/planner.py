"""Trip planning use case: routes → checkpoints → weather at ETA → risk → recommendation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..domain.checkpoints import Checkpoint, build_checkpoints
from ..domain.geo import LatLon, simplify_indices, slice_polyline
from ..domain.recommend import Candidate, RiskSegment, RouteRiskSummary, explain, rank, summarize
from ..domain.risk import RiskAssessment, RiskLevel, assess
from ..domain.route import Route
from . import routing, weather
from .validation import PlanRequest

SIMPLIFY_TOLERANCE_DEG = 0.0003  # ~30 m; keeps map geometry light without visible change


@dataclass
class EvaluatedCheckpoint:
    checkpoint: Checkpoint
    sample: weather.WeatherSample | None
    risk: RiskAssessment | None

    @property
    def level(self) -> RiskLevel | None:
        return self.risk.level if self.risk else None


def _evaluate(checkpoints: list[Checkpoint], forecasts: list[weather.Forecast | None], load_lbs: float) -> list[EvaluatedCheckpoint]:
    out = []
    for cp, forecast in zip(checkpoints, forecasts):
        sample = forecast.at(cp.eta) if forecast else None
        risk = assess(sample.wind_mph, sample.rain_in, sample.snow_in, load_lbs) if sample else None
        out.append(EvaluatedCheckpoint(cp, sample, risk))
    return out


def _round_pt(p: LatLon) -> list[float]:
    return [round(p[0], 5), round(p[1], 5)]


def _risk_segments(route: Route, evaluated: list[EvaluatedCheckpoint]) -> tuple[list[LatLon], list[dict]]:
    """Simplified geometry plus polylines coloured by the checkpoint that owns each stretch."""
    keep = simplify_indices(route.coords, SIMPLIFY_TOLERANCE_DEG)
    coords = [route.coords[i] for i in keep]
    miles = [route.miles[i] for i in keep]

    merged: list[tuple[RiskLevel | None, float, float]] = []
    for ev in evaluated:
        cp = ev.checkpoint
        if merged and merged[-1][0] == ev.level:
            merged[-1] = (ev.level, merged[-1][1], cp.end_mile)
        else:
            merged.append((ev.level, cp.start_mile, cp.end_mile))

    segments = [
        {"level": None if level is None else int(level), "coords": [_round_pt(p) for p in slice_polyline(coords, miles, a, b)]}
        for level, a, b in merged
    ]
    return coords, segments


def _risk_dict(summary: RouteRiskSummary) -> dict:
    return {
        "miles_by_level": {lvl.key: round(m, 1) for lvl, m in summary.miles_by_level.items()},
        "unknown_miles": round(summary.unknown_miles, 1),
        "avg_risk": None if summary.avg_risk is None else round(summary.avg_risk, 3),
        "max_level": None if summary.max_level is None else int(summary.max_level),
    }


def _checkpoint_dict(ev: EvaluatedCheckpoint) -> dict:
    cp = ev.checkpoint
    return {
        "index": cp.index,
        "mile": round(cp.mile, 1),
        "lat": round(cp.lat, 5),
        "lon": round(cp.lon, 5),
        "eta": cp.eta.isoformat(),
        "covers_miles": round(cp.covered_miles, 2),
        "weather": ev.sample.as_dict() if ev.sample else None,
        "risk": None
        if ev.risk is None
        else {
            "level": int(ev.risk.level),
            "label": ev.risk.level.label,
            "wind": int(ev.risk.wind),
            "rain": int(ev.risk.rain),
            "snow": int(ev.risk.snow),
            "factors": ev.risk.factors,
        },
    }


def _warnings(best_summary: RouteRiskSummary, best_name: str, departure: datetime) -> list[str]:
    warnings = []
    if best_summary.no_travel_miles > 0:
        warnings.append(
            f"Even {best_name} crosses {best_summary.no_travel_miles:.0f} mi of No Travel conditions — consider delaying departure."
        )
    elif best_summary.severe_miles > 0:
        warnings.append(f"{best_name} still includes {best_summary.severe_miles:.0f} mi of Severe conditions.")
    if best_summary.unknown_miles > 0:
        warnings.append(f"No forecast is available for {best_summary.unknown_miles:.0f} mi of the trip (beyond the forecast horizon).")
    return warnings


def plan_trip(req: PlanRequest) -> dict:
    routes = routing.route_options((req.origin.lat, req.origin.lon), (req.destination.lat, req.destination.lon))
    per_route = [build_checkpoints(r, req.interval_mi, req.departure, req.hours_of_service) for r in routes]

    flat = [cp for cps in per_route for cp in cps]
    last_eta = max(cp.eta for cp in flat)
    forecasts = weather.fetch_forecasts([(cp.lat, cp.lon) for cp in flat], req.departure, last_eta)

    payload_routes: list[dict] = []
    candidates: list[Candidate] = []
    offset = 0
    for i, (route, cps) in enumerate(zip(routes, per_route)):
        evaluated = _evaluate(cps, forecasts[offset : offset + len(cps)], req.load_lbs)
        offset += len(cps)
        summary = summarize(RiskSegment(ev.checkpoint.covered_miles, ev.level) for ev in evaluated)
        geometry, segments = _risk_segments(route, evaluated)
        route_id = "ABC"[i]
        trip_seconds = (cps[-1].eta - req.departure).total_seconds()
        candidates.append(Candidate(route_id, f"Route {route_id}", summary, trip_seconds))
        payload_routes.append(
            {
                "id": route_id,
                "name": f"Route {route_id}",
                "via": route.summary,
                "distance_mi": round(route.distance_mi, 1),
                "drive_duration_s": round(route.drive_duration_s),
                "trip_duration_s": round(trip_seconds),
                "arrival": cps[-1].eta.isoformat(),
                "geometry": [_round_pt(p) for p in geometry],
                "segments": segments,
                "checkpoints": [_checkpoint_dict(ev) for ev in evaluated],
                "risk": _risk_dict(summary),
            }
        )

    ranked = rank(candidates)
    rank_of = {c.route_id: n + 1 for n, c in enumerate(ranked)}
    for route in payload_routes:
        route["rank"] = rank_of[route["id"]]
        route["recommended"] = route["rank"] == 1
    best = ranked[0]

    return {
        "origin": req.origin.as_dict(),
        "destination": req.destination.as_dict(),
        "departure": req.departure.isoformat(),
        "load_lbs": req.load_lbs,
        "interval_mi": req.interval_mi,
        "hours_of_service": req.hours_of_service,
        "routes": payload_routes,
        "recommendation": {
            "route_id": best.route_id,
            "reason": explain(best, ranked[1] if len(ranked) > 1 else None),
            "warnings": _warnings(best.risk, best.name, req.departure),
        },
    }
