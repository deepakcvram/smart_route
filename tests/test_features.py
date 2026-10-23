import unittest
import math
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.route_safety import (
    calculate_route_distance_km,
    calculate_route_safety_score,
    get_safety_recommendation,
    DEFAULT_RISK_WEIGHTS,
    DEFAULT_SCORE_CATEGORIES,
)
from utils.ai_description import get_live_weather, _default_weather
from utils.location_service import suggest_typo_corrections, resolve_location, search_location_suggestions
from utils.weather_advisor import get_weather_safety_advisory
from utils.report_generator import generate_csv_report, generate_pdf_report


class TestRouteSafetyFeatures(unittest.TestCase):

    def test_distance_calculation_normal(self):
        # Coordinates roughly Chennai to Bangalore (~300+ km)
        coords = [(13.0827, 80.2707), (12.9716, 77.5946)]
        dist = calculate_route_distance_km(coords)
        self.assertGreater(dist, 250.0)
        self.assertLess(dist, 350.0)

    def test_distance_calculation_empty_or_single(self):
        self.assertEqual(calculate_route_distance_km([]), 0.0)
        self.assertEqual(calculate_route_distance_km([(13.0827, 80.2707)]), 0.0)
        self.assertEqual(calculate_route_distance_km(None), 0.0)

    def test_zero_hotspots_route_score(self):
        res = calculate_route_safety_score([], route_distance_km=100.0)
        self.assertEqual(res["total_hotspots"], 0)
        self.assertEqual(res["high_count"], 0)
        self.assertEqual(res["medium_count"], 0)
        self.assertEqual(res["low_count"], 0)
        self.assertGreaterEqual(res["safety_score"], 80)
        self.assertEqual(res["risk_category"], "LOWER RELATIVE RISK")

    def test_high_risk_route_score(self):
        # 10 HIGH risk hotspots on a short 10 km corridor
        alerts = [
            {"cluster_id": i, "risk_level": "HIGH", "total_accidents": 20, "fatal": 5}
            for i in range(10)
        ]
        res = calculate_route_safety_score(alerts, route_distance_km=10.0)
        self.assertEqual(res["total_hotspots"], 10)
        self.assertEqual(res["high_count"], 10)
        self.assertLess(res["safety_score"], 60)
        self.assertEqual(res["risk_category"], "HIGHER RELATIVE RISK")
        self.assertGreaterEqual(res["safety_score"], 0)

    def test_score_bounds_and_categories(self):
        for dist in [5, 25, 100, 500]:
            for n_high in [0, 1, 5, 20]:
                alerts = [{"cluster_id": i, "risk_level": "HIGH"} for i in range(n_high)]
                res = calculate_route_safety_score(alerts, route_distance_km=dist)
                score = res["safety_score"]
                self.assertTrue(0 <= score <= 100, f"Score {score} out of bounds for dist={dist}, n={n_high}")
                if score >= 80:
                    self.assertEqual(res["risk_category"], "LOWER RELATIVE RISK")
                elif score >= 60:
                    self.assertEqual(res["risk_category"], "MODERATE RELATIVE RISK")
                else:
                    self.assertEqual(res["risk_category"], "HIGHER RELATIVE RISK")

    def test_cluster_deduplication(self):
        # Duplicated alerts for the same cluster (e.g. from nearby route points)
        duplicated = [
            {"cluster_id": 101, "risk_level": "HIGH"},
            {"cluster_id": 101, "risk_level": "HIGH"},
            {"cluster_id": 202, "risk_level": "MEDIUM"},
        ]
        res = calculate_route_safety_score(duplicated, route_distance_km=50.0)
        self.assertEqual(res["total_hotspots"], 2)
        self.assertEqual(res["high_count"], 1)
        self.assertEqual(res["medium_count"], 1)

    def test_missing_and_corrupt_data_handling(self):
        corrupt_alerts = [
            {},  # empty dict
            {"risk_level": None},  # None risk level
            {"cluster_id": "abc", "risk_level": "UNKNOWN"},
        ]
        res = calculate_route_safety_score(corrupt_alerts, route_distance_km=None)
        self.assertTrue(0 <= res["safety_score"] <= 100)

    def test_safety_recommendations(self):
        rec1 = get_safety_recommendation({"top_cause": "overspeeding", "risk_level": "HIGH", "fatal": 2})
        self.assertIn("speed", rec1.lower())

        rec2 = get_safety_recommendation({"top_cause": "drunk driving", "risk_level": "MEDIUM", "fatal": 0})
        self.assertIn("impaired", rec2.lower())

        rec3 = get_safety_recommendation({"top_cause": "poor road", "risk_level": "LOW", "fatal": 0})
        self.assertIn("pothole", rec3.lower())

        rec4 = get_safety_recommendation({"top_cause": "distraction", "risk_level": "MEDIUM", "night_pct": 60})
        self.assertIn("distraction", rec4.lower())
        self.assertIn("headlight", rec4.lower())


class TestWeatherIntegration(unittest.TestCase):
    """Test Feature 1 — Weather integration with is_fallback flag."""

    def test_default_weather_has_is_fallback_true(self):
        w = _default_weather(is_fallback=True, reason="test")
        self.assertTrue(w["is_fallback"])
        self.assertIn("fallback_reason", w)

    def test_live_weather_no_key_returns_fallback(self):
        import utils.ai_description as ad_mod
        original_key = ad_mod.OPENWEATHER_KEY
        ad_mod.OPENWEATHER_KEY = ""
        try:
            w = get_live_weather(13.08, 80.27)
            self.assertTrue(w["is_fallback"], "Should return fallback when key is empty")
            self.assertEqual(w["fallback_reason"], "no_key")
        finally:
            ad_mod.OPENWEATHER_KEY = original_key

    def test_fallback_weather_never_fabricates(self):
        w = _default_weather(is_fallback=True)
        self.assertFalse(w["is_rain"])
        self.assertFalse(w["is_fog"])

    def test_weather_contains_required_fields(self):
        w = _default_weather()
        for field in ["description", "temp", "wind_speed", "is_rain", "is_fog", "is_fallback"]:
            self.assertIn(field, w, f"Missing field: {field}")


