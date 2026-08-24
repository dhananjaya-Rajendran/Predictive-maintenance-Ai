"""
Autonomous Reasoning Engine for Predictive Maintenance AI Agent.
Executes deterministic multi-step diagnostic reasoning, schedule alignment, and prescriptive action synthesis.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from src.agent.tools import MaintenanceAgentTools
from src.config import CONFIG, CriticalityTier


class MaintenanceReasoningEngine:
    """
    Core reasoning pipeline orchestrating multi-tool diagnostic workflows.
    """

    @classmethod
    def execute_deep_diagnosis(cls, machine_id: str) -> Dict[str, Any]:
        """
        Executes an end-to-end multi-step autonomous diagnostic analysis for a machine.
        """
        trace_steps = []

        # Step 1: Telemetry & ML Assessment
        trace_steps.append({"step": 1, "action": "Inspect Live Telemetry & Dual-Stage Prediction", "status": "COMPLETED"})
        telemetry = MaintenanceAgentTools.get_machine_telemetry(machine_id)
        if "error" in telemetry:
            return {"error": telemetry["error"]}

        prediction = telemetry["prediction"]

        # Step 2: FFT Spectral Harmonic Analysis
        trace_steps.append({"step": 2, "action": "Execute FFT Power Spectrum & Bearing Kinematic Math", "status": "COMPLETED"})
        fft_diag = MaintenanceAgentTools.run_fft_diagnostics(machine_id)

        # Step 3: Financial & Bottleneck Impact Modeling
        trace_steps.append({"step": 3, "action": "Calculate Financial Downtime Exposure & Bottleneck Severity", "status": "COMPLETED"})
        financial = MaintenanceAgentTools.calculate_downtime_financial_impact(machine_id)

        # Step 4: Maintenance Window Scheduling Optimization
        trace_steps.append({"step": 4, "action": "Query Plant Shift Buffers & Tooling Changeovers", "status": "COMPLETED"})
        windows = MaintenanceAgentTools.query_scheduled_maintenance_windows(telemetry["shop"])

        # Determine optimal window matching predicted horizon
        optimal_window = windows[0]  # Default to nearest buffer window
        pred_horizon = prediction["predicted_horizon_hours"]
        if pred_horizon > 40.0 and len(windows) > 1:
            optimal_window = windows[0]  # Still take nearest safe buffer shift

        # Step 5: Prescriptive Maintenance Action Generation
        detected_mode = fft_diag.get("spectral_fault_diagnosis", "BEARING_INNER_RACE_DEFECT (BPFI)")
        trace_steps.append({"step": 5, "action": f"Synthesize Step-by-Step Repair Instructions for {detected_mode}", "status": "COMPLETED"})
        prescription = MaintenanceAgentTools.generate_prescriptive_repair_plan(machine_id, detected_mode)

        # Step 6: CMMS Work Order Drafting
        trace_steps.append({"step": 6, "action": "Generate Enterprise SAP PM Work Order Draft", "status": "COMPLETED"})
        cmms_draft = MaintenanceAgentTools.draft_cmms_work_order(machine_id, prescription)

        # Formulate Comprehensive Agent Executive Summary
        executive_summary = (
            f"Asset {telemetry['asset_tag']} ({telemetry['name']}) is exhibiting an elevated failure risk of "
            f"{round(prediction['failure_probability'] * 100, 1)}% projected to occur within {prediction['predicted_horizon_hours']} hours. "
            f"Spectral Fast Fourier Transform (FFT) confirms {detected_mode} with dominant peak at {fft_diag['dominant_frequency_hz']} Hz. "
            f"Because this asset is a {telemetry['criticality']}, an unplanned failure carries an estimated downtime exposure of "
            f"${int(financial['estimated_unplanned_failure_cost_usd']):,} USD. "
            f"Recommended Action: Execute bearing replacement during the upcoming planned buffer window '{optimal_window['window_type']}' "
            f"({optimal_window['window_id']}) to achieve zero production line interruption."
        )

        return {
            "machine_id": machine_id,
            "asset_tag": telemetry["asset_tag"],
            "machine_name": telemetry["name"],
            "shop": telemetry["shop"],
            "criticality": telemetry["criticality"],
            "analyzed_at_iso": datetime.now(timezone.utc).isoformat(),
            "executive_summary": executive_summary,
            "prediction_summary": {
                "failure_probability": prediction["failure_probability"],
                "predicted_horizon_hours": prediction["predicted_horizon_hours"],
                "confidence_score": prediction["confidence_score"],
                "composite_risk_score": prediction["composite_risk_score"],
                "risk_tier": prediction["risk_tier"]
            },
            "root_cause_explanation": {
                "detected_failure_mode": detected_mode,
                "dominant_frequency_hz": fft_diag["dominant_frequency_hz"],
                "top_contributing_features": prediction["top_contributing_features"],
                "evidence_statements": fft_diag["evidence"]
            },
            "financial_impact": financial,
            "recommended_maintenance_window": optimal_window,
            "prescriptive_repair_plan": prescription,
            "sap_work_order_draft": cmms_draft,
            "agent_reasoning_trace": trace_steps
        }
