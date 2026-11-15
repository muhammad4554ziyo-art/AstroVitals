"""
Multi-Crew Autonomous Triage & Priority Queue Engine.

Implements spaceflight mass-casualty triage & deterministic resource allocation:
1. Spaceflight-Adapted Triage Matrix (RED, YELLOW, GREEN, BLACK)
2. Deterministic Priority Min-Heap with Strict Tie-Breaking
3. Automated Life-Support Countermeasure Allocator (O2 injection, cooling boost, bulkhead isolation)
4. Consumable Depletion Tracking under Multiple Simultaneous Casualties
"""

import heapq
from typing import Dict, Any, List, Tuple, Optional
import time

class TriageTier:
    RED = 1      # Immediate Life Threat (Hypoxia, Cardiac Arrest, Rapid Decompression)
    YELLOW = 2   # Urgent / Delayed (Moderate Hypoxia, Hyperthermia, Hypercapnia)
    GREEN = 3    # Minimal / Stable (Fatigue, Mild vital drift, Motion Sickness)
    BLACK = 4    # Expectant / Non-Viable (Divert scarce life-support to salvageable crew)

    LABELS = {
        RED: "P1_RED_IMMEDIATE",
        YELLOW: "P2_YELLOW_URGENT",
        GREEN: "P3_GREEN_MINIMAL",
        BLACK: "P4_BLACK_EXPECTANT"
    }


class CrewTriageAssessment:
    """Represents a single astronaut's current medical triage status."""

    def __init__(self,
                 astronaut_id: str,
                 filtered_hr: float,
                 filtered_spo2: float,
                 suit_pressure_kpa: float,
                 stress_index: float,
                 o2_depletion_rate_kpa_min: float = 0.0):
        self.astronaut_id = astronaut_id
        self.filtered_hr = filtered_hr
        self.filtered_spo2 = filtered_spo2
        self.suit_pressure_kpa = suit_pressure_kpa
        self.stress_index = stress_index
        self.o2_depletion_rate = o2_depletion_rate_kpa_min

        self.tier, self.urgency_score, self.primary_diagnostic = self._evaluate_tier()

    def _evaluate_tier(self) -> Tuple[int, float, str]:
        """Classifies astronaut into triage matrix deterministically."""
        # Non-viable check (Black)
        if self.suit_pressure_kpa < 10.0 and self.filtered_hr <= 0.0 and self.filtered_spo2 < 20.0:
            return TriageTier.BLACK, 0.0, "Catastrophic suit breach & asystole"

        # Immediate Life Threat (Red)
        if self.filtered_spo2 < 80.0:
            urgency = (80.0 - self.filtered_spo2) * 5.0 + 100.0
            return TriageTier.RED, urgency, f"Acute Hypoxia (SpO2 {self.filtered_spo2}%)"

        if self.suit_pressure_kpa < 22.0:
            urgency = (22.0 - self.suit_pressure_kpa) * 10.0 + 120.0
            return TriageTier.RED, urgency, f"Rapid Suit Decompression ({self.suit_pressure_kpa} kPa)"

        if self.filtered_hr > 165.0 or (self.filtered_hr < 38.0 and self.filtered_hr > 0.0):
            urgency = abs(self.filtered_hr - 75.0) * 2.0 + 90.0
            return TriageTier.RED, urgency, f"Critical Cardiac Arrhythmia ({self.filtered_hr} bpm)"

        # Urgent / Delayed (Yellow)
        if self.filtered_spo2 < 90.0:
            urgency = (90.0 - self.filtered_spo2) * 3.0 + 50.0
            return TriageTier.YELLOW, urgency, f"Moderate Hypoxia (SpO2 {self.filtered_spo2}%)"

        if self.filtered_hr > 135.0 or (self.filtered_hr < 45.0):
            urgency = abs(self.filtered_hr - 75.0) * 1.5 + 40.0
            return TriageTier.YELLOW, urgency, f"Tachycardia/Bradycardia ({self.filtered_hr} bpm)"

        if self.stress_index > 500.0:
            urgency = 30.0 + (self.stress_index / 20.0)
            return TriageTier.YELLOW, urgency, f"Acute Panic Episode (SI {self.stress_index})"

        # Minimal / Stable (Green)
        urgency = max(0.0, self.stress_index / 50.0)
        return TriageTier.GREEN, urgency, "Vitals within operational margins"

    def to_priority_tuple(self) -> Tuple[int, float, float, str]:
        """
        Generates deterministic sort key:
        (tier_rank ASC, -urgency_score DESC, -o2_depletion_rate DESC, astronaut_id ASC)
        """
        return (
            self.tier,
            -self.urgency_score,
            -self.o2_depletion_rate,
            self.astronaut_id
        )