class TestWeatherAdvisory(unittest.TestCase):
    """Test Feature 2 — Weather-Based Safety Recommendations."""

    def _make_alerts(self):
        return [
            {"risk_level": "MEDIUM", "top_weather": "rain", "night_pct": 50,
             "total_accidents": 10, "fatal": 1, "peak_hour": 18}
        ]

    def test_rain_advisory(self):
        w = {"description": "Rain", "temp": 25.0, "wind_speed": 10.0,
             "is_rain": True, "is_fog": False, "raw": "rain", "is_fallback": False}
        advisory = get_weather_safety_advisory(w, self._make_alerts())
        self.assertIn("rain", advisory["condition_title"].lower())
        self.assertGreater(len(advisory["precautions"]), 0)
        self.assertIn("condition_color", advisory)

    def test_clear_advisory(self):
        w = {"description": "Clear", "temp": 28.0, "wind_speed": 5.0,
             "is_rain": False, "is_fog": False, "raw": "clear", "is_fallback": False}
        advisory = get_weather_safety_advisory(w)
        self.assertGreater(len(advisory["precautions"]), 0)
        self.assertEqual(advisory["condition_color"], "#39FF14")

    def test_advisory_with_no_alerts(self):
        w = {"description": "Clear", "temp": 28.0, "wind_speed": 5.0,
             "is_rain": False, "is_fog": False, "raw": "clear", "is_fallback": False}
        advisory = get_weather_safety_advisory(w, [])
        self.assertEqual(advisory["contextual_alerts"], [])


class TestLocationService(unittest.TestCase):
    """Test Feature 3 — City Autocomplete and Typo Correction."""

    def test_exact_match(self):
        r = resolve_location("Chennai")
        self.assertIsNotNone(r)
        self.assertEqual(r["city"], "Chennai")
        self.assertEqual(r["match_type"], "exact")

    def test_alternative_name(self):
        r = resolve_location("Bangalore")
        self.assertIsNotNone(r)
        self.assertIn("Bengaluru", r["display_name"])

    def test_typo_banlgore(self):
        corrections = suggest_typo_corrections("banlgore", limit=1)
        self.assertGreater(len(corrections), 0)
        self.assertIn("Bengaluru", corrections[0]["display_name"])

    def test_typo_chenai(self):
        corrections = suggest_typo_corrections("Chenai", limit=1)
        self.assertGreater(len(corrections), 0)
        self.assertEqual(corrections[0]["city"], "Chennai")

    def test_prefix_autocomplete(self):
        results = search_location_suggestions("Banga", limit=3)
        cities = [r["city"] for r in results]
        self.assertTrue(any("Bengaluru" in c or "Bangalore" in c for c in cities))

    def test_empty_query_returns_empty(self):
        self.assertEqual(suggest_typo_corrections(""), [])
        self.assertEqual(search_location_suggestions(""), [])

    def test_resolve_returns_lat_lon(self):
        r = resolve_location("Mumbai")
        self.assertIsNotNone(r)
        self.assertIn("lat", r)
        self.assertIn("lon", r)
        self.assertIsInstance(r["lat"], float)
        self.assertIsInstance(r["lon"], float)


class TestReportGenerators(unittest.TestCase):
    """Test Feature 7 — Downloadable Route Safety Report."""

    def _make_route_sum(self):
        return {
            "start_label": "Chennai",
            "end_label": "Bangalore",
            "route_distance_km": 327.3,
            "safety_score": 68,
            "risk_category": "MODERATE RELATIVE RISK",
            "total_hotspots": 3,
            "high_count": 1,
            "medium_count": 2,
            "low_count": 0,
        }

    def _make_alerts(self):
        return [
            {"cluster_id": 100, "risk_level": "HIGH", "distance_m": 250,
             "hotspot_lat": 13.0, "hotspot_lon": 80.0, "total_accidents": 15,
             "fatal": 2, "casualties": 10, "top_cause": "overspeeding",
             "peak_hour": 18, "night_pct": 45, "top_weather": "rain",
             "ai_desc": "High risk zone.", "safety_recommendation": "Reduce speed."},
        ]

    def _make_weather(self):
        return {"description": "Clear", "temp": 28.0, "wind_speed": 5.0,
                "is_rain": False, "is_fog": False, "is_fallback": True}

    def test_csv_report_structure(self):
        csv_str = generate_csv_report(self._make_route_sum(), self._make_alerts(), self._make_weather())
        self.assertIsInstance(csv_str, str)
        self.assertIn("Chennai", csv_str)
        self.assertIn("Bangalore", csv_str)
        self.assertIn("HIGH", csv_str)

    def test_csv_has_hotspot_data(self):
        csv_str = generate_csv_report(self._make_route_sum(), self._make_alerts(), self._make_weather())
        self.assertIn("overspeeding", csv_str.lower())

    def test_pdf_report_returns_bytes(self):
        pdf_bytes = generate_pdf_report(self._make_route_sum(), self._make_alerts(), self._make_weather())
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 1000)
        self.assertTrue(pdf_bytes[:4] == b"%PDF")

    def test_pdf_report_with_empty_alerts(self):
        pdf_bytes = generate_pdf_report(self._make_route_sum(), [], self._make_weather())
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 500)


if __name__ == "__main__":
    unittest.main()
