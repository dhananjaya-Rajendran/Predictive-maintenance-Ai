"""
Unit Tests for Dual-Stage ML Prediction Engine, RUL, and SHAP Explainability.
"""
import pytest
from src.ml.predictor import PREDICTION_ENGINE
from src.config import CriticalityTier, RiskTier


def test_prediction_healthy_baseline():
    healthy_features = {
        "vib_rms_current": 1.75,
        "vib_rms_mean_6h": 1.72,
        "vib_rms_slope_24h": 0.02,
        "kurtosis_current": 3.02,
        "crest_factor_current": 2.45,
        "temp_current": 54.0,
        "temp_rate_of_rise_c_per_hour": 0.05,
        "current_rms": 45.0,
        "current_thd": 1.8,
        "rpm": 1780.0
    }

    pred = PREDICTION_ENGINE.predict(
        machine_id="m-test-healthy",
        features=healthy_features,
        criticality_tier=CriticalityTier.TIER_2_MAJOR.value
    )

    assert pred["failure_probability"] < 0.35
    assert pred["risk_tier"] in [RiskTier.HEALTHY.value, RiskTier.WATCH.value]
    assert pred["confidence_score"] >= 0.70
    assert len(pred["top_contributing_features"]) > 0


def test_prediction_bearing_inner_race_fault():
    fault_features = {
        "vib_rms_current": 6.85,
        "vib_rms_mean_6h": 5.90,
        "vib_rms_slope_24h": 2.40,
        "kurtosis_current": 7.20,
        "crest_factor_current": 5.10,
        "temp_current": 78.5,
        "temp_rate_of_rise_c_per_hour": 3.5,
        "current_rms": 52.0,
        "current_thd": 6.8,
        "rpm": 1780.0
    }

    pred = PREDICTION_ENGINE.predict(
        machine_id="m-test-fault",
        features=fault_features,
        criticality_tier=CriticalityTier.TIER_1_BOTTLENECK.value
    )

    assert pred["failure_probability"] >= 0.75
    assert pred["risk_tier"] == RiskTier.CRITICAL.value
    assert 24.0 <= pred["predicted_horizon_hours"] <= 72.0
    assert pred["composite_risk_score"] >= 0.75

    # Check that top SHAP feature mentions vibration kurtosis or RMS
    top_feature_keys = [f["feature_key"] for f in pred["top_contributing_features"]]
    assert any("vibration" in k for k in top_feature_keys)
