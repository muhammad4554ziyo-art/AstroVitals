"""
Simulation Engine for Astronaut Digital Twins.
Calculates dynamic physical, environmental, metabolic, and cardiovascular responses.
"""

import math
from typing import List, Dict, Any, Tuple
from .models import AstronautProfile, MissionOperation, SimulationStep, MissionSimulationReport


class DigitalTwinEngine:
    """
    High-fidelity physiological and planetary physics simulation engine.
    Steps through mission time slices, computing:
    - Dynamic heart rate & cardiovascular load
    - Oxygen (VO2) consumption and suit ECLSS depletion
    - Core body thermoregulation & suit heat dissipation
    - Blood pressure and orthostatic response
    - Radiation dosage accumulation
    - Gravitational tidal gradient stress (spaghettification limits)
    - Metabolic fatigue and lactate accumulation
    - Deterministic GO / CAUTION / NO-GO / CATASTROPHIC_FAILURE verdict
    """

    @classmethod
    def run_simulation(
        cls,
        astronaut: AstronautProfile,
        operation: MissionOperation,
        time_step_minutes: float = 1.0
    ) -> MissionSimulationReport:
        steps: List[SimulationStep] = []

        total_duration = operation.duration_minutes
        steps_count = max(5, int(total_duration / time_step_minutes))
        actual_step_min = total_duration / steps_count

        # Initial physiological baseline
        curr_hr = astronaut.resting_hr
        curr_spo2 = 98.5
        curr_bp_sys = astronaut.resting_bp_sys
        curr_bp_dia = astronaut.resting_bp_dia
        curr_core_temp = 37.0  # Celsius
        curr_suit_pressure = 29.6  # kPa (nominal suit pressure)
        curr_o2_pct = 100.0
        accumulated_rad_msv = 0.0
        curr_lactate = 1.0  # mmol/L baseline
        curr_stress_index = 80.0  # Nominal Baevsky index

        peak_hr = curr_hr
        min_spo2 = curr_spo2
        peak_g = 0.0
        failure_time: float = None
        cause_of_failure: str = None
        final_verdict = "GO"

        # Check for Black Hole (Level 5) impossible limits
        is_black_hole_mission = (operation.level >= 5 or operation.tidal_gradient_g > 100.0)

        for i in range(steps_count + 1):
            t_min = i * actual_step_min
            progress_ratio = min(1.0, t_min / max(1.0, total_duration))

            # 1. Environmental & Tidal G-load calculation
            base_g = operation.gravity_g
            tidal_g = operation.tidal_gradient_g * (1.0 + 0.1 * math.sin(i * 0.5))
            effective_g = base_g + tidal_g
            peak_g = max(peak_g, effective_g)

            # 2. Radiation accumulation
            rad_rate_msv_per_min = (operation.radiation_mSv_per_hour / 60.0)
            accumulated_rad_msv += rad_rate_msv_per_min * actual_step_min

            # 3. Workload and Heart Rate Dynamics
            workload = operation.physical_workload_intensity
            terrain_factor = operation.terrain_difficulty

            # Dynamic exertion curve (peaks in middle of mission)
            exertion_factor = workload * (0.6 + 0.4 * math.sin(progress_ratio * math.pi))
            target_hr = astronaut.resting_hr + (astronaut.max_hr - astronaut.resting_hr) * exertion_factor

            # Resistance adjustments
            target_hr *= (1.0 + 0.15 * terrain_factor)

            # Tidal spaghettification effect on cardiovascular system
            if tidal_g > 10.0:
                # Extreme hydrostatic blood pooling tearing circulation
                target_hr = 230.0 + tidal_g * 0.05
                curr_bp_sys = max(0.0, curr_bp_sys - tidal_g * 0.5)

            # Smooth HR adaptation
            curr_hr = 0.7 * curr_hr + 0.3 * target_hr
            peak_hr = max(peak_hr, curr_hr)

            # 4. SpO2 and Oxygen Depletion
            # Metabolic O2 consumption rate based on VO2 max & exertion
            o2_burn_rate_pct_per_min = (0.25 + 0.55 * exertion_factor) * (80.0 / max(40.0, astronaut.vo2_max))
            curr_o2_pct = max(0.0, curr_o2_pct - o2_burn_rate_pct_per_min * actual_step_min)

            if curr_o2_pct > 20.0:
                curr_spo2 = max(88.0, 99.0 - (100.0 - curr_o2_pct) * 0.08 - exertion_factor * 3.0)
            else:
                # Hypoxia regime
                curr_spo2 = max(0.0, 88.0 - (20.0 - curr_o2_pct) * 4.0)

            min_spo2 = min(min_spo2, curr_spo2)

            # 5. Lactate & Muscle Fatigue
            if exertion_factor > 0.75:
                curr_lactate = min(18.0, curr_lactate + 0.45 * actual_step_min)
            else:
                curr_lactate = max(1.0, curr_lactate - 0.15 * actual_step_min)

            # 6. Thermal regulation (Core Temp)
            ambient_delta = operation.ambient_temp_c - 20.0
            cooling_efficiency = astronaut.cold_tolerance
            heat_generation = exertion_factor * 1.5

            if operation.ambient_temp_c < -100.0:
                # Deep cryogenic freeze
                curr_core_temp -= (0.04 / max(0.2, cooling_efficiency)) * actual_step_min
            elif operation.ambient_temp_c > 1000.0:
                # Black hole accretion disk thermal plasma radiation
                curr_core_temp += 8.5 * actual_step_min
            else:
                # Balanced EVA suit range
                curr_core_temp = 37.0 + heat_generation * 0.4 - 0.2

            # 7. Stress Index (Baevsky)
            base_stress = 80.0 + exertion_factor * 140.0 + terrain_factor * 100.0
            resilience = astronaut.psychological_resilience
            curr_stress_index = (base_stress / max(0.4, resilience))

            # 8. Check Biological & Structural Failure Limits
            step_status = "NOMINAL"
            event_log = "Barcha telemetriya ko'rsatkichlari me'yorda."

            # Evaluate thresholds
            if is_black_hole_mission:
                # Catastrophic tidal gravitational gradient & radiation collapse
                if t_min >= 2.0:
                    step_status = "CRITICAL_FAILURE"
                    curr_hr = 0.0
                    curr_spo2 = 0.0
                    curr_bp_sys = 0.0
                    curr_bp_dia = 0.0
                    curr_suit_pressure = 0.0
                    curr_o2_pct = 0.0
                    event_log = (
                        "FOJIAVIY HALOKAT: 2850g gravitatsion to'lqin gradienti (spaghettification) "
                        "skafandr va inson vaskulyar tizimini bir zumda parchalab yubordi. "
                        "Radiatsion doza xavfsiz chegaradan 100,000 marta ortib ketdi. Telemetriya uzildi."
                    )
                    failure_time = t_min
                    cause_of_failure = "Spaghettification Gravitatsion To'lqin Gradienti va Ekstremal Relyativistik Radiatsiya"
                    final_verdict = "FATAL_FAILURE"
                    steps.append(SimulationStep(
                        minute=t_min, hr=curr_hr, spo2=curr_spo2, bp_sys=curr_bp_sys, bp_dia=curr_bp_dia,
                        core_temp=curr_core_temp, suit_pressure_kpa=curr_suit_pressure, o2_remaining_pct=curr_o2_pct,
                        accumulated_radiation_msv=accumulated_rad_msv, g_force_effective=effective_g,
                        stress_index=999.0, lactate_mmol=25.0, status=step_status, event_log=event_log
                    ))
                    break
                else:
                    step_status = "CRITICAL"
                    curr_hr = 210.0
                    curr_stress_index = 850.0
                    event_log = "OGOHLANTIRISH: Ergosfera chegarasida kutilmagan giper-gravitatsion bosim va radiatsiya oqimi."
            else:
                # Realistic space missions (Moon, Mars, Titan)
                if curr_hr > astronaut.max_hr:
                    step_status = "CRITICAL"
                    event_log = f"Yurak urishi kritik chegaradan oshdi ({curr_hr:.1f} bpm > {astronaut.max_hr} bpm)."
                    final_verdict = "CAUTION_GO"
                elif curr_lactate > 8.0:
                    step_status = "ELEVATED"
                    event_log = f"Mushaklarda yuqori laktat to'planishi ({curr_lactate:.1f} mmol/L). Charchoq alomati."
                elif curr_core_temp < 35.5:
                    step_status = "CRITICAL"
                    event_log = f"Gipotermiya xavfi: tana harorati {curr_core_temp:.1f}°C gacha tushdi."
                    final_verdict = "CAUTION_GO"
                elif curr_o2_pct < 25.0:
                    step_status = "ELEVATED"
                    event_log = f"Kislorod zaxirasi zaxira chegarasiga yetmoqda ({curr_o2_pct:.1f}% qoldi)."

            steps.append(SimulationStep(
                minute=t_min,
                hr=curr_hr,
                spo2=curr_spo2,
                bp_sys=curr_bp_sys,
                bp_dia=curr_bp_dia,
                core_temp=curr_core_temp,
                suit_pressure_kpa=curr_suit_pressure,
                o2_remaining_pct=curr_o2_pct,
                accumulated_radiation_msv=accumulated_rad_msv,
                g_force_effective=effective_g,
                stress_index=curr_stress_index,
                lactate_mmol=curr_lactate,
                status=step_status,
                event_log=event_log
            ))

        # Survival probability calculation
        if final_verdict == "FATAL_FAILURE":
            survival_prob = 0.0
        elif final_verdict == "CAUTION_GO":
            survival_prob = 74.5 + (astronaut.vo2_max - 50.0) * 1.5
        else:
            survival_prob = 96.0 + (astronaut.psychological_resilience * 3.5)

        survival_prob = max(0.0, min(100.0, survival_prob))

        # Generate summary and recommendations
        summary, recs = cls._generate_diagnostic_analysis(
            astronaut, operation, final_verdict, survival_prob, peak_hr, min_spo2, peak_g, accumulated_rad_msv, cause_of_failure
        )

        return MissionSimulationReport(
            astronaut_id=astronaut.id,
            astronaut_name=astronaut.name,
            operation_id=operation.id,
            operation_title=operation.title,
            verdict=final_verdict,
            survival_probability_pct=survival_prob,
            peak_hr=peak_hr,
            min_spo2=min_spo2,
            peak_g_force=peak_g,
            total_radiation_msv=accumulated_rad_msv,
            o2_margin_pct=curr_o2_pct,
            cause_of_death=cause_of_failure,
            time_of_failure_min=failure_time,
            steps=steps,
            medical_summary=summary,
            safety_recommendations=recs
        )

    @staticmethod
    def _generate_diagnostic_analysis(
        astronaut: AstronautProfile,
        operation: MissionOperation,
        verdict: str,
        survival_prob: float,
        peak_hr: float,
        min_spo2: float,
        peak_g: float,
        rad_msv: float,
        cause_of_failure: str = None
    ) -> Tuple[str, List[str]]:
        if verdict == "FATAL_FAILURE":
            summary = (
                f"MUTLAQ NO-GO (HALOKAT): {astronaut.name} ning raqamli egizagi ushbu muhitda "
                f"100% fojiali yakun topdi. Sabab: {cause_of_failure}. "
                f"Tashqi gravitatsion to'lqin gradienti ({peak_g:.1f}g) va ekstremal nurlanish "
                f"mavjud inson biologiyasi va skafandr texnologiyasi chidamlilik chegarasidan milliard marta yuqori. "
                f"Hech qanday tirik insonni ushbu operatsiyaga yuborish mumkin emas!"
            )
            recs = [
                "Operatsiyani to'xtatish (ABSOLUTE ABORT) — insonli missiya mutlaqo imkonsiz.",
                "Faqat avtonom og'ir kvant zondlari yoki masofaviy robototexnika vositalaridan foydalanish.",
                "Gravitatsion to'lqinlar ta'sir doirasidan kamida 1.5 astronomik birlik xavfsiz masofada qolish."
            ]
        elif verdict == "CAUTION_GO":
            summary = (
                f"OGOHLANTIRISH BILAN RUXSAT ETILADI (CAUTION GO): {astronaut.name} ning raqamli egizagi "
                f"operatsiyani bajardi, biroq yuqori zo'riqish va biometrik chegaralarga yaqinlashish kuzatildi. "
                f"Maksimal puls: {peak_hr:.1f} bpm, Minimal SpO2: {min_spo2:.1f}%, To'plangan nurlanish: {rad_msv:.2f} mSv. "
                f"Omon qolish ehtimoli: {survival_prob:.1f}%."
            )
            recs = [
                "Operatsiyani har 30 daqiqada 5 daqiqalik majburiy dam olish intervallari bilan rejalashtirish.",
                "Skafandr sovutish/isitish tizimiga qo'shimcha quvvat zaxirasini ajratish.",
                "Laktat darajasi oshib ketmasligi uchun og'ir asboblarni avtomatlashtirilgan aravachada tashish."
            ]
        else:
            summary = (
                f"TO'LIQ RUXSAT ETILADI (GO): {astronaut.name} ning raqamli egizagi missiyani a'lo darajada bajardi. "
                f"Barcha fiziologik ko'rsatkichlar xavfsiz oraliqda saqlandi. "
                f"Maksimal puls: {peak_hr:.1f} bpm, Omon qolish ehtimoli: {survival_prob:.1f}%. "
                f"Astronavtning individual parametrlari ushbu operatsiya talablariga to'liq javob beradi."
            )
            recs = [
                "Standart EVA xavfsizlik protokoliga rioya qilish.",
                "Kislorod zaxirasi sarfini telemetriya orqali odatiy rejimda kuzatib borish."
            ]

        return summary, recs
