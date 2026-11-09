"""
Psychological Stress, Cognitive Fatigue & Panic Detection Engine.

Implements deep-space psychophysiological monitoring:
1. HRV Time-Domain Metrics: SDNN, RMSSD, pNN50
2. Russian/NASA Baevsky Stress Index (SI) for autonomic tone evaluation
3. Electrodermal Activity (EDA / GSR) Tonic (SCL) and Phasic (SCR) decomposition
4. Multi-modal classifier for Acute Panic Episodes and Stealth Burnout / Cognitive Fatigue
"""

import math
import collections
from typing import Dict, Any, List, Tuple, Optional
import numpy as np

class PsychophysiologicalAnalyzer:
    """
    Analyzes inter-beat intervals (RR/NN) and EDA streams to assess
    astronaut psychological state, panic thresholds, and cognitive exhaustion.
    """

    def __init__(self, astronaut_id: str, buffer_size: int = 120):
        self.astronaut_id = astronaut_id
        self.buffer_size = buffer_size

        # Circular buffer for RR/NN intervals (in milliseconds)
        self._rr_intervals: collections.deque[float] = collections.deque(maxlen=buffer_size)

        # Circular buffer for raw EDA (in microSiemens, uS)
        self._eda_buffer: collections.deque[float] = collections.deque(maxlen=buffer_size)

        # Baseline SCL (tonic component tracking)
        self._tonic_scl_ema: float = 2.0  # Typical resting skin conductance (uS)
        self._tonic_alpha: float = 0.01

        # Phasic SCR peak detector state
        self._recent_scr_peaks: collections.deque[float] = collections.deque(maxlen=60)
        self._prev_eda_diff: float = 0.0

        # Burnout history tracker (rolling window of SDNN over past evaluations)
        self._sdnn_history: collections.deque[float] = collections.deque(maxlen=30)

    def add_cardiac_sample(self, heart_rate_bpm: float) -> None:
        """Derives inter-beat interval (ms) from instantaneous heart rate with physiological noise."""
        if heart_rate_bpm <= 0:
            return
        # Calculate approximate instantaneous RR interval in ms
        rr_ms = 60000.0 / heart_rate_bpm
        self._rr_intervals.append(rr_ms)

    def add_eda_sample(self, eda_microsiemens: float, timestamp_sec: float) -> None:
        """Processes skin conductance for tonic baseline and phasic peak detection."""
        val = max(0.1, min(35.0, float(eda_microsiemens)))
        self._eda_buffer.append(val)

        # Update Tonic SCL (low-pass EMA)
        self._tonic_scl_ema = (1.0 - self._tonic_alpha) * self._tonic_scl_ema + self._tonic_alpha * val

        # Phasic SCR Peak Detection
        # An SCR peak is a steep rise (> 0.02 uS) followed by inflection
        if len(self._eda_buffer) >= 3:
            y0, y1, y2 = self._eda_buffer[-3], self._eda_buffer[-2], self._eda_buffer[-1]
            diff1 = y1 - y0
            diff2 = y2 - y1
            if diff1 > 0.02 and diff2 <= 0.01:
                # Local peak detected
                self._recent_scr_peaks.append(timestamp_sec)

    def compute_hrv_metrics(self) -> Dict[str, float]:
        """Calculates standard HRV parameters (SDNN, RMSSD, pNN50, Baevsky SI)."""
        if len(self._rr_intervals) < 10:
            return {
                "sdnn_ms": 50.0,
                "rmssd_ms": 42.0,
                "pnn50_pct": 15.0,
                "baevsky_stress_index": 100.0,
                "sample_count": len(self._rr_intervals)
            }

        rr = np.array(self._rr_intervals)
        rr_diff = np.diff(rr)

        # SDNN: Standard deviation of NN intervals
        sdnn = float(np.std(rr, ddof=1))

        # RMSSD: Root Mean Square of Successive Differences
        rmssd = float(np.sqrt(np.mean(rr_diff ** 2)))

        # pNN50: Percentage of successive differences > 50 ms
        pnn50 = float(np.sum(np.abs(rr_diff) > 50.0) / len(rr_diff) * 100.0)

        # Baevsky Stress Index (SI): SI = AMo / (2 * Mo * MxDMn)
        # Convert ms to seconds for Baevsky standard formula
        rr_sec = rr / 1000.0
        bin_width = 0.05  # 50 ms bins
        hist, bin_edges = np.histogram(rr_sec, bins=max(5, int((np.max(rr_sec) - np.min(rr_sec)) / bin_width) + 1))
        max_idx = int(np.argmax(hist))
        mo = (bin_edges[max_idx] + bin_edges[max_idx + 1]) / 2.0  # Mode
        amo = (hist[max_idx] / len(rr_sec)) * 100.0                # Amplitude of Mode (%)
        mxdmn = max(0.05, float(np.max(rr_sec) - np.min(rr_sec)))  # Variation Range

        baevsky_si = float(amo / (2.0 * max(0.3, mo) * mxdmn))

        # Track history for burnout detection
        self._sdnn_history.append(sdnn)

        return {
            "sdnn_ms": round(sdnn, 2),
            "rmssd_ms": round(rmssd, 2),
            "pnn50_pct": round(pnn50, 1),
            "baevsky_stress_index": round(baevsky_si, 1),
            "sample_count": len(self._rr_intervals)
        }

    def compute_eda_metrics(self, current_time_sec: float) -> Dict[str, float]:
        """Calculates Tonic SCL and Phasic SCR peak frequency."""
        # Clean peaks older than 60 seconds
        cutoff = current_time_sec - 60.0
        while self._recent_scr_peaks and self._recent_scr_peaks[0] < cutoff:
            self._recent_scr_peaks.popleft()

        scr_peaks_per_min = float(len(self._recent_scr_peaks))

        return {
            "tonic_scl_us": round(self._tonic_scl_ema, 2),
            "scr_peaks_per_min": scr_peaks_per_min
        }

    def evaluate_psychological_state(self, current_time_sec: float) -> Dict[str, Any]:
        """
        Synthesizes HRV and EDA biomarkers into a diagnostic cognitive assessment:
        - NOMINAL_REST
        - ACTIVE_WORKLOAD
        - ACUTE_PANIC
        - STEALTH_BURNOUT
        """
        hrv = self.compute_hrv_metrics()
        eda = self.compute_eda_metrics(current_time_sec)

        rmssd = hrv["rmssd_ms"]
        sdnn = hrv["sdnn_ms"]
        si = hrv["baevsky_stress_index"]
        scr_rate = eda["scr_peaks_per_min"]
        tonic_scl = eda["tonic_scl_us"]

        # Classification Logic
        # 1. Acute Panic / Hyper-Arousal:
        # Parasympathetic collapse (RMSSD < 18ms), Baevsky SI > 500, burst of SCR peaks (> 7/min)
        if (rmssd < 20.0 and si > 450.0) or (si > 700.0 and scr_rate >= 6.0):
            state = "ACUTE_PANIC_EPISODE"
            severity = "CRITICAL"
            advice = "Trigger suit soothing haptic cadence; instruct 4-7-8 tactical box breathing; halt high-risk EVA operations."
        
        # 2. Stealth Psychological Burnout / Chronic Cognitive Fatigue:
        # Sustained low autonomic tone (SDNN < 24ms over time), elevated tonic SCL, low pNN50
        elif (len(self._sdnn_history) >= 15 and np.mean(self._sdnn_history) < 26.0 and tonic_scl > 4.5) or (sdnn < 22.0 and hrv["pnn50_pct"] < 3.0):
            state = "STEALTH_BURNOUT_FATIGUE"
            severity = "WARNING"
            advice = "Cognitive degradation detected. Recommend task rotation, hydration, and sleep cycle rescheduling."

        # 3. Elevated Cognitive Load / Workload Strain:
        elif si > 250.0 or scr_rate >= 5.0 or rmssd < 28.0:
            state = "ELEVATED_COGNITIVE_LOAD"
            severity = "ELEVATED"
            advice = "Astronaut under significant operational focus/strain. Monitor error rates."

        # 4. Nominal:
        else:
            state = "NOMINAL_OPTIMAL"
            severity = "NORMAL"
            advice = "Psychophysiological markers within optimal mission envelope."

        return {
            "astronaut_id": self.astronaut_id,
            "psych_state": state,
            "severity_level": severity,
            "advice": advice,
            "metrics": {
                "rmssd_ms": rmssd,
                "sdnn_ms": sdnn,
                "baevsky_si": si,
                "scr_peaks_per_min": scr_rate,
                "tonic_scl_us": tonic_scl
            }
        }
