#!/usr/bin/env python3
"""
Interactive CLI Demonstrator for Astronaut Digital Twins & Graded Space Missions.
Allows testing all 5 astronauts (Rozimurod, Muhammadziyo, Eldor, Jasur, Shohruxmirzo)
across 5 mission operations (Level 1 Lunar up to Level 5 Cygnus X-1 Black Hole).
"""

import sys
import time
from health_monitor.digital_twin import (
    get_default_crew,
    get_default_operations,
    DigitalTwinEngine
)
from health_monitor.hud_interface import Color


def print_banner():
    print(f"\n{Color.BG_BLACK}{Color.CYAN_INFO}{'='*80}{Color.RESET}")
    print(f"{Color.BG_BLACK}{Color.WHITE_BOLD}   ASTROVITALS - ASTRONAVT BIOLOGIK RAQAMLI EGIZAKLARI SIMULYATORI{Color.RESET}")
    print(f"{Color.BG_BLACK}{Color.WHITE_BOLD}   (ASTRONAUT BIO-DIGITAL TWIN & PRE-MISSION AI PREDICTIVE ENGINE){Color.RESET}")
    print(f"{Color.BG_BLACK}{Color.CYAN_INFO}{'='*80}{Color.RESET}\n")


def display_crew(crew):
    print(f"{Color.AMBER_WARN}>>> MAVJUD ASTRONAVTLAR (DIGITAL TWIN PROFILLARI):{Color.RESET}")
    for idx, (aid, a) in enumerate(crew.items(), start=1):
        print(f"  [{idx}] {Color.WHITE_BOLD}{a.name:<14}{Color.RESET} | "
              f"Kodi: {a.callsign:<15} | Rol: {a.role:<38} | "
              f"VO2max: {a.vo2_max} | G-chidam: {a.g_tolerance}g")
    print()


def display_operations(ops):
    print(f"{Color.CYAN_INFO}>>> FAZOVIY OPERATSIYALAR KATALOGI (DARAJALAR BO'YICHA):{Color.RESET}")
    for idx, (oid, op) in enumerate(ops.items(), start=1):
        lvl_color = Color.GREEN_NOMINAL if op.level <= 2 else (Color.AMBER_WARN if op.level <= 4 else Color.RED_ALERT)
        print(f"  [{idx}] {lvl_color}[DARAJA {op.level}] {op.title:<55}{Color.RESET} | "
              f"Obyekt: {op.target_body:<25} | Davomiylik: {op.duration_minutes} daq")
    print()


def run_single_simulation(astro, op):
    print(f"\n{Color.BG_BLACK}{Color.CYAN_INFO}[+] Simulyatsiya hisoblanmoqda... {astro.name} -> {op.title}...{Color.RESET}")
    time.sleep(0.4)
    report = DigitalTwinEngine.run_simulation(astro, op)

    # Header
    print(f"\n{Color.BG_BLACK}{'='*80}{Color.RESET}")
    if report.verdict == "FATAL_FAILURE":
        v_badge = f"{Color.RED_ALERT}{Color.FLASH}☠️  FOJIAVIY HALOKAT (FATAL_FAILURE) - MUTLAQ NO-GO{Color.RESET}"
    elif report.verdict == "CAUTION_GO":
        v_badge = f"{Color.AMBER_WARN}⚠️  OGOHLANTIRISH BILAN RUXSAT (CAUTION_GO){Color.RESET}"
    else:
        v_badge = f"{Color.GREEN_NOMINAL}✅  TO'LIQ XAVFSIZ (MISSION GO){Color.RESET}"

    print(f"  ASTRONAVT : {Color.WHITE_BOLD}{report.astronaut_name}{Color.RESET} ({astro.role})")
    print(f"  OPERATSIYA: {Color.WHITE_BOLD}{report.operation_title}{Color.RESET}")
    print(f"  XULOSA    : {v_badge}")
    print(f"  OMON QOLISH EHTIMOLI: {Color.WHITE_BOLD}{report.survival_probability_pct:.1f}%{Color.RESET}")
    print(f"{Color.BG_BLACK}{'-'*80}{Color.RESET}")

    # Telemetry peaks
    print(f"  * Maksimal Puls       : {report.peak_hr:.1f} bpm (Me'yor: {astro.resting_hr:.0f}-{astro.max_hr:.0f} bpm)")
    print(f"  * Minimal SpO2        : {report.min_spo2:.1f}%")
    print(f"  * Maksimal G-kuch     : {report.peak_g_force:.2f} g")
    print(f"  * To'plangan Radiatsiya: {report.total_radiation_msv:.2f} mSv")
    print(f"  * Qolgan Kislorod     : {report.o2_margin_pct:.1f}%")
    if report.cause_of_death:
        print(f"  * {Color.RED_ALERT}Halokat sababi      : {report.cause_of_death}{Color.RESET}")
        print(f"  * {Color.RED_ALERT}Halokat vaqti       : {report.time_of_failure_min:.1f}-daqiqa{Color.RESET}")

    print(f"\n{Color.WHITE_BOLD}[TIBBIY VA MUHANDISLIK DIAGNOSTIKASI]:{Color.RESET}")
    print(f"  {report.medical_summary}")

    print(f"\n{Color.WHITE_BOLD}[XAVFSIZLIK CHORALARI & TAVSIYALAR]:{Color.RESET}")
    for r in report.safety_recommendations:
        print(f"  - {r}")

    # Telemetry Timeline (Sample steps)
    print(f"\n{Color.WHITE_BOLD}[SIMULYATSIYA TELEMETRIYA XRONOLOGIYASI]:{Color.RESET}")
    print(f"  {'Daq':>4} | {'Puls':>6} | {'SpO2':>5} | {'Bosim':>6} | {'Tana T':>6} | {'O2 %':>5} | {'G-kuch':>7} | {'Holat':<12}")
    print(f"  {'-'*65}")
    for s in report.steps:
        st_color = Color.GREEN_NOMINAL if s.status == "NOMINAL" else (Color.AMBER_WARN if s.status in ["ELEVATED", "CRITICAL"] else Color.RED_ALERT)
        print(f"  {s.minute:4.1f} | {s.hr:6.1f} | {s.spo2:5.1f} | {s.suit_pressure_kpa:6.1f} | {s.core_temp:6.1f} | {s.o2_remaining_pct:5.1f} | {s.g_force_effective:7.2f} | {st_color}{s.status:<12}{Color.RESET}")

    print(f"{Color.BG_BLACK}{'='*80}{Color.RESET}\n")


