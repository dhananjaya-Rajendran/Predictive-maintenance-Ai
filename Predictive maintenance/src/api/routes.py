"""
FastAPI REST Routing Module for AutoPredict AI Platform.
"""
from fastapi import APIRouter, HTTPException, Query, Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from src.config import CONFIG, ShopType, CriticalityTier, RiskTier, FailureMode
from src.engine.simulator import PLANT_SIMULATOR
from src.engine.signal_processor import SignalProcessor
from src.ml.predictor import PREDICTION_ENGINE
from src.ml.model_registry import MODEL_REGISTRY
from src.storage.memory_store import MEMORY_STORE
from src.agent.copilot import MaintenanceCopilot
from src.agent.reasoning_engine import MaintenanceReasoningEngine
from src.agent.tools import MaintenanceAgentTools
from src.api.schemas import (
    DashboardSummaryResponse,
    MachineListItem,
    MachineHealthResponse,
    PredictionResponse,
    FeedbackRequest,
    AgentQueryRequest,
    AnomalyInjectionRequest
)

router = APIRouter(prefix="/api/v1")


@router.get("/dashboard/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary():
    """
    Returns executive summary metrics, Plant Health Index, and active critical alerts.
    """
    monitored_assets = list(PLANT_SIMULATOR.machines.values())
    risk_counts = {"CRITICAL": 0, "WARNING": 0, "WATCH": 0, "HEALTHY": 0}
    critical_alerts = []
    health_scores = []

    for m in monitored_assets:
        agg = m.buffer.get_aggregated_features()
        pred = PREDICTION_ENGINE.predict(m.machine_id, agg, m.criticality.value)
        tier = pred["risk_tier"]
        risk_counts[tier] = risk_counts.get(tier, 0) + 1

        # Individual asset health score: 100 - (Composite Risk * 100)
        asset_health = max(0.0, 100.0 - (pred["composite_risk_score"] * 100.0))
        health_scores.append(asset_health)

        if tier == "CRITICAL":
            critical_alerts.append({
                "machine_id": m.machine_id,
                "asset_tag": m.asset_tag,
                "machine_name": m.name,
                "shop": m.shop.value,
                "criticality_tier": m.criticality.value,
                "failure_probability": pred["failure_probability"],
                "predicted_horizon_hours": pred["predicted_horizon_hours"],
                "composite_risk_score": pred["composite_risk_score"],
                "primary_failure_mode": m.failure_mode.value,
                "risk_tier": "CRITICAL"
            })

    # Sort critical alerts descending by composite risk
    critical_alerts.sort(key=lambda x: x["composite_risk_score"], reverse=True)
    overall_health = round(float(sum(health_scores) / len(health_scores)), 1) if health_scores else 85.0

    return DashboardSummaryResponse(
        plant_code="PLANT-DETROIT-01",
        generated_at_iso=datetime.now(timezone.utc).isoformat(),
        overall_plant_health_index=overall_health,
        monitored_assets_total=len(monitored_assets),
        risk_breakdown=risk_counts,
        downtime_avoided_hours_mtd=38.5,
        estimated_cost_saved_usd=1925000.0,
        prediction_accuracy_percentage=94.2,
        critical_alerts=critical_alerts
    )


@router.get("/machines", response_model=List[MachineListItem])
async def list_machines(
    shop: Optional[str] = Query(None, description="Filter by shop type"),
    risk_tier: Optional[str] = Query(None, description="Filter by risk tier")
):
    """
    Returns all monitored machines sorted by Composite Risk Score descending.
    """
    items = []
    for m in PLANT_SIMULATOR.machines.values():
        if shop and shop.upper() != "ALL" and m.shop.value != shop.upper():
            continue

        agg = m.buffer.get_aggregated_features()
        pred = PREDICTION_ENGINE.predict(m.machine_id, agg, m.criticality.value)

        if risk_tier and risk_tier.upper() != "ALL" and pred["risk_tier"] != risk_tier.upper():
            continue

        items.append(MachineListItem(
            machine_id=m.machine_id,
            asset_tag=m.asset_tag,
            name=m.name,
            shop=m.shop.value,
            criticality=m.criticality.value,
            operational_status=m.operational_status,
            composite_risk_score=pred["composite_risk_score"],
            risk_tier=pred["risk_tier"],
            failure_probability=pred["failure_probability"],
            predicted_horizon_hours=pred["predicted_horizon_hours"]
        ))

    items.sort(key=lambda x: x.composite_risk_score, reverse=True)
    return items


@router.get("/machines/{machine_id}/health", response_model=MachineHealthResponse)
async def get_machine_health(machine_id: str = Path(...)):
    """
    Returns detailed condition monitoring telemetry and active prediction for a machine.
    """
    if machine_id not in PLANT_SIMULATOR.machines:
        raise HTTPException(status_code=404, detail="Machine not found")

    m = PLANT_SIMULATOR.machines[machine_id]
    agg = m.buffer.get_aggregated_features()
    pred = PREDICTION_ENGINE.predict(machine_id, agg, m.criticality.value)

    # Compile sensors summary list
    sensors = [
        {
            "sensor_key": "vibration_de_rms",
            "sensor_name": "Drive End Vibration (RMS)",
            "latest_value": agg["vib_rms_current"],
            "unit": "mm/s RMS",
            "status": "ALARM_HIGH" if agg["vib_rms_current"] >= CONFIG.ISO_VIBRATION_WARNING else "NORMAL",
            "warning_threshold": CONFIG.ISO_VIBRATION_ACCEPTABLE,
            "critical_threshold": CONFIG.ISO_VIBRATION_WARNING
        },
        {
            "sensor_key": "vibration_kurtosis",
            "sensor_name": "Vibration Kurtosis (Impact Shocks)",
            "latest_value": agg["kurtosis_current"],
            "unit": "Kurtosis",
            "status": "ALARM_HIGH" if agg["kurtosis_current"] >= 4.5 else "NORMAL",
            "warning_threshold": 3.8,
            "critical_threshold": 5.0
        },
        {
            "sensor_key": "stator_temperature",
            "sensor_name": "Stator Winding Temperature",
            "latest_value": agg["temp_current"],
            "unit": "°C",
            "status": "ALARM_HIGH" if agg["temp_current"] >= CONFIG.TEMP_WARNING else "NORMAL",
            "warning_threshold": CONFIG.TEMP_NORMAL_MAX,
            "critical_threshold": CONFIG.TEMP_WARNING
        },
        {
            "sensor_key": "motor_current",
            "sensor_name": "Motor Phase Current",
            "latest_value": agg["current_rms"],
            "unit": "A",
            "status": "NORMAL",
            "warning_threshold": m.nominal_current * 1.25,
            "critical_threshold": m.nominal_current * 1.40
        },
        {
            "sensor_key": "current_thd",
            "sensor_name": "Current Total Harmonic Distortion",
            "latest_value": agg["current_thd"],
            "unit": "%",
            "status": "ALARM_HIGH" if agg["current_thd"] >= 6.0 else "NORMAL",
            "warning_threshold": 4.0,
            "critical_threshold": 7.0
        }
    ]

    return MachineHealthResponse(
        machine_id=m.machine_id,
        asset_tag=m.asset_tag,
        name=m.name,
        shop=m.shop.value,
        criticality=m.criticality.value,
        operational_status=m.operational_status,
        composite_risk_score=pred["composite_risk_score"],
        risk_tier=pred["risk_tier"],
        prediction=PredictionResponse(**pred),
        sensors=sensors
    )


@router.get("/machines/{machine_id}/telemetry")
async def get_machine_telemetry_history(machine_id: str = Path(...)):
    """
    Returns time-series telemetry series for 7-day or 72-hour chart plotting.
    """
    if machine_id not in PLANT_SIMULATOR.machines:
        raise HTTPException(status_code=404, detail="Machine not found")

    m = PLANT_SIMULATOR.machines[machine_id]
    buf = m.buffer

    return {
        "machine_id": machine_id,
        "asset_tag": m.asset_tag,
        "timestamps": list(buf.timestamps),
        "vibration_rms": list(buf.vibration_de_rms),
        "vibration_kurtosis": list(buf.vibration_kurtosis),
        "vibration_crest_factor": list(buf.vibration_crest_factor),
        "temperature_c": list(buf.stator_temp_c),
        "current_a": list(buf.motor_current_a),
        "rpm": list(buf.rpm),
        "current_thd": list(buf.current_thd)
    }


@router.get("/machines/{machine_id}/fft")
async def get_machine_fft(machine_id: str = Path(...)):
    """
    Returns high-resolution FFT frequency spectrum and bearing kinematic markers.
    """
    if machine_id not in PLANT_SIMULATOR.machines:
        raise HTTPException(status_code=404, detail="Machine not found")

    m = PLANT_SIMULATOR.machines[machine_id]
    waveform = m.generate_high_frequency_waveform(sample_rate_hz=4000.0, duration_sec=0.5)
    freqs, amps, metrics = SignalProcessor.compute_fft_spectrum(waveform, sample_rate_hz=4000.0)
    kinematics = SignalProcessor.calculate_bearing_fault_frequencies(m.nominal_rpm)

    # Subsample to 500 bins for performant browser rendering
    step = max(1, len(freqs) // 500)
    freq_list = [round(float(f), 1) for f in freqs[::step]]
    amp_list = [round(float(a), 4) for a in amps[::step]]

    return {
        "machine_id": machine_id,
        "asset_tag": m.asset_tag,
        "frequencies_hz": freq_list,
        "amplitudes": amp_list,
        "spectral_metrics": metrics,
        "bearing_kinematic_markers": kinematics
    }


@router.post("/agent/query")
async def query_ai_agent(request: AgentQueryRequest):
    """
    Processes natural language conversational inquiry with the AI Maintenance Copilot.
    """
    response = MaintenanceCopilot.process_query(
        user_message=request.user_message,
        current_machine_id=request.machine_id
    )
    return response


@router.post("/agent/diagnose/{machine_id}")
async def run_autonomous_diagnosis(machine_id: str = Path(...)):
    """
    Executes full multi-step reasoning diagnosis for a specific machine.
    """
    diag = MaintenanceReasoningEngine.execute_deep_diagnosis(machine_id)
    if "error" in diag:
        raise HTTPException(status_code=404, detail=diag["error"])
    return diag


@router.post("/agent/prescribe/{machine_id}")
async def generate_prescription(machine_id: str = Path(...)):
    """
    Generates prescriptive repair plan and drafts SAP PM work order.
    """
    diag = MaintenanceReasoningEngine.execute_deep_diagnosis(machine_id)
    if "error" in diag:
        raise HTTPException(status_code=404, detail=diag["error"])
    return {
        "prescriptive_repair_plan": diag["prescriptive_repair_plan"],
        "recommended_window": diag["recommended_maintenance_window"],
        "sap_work_order_draft": diag["sap_work_order_draft"]
    }


@router.post("/predictions/{prediction_id}/feedback")
async def record_prediction_feedback(prediction_id: str, request: FeedbackRequest):
    """
    Records engineering ground-truth feedback for model retraining.
    """
    record = MEMORY_STORE.record_feedback(
        prediction_id=prediction_id,
        user_id=request.user_id,
        outcome_classification=request.outcome_classification,
        root_cause=request.root_cause,
        work_order_reference=request.work_order_reference,
        notes=request.notes
    )
    return {"status": "FEEDBACK_RECORDED", "feedback": record}


@router.get("/predictions/history")
async def get_prediction_history(machine_id: Optional[str] = None):
    """
    Returns audit log of generated predictions.
    """
    return MEMORY_STORE.get_prediction_history(machine_id=machine_id)


@router.post("/simulator/inject_anomaly")
async def inject_simulated_anomaly(request: AnomalyInjectionRequest):
    """
    Interactive test tool: Injects a physical defect into a machine at runtime.
    """
    try:
        f_mode = FailureMode(request.failure_mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid failure mode: {request.failure_mode}")

    success = PLANT_SIMULATOR.inject_fault(
        machine_id=request.machine_id,
        mode=f_mode,
        severity=request.severity,
        rate_per_hour=request.rate_per_hour
    )
    if not success:
        raise HTTPException(status_code=404, detail="Machine not found")

    return {
        "status": "ANOMALY_INJECTED",
        "machine_id": request.machine_id,
        "failure_mode": request.failure_mode,
        "severity": request.severity
    }


@router.post("/simulator/clear_fault/{machine_id}")
async def clear_simulated_fault(machine_id: str = Path(...)):
    """
    Resets a machine to normal healthy baseline.
    """
    success = PLANT_SIMULATOR.clear_fault(machine_id)
    if not success:
        raise HTTPException(status_code=404, detail="Machine not found")
    return {"status": "FAULT_CLEARED", "machine_id": machine_id}


@router.get("/model/info")
async def get_model_info():
    """
    Returns active ML model metadata, benchmarks, and population drift metrics.
    """
    return MODEL_REGISTRY.get_model_info()
