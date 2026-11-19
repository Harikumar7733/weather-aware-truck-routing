from django.test import SimpleTestCase

from planner.domain.risk import (
    RAIN_BANDS_IN_HR,
    SNOW_BANDS_IN_HR,
    WIND_BANDS_MPH,
    RiskLevel,
    assess,
    classify,
    classify_wind,
)

L, M, H, S, N = RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.SEVERE, RiskLevel.NO_TRAVEL


class ThresholdTests(SimpleTestCase):
    def test_wind_bands(self):
        cases = [(0, L), (24.9, L), (25, M), (34.9, M), (35, H), (44.9, H), (45, S), (54.9, S), (55, N), (80, N)]
        for value, expected in cases:
            with self.subTest(wind=value):
                self.assertEqual(classify(value, WIND_BANDS_MPH), expected)

    def test_rain_bands(self):
        cases = [(0, L), (0.09, L), (0.10, M), (0.24, M), (0.25, H), (0.49, H), (0.50, S), (1.00, S), (1.01, N)]
        for value, expected in cases:
            with self.subTest(rain=value):
                self.assertEqual(classify(value, RAIN_BANDS_IN_HR), expected)

    def test_snow_bands(self):
        cases = [(0, L), (0.49, L), (0.5, M), (0.99, M), (1.0, H), (1.99, H), (2.0, S), (3.0, S), (3.01, N)]
        for value, expected in cases:
            with self.subTest(snow=value):
                self.assertEqual(classify(value, SNOW_BANDS_IN_HR), expected)


class LoadRuleTests(SimpleTestCase):
    def test_55_mph_is_no_travel_for_any_load(self):
        self.assertEqual(classify_wind(55, 0)[0], N)

    def test_45_to_54_with_heavy_load_is_no_travel(self):
        self.assertEqual(classify_wind(50, 30_001)[0], N)
        self.assertEqual(classify_wind(50, 30_000)[0], S)  # rule is strictly "> 30,000 lb"

    def test_35_to_44_with_heavier_load_is_severe(self):
        self.assertEqual(classify_wind(40, 40_001)[0], S)
        self.assertEqual(classify_wind(40, 40_000)[0], H)
        self.assertEqual(classify_wind(40, 35_000)[0], H)

    def test_load_does_not_affect_low_wind(self):
        self.assertEqual(classify_wind(20, 80_000)[0], L)


class AssessTests(SimpleTestCase):
    def test_worst_condition_wins(self):
        result = assess(wind_mph=10, rain_in_hr=0.3, snow_in_hr=2.5, load_lbs=10_000)
        self.assertEqual(result.level, S)
        self.assertEqual(result.factors, ["Snow 2.50 in/hr"])

    def test_load_rule_reported_as_factor(self):
        result = assess(wind_mph=47, rain_in_hr=0, snow_in_hr=0, load_lbs=35_000)
        self.assertEqual(result.level, N)
        self.assertIn("30,000 lb", result.factors[0])

    def test_calm_weather_is_low_with_no_factors(self):
        result = assess(5, 0, 0, 40_000)
        self.assertEqual(result.level, L)
        self.assertEqual(result.factors, [])
