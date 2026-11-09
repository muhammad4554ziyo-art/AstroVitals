#!/usr/bin/env python3
"""
AstroLogic X - NASA Mission Control Autonomous Space Medicine Platform.
Integrates Real-Time Suit Edge Telemetry and Bio-Digital Twin Pre-Mission Predictive Simulator.
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
from health_monitor.digital_twin import (
    get_default_crew,
    get_default_operations,
    DigitalTwinEngine
)

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
            time.sleep(1.0)

bg_thread = threading.Thread(target=simulation_background_loop, daemon=True)
bg_thread.start()

# ----------------- REST API ROUTES -----------------

@app.route("/api/telemetry", methods=["GET"])
def get_telemetry():
    if not scenario_state["recent_frames"]:
        return jsonify({"status": "WAITING"})
    latest = scenario_state["recent_frames"][-1]
    return jsonify({
        "latest": latest,
        "history": scenario_state["recent_frames"][-30:],
        "scenario": scenario_state["mode"],
        "multi_crew": scenario_state["multi_crew_data"],
        "bit_flip": scenario_state["last_bit_flip_event"],
        "crypto_attack": scenario_state["last_crypto_attack_result"]
    })

@app.route("/api/scenario", methods=["POST"])
def set_scenario():
    data = request.get_json(force=True) or {}
    mode = data.get("mode", "NOMINAL").upper()
    if mode in ["NOMINAL", "DRILLING", "HYPOXIA", "PANIC", "MULTI_CREW"]:
        scenario_state["mode"] = mode
        return jsonify({"status": "SUCCESS", "mode": mode})
    return jsonify({"status": "ERROR", "message": "Noma'lum ssenariy"}), 400

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

# Digital Twin Endpoints
@app.route("/api/digital_twin/crew", methods=["GET"])
def api_dt_crew():
    crew = get_default_crew()
    return jsonify({aid: a.to_dict() for aid, a in crew.items()})

@app.route("/api/digital_twin/operations", methods=["GET"])
def api_dt_operations():
    ops = get_default_operations()
    return jsonify({oid: op.to_dict() for oid, op in ops.items()})

@app.route("/api/digital_twin/simulate", methods=["POST"])
def api_dt_simulate():
    data = request.get_json(force=True) or {}
    astro_id = data.get("astronaut_id")
    op_id = data.get("operation_id")
    crew = get_default_crew()
    ops = get_default_operations()

    if not astro_id or astro_id not in crew:
        return jsonify({"error": "Noma'lum astronavt ID"}), 400
    if not op_id or op_id not in ops:
        return jsonify({"error": "Noma'lum operatsiya ID"}), 400

    report = DigitalTwinEngine.run_simulation(crew[astro_id], ops[op_id])
    return jsonify(report.to_dict())


# ----------------- NASA OPEN MCT-STYLE HTML TEMPLATE -----------------

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AstroLogic X | NASA Mission Control & Bio-Digital Twin Platform</title>
    <style>
        :root {
            --bg-root: #06090e;
            --bg-sidebar: #0b111b;
            --bg-surface: #101928;
            --bg-card: #152238;
            --bg-card-hover: #1c2e4c;
            --border-subtle: #1e304f;
            --border-strong: #2c4672;

            /* NASA Colors */
            --nasa-blue: #0b3d91;
            --nasa-blue-light: #1e5cb8;
            --nasa-red: #fc3d21;
            --accent-cyan: #00e5ff;
            --accent-green: #00ff88;
            --accent-amber: #ffb700;
            --accent-red: #ff2a55;
            --accent-purple: #a855f7;

            --text-primary: #f0f4fc;
            --text-secondary: #9cb1d1;
            --text-muted: #5e779e;
            --font-mono: 'JetBrains Mono', 'SF Pro Mono', Consolas, monospace;
            --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background-color: var(--bg-root);
            color: var(--text-primary);
            font-family: var(--font-sans);
            height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            font-size: 13px;
            user-select: none;
        }

        /* 1. TOP FLIGHT BAR (NASA OPEN MCT CONDUCTOR) */
        .flight-bar {
            height: 48px;
            background: linear-gradient(180deg, #0f1827 0%, #0a101a 100%);
            border-bottom: 1px solid var(--border-strong);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 16px;
            flex-shrink: 0;
            z-index: 100;
        }
        .brand-container {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .brand-logo-badge {
            background: linear-gradient(135deg, var(--nasa-blue) 0%, var(--nasa-red) 100%);
            color: #fff;
            font-weight: 900;
            font-size: 11px;
            letter-spacing: 1px;
            padding: 4px 8px;
            border-radius: 4px;
            display: flex;
            align-items: center;
            gap: 5px;
            border: 1px solid rgba(255,255,255,0.2);
        }
        .brand-text {
            font-family: var(--font-mono);
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 0.8px;
        }
        .brand-text span { color: var(--accent-cyan); }
        .brand-sub {
            font-size: 9px;
            color: var(--text-muted);
            letter-spacing: 0.5px;
        }

        /* Navigation Tabs */
        .nav-tabs {
            display: flex;
            gap: 4px;
            background: #090e17;
            padding: 3px;
            border-radius: 6px;
            border: 1px solid var(--border-subtle);
        }
        .nav-tab-btn {
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-family: var(--font-mono);
            font-size: 11px;
            padding: 6px 14px;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s ease;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .nav-tab-btn:hover {
            color: #fff;
            background: rgba(255,255,255,0.05);
        }
        .nav-tab-btn.active {
            background: var(--nasa-blue);
            color: #fff;
            box-shadow: 0 0 10px rgba(11, 61, 145, 0.5);
        }

        .conductor-clock {
            display: flex;
            align-items: center;
            gap: 16px;
            font-family: var(--font-mono);
            font-size: 11px;
        }
        .clock-item {
            display: flex;
            flex-direction: column;
            text-align: right;
        }
        .clock-lbl { font-size: 8px; color: var(--text-muted); letter-spacing: 0.5px; }
        .clock-val { font-weight: 700; color: var(--text-primary); }

        /* 2. MAIN WORKSPACE */
        .app-workspace {
            flex: 1;
            display: flex;
            overflow: hidden;
            position: relative;
        }

        .tab-content {
            display: none;
            flex: 1;
            overflow-y: auto;
            padding: 16px;
            gap: 16px;
        }
        .tab-content.active {
            display: flex;
            flex-direction: column;
        }

        /* CARDS & PANELS */
        .panel {
            background: var(--bg-surface);
            border: 1px solid var(--border-subtle);
            border-radius: 8px;
            padding: 16px;
            position: relative;
        }
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
            border-bottom: 1px solid var(--border-subtle);
            padding-bottom: 10px;
        }
        .panel-title {
            font-family: var(--font-mono);
            font-size: 13px;
            font-weight: 800;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .panel-subtitle {
            font-size: 11px;
            color: var(--text-muted);
        }

        /* 3. STEP GUIDES */
        .step-badge {
            background: #19273c;
            color: var(--accent-cyan);
            border: 1px solid var(--border-strong);
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 10px;
            font-weight: 700;
            font-family: var(--font-mono);
        }

        /* 4. CREW SELECTOR GRID */
        .crew-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 12px;
        }
        .crew-card {
            background: var(--bg-card);
            border: 2px solid var(--border-subtle);
            border-radius: 8px;
            padding: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            position: relative;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .crew-card:hover {
            border-color: var(--border-strong);
            transform: translateY(-2px);
            background: var(--bg-card-hover);
        }
        .crew-card.selected {
            border-color: var(--accent-cyan);
            background: #142845;
            box-shadow: 0 0 14px rgba(0, 229, 255, 0.25);
        }
        .crew-card-top {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .crew-avatar {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: #090e17;
            border: 2px solid var(--border-strong);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            flex-shrink: 0;
        }
        .crew-card.selected .crew-avatar {
            border-color: var(--accent-cyan);
        }
        .crew-name {
            font-weight: 800;
            font-size: 13px;
            color: #fff;
        }
        .crew-role {
            font-size: 10px;
            color: var(--accent-cyan);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .crew-specs {
            display: flex;
            flex-direction: column;
            gap: 4px;
            font-size: 10px;
            color: var(--text-secondary);
            font-family: var(--font-mono);
            border-top: 1px solid rgba(255,255,255,0.06);
            padding-top: 6px;
        }
        .crew-spec-row {
            display: flex;
            justify-content: space-between;
        }

        /* 5. OPERATIONS GRID */
        .ops-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 12px;
        }
        .op-card {
            background: var(--bg-card);
            border: 2px solid var(--border-subtle);
            border-radius: 8px;
            padding: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            flex-direction: column;
            gap: 8px;
            position: relative;
        }
        .op-card:hover {
            border-color: var(--border-strong);
            transform: translateY(-2px);
            background: var(--bg-card-hover);
        }
        .op-card.selected {
            border-color: var(--accent-amber);
            background: #252014;
            box-shadow: 0 0 14px rgba(255, 183, 0, 0.25);
        }
        .op-card.level-5.selected {
            border-color: var(--accent-red);
            background: #281119;
            box-shadow: 0 0 16px rgba(255, 42, 85, 0.35);
        }
        .op-level-badge {
            font-family: var(--font-mono);
            font-size: 9px;
            font-weight: 800;
            padding: 2px 6px;
            border-radius: 4px;
            width: fit-content;
            letter-spacing: 0.5px;
        }
        .lvl-1 { background: rgba(0,255,136,0.15); color: var(--accent-green); border: 1px solid var(--accent-green); }
        .lvl-2 { background: rgba(0,229,255,0.15); color: var(--accent-cyan); border: 1px solid var(--accent-cyan); }
        .lvl-3 { background: rgba(255,183,0,0.15); color: var(--accent-amber); border: 1px solid var(--accent-amber); }
        .lvl-4 { background: rgba(168,85,247,0.15); color: var(--accent-purple); border: 1px solid var(--accent-purple); }
        .lvl-5 { background: rgba(255,42,85,0.2); color: var(--accent-red); border: 1px solid var(--accent-red); }

        .op-title {
            font-weight: 800;
            font-size: 12px;
            color: #fff;
            line-height: 1.3;
            min-height: 32px;
        }
        .op-target {
            font-size: 10px;
            color: var(--text-muted);
        }
        .op-specs {
            display: flex;
            flex-direction: column;
            gap: 3px;
            font-size: 10px;
            color: var(--text-secondary);
            font-family: var(--font-mono);
            border-top: 1px solid rgba(255,255,255,0.06);
            padding-top: 6px;
        }

        /* 6. LAUNCH ACTION BAR */
        .launch-bar {
            background: linear-gradient(90deg, #101c2e 0%, #162a47 100%);
            border: 1px solid var(--border-strong);
            border-radius: 8px;
            padding: 12px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .selection-summary {
            display: flex;
            align-items: center;
            gap: 20px;
        }
        .summary-item {
            display: flex;
            flex-direction: column;
        }
        .summary-lbl {
            font-size: 9px;
            color: var(--text-muted);
            letter-spacing: 0.5px;
            font-family: var(--font-mono);
        }
        .summary-val {
            font-size: 14px;
            font-weight: 800;
            color: #fff;
        }
        .btn-launch {
            background: linear-gradient(135deg, var(--nasa-blue) 0%, var(--nasa-blue-light) 100%);
            color: #fff;
            border: 1px solid var(--accent-cyan);
            border-radius: 6px;
            font-family: var(--font-mono);
            font-size: 13px;
            font-weight: 800;
            padding: 10px 24px;
            cursor: pointer;
            box-shadow: 0 0 15px rgba(0, 229, 255, 0.3);
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .btn-launch:hover {
            transform: scale(1.02);
            box-shadow: 0 0 20px rgba(0, 229, 255, 0.5);
        }

        /* 7. SIMULATION MONITOR & CANVAS */
        .sim-monitor-grid {
            display: grid;
            grid-template-columns: 1.5fr 1fr;
            gap: 16px;
        }
        .canvas-container {
            background: #070c14;
            border: 1px solid var(--border-strong);
            border-radius: 8px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .canvas-header {
            background: #0c1524;
            padding: 8px 12px;
            font-family: var(--font-mono);
            font-size: 11px;
            font-weight: 700;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--border-subtle);
            display: flex;
            justify-content: space-between;
        }
        #envCanvas {
            width: 100%;
            height: 230px;
            display: block;
            background: #000;
        }

        /* Vitals Dashboard */
        .vitals-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
        }
        .vital-box {
            background: #0e1624;
            border: 1px solid var(--border-subtle);
            border-radius: 6px;
            padding: 10px;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }
        .vital-lbl {
            font-size: 9px;
            color: var(--text-muted);
            font-family: var(--font-mono);
            letter-spacing: 0.5px;
        }
        .vital-val {
            font-size: 18px;
            font-weight: 800;
            font-family: var(--font-mono);
            color: #fff;
        }
        .vital-sub {
            font-size: 9px;
            color: var(--text-secondary);
        }

        /* Diagnostic Verdict Banner */
        .verdict-banner {
            border-radius: 8px;
            padding: 14px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: 10px;
        }
        .verdict-banner.go {
            background: rgba(0, 255, 136, 0.1);
            border: 1px solid var(--accent-green);
        }
        .verdict-banner.caution {
            background: rgba(255, 183, 0, 0.1);
            border: 1px solid var(--accent-amber);
        }
        .verdict-banner.fatal {
            background: rgba(255, 42, 85, 0.15);
            border: 2px solid var(--accent-red);
            animation: pulse-fatal 2s infinite;
        }
        @keyframes pulse-fatal {
            0% { box-shadow: 0 0 0 0 rgba(255, 42, 85, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(255, 42, 85, 0); }
            100% { box-shadow: 0 0 0 0 rgba(255, 42, 85, 0); }
        }

        /* Timeline Table */
        .sim-table-wrap {
            max-height: 180px;
            overflow-y: auto;
            border: 1px solid var(--border-subtle);
            border-radius: 6px;
            background: #0a0f18;
            margin-top: 12px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-family: var(--font-mono);
            font-size: 11px;
        }
        th {
            background: #0f1827;
            color: var(--text-muted);
            text-align: left;
            padding: 6px 10px;
            font-size: 9px;
            position: sticky;
            top: 0;
            border-bottom: 1px solid var(--border-subtle);
        }
        td {
            padding: 5px 10px;
            border-bottom: 1px solid rgba(255,255,255,0.03);
            color: var(--text-secondary);
        }
        tr:hover td {
            background: rgba(255,255,255,0.02);
        }

        /* REAL-TIME SUIT VIEW STYLES */
        .live-grid {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 16px;
        }

        /* EMERGENCY OVERRIDE BANNER */
        #emergency-banner {
            display: none;
            background: linear-gradient(90deg, rgba(255, 42, 85, 0.9) 0%, rgba(138, 12, 34, 0.9) 100%);
            border: 2px solid #fff;
            padding: 10px 16px;
            border-radius: 6px;
            margin-bottom: 12px;
        }
        .btn-ack {
            background: #fff;
            color: #b00;
            font-weight: 800;
            border: none;
            padding: 6px 14px;
            border-radius: 4px;
            cursor: pointer;
            font-family: var(--font-mono);
        }

        .btn-scen {
            background: #141f30;
            border: 1px solid var(--border-strong);
            color: #fff;
            padding: 8px 12px;
            border-radius: 4px;
            font-family: var(--font-mono);
            font-size: 11px;
            cursor: pointer;
        }
        .btn-scen.active {
            background: var(--nasa-blue);
            border-color: var(--accent-cyan);
        }
    </style>
</head>
<body>

    <!-- 1. FLIGHT BAR -->
    <header class="flight-bar">
        <div class="brand-container">
            <div class="brand-logo-badge">
                <span>NASA</span> / <span>AL-X</span>
            </div>
            <div class="brand-text">
                ASTROLOGIC <span>X</span>
            </div>
            <div class="brand-sub">AUTONOMOUS SPACE MEDICINE & DIGITAL TWIN OS</div>
        </div>

        <!-- Center Tabs -->
        <div class="nav-tabs">
            <button class="nav-tab-btn active" onclick="switchTab('tab-digital-twin')">
                🚀 1. DIGITAL TWIN SIMULYATORI
            </button>
            <button class="nav-tab-btn" onclick="switchTab('tab-live-telemetry')">
                📡 2. REAL-VAQT TELEMETRIYA (LIVE)
            </button>
            <button class="nav-tab-btn" onclick="switchTab('tab-crew-dossier')">
                👥 3. EKIPAJ TIBBIY BAZASI
            </button>
            <button class="nav-tab-btn" onclick="switchTab('tab-ops-atlas')">
                🪐 4. FAZOVIY OPERATSIYALAR ATLASI
            </button>
            <button class="nav-tab-btn" onclick="switchTab('tab-security')">
                🛡️ 5. AVIONIKA VA XAVFSIZLIK
            </button>
        </div>

        <!-- Clocks -->
        <div class="conductor-clock">
            <div class="clock-item">
                <span class="clock-lbl">MISSION ELAPSED TIME</span>
                <span class="clock-val" id="lbl-met">MET 004 / 05:22:18</span>
            </div>
            <div class="clock-item">
                <span class="clock-lbl">EDGE LATENCY</span>
                <span class="clock-val" style="color: var(--accent-green);" id="lbl-lat">0.67 ms</span>
            </div>
            <div class="clock-item">
                <span class="clock-lbl">DSN LINK</span>
                <span class="clock-val" style="color: var(--accent-amber);">BLACKOUT (4m Delay)</span>
            </div>
        </div>
    </header>

    <!-- 2. MAIN WORKSPACE -->
    <div class="app-workspace">
        
        <!-- ============================================================== -->
        <!-- TAB 1: DIGITAL TWIN SIMULATOR (PRIMARY INTUITIVE NASA INTERFACE)-->
        <!-- ============================================================== -->
        <div class="tab-content active" id="tab-digital-twin">
            
            <!-- STEP 1: CHOOSE ASTRONAUT -->
            <div class="panel">
                <div class="panel-header">
                    <div>
                        <div class="panel-title">
                            <span class="step-badge">1-QADAM</span>
                            <span>ASTRONAVTNI TANLANG (BIOLOGIK RAQAMLI EGIZAK)</span>
                        </div>
                        <div class="panel-subtitle">Har bir astronavt individual yurak, o'pka hajmi, radiatsiya va psixologik profilga ega</div>
                    </div>
                    <div style="font-size: 11px; color: var(--accent-cyan); font-family: var(--font-mono);" id="selected-astro-badge">
                        TANLANGAN: JASUR (Lead EVA)
                    </div>
                </div>

                <div class="crew-grid" id="crew-cards-container">
                    <!-- Loaded dynamically via JS -->
                </div>
            </div>

            <!-- STEP 2: CHOOSE OPERATION -->
            <div class="panel">
                <div class="panel-header">
                    <div>
                        <div class="panel-title">
                            <span class="step-badge">2-QADAM</span>
                            <span>FAZOVIY OPERATSIYANI TANLANG (OSSONDAN QORA TUYNUKGACHA)</span>
                        </div>
                        <div class="panel-subtitle">Atrof-muhit bosimi, relyef qiyaligi, gravitatsiya va radiatsion xavflar darajalari</div>
                    </div>
                    <div style="font-size: 11px; color: var(--accent-amber); font-family: var(--font-mono);" id="selected-op-badge">
                        TANLANGAN: 3-DARAJA (Mars Kanyoni)
                    </div>
                </div>

                <div class="ops-grid" id="ops-cards-container">
                    <!-- Loaded dynamically via JS -->
                </div>
            </div>

            <!-- LAUNCH BAR -->
            <div class="launch-bar">
                <div class="selection-summary">
                    <div class="summary-item">
                        <span class="summary-lbl">TANLANGAN ASTRONAVT</span>
                        <span class="summary-val" id="sum-astro-name" style="color: var(--accent-cyan);">Jasur</span>
                    </div>
                    <div style="font-size: 20px; color: var(--border-strong);">➔</div>
                    <div class="summary-item">
                        <span class="summary-lbl">FAZOVIY OPERATSIYA</span>
                        <span class="summary-val" id="sum-op-title" style="color: var(--accent-amber);">Mars Valles Marineris Kanyoniga Tushish</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-lbl">BOSQICH DARAJASI</span>
                        <span class="summary-val" id="sum-op-level" style="color: #fff;">3-DARAJA (Qiyin)</span>
                    </div>
                </div>

                <button class="btn-launch" onclick="executeDigitalTwinSimulation()">
                    <span>▶ SIMULATSIYANI ISHGA TUSHIRISH</span>
                </button>
            </div>

            <!-- STEP 3: SIMULATION MONITOR & GRAPHICAL CANVAS -->
            <div class="panel" id="sim-monitor-panel" style="display: none;">
                <div class="panel-header">
                    <div class="panel-title">
                        <span class="step-badge">3-QADAM</span>
                        <span style="color: var(--accent-cyan);">HISOBLANGAN GRAFIK SIMULYATSIYA VA TIBBIY BASHORAT</span>
                    </div>
                    <div id="sim-verdict-tag" style="font-family: var(--font-mono); font-weight: 800; font-size: 12px;"></div>
                </div>

                <div class="sim-monitor-grid">
                    <!-- Left: Canvas Graphic View of Environment -->
                    <div class="canvas-container">
                        <div class="canvas-header">
                            <span id="canvas-env-title">RELYEF VA TRAEKTORIYA MONITORI</span>
                            <span id="canvas-env-status" style="color: var(--accent-green);">PHYSICS SIMULATION: ACTIVE</span>
                        </div>
                        <canvas id="envCanvas" width="800" height="230"></canvas>
                    </div>

                    <!-- Right: Dynamic Vitals Gauges -->
                    <div style="display: flex; flex-direction: column; gap: 8px;">
                        <div class="vitals-grid">
                            <div class="vital-box">
                                <span class="vital-lbl">PIK PULS (HR)</span>
                                <span class="vital-val" id="sim-val-hr" style="color: var(--accent-green);">--</span>
                                <span class="vital-sub">Maks chegarasi ichida</span>
                            </div>
                            <div class="vital-box">
                                <span class="vital-lbl">MIN SpO2</span>
                                <span class="vital-val" id="sim-val-spo2" style="color: var(--accent-cyan);">--</span>
                                <span class="vital-sub">Kislorod to'yinishi</span>
                            </div>
                            <div class="vital-box">
                                <span class="vital-lbl">MAKS G-KUCH</span>
                                <span class="vital-val" id="sim-val-g" style="color: var(--accent-amber);">--</span>
                                <span class="vital-sub">Gravitatsion zo'riqish</span>
                            </div>
                            <div class="vital-box">
                                <span class="vital-lbl">RADIATSIYA</span>
                                <span class="vital-val" id="sim-val-rad" style="color: var(--accent-red);">--</span>
                                <span class="vital-sub">To'plangan doza (mSv)</span>
                            </div>
                            <div class="vital-box">
                                <span class="vital-lbl">QOLGAN O2</span>
                                <span class="vital-val" id="sim-val-o2" style="color: #fff;">--</span>
                                <span class="vital-sub">Skafandr zaxirasi</span>
                            </div>
                            <div class="vital-box">
                                <span class="vital-lbl">OMON QOLISH</span>
                                <span class="vital-val" id="sim-val-survival" style="color: var(--accent-green);">--</span>
                                <span class="vital-sub">AI ehtimollik bahosi</span>
                            </div>
                        </div>

                        <!-- Verdict Card -->
                        <div id="sim-verdict-box" class="verdict-banner go">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <strong id="sim-verdict-title" style="font-size: 13px;">MISSION GO: XAVFSIZ</strong>
                                <span id="sim-verdict-sub" style="font-family: var(--font-mono); font-size: 11px;"></span>
                            </div>
                            <div id="sim-verdict-text" style="font-size: 11px; line-height: 1.4; color: var(--text-primary);"></div>
                            <div id="sim-verdict-recs" style="font-size: 10px; color: var(--text-secondary); margin-top: 4px;"></div>
                        </div>
                    </div>
                </div>

                <!-- Simulation Steps Table -->
                <div class="sim-table-wrap">
                    <table>
                        <thead>
                            <tr>
                                <th>DAQIQA</th>
                                <th>PULS (HR)</th>
                                <th>SpO2</th>
                                <th>QON BOSIMI</th>
                                <th>TANA HARORATI</th>
                                <th>SKAFANDR BOSIMI</th>
                                <th>O2 %</th>
                                <th>G-KUCH</th>
                                <th>HOLAT</th>
                                <th>HODISALAR VA TELEMETRIYA JURNALI</th>
                            </tr>
                        </thead>
                        <tbody id="sim-steps-tbody">
                            <!-- Populated by JS -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- ============================================================== -->
        <!-- TAB 2: LIVE EDGE SUIT TELEMETRY (PRESERVED FUNCTIONALITY) -->
        <!-- ============================================================== -->
        <div class="tab-content" id="tab-live-telemetry">
            <div id="emergency-banner">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="font-weight: 800; font-size: 13px;">⚠️ FAVQULODDA DEKOMPRESSIYA VA GIPOKSIYA XAVFI!</div>
                        <div style="font-size: 11px;">Skafandr O2 klapani ochildi. Zudlik bilan shlyuzga chekinish buyuriladi!</div>
                    </div>
                    <button class="btn-ack" onclick="acknowledgeAlert()">GLOVE ACK (SPACEBAR)</button>
                </div>
            </div>

            <div class="live-grid">
                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title">REAL-VAQT BIOMETRIK TO'LQINLAR & KALMAN DSP FILTRI</div>
                        <div style="display: flex; gap: 6px;">
                            <button class="btn-scen active" id="btn-scen-nominal" onclick="setScenario('NOMINAL')">NOMINAL</button>
                            <button class="btn-scen" id="btn-scen-drilling" onclick="setScenario('DRILLING')">BURG'ULASH</button>
                            <button class="btn-scen" id="btn-scen-hypoxia" onclick="setScenario('HYPOXIA')">DEKOMPRESSIYA</button>
                            <button class="btn-scen" id="btn-scen-panic" onclick="setScenario('PANIC')">VAHIMA</button>
                            <button class="btn-scen" id="btn-scen-multi_crew" onclick="setScenario('MULTI_CREW')">MULTI-CREW</button>
                        </div>
                    </div>

                    <canvas id="waveformCanvas" width="800" height="200" style="width: 100%; height: 200px; background: #070c14; border-radius: 6px;"></canvas>

                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 14px;">
                        <div class="vital-box">
                            <span class="vital-lbl">KALMAN PULS</span>
                            <span class="vital-val" id="val-hr" style="color: var(--accent-green);">72.4</span>
                            <span class="vital-sub">Xom sensor: <strong id="val-raw-hr">73.1</strong> bpm</span>
                        </div>
                        <div class="vital-box">
                            <span class="vital-lbl">KISLOROD (SpO2)</span>
                            <span class="vital-val" id="val-spo2" style="color: var(--accent-cyan);">98.2%</span>
                            <span class="vital-sub">Me'yorda (&gt;90%)</span>
                        </div>
                        <div class="vital-box">
                            <span class="vital-lbl">SKAFANDR BOSIMI</span>
                            <span class="vital-val" id="val-p" style="color: #fff;">29.6 kPa</span>
                            <span class="vital-sub">4.3 PSI Nominal</span>
                        </div>
                        <div class="vital-box">
                            <span class="vital-lbl">BAEVSKY STRESS (SI)</span>
                            <span class="vital-val" id="val-stress" style="color: var(--accent-amber);">105</span>
                            <span class="vital-sub">Optimal holat</span>
                        </div>
                    </div>
                </div>

                <!-- Right Side: Autonomous Space Triage -->
                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title">AVTONOM TRIYAJ & DSN RESURS TAQSIMOTI</div>
                        <span style="font-size: 10px; color: var(--accent-green);">Deterministic Min-Heap</span>
                    </div>

                    <table>
                        <thead>
                            <tr>
                                <th>O'RIN</th>
                                <th>ASTRONAVT</th>
                                <th>DARAJA</th>
                                <th>PULS</th>
                                <th>SpO2</th>
                            </tr>
                        </thead>
                        <tbody id="triage-body">
                            <!-- Filled dynamically -->
                        </tbody>
                    </table>

                    <div style="margin-top: 16px; border-top: 1px solid var(--border-subtle); padding-top: 12px;">
                        <div class="panel-title" style="font-size: 11px; margin-bottom: 6px;">MIKROGRAVITATSIYA MOSLASHUVI (MET 4.2d)</div>
                        <div style="font-size: 11px; color: var(--text-secondary); line-height: 1.5;">
                            <div>Tsefalik suyuqlik siljishi: <strong style="color: var(--accent-cyan);">+8.5 bpm</strong></div>
                            <div>Fazoviy moslashgan chegara: <strong style="color: var(--accent-green);">76.5 bpm</strong></div>
                            <div style="font-size: 10px; color: var(--text-muted); margin-top: 4px;">Yer me'yori bo'yicha soxta signallar bloklangan.</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- ============================================================== -->
        <!-- TAB 3: CREW DOSSIER (5 ASTRONAUTS FULL DATA) -->
        <!-- ============================================================== -->
        <div class="tab-content" id="tab-crew-dossier">
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">MISSIYA EKIPAJI TIBBIY VA FIZIOLOGIK REESTRI (5 RAQAMLI EGIZAK)</div>
                    <div style="font-size: 11px; color: var(--text-muted);">Tibbiy bazadagi o'zgarishlar simulyatorga 1:1 bog'langan</div>
                </div>

                <div id="crew-dossier-full" style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px;">
                    <!-- Loaded dynamically via JS -->
                </div>
            </div>
        </div>

        <!-- ============================================================== -->
        <!-- TAB 4: OPERATIONS ATLAS (5 GRADED MISSIONS) -->
        <!-- ============================================================== -->
        <div class="tab-content" id="tab-ops-atlas">
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">FAZOVIY OPERATSIYALARNING MUHIT VA FIZIKA ATLASI</div>
                    <div style="font-size: 11px; color: var(--text-muted);">1-darajadan 5-daraja (Qora Tuynuk) gacha fizika parametrlari</div>
                </div>

                <div id="ops-atlas-full" style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px;">
                    <!-- Loaded dynamically via JS -->
                </div>
            </div>
        </div>

        <!-- ============================================================== -->
        <!-- TAB 5: AVIONICS & CYBERSECURITY -->
        <!-- ============================================================== -->
        <div class="tab-content" id="tab-security">
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">AVIONIKA, TMR RADIATSIYA REPARATSIYASI & KIBERXAVFSIZLIK</div>
                    <div style="font-size: 11px; color: var(--accent-green);">0600 Permissions, AES-256-GCM, TMR Triple Modular Redundancy</div>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                    <div class="vital-box">
                        <strong style="color: var(--accent-amber); font-size: 13px;">⚡ KOSMIK RADIATSIYA SEU BIT-FLIP TESTI:</strong>
                        <p style="font-size: 11px; color: var(--text-secondary); margin: 6px 0;">
                            Galaktik kosmik nurlar (GCR) kompyuter xotirasidagi bitlarni (0 ni 1 ga yoki 1 ni 0 ga) ag'darib yuboradi. 
                            Ushbu test orqali TMR (Triple Modular Redundancy) 3 nusxa ichidan zararlanganini avto-tuzatadi.
                        </p>
                        <button class="btn-scen" style="border-color: var(--accent-amber); width: fit-content;" onclick="injectBitFlip()">
                            ⚡ Radiatsiya Bit-Flip Inyeksiya Qilish
                        </button>
                        <div id="sec-seu-log" style="font-size: 11px; font-family: var(--font-mono); margin-top: 8px; color: var(--accent-cyan);">
                            Holat: TMR tekshiruvga tayyor.
                        </div>
                    </div>

                    <div class="vital-box">
                        <strong style="color: var(--accent-red); font-size: 13px;">🛡️ KIBERHUJUMLARNI QAYTARISH AUDITI:</strong>
                        <p style="font-size: 11px; color: var(--text-secondary); margin: 6px 0;">
                            Sun'iy yo'ldosh yoki kema telemetriyasini soxtalashtirish (Tampering) yoki paketlarni qayta jo'natish (Replay Attack) ni testdan o'tkazish.
                        </p>
                        <div style="display: flex; gap: 8px;">
                            <button class="btn-scen" style="border-color: var(--accent-red);" onclick="testCryptoAttack('TAMPER')">
                                🛡️ Shifrni Buzish (Tamper)
                            </button>
                            <button class="btn-scen" style="border-color: var(--accent-red);" onclick="testCryptoAttack('REPLAY')">
                                🔁 Replay Hujum Testi
                            </button>
                        </div>
                        <div id="sec-crypto-log" style="font-size: 11px; font-family: var(--font-mono); margin-top: 8px; color: var(--accent-green);">
                            Holat: AES-256-GCM faol.
                        </div>
                    </div>
                </div>
            </div>
        </div>

    </div>

    <!-- SCRIPT LOGIC -->
    <script>
        let crewData = {};
        let opsData = {};
        let selectedAstroId = "ASTRO-JASUR";
        let selectedOpId = "OP-03-MARS-CANYON-HARD";

        // Tab Switching
        function switchTab(tabId) {
            document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
            document.querySelectorAll(".nav-tab-btn").forEach(el => el.classList.remove("active"));

            const target = document.getElementById(tabId);
            if (target) target.classList.add("active");

            event.currentTarget.classList.add("active");
        }

        // Load Crew and Ops on startup
        async function loadInitialData() {
            try {
                const [crewRes, opsRes] = await Promise.all([
                    fetch("/api/digital_twin/crew"),
                    fetch("/api/digital_twin/operations")
                ]);
                crewData = await crewRes.json();
                opsData = await opsRes.json();

                renderCrewCards();
                renderOpsCards();
                renderCrewDossierFull();
                renderOpsAtlasFull();
                updateSelectionSummary();
            } catch (err) {
                console.error("Initial load error:", err);
            }
        }

        function renderCrewCards() {
            const container = document.getElementById("crew-cards-container");
            container.innerHTML = "";

            const avatars = {
                "ASTRO-ROZIMUROD": "👨‍✈️",
                "ASTRO-MUHAMMADZIYO": "👨‍⚕️",
                "ASTRO-ELDOR": "👷‍♂️",
                "ASTRO-JASUR": "👨‍🚀",
                "ASTRO-SHOHRUXMIRZO": "🦅"
            };

            for (const [id, a] of Object.entries(crewData)) {
                const card = document.createElement("div");
                card.className = "crew-card" + (id === selectedAstroId ? " selected" : "");
                card.onclick = () => selectAstro(id);

                card.innerHTML = `
                    <div class="crew-card-top">
                        <div class="crew-avatar">${avatars[id] || "👨‍🚀"}</div>
                        <div style="overflow: hidden;">
                            <div class="crew-name">${a.name}</div>
                            <div class="crew-role">${a.role}</div>
                        </div>
                    </div>
                    <div class="crew-specs">
                        <div class="crew-spec-row">
                            <span>Yosh / Bo'y:</span>
                            <strong style="color: #fff;">${a.age} yosh | ${a.height_cm} sm</strong>
                        </div>
                        <div class="crew-spec-row">
                            <span>Yurak (VO2max):</span>
                            <strong style="color: var(--accent-green);">${a.vo2_max} ml/kg</strong>
                        </div>
                        <div class="crew-spec-row">
                            <span>G-Bardoshlik:</span>
                            <strong style="color: var(--accent-amber);">${a.g_tolerance} g</strong>
                        </div>
                        <div class="crew-spec-row">
                            <span>Puls oralig'i:</span>
                            <span>${Math.round(a.resting_hr)} - ${Math.round(a.max_hr)} bpm</span>
                        </div>
                    </div>
                `;
                container.appendChild(card);
            }
        }

        function renderOpsCards() {
            const container = document.getElementById("ops-cards-container");
            container.innerHTML = "";

            for (const [id, op] of Object.entries(opsData)) {
                const card = document.createElement("div");
                card.className = "op-card level-" + op.level + (id === selectedOpId ? " selected" : "");
                card.onclick = () => selectOp(id);

                card.innerHTML = `
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="op-level-badge lvl-${op.level}">${op.level}-DARAJA</span>
                        <span style="font-size: 10px; color: var(--text-muted); font-family: var(--font-mono);">${op.duration_minutes} daq</span>
                    </div>
                    <div class="op-title">${op.title}</div>
                    <div class="op-target">📍 ${op.target_body}</div>
                    <div class="op-specs">
                        <div class="crew-spec-row">
                            <span>Gravitatsiya:</span>
                            <strong style="color: #fff;">${op.gravity_g} g</strong>
                        </div>
                        <div class="crew-spec-row">
                            <span>Harorat:</span>
                            <strong style="color: ${op.ambient_temp_c < 0 ? 'var(--accent-cyan)' : 'var(--accent-red)'};">${op.ambient_temp_c > 1000 ? '> 1,000,000°C' : op.ambient_temp_c + '°C'}</strong>
                        </div>
                        <div class="crew-spec-row">
                            <span>Radiatsiya:</span>
                            <strong style="color: ${op.level === 5 ? 'var(--accent-red)' : 'var(--text-secondary)'};">${op.radiation_mSv_per_hour > 1000 ? '> 95,000 Sv/h' : op.radiation_mSv_per_hour + ' mSv/h'}</strong>
                        </div>
                    </div>
                `;
                container.appendChild(card);
            }
        }

        function selectAstro(id) {
            selectedAstroId = id;
            renderCrewCards();
            updateSelectionSummary();
        }

        function selectOp(id) {
            selectedOpId = id;
            renderOpsCards();
            updateSelectionSummary();
        }

        function updateSelectionSummary() {
            const astro = crewData[selectedAstroId];
            const op = opsData[selectedOpId];
            if (!astro || !op) return;

            document.getElementById("sum-astro-name").innerText = `${astro.name} (${astro.role})`;
            document.getElementById("selected-astro-badge").innerText = `TANLANGAN: ${astro.name.toUpperCase()} (${astro.callsign})`;

            document.getElementById("sum-op-title").innerText = op.title;
            document.getElementById("sum-op-level").innerText = `${op.level}-DARAJA (${op.target_body})`;
            document.getElementById("selected-op-badge").innerText = `TANLANGAN: ${op.level}-DARAJA (${op.title})`;
        }

        // Run simulation
        async function executeDigitalTwinSimulation() {
            const panel = document.getElementById("sim-monitor-panel");
            panel.style.display = "block";
            panel.scrollIntoView({ behavior: 'smooth' });

            document.getElementById("canvas-env-status").innerText = "HISOBLANMOQDA...";

            const res = await fetch("/api/digital_twin/simulate", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({astronaut_id: selectedAstroId, operation_id: selectedOpId})
            });
            const d = await res.json();

            // Populate Vitals
            document.getElementById("sim-val-hr").innerText = `${d.peak_hr} bpm`;
            document.getElementById("sim-val-spo2").innerText = `${d.min_spo2}%`;
            document.getElementById("sim-val-g").innerText = `${d.peak_g_force} g`;
            document.getElementById("sim-val-rad").innerText = `${d.total_radiation_msv > 1000 ? (d.total_radiation_msv/1000).toFixed(1) + 'k' : d.total_radiation_msv} mSv`;
            document.getElementById("sim-val-o2").innerText = `${d.o2_margin_pct}%`;
            document.getElementById("sim-val-survival").innerText = `${d.survival_probability_pct}%`;

            // Verdict Styling
            const vBox = document.getElementById("sim-verdict-box");
            const vTitle = document.getElementById("sim-verdict-title");
            const vSub = document.getElementById("sim-verdict-sub");
            const vTag = document.getElementById("sim-verdict-tag");

            vBox.className = "verdict-banner";
            if (d.verdict === "FATAL_FAILURE") {
                vBox.classList.add("fatal");
                vTitle.innerText = "☠️ FOJIAVIY HALOKAT (0% OMON QOLISH) - MUTLAQ NO-GO";
                vTitle.style.color = "var(--accent-red)";
                vSub.innerText = `HALOKAT VAQTI: ${d.time_of_failure_min} daqiqada | Sabab: ${d.cause_of_death}`;
                vTag.style.color = "var(--accent-red)";
                vTag.innerText = "VERDICT: CATASTROPHIC FAILURE";
            } else if (d.verdict === "CAUTION_GO") {
                vBox.classList.add("caution");
                vTitle.innerText = "⚠️ OGOHLANTIRISH BILAN RUXSAT (CAUTION GO)";
                vTitle.style.color = "var(--accent-amber)";
                vSub.innerText = `Omon qolish ehtimoli: ${d.survival_probability_pct}% | Zo'riqish yuqori`;
                vTag.style.color = "var(--accent-amber)";
                vTag.innerText = "VERDICT: CONDITIONAL GO";
            } else {
                vBox.classList.add("go");
                vTitle.innerText = "✅ TO'LIQ XAVFSIZ (MISSION GO)";
                vTitle.style.color = "var(--accent-green)";
                vSub.innerText = `Omon qolish ehtimoli: ${d.survival_probability_pct}% | Barcha parametrlar nominal`;
                vTag.style.color = "var(--accent-green)";
                vTag.innerText = "VERDICT: FULL PASS";
            }

            document.getElementById("sim-verdict-text").innerText = d.medical_summary;

            let recsHtml = "<strong>Xavfsizlik Tavsiyalari:</strong><ul style='margin-left: 18px; margin-top: 4px;'>";
            d.safety_recommendations.forEach(r => recsHtml += `<li>${r}</li>`);
            recsHtml += "</ul>";
            document.getElementById("sim-verdict-recs").innerHTML = recsHtml;

            // Steps Table
            const tbody = document.getElementById("sim-steps-tbody");
            tbody.innerHTML = "";
            d.steps.forEach(s => {
                const tr = document.createElement("tr");
                const stColor = s.status === "NOMINAL" ? "var(--accent-green)" : (s.status === "CRITICAL_FAILURE" ? "var(--accent-red)" : "var(--accent-amber)");
                tr.innerHTML = `
                    <td>${s.minute.toFixed(1)}</td>
                    <td style="color: ${s.hr > 170 ? 'var(--accent-red)' : 'var(--accent-green)'}">${s.hr.toFixed(1)}</td>
                    <td style="color: ${s.spo2 < 90 ? 'var(--accent-red)' : 'var(--accent-cyan)'}">${s.spo2.toFixed(1)}%</td>
                    <td>${Math.round(s.bp_sys)}/${Math.round(s.bp_dia)}</td>
                    <td>${s.core_temp.toFixed(1)}°C</td>
                    <td>${s.suit_pressure_kpa.toFixed(1)} kPa</td>
                    <td>${s.o2_remaining_pct.toFixed(1)}%</td>
                    <td>${s.g_force_effective.toFixed(2)} g</td>
                    <td style="color: ${stColor}; font-weight: bold;">${s.status}</td>
                    <td>${s.event_log}</td>
                `;
                tbody.appendChild(tr);
            });

            // Draw Visual Graphic Canvas
            drawEnvironmentCanvas(d.operation_id, d.verdict, d.steps);
            document.getElementById("canvas-env-status").innerText = "SIMULATION COMPLETE";
        }

        // Real graphic canvas renderer for each space environment
        function drawEnvironmentCanvas(opId, verdict, steps) {
            const canvas = document.getElementById("envCanvas");
            const ctx = canvas.getContext("2d");
            const w = canvas.width;
            const h = canvas.height;

            ctx.clearRect(0, 0, w, h);

            if (opId.includes("BLACK-HOLE")) {
                // CYGNUS X-1 BLACK HOLE WITH ACCRETION DISK & SPAGHETTIFICATION
                document.getElementById("canvas-env-title").innerText = "CYGNUS X-1: ERGOSFERA & VOQEALAR GORIZONTI";

                // Deep space gradient
                const grad = ctx.createRadialGradient(w/2, h/2, 10, w/2, h/2, w/2);
                grad.addColorStop(0, "#000000");
                grad.addColorStop(0.2, "#080512");
                grad.addColorStop(0.5, "#25092b");
                grad.addColorStop(1, "#020308");
                ctx.fillStyle = grad;
                ctx.fillRect(0, 0, w, h);

                // Relativistic Accretion Disk
                ctx.save();
                ctx.translate(w/2, h/2);
                ctx.rotate(-0.25);
                ctx.scale(1.0, 0.32);

                const diskGrad = ctx.createRadialGradient(0, 0, 45, 0, 0, 240);
                diskGrad.addColorStop(0, "rgba(255, 42, 85, 0)");
                diskGrad.addColorStop(0.18, "#ff2a55");
                diskGrad.addColorStop(0.4, "#00e5ff");
                diskGrad.addColorStop(0.7, "#a855f7");
                diskGrad.addColorStop(1, "rgba(0,0,0,0)");

                ctx.beginPath();
                ctx.arc(0, 0, 240, 0, Math.PI * 2);
                ctx.fillStyle = diskGrad;
                ctx.fill();

                // Inner Schwarzschild Event Horizon (pitch black hole)
                ctx.beginPath();
                ctx.arc(0, 0, 48, 0, Math.PI * 2);
                ctx.fillStyle = "#000000";
                ctx.fill();
                ctx.lineWidth = 4;
                ctx.strokeStyle = "#00e5ff";
                ctx.stroke();
                ctx.restore();

                // Spaghettification Gravitational Gradient Boundary
                ctx.strokeStyle = "rgba(255, 42, 85, 0.8)";
                ctx.setLineDash([8, 6]);
                ctx.beginPath();
                ctx.arc(w/2, h/2, 90, 0, Math.PI * 2);
                ctx.stroke();
                ctx.setLineDash([]);

                // Warning callouts
                ctx.fillStyle = "#ff2a55";
                ctx.font = "bold 11px JetBrains Mono";
                ctx.fillText("⚠️ SPAGHETTIFICATION ZONE (2850g)", w/2 - 110, 35);
                ctx.fillStyle = "#00e5ff";
                ctx.fillText("SCHWARZSCHILD EVENT HORIZON", w/2 - 95, h - 20);

                // Fatal probe trajectory
                ctx.strokeStyle = "#fff";
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(80, 40);
                ctx.quadraticCurveTo(w/2 - 40, h/2 - 60, w/2 - 20, h/2 - 10);
                ctx.stroke();

                // Skull marker
                ctx.fillStyle = "#ff2a55";
                ctx.font = "20px Arial";
                ctx.fillText("☠️", w/2 - 30, h/2 - 8);
                ctx.font = "bold 10px JetBrains Mono";
                ctx.fillText("HALOKAT (00:02 min)", w/2 + 2, h/2 - 8);

            } else if (opId.includes("MARS-CANYON")) {
                // MARS VALLES MARINERIS 4.2 KM CANYON DESCENT
                document.getElementById("canvas-env-title").innerText = "MARS VALLES MARINERIS: 4.2 KM TIK KANYON PROFILI";

                // Sky
                const sky = ctx.createLinearGradient(0, 0, 0, h);
                sky.addColorStop(0, "#2c140d");
                sky.addColorStop(0.4, "#59281a");
                sky.addColorStop(1, "#120a07");
                ctx.fillStyle = sky;
                ctx.fillRect(0, 0, w, h);

                // Distant Canyon Cliffs
                ctx.fillStyle = "#3d1b12";
                ctx.beginPath();
                ctx.moveTo(0, 110);
                ctx.lineTo(250, 80);
                ctx.lineTo(500, 120);
                ctx.lineTo(800, 95);
                ctx.lineTo(800, h);
                ctx.lineTo(0, h);
                ctx.fill();

                // Near 42-degree Steep Canyon Cliff Face
                ctx.fillStyle = "#1e0b06";
                ctx.beginPath();
                ctx.moveTo(0, 30);
                ctx.lineTo(160, 40);
                ctx.lineTo(480, 200);
                ctx.lineTo(800, 210);
                ctx.lineTo(800, h);
                ctx.lineTo(0, h);
                ctx.fill();

                // Canyon Deep Shadow Region
                ctx.fillStyle = "rgba(0, 0, 0, 0.65)";
                ctx.fillRect(250, 120, 550, h - 120);

                // Laser Tether Descent Path
                ctx.strokeStyle = "rgba(0, 229, 255, 0.8)";
                ctx.lineWidth = 2;
                ctx.setLineDash([6, 4]);
                ctx.beginPath();
                ctx.moveTo(150, 40);
                ctx.lineTo(460, 195);
                ctx.stroke();
                ctx.setLineDash([]);

                // Markers & Hazards
                ctx.fillStyle = "#00e5ff";
                ctx.beginPath();
                ctx.arc(320, 125, 6, 0, Math.PI * 2);
                ctx.fill();

                ctx.font = "bold 10px JetBrains Mono";
                ctx.fillStyle = "#ffb700";
                ctx.fillText("⚠️ 42° TIK REGOLIT QIYALIK", 170, 75);
                ctx.fillStyle = "#00e5ff";
                ctx.fillText("📍 JASUR: 2.1 km CHUQURLIKDA (Puls 135 bpm)", 335, 125);
                ctx.fillStyle = "#a855f7";
                ctx.fillText("🧊 KANYON TUBI MUZ QATLAMI (-95°C)", 480, 215);

            } else if (opId.includes("LUNAR")) {
                // MOON SHACKLETON CRATER EVA
                document.getElementById("canvas-env-title").innerText = "OY: SHACKLETON KRATERI VA QUYOSH PANELLARI";

                // Starfield black
                ctx.fillStyle = "#020307";
                ctx.fillRect(0, 0, w, h);

                // Stars
                ctx.fillStyle = "#ffffff";
                for (let i = 0; i < 70; i++) {
                    const sx = (i * 37) % w;
                    const sy = (i * 23) % 120;
                    ctx.fillRect(sx, sy, 1.5, 1.5);
                }

                // Earth in sky
                ctx.beginPath();
                ctx.arc(700, 50, 28, 0, Math.PI * 2);
                const earthGrad = ctx.createLinearGradient(680, 30, 720, 70);
                earthGrad.addColorStop(0, "#00e5ff");
                earthGrad.addColorStop(0.7, "#0b3d91");
                earthGrad.addColorStop(1, "#031433");
                ctx.fillStyle = earthGrad;
                ctx.fill();

                // Moon Surface
                ctx.fillStyle = "#333a45";
                ctx.beginPath();
                ctx.moveTo(0, 130);
                ctx.quadraticCurveTo(200, 110, 450, 140);
                ctx.quadraticCurveTo(650, 155, 800, 135);
                ctx.lineTo(800, h);
                ctx.lineTo(0, h);
                ctx.fill();

                // Solar Panels Tower
                ctx.fillStyle = "#1e5cb8";
                ctx.fillRect(150, 80, 80, 55);
                ctx.strokeStyle = "#00e5ff";
                ctx.strokeRect(150, 80, 80, 55);

                ctx.fillStyle = "#00ff88";
                ctx.font = "bold 10px JetBrains Mono";
                ctx.fillText("✅ NOMINAL OY EVA (Puls: 105 bpm, SpO2: 99%)", 260, 160);

            } else if (opId.includes("TITAN")) {
                // TITAN CRYO-METHANE STORM
                document.getElementById("canvas-env-title").innerText = "TITAN: KRAKEN MARE METAN BO'RONI (-179°C)";

                // Hazy Orange Atmosphere
                const hazy = ctx.createLinearGradient(0, 0, 0, h);
                hazy.addColorStop(0, "#331804");
                hazy.addColorStop(0.5, "#6b330a");
                hazy.addColorStop(1, "#140a02");
                ctx.fillStyle = hazy;
                ctx.fillRect(0, 0, w, h);

                // Methane rain streaks
                ctx.strokeStyle = "rgba(0, 229, 255, 0.4)";
                ctx.lineWidth = 1.5;
                for (let i = 0; i < 50; i++) {
                    const rx = (i * 29) % w;
                    const ry = (i * 17) % h;
                    ctx.beginPath();
                    ctx.moveTo(rx, ry);
                    ctx.lineTo(rx - 25, ry + 35);
                    ctx.stroke();
                }

                // Frozen shoreline
                ctx.fillStyle = "#121b24";
                ctx.beginPath();
                ctx.moveTo(0, 170);
                ctx.lineTo(400, 150);
                ctx.lineTo(800, 180);
                ctx.lineTo(800, h);
                ctx.lineTo(0, h);
                ctx.fill();

                ctx.fillStyle = "#ffb700";
                ctx.font = "bold 11px JetBrains Mono";
                ctx.fillText("⚠️ 35 m/s METAN BO'RONI VA GIPOTERMIYA CHEGARASI (-179°C)", 140, 50);

            } else {
                // LOW MARS ORBIT EXTERIOR
                document.getElementById("canvas-env-title").innerText = "MARS ORBITASI: ARES-TRANSIT STANSIYASI (420 KM)";

                ctx.fillStyle = "#04070d";
                ctx.fillRect(0, 0, w, h);

                // Curved red Mars horizon below
                ctx.beginPath();
                ctx.arc(w/2, h + 380, 500, 0, Math.PI * 2);
                ctx.fillStyle = "#8a3116";
                ctx.fill();
                ctx.strokeStyle = "rgba(255, 100, 50, 0.5)";
                ctx.lineWidth = 6;
                ctx.stroke();

                // Station Truss & Solar Arrays
                ctx.fillStyle = "#607d8b";
                ctx.fillRect(200, 60, 400, 14);
                ctx.fillStyle = "#1e5cb8";
                ctx.fillRect(240, 20, 60, 90);
                ctx.fillRect(500, 20, 60, 90);

                ctx.fillStyle = "#00ff88";
                ctx.font = "bold 10px JetBrains Mono";
                ctx.fillText("✅ 0g MIKROGRAVITATSIYA REJIMI (NOMINAL O'TDI)", w/2 - 130, 150);
            }
        }

        // Full Crew Dossier Renderer
        function renderCrewDossierFull() {
            const container = document.getElementById("crew-dossier-full");
            container.innerHTML = "";
            for (const [id, a] of Object.entries(crewData)) {
                const box = document.createElement("div");
                box.className = "vital-box";
                box.style.background = "#121b2b";
                box.innerHTML = `
                    <div style="font-weight: 800; font-size: 14px; color: #fff;">${a.name}</div>
                    <div style="color: var(--accent-cyan); font-size: 11px; margin-bottom: 6px;">${a.callsign} | ${a.role}</div>
                    <div style="font-size: 11px; color: var(--text-secondary); line-height: 1.6; font-family: var(--font-mono);">
                        <div>Yosh / Vazn: <strong>${a.age} yosh | ${a.mass_kg} kg</strong></div>
                        <div>VO2 Max: <strong style="color: var(--accent-green);">${a.vo2_max} ml/kg/min</strong></div>
                        <div>Puls chegarasi: <strong>${a.resting_hr} - ${a.max_hr} bpm</strong></div>
                        <div>G-Bardoshlik: <strong style="color: var(--accent-amber);">${a.g_tolerance} g</strong></div>
                        <div>Radiatsiya chegarasi: <strong>${a.radiation_tolerance_sv} Sv</strong></div>
                        <div>Psixologik chidamlilik: <strong>${(a.psychological_resilience*100).toFixed(0)}%</strong></div>
                    </div>
                    <div style="margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 6px; font-size: 10px; color: var(--text-muted);">
                        <strong>Ixtisosliklari:</strong>
                        <ul style="margin-left: 14px; margin-top: 3px;">
                            ${a.specialty_skills.map(s => `<li>${s}</li>`).join('')}
                        </ul>
                    </div>
                `;
                container.appendChild(box);
            }
        }

        // Full Ops Atlas Renderer
        function renderOpsAtlasFull() {
            const container = document.getElementById("ops-atlas-full");
            container.innerHTML = "";
            for (const [id, op] of Object.entries(opsData)) {
                const box = document.createElement("div");
                box.className = "vital-box";
                box.style.background = "#121b2b";
                box.innerHTML = `
                    <span class="op-level-badge lvl-${op.level}">${op.level}-DARAJA</span>
                    <div style="font-weight: 800; font-size: 13px; color: #fff; margin: 4px 0;">${op.title}</div>
                    <div style="color: var(--accent-cyan); font-size: 10px; margin-bottom: 6px;">📍 ${op.target_body}</div>
                    <p style="font-size: 10px; color: var(--text-secondary); line-height: 1.4; margin-bottom: 8px;">${op.description}</p>
                    <div style="font-size: 10px; color: var(--text-secondary); line-height: 1.6; font-family: var(--font-mono); border-top: 1px solid rgba(255,255,255,0.06); padding-top: 6px;">
                        <div>Gravitatsiya: <strong>${op.gravity_g} g</strong></div>
                        <div>Harorat: <strong>${op.ambient_temp_c}°C</strong></div>
                        <div>Atmosfera: <strong>${op.ambient_pressure_kpa} kPa</strong></div>
                        <div>Radiatsiya: <strong>${op.radiation_mSv_per_hour} mSv/h</strong></div>
                        <div>Davomiyligi: <strong>${op.duration_minutes} daqiqa</strong></div>
                    </div>
                `;
                container.appendChild(box);
            }
        }

        // Real-Time Telemetry Polling Loop
        async function updateLiveTelemetry() {
            try {
                const res = await fetch("/api/telemetry");
                const d = await res.json();
                if (d.status === "WAITING" || !d.latest) return;

                const l = d.latest;
                document.getElementById("val-hr").innerText = l.filtered_hr.toFixed(1);
                document.getElementById("val-raw-hr").innerText = l.raw_hr.toFixed(1);
                document.getElementById("val-spo2").innerText = l.filtered_spo2.toFixed(1) + "%";
                document.getElementById("val-p").innerText = l.suit_pressure_kpa.toFixed(1) + " kPa";
                document.getElementById("val-stress").innerText = Math.round(l.stress_index);

                // Override alert
                const banner = document.getElementById("emergency-banner");
                if (l.suit_pressure_kpa < 24.0 || l.filtered_spo2 < 86.0) {
                    banner.style.display = "block";
                } else {
                    banner.style.display = "none";
                }

                // Triage Table
                const tbody = document.getElementById("triage-body");
                if (d.multi_crew && d.multi_crew.length > 0) {
                    tbody.innerHTML = "";
                    d.multi_crew.forEach((c, idx) => {
                        const tr = document.createElement("tr");
                        tr.innerHTML = `
                            <td>#${idx + 1}</td>
                            <td style="font-weight: bold; color: #fff;">${c.astronaut_id}</td>
                            <td style="color: ${c.tier === 'P1_RED' ? 'var(--accent-red)' : 'var(--accent-green)'}">${c.tier}</td>
                            <td>${c.filtered_hr.toFixed(1)}</td>
                            <td>${c.filtered_spo2.toFixed(1)}%</td>
                        `;
                        tbody.appendChild(tr);
                    });
                }

                // Draw Waveform
                drawLiveWaveform(d.history);
            } catch (err) {}
        }

        function drawLiveWaveform(history) {
            const canvas = document.getElementById("waveformCanvas");
            if (!canvas) return;
            const ctx = canvas.getContext("2d");
            const w = canvas.width;
            const h = canvas.height;

            ctx.clearRect(0, 0, w, h);

            // Grid lines
            ctx.strokeStyle = "#101d30";
            ctx.lineWidth = 1;
            for (let y = 20; y < h; y += 30) {
                ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
            }

            if (!history || history.length < 2) return;

            // Draw Raw noisy HR
            ctx.strokeStyle = "rgba(255, 42, 85, 0.4)";
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            const stepX = w / (history.length - 1);
            history.forEach((pt, i) => {
                const y = h - ((pt.raw_hr - 50) / 100) * h;
                if (i === 0) ctx.moveTo(0, y); else ctx.lineTo(i * stepX, y);
            });
            ctx.stroke();

            // Draw Filtered Kalman HR
            ctx.strokeStyle = "#00ff88";
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            history.forEach((pt, i) => {
                const y = h - ((pt.filtered_hr - 50) / 100) * h;
                if (i === 0) ctx.moveTo(0, y); else ctx.lineTo(i * stepX, y);
            });
            ctx.stroke();
        }

        async function setScenario(mode) {
            document.querySelectorAll(".btn-scen").forEach(b => b.classList.remove("active"));
            const btn = document.getElementById("btn-scen-" + mode.toLowerCase());
            if (btn) btn.classList.add("active");
            await fetch("/api/scenario", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({mode: mode})
            });
        }

        async function acknowledgeAlert() {
            await fetch("/api/hud/acknowledge", {method: "POST"});
            document.getElementById("emergency-banner").style.display = "none";
        }

        async function injectBitFlip() {
            const res = await fetch("/api/test/bitflip", {method: "POST"});
            const d = await res.json();
            document.getElementById("sec-seu-log").innerText = `[SEU TO'G'RILANDI]: ${d.event.crc_status} -> TMR o'zini tuzatdi (Jami tiklashlar: ${d.event.total_tmr_repairs})`;
        }

        async function testCryptoAttack(type) {
            const res = await fetch("/api/test/crypto_attack", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({type: type})
            });
            const d = await res.json();
            document.getElementById("sec-crypto-log").innerText = `[HUJUM QAYTARILDI]: ${d.result.attack} -> ${d.result.status_message} [${d.result.verdict}]`;
        }

        window.addEventListener("keydown", (e) => {
            if (e.code === "Space") {
                const banner = document.getElementById("emergency-banner");
                if (banner && banner.style.display !== "none") {
                    e.preventDefault();
                    acknowledgeAlert();
                }
            }
        });

        // Initialize
        loadInitialData();
        setInterval(updateLiveTelemetry, 500);
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
    print(f"  ASTROLOGIC X - NASA MISSION CONTROL INTERFACE STARTED")
    print(f"  Local URL: http://{HOST}:{PORT}")
    print(f"==================================================================\n")
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
