"""
Configuration and domain constants for AutoPredict AI Automotive Platform.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any


class ShopType(str, Enum):
    STAMPING = "STAMPING"
    BIW = "BIW"  # Body-in-White
    PAINT = "PAINT"
    POWERTRAIN = "POWERTRAIN"
    ASSEMBLY = "ASSEMBLY"


class CriticalityTier(str, Enum):
    TIER_1_BOTTLENECK = "TIER_1_BOTTLENECK"  # Line halting bottleneck ($50k/min)
    TIER_2_MAJOR = "TIER_2_MAJOR"            # Major sub-assembly ($15k/min)
    TIER_3_BUFFER = "TIER_3_BUFFER"          # Redundant/Buffer asset ($3k/min)


class RiskTier(str, Enum):
    CRITICAL = "CRITICAL"    # Score >= 0.75 (Action window 24-48h)
    WARNING = "WARNING"      # Score 0.50 - 0.74 (Action window 48-72h)
    WATCH = "WATCH"          # Score 0.30 - 0.49 (Incipient anomaly)
    HEALTHY = "HEALTHY"      # Score < 0.30 (Normal baseline)


class FailureMode(str, Enum):
    BEARING_INNER_RACE = "BEARING_INNER_RACE"        # BPFI signature, high Kurtosis
    BEARING_OUTER_RACE = "BEARING_OUTER_RACE"        # BPFO signature
    LUBRICATION_STARVATION = "LUBRICATION_STARVATION"  # High friction, thermal dT/dt rise
    STATOR_WINDING_FAULT = "STATOR_WINDING_FAULT"    # Current THD spike, phase unbalance
    MECHANICAL_LOOSENESS = "MECHANICAL_LOOSENESS"    # 1X/2X harmonics, peak-to-peak rise
    NORMAL_OPERATION = "NORMAL_OPERATION"


@dataclass
class PlatformConfig:
    # Target prediction window
    MIN_PREDICTION_HORIZON_HOURS: float = 24.0
    MAX_PREDICTION_HORIZON_HOURS: float = 72.0

    # Risk Calculation Weights
    WEIGHT_FAILURE_PROBABILITY: float = 0.60
    WEIGHT_CRITICALITY_TIER: float = 0.25
    WEIGHT_DEGRADATION_VELOCITY: float = 0.15

    # Criticality tier numerical weights
    CRITICALITY_WEIGHTS: Dict[str, float] = None

    # Thresholds for Risk Classification
    RISK_CRITICAL_THRESHOLD: float = 0.75
    RISK_WARNING_THRESHOLD: float = 0.50
    RISK_WATCH_THRESHOLD: float = 0.30

    # ISO 10816 Vibration Velocity (mm/s RMS) Limits for Class III/IV heavy industrial machinery
    ISO_VIBRATION_GOOD: float = 2.80
    ISO_VIBRATION_ACCEPTABLE: float = 4.50
    ISO_VIBRATION_WARNING: float = 7.10
    ISO_VIBRATION_CRITICAL: float = 11.20

    # Stator temperature limits (deg C)
    TEMP_NORMAL_MAX: float = 75.0
    TEMP_WARNING: float = 85.0
    TEMP_CRITICAL: float = 98.0

    # Bearing geometry parameters for 6205/6312 standard automotive industrial bearings
    DEFAULT_ROLLER_COUNT: int = 9
    DEFAULT_ROLLER_DIAMETER_MM: float = 7.94
    DEFAULT_PITCH_DIAMETER_MM: float = 38.5
    DEFAULT_CONTACT_ANGLE_DEG: float = 0.0

    # Plant Downtime Cost Model ($/minute)
    DOWNTIME_COST_PER_MINUTE: Dict[str, float] = None

    def __post_init__(self):
        if self.CRITICALITY_WEIGHTS is None:
            self.CRITICALITY_WEIGHTS = {
                CriticalityTier.TIER_1_BOTTLENECK.value: 1.0,
                CriticalityTier.TIER_2_MAJOR.value: 0.65,
                CriticalityTier.TIER_3_BUFFER.value: 0.30,
            }
        if self.DOWNTIME_COST_PER_MINUTE is None:
            self.DOWNTIME_COST_PER_MINUTE = {
                CriticalityTier.TIER_1_BOTTLENECK.value: 50000.0,
                CriticalityTier.TIER_2_MAJOR.value: 15000.0,
                CriticalityTier.TIER_3_BUFFER.value: 3000.0,
            }


CONFIG = PlatformConfig()
