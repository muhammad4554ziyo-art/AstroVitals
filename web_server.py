#!/usr/bin/env python3
"""
AstroLogic X - NASA Open MCT-Style Autonomous Space Health Monitoring Console.

Designed in accordance with NASA Open MCT, cFS, and Artemis Glass Cockpit standards:
- Dark tactical theme, NASA Time Conductor, Domain Object Sidebar
- Multi-channel live Canvas biometric waveforms with tolerance bands
- Autonomous Triage, Microgravity Drift Tracker, and Life Support Actuators
- Interactive Cryptography & SEU Radiation Security Playground
"""

import os
import sys
import time
import json
import asyncio
import threading
from typing import Dict, Any, List
from flask import Flask, jsonify, request, render_template_string

from health_monitor.config import SecurityConfig, MissionParams
from health_monitor.edge_daemon import AutonomousSuitEdgeDaemon
from health_monitor.simulator import SpaceflightScenarioSimulator
from health_monitor.seu_protection import TelemetryFrameIntegrity, RadiationFaultInjector
from health_monitor.multi_crew_triage import AutonomousTriageEngine
from health_monitor.telemetry_buffer import DeltaCompressionEngine, DSNTelemetrySyncPackager
from health_monitor.crypto_layer import CryptoEngine

app = Flask(__name__)

# Core monitoring daemon
daemon = AutonomousSuitEdgeDaemon("ASTRO-01-CDR", mission_elapsed_days=4.2)
crypto = CryptoEngine()
triage_engine = AutonomousTriageEngine()

# Simulation state
scenario_state = {
    "mode": "NOMINAL",       # NOMINAL, DRILLING, HYPOXIA, PANIC, MULTI_CREW
    "tool_vibration": 0.0,
    "last_bit_flip_event": None,
    "last_crypto_attack_result": None,
    "multi_crew_data": [],
    "recent_frames": []
}

def simulation_background_loop():
    """Continuous real-time sensor generation and edge evaluation."""
    t_step = 0.0
    while True:
        try:
            mode = scenario_state["mode"]
            astro_id = "ASTRO-01-CDR"

            if mode == "NOMINAL":
                frame = SpaceflightScenarioSimulator.generate_nominal_frame(astro_id, t_step)
            elif mode == "DRILLING":
                frame = SpaceflightScenarioSimulator.generate_eva_tool_drilling_frame(astro_id, t_step)
            elif mode == "HYPOXIA":
                frame = SpaceflightScenarioSimulator.generate_acute_hypoxia_decompression_frame(astro_id)
            elif mode == "PANIC":
                frame = SpaceflightScenarioSimulator.generate_acute_panic_frame(astro_id)
            else:
                frame = SpaceflightScenarioSimulator.generate_nominal_frame(astro_id, t_step)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(daemon.process_single_frame(frame))
            finally:
                loop.close()

            scenario_state["recent_frames"].append(result)
            if len(scenario_state["recent_frames"]) > 60:
                scenario_state["recent_frames"].pop(0)

            if mode == "MULTI_CREW":
                raw_crew = SpaceflightScenarioSimulator.generate_multi_crew_crisis()
                ranked = triage_engine.triage_crew(raw_crew)
                alloc = triage_engine.allocate_automated_countermeasures(ranked)
                scenario_state["multi_crew_data"] = [
                    {**r, "allocated_actions": a["allocated_actions"]}
                    for r, a in zip(ranked, alloc)
                ]
            else:
                crew_snapshots = [
                    {"astronaut_id": "ASTRO-01-CDR", "filtered_hr": result["filtered_hr"], "filtered_spo2": result["filtered_spo2"], "suit_pressure_kpa": result["suit_pressure_kpa"], "stress_index": result["stress_index"]},
                    {"astronaut_id": "ASTRO-02-PLT", "filtered_hr": 74.0, "filtered_spo2": 98.4, "suit_pressure_kpa": 29.6, "stress_index": 120.0},
                    {"astronaut_id": "ASTRO-03-MS1", "filtered_hr": 78.5, "filtered_spo2": 97.9, "suit_pressure_kpa": 29.5, "stress_index": 150.0},
                    {"astronaut_id": "ASTRO-04-MS2", "filtered_hr": 71.0, "filtered_spo2": 98.8, "suit_pressure_kpa": 29.6, "stress_index": 95.0}
                ]
                ranked = triage_engine.triage_crew(crew_snapshots)
                alloc = triage_engine.allocate_automated_countermeasures(ranked)
                scenario_state["multi_crew_data"] = [
                    {**r, "allocated_actions": a["allocated_actions"]}
                    for r, a in zip(ranked, alloc)
                ]

            t_step += 0.5
            time.sleep(0.5)
        except Exception as exc:
            print("Background loop exception:", exc)
            time.sleep(1.0)

bg_thread = threading.Thread(target=simulation_background_loop, daemon=True)
bg_thread.start()

# ----------------- API ENDPOINTS -----------------

