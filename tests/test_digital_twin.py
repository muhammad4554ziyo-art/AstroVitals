"""
Comprehensive Test Suite for Astronaut Digital Twin Simulation.
Verifies all 5 astronauts across all 5 graded operations,
with mandatory verification that the Black Hole mission fails catastrophically for 100% of crew members.
"""

import unittest
from health_monitor.digital_twin import (
    get_default_crew,
    get_default_operations,
    DigitalTwinEngine
)


class TestDigitalTwinSimulation(unittest.TestCase):
    def setUp(self):
        self.crew = get_default_crew()
        self.operations = get_default_operations()

    def test_crew_composition(self):
        """Verify all 5 named astronauts are present with valid physiological baselines."""
        expected_names = {"Rozimurod", "Muhammadziyo", "Eldor", "Jasur", "Shohruxmirzo"}
        actual_names = {a.name for a in self.crew.values()}
        self.assertEqual(expected_names, actual_names)

        for astro in self.crew.values():
            self.assertGreater(astro.vo2_max, 45.0)
            self.assertGreater(astro.max_hr, 160.0)
            self.assertGreater(astro.resting_hr, 45.0)
            self.assertGreater(astro.g_tolerance, 5.0)

    def test_operations_progression(self):
        """Verify operations are graded from Level 1 to Level 5."""
        levels = [op.level for op in self.operations.values()]
        self.assertEqual(sorted(levels), [1, 2, 3, 4, 5])

    def test_lunar_easy_mission(self):
        """Verify Level 1 Lunar EVA is safe (GO) for all crew members."""
        op = self.operations["OP-01-LUNAR-EASY"]
        for astro in self.crew.values():
            report = DigitalTwinEngine.run_simulation(astro, op)
            self.assertEqual(report.verdict, "GO")
            self.assertGreater(report.survival_probability_pct, 95.0)
            self.assertLess(report.peak_hr, 125.0)

    def test_titan_extreme_mission(self):
        """Verify Level 4 Titan mission stresses astronauts with cryogenic warnings (CAUTION_GO)."""
        op = self.operations["OP-04-TITAN-EXTREME"]
        for astro in self.crew.values():
            report = DigitalTwinEngine.run_simulation(astro, op)
            self.assertIn(report.verdict, ["CAUTION_GO", "GO"])
            self.assertGreater(report.peak_hr, 160.0)

    def test_black_hole_universal_catastrophic_failure(self):
        """
        MANDATORY REQUIREMENT:
        Verify Cygnus X-1 Black Hole mission results in 100% FATAL_FAILURE (0% survival)
        for every single astronaut without exception.
        """
        op = self.operations["OP-05-BLACK-HOLE-IMPOSSIBLE"]
        for astro in self.crew.values():
            report = DigitalTwinEngine.run_simulation(astro, op)
            self.assertEqual(
                report.verdict,
                "FATAL_FAILURE",
                f"Astronaut {astro.name} must not survive the black hole mission!"
            )
            self.assertEqual(report.survival_probability_pct, 0.0)
            self.assertIsNotNone(report.cause_of_death)
            self.assertIn("Spaghettification", report.cause_of_death)
            self.assertLessEqual(report.time_of_failure_min, 5.0)


if __name__ == "__main__":
    unittest.main()
