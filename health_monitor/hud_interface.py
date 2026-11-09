"""
EVA Ergonomic Head-Up Display (HUD) Interface.

Implements deep-space EVA helmet display requirements:
1. High-Contrast, Glare-Resistant Visual Design (ANSI 256/TrueColor)
2. Low-Cognitive Load Tactical Telemetry Gauges
3. Instant Critical Alarm Override (preempts navigation, checklists, cameras)
4. Haptic & Acoustic Suit Cue Generation
5. Glove-Friendly Single-Key Acknowledgment with 15s Auto-Escalation
"""

import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("EVA_HUD")

class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    FLASH = "\033[5m"
    BG_BLACK = "\033[40m"
    
    # High-lum visibility colors for gold-tinted visors
    RED_ALERT = "\033[91;1m"
    AMBER_WARN = "\033[93;1m"
    GREEN_NOMINAL = "\033[92;1m"
    CYAN_INFO = "\033[96;1m"
    WHITE_BOLD = "\033[97;1m"
    DIM = "\033[90m"


class EVAHeadUpDisplay:
    """
    Renders high-contrast, low-cognitive-load HUD frames
    and handles emergency interrupt overrides.
    """

    def __init__(self, wearer_id: str = "ASTRO-01-CDR"):
        self.wearer_id = wearer_id
        self.active_critical_alert: Optional[Dict[str, Any]] = None
        self.alert_start_time: float = 0.0
        self.is_acknowledged: bool = False
        self.escalated_to_habitat: bool = False

    def trigger_critical_override(self, alert_data: Dict[str, Any]) -> None:
        """Forcibly overrides all non-essential HUD screens with emergency directive."""
        self.active_critical_alert = alert_data
        self.alert_start_time = time.time()
        self.is_acknowledged = False
        self.escalated_to_habitat = False
        # Acoustic klaxon bell trigger
        print("\a", end="", flush=True)

    def acknowledge_glove_button(self) -> str:
        """Single physical button press acknowledgment (glove-friendly)."""
        if self.active_critical_alert:
            self.is_acknowledged = True
            msg = f"[HUD ACK] Wearer {self.wearer_id} acknowledged alert: {self.active_critical_alert.get('diagnostic', 'CRITICAL')}"
            logger.info(msg)
            return msg
        return "[HUD ACK] No active emergency alert to acknowledge."

    def clear_alert(self) -> None:
        """Clears resolved alert."""
        self.active_critical_alert = None
        self.is_acknowledged = False
        self.escalated_to_habitat = False

    def render_frame(self, telemetry: Dict[str, Any], triage_summary: Optional[Dict[str, Any]] = None) -> str:
        """
        Renders HUD telemetry frame.
        If critical alert is active, renders emergency override screen.
        """
        now = time.time()
        lines = []

        # Check for unacknowledged escalation (15-second timeout)
        if self.active_critical_alert and not self.is_acknowledged:
            elapsed = now - self.alert_start_time
            if elapsed > 15.0 and not self.escalated_to_habitat:
                self.escalated_to_habitat = True
                logger.critical("[HUD AUTO-ESCALATE] Critical alert unacknowledged for %.1fs. Transmitting squad distress signal!", elapsed)

        # ---------------- EMERGENCY OVERRIDE VIEW ----------------
        if self.active_critical_alert:
            elapsed_sec = int(now - self.alert_start_time)
            lines.append(f"{Color.BG_BLACK}{Color.RED_ALERT}╔══════════════════════════════════════════════════════════════════════════════╗{Color.RESET}")
            lines.append(f"{Color.BG_BLACK}{Color.RED_ALERT}║  !!! CRITICAL LIFE-SUPPORT OVERRIDE -- IMMEDIATE ACTION REQUIRED !!!        ║{Color.RESET}")
            lines.append(f"{Color.BG_BLACK}{Color.RED_ALERT}╠══════════════════════════════════════════════════════════════════════════════╣{Color.RESET}")
            
            diagnostic = self.active_critical_alert.get("diagnostic", "ACUTE HYPOXIA / PRESSURE LOSS")
            lines.append(f"{Color.BG_BLACK}{Color.WHITE_BOLD}║  EMERGENCY:   {Color.RED_ALERT}{diagnostic:<58} {Color.WHITE_BOLD}║{Color.RESET}")
            
            action = self.active_critical_alert.get("action", "ENGAGE O2 PURGE VALVE & RETURN TO AIRLOCK")
            lines.append(f"{Color.BG_BLACK}{Color.WHITE_BOLD}║  DIRECTIVE:   {Color.AMBER_WARN}{action:<58} {Color.WHITE_BOLD}║{Color.RESET}")

            # Haptic and Audio Status
            lines.append(f"{Color.BG_BLACK}{Color.CYAN_INFO}║  HAPTIC CUE:  [((( 250Hz RAPID TRIPLE-PULSE ACTIVE )))]                      ║{Color.RESET}")
            lines.append(f"{Color.BG_BLACK}{Color.CYAN_INFO}║  AUDIO CUE:   [(( 800Hz DUAL-TONE EMERGENCY KLAXON ACTIVE ))]               ║{Color.RESET}")

            # Acknowledgment status
            if self.is_acknowledged:
                ack_status = f"{Color.GREEN_NOMINAL}ACKNOWLEDGED BY WEARER (LOCAL COUNTERMEASURES RUNNING){Color.WHITE_BOLD}"
            elif self.escalated_to_habitat:
                ack_status = f"{Color.RED_ALERT}UNACKNOWLEDGED ({elapsed_sec}s) - SQUAD & HABITAT RESCUE ESCALATED!{Color.WHITE_BOLD}"
            else:
                ack_status = f"{Color.FLASH}{Color.AMBER_WARN}PRESS [SPACE] OR SUIT GLOVE BUTTON TO ACKNOWLEDGE ({15 - elapsed_sec}s left){Color.RESET}{Color.WHITE_BOLD}"

            lines.append(f"{Color.BG_BLACK}{Color.WHITE_BOLD}║  STATUS:      {ack_status:<58} ║{Color.RESET}")
            lines.append(f"{Color.BG_BLACK}{Color.RED_ALERT}╚══════════════════════════════════════════════════════════════════════════════╝{Color.RESET}")
            return "\n".join(lines)

        # ---------------- NOMINAL TACTICAL HUD VIEW ----------------
        hr = telemetry.get("filtered_hr", 75.0)
        spo2 = telemetry.get("filtered_spo2", 98.0)
        suit_p = telemetry.get("suit_pressure_kpa", 29.6)
        stress = telemetry.get("stress_index", 110.0)
        sqi = telemetry.get("sqi", 0.95)
        motion_active = telemetry.get("motion_artifact_detected", False)

        # Dynamic color coding for low cognitive load
        hr_color = Color.GREEN_NOMINAL if 50 <= hr <= 110 else (Color.AMBER_WARN if 110 < hr <= 140 else Color.RED_ALERT)
        spo2_color = Color.GREEN_NOMINAL if spo2 >= 92 else (Color.AMBER_WARN if spo2 >= 85 else Color.RED_ALERT)
        p_color = Color.GREEN_NOMINAL if suit_p >= 27.0 else (Color.AMBER_WARN if suit_p >= 23.0 else Color.RED_ALERT)
        stress_color = Color.GREEN_NOMINAL if stress < 200 else (Color.AMBER_WARN if stress < 450 else Color.RED_ALERT)

        motion_badge = f"{Color.AMBER_WARN}[TOOL VIBRATION ACTIVE - DSP MOTION REJECTION ON]{Color.RESET}" if motion_active else f"{Color.CYAN_INFO}[MOTION STABLE]{Color.RESET}"

        lines.append(f"{Color.BG_BLACK}{Color.CYAN_INFO}┌─── EVA TACTICAL HUD ─── {Color.WHITE_BOLD}{self.wearer_id}{Color.CYAN_INFO} ──────────────────────────────────────┐{Color.RESET}")
        lines.append(f"{Color.BG_BLACK}{Color.CYAN_INFO}│ {motion_badge:<73} │{Color.RESET}")
        lines.append(f"{Color.BG_BLACK}{Color.CYAN_INFO}├─────────────────────────────────────────────────────────────────────────────┤{Color.RESET}")
        
        # Telemetry Gauge Line
        g1 = f"HR: {hr_color}{hr:5.1f} bpm{Color.RESET}"
        g2 = f"SpO2: {spo2_color}{spo2:5.1f} %{Color.RESET}"
        g3 = f"SUIT-P: {p_color}{suit_p:4.1f} kPa{Color.RESET}"
        g4 = f"STRESS-SI: {stress_color}{stress:4.0f}{Color.RESET}"
        lines.append(f"{Color.BG_BLACK}{Color.CYAN_INFO}│  {g1}   │   {g2}   │   {g3}   │   {g4}  │{Color.RESET}")

        # Signal Quality Index Bar
        bar_len = int(sqi * 20)
        sqi_bar = "█" * bar_len + "░" * (20 - bar_len)
        lines.append(f"{Color.BG_BLACK}{Color.CYAN_INFO}│  SIGNAL QUALITY (SQI): [{Color.GREEN_NOMINAL}{sqi_bar}{Color.CYAN_INFO}] {int(sqi*100):3d}%     DSN LINK: {Color.DIM}[STANDBY - 4m]{Color.CYAN_INFO} │{Color.RESET}")

        # Crew Squad Triage Summary (if present)
        if triage_summary:
            lines.append(f"{Color.BG_BLACK}{Color.CYAN_INFO}├── SQUAD TRIAGE RADAR ───────────────────────────────────────────────────────┤{Color.RESET}")
            crew_items = []
            for item in triage_summary.get("ranked_crew", [])[:4]:
                c_id = item["astronaut_id"]
                t_lbl = item["tier_label"].split("_")[1] # RED, YELLOW, GREEN
                c_col = Color.RED_ALERT if t_lbl == "RED" else (Color.AMBER_WARN if t_lbl == "YELLOW" else Color.GREEN_NOMINAL)
                crew_items.append(f"{c_id}: {c_col}{t_lbl}{Color.CYAN_INFO}")
            squad_line = "  |  ".join(crew_items)
            lines.append(f"{Color.BG_BLACK}{Color.CYAN_INFO}│  {squad_line:<73} │{Color.RESET}")

        lines.append(f"{Color.BG_BLACK}{Color.CYAN_INFO}└─────────────────────────────────────────────────────────────────────────────┘{Color.RESET}")
        return "\n".join(lines)
