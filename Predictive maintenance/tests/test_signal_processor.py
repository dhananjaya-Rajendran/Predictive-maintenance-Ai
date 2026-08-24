"""
Unit Tests for Signal Processing, FFT, and Bearing Kinematics.
"""
import numpy as np
import pytest
from src.engine.signal_processor import SignalProcessor


def test_time_domain_features():
    # Synthetic sinusoidal test waveform
    t = np.linspace(0, 1.0, 1000, endpoint=False)
    sig = 2.0 * np.sin(2 * np.pi * 50.0 * t)

    feats = SignalProcessor.calculate_time_domain_features(sig)

    # Theoretical RMS for sine wave of amp 2.0 is 2.0 / sqrt(2) ≈ 1.414
    assert pytest.approx(feats["rms"], 0.05) == 1.414
    assert pytest.approx(feats["peak_to_peak"], 0.1) == 4.0
    assert "kurtosis" in feats
    assert "crest_factor" in feats


def test_fft_spectrum():
    sample_rate = 2000.0
    duration = 0.5
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)

    # 120 Hz pure tone
    sig = 3.0 * np.sin(2 * np.pi * 120.0 * t)
    freqs, amps, metrics = SignalProcessor.compute_fft_spectrum(sig, sample_rate_hz=sample_rate)

    assert metrics["peak_frequency_hz"] == 120.0
    assert metrics["peak_amplitude"] > 2.5


def test_bearing_kinematics():
    kinematics = SignalProcessor.calculate_bearing_fault_frequencies(
        rpm=1780.0,
        num_rollers=9,
        roller_diameter_mm=7.94,
        pitch_diameter_mm=38.5
    )

    # 1780 RPM -> Shaft speed ≈ 29.67 Hz
    assert pytest.approx(kinematics["shaft_rotational_1x_hz"], 0.1) == 29.67
    # BPFI should be greater than 1X * (rollers/2)
    assert kinematics["bpfi_inner_race_hz"] > 140.0
    assert kinematics["bpfo_outer_race_hz"] < kinematics["bpfi_inner_race_hz"]
