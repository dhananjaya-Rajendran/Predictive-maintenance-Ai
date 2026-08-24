"""
In-Memory Store for Telemetry, Prediction Audit Trails, and Feedback Records.
Provides thread-safe persistence and querying for the platform.
"""
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone


class MemoryStore:
    """
    In-memory operational repository.
    """

    def __init__(self):
        self.prediction_history: List[Dict[str, Any]] = []
        self.feedback_records: List[Dict[str, Any]] = []
        self._initialize_sample_history()

    def _initialize_sample_history(self):
        """
        Seeds realistic historical prediction audit records.
        """
        now = datetime.now(timezone.utc)
        self.prediction_history.extend([
            {
                "id": str(uuid.uuid4()),
                "machine_id": "m-stamp-04",
                "asset_tag": "STAMP-P04-5000T",
                "machine_name": "Stamping Press 04 Main Drive",
                "shop": "STAMPING",
                "predicted_at": (now).isoformat(),
                "failure_probability": 0.915,
                "predicted_horizon_hours": 48.5,
                "confidence_score": 0.94,
                "risk_tier": "CRITICAL",
                "primary_failure_mode": "Bearing Inner Race Wear (BPFI)",
                "status": "ACTIVE_UNRESOLVED"
            },
            {
                "id": str(uuid.uuid4()),
                "machine_id": "m-biw-08",
                "asset_tag": "BIW-R08-FRM",
                "machine_name": "Framing Robot 08 Servo Axis 3",
                "shop": "BIW",
                "predicted_at": (now).isoformat(),
                "failure_probability": 0.882,
                "predicted_horizon_hours": 31.0,
                "confidence_score": 0.91,
                "risk_tier": "CRITICAL",
                "primary_failure_mode": "Gearbox Lubrication Starvation",
                "status": "ACTIVE_UNRESOLVED"
            },
            {
                "id": str(uuid.uuid4()),
                "machine_id": "m-pwt-14",
                "asset_tag": "PWT-CNC-14",
                "machine_name": "Cylinder Block 5-Axis Milling Spindle",
                "shop": "POWERTRAIN",
                "predicted_at": (now).isoformat(),
                "failure_probability": 0.820,
                "predicted_horizon_hours": 62.0,
                "confidence_score": 0.89,
                "risk_tier": "CRITICAL",
                "primary_failure_mode": "Stator Winding Thermal Runaway",
                "status": "ACTIVE_UNRESOLVED"
            }
        ])

    def record_prediction(self, prediction_payload: Dict[str, Any]) -> str:
        pred_id = str(uuid.uuid4())
        record = {
            "id": pred_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            **prediction_payload
        }
        self.prediction_history.append(record)
        return pred_id

    def record_feedback(
        self,
        prediction_id: str,
        user_id: str,
        outcome_classification: str,
        root_cause: Optional[str] = None,
        work_order_reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        feedback_id = str(uuid.uuid4())
        record = {
            "feedback_id": feedback_id,
            "prediction_id": prediction_id,
            "user_id": user_id,
            "outcome_classification": outcome_classification,
            "root_cause": root_cause or "UNSPECIFIED",
            "work_order_reference": work_order_reference or "N/A",
            "notes": notes or "",
            "submitted_at": datetime.now(timezone.utc).isoformat()
        }
        self.feedback_records.append(record)

        # Mark prediction status as reviewed
        for p in self.prediction_history:
            if p.get("id") == prediction_id:
                p["status"] = f"RESOLVED_{outcome_classification}"

        return record

    def get_prediction_history(self, machine_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if machine_id:
            filtered = [p for p in self.prediction_history if p.get("machine_id") == machine_id]
            return filtered[-limit:]
        return self.prediction_history[-limit:]

    def get_feedback_records(self) -> List[Dict[str, Any]]:
        return self.feedback_records


MEMORY_STORE = MemoryStore()