@app.route("/api/telemetry", methods=["GET"])
def get_telemetry():
    last_frame = daemon.last_frame_telemetry or {}
    hud_alert = daemon.hud.active_critical_alert
    is_ack = daemon.hud.is_acknowledged

    return jsonify({
        "status": "OK",
        "mode": scenario_state["mode"],
        "telemetry": last_frame,
        "hud_alert": hud_alert,
        "hud_acknowledged": is_ack,
        "tmr_repairs": daemon.tmr_suit_o2_solenoid.seu_repair_count,
        "history": scenario_state["recent_frames"][-30:],
        "multi_crew": scenario_state["multi_crew_data"],
        "last_bit_flip": scenario_state["last_bit_flip_event"],
        "last_crypto_attack": scenario_state["last_crypto_attack_result"],
        "server_time": time.time()
    })

@app.route("/api/scenario", methods=["POST"])
def set_scenario():
    data = request.get_json(force=True) or {}
    new_mode = data.get("mode", "NOMINAL").upper()
    if new_mode in ["NOMINAL", "DRILLING", "HYPOXIA", "PANIC", "MULTI_CREW"]:
        scenario_state["mode"] = new_mode
        if new_mode == "NOMINAL":
            daemon.hud.clear_alert()
        return jsonify({"status": "SUCCESS", "mode": new_mode})
    return jsonify({"status": "ERROR", "message": "Invalid mode"}), 400

@app.route("/api/hud/acknowledge", methods=["POST"])
def acknowledge_hud():
    msg = daemon.hud.acknowledge_glove_button()
    return jsonify({"status": "SUCCESS", "message": msg})

@app.route("/api/test/bitflip", methods=["POST"])
def inject_bitflip():
    payload = {"astronaut_id": "ASTRO-01-CDR", "filtered_hr": 76.5, "spo2": 98.0}
    wrapped = TelemetryFrameIntegrity.wrap_telemetry(payload)
    corrupted = RadiationFaultInjector.inject_seu_into_telemetry(wrapped, "filtered_hr")
    valid, reason = TelemetryFrameIntegrity.verify_telemetry(corrupted)

    daemon.tmr_suit_o2_solenoid.inject_bitflip(1)
    healed = daemon.tmr_suit_o2_solenoid.get()

    event = {
        "timestamp": time.time(),
        "type": "COSMIC_RAY_SEU_SPE",
        "crc_status": reason,
        "quarantined": not valid,
        "tmr_repaired_val": healed,
        "total_tmr_repairs": daemon.tmr_suit_o2_solenoid.seu_repair_count
    }
    scenario_state["last_bit_flip_event"] = event
    return jsonify({"status": "SUCCESS", "event": event})

@app.route("/api/test/crypto_attack", methods=["POST"])
def test_crypto_attack():
    data = request.get_json(force=True) or {}
    attack_type = data.get("type", "TAMPER").upper()

    sample_payload = {"astronaut_id": "ASTRO-01-CDR", "command": "O2_PURGE", "ts": time.time()}
    packet = crypto.encrypt_telemetry("ASTRO-01-CDR", sample_payload)

    if attack_type == "REPLAY":
        crypto.decrypt_telemetry(packet)
        ok, _, reason = crypto.decrypt_telemetry(packet)
        result = {
            "attack": "REPLAY_ATTACK",
            "detected": not ok,
            "status_message": reason,
            "verdict": "BLOCKED" if not ok else "FAILED"
        }
    else:
        tampered_pkt = dict(packet)
        c_bytes = bytearray.fromhex(tampered_pkt["ciphertext_hex"])
        c_bytes[4] ^= 0xFF
        tampered_pkt["ciphertext_hex"] = c_bytes.hex()
        ok, _, reason = crypto.decrypt_telemetry(tampered_pkt)
        result = {
            "attack": "CIPHERTEXT_TAMPER_ATTACK",
            "detected": not ok,
            "status_message": reason,
            "verdict": "BLOCKED" if not ok else "FAILED"
        }

    scenario_state["last_crypto_attack_result"] = result
    return jsonify({"status": "SUCCESS", "result": result})

@app.route("/api/dsn/sync", methods=["GET"])
def get_dsn_sync():
    packager = DSNTelemetrySyncPackager(daemon.buffer)
    bundle = packager.package_dsn_burst()
    return jsonify({"status": "SUCCESS", "dsn_bundle": bundle})

