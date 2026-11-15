"""
Registry of Space Mission Operations graded from Level 1 (Easy) to Level 5 (Black Hole / Impossible).
"""

from typing import Dict, List
from .models import MissionOperation


def get_default_operations() -> Dict[str, MissionOperation]:
    """
    Returns graded space missions:
    1. Level 1 (Oson): Oydagi Janubiy Qutb Quyosh Panellarini Tozalash (Lunar South Pole EVA)
    2. Level 2 (O'rtacha): Pastki Mars Orbitasi Dvigatellarini Ta'mirlash (Mars Orbit Exterior EVA)
    3. Level 3 (Qiyin): Mars Valles Marineris Kanyoniga Tushish & Burg'ulash (Mars Canyon Descent)
    4. Level 4 (Juda Qiyin): Titan Kriogen Metan Bo'ronida Namuna Yig'ish (Titan Cryo-Storm EVA)
    5. Level 5 (Imkonsiz / Qora Tuynuk): Cygnus X-1 Ergosferasida Gravitatsion Zond O'rnatish (Black Hole EVA)
    """
    ops_list = [
        MissionOperation(
            id="OP-01-LUNAR-EASY",
            level=1,
            title="Oydagi Janubiy Qutb Quyosh Panellarini Tozalash",
            target_body="Oy (Shackleton Krateri Cheti)",
            description=(
                "Yassi bazalt va regolitsimon maydonda quyosh panellaridagi changni tozalash, "
                "optik kabellarni almashtirish va telemetriya uzatgichini profilaktika qilish. "
                "Yuklama o'rtacha past, relyef tekis, erkin harakatlanish imkoniyati mavjud."
            ),
            duration_minutes=60,
            gravity_g=0.166,
            ambient_pressure_kpa=0.0,
            ambient_temp_c=-25.0,
            radiation_mSv_per_hour=0.08,
            terrain_difficulty=0.20,
            physical_workload_intensity=0.35,
            tidal_gradient_g=0.0,
            relativity_distortion=1.0,
            suit_hazard_multiplier=1.0
        ),
        MissionOperation(
            id="OP-02-ORBIT-MEDIUM",
            level=2,
            title="Pastki Mars Orbitasi Tashqi Dvigatellarini Ta'mirlash",
            target_body="Mars Orbitasi (Ares-Transit Stansiyasi, 420 km)",
            description=(
                "Nol gravitatsiya (0g) sharoitida ochiq fazoga chiqish, mikrometeoritdan zararlangan "
                "ion manyovr dvigatelini qismlarga ajratish va optik datchiklarni qayta lehimlash. "
                "Fazoviy noaniqlik, ko'ngil aynishi va kema korpusi bo'ylab trossda siljish talab etiladi."
            ),
            duration_minutes=120,
            gravity_g=0.0,
            ambient_pressure_kpa=0.0,
            ambient_temp_c=-45.0,
            radiation_mSv_per_hour=0.35,
            terrain_difficulty=0.45,
            physical_workload_intensity=0.55,
            tidal_gradient_g=0.0,
            relativity_distortion=1.0,
            suit_hazard_multiplier=1.2
        ),
        MissionOperation(
            id="OP-03-MARS-CANYON-HARD",
            level=3,
            title="Mars Valles Marineris Kanyoniga Tushish & Chuqur Burg'ulash",
            target_body="Mars (Melas Chasma Kanyoni, 4.2 km chuqurlik)",
            description=(
                "Quyosh tushmaydigan o'ta sovuq kanyon tubiga 42 graduslik sirpanchiq regolit qiyalik "
                "orqali tushish, 25 kg li chuqur tog' jinslarini burg'ulash uskunasini qo'lda tashish "
                "va muz namunalarini germetik konteynerlarga joylash. Juda yuqori yurak va laktat yuklamasi."
            ),
            duration_minutes=180,
            gravity_g=0.38,
            ambient_pressure_kpa=0.65,
            ambient_temp_c=-95.0,
            radiation_mSv_per_hour=0.75,
            terrain_difficulty=0.85,
            physical_workload_intensity=0.82,
            tidal_gradient_g=0.0,
            relativity_distortion=1.0,
            suit_hazard_multiplier=1.8
        ),
        MissionOperation(
            id="OP-04-TITAN-EXTREME",
            level=4,
            title="Titan Kriogen Metan Bo'ronida Sirt Namunalarini Yig'ish",
            target_body="Titan (Kraken Mare Metan Dengizi Qirg'og'i)",
            description=(
                "O'ta qattiq sovuq (-179°C), suyuq metan/etan yomg'iri va 1.45 atm zich atmosfera. "
                "Skafandrning suyuqlik isitish tizimi maksimal quvvatda ishlaydi. 35 m/s shamol "
                "zarbalariga qarshi turib kriogen qirg'oq muzligini o'rganish. Gipotermiya xavfi o'ta yuqori."
            ),
            duration_minutes=90,
            gravity_g=0.14,
            ambient_pressure_kpa=147.0,
            ambient_temp_c=-179.0,
            radiation_mSv_per_hour=0.15,
            terrain_difficulty=0.75,
            physical_workload_intensity=0.78,
            tidal_gradient_g=0.0,
            relativity_distortion=1.0,
            suit_hazard_multiplier=3.2
        ),
        MissionOperation(
            id="OP-05-BLACK-HOLE-IMPOSSIBLE",
            level=5,
            title="Cygnus X-1 Qora Tuynuk Ergosferasida Gravitatsion Zond O'rnatish",
            target_body="Cygnus X-1 Qora Tuynuki (Voqealar Gorizonti / Ergosfera)",
            description=(
                "Yulduz massasidagi qora tuynukning voqealar gorizontiga 1.15 Schwartzschild radiusida "
                "yaqinlashib, giper-fazoviy gravitatsion zondni qo'lda joylashtirish. "
                "Haddan tashqari gravitatsion to'lqin gradienti (Spaghettification), akkretsion diskning "
                "relyativistik qattiq gamma/rentgen plazmasi va o'ta kuchli relyativistik fazo-vaqt egriligi. "
                "Inson biologiyasi va mavjud skafandrlar uchun mutlaqo chidab bo'lmas shart-sharoit."
            ),
            duration_minutes=15,  # Fatal collapse occurs within 5-10 minutes
            gravity_g=450.0,
            ambient_pressure_kpa=0.0,
            ambient_temp_c=1850000.0,  # Relativistic thermal radiation of accretion disk
            radiation_mSv_per_hour=95000000.0,  # Lethal gamma rays: >95,000 Sv/hr
            terrain_difficulty=1.0,
            physical_workload_intensity=1.0,
            tidal_gradient_g=2850.0,  # Spaghettification gradient tearing human body vertically
            relativity_distortion=25000.0,
            suit_hazard_multiplier=100.0
        ),
    ]
    return {op.id: op for op in ops_list}
