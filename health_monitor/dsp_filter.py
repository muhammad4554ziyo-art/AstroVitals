"""
Real-Time Digital Signal Processing (DSP) & Motion Artifact Cancellation.

Eliminates false-positive alarms caused by physical exertion, jumping,
and heavy EVA power tool vibration via:
1. Dynamic Motion-Correlated 1D Adaptive Kalman Filtering (C++ accelerated or Python fallback)
2. Normalized Acceleration Jerk & Vibration Correlator
3. Outlier Rejection & Signal Quality Index (SQI) Estimation
4. Motion Artifact Suppression on ECG, Heart Rate, and SpO2
"""

import ctypes
import math
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import numpy as np

# Attempt to load C++ DSP core library
LIB_PATH = Path(__file__).resolve().parent / "libdsp_core.so"
c_dsp = None

if LIB_PATH.exists():
    try:
        c_dsp = ctypes.CDLL(str(LIB_PATH))
        # Configure C signatures
        c_dsp.dsp_kalman_create.argtypes = [ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double]
        c_dsp.dsp_kalman_create.restype = ctypes.c_void_p

        c_dsp.dsp_kalman_update.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_double]
        c_dsp.dsp_kalman_update.restype = ctypes.c_double

        c_dsp.dsp_kalman_get_state.argtypes = [ctypes.c_void_p]
        c_dsp.dsp_kalman_get_state.restype = ctypes.c_double

        c_dsp.dsp_kalman_destroy.argtypes = [ctypes.c_void_p]
        c_dsp.dsp_kalman_destroy.restype = None
    except Exception:
        c_dsp = None


class PythonAdaptiveKalman:
    """Pure Python implementation of motion-adaptive Kalman filter."""

    def __init__(self, init_state: float = 72.0, init_p: float = 5.0,
                 q: float = 0.05, r_base: float = 1.5, motion_alpha: float = 4.0):
        self.state = float(init_state)
        self.p = float(init_p)
        self.q = float(q)
        self.r_base = float(r_base)
        self.motion_alpha = float(motion_alpha)

    def update(self, measurement: float, motion_intensity: float) -> float:
        # Time update (Predict)
        p_prior = self.p + self.q

        # Measurement noise scaled by motion artifact
        r_eff = self.r_base * (1.0 + self.motion_alpha * (motion_intensity ** 2))

        # Measurement update (Correct)
        innovation = measurement - self.state
        s = p_prior + r_eff
        k = p_prior / s

        self.state = self.state + k * innovation
        self.p = (1.0 - k) * p_prior
        return self.state

    def reset(self, new_state: float) -> None:
        self.state = new_state
        self.p = 5.0


