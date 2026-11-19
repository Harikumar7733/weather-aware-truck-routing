from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from planner.domain.checkpoints import build_checkpoints, checkpoint_miles
from planner.domain.eta import HOUR, elapsed_seconds
from planner.domain.geo import cumulative_miles, haversine_mi, simplify_indices, slice_polyline
from planner.domain.recommend import Candidate, RiskSegment, explain, rank, summarize
from planner.domain.risk import RiskLevel
from planner.domain.route import Route


def straight_route(miles: float, speed_mph: float = 60, max_speed: float = 65) -> Route:
    """A due-north route along a meridian; 1° latitude ≈ 69.09 mi."""
    deg = miles / 69.093
    n = 200
    coords = [(30 + deg * i / n, -95.0) for i in range(n + 1)]
    seg_miles = [haversine_mi(a, b) for a, b in zip(coords, coords[1:])]
    durations = [m / speed_mph * 3600 for m in seg_miles]
    return Route.build(coords, sum(durations), durations, max_speed_mph=max_speed)


class GeoTests(SimpleTestCase):
    def test_haversine_one_degree_latitude(self):
        self.assertAlmostEqual(haversine_mi((0, 0), (1, 0)), 69.09, places=1)

    def test_slice_polyline_endpoints(self):
        coords = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
        cum = cumulative_miles(coords)
        part = slice_polyline(coords, cum, cum[1] / 2, cum[1] * 1.5)
        self.assertAlmostEqual(part[0][0], 0.5)
        self.assertEqual(part[1], (1.0, 0.0))
        self.assertAlmostEqual(part[-1][0], 1.5)

    def test_simplify_drops_collinear_points(self):
        coords = [(0.0, i * 0.01) for i in range(100)]
        self.assertEqual(simplify_indices(coords, 0.0001), [0, 99])


class RouteTimingTests(SimpleTestCase):
    def test_truck_speed_cap(self):
        fast = straight_route(130, speed_mph=80, max_speed=65)
        self.assertAlmostEqual(fast.drive_duration_s / HOUR, fast.distance_mi / 65, places=3)

    def test_slower_router_time_is_kept(self):
        slow = straight_route(120, speed_mph=50, max_speed=65)
        self.assertAlmostEqual(slow.drive_duration_s / HOUR, slow.distance_mi / 50, places=3)


class HoursOfServiceTests(SimpleTestCase):
    def test_disabled(self):
        self.assertEqual(elapsed_seconds(20 * HOUR, False), 20 * HOUR)

    def test_under_eight_hours_has_no_break(self):
        self.assertEqual(elapsed_seconds(8 * HOUR, True), 8 * HOUR)

    def test_thirty_minute_break_after_eight_hours(self):
        self.assertEqual(elapsed_seconds(9 * HOUR, True), 9.5 * HOUR)

    def test_full_shift_ends_without_rest(self):
        self.assertEqual(elapsed_seconds(11 * HOUR, True), 11.5 * HOUR)

    def test_ten_hour_rest_after_eleven_hours(self):
        # 11h drive + 0.5 break + 10h rest + 1h drive
        self.assertEqual(elapsed_seconds(12 * HOUR, True), 22.5 * HOUR)


class CheckpointTests(SimpleTestCase):
    def test_marks_include_destination(self):
        self.assertEqual(checkpoint_miles(60, 25), [0, 25, 50, 60])
        self.assertEqual(checkpoint_miles(50, 25), [0, 25, 50])

    def test_checkpoints_cover_route_exactly_and_eta_increases(self):
        route = straight_route(237, speed_mph=60)
        dep = datetime(2026, 1, 1, 8, tzinfo=timezone.utc)
        for interval in (10, 25, 50):
            with self.subTest(interval=interval):
                cps = build_checkpoints(route, interval, dep, hours_of_service=False)
                self.assertAlmostEqual(sum(cp.covered_miles for cp in cps), route.distance_mi, places=6)
                self.assertEqual(cps[0].eta, dep)
                self.assertTrue(all(a.eta < b.eta for a, b in zip(cps, cps[1:])))
                expected = dep + timedelta(seconds=route.drive_duration_s)
                self.assertAlmostEqual((cps[-1].eta - expected).total_seconds(), 0, places=3)

    def test_eta_at_checkpoint_matches_speed(self):
        route = straight_route(120, speed_mph=60)
        dep = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cps = build_checkpoints(route, 25, dep, hours_of_service=False)
        self.assertAlmostEqual((cps[2].eta - dep).total_seconds() / 60, 50, delta=0.5)  # mile 50 at 60 mph


def cand(rid, *, nt=0.0, severe=0.0, high=0.0, low=100.0, hours=10.0) -> Candidate:
    segs = [RiskSegment(nt, RiskLevel.NO_TRAVEL), RiskSegment(severe, RiskLevel.SEVERE), RiskSegment(high, RiskLevel.HIGH), RiskSegment(low, RiskLevel.LOW)]
    return Candidate(rid, f"Route {rid}", summarize(segs), hours * HOUR)


class RecommendationTests(SimpleTestCase):
    def test_summary_weighted_average(self):
        s = summarize([RiskSegment(10, RiskLevel.SEVERE), RiskSegment(30, RiskLevel.LOW), RiskSegment(5, None)])
        self.assertAlmostEqual(s.avg_risk, 0.75)
        self.assertEqual(s.unknown_miles, 5)
        self.assertEqual(s.max_level, RiskLevel.SEVERE)

    def test_fewest_severe_miles_beats_faster_route(self):
        ranked = rank([cand("A", severe=20, hours=8), cand("B", severe=0, high=50, hours=12)])
        self.assertEqual(ranked[0].route_id, "B")
        self.assertIn("fewest Severe miles", explain(ranked[0], ranked[1]))

    def test_no_travel_is_worse_than_severe(self):
        ranked = rank([cand("A", nt=5), cand("B", severe=100)])
        self.assertEqual(ranked[0].route_id, "B")

    def test_high_miles_then_average_then_time(self):
        self.assertEqual(rank([cand("A", high=30), cand("B", high=10)])[0].route_id, "B")
        # same severe/high miles; lower average risk wins
        a = Candidate("A", "Route A", summarize([RiskSegment(100, RiskLevel.MODERATE)]), 5 * HOUR)
        b = Candidate("B", "Route B", summarize([RiskSegment(100, RiskLevel.LOW)]), 9 * HOUR)
        self.assertEqual(rank([a, b])[0].route_id, "B")
        # identical risk → fastest wins
        self.assertEqual(rank([cand("A", hours=11), cand("B", hours=9)])[0].route_id, "B")
        self.assertIn("shortest travel time", explain(cand("B", hours=9), cand("A", hours=11)))
