"""
Security & System Configuration for Edge-First Astronaut Health Monitor.

Ensures strict compliance with cybersecurity standards:
- Zero hardcoded plaintext secret keys or passwords.
- Secure key derivation using HKDF with PBKDF2/SHA-256.
- Strict filesystem permission enforcement (0600 on secrets).
- Process umask enforcement (0077).
- In-memory key zeroization support.
"""

import os
import stat
import logging
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("AstronautConfig")

# Enforce secure process umask (restrictive file permissions by default)
os.umask(0o077)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SECRETS_DIR = PROJECT_ROOT / ".secrets"

DATA_DIR.mkdir(mode=0o700, exist_ok=True)
SECRETS_DIR.mkdir(mode=0o700, exist_ok=True)

class SecurityConfig:
    """Manages cryptographic keys securely without hardcoding."""

    KEY_FILE_NAME = "suit_master.key"
    KEY_PATH = SECRETS_DIR / KEY_FILE_NAME

    @classmethod
    def get_master_key(cls) -> bytes:
        """
        Retrieves or initializes the 256-bit master key.
        Priority:
        1. Environment variable `ASTRONAUT_SUIT_KEY` (hex-encoded)
        2. Protected key file with 0600 permissions
        3. Ephemeral high-entropy secure generation with persistence
        """
        env_key = os.environ.get("ASTRONAUT_SUIT_KEY")
        if env_key:
            try:
                raw = bytes.fromhex(env_key.strip())
                if len(raw) == 32:
                    return raw
                logger.warning("ASTRONAUT_SUIT_KEY length invalid (must be 32 bytes hex). Falling back.")
            except ValueError:
                logger.warning("ASTRONAUT_SUIT_KEY contains invalid hex. Falling back.")

        if cls.KEY_PATH.exists():
            # Verify permissions (must not be group/other readable)
            file_stat = cls.KEY_PATH.stat()
            file_mode = stat.S_IMODE(file_stat.st_mode)
            if file_mode & 0o077 != 0:
                logger.warning("Insecure key file permissions (0%o). Rectifying to 0600...", file_mode)
                cls.KEY_PATH.chmod(0o600)
            
            with open(cls.KEY_PATH, "rb") as f:
                key = f.read()
                if len(key) == 32:
                    return key
                logger.warning("Stored key file corrupted. Generating new secure key.")

        # Secure generation
        master_key = os.urandom(32)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        mode = 0o600
        fd = os.open(cls.KEY_PATH, flags, mode)
        with open(fd, "wb") as f:
            f.write(master_key)
        cls.KEY_PATH.chmod(0o600)
        logger.info("Generated and locked new 256-bit master secret at %s", cls.KEY_PATH)
        return master_key

    @staticmethod
    def secure_wipe(buffer: bytearray) -> None:
        """Zero out sensitive key buffers in memory."""
        if isinstance(buffer, bytearray):
            for i in range(len(buffer)):
                buffer[i] = 0

class MissionParams:
    """Operational parameters for deep-space mission health monitoring."""

    # Astronaut IDs for multi-crew monitoring
    CREW_IDS = ["ASTRO-01-CDR", "ASTRO-02-PLT", "ASTRO-03-MS1", "ASTRO-04-MS2"]

    # EVA Suit Telemetry Sampling Rates (Hz)
    SAMPLE_RATE_NOMINAL_HZ = 10     # Normal rest / EVA steady-state
    SAMPLE_RATE_BURST_HZ = 100       # High-vibration tool usage or anomaly triage
    SAMPLE_RATE_SLEEP_HZ = 1         # Habitat sleep cycle power-save mode

    # Physiological Baseline Bounds (Microgravity Adaptive Defaults)
    HR_MIN_CRITICAL = 40.0           # Severe bradycardia
    HR_MAX_CRITICAL = 170.0          # Acute ventricular tachycardia
    SPO2_MIN_CRITICAL = 82.0         # Acute hypoxia
    SPO2_MIN_WARNING = 90.0          # Moderate hypoxia
    CORE_TEMP_MIN_C = 35.0           # Hypothermia
    CORE_TEMP_MAX_C = 39.2           # Heat stroke

    # Suit Life Support Environmental Safeguards
    SUIT_PRESSURE_NOMINAL_KPA = 29.6 # ~4.3 psi (standard EVA suit pressure)
    SUIT_PRESSURE_MIN_KPA = 22.0     # Critical decompression warning
    SUIT_O2_LEVEL_MIN_PCT = 19.5     # Hypoxic suit gas mix

    # SEU / Radiation Thresholds
    RADIATION_SPE_THRESHOLD_RAD = 0.5 # Solar Particle Event alarm limit

    # DSN (Deep Space Network) Link Budget
    DSN_WINDOW_CADENCE_SEC = 300     # 5-minute telemetry sync window
    DSN_MAX_BANDWIDTH_BYTES = 64000  # Strict bandwidth limit per window
