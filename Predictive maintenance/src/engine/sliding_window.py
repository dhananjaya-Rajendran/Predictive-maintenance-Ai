"""
Sliding Window Aggregation Module.
Maintains multi-horizon rolling buffers (1h, 6h, 24h, 72h) for time-series features.
"""
from collections import deque
from typing import Dict, List, Any, Optional
import numpy as np
from src.engine.signal_processor import SignalProcessor


class SlidingWindowBuffer:
    """
    Circular sliding-window buffer storing time-stamped sensor observations.
    """

    def __init__(self, machine_id: str, max_points_72h: int = 1440):
        # 1440 samples corresponds to 1 sample / 3 minutes over 72 hours
        self.machine_id = machine_id
        self.max_points = max_points_72h
        self.timestamps = deque(maxlen=max_points_72h)
        self.vibration_de_rms = deque(maxlen=max_points_72h)
        self.vibration_kurtosis = deque(maxlen=max_points_72h)
        self.vibration_crest_factor = deque(maxlen=max_points_72h)
        self.stator_temp_c = deque(maxlen=max_points_72h)
        self.motor_current_a = deque(maxlen=max_points_72h)
        self.rpm = deque(maxlen=max_points_72h)
        self.hydraulic_pressure_bar = deque(maxlen=max_points_72h)
        self.current_thd = deque(maxlen=max_points_72h)

    def append_observation(
        self,
        timestamp_iso: str,
        vib_rms: float,
        vib_kurtosis: float,
        vib_crest_factor: float,
        temp_c: float,
        current_a: float,
        rpm_val: float,
        pressure_bar: float = 120.0,
        thd_val: float = 1.8
    ):
        self.timestamps.append(timestamp_iso)
        self.vibration_de_rms.append(vib_rms)
        self.vibration_kurtosis.append(vib_kurtosis)
        self.vibration_crest_factor.append(vib_crest_factor)
        self.stator_temp_c.append(temp_c)
        self.motor_current_a.append(current_a)
        self.rpm.append(rpm_val)
        self.hydraulic_pressure_bar.append(pressure_bar)
        self.current_thd.append(thd_val)

    def get_aggregated_features(self) -> Dict[str, float]:
        """
        Extracts multi-window rolling features for ML inference.
        """
        if len(self.vibration_de_rms) == 0:
            return {
                "vib_rms_current": 1.8,
                "vib_rms_mean_6h": 1.8,
                "vib_rms_mean_24h": 1.8,
                "vib_rms_slope_24h": 0.0,
                "kurtosis_current": 3.0,
                "kurtosis_mean_6h": 3.0,
                "crest_factor_current": 2.5,
                "temp_current": 55.0,
                "temp_rate_of_rise_c_per_hour": 0.0,
                "current_rms": 45.0,
                "current_thd": 1.8,
                "rpm": 1780.0,
                "hydraulic_pressure": 120.0
            }

        vib_arr = np.array(self.vibration_de_rms)
        kurt_arr = np.array(self.vibration_kurtosis)
        temp_arr = np.array(self.stator_temp_c)

        # 6h window (approx last 120 samples if 3m interval, or last 20% of buffer)
        n_6h = min(len(vib_arr), 120)
        # 24h window (approx last 480 samples)
        n_24h = min(len(vib_arr), 480)

        vib_mean_6h = float(np.mean(vib_arr[-n_6h:]))
        vib_mean_24h = float(np.mean(vib_arr[-n_24h:]))

        # Slope calculation over 24h (mm/s RMS per day)
        if n_24h > 1:
            x = np.arange(n_24h)
            slope = float(np.polyfit(x, vib_arr[-n_24h:], 1)[0] * 480)  # extrapolated daily slope
        else:
            slope = 0.0

        # Thermal rate of rise (last 1 hour = 20 samples)
        n_1h = min(len(temp_arr), 20)
        temp_rate = SignalProcessor.calculate_thermal_rate_of_rise(list(temp_arr[-n_1h:]), dt_hours=1.0)

        return {
            "vib_rms_current": round(float(self.vibration_de_rms[-1]), 3),
            "vib_rms_mean_6h": round(vib_mean_6h, 3),
            "vib_rms_mean_24h": round(vib_mean_24h, 3),
            "vib_rms_slope_24h": round(slope, 3),
            "kurtosis_current": round(float(self.vibration_kurtosis[-1]), 3),
            "kurtosis_mean_6h": round(float(np.mean(kurt_arr[-n_6h:])), 3),
            "crest_factor_current": round(float(self.vibration_crest_factor[-1]), 3),
            "temp_current": round(float(self.stator_temp_c[-1]), 2),
            "temp_rate_of_rise_c_per_hour": round(temp_rate, 3),
            "current_rms": round(float(self.motor_current_a[-1]), 2),
            "current_thd": round(float(self.current_thd[-1]), 2),
            "rpm": round(float(self.rpm[-1]), 1),
            "hydraulic_pressure": round(float(self.hydraulic_pressure_bar[-1]), 1)
        }
