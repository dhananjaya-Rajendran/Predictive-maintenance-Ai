"""
Stage 1: Semi-Supervised Anomaly Detector.
Trained on healthy baseline distributions to score novel mechanical/electrical drift.
"""
import numpy as np
from typing import Dict, Any, List
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


class AnomalyDetector:
    """
    Stage 1 Anomaly Scoring Engine.
    Detects multivariate feature deviations from nominal baseline operations.
    """

    FEATURE_KEYS = [
        "vib_rms_current",
        "vib_rms_mean_6h",
        "kurtosis_current",
        "crest_factor_current",
        "temp_current",
        "temp_rate_of_rise_c_per_hour",
        "current_thd"
    ]

    def __init__(self):
        self.scaler = StandardScaler()
        self.model = IsolationForest(
            n_estimators=100,
            contamination=0.03,
            random_state=42
        )
        self.is_fitted = False
        self._fit_default_baseline()

    def _fit_default_baseline(self):
        """
        Generates synthetic healthy baseline distributions across all key sensor features.
        """
        np.random.seed(42)
        n_samples = 2500

        # Normal distributions representing healthy automotive machinery
        vib_rms = np.random.normal(1.8, 0.35, n_samples)
        vib_mean_6h = np.random.normal(1.8, 0.25, n_samples)
        kurtosis = np.random.normal(3.05, 0.20, n_samples)
        crest_factor = np.random.normal(2.6, 0.30, n_samples)
        temp = np.random.normal(54.0, 4.5, n_samples)
        temp_rate = np.random.normal(0.05, 0.10, n_samples)
        current_thd = np.random.normal(1.8, 0.30, n_samples)

        X_baseline = np.column_stack([
            vib_rms,
            vib_mean_6h,
            kurtosis,
            crest_factor,
            temp,
            temp_rate,
            current_thd
        ])

        X_scaled = self.scaler.fit_transform(X_baseline)
        self.model.fit(X_scaled)
        self.is_fitted = True

    def compute_anomaly_score(self, features: Dict[str, float]) -> float:
        """
        Computes normalized anomaly score in range [0.0, 1.0].
        0.0 = Perfectly Normal Baseline, 1.0 = Extreme Novel Anomaly.
        """
        raw_vec = np.array([[
            features.get("vib_rms_current", 1.8),
            features.get("vib_rms_mean_6h", 1.8),
            features.get("kurtosis_current", 3.0),
            features.get("crest_factor_current", 2.6),
            features.get("temp_current", 54.0),
            features.get("temp_rate_of_rise_c_per_hour", 0.0),
            features.get("current_thd", 1.8)
        ]], dtype=np.float64)

        vec_scaled = self.scaler.transform(raw_vec)
        # IsolationForest decision_function outputs negative scores for anomalies
        raw_score = self.model.decision_function(vec_scaled)[0]

        # Map to [0.0, 1.0] sigmoid/min-max range
        # Typical raw_score is in [-0.35, +0.25]
        normalized_score = 1.0 / (1.0 + np.exp((raw_score + 0.05) * 8.0))
        return round(float(np.clip(normalized_score, 0.0, 1.0)), 3)
