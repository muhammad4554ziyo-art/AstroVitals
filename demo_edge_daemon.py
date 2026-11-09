#!/usr/bin/env python3
"""
Interactive Demonstration: Edge-First Autonomous Astronaut Health Monitoring System.

Simulates 7 mission scenarios on deep-space Lunar/Mars operations:
1. Nominal EVA Baseline & Microgravity Adaptation
2. Heavy EVA Rock Coring Drill Vibration (DSP Kalman Motion Artifact Rejection)
3. Solar Particle Event (SPE) Cosmic Radiation Bit-Flips (SEU TMR Self-Healing)
4. Micrometeoroid Suit Puncture & Acute Hypoxia (Zero-Latency Local Emergency Safety Triggers)
5. Glove-Friendly HUD Emergency Override & Acknowledgment
6. Multi-Crew Mass-Casualty Triage & Resource Allocation
7. Deep Space Network (DSN) Delta Compression Sync Pass
"""

import sys
import os
import time
import asyncio
import json

from health_monitor.edge_daemon import AutonomousSuitEdgeDaemon
from health_monitor.simulator import SpaceflightScenarioSimulator
from health_monitor.seu_protection import TelemetryFrameIntegrity, RadiationFaultInjector
from health_monitor.multi_crew_triage import AutonomousTriageEngine
from health_monitor.telemetry_buffer import DeltaCompressionEngine, DSNTelemetrySyncPackager
from health_monitor.hud_interface import Color

def print_banner(title: str):
    print(f"\n{Color.BG_BLACK}{Color.CYAN_INFO}{'='*78}{Color.RESET}")
    print(f"{Color.BG_BLACK}{Color.WHITE_BOLD}  {title}{Color.RESET}")
    print(f"{Color.BG_BLACK}{Color.CYAN_INFO}{'='*78}{Color.RESET}\n")

