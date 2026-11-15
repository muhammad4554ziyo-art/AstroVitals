"""
Microgravity Physiological Baseline Adaptation Engine.

Replaces rigid static "Earth-normal" medical thresholds with dynamic,
auto-calibrating physiological envelopes that adapt to:
1. Cephalad Fluid Shift (acute 72-hour cranial venous engorgement & plasma reduction)
2. Baroreceptor Recalibration & Heart Rate Baseline Elevation (+5-15 bpm)
3. Long-Duration Cardiovascular & Musculoskeletal Deconditioning
4. Mission Elapsed Time (MET) Multi-Phase Transition Model
5. Inviolable Hard-Safety Boundary Overrides (Zero suppression of true emergencies)
"""

import math
from typing import Dict, Any, Tuple

class MicrogravityAdaptationEngine:
    """
    Dynamically adapts an astronaut's vital baseline according to
    Mission Elapsed Time (MET) and continuous empirical measurements.
    """

    def __init__(self,
                 astronaut_id: str,
                 earth_baseline_hr: float = 68.0,
                 earth_baseline_spo2: float = 98.0,
                 earth_baseline_temp: float = 36.8):
        self.astronaut_id = astronaut_id
        self.earth_hr = earth_baseline_hr
        self.earth_spo2 = earth_baseline_spo2
        self.earth_temp = earth_baseline_temp

        # Running statistical state (Welford's algorithm)
        self.count = 0
        self.running_hr_mean = earth_baseline_hr
        self.running_hr_m2 = 4.0  # Initial variance ~4.0 (std ~2 bpm)

        self.running_spo2_mean = earth_baseline_spo2
        self.running_spo2_m2 = 1.0

        # Adaptation smoothing factor (EWMA)
        self.ewma_alpha = 0.05

    def get_phase_name(self, met_days: float) -> str:
        """Determines mission phase based on Mission Elapsed Time (days)."""
        if met_days < 7.0:
            return "ACUTE_CEPHALAD_FLUID_SHIFT"
        elif met_days < 30.0:
            return "INTERMEDIATE_VASCULAR_EQUILIBRIUM"
        else:
            return "CHRONIC_MICROGRAVITY_DECONDITIONING"

    def calculate_theoretical_fluid_shift_offset(self, met_days: float) -> float:
        """
        Models expected physiological baseline drift due to microgravity:
        - Days 0-3: Rapid 2L cephalad fluid migration causes resting HR to elevate by ~8-12 bpm.
        - Days 4-14: Baroreceptor reset and diuresis stabilize resting HR ~6-10 bpm above Earth baseline.
        - Days 30+: Cardiac remodeling stabilizes resting HR ~8 bpm higher with reduced stroke volume.
        """
        if met_days <= 3.0:
            # Steep exponential rise
            return 10.0 * (1.0 - math.exp(-met_days / 1.2))
        elif met_days <= 14.0:
            # Slight relaxation after diuresis
            decay = (met_days - 3.0) / 11.0
            return 10.0 - (2.0 * decay)
        else:
            # Steady chronic offset
            return 8.0

    def update_with_sample(self, hr: float, spo2: float, met_days: float) -> None:
        """Updates empirical running statistics using Welford's algorithm."""
        self.count += 1
        
        # Welford for HR
        delta_hr = hr - self.running_hr_mean
        self.running_hr_mean += delta_hr / self.count
        delta2_hr = hr - self.running_hr_mean
        self.running_hr_m2 += delta_hr * delta2_hr

        # Welford for SpO2
        delta_sp = spo2 - self.running_spo2_mean
        self.running_spo2_mean += delta_sp / self.count
        delta2_sp = spo2 - self.running_spo2_mean
        self.running_spo2_m2 += delta_sp * delta2_sp

    def get_adapted_thresholds(self, met_days: float) -> Dict[str, Any]:
        """
        Calculates dynamic threshold bands incorporating theoretical model
        and astronaut's empirical empirical running distribution.
        """
        phase = self.get_phase_name(met_days)
        offset = self.calculate_theoretical_fluid_shift_offset(met_days)

        # Baseline HR adapted = blend of theoretical drift + empirical observation
        emp_hr_mean = self.running_hr_mean if self.count > 10 else (self.earth_hr + offset)
        emp_hr_std = math.sqrt(self.running_hr_m2 / max(1, self.count - 1)) if self.count > 10 else 4.0
        emp_hr_std = max(3.0, min(12.0, emp_hr_std))

        adapted_center_hr = 0.5 * (self.earth_hr + offset) + 0.5 * emp_hr_mean

        # Dynamic statistical bounds (3-sigma for warning, 4.5-sigma for critical)
        warning_low_hr = adapted_center_hr - 3.0 * emp_hr_std
        warning_high_hr = adapted_center_hr + 3.0 * emp_hr_std
        critical_low_hr = adapted_center_hr - 4.5 * emp_hr_std
        critical_high_hr = adapted_center_hr + 4.5 * emp_hr_std

        # Inviolable Hard Medical Safeguards (Never suppressed by adaptation!)
        # Bradycardia < 42 bpm or acute tachycardia > 165 bpm always alarm
        warning_low_hr = max(45.0, warning_low_hr)
        warning_high_hr = min(150.0, max(warning_high_hr, adapted_center_hr + 12.0))
        critical_low_hr = max(38.0, critical_low_hr)
        critical_high_hr = min(170.0, critical_high_hr)

        # Dynamic SpO2 Bounds (Pressure-correlated, typically 94-99% in suit O2)
        warning_low_spo2 = 91.0
        critical_low_spo2 = 85.0

        return {
            "astronaut_id": self.astronaut_id,
            "met_days": round(met_days, 2),
            "mission_phase": phase,
            "fluid_shift_hr_offset_bpm": round(offset, 1),
            "earth_baseline_hr": self.earth_hr,
            "adapted_baseline_hr": round(adapted_center_hr, 1),
            "hr_std_dev": round(emp_hr_std, 2),
            "thresholds": {
                "hr_warning_low": round(warning_low_hr, 1),
                "hr_warning_high": round(warning_high_hr, 1),
                "hr_critical_low": round(critical_low_hr, 1),
                "hr_critical_high": round(critical_high_hr, 1),
                "spo2_warning_low": warning_low_spo2,
                "spo2_critical_low": critical_low_spo2,
            }
        }

    def evaluate_vital_status(self, filtered_hr: float, filtered_spo2: float, met_days: float) -> Dict[str, Any]:
        """
        Assesses vital against adapted thresholds.
        Illustrates the difference between static Earth thresholds and microgravity adaptation.
        """
        self.update_with_sample(filtered_hr, filtered_spo2, met_days)
        model = self.get_adapted_thresholds(met_days)
        th = model["thresholds"]

        # Check against adapted bounds
        status = "NOMINAL"
        severity = 0
        details = []

        # Check SpO2
        if filtered_spo2 < th["spo2_critical_low"]:
            status = "CRITICAL_HYPOXIA"
            severity = 3
            details.append(f"SpO2 {filtered_spo2}% below critical threshold {th['spo2_critical_low']}%")
        elif filtered_spo2 < th["spo2_warning_low"]:
            status = "WARNING_HYPOXIA"
            severity = 2
            details.append(f"SpO2 {filtered_spo2}% below warning threshold {th['spo2_warning_low']}%")

        # Check Heart Rate
        if filtered_hr > th["hr_critical_high"]:
            status = "CRITICAL_TACHYCARDIA"
            severity = 3
            details.append(f"HR {filtered_hr} bpm exceeds adapted critical ceiling {th['hr_critical_high']} bpm")
        elif filtered_hr < th["hr_critical_low"]:
            status = "CRITICAL_BRADYCARDIA"
            severity = 3
            details.append(f"HR {filtered_hr} bpm below adapted critical floor {th['hr_critical_low']} bpm")
        elif filtered_hr > th["hr_warning_high"] and severity < 2:
            status = "WARNING_ELEVATED_HR"
            severity = 2
            details.append(f"HR {filtered_hr} bpm exceeds adapted warning limit {th['hr_warning_high']} bpm")
        elif filtered_hr < th["hr_warning_low"] and severity < 2:
            status = "WARNING_DEPRESSED_HR"
            severity = 2
            details.append(f"HR {filtered_hr} bpm below adapted warning limit {th['hr_warning_low']} bpm")

        # Earth-Static Evaluation (Demonstrates why static thresholds fail)
        earth_false_alarm = False
        if filtered_hr > 85.0 and filtered_hr <= th["hr_warning_high"]:
            earth_false_alarm = True

        return {
            "astronaut_id": self.astronaut_id,
            "status": status,
            "severity_score": severity,
            "filtered_hr": filtered_hr,
            "filtered_spo2": filtered_spo2,
            "adapted_baseline_hr": model["adapted_baseline_hr"],
            "fluid_shift_offset": model["fluid_shift_hr_offset_bpm"],
            "earth_baseline_hr": model["earth_baseline_hr"],
            "details": details,
            "static_earth_false_alarm_prevented": earth_false_alarm
        }
