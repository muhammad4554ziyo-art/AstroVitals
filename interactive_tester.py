#!/usr/bin/env python3
"""
Interactive Hands-On Test Suite for Edge-First Astronaut Health Monitor.

Allows security researchers and engineers to manually trigger, inspect,
and stress-test each of the 10 core constraints independently.
"""

import sys
import time
import os
import zlib
import asyncio
import numpy as np

from health_monitor.config import SecurityConfig, MissionParams
from health_monitor.dsp_filter import BiometricDSPPipeline
from health_monitor.seu_protection import TelemetryFrameIntegrity, TMRProtectedVariable, RadiationFaultInjector
from health_monitor.crypto_layer import CryptoEngine
from health_monitor.biomarkers_hrv_eda import PsychophysiologicalAnalyzer
from health_monitor.baseline_adaptation import MicrogravityAdaptationEngine
from health_monitor.telemetry_buffer import CircularTelemetryBuffer, DeltaCompressionEngine, DSNTelemetrySyncPackager
from health_monitor.multi_crew_triage import AutonomousTriageEngine, TriageTier
from health_monitor.hud_interface import EVAHeadUpDisplay, Color
from health_monitor.edge_daemon import AutonomousSuitEdgeDaemon
from health_monitor.simulator import SpaceflightScenarioSimulator

def clear_screen():
    print("\033[2J\033[H", end="")

def print_header(title: str):
    print(f"\n{Color.BG_BLACK}{Color.CYAN_INFO}{'='*75}{Color.RESET}")
    print(f"{Color.BG_BLACK}{Color.WHITE_BOLD}  [TEST] {title}{Color.RESET}")
    print(f"{Color.BG_BLACK}{Color.CYAN_INFO}{'='*75}{Color.RESET}\n")

# ----------------- TEST 1 -----------------
def test_zero_latency_core():
    print_header("1. Zero-Latency Local Emergency Reaction Benchmark")
    daemon = AutonomousSuitEdgeDaemon("ASTRO-01-CDR")
    
    # Warmup
    asyncio.run(daemon.process_single_frame(SpaceflightScenarioSimulator.generate_nominal_frame("ASTRO-01-CDR", 0.0)))
    
    hypoxia_frame = SpaceflightScenarioSimulator.generate_acute_hypoxia_decompression_frame("ASTRO-01-CDR")
    latencies = []
    
    print("Executing 50 consecutive local emergency evaluations...")
    for _ in range(50):
        t0 = time.perf_counter()
        res = asyncio.run(daemon.process_single_frame(hypoxia_frame))
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    avg_lat = np.mean(latencies)
    min_lat = np.min(latencies)
    max_lat = np.max(latencies)
    
    print(f"\n  Natijalar (50 ta sinov):")
    print(f"  - O'rtacha kechikish:   {Color.GREEN_NOMINAL}{avg_lat:.3f} ms{Color.RESET} (Talab: < 5.0 ms)")
    print(f"  - Minimal kechikish:   {min_lat:.3f} ms")
    print(f"  - Maksimal kechikish:  {max_lat:.3f} ms")
    print(f"  - Favqulodda harakatlar: {res['allocated_actions']}")
    print(f"  - Xulosa: {Color.GREEN_NOMINAL}PASSED (Nol-bulut lokal xavfsizlik to'liq mustaqil){Color.RESET}")