def run_full_matrix(crew, ops):
    print(f"\n{Color.WHITE_BOLD}=== BARCHA 5 ASTRONAVTNING 5 TA OPERATSIYA BO'YICHA TO'LIQ MATRITSASI ==={Color.RESET}\n")
    print(f"{'Astronavt':<14} | {'1. Oy (Oson)':<14} | {'2. Mars Orbitasi':<16} | {'3. Kanyon (Qiyin)':<17} | {'4. Titan (Ekstremal)':<19} | {'5. QORA TUYNUK':<15}")
    print("-" * 105)

    ops_list = list(ops.values())
    for astro in crew.values():
        row_str = f"{Color.WHITE_BOLD}{astro.name:<14}{Color.RESET} | "
        for op in ops_list:
            rep = DigitalTwinEngine.run_simulation(astro, op)
            if rep.verdict == "FATAL_FAILURE":
                badge = f"{Color.RED_ALERT}☠️ 0% HALOK{Color.RESET}    "
            elif rep.verdict == "CAUTION_GO":
                badge = f"{Color.AMBER_WARN}⚠️ {rep.survival_probability_pct:.0f}% EHTIYoT{Color.RESET} "
            else:
                badge = f"{Color.GREEN_NOMINAL}✅ {rep.survival_probability_pct:.0f}% O'TDI{Color.RESET}  "
            row_str += f"{badge:<24} | "
        print(row_str)
    print("-" * 105)
    print(f"\n{Color.CYAN_INFO}[XULOSA]: Qora tuynuk missiyasida barcha 5 nafar astronavt uchun omon qolish ehtimoli 0% (FOJIAVIY HALOKAT).{Color.RESET}")
    print(f"{Color.CYAN_INFO}Bu Raqamli Egizak simulyatsiyasi nima uchun inson hayotini saqlab qolishini amalda isbotlaydi!{Color.RESET}\n")


def main():
    crew = get_default_crew()
    ops = get_default_operations()

    print_banner()

    if len(sys.argv) > 1 and sys.argv[1] == "--matrix":
        run_full_matrix(crew, ops)
        return

    display_crew(crew)
    display_operations(ops)

    print(f"{Color.WHITE_BOLD}Tanlovlar:{Color.RESET}")
    print("  [1-5] Muayyan astronavt va operatsiyani tanlash")
    print("  [M]   Barcha 5 astronavt va 5 ta operatsiyani to'liq matritsa ko'rinishida taqqoslash")
    print("  [B]   Cygnus X-1 Qora tuynuk sinovini barcha astronavtlar uchun birdaniga ko'rish")
    print("  [Q]   Chiqish\n")

    choice = input(f"{Color.CYAN_INFO}Buyruqni kiriting [M/B/1/Q]: {Color.RESET}").strip().upper()

    if choice == "M":
        run_full_matrix(crew, ops)
    elif choice == "B":
        op = ops["OP-05-BLACK-HOLE-IMPOSSIBLE"]
        for astro in crew.values():
            run_single_simulation(astro, op)
    elif choice in ["1", "2", "3", "4", "5"]:
        astro_keys = list(crew.keys())
        astro = crew[astro_keys[int(choice) - 1]]
        print(f"\nTanlangan astronavt: {Color.WHITE_BOLD}{astro.name}{Color.RESET}")
        op_keys = list(ops.keys())
        op_choice = input(f"{Color.CYAN_INFO}Operatsiya raqamini tanlang (1-5): {Color.RESET}").strip()
        if op_choice in ["1", "2", "3", "4", "5"]:
            op = ops[op_keys[int(op_choice) - 1]]
            run_single_simulation(astro, op)
        else:
            print("Noto'g'ri operatsiya tanlandi.")
    else:
        print("Dastur yakunlandi.")


if __name__ == "__main__":
    main()
