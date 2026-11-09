#!/usr/bin/env bash
# ==============================================================================
# Edge-First Autonomous Astronaut Health Monitoring System Launcher
#
# Enforces strict security standards:
# - Restrictive process umask (077)
# - Secure directory and key permissions checks (0700/0600)
# - Input validation & error trapping
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# 1. Enforce strict umask
umask 077

echo "[+] Initializing Edge-First Astronaut Health Monitor..."

# 2. Permission Security Verification
SECRETS_DIR="${SCRIPT_DIR}/.secrets"
DATA_DIR="${SCRIPT_DIR}/data"

mkdir -p "${SECRETS_DIR}" "${DATA_DIR}"
chmod 700 "${SECRETS_DIR}" "${DATA_DIR}"

if [[ -f "${SECRETS_DIR}/suit_master.key" ]]; then
    chmod 600 "${SECRETS_DIR}/suit_master.key"
fi

# 3. Compile C++ Core if required
if [[ ! -f "${SCRIPT_DIR}/health_monitor/libdsp_core.so" || ! -f "${SCRIPT_DIR}/build/dsp_benchmark" ]]; then
    echo "[+] Compiling C++ DSP Core & SEU TMR Shared Library..."
    mkdir -p "${SCRIPT_DIR}/build"
    cd "${SCRIPT_DIR}/build"
    cmake .. -DCMAKE_BUILD_TYPE=Release
    make -j$(nproc)
    cd "${SCRIPT_DIR}"
fi

# 4. Verify C++ Benchmark
echo "[+] Running C++ DSP & SEU Hardening Benchmark..."
"${SCRIPT_DIR}/build/dsp_benchmark"

# 5. Run Automated Unit & Integration Test Suite (All 17 Tests)
echo "[+] Running Full Spaceflight & Bio-Digital Twin Test Suite (17 Tests)..."
python3 -m unittest discover tests

# 6. Run Spaceflight Mission Demonstration & Digital Twin Matrix
echo "[+] Launching Live Spaceflight Telemetry & Emergency Simulation..."
python3 demo_edge_daemon.py

echo "[+] Running Bio-Digital Twin 5x5 Mission Simulation Matrix..."
python3 demo_digital_twin.py --matrix

echo ""
echo "=================================================================="
echo "  NASA MISSION CONTROL CONSOLE IS READY TO RUN"
echo "  To start the Web UI Console, execute:"
echo "    python3 web_server.py"
echo "  Open browser at: http://127.0.0.1:8080"
echo "=================================================================="