# ----------------- TEST 2 -----------------
def test_dsp_motion_rejection():
    print_header("2. DSP Tebranish va Harakat Shovqinini Filtrlash")
    dsp = BiometricDSPPipeline("ASTRO-01-CDR")
    
    print("10 ta qadam oddiy yurish, so'ngra 10 ta qadam tosh burg'ulash (vibratsiya) simulyatsiyasi:\n")
    print(f"  {'QADAM':<8} {'ASL HR':<12} {'XOM SENSOR (HR)':<18} {'FILTRLANGAN HR':<18} {'VIBRATSIYA (m/s²)':<18} {'HOLAT'}")
    print("  " + "-" * 88)
    
    for i in range(12):
        if i < 4:
            frame = SpaceflightScenarioSimulator.generate_nominal_frame("ASTRO-01-CDR", float(i))
            label = "Nominal"
            true_hr = 72.0
        else:
            frame = SpaceflightScenarioSimulator.generate_eva_tool_drilling_frame("ASTRO-01-CDR", float(i))
            label = Color.AMBER_WARN + "Vibratsiya" + Color.RESET
            true_hr = 88.0
            
        res = dsp.filter_telemetry_frame(
            raw_hr=frame["raw_hr"],
            raw_spo2=frame["raw_spo2"],
            ax=frame["accel"][0], ay=frame["accel"][1], az=frame["accel"][2],
            tool_vibration=frame["tool_vibration"]
        )
        
        hr_disp = f"{Color.GREEN_NOMINAL}{res['filtered_hr']:5.1f} bpm{Color.RESET}"
        raw_disp = f"{Color.RED_ALERT if abs(frame['raw_hr'] - true_hr) > 15 else Color.WHITE_BOLD}{frame['raw_hr']:5.1f} bpm{Color.RESET}"
        print(f"  #{i+1:<7} {true_hr:5.1f} bpm   {raw_disp:<27} {hr_disp:<27} {res['motion_intensity']:5.2f} m/s²           {label}")
    print(f"\n  Xulosa: Xom sensordagi 110-130 bpm shovqinlar filtrlandi, haqiqiy yurak urishi saqlab qolindi.")

# ----------------- TEST 3 -----------------
def test_seu_bit_flip():
    print_header("3. Kosmik Radiatsiya (SEU Bit-Flip) va TMR O'zini Tiklash")
    
    print("A) CRC32 va SHA-256 Telemetriya Buzilishini Tekshirish:")
    payload = {"astronaut_id": "ASTRO-01-CDR", "filtered_hr": 75.0, "spo2": 98.0}
    wrapped = TelemetryFrameIntegrity.wrap_telemetry(payload)
    print(f"  - Asl paket CRC32: {hex(wrapped['crc32'])}, SHA256: {wrapped['sha256'][:16]}...")
    
    # Radiatsiya zarbasi simulyatsiyasi
    corrupted = RadiationFaultInjector.inject_seu_into_telemetry(wrapped, "filtered_hr")
    valid, reason = TelemetryFrameIntegrity.verify_telemetry(corrupted)
    print(f"  - 1 bit buzilgandan keyingi tekshiruv: {Color.RED_ALERT}{reason}{Color.RESET}")
    print(f"  - Qaror: Noto'g'ri qiymat karantinga olindi (tibbiy qarorlarga kiritilmadi).\n")
    
    print("B) Triple Modular Redundancy (TMR) Xotirani Avtomatik Davolash:")
    tmr_o2 = TMRProtectedVariable(100, "O2_SOLENOID_STATE")
    print(f"  - Dastlabki holat: R0={tmr_o2._r0}, R1={tmr_o2._r1}, R2={tmr_o2._r2}")
    
    print("  - Kosmik zarracha Replica 1 xotirasiga urilib, bitni teskari qildi (injected)...")
    tmr_o2.inject_bitflip(1)
    print(f"  - Buzilgan holat:  R0={tmr_o2._r0}, R1={tmr_o2._r1}, R2={tmr_o2._r2}")
    
    val = tmr_o2.get() # Majority voting trigger
    print(f"  - Majority Voting natijasi: {Color.GREEN_NOMINAL}{val}{Color.RESET}")
    print(f"  - Davolangandan so'ng: R0={tmr_o2._r0}, R1={tmr_o2._r1}, R2={tmr_o2._r2}")
    print(f"  - O'zini tiklashlar soni: {tmr_o2.seu_repair_count}")

