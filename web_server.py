#!/usr/bin/env python3
"""
AstroVitals - Autonomous Deep-Space Astronaut Health & Bio-Digital Twin Platform.
Integrates Real-Time Suit Edge Telemetry and Bio-Digital Twin Pre-Mission Predictive Simulator.
"""

import os
import sys
import time
import json
import asyncio
import threading
import queue
from typing import Dict, Any, List, Generator
from flask import Flask, jsonify, request, render_template_string, Response, stream_with_context

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
                del scenario_state["recent_frames"][0]

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

            # SSE broadcast – push latest telemetry and triage to all listeners
            _publish_sse({
                "latest": result,
                "scenario": scenario_state["mode"],
                "multi_crew": scenario_state["multi_crew_data"],
                "ts": time.time()
            })

            t_step += 0.5
            time.sleep(0.5)
        except Exception as exc:
            time.sleep(1.0)

# SSE subscribers queue list (thread-safe)
_sse_subscribers: List[queue.Queue] = []
_sse_lock = threading.Lock()

def _publish_sse(data: dict) -> None:
    """Broadcast SSE event to all connected clients (drop if queue full)."""
    msg = "data: " + json.dumps(data) + "\n\n"
    with _sse_lock:
        dead = []
        for q in _sse_subscribers:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_subscribers.remove(q)


bg_thread = threading.Thread(target=simulation_background_loop, daemon=True)
bg_thread.start()

# ----------------- REST API ROUTES -----------------

@app.route("/api/stream", methods=["GET"])
def sse_stream():
    """Server-Sent Events endpoint – real-time telemetry push (no polling needed)."""
    client_q: queue.Queue = queue.Queue(maxsize=30)
    with _sse_lock:
        _sse_subscribers.append(client_q)

    def generate() -> Generator[str, None, None]:
        # Send initial snapshot immediately
        if scenario_state["recent_frames"]:
            yield "data: " + json.dumps({
                "latest": scenario_state["recent_frames"][-1],
                "scenario": scenario_state["mode"],
                "multi_crew": scenario_state["multi_crew_data"],
                "ts": time.time()
            }) + "\n\n"
        try:
            while True:
                try:
                    msg = client_q.get(timeout=20)
                    yield msg
                except queue.Empty:
                    # Keep-alive comment
                    yield ": keep-alive\n\n"
        except GeneratorExit:
            with _sse_lock:
                try:
                    _sse_subscribers.remove(client_q)
                except ValueError:
                    pass

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


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
# ----------------- NASA OPEN MCT-STYLE HTML TEMPLATE -----------------
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "templates", "index.html")

def get_html_template():
    if os.path.exists(TEMPLATE_PATH):
        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>NASA Bio-Mission Control Template Not Found</h1>"

@app.route("/", methods=["GET"])
def index():
    return render_template_string(get_html_template())

if __name__ == "__main__":
    PORT = 8080
    HOST = "0.0.0.0"
    print(f"\n==================================================================")
    print(f"  ASTROVITALS - MISSION CONTROL & BIO-DIGITAL TWIN PLATFORM")
    print(f"  Local URL: http://{HOST}:{PORT}")
    print(f"==================================================================\n")
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
