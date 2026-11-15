"""
Data models for Astronaut Digital Twins and Deep-Space Operations.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class AstronautProfile:
    """Detailed biological and physiological digital profile of an astronaut."""
    id: str
    name: str
    callsign: str
    role: str
    age: int
    mass_kg: float
    height_cm: float
    resting_hr: float
    max_hr: float
    vo2_max: float                       # ml/kg/min (Cardiorespiratory endurance)
    resting_bp_sys: float                 # mmHg (Systolic)
    resting_bp_dia: float                 # mmHg (Diastolic)
    radiation_tolerance_sv: float         # Acute radiation threshold in Sieverts
    g_tolerance: float                    # Max sustainable acceleration in Gs
    cold_tolerance: float                 # Metabolic thermogenesis efficiency (0.0 to 1.0)
    psychological_resilience: float       # Resistance to panic / Baevsky autonomic strain (0.0 to 1.0)
    basal_metabolic_rate_w: float         # Basal thermal/metabolic wattage
    sweat_rate_l_per_h: float             # Hydration loss rate under EVA exertion
    specialty_skills: List[str] = field(default_factory=list)

    # Enhanced physical, physiological & biomechanical capabilities (NASA/ESA Class-1 Flight Standard)
    rank: str = ""
    avatar_url: str = ""
    blood_type: str = "O(I) Rh+"
    body_fat_pct: float = 12.0
    skeletal_muscle_mass_kg: float = 38.0
    bone_mineral_density_t: float = 1.2
    lung_capacity_liters: float = 6.2
    forced_vital_capacity_liters: float = 5.1
    lactate_threshold_mmol: float = 4.2
    heart_rate_recovery_60s: int = 42
    mean_arterial_pressure: float = 93.0
    negative_g_tolerance: float = -2.8
    hypoxia_tolerance_index: float = 0.98
    vestibular_motion_resistance: float = 0.97
    thermal_regulation_range: str = "-85°C dan +115°C gacha"
    max_continuous_eva_hours: float = 9.0
    reaction_time_ms: int = 195
    cognitive_dual_task_index: float = 0.94
    stress_index_baevsky: float = 52.0
    flight_surgeon_clearance: str = "CLASS-1 TO'LIQ FAZOGA RUXSAT (FLIGHT SURGEON CERTIFIED)"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "callsign": self.callsign,
            "role": self.role,
            "age": self.age,
            "mass_kg": self.mass_kg,
            "height_cm": self.height_cm,
            "resting_hr": self.resting_hr,
            "max_hr": self.max_hr,
            "vo2_max": self.vo2_max,
            "resting_bp_sys": self.resting_bp_sys,
            "resting_bp_dia": self.resting_bp_dia,
            "radiation_tolerance_sv": self.radiation_tolerance_sv,
            "g_tolerance": self.g_tolerance,
            "cold_tolerance": self.cold_tolerance,
            "psychological_resilience": self.psychological_resilience,
            "basal_metabolic_rate_w": self.basal_metabolic_rate_w,
            "sweat_rate_l_per_h": self.sweat_rate_l_per_h,
            "specialty_skills": self.specialty_skills,
            "rank": self.rank,
            "avatar_url": self.avatar_url,
            "blood_type": self.blood_type,
            "body_fat_pct": self.body_fat_pct,
            "skeletal_muscle_mass_kg": self.skeletal_muscle_mass_kg,
            "bone_mineral_density_t": self.bone_mineral_density_t,
            "lung_capacity_liters": self.lung_capacity_liters,
            "forced_vital_capacity_liters": self.forced_vital_capacity_liters,
            "lactate_threshold_mmol": self.lactate_threshold_mmol,
            "heart_rate_recovery_60s": self.heart_rate_recovery_60s,
            "mean_arterial_pressure": self.mean_arterial_pressure,
            "negative_g_tolerance": self.negative_g_tolerance,
            "hypoxia_tolerance_index": self.hypoxia_tolerance_index,
            "vestibular_motion_resistance": self.vestibular_motion_resistance,
            "thermal_regulation_range": self.thermal_regulation_range,
            "max_continuous_eva_hours": self.max_continuous_eva_hours,
            "reaction_time_ms": self.reaction_time_ms,
            "cognitive_dual_task_index": self.cognitive_dual_task_index,
            "stress_index_baevsky": self.stress_index_baevsky,
            "flight_surgeon_clearance": self.flight_surgeon_clearance
        }


@dataclass
class MissionOperation:
    """Space mission operation specifications with environmental and physical stressors."""
    id: str
    level: int                            # 1: Oson, 2: O'rtacha, 3: Qiyin, 4: Juda Qiyin, 5: Qora Tuynuk
    title: str
    target_body: str                      # Moon, Mars Orbit, Mars Canyon, Titan, Cygnus X-1
    description: str
    duration_minutes: int
    gravity_g: float                      # Planetary surface gravity in Earth G
    ambient_pressure_kpa: float           # Ambient atmospheric pressure
    ambient_temp_c: float                 # External ambient temperature
    radiation_mSv_per_hour: float         # Radiation flux in mSv/hr
    terrain_difficulty: float             # 0.0 (smooth) to 1.0 (deadly cliffs)
    physical_workload_intensity: float    # 0.0 (idle) to 1.0 (extreme exertion)
    tidal_gradient_g: float = 0.0         # Gravitational tidal gradient (spaghettification)
    relativity_distortion: float = 1.0    # Relativistic time dilation & frame dragging factor
    suit_hazard_multiplier: float = 1.0   # Stress multiplier on EVA suit ECLSS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "level": self.level,
            "title": self.title,
            "target_body": self.target_body,
            "description": self.description,
            "duration_minutes": self.duration_minutes,
            "gravity_g": self.gravity_g,
            "ambient_pressure_kpa": self.ambient_pressure_kpa,
            "ambient_temp_c": self.ambient_temp_c,
            "radiation_mSv_per_hour": self.radiation_mSv_per_hour,
            "terrain_difficulty": self.terrain_difficulty,
            "physical_workload_intensity": self.physical_workload_intensity,
            "tidal_gradient_g": self.tidal_gradient_g,
            "relativity_distortion": self.relativity_distortion,
            "suit_hazard_multiplier": self.suit_hazard_multiplier
        }


@dataclass
class SimulationStep:
    """One discrete telemetry evaluation step during the digital twin simulation."""
    minute: float
    hr: float
    spo2: float
    bp_sys: float
    bp_dia: float
    core_temp: float
    suit_pressure_kpa: float
    o2_remaining_pct: float
    accumulated_radiation_msv: float
    g_force_effective: float
    stress_index: float
    lactate_mmol: float
    status: str                           # NOMINAL, ELEVATED, CRITICAL, FATAL
    event_log: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "minute": round(self.minute, 1),
            "hr": round(self.hr, 1),
            "spo2": round(self.spo2, 1),
            "bp_sys": round(self.bp_sys, 1),
            "bp_dia": round(self.bp_dia, 1),
            "core_temp": round(self.core_temp, 2),
            "suit_pressure_kpa": round(self.suit_pressure_kpa, 2),
            "o2_remaining_pct": round(self.o2_remaining_pct, 1),
            "accumulated_radiation_msv": round(self.accumulated_radiation_msv, 2),
            "g_force_effective": round(self.g_force_effective, 2),
            "stress_index": round(self.stress_index, 1),
            "lactate_mmol": round(self.lactate_mmol, 2),
            "status": self.status,
            "event_log": self.event_log
        }


@dataclass
class MissionSimulationReport:
    """Comprehensive post-simulation diagnostic evaluation report."""
    astronaut_id: str
    astronaut_name: str
    operation_id: str
    operation_title: str
    verdict: str                          # GO, CAUTION_GO, ABORT_REQUIRED, FATAL_FAILURE
    survival_probability_pct: float
    peak_hr: float
    min_spo2: float
    peak_g_force: float
    total_radiation_msv: float
    o2_margin_pct: float
    cause_of_death: Optional[str]
    time_of_failure_min: Optional[float]
    steps: List[SimulationStep]
    medical_summary: str
    safety_recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "astronaut_id": self.astronaut_id,
            "astronaut_name": self.astronaut_name,
            "operation_id": self.operation_id,
            "operation_title": self.operation_title,
            "verdict": self.verdict,
            "survival_probability_pct": round(self.survival_probability_pct, 1),
            "peak_hr": round(self.peak_hr, 1),
            "min_spo2": round(self.min_spo2, 1),
            "peak_g_force": round(self.peak_g_force, 2),
            "total_radiation_msv": round(self.total_radiation_msv, 2),
            "o2_margin_pct": round(self.o2_margin_pct, 1),
            "cause_of_death": self.cause_of_death,
            "time_of_failure_min": round(self.time_of_failure_min, 1) if self.time_of_failure_min else None,
            "steps": [s.to_dict() for s in self.steps],
            "medical_summary": self.medical_summary,
            "safety_recommendations": self.safety_recommendations
        }
