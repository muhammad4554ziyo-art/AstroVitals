"""
Astronaut Crew Registry for Digital Twin Simulation.
Registers the 5 astronauts with unique biological, physiological, and endurance profiles.
"""

from typing import Dict, List
from .models import AstronautProfile


def get_default_crew() -> Dict[str, AstronautProfile]:
    """
    Returns the calibrated digital profiles of the 5 mission astronauts:
    - Rozimurod (Commander)
    - Muhammadziyo (Flight Surgeon / Astrobiologist)
    - Eldor (Flight Engineer / Heavy Robotics)
    - Jasur (Lead EVA Specialist / Geologist)
    - Shohruxmirzo (Lander Pilot / Navigation Officer)
    """
    crew_list = [
        AstronautProfile(
            id="ASTRO-ROZIMUROD",
            name="Rozimurod",
            callsign="Pheonix-Actual",
            role="Ekipaj Komandiri & Tizim Muhandisi",
            age=42,
            mass_kg=79.5,
            height_cm=181.0,
            resting_hr=62.0,
            max_hr=178.0,
            vo2_max=52.5,
            resting_bp_sys=124.0,
            resting_bp_dia=82.0,
            radiation_tolerance_sv=0.85,
            g_tolerance=6.8,
            cold_tolerance=0.82,
            psychological_resilience=0.96,  # Exceptional calm & tactical decision-making
            basal_metabolic_rate_w=85.0,
            sweat_rate_l_per_h=0.75,
            specialty_skills=[
                "ECLSS Kostyum Hayot Ta'minotini Boshqarish",
                "Favqulodda Qarorlar Qabul Qilish",
                "Kema Energetik Tizimlari"
            ]
        ),
        AstronautProfile(
            id="ASTRO-MUHAMMADZIYO",
            name="Muhammadziyo",
            callsign="Aura-Doc",
            role="Bosh Shifokor & Astrobiolog",
            age=31,
            mass_kg=72.0,
            height_cm=176.0,
            resting_hr=56.0,
            max_hr=189.0,
            vo2_max=54.0,
            resting_bp_sys=116.0,
            resting_bp_dia=75.0,
            radiation_tolerance_sv=0.95,
            g_tolerance=6.2,
            cold_tolerance=0.78,
            psychological_resilience=0.91,
            basal_metabolic_rate_w=78.0,
            sweat_rate_l_per_h=0.68,
            specialty_skills=[
                "Biometrik Reanimatsiya va Fiziologik Tiklash",
                "Chuqur Fazo Mikrobiologiyasi",
                "Gipoksiya va Keson Profilaktikasi"
            ]
        ),
        AstronautProfile(
            id="ASTRO-ELDOR",
            name="Eldor",
            callsign="Titan-Wrench",
            role="Bosh Mexanik & Og'ir Robototexnika Mutaxassisi",
            age=37,
            mass_kg=86.0,
            height_cm=185.0,
            resting_hr=64.0,
            max_hr=183.0,
            vo2_max=53.0,
            resting_bp_sys=122.0,
            resting_bp_dia=80.0,
            radiation_tolerance_sv=0.90,
            g_tolerance=8.4,  # High G-tolerance and immense physical strength
            cold_tolerance=0.88,
            psychological_resilience=0.89,
            basal_metabolic_rate_w=95.0,
            sweat_rate_l_per_h=1.15,  # Higher hydration loss under EVA
            specialty_skills=[
                "Og'ir Fazo Konstruksiyalarini Ta'mirlash",
                "Skafandr Mexanik Payvandlash",
                "Burg'ulash va Seysmik Uskunalar"
            ]
        ),
        AstronautProfile(
            id="ASTRO-JASUR",
            name="Jasur",
            callsign="Ares-Vanguard",
            role="Yetakchi EVA Spetsialisti & Planetar Geolog",
            age=34,
            mass_kg=76.0,
            height_cm=179.0,
            resting_hr=55.0,
            max_hr=186.0,
            vo2_max=59.5,  # Highest cardiovascular endurance & stamina
            resting_bp_sys=118.0,
            resting_bp_dia=76.0,
            radiation_tolerance_sv=0.92,
            g_tolerance=7.5,
            cold_tolerance=0.92,  # Exceptional thermal endurance in shadow
            psychological_resilience=0.93,
            basal_metabolic_rate_w=82.0,
            sweat_rate_l_per_h=0.85,
            specialty_skills=[
                "Kanyon va Tik Tog' Relyeflarida EVA Harakati",
                "Chuqur Muzliklarni Burg'ulash",
                "Metabolik Resurslarni Ekologik Tejash"
            ]
        ),
        AstronautProfile(
            id="ASTRO-SHOHRUXMIRZO",
            name="Shohruxmirzo",
            callsign="Falcon-Eye",
            role="Qo'nish Moduli Uchuvchisi & Navigatsiya Ofitseri",
            age=29,
            mass_kg=71.0,
            height_cm=175.0,
            resting_hr=58.0,
            max_hr=191.0,
            vo2_max=56.0,
            resting_bp_sys=115.0,
            resting_bp_dia=74.0,
            radiation_tolerance_sv=0.88,
            g_tolerance=8.0,  # Pilot reflexes and high vestibular resistance
            cold_tolerance=0.79,
            psychological_resilience=0.87,
            basal_metabolic_rate_w=80.0,
            sweat_rate_l_per_h=0.72,
            specialty_skills=[
                "Murakkab Gravitatsion Manyovrlar",
                "Pastki Orbita Favqulodda Doklanish",
                "Sensorni Qayta Kalibrlash"
            ]
        ),
    ]
    return {p.id: p for p in crew_list}
