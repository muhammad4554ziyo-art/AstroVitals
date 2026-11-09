"""
Deep-Space Realistic Telemetry & Emergency Scenario Simulator.

Generates realistic physiological streams and environmental hazards:
1. Nominal EVA Baseline
2. Heavy EVA Power Drill Vibration & Motion Artifacts
3. Galactic Cosmic Ray (GCR) / Solar Particle Event (SPE) SEU Bit Flips
4. Acute Micrometeoroid Strike & Hypoxic Decompression
5. Psychological Panic Attack & Stealth Burnout
6. Multi-Crew Simultaneous Cabin Crisis
"""

import math
import random
import time
from typing import Dict, Any, List

class SpaceflightScenarioSimulator:
    """Simulates realistic telemetry streams and spaceflight emergencies."""

    @staticmethod
    def generate_nominal_frame(astronaut_id: str, t_sec: float) -> Dict[str, Any]:
        """Nominal resting or gentle EVA walking."""
        # Baseline HR ~ 72 bpm with natural sinus arrhythmia
        hr = 72.0 + 3.0 * math.sin(t_sec * 0.2) + random.gauss(0, 0.8)
        spo2 = 98.2 + random.gauss(0, 0.2)
        # Gentle walking acceleration in microgravity
        ax = 0.1 * math.sin(t_sec * 1.5) + random.gauss(0, 0.05)
        ay = 0.15 * math.cos(t_sec * 1.5) + random.gauss(0, 0.05)
        az = 0.08 * math.sin(t_sec * 0.8) + random.gauss(0, 0.05)

        return {
            "astronaut_id": astronaut_id,
            "raw_hr": round(hr, 1),
            "raw_spo2": round(spo2, 1),
            "accel": (ax, ay, az),
            "tool_vibration": 0.0,
            "suit_pressure_kpa": 29.6,
            "eda_microsiemens": 2.1 + random.gauss(0, 0.05)
        }

    @staticmethod
    def generate_eva_tool_drilling_frame(astronaut_id: str, t_sec: float) -> Dict[str, Any]:
        """
        Simulates astronaut using heavy pneumatic/electric rock coring drill.
        Severe mechanical vibration (high frequency acceleration) + optical probe motion noise.
        True physiological HR is ~88 bpm, but raw sensor experiences spikes up to 135 bpm.
        """
        true_hr = 88.0 + 2.0 * math.sin(t_sec * 0.1)
        # Heavy vibration artifact on raw sensor
        sensor_spike = random.choice([0.0, 0.0, 25.0, -20.0, 35.0]) if random.random() > 0.4 else 0.0
        raw_hr = true_hr + sensor_spike + random.gauss(0, 4.0)

        # Optical PPG sensor displacement noise on SpO2
        raw_spo2 = 98.0 - (abs(sensor_spike) * 0.3 if sensor_spike != 0.0 else random.gauss(0, 0.3))

        # Heavy 3-axis vibration (4 to 8 m/s^2)
        vib_freq = 25.0 # 25 Hz hammer drill
        ax = 4.5 * math.sin(t_sec * vib_freq) + random.gauss(0, 0.5)
        ay = 5.2 * math.cos(t_sec * vib_freq) + random.gauss(0, 0.5)
        az = 3.8 * math.sin(t_sec * vib_freq * 1.2) + random.gauss(0, 0.5)

        return {
            "astronaut_id": astronaut_id,
            "raw_hr": round(raw_hr, 1),
            "true_underlying_hr": round(true_hr, 1),
            "raw_spo2": round(max(70.0, min(100.0, raw_spo2)), 1),
            "accel": (ax, ay, az),
            "tool_vibration": 6.5,
            "suit_pressure_kpa": 29.5,
            "eda_microsiemens": 3.8 + random.gauss(0, 0.1)
        }

    @staticmethod
    def generate_acute_hypoxia_decompression_frame(astronaut_id: str, severity_factor: float = 0.8) -> Dict[str, Any]:
        """
        Simulates micrometeoroid penetration or suit O2 regulator freeze.
        SpO2 plunges < 78%, suit pressure falls, compensatory tachycardia.
        """
        return {
            "astronaut_id": astronaut_id,
            "raw_hr": 142.0 + random.gauss(0, 1.5), # Tachycardia
            "raw_spo2": 74.0,                        # Critical hypoxia
            "accel": (0.3, 0.2, 0.1),
            "tool_vibration": 0.0,
            "suit_pressure_kpa": 21.4,               # Suit decompression
            "eda_microsiemens": 8.5,                 # Sympathetic panic burst
            "o2_depletion_rate": 4.2                 # Fast pressure drop (kPa/min)
        }

    @staticmethod
    def generate_acute_panic_frame(astronaut_id: str) -> Dict[str, Any]:
        """
        Simulates acute psychological panic episode (e.g. tether snag or disorientation).
        HR spike, RMSSD collapse (low beat-to-beat variability), elevated EDA phasic peaks.
        """
        return {
            "astronaut_id": astronaut_id,
            "raw_hr": 138.0 + random.gauss(0, 0.5), # Rigid high HR
            "raw_spo2": 97.5,
            "accel": (0.2, 0.4, 0.1),
            "tool_vibration": 0.0,
            "suit_pressure_kpa": 29.6,
            "eda_microsiemens": 9.2 + random.gauss(0, 0.2) # High sympathetic burst
        }

    @staticmethod
    def generate_multi_crew_crisis() -> List[Dict[str, Any]]:
        """
        Generates mass-casualty scenario for 4 crew members:
        - CDR: Critical Hypoxia (SpO2 73%, Suit P 21.0 kPa) -> P1 RED
        - PLT: Severe Tachycardia (HR 155 bpm, Stress 580) -> P2 YELLOW
        - MS1: Decompression fatality / Non-viable -> P4 BLACK
        - MS2: Normal vitals with elevated stress -> P3 GREEN
        """
        return [
            {
                "astronaut_id": "ASTRO-01-CDR",
                "filtered_hr": 145.0,
                "filtered_spo2": 73.5,
                "suit_pressure_kpa": 21.0,
                "stress_index": 620.0,
                "o2_depletion_rate": 5.5
            },
            {
                "astronaut_id": "ASTRO-02-PLT",
                "filtered_hr": 155.0,
                "filtered_spo2": 88.0,
                "suit_pressure_kpa": 28.5,
                "stress_index": 540.0,
                "o2_depletion_rate": 1.2
            },
            {
                "astronaut_id": "ASTRO-03-MS1",
                "filtered_hr": 0.0,
                "filtered_spo2": 0.0,
                "suit_pressure_kpa": 2.1, # Vacuum exposure
                "stress_index": 0.0,
                "o2_depletion_rate": 0.0
            },
            {
                "astronaut_id": "ASTRO-04-MS2",
                "filtered_hr": 84.0,
                "filtered_spo2": 97.8,
                "suit_pressure_kpa": 29.6,
                "stress_index": 180.0,
                "o2_depletion_rate": 0.1
            }
        ]
