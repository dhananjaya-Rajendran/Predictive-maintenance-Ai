"""
Pydantic v2 Schemas for Request and Response Validation.
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional


class FeatureAttribution(BaseModel):
    feature_key: str
    feature_name: str
    current_value: float
    healthy_baseline: float
    unit: str
    shap_importance_percent: float
    diagnostic_note: str


class PredictionResponse(BaseModel):
    machine_id: str
    failure_probability: float
    predicted_horizon_hours: float
    confidence_score: float
    composite_risk_score: float
    risk_tier: str
    stage1_anomaly_score: float
    top_contributing_features: List[FeatureAttribution]
    model_version: str


class SensorSummaryItem(BaseModel):
    sensor_key: str
    sensor_name: str
    latest_value: float
    unit: str
    status: str
    warning_threshold: float
    critical_threshold: float


class MachineHealthResponse(BaseModel):
    machine_id: str
    asset_tag: str
    name: str
    shop: str
    criticality: str
    operational_status: str
    composite_risk_score: float
    risk_tier: str
    prediction: PredictionResponse
    sensors: List[SensorSummaryItem]


class MachineListItem(BaseModel):
    machine_id: str
    asset_tag: str
    name: str
    shop: str
    criticality: str
    operational_status: str
    composite_risk_score: float
    risk_tier: str
    failure_probability: float
    predicted_horizon_hours: float


class DashboardSummaryResponse(BaseModel):
    plant_code: str
    generated_at_iso: str
    overall_plant_health_index: float
    monitored_assets_total: int
    risk_breakdown: Dict[str, int]
    downtime_avoided_hours_mtd: float
    estimated_cost_saved_usd: float
    prediction_accuracy_percentage: float
    critical_alerts: List[Dict[str, Any]]


class FeedbackRequest(BaseModel):
    user_id: str
    outcome_classification: str = Field(..., description="TRUE_POSITIVE_PREVENTED, FALSE_POSITIVE, NORMAL_PROCESS")
    root_cause: Optional[str] = None
    work_order_reference: Optional[str] = None
    notes: Optional[str] = None


class AgentQueryRequest(BaseModel):
    user_message: str
    machine_id: Optional[str] = None


class AnomalyInjectionRequest(BaseModel):
    machine_id: str
    failure_mode: str = Field(..., description="BEARING_INNER_RACE, LUBRICATION_STARVATION, STATOR_WINDING_FAULT, MECHANICAL_LOOSENESS")
    severity: float = Field(0.75, ge=0.0, le=1.0)
    rate_per_hour: float = Field(0.01, ge=0.0, le=0.1)