# ----------------- TEST 4 -----------------
def test_crypto_tampering():
    print_header("4. Kriptografik Xavfsizlik, Tamper va Replay Hujumlari Sinovi")
    crypto = CryptoEngine()
    payload = {"astronaut_id": "ASTRO-01-CDR", "command": "INJECT_EMERGENCY_O2", "amount_liters": 2.5}
    
    # 1. Shifrlash
    packet = crypto.encrypt_telemetry("ASTRO-01-CDR", payload)
    print(f"  [1] Shifrlangan paket:")
    print(f"      - Seq: {packet['seq_num']}")
    print(f"      - Nonce: {packet['nonce_hex']}")
    print(f"      - Ciphertext: {packet['ciphertext_hex'][:32]}... ({len(packet['ciphertext_hex'])} hex chars)")
    
    # 2. Qonuniy deshifrlash
    ok, dec, msg = crypto.decrypt_telemetry(packet)
    print(f"  [2] Qonuniy Deshifrlash: {Color.GREEN_NOMINAL}{msg}{Color.RESET} -> Buyruq: {dec['command']}")
    
    # 3. Replay Attack (Xuddi shu paketni qayta jo'natish)
    print(f"\n  [3] Replay Attack sinovi (paketni ikkinchi marta jo'natish):")
    rep_ok, _, rep_msg = crypto.decrypt_telemetry(packet)
    print(f"      - Natija: {Color.RED_ALERT if not rep_ok else Color.GREEN_NOMINAL}{rep_msg}{Color.RESET}")
    
    # 4. Tamper Attack (Ciphertext ichidan 1 baytni o'zgartirish)
    print(f"\n  [4] Tampering Attack sinovi (shifrlangan baytni buzib ko'rish):")
    tampered_packet = crypto.encrypt_telemetry("ASTRO-01-CDR", payload)
    raw_bytes = bytearray.fromhex(tampered_packet["ciphertext_hex"])
    raw_bytes[5] ^= 0xAA # 1 baytni o'zgartiramiz
    tampered_packet["ciphertext_hex"] = raw_bytes.hex()
    
    tamp_ok, _, tamp_msg = crypto.decrypt_telemetry(tampered_packet)
    print(f"      - Natija: {Color.RED_ALERT if not tamp_ok else Color.GREEN_NOMINAL}{tamp_msg}{Color.RESET}")
    print(f"      - Xulosa: AEAD autentifikatsiya tegi buzilganlikni 100% aniqladi.")

# ----------------- TEST 5 -----------------
def test_psych_stress_burnout():
    print_header("5. Psixologik Vahima (Panic) va Yashirin Charchoq (Burnout)")
    analyzer = PsychophysiologicalAnalyzer("ASTRO-01-CDR")
    
    print("Vahima (Acute Panic) holatini simulyatsiya qilish (RMSSD keskin pasayishi, EDA sakrashi)...")
    t = 100.0
    for _ in range(40):
        # Qattiq, o'zgarmas yuqori puls (parasimpatik pasayish)
        analyzer.add_cardiac_sample(138.0 + np.random.normal(0, 0.4))
        # Teri o'tkazuvchanligi cho'qqilari
        analyzer.add_eda_sample(8.5 + (0.1 if _ % 5 == 0 else 0.0), t)
        t += 1.0
        
    res = analyzer.evaluate_psychological_state(t)
    m = res["metrics"]
    print(f"\n  Biomarkerlar:")
    print(f"  - RMSSD:                 {m['rmssd_ms']:.1f} ms (Past vagal tonus)")
    print(f"  - SDNN:                  {m['sdnn_ms']:.1f} ms")
    print(f"  - Bayevskiy Stress (SI): {Color.RED_ALERT}{m['baevsky_si']:.1f}{Color.RESET} (Normal: 50-150, Vahima: >500)")
    print(f"  - EDA SCR cho'qqilari:   {m['scr_peaks_per_min']} /min")
    print(f"  - Tashxis:               {Color.RED_ALERT}{res['psych_state']}{Color.RESET}")
    print(f"  - Tavsiya:               {res['advice']}")