# ----------------- NASA OPEN MCT-STYLE HTML TEMPLATE -----------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AstroLogic X - NASA Open MCT Autonomous Space Medicine Platform</title>
    <style>
        :root {
            --bg-root: #0a0d14;
            --bg-sidebar: #0f141f;
            --bg-surface: #141b2a;
            --bg-card: #182235;
            --bg-card-hover: #1f2b42;
            --border-subtle: #223048;
            --border-strong: #314466;

            /* NASA / Open MCT Palette */
            --nasa-blue: #0b3d91;
            --nasa-red: #fc3d21;
            --accent-cyan: #00e5ff;
            --accent-green: #00ff88;
            --accent-amber: #ffb700;
            --accent-red: #ff2a55;

            --text-primary: #edf2fa;
            --text-secondary: #8da4c4;
            --text-muted: #576d8c;
            --font-mono: 'JetBrains Mono', 'SF Pro Mono', 'SFMono-Regular', Consolas, Menlo, monospace;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: var(--bg-root);
            color: var(--text-primary);
            font-family: var(--font-mono);
            font-size: 12px;
            line-height: 1.4;
            overflow-x: hidden;
        }

        /* ---------------- TOP FLIGHT BAR (Open MCT Header) ---------------- */
        .flight-bar {
            height: 48px;
            background: linear-gradient(90deg, #0e1422 0%, #151e33 50%, #0e1422 100%);
            border-bottom: 1px solid var(--border-subtle);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 16px;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .brand-container {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-svg {
            width: 32px;
            height: 32px;
            filter: drop-shadow(0 0 6px rgba(0, 229, 255, 0.6));
        }

        .brand-text {
            display: flex;
            flex-direction: column;
        }

        .brand-title {
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 1.5px;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .brand-title span {
            color: var(--accent-cyan);
        }

        .brand-subtitle {
            font-size: 9px;
            color: var(--text-muted);
            letter-spacing: 0.8px;
        }

        .conductor-clock {
            display: flex;
            align-items: center;
            gap: 20px;
            background: rgba(0, 0, 0, 0.4);
            padding: 6px 14px;
            border-radius: 4px;
            border: 1px solid var(--border-subtle);
        }

        .clock-item {
            display: flex;
            flex-direction: column;
            text-align: center;
        }

        .clock-lbl {
            font-size: 9px;
            color: var(--text-muted);
            text-transform: uppercase;
        }

        .clock-val {
            font-size: 13px;
            font-weight: 700;
            color: var(--text-primary);
        }

        .status-badge {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            background: rgba(0, 255, 136, 0.1);
            border: 1px solid var(--accent-green);
            color: var(--accent-green);
        }

        .status-pulse {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--accent-green);
            box-shadow: 0 0 8px var(--accent-green);
            animation: pulse-dot 1.5s infinite;
        }

        @keyframes pulse-dot {
            0%, 100% { opacity: 0.5; transform: scale(0.9); }
            50% { opacity: 1; transform: scale(1.2); }
        }

        /* ---------------- APP LAYOUT: SIDEBAR + WORKSPACE ---------------- */
        .app-body {
            display: grid;
            grid-template-columns: 240px 1fr 340px;
            height: calc(100vh - 48px);
            overflow: hidden;
        }

        /* LEFT SIDEBAR (Domain Tree Hierarchy) */
        .sidebar {
            background: var(--bg-sidebar);
            border-right: 1px solid var(--border-subtle);
            padding: 12px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .sidebar-section-title {
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 6px;
        }

        .tree-node {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 8px;
            border-radius: 4px;
            color: var(--text-secondary);
            cursor: pointer;
            transition: 0.15s;
        }

        .tree-node:hover {
            background: var(--bg-surface);
            color: var(--text-primary);
        }

        .tree-node.active {
            background: rgba(0, 229, 255, 0.12);
            color: var(--accent-cyan);
            border-left: 2px solid var(--accent-cyan);
            font-weight: bold;
        }

        .node-icon {
            font-size: 12px;
            color: var(--text-muted);
        }

        /* CENTER WORKSPACE */
        .workspace {
            padding: 14px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 14px;
            background: radial-gradient(circle at 50% 20%, #101624 0%, #0a0d14 100%);
        }

        /* CRITICAL EMERGENCY HUD OVERRIDE BANNER */
        #emergency-banner {
            display: none;
            background: linear-gradient(90deg, #3d0510, #220308);
            border: 2px solid var(--accent-red);
            border-radius: 6px;
            padding: 16px 20px;
            animation: red-glow 1s infinite alternate;
        }

        @keyframes red-glow {
            from { box-shadow: 0 0 12px rgba(255, 42, 85, 0.4); }
            to { box-shadow: 0 0 30px rgba(255, 42, 85, 0.9); }
        }

        .emergency-grid {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
        }

        .btn-ack {
            background: var(--accent-red);
            color: #fff;
            border: none;
            padding: 14px 28px;
            font-size: 13px;
            font-weight: 800;
            font-family: var(--font-mono);
            border-radius: 4px;
            cursor: pointer;
            box-shadow: 0 0 20px rgba(255, 42, 85, 0.8);
            transition: 0.2s;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .btn-ack:hover {
            background: #ff476d;
            transform: scale(1.02);
        }

        .btn-ack.acknowledged {
            background: #143521;
            color: var(--accent-green);
            border: 1px solid var(--accent-green);
            box-shadow: none;
            cursor: default;
        }

        /* TACTICAL METRIC CARDS */
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
        }

        .gauge-card {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: 6px;
            padding: 12px 14px;
            display: flex;
            flex-direction: column;
            gap: 6px;
            position: relative;
            overflow: hidden;
        }

        .gauge-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: var(--border-strong);
        }

        .gauge-card.nominal::before { background: var(--accent-green); }
        .gauge-card.warning::before { background: var(--accent-amber); }
        .gauge-card.critical::before { background: var(--accent-red); }

        .gauge-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 10px;
            color: var(--text-muted);
        }

        .gauge-value {
            font-size: 26px;
            font-weight: 800;
            color: var(--text-primary);
            letter-spacing: 0.5px;
        }

        .gauge-sub {
            display: flex;
            justify-content: space-between;
            font-size: 10px;
            color: var(--text-secondary);
        }

        /* TIME CONDUCTOR MULTI-CHANNEL CANVAS */
        .chart-card {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: 6px;
            padding: 14px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .chart-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .chart-title {
            font-weight: 700;
            font-size: 12px;
            color: var(--accent-cyan);
            letter-spacing: 0.5px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .chart-legend {
            display: flex;
            gap: 14px;
            font-size: 10px;
        }

        .legend-item {
            display: flex;
            align-items: center;
            gap: 6px;
            color: var(--text-secondary);
        }

        .legend-dot {
            width: 8px;
            height: 8px;
            border-radius: 2px;
        }

        canvas {
            width: 100%;
            height: 190px;
            background: #080c14;
            border: 1px solid var(--border-subtle);
            border-radius: 4px;
            display: block;
        }

        /* SCENARIO ACTION DOCK (Bottom Center) */
        .action-dock {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: 6px;
            padding: 12px;
        }

        .dock-title {
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }

        .scenarios-toolbar {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 8px;
        }

        .btn-toolbar {
            background: #101726;
            border: 1px solid var(--border-subtle);
            color: var(--text-secondary);
            padding: 8px 10px;
            font-family: var(--font-mono);
            font-size: 10px;
            font-weight: 600;
            border-radius: 4px;
            cursor: pointer;
            text-align: center;
            transition: 0.15s;
        }

        .btn-toolbar:hover {
            border-color: var(--accent-cyan);
            color: var(--text-primary);
            background: #172238;
        }

        .btn-toolbar.active {
            border-color: var(--accent-cyan);
            background: rgba(0, 229, 255, 0.15);
            color: var(--accent-cyan);
        }

        /* RIGHT INSPECTOR PANEL */
        .inspector {
            background: var(--bg-sidebar);
            border-left: 1px solid var(--border-subtle);
            padding: 14px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .panel-block {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: 6px;
            padding: 12px;
        }

        .panel-title {
            font-size: 11px;
            font-weight: 700;
            color: var(--accent-cyan);
            text-transform: uppercase;
            letter-spacing: 0.8px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        /* TRIAGE TABLE */
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 11px;
        }
        th, td {
            padding: 6px 8px;
            text-align: left;
            border-bottom: 1px solid var(--border-subtle);
        }
        th { color: var(--text-muted); font-weight: normal; font-size: 10px; }

        .tier-pill {
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 9px;
            font-weight: 700;
            display: inline-block;
        }
        .tier-red { background: rgba(255, 42, 85, 0.2); color: var(--accent-red); border: 1px solid var(--accent-red); }
        .tier-yellow { background: rgba(255, 183, 0, 0.2); color: var(--accent-amber); border: 1px solid var(--accent-amber); }
        .tier-green { background: rgba(0, 255, 136, 0.2); color: var(--accent-green); border: 1px solid var(--accent-green); }
        .tier-black { background: #1a1e26; color: #738299; border: 1px solid #333d4d; }

        /* SECURITY TERMINAL */
        .terminal-log {
            background: #060910;
            border: 1px solid var(--border-subtle);
            border-radius: 4px;
            padding: 8px 10px;
            font-size: 10px;
            color: #7d96b8;
            height: 120px;
            overflow-y: auto;
            margin-top: 8px;
        }

        .btn-test {
            background: #131c2b;
            border: 1px solid var(--border-subtle);
            color: var(--accent-cyan);
            padding: 5px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-family: var(--font-mono);
            font-size: 10px;
            transition: 0.15s;
        }
        .btn-test:hover {
            background: #1b283d;
            border-color: var(--accent-cyan);
        }
    </style>
</head>
<body>

    <!-- 1. FLIGHT BAR (NASA Open MCT Conductor) -->
    <header class="flight-bar">
        <div class="brand-container">
            <!-- Custom AstroLogic X Vector Logo -->
            <svg class="logo-svg" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="50" cy="50" r="44" stroke="#1c2a40" stroke-width="4"/>
                <path d="M15 50C15 30 85 30 85 50C85 70 15 70 15 50Z" stroke="#00e5ff" stroke-width="3" stroke-dasharray="6 4"/>
                <!-- Stylized X -->
                <path d="M30 25L70 75M70 25L30 75" stroke="#ffffff" stroke-width="6" stroke-linecap="round"/>
                <!-- Pulse Core -->
                <circle cx="50" cy="50" r="9" fill="#ff2a55"/>
                <path d="M40 50H46L49 44L52 56L55 50H60" stroke="#00ff88" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <div class="brand-text">
                <div class="brand-title">ASTROLOGIC <span>X</span></div>
                <div class="brand-subtitle">AUTONOMOUS SPACE HEALTH MONITORING OS</div>
            </div>
        </div>

        <!-- Central Time Conductor Clocks -->
        <div class="conductor-clock">
            <div class="clock-item">
                <span class="clock-lbl">MISSION ELAPSED TIME</span>
                <span class="clock-val" id="lbl-met">MET 004 / 05:22:18</span>
            </div>
            <div class="clock-item">
                <span class="clock-lbl">EDGE LATENCY</span>
                <span class="clock-val" style="color: var(--accent-green);" id="lbl-lat">0.69 ms</span>
            </div>
            <div class="clock-item">
                <span class="clock-lbl">DSN LINK BUDGET</span>
                <span class="clock-val" style="color: var(--accent-amber);">BLACKOUT (4m Delay)</span>
            </div>
        </div>

        <!-- Mode & Status Badges -->
        <div style="display: flex; align-items: center; gap: 10px;">
            <div class="status-badge">
                <div class="status-pulse"></div>
                <span>EDGE AUTONOMOUS</span>
            </div>
        </div>
    </header>

    <!-- 2. MAIN BODY (Sidebar, Center Workspace, Right Inspector) -->
    <div class="app-body">
        
        <!-- LEFT: Domain Object Hierarchy Tree -->
        <aside class="sidebar">
            <div>
                <div class="sidebar-section-title">Telemetry Hierarchy</div>
                <div class="tree-node active">
                    <span class="node-icon">▼</span>
                    <span>AstroLogic Core</span>
                </div>
                <div style="padding-left: 14px;">
                    <div class="tree-node active">
                        <span class="node-icon">●</span>
                        <span>ASTRO-01-CDR (EVA)</span>
                    </div>
                    <div class="tree-node">
                        <span class="node-icon">○</span>
                        <span>ASTRO-02-PLT (Cabin)</span>
                    </div>
                    <div class="tree-node">
                        <span class="node-icon">○</span>
                        <span>ASTRO-03-MS1 (Science)</span>
                    </div>
                    <div class="tree-node">
                        <span class="node-icon">○</span>
                        <span>ASTRO-04-MS2 (Flight)</span>
                    </div>
                </div>
            </div>

            <div>
                <div class="sidebar-section-title">Life Support Systems (LSS)</div>
                <div class="tree-node">
                    <span class="node-icon">▷</span>
                    <span>Suit Pressure Solenoid</span>
                </div>
                <div class="tree-node">
                    <span class="node-icon">▷</span>
                    <span>Emergency O2 Reserve</span>
                </div>
                <div class="tree-node">
                    <span class="node-icon">▷</span>
                    <span>Liquid Cooling Loop</span>
                </div>
            </div>

            <div>
                <div class="sidebar-section-title">Security & Avionics</div>
                <div class="tree-node">
                    <span class="node-icon">🛡️</span>
                    <span>AES-256-GCM AEAD Pipe</span>
                </div>
                <div class="tree-node">
                    <span class="node-icon">⚡</span>
                    <span>TMR SEU Memory Scrubber</span>
                </div>
                <div class="tree-node">
                    <span class="node-icon">📡</span>
                    <span>DSN Delta Queue (WAL)</span>
                </div>
            </div>
        </aside>

        <!-- CENTER: Main Telemetry View & Charts -->
        <main class="workspace">
            
            <!-- EMERGENCY SCREEN OVERRIDE -->
            <div id="emergency-banner">
                <div class="emergency-grid">
                    <div>
                        <div style="color: var(--accent-red); font-size: 15px; font-weight: 800; letter-spacing: 0.8px;">
                            ⚠️ CRITICAL LIFE-SUPPORT OVERRIDE -- IMMEDIATE ACTION REQUIRED
                        </div>
                        <div style="font-size: 12px; color: #fff; margin-top: 4px;" id="override-diagnostic">
                            Rapid Suit Decompression (21.4 kPa) -- Acute Hypoxia Detected!
                        </div>
                        <div style="color: var(--accent-amber); font-size: 11px; margin-top: 3px;" id="override-action">
                            DIRECTIVE: ENGAGE SUIT O2 PURGE VALVE & RETREAT TO HABITAT AIRLOCK
                        </div>
                    </div>
                    <div>
                        <button class="btn-ack" id="btn-glove-ack" onclick="acknowledgeAlert()">
                            [⬡] GLOVE ACK (SPACE)
                        </button>
                    </div>
                </div>
            </div>

            <!-- TACTICAL METRIC GAUGES -->
            <div class="metrics-grid">
                <div class="gauge-card nominal" id="card-hr">
                    <div class="gauge-top">
                        <span>HEART RATE (KALMAN)</span>
                        <span id="badge-motion" style="color: var(--text-muted);">NOMINAL</span>
                    </div>
                    <div class="gauge-value" id="val-hr">72.4</div>
                    <div class="gauge-sub">
                        <span>RAW SENSOR: <strong id="val-raw-hr">73.1</strong> bpm</span>
                        <span>SQI: <strong id="lbl-sqi" style="color: var(--accent-green);">95%</strong></span>
                    </div>
                </div>

                <div class="gauge-card nominal" id="card-spo2">
                    <div class="gauge-top">
                        <span>OXYGEN SATURATION</span>
                        <span>SpO2</span>
                    </div>
                    <div class="gauge-value" id="val-spo2">98.2</div>
                    <div class="gauge-sub">
                        <span>THRESHOLD: &gt;90%</span>
                        <span style="color: var(--accent-green);">SAFE OXYGENATION</span>
                    </div>
                </div>

                <div class="gauge-card nominal" id="card-p">
                    <div class="gauge-top">
                        <span>SUIT PRESSURE</span>
                        <span>4.3 PSI NOM</span>
                    </div>
                    <div class="gauge-value" id="val-p">29.6</div>
                    <div class="gauge-sub">
                        <span>MIN SAFE: 22.0 kPa</span>
                        <span>SUIT LOOP OK</span>
                    </div>
                </div>

                <div class="gauge-card nominal" id="card-stress">
                    <div class="gauge-top">
                        <span>BAEVSKY STRESS (SI)</span>
                        <span id="lbl-psych" style="color: var(--accent-cyan);">OPTIMAL</span>
                    </div>
                    <div class="gauge-value" id="val-stress">105</div>
                    <div class="gauge-sub">
                        <span>RMSSD: <strong id="val-rmssd">42</strong> ms</span>
                        <span>SCR PEAKS: <strong id="val-scr">1</strong>/min</span>
                    </div>
                </div>
            </div>

            <!-- MULTI-CHANNEL TIME CONDUCTOR CANVAS -->
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title">
                        <span>REAL-TIME BIOMETRIC TELEMETRY & DSP KALMAN MOTION FILTER</span>
                    </div>
                    <div class="chart-legend">
                        <div class="legend-item">
                            <div class="legend-dot" style="background: rgba(255, 42, 85, 0.8);"></div>
                            <span>Raw Sensor (Noise Spikes)</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-dot" style="background: var(--accent-green);"></div>
                            <span>Kalman Filtered HR</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-dot" style="background: var(--accent-amber);"></div>
                            <span>IMU Tool Vibration</span>
                        </div>
                    </div>
                </div>
                <canvas id="waveformCanvas" width="800" height="190"></canvas>
                <div style="display: flex; justify-content: space-between; font-size: 10px; color: var(--text-muted);">
                    <div>Harakat va Tebranish Akseleratsiyasi: <strong style="color: var(--accent-amber);" id="lbl-motion">0.12 m/s²</strong></div>
                    <div>Skafandr Gaptik Impulsi: <strong style="color: var(--accent-cyan);" id="lbl-haptic">STANDBY</strong></div>
                    <div>Audio Klaxon Holati: <strong style="color: var(--accent-green);" id="lbl-audio">MUTED (NOMINAL)</strong></div>
                </div>
            </div>

            <!-- SCENARIO SWITCHER DOCK -->
            <div class="action-dock">
                <div class="dock-title">Spaceflight Simulation & Hazard Scenarios</div>
                <div class="scenarios-toolbar">
                    <button class="btn-toolbar active" id="btn-scen-nominal" onclick="setScenario('NOMINAL')">
                        1. NOMINAL EVA
                    </button>
                    <button class="btn-toolbar" id="btn-scen-drilling" onclick="setScenario('DRILLING')">
                        2. TOOL DRILLING
                    </button>
                    <button class="btn-toolbar" id="btn-scen-hypoxia" onclick="setScenario('HYPOXIA')">
                        3. SUIT PUNCTURE
                    </button>
                    <button class="btn-toolbar" id="btn-scen-panic" onclick="setScenario('PANIC')">
                        4. PSYCH PANIC
                    </button>
                    <button class="btn-toolbar" id="btn-scen-multi_crew" onclick="setScenario('MULTI_CREW')">
                        5. MULTI-CREW
                    </button>
                    <button class="btn-toolbar" onclick="fetchDSN()">
                        6. DSN SYNC
                    </button>
                </div>
            </div>
        </main>

        <!-- RIGHT: NASA Autonomous Triage & Security Inspector -->
        <aside class="inspector">
            
            <!-- MULTI-CREW DETERMINISTIC TRIAGE -->
            <div class="panel-block">
                <div class="panel-title">
                    <span>Autonomous Space Triage</span>
                    <span style="font-size: 9px; color: var(--text-muted);">Priority Min-Heap</span>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>RANK</th>
                            <th>CREW</th>
                            <th>TIER</th>
                            <th>HR</th>
                            <th>SpO2</th>
                        </tr>
                    </thead>
                    <tbody id="triage-body">
                        <!-- Filled by JS -->
                    </tbody>
                </table>
            </div>

            <!-- MICROGRAVITY ADAPTATION TRACKER -->
            <div class="panel-block">
                <div class="panel-title">
                    <span>Microgravity Adaptation</span>
                    <span style="font-size: 9px; color: var(--accent-green);">Day 4.2</span>
                </div>
                <div style="font-size: 11px; display: flex; flex-direction: column; gap: 4px; color: var(--text-secondary);">
                    <div>Tsefalik Suyuqlik Siljishi: <strong style="color: var(--accent-cyan);">+8.5 bpm</strong></div>
                    <div>Yer Normal Baza: <strong>68.0 bpm</strong></div>
                    <div>Moslashtirilgan Fazoviy Baza: <strong style="color: var(--accent-green);">76.5 bpm</strong></div>
                    <div style="font-size: 10px; color: var(--text-muted); margin-top: 4px;">
                        ✓ Yer me'yori bo'yicha soxta signallar bloklangan.
                    </div>
                </div>
            </div>

            <!-- SECURITY & SEU HARBOR CONSOLE -->
            <div class="panel-block">
                <div class="panel-title">
                    <span>Avionics & Crypto Security</span>
                </div>
                <div style="display: flex; gap: 6px; margin-bottom: 8px;">
                    <button class="btn-test" onclick="injectBitFlip()">⚡ SEU Bit-Flip</button>
                    <button class="btn-test" onclick="testCryptoAttack('TAMPER')">🛡️ Tamper Test</button>
                    <button class="btn-test" onclick="testCryptoAttack('REPLAY')">🔁 Replay Test</button>
                </div>
                <div style="font-size: 10px; color: var(--text-muted); display: flex; justify-content: space-between;">
                    <span>TMR O'zini Tiklash: <strong style="color: var(--accent-green);" id="lbl-tmr">0</strong></span>
                    <span>AES-GCM AEAD: <strong style="color: var(--accent-cyan);">VALID</strong></span>
                </div>
                <div class="terminal-log" id="sec-log">
                    [00:00:01] AstroLogic X Engine Secure Boot (Umask 077, 0600 keys).<br>
                    [00:00:02] Anti-Replay sliding window filter armed.<br>
                    [00:00:03] Triple Modular Redundancy (TMR) watchdog active.
                </div>
            </div>

        </aside>

    </div>

    <!-- JAVASCRIPT LOGIC -->
    <script>
        let rawHistory = [];
        let filteredHistory = [];

        function appendLog(msg) {
            const el = document.getElementById("sec-log");
            const time = new Date().toTimeString().split(' ')[0];
            el.innerHTML = `[${time}] ${msg}<br>` + el.innerHTML;
        }

        async function updateTelemetry() {
            try {
                const res = await fetch("/api/telemetry");
                const data = await res.json();
                const t = data.telemetry;

                if (!t || Object.keys(t).length === 0) return;

                // Numbers
                document.getElementById("val-hr").innerText = t.filtered_hr.toFixed(1);
                document.getElementById("val-raw-hr").innerText = t.raw_hr.toFixed(1);
                document.getElementById("val-spo2").innerText = t.filtered_spo2.toFixed(1);
                document.getElementById("val-p").innerText = t.suit_pressure_kpa.toFixed(1);
                document.getElementById("val-stress").innerText = Math.round(t.stress_index);
                document.getElementById("lbl-psych").innerText = t.psych_state || "NOMINAL";
                document.getElementById("lbl-sqi").innerText = Math.round((t.sqi || 1) * 100) + "%";
                document.getElementById("lbl-motion").innerText = (t.motion_intensity || 0).toFixed(2) + " m/s²";
                document.getElementById("lbl-lat").innerText = (t.latency_ms || 0.6).toFixed(2) + " ms";
                document.getElementById("lbl-tmr").innerText = data.tmr_repairs;

                // Gauges cards color states
                const cHr = document.getElementById("card-hr");
                const cSp = document.getElementById("card-spo2");
                const cP = document.getElementById("card-p");

                if (t.filtered_hr > 140 || t.filtered_hr < 45) cHr.className = "gauge-card critical";
                else if (t.filtered_hr > 110) cHr.className = "gauge-card warning";
                else cHr.className = "gauge-card nominal";

                if (t.filtered_spo2 < 80) cSp.className = "gauge-card critical";
                else if (t.filtered_spo2 < 90) cSp.className = "gauge-card warning";
                else cSp.className = "gauge-card nominal";

                if (t.suit_pressure_kpa < 22) cP.className = "gauge-card critical";
                else cP.className = "gauge-card nominal";

                // Audio & Haptics
                if (t.allocated_actions && t.allocated_actions.includes("LOCAL_HAPTIC_TRIPLE_PULSE_250HZ")) {
                    document.getElementById("lbl-haptic").innerText = "250Hz RAPID VIBRO-BURST";
                    document.getElementById("lbl-haptic").style.color = "var(--accent-red)";
                    document.getElementById("lbl-audio").innerText = "800Hz KLAXON ACTIVE";
                    document.getElementById("lbl-audio").style.color = "var(--accent-red)";
                } else if (t.motion_artifact_detected) {
                    document.getElementById("lbl-haptic").innerText = "DSP VIB-CANCELLATION";
                    document.getElementById("lbl-haptic").style.color = "var(--accent-amber)";
                    document.getElementById("lbl-audio").innerText = "MUTED";
                    document.getElementById("lbl-audio").style.color = "var(--text-muted)";
                } else {
                    document.getElementById("lbl-haptic").innerText = "STANDBY";
                    document.getElementById("lbl-haptic").style.color = "var(--accent-cyan)";
                    document.getElementById("lbl-audio").innerText = "MUTED (NOMINAL)";
                    document.getElementById("lbl-audio").style.color = "var(--accent-green)";
                }

                // Emergency override
                const banner = document.getElementById("emergency-banner");
                const ackBtn = document.getElementById("btn-glove-ack");
                if (data.hud_alert) {
                    banner.style.display = "block";
                    document.getElementById("override-diagnostic").innerText = data.hud_alert.diagnostic || "CRITICAL EVENT";
                    document.getElementById("override-action").innerText = "DIRECTIVE: " + (data.hud_alert.action || "SEAL AIRLOCK");
                    if (data.hud_acknowledged) {
                        ackBtn.innerText = "✓ ACKNOWLEDGED BY WEARER";
                        ackBtn.className = "btn-ack acknowledged";
                    } else {
                        ackBtn.innerText = "[⬡] GLOVE ACK (SPACE)";
                        ackBtn.className = "btn-ack";
                    }
                } else {
                    banner.style.display = "none";
                }

                // Multi-crew Table
                const tbody = document.getElementById("triage-body");
                tbody.innerHTML = "";
                (data.multi_crew || []).forEach(c => {
                    let pillCls = "tier-green";
                    if (c.tier_label.includes("RED")) pillCls = "tier-red";
                    else if (c.tier_label.includes("YELLOW")) pillCls = "tier-yellow";
                    else if (c.tier_label.includes("BLACK")) pillCls = "tier-black";

                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td>#${c.triage_rank}</td>
                        <td><strong>${c.astronaut_id.split('-')[2] || c.astronaut_id}</strong></td>
                        <td><span class="tier-pill ${pillCls}">${c.tier_label.split('_')[1]}</span></td>
                        <td>${c.filtered_hr.toFixed(0)}</td>
                        <td>${c.filtered_spo2.toFixed(0)}%</td>
                    `;
                    tbody.appendChild(tr);
                });

                // Waveform update
                rawHistory.push(t.raw_hr);
                filteredHistory.push(t.filtered_hr);
                if (rawHistory.length > 80) rawHistory.shift();
                if (filteredHistory.length > 80) filteredHistory.shift();
                drawWaveform();

            } catch (err) {
                console.error("Telemetry fetch error:", err);
            }
        }

        function drawWaveform() {
            const canvas = document.getElementById("waveformCanvas");
            const ctx = canvas.getContext("2d");
            const w = canvas.width;
            const h = canvas.height;

            ctx.fillStyle = "#080c14";
            ctx.fillRect(0, 0, w, h);

            // Grid lines
            ctx.strokeStyle = "#141c2b";
            ctx.lineWidth = 1;
            for (let y = 30; y < h; y += 35) {
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(w, y);
                ctx.stroke();
            }

            // Normal Zone Shade (HR 60 to 100)
            const y100 = h - ((100 - 40) / 130) * (h - 20) - 10;
            const y60 = h - ((60 - 40) / 130) * (h - 20) - 10;
            ctx.fillStyle = "rgba(0, 255, 136, 0.04)";
            ctx.fillRect(0, y100, w, y60 - y100);

            if (rawHistory.length < 2) return;

            const stepX = w / 80;

            // Draw Raw Corrupted Line (Red)
            ctx.strokeStyle = "rgba(255, 42, 85, 0.65)";
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            rawHistory.forEach((val, idx) => {
                const y = h - ((val - 40) / 130) * (h - 20) - 10;
                if (idx === 0) ctx.moveTo(0, y);
                else ctx.lineTo(idx * stepX, y);
            });
            ctx.stroke();

            // Draw Filtered Kalman Line (Green)
            ctx.strokeStyle = "#00ff88";
            ctx.lineWidth = 2.5;
            ctx.shadowColor = "#00ff88";
            ctx.shadowBlur = 4;
            ctx.beginPath();
            filteredHistory.forEach((val, idx) => {
                const y = h - ((val - 40) / 130) * (h - 20) - 10;
                if (idx === 0) ctx.moveTo(0, y);
                else ctx.lineTo(idx * stepX, y);
            });
            ctx.stroke();
            ctx.shadowBlur = 0; // reset
        }

        async function setScenario(mode) {
            document.querySelectorAll(".btn-toolbar").forEach(b => b.classList.remove("active"));
            const btn = document.getElementById("btn-scen-" + mode.toLowerCase());
            if (btn) btn.classList.add("active");

            appendLog(`Rejim o'zgartirildi: ${mode}`);
            await fetch("/api/scenario", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({mode: mode})
            });
        }

        async function acknowledgeAlert() {
            const res = await fetch("/api/hud/acknowledge", {method: "POST"});
            const d = await res.json();
            appendLog(`[HUD] ${d.message}`);
        }

        window.addEventListener("keydown", (e) => {
            if (e.code === "Space") {
                const banner = document.getElementById("emergency-banner");
                if (banner.style.display !== "none") {
                    e.preventDefault();
                    acknowledgeAlert();
                }
            }
        });

        async function injectBitFlip() {
            const res = await fetch("/api/test/bitflip", {method: "POST"});
            const d = await res.json();
            appendLog(`<span style="color: var(--accent-amber);">⚡ SEU RADIATSIYA:</span> ${d.event.crc_status} -> TMR o'zini tikladi! (Jami: ${d.event.total_tmr_repairs})`);
        }

        async function testCryptoAttack(type) {
            const res = await fetch("/api/test/crypto_attack", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({type: type})
            });
            const d = await res.json();
            const r = d.result;
            appendLog(`<span style="color: var(--accent-red);">🛡️ HUJUM (${r.attack}):</span> ${r.status_message} -> [${r.verdict}]`);
        }

        async function fetchDSN() {
            const res = await fetch("/api/dsn/sync");
            const d = await res.json();
            const rawInfo = d.dsn_bundle.tier3_compressed_raw["ASTRO-01-CDR"];
            appendLog(`<span style="color: var(--accent-cyan);">📡 DSN SYNC:</span> Delta-of-Delta: ${rawInfo.space_savings_pct}% tejandi (${rawInfo.uncompressed_bytes}B -> ${rawInfo.compressed_bytes}B)`);
        }

        setInterval(updateTelemetry, 500);
        updateTelemetry();
    </script>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == "__main__":
    PORT = 8080
    HOST = "127.0.0.1"
    print(f"\n==================================================================")
    print(f"  ASTROLOGIC X - NASA OPEN MCT EDITION STARTED")
    print(f"  Local URL: http://{HOST}:{PORT}")
    print(f"==================================================================\n")
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
