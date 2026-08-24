"""
Signal Processing and Feature Engineering Module.
Extracts time-domain, frequency-domain (FFT), and physical features from raw industrial sensor waveforms.
"""
import math
import numpy as np
from typing import Dict, List, Tuple, Any, Optional
from scipy.signal import find_peaks
from src.config import CONFIG


class SignalProcessor:
    """
    High-performance signal processing engine for mechanical and electrical telemetry.
    """

    @staticmethod
    def calculate_time_domain_features(signal: np.ndarray) -> Dict[str, float]:
        """
        Calculates time-domain statistical moments and envelope metrics.
        """
        if len(signal) == 0:
            return {
                "rms": 0.0,
                "peak_to_peak": 0.0,
                "kurtosis": 3.0,
                "crest_factor": 1.0,
                "skewness": 0.0,
                "variance": 0.0,
                "mean": 0.0
            }

        arr = np.asarray(signal, dtype=np.float64)
        mean_val = float(np.mean(arr))
        variance_val = float(np.var(arr))
        std_val = float(np.std(arr))
        rms_val = float(np.sqrt(np.mean(arr ** 2)))
        peak_val = float(np.max(np.abs(arr)))
        peak_to_peak_val = float(np.max(arr) - np.min(arr))

        # Kurtosis (4th normalized statistical moment)
        if std_val > 1e-9:
            kurtosis_val = float(np.mean(((arr - mean_val) / std_val) ** 4))
            skewness_val = float(np.mean(((arr - mean_val) / std_val) ** 3))
        else:
            kurtosis_val = 3.0
            skewness_val = 0.0

        # Crest Factor (Peak / RMS)
        crest_factor_val = float(peak_val / (rms_val + 1e-9))

        return {
            "rms": round(rms_val, 4),
            "peak_to_peak": round(peak_to_peak_val, 4),
            "kurtosis": round(kurtosis_val, 4),
            "crest_factor": round(crest_factor_val, 4),
            "skewness": round(skewness_val, 4),
            "variance": round(variance_val, 4),
            "mean": round(mean_val, 4)
        }

    @staticmethod
    def compute_fft_spectrum(
        signal: np.ndarray,
        sample_rate_hz: float
    ) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
        """
        Computes single-sided Fast Fourier Transform (FFT) Power Spectrum and spectral indicators.
        Returns: (frequencies, amplitudes, spectral_metrics)
        """
        n = len(signal)
        if n < 4:
            return np.array([0.0]), np.array([0.0]), {
                "peak_frequency_hz": 0.0,
                "spectral_energy_low_hz": 0.0,
                "spectral_energy_mid_hz": 0.0,
                "spectral_energy_high_hz": 0.0,
                "spectral_centroid": 0.0
            }

        # Apply Hanning window to prevent spectral leakage
        window = np.hanning(n)
        windowed_signal = (signal - np.mean(signal)) * window

        # Compute Real FFT with coherent window gain correction
        fft_vals = np.fft.rfft(windowed_signal)
        freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate_hz)
        window_coherent_gain = np.sum(window)
        amplitudes = np.abs(fft_vals) * (2.0 / (window_coherent_gain + 1e-9))

        # Spectral Centroid
        total_amp = np.sum(amplitudes)
        if total_amp > 1e-9:
            spectral_centroid = float(np.sum(freqs * amplitudes) / total_amp)
        else:
            spectral_centroid = 0.0

        # Dominant peak frequency
        peak_idx = int(np.argmax(amplitudes))
        peak_freq = float(freqs[peak_idx])

        # Energy in critical frequency bands (Low: 0-100Hz, Mid: 100-1000Hz, High: 1000-10000Hz)
        low_band = amplitudes[(freqs >= 0) & (freqs < 100)]
        mid_band = amplitudes[(freqs >= 100) & (freqs < 1000)]
        high_band = amplitudes[(freqs >= 1000)]

        spectral_metrics = {
            "peak_frequency_hz": round(peak_freq, 2),
            "peak_amplitude": round(float(amplitudes[peak_idx]), 4),
            "spectral_energy_low_hz": round(float(np.sum(low_band ** 2)), 4),
            "spectral_energy_mid_hz": round(float(np.sum(mid_band ** 2)), 4),
            "spectral_energy_high_hz": round(float(np.sum(high_band ** 2)), 4),
            "spectral_centroid": round(spectral_centroid, 2)
        }

        return freqs, amplitudes, spectral_metrics

    @staticmethod
    def calculate_bearing_fault_frequencies(
        rpm: float,
        num_rollers: int = CONFIG.DEFAULT_ROLLER_COUNT,
        roller_diameter_mm: float = CONFIG.DEFAULT_ROLLER_DIAMETER_MM,
        pitch_diameter_mm: float = CONFIG.DEFAULT_PITCH_DIAMETER_MM,
        contact_angle_deg: float = CONFIG.DEFAULT_CONTACT_ANGLE_DEG
    ) -> Dict[str, float]:
        """
        Calculates theoretical bearing fault characteristic frequencies based on kinematic equations:
        - Shaft Rotational Frequency (1X)
        - Ball Pass Frequency Inner Ring (BPFI)
        - Ball Pass Frequency Outer Ring (BPFO)
        - Ball Spin Frequency (BSF)
        - Fundamental Train Frequency / Cage (FTF)
        """
        shaft_freq_hz = rpm / 60.0
        gamma = (roller_diameter_mm / pitch_diameter_mm) * math.cos(math.radians(contact_angle_deg))

        bpfi = (num_rollers / 2.0) * shaft_freq_hz * (1.0 + gamma)
        bpfo = (num_rollers / 2.0) * shaft_freq_hz * (1.0 - gamma)
        bsf = (pitch_diameter_mm / (2.0 * roller_diameter_mm)) * shaft_freq_hz * (1.0 - (gamma ** 2))
        ftf = 0.5 * shaft_freq_hz * (1.0 - gamma)

        return {
            "shaft_rotational_1x_hz": round(shaft_freq_hz, 2),
            "shaft_rotational_2x_hz": round(shaft_freq_hz * 2.0, 2),
            "bpfi_inner_race_hz": round(bpfi, 2),
            "bpfo_outer_race_hz": round(bpfo, 2),
            "bsf_roller_spin_hz": round(bsf, 2),
            "ftf_cage_hz": round(ftf, 2)
        }

    @staticmethod
    def calculate_thermal_rate_of_rise(temp_history_celsius: List[float], dt_hours: float = 1.0) -> float:
        """
        Calculates stator/bearing temperature rate of rise in deg C / hour.
        """
        if len(temp_history_celsius) < 2 or dt_hours <= 0:
            return 0.0
        delta_temp = temp_history_celsius[-1] - temp_history_celsius[0]
        rate = delta_temp / dt_hours
        return round(float(rate), 3)

    @staticmethod
    def calculate_current_thd(current_waveform: np.ndarray, sample_rate_hz: float, fundamental_hz: float = 60.0) -> float:
        """
        Computes Total Harmonic Distortion (THD %) on motor current waveform.
        """
        if len(current_waveform) < 16:
            return 1.50

        freqs, amps, _ = SignalProcessor.compute_fft_spectrum(current_waveform, sample_rate_hz)
        fund_mask = (freqs >= fundamental_hz * 0.9) & (freqs <= fundamental_hz * 1.1)
        fund_amp = np.max(amps[fund_mask]) if np.any(fund_mask) else 1.0

        if fund_amp <= 1e-6:
            return 1.50

        harmonic_mask = (freqs > fundamental_hz * 1.2) & (freqs <= fundamental_hz * 10.0)
        harmonic_sum_sq = np.sum(amps[harmonic_mask] ** 2) if np.any(harmonic_mask) else 0.0

        thd = (np.sqrt(harmonic_sum_sq) / fund_amp) * 100.0
        return round(float(min(max(thd, 0.5), 35.0)), 2)