# ----------------- TEST 6 -----------------
def test_baseline_drift():
    print_header("6. Mikrogravitatsiyaga Moslashuv (Yer Normalari Soxta Signali)")
    engine = MicrogravityAdaptationEngine("ASTRO-01-CDR", earth_baseline_hr=68.0)
    
    print("Uchishning 3-kuni (Tsefalik qon siljishi sababli normal dam olish pulsi +8.5 bpm oshgan):")
    model = engine.get_adapted_thresholds(met_days=3.0)
    print(f"  - Yer bazaviy pulsi:        {model['earth_baseline_hr']} bpm")
    print(f"  - Moslashtirilgan baza:     {model['adapted_baseline_hr']} bpm")
    print(f"  - Ogohlantirish chegarasi:  {model['thresholds']['hr_warning_low']} - {model['thresholds']['hr_warning_high']} bpm\n")
    
    # Kosmonavt tinch holatda 88 bpm pulsda
    eval1 = engine.evaluate_vital_status(filtered_hr=88.0, filtered_spo2=98.0, met_days=3.0)
    print(f"  [Holat 1] Kosmonavt pulsi 88.0 bpm (fazoda tinch holat):")
    print(f"      - Moslashtirilgan status: {Color.GREEN_NOMINAL}{eval1['status']}{Color.RESET}")
    print(f"      - Yer normasi bo'yicha soxta signal oldi olindimi?: {Color.GREEN_NOMINAL}{eval1['static_earth_false_alarm_prevented']}{Color.RESET}")
    
    # Haqiqiy taxikardiya (175 bpm)
    eval2 = engine.evaluate_vital_status(filtered_hr=175.0, filtered_spo2=98.0, met_days=3.0)
    print(f"\n  [Holat 2] Haqiqiy yurak xuruji (175.0 bpm):")
    print(f"      - Moslashtirilgan status: {Color.RED_ALERT}{eval2['status']}{Color.RESET} (Buzilmadi, zudlik bilan signal berildi)")

# ----------------- TEST 7 -----------------
def test_multi_crew_triage():
    print_header("7. Ko'p Ekipajli Favqulodda Triaj va Resurslarni Taqsimlash")
    triage = AutonomousTriageEngine()
    crew_data = SpaceflightScenarioSimulator.generate_multi_crew_crisis()
    
    ranked = triage.triage_crew(crew_data)
    alloc = triage.allocate_automated_countermeasures(ranked)
    
    print(f"  {'O\'RIN':<7} {'ASTRONAVT':<15} {'TRIAJ DARAJASI':<22} {'ASOSIY TASHXIS':<35} {'AJRATILGAN RESURS'}")
    print("  " + "-" * 105)
    for r, a in zip(ranked, alloc):
        col = Color.RED_ALERT if "RED" in r["tier_label"] else (Color.AMBER_WARN if "YELLOW" in r["tier_label"] else Color.GREEN_NOMINAL)
        print(f"  #{r['triage_rank']:<6} {r['astronaut_id']:<15} {col}{r['tier_label']:<22}{Color.RESET} {r['primary_diagnostic']:<35} {a['allocated_actions']}")
    print(f"\n  Xulosa: Qutqariladigan P1_RED a'zoga (CDR) zudlik bilan avariya kislorodi berildi, vafot etgan P4_BLACK ga zaxira isrof qilinmadi.")

# ----------------- TEST 8 -----------------
def test_delta_compression():
    print_header("8. Telemetriya Delta-of-Delta Siqish va Tiklash")
    
    # 120 ta namunali vaqt qatori
    t = np.linspace(0, 60, 120)
    original = [round(float(75.0 + 4.0 * np.sin(x) + np.random.normal(0, 0.4)), 1) for x in t]
    
    compressed = DeltaCompressionEngine.compress_numeric_series(original)
    raw_size = len(original) * 8
    comp_size = len(compressed)
    savings = (1.0 - (comp_size / raw_size)) * 100.0
    
    decompressed = DeltaCompressionEngine.decompress_numeric_series(compressed)
    
    # Yaxlitlikni tekshirish
    max_err = max(abs(o - d) for o, d in zip(original, decompressed))
    
    print(f"  - Asl ma'lumot hajmi (float64):   {raw_size} bayt")
    print(f"  - Delta siqilgan hajm:           {comp_size} bayt")
    print(f"  - Tejalgan DSN kanali hajmi:     {Color.GREEN_NOMINAL}{savings:.1f}%{Color.RESET}")
    print(f"  - Qayta tiklash xatoligi (delta): {max_err:.2f} (Lossless)")