class AutonomousTriageEngine:
    """
    Evaluates multi-crew vitals and allocates automated life-support countermeasures.
    """

    def __init__(self):
        # Tracking finite consumables
        self.emergency_o2_reserves_available = 2  # Max 2 simultaneous suit high-pressure burst canisters
        self.cooling_boost_pumps_available = 3

    def triage_crew(self, crew_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Executes deterministic multi-crew triage.
        Returns ranked crew members ordered by medical priority.
        """
        assessments: List[CrewTriageAssessment] = []
        for d in crew_data:
            assess = CrewTriageAssessment(
                astronaut_id=d["astronaut_id"],
                filtered_hr=d.get("filtered_hr", 75.0),
                filtered_spo2=d.get("filtered_spo2", 98.0),
                suit_pressure_kpa=d.get("suit_pressure_kpa", 29.6),
                stress_index=d.get("stress_index", 100.0),
                o2_depletion_rate_kpa_min=d.get("o2_depletion_rate", 0.0)
            )
            assessments.append(assess)

        # Sort deterministically
        assessments.sort(key=lambda a: a.to_priority_tuple())

        ranked_results = []
        for rank, a in enumerate(assessments, start=1):
            ranked_results.append({
                "triage_rank": rank,
                "astronaut_id": a.astronaut_id,
                "tier_code": a.tier,
                "tier_label": TriageTier.LABELS[a.tier],
                "urgency_score": round(a.urgency_score, 1),
                "primary_diagnostic": a.primary_diagnostic,
                "filtered_hr": a.filtered_hr,
                "filtered_spo2": a.filtered_spo2,
                "suit_pressure_kpa": a.suit_pressure_kpa
            })

        return ranked_results

    def allocate_automated_countermeasures(self, ranked_triage: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Safely dispatches automated life-support countermeasures
        prioritizing highest-ranked salvageable casualties.
        """
        countermeasures = []
        o2_left = self.emergency_o2_reserves_available

        for item in ranked_triage:
            astro_id = item["astronaut_id"]
            tier = item["tier_code"]
            diagnostic = item["primary_diagnostic"]

            actions = []
            if tier == TriageTier.RED:
                # Critical: Trigger immediate local emergency suit protocol
                actions.append("LOCAL_SUIT_HAPTIC_PULSE_RAPID")
                actions.append("AUDIO_KLAXON_800HZ_WARNING")
                if "Hypoxia" in diagnostic or "Decompression" in diagnostic:
                    if o2_left > 0:
                        actions.append("EXECUTE_EMERGENCY_O2_SOLENOID_INJECTION")
                        o2_left -= 1
                    else:
                        actions.append("O2_RESERVE_EXHAUSTED_ALERT_HABITAT_CREW")
                actions.append("COMMAND_AUTONOMOUS_AIRLOCK_WINCH_RETRIEVAL")

            elif tier == TriageTier.YELLOW:
                actions.append("LOCAL_SUIT_HAPTIC_PULSE_MODERATE")
                actions.append("HUD_WARNING_FLASH_AMBER")
                actions.append("SUIT_VENTILATION_FAN_BOOST")

            elif tier == TriageTier.GREEN:
                actions.append("HUD_NOMINAL_TELEMETRY_REFRESH")

            elif tier == TriageTier.BLACK:
                actions.append("CONSERVE_CONSUMABLES_DIVERT_TO_P1_CREW")

            countermeasures.append({
                "astronaut_id": astro_id,
                "tier_label": item["tier_label"],
                "allocated_actions": actions,
                "timestamp_ms": int(time.time() * 1000)
            })

        return countermeasures