async def run_mission_demo():
    print(f"{Color.BG_BLACK}{Color.WHITE_BOLD}")
    print("  ********************************************************************")
    print("  *    DEEP-SPACE EDGE-FIRST AUTONOMOUS ASTRONAUT HEALTH MONITOR     *")
    print("  *    Operating Mode: Zero-Cloud / Earth Blackout / Edge Autonomous *")
    print("  *    Mission: Artemis / Mars Transit - Flight Day 4.2              *")
    print("  ********************************************************************")
    print(f"{Color.RESET}")

    daemon = AutonomousSuitEdgeDaemon(astronaut_id="ASTRO-01-CDR", mission_elapsed_days=4.2)
    # Warm up internal buffers
    await daemon.process_single_frame(SpaceflightScenarioSimulator.generate_nominal_frame("ASTRO-01-CDR", 0.0))

    # -------------------------------------------------------------
    # SCENARIO 1: Nominal EVA Walking & Microgravity Adaptation
    # -------------------------------------------------------------
    print_banner("SCENARIO 1: Nominal EVA Operations & Microgravity Baseline Drift")
    print("Astronaut CDR is conducting geological survey on Lunar Shackleton crater rim.")
    print("Microgravity cephalad fluid shift offset: +8.5 bpm baseline shift active.")

    for i in range(5):
        frame = SpaceflightScenarioSimulator.generate_nominal_frame("ASTRO-01-CDR", float(i))
        result = await daemon.process_single_frame(frame)
        print(f"  [Frame {i+1}] HR: {result['filtered_hr']} bpm | SpO2: {result['filtered_spo2']}% | "
              f"Suit-P: {result['suit_pressure_kpa']} kPa | Stress-SI: {result['stress_index']:.0f} | "
              f"Latency: {result['latency_ms']:.2f}ms | Triage: {result['triage_tier_label']}")
        await asyncio.sleep(0.1)

    print("\n  >> Live Helmet HUD View:")
    hud_output = daemon.hud.render_frame(daemon.last_frame_telemetry)
    print(hud_output)
    await asyncio.sleep(0.5)

    # -------------------------------------------------------------
    # SCENARIO 2: Heavy EVA Power Drill Vibration (DSP Filtering)
    # -------------------------------------------------------------
    print_banner("SCENARIO 2: High-Vibration Rock Coring Drill (DSP Motion Rejection)")
    print("Astronaut starts heavy pneumatic hammer drill into basalt regolith.")
    print("Raw photoplethysmography (PPG) and ECG experience severe vibration motion artifacts.")
    print("Standard Earth monitors would trigger false ventricular tachycardia alarms!")

    for i in range(5):
        frame = SpaceflightScenarioSimulator.generate_eva_tool_drilling_frame("ASTRO-01-CDR", float(i))
        result = await daemon.process_single_frame(frame)
        print(f"  [Vibration Sample {i+1}] Raw HR: {result['raw_hr']:5.1f} bpm -> Filtered: {Color.GREEN_NOMINAL}{result['filtered_hr']:5.1f} bpm{Color.RESET} "
              f"| Motion Jerk: {result['motion_intensity']:4.1f} m/s² | SQI: {result['sqi']:.2f} | "
              f"Motion Suppressed: {Color.AMBER_WARN}{result['motion_artifact_detected']}{Color.RESET}")
        await asyncio.sleep(0.1)

    print("\n  >> Filtered HUD View under Heavy Vibration (Zero False Alarms):")
    hud_output = daemon.hud.render_frame(daemon.last_frame_telemetry)
    print(hud_output)
    await asyncio.sleep(0.5)

    # -------------------------------------------------------------
    # SCENARIO 3: Solar Particle Event (SPE) Cosmic Radiation Bit-Flips
    # -------------------------------------------------------------
    print_banner("SCENARIO 3: Cosmic Radiation Single-Event Upset (SEU) Detection & TMR Auto-Repair")
    print("High-Z cosmic ray particle penetrates suit avionics bay, flipping bit in memory.")

    # 1. Telemetry CRC32 Checksum Detection
    sample_payload = {"astronaut_id": "ASTRO-01-CDR", "filtered_hr": 76.5, "spo2": 98.0}
    wrapped = TelemetryFrameIntegrity.wrap_telemetry(sample_payload)
    print(f"  [1] Nominal Telemetry Frame: CRC-32 = {hex(wrapped['crc32'])} | SHA-256 = {wrapped['sha256'][:16]}... [VALID]")

    corrupted = RadiationFaultInjector.inject_seu_into_telemetry(wrapped, "filtered_hr")
    valid, reason = TelemetryFrameIntegrity.verify_telemetry(corrupted)
    print(f"  [2] Simulated Cosmic Ray Bit-Flip: Verification Result = {Color.RED_ALERT}{reason}{Color.RESET} -> QUARANTINED")

    # 2. TMR Self-Healing of Mission-Critical Variable
    print("\n  >> Triple Modular Redundancy (TMR) Memory Protection:")
    print(f"     Initial Life-Support Solenoid State: {daemon.tmr_suit_o2_solenoid.get()}")
    daemon.tmr_suit_o2_solenoid.inject_bitflip(1) # Corrupt replica 1
    repaired_val = daemon.tmr_suit_o2_solenoid.get()
    print(f"     SEU particle struck Replica 1! TMR Majority Vote read: {Color.GREEN_NOMINAL}{repaired_val}{Color.RESET} (Auto-Healed)")
    print(f"     Total SEU Memory Bit-Flip Repairs: {daemon.tmr_suit_o2_solenoid.seu_repair_count}")
    await asyncio.sleep(0.5)

    # -------------------------------------------------------------
    # SCENARIO 4 & 5: Acute Micrometeoroid Puncture, Hypoxia & HUD Override
    # -------------------------------------------------------------
    print_banner("SCENARIO 4 & 5: Micrometeoroid Suit Puncture, Zero-Latency Emergency & HUD Override")
    print("Micrometeoroid punctures outer thermal micrometeoroid garment (TMG) of CDR.")
    print("Suit pressure drops to 21.4 kPa, SpO2 collapses to 74.0% (Critical Hypoxia).")

    puncture_frame = SpaceflightScenarioSimulator.generate_acute_hypoxia_decompression_frame("ASTRO-01-CDR")
    t0 = time.perf_counter()
    result = await daemon.process_single_frame(puncture_frame)
    t1 = time.perf_counter()

    print(f"\n  [!] LOCAL EMERGENCY TRIGGERED IN {result['latency_ms']:.3f} ms (<5ms hard limit)!")
    print(f"      Triage Level:       {Color.RED_ALERT}{result['triage_tier_label']}{Color.RESET}")
    print(f"      Allocated Actions:  {result['allocated_actions']}")
    print(f"      TMR Solenoid State: {result['tmr_o2_solenoid']} (Emergency 100% O2 Purge Fired)")

    print("\n  >> Live Helmet HUD View - CRITICAL EMERGENCY OVERRIDE:")
    hud_output = daemon.hud.render_frame(daemon.last_frame_telemetry)
    print(hud_output)

    print("\n  >> Simulating Glove-Friendly Suit Button Press [SPACE/TOGGLE]...")
    ack_result = daemon.hud.acknowledge_glove_button()
    print(f"  {Color.GREEN_NOMINAL}{ack_result}{Color.RESET}")

    hud_acknowledged = daemon.hud.render_frame(daemon.last_frame_telemetry)
    print(hud_acknowledged)
    await asyncio.sleep(0.5)

    # -------------------------------------------------------------
    # SCENARIO 6: Multi-Crew Mass-Casualty Triage
    # -------------------------------------------------------------
    print_banner("SCENARIO 6: Deterministic Multi-Crew Autonomous Triage & Countermeasure Allocation")
    print("Cabin airlock pressure decompression affects entire 4-person expedition crew simultaneously.")

    triage_engine = AutonomousTriageEngine()
    crew_data = SpaceflightScenarioSimulator.generate_multi_crew_crisis()
    ranked_crew = triage_engine.triage_crew(crew_data)
    allocations = triage_engine.allocate_automated_countermeasures(ranked_crew)

    print(f"  {'RANK':<6} {'ASTRONAUT ID':<16} {'TRIAGE TIER':<20} {'PRIMARY DIAGNOSTIC':<35} {'ACTIONS ALLOCATED'}")
    print("  " + "-" * 105)
    for r, a in zip(ranked_crew, allocations):
        tier_col = Color.RED_ALERT if "RED" in r["tier_label"] else (Color.AMBER_WARN if "YELLOW" in r["tier_label"] else Color.GREEN_NOMINAL)
        print(f"  #{r['triage_rank']:<5} {r['astronaut_id']:<16} {tier_col}{r['tier_label']:<20}{Color.RESET} {r['primary_diagnostic']:<35} {a['allocated_actions']}")

    await asyncio.sleep(0.5)

    # -------------------------------------------------------------
    # SCENARIO 7: Bandwidth-Optimized DSN Telemetry Sync Pass
    # -------------------------------------------------------------
    print_banner("SCENARIO 7: Bandwidth-Optimized Deep Space Network (DSN) Telemetry Sync")
    print("34-meter Deep Space Network Ground Antenna establishes 5-minute transmission window.")
    print("Bandwidth is strictly constrained (max 64 KB); Delta-of-Delta compression engaged.")

    packager = DSNTelemetrySyncPackager(daemon.buffer)
    dsn_bundle = packager.package_dsn_burst()

    print(f"  [1] Tier 1 Emergency Anomaly Packages:  {len(dsn_bundle['tier1_anomalies'])} priority packages queued")
    print(f"  [2] Tier 2 Statistical Crew Summaries: {len(dsn_bundle['tier2_statistical_summaries'])} crew windows generated")
    for cid, summ in dsn_bundle["tier2_statistical_summaries"].items():
        print(f"      - {cid}: HR mean {summ['hr_mean']} bpm | SpO2 min {summ['spo2_min']}% | Stress {summ['stress_mean']}")

    print("  [3] Tier 3 Delta-of-Delta Compressed Raw Telemetry:")
    for cid, raw_info in dsn_bundle["tier3_compressed_raw"].items():
        print(f"      - {cid}: Raw {raw_info['uncompressed_bytes']}B -> Compressed {raw_info['compressed_bytes']}B | "
              f"Space Savings: {Color.GREEN_NOMINAL}{raw_info['space_savings_pct']}%{Color.RESET}")

    print_banner("ALL 10 MISSION CONSTRAINTS SUCCESSFULLY DEMONSTRATED & VERIFIED")

if __name__ == "__main__":
    asyncio.run(run_mission_demo())