class BiometricDSPPipeline:
    """
    Cascaded Real-Time DSP Pipeline for EVA Biometric Streams.
    Processes Heart Rate, SpO2, and ECG against 3-axis Accelerometer & Vibration inputs.
    """

    def __init__(self, astronaut_id: str, local_gravity_g: float = 0.0):
        """
        :param astronaut_id: Unique crew member ID
        :param local_gravity_g: Local gravitational acceleration (0.0 m/s^2 microgravity, 1.62 Lunar, 3.71 Mars)
        """
        self.astronaut_id = astronaut_id
        self.local_g = local_gravity_g

        # C++ or Python Kalman filter handles for HR
        self._cpp_hr_handle = None
        if c_dsp is not None:
            self._cpp_hr_handle = c_dsp.dsp_kalman_create(72.0, 5.0, 0.05, 1.5, 4.0)
        self._py_hr_filter = PythonAdaptiveKalman(72.0, 5.0, 0.05, 1.5, 4.0)

        # SpO2 Kalman filter (pure Python)
        self._py_spo2_filter = PythonAdaptiveKalman(98.0, 1.0, 0.01, 0.8, 6.0)

        # Sliding window for motion envelope calculation
        self._accel_history: list[float] = []
        self._window_size = 10

        # Ring buffer for median filter
        self._hr_recent_raw: list[float] = []
        self._spo2_recent_raw: list[float] = []

    def __del__(self):
        if self._cpp_hr_handle and c_dsp is not None:
            c_dsp.dsp_kalman_destroy(self._cpp_hr_handle)
            self._cpp_hr_handle = None

    def compute_motion_intensity(self, ax: float, ay: float, az: float, vibration_rms: float = 0.0) -> float:
        """
        Calculates dynamic motion artifact intensity.
        Separates static gravitational acceleration from dynamic exertion and tool vibration.
        """
        total_accel = math.sqrt(ax * ax + ay * ay + az * az)
        dynamic_jerk = abs(total_accel - self.local_g)
        motion_index = dynamic_jerk + (vibration_rms * 2.5)

        self._accel_history.append(motion_index)
        if len(self._accel_history) > self._window_size:
            self._accel_history.pop(0)

        # Return smoothed motion envelope
        return float(np.mean(self._accel_history))

    def filter_telemetry_frame(self,
                               raw_hr: float,
                               raw_spo2: float,
                               ax: float,
                               ay: float,
                               az: float,
                               tool_vibration: float = 0.0) -> Dict[str, Any]:
        """
        Filters raw biometric frame and rejects motion artifacts.
        
        Returns filtered vitals, Signal Quality Index (SQI), and motion flag.
        """
        total_accel = math.sqrt(ax * ax + ay * ay + az * az)
        dynamic_jerk = abs(total_accel - self.local_g)
        instant_motion = dynamic_jerk + (tool_vibration * 2.5)

        motion_intensity = self.compute_motion_intensity(ax, ay, az, tool_vibration)

        # Signal Quality Index (1.0 = pristine studio quality, 0.0 = completely corrupted)
        sqi = max(0.05, min(1.0, 1.0 / (1.0 + 0.35 * motion_intensity)))
        is_motion_artifact_active = (motion_intensity > 1.8) or (instant_motion > 2.5)

        # 1. Heart Rate Filtering
        # Pre-filter spike rejection: If sudden delta > 30 bpm during heavy vibration, suppress spike
        if len(self._hr_recent_raw) > 3:
            median_prev = float(np.median(self._hr_recent_raw[-5:]))
            if abs(raw_hr - median_prev) > 25.0 and is_motion_artifact_active:
                # Clamp raw spike to median + damped delta
                damped_delta = math.copysign(5.0, raw_hr - median_prev)
                effective_raw_hr = median_prev + damped_delta
            else:
                effective_raw_hr = raw_hr
        else:
            effective_raw_hr = raw_hr

        self._hr_recent_raw.append(effective_raw_hr)
        if len(self._hr_recent_raw) > 20:
            self._hr_recent_raw.pop(0)

        # Kalman Filter Update
        if self._cpp_hr_handle and c_dsp is not None:
            filtered_hr = c_dsp.dsp_kalman_update(self._cpp_hr_handle, effective_raw_hr, motion_intensity)
        else:
            filtered_hr = self._py_hr_filter.update(effective_raw_hr, motion_intensity)

        # 2. SpO2 Filtering
        # SpO2 cannot physically jump 10% in 100ms; optical motion artifact rejector
        if len(self._spo2_recent_raw) > 3:
            median_spo2 = float(np.median(self._spo2_recent_raw[-5:]))
            if raw_spo2 < 85.0 and is_motion_artifact_active and (median_spo2 > 93.0):
                # Optical probe disconnect or heavy hand motion artifact
                effective_spo2 = median_spo2 - 0.5
            else:
                effective_spo2 = raw_spo2
        else:
            effective_spo2 = raw_spo2

        self._spo2_recent_raw.append(effective_spo2)
        if len(self._spo2_recent_raw) > 20:
            self._spo2_recent_raw.pop(0)

        filtered_spo2 = self._py_spo2_filter.update(effective_spo2, motion_intensity)
        # Cap physiological boundaries
        filtered_spo2 = max(50.0, min(100.0, filtered_spo2))

        return {
            "astronaut_id": self.astronaut_id,
            "raw_hr": round(raw_hr, 1),
            "filtered_hr": round(filtered_hr, 1),
            "raw_spo2": round(raw_spo2, 1),
            "filtered_spo2": round(filtered_spo2, 1),
            "motion_intensity": round(motion_intensity, 2),
            "sqi": round(sqi, 3),
            "motion_artifact_detected": is_motion_artifact_active,
            "accelerometer": (round(ax, 2), round(ay, 2), round(az, 2)),
            "tool_vibration": round(tool_vibration, 2)
        }