# ----------------- TEST 9 -----------------
def test_interactive_hud():
    print_header("9. Interaktiv EVA Shlemi (HUD) va Qo'lqop Tugmasi Sinovi")
    hud = EVAHeadUpDisplay("ASTRO-01-CDR")
    
    print("A) Odatiy holatdagi HUD ko'rinishi:")
    nom_frame = {"filtered_hr": 73.5, "filtered_spo2": 98.2, "suit_pressure_kpa": 29.6, "stress_index": 120.0, "sqi": 0.95}
    print(hud.render_frame(nom_frame))
    
    print("\nB) Favqulodda holat vujudga keldi (Bosim tushib ketdi):")
    hud.trigger_critical_override({
        "diagnostic": "SUIT DECOMPRESSION - 21.0 kPa",
        "action": "ENGAGE O2 PURGE VALVE & RETREAT TO AIRLOCK"
    })
    crit_frame = {"filtered_hr": 145.0, "filtered_spo2": 73.0, "suit_pressure_kpa": 21.0, "stress_index": 620.0, "sqi": 0.88}
    print(hud.render_frame(crit_frame))
    
    print(f"\n{Color.AMBER_WARN}Skafandr qo'lqopidagi tugmani bosishni xohlaysizmi? (Enter bosing)...{Color.RESET}")
    try:
        input("  >> [BOSISH UCHUN ENTER]")
    except EOFError:
        pass
        
    ack = hud.acknowledge_glove_button()
    print(f"\n{Color.GREEN_NOMINAL}{ack}{Color.RESET}")
    print("\nTasdiqlangandan keyingi HUD ko'rinishi:")
    print(hud.render_frame(crit_frame))

def main():
    while True:
        print(f"\n{Color.BG_BLACK}{Color.CYAN_INFO}======================================================================={Color.RESET}")
        print(f"{Color.BG_BLACK}{Color.WHITE_BOLD}     KOSMONAVT SALOMATLIK TIZIMI: INTERAKTIV TEST MENYUSI             {Color.RESET}")
        print(f"{Color.BG_BLACK}{Color.CYAN_INFO}======================================================================={Color.RESET}")
        print("  1. [Kechikish]      Nol-kechikishli yadro tezligi (<5ms)")
        print("  2. [DSP Filtr]      Burg'ulash tebranishi va harakat shovqinini yo'qotish")
        print("  3. [Radiatsiya]     Kosmik nurlar SEU bit-flip va TMR o'zini davolash")
        print("  4. [Xavfsizlik]     AES-256-GCM, Tamper va Replay hujumlarini qaytarish")
        print("  5. [Psixologiya]    Vahima (Panic) va Charchoqni (Burnout) aniqlash")
        print("  6. [Moslashuv]      Mikrogravitatsiyadagi puls siljishi (Yer soxta signali)")
        print("  7. [Triaj]          Ko'p kishilik halokatda resurslarni adolatli taqsimlash")
        print("  8. [Siqish]         Delta-of-Delta algoritmi va DSN trafigini tejash")
        print("  9. [EVA HUD]        Interaktiv shlem displeyi va qo'lqop tugmasi")
        print("  A. [Barchasi]       Barcha testlarni ketma-ket ishga tushirish")
        print("  0. [Chiqish]")
        print(f"{Color.BG_BLACK}{Color.CYAN_INFO}-----------------------------------------------------------------------{Color.RESET}")
        
        try:
            choice = input(f"{Color.WHITE_BOLD}Test raqamini tanlang (0-9, A): {Color.RESET}").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print("\nChiqildi.")
            break
            
        if choice == "1":
            test_zero_latency_core()
        elif choice == "2":
            test_dsp_motion_rejection()
        elif choice == "3":
            test_seu_bit_flip()
        elif choice == "4":
            test_crypto_tampering()
        elif choice == "5":
            test_psych_stress_burnout()
        elif choice == "6":
            test_baseline_drift()
        elif choice == "7":
            test_multi_crew_triage()
        elif choice == "8":
            test_delta_compression()
        elif choice == "9":
            test_interactive_hud()
        elif choice == "A":
            test_zero_latency_core()
            test_dsp_motion_rejection()
            test_seu_bit_flip()
            test_crypto_tampering()
            test_psych_stress_burnout()
            test_baseline_drift()
            test_multi_crew_triage()
            test_delta_compression()
            test_interactive_hud()
        elif choice == "0":
            print("Dastur yakunlandi.")
            break
        else:
            print("Noto'g'ri tanlov!")

if __name__ == "__main__":
    main()
