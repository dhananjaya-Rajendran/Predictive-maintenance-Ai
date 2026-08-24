"""
Unit Tests for FastAPI REST Endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from run_server import app

client = TestClient(app)


def test_dashboard_summary_endpoint():
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["plant_code"] == "PLANT-DETROIT-01"
    assert data["monitored_assets_total"] >= 10
    assert "risk_breakdown" in data
    assert data["overall_plant_health_index"] > 0


def test_machines_list_endpoint():
    response = client.get("/api/v1/machines")
    assert response.status_code == 200
    machines = response.json()
    assert len(machines) >= 10
    # Check sorted descending by composite risk
    scores = [m["composite_risk_score"] for m in machines]
    assert scores == sorted(scores, reverse=True)


def test_machine_health_endpoint():
    response = client.get("/api/v1/machines/m-stamp-04/health")
    assert response.status_code == 200
    data = response.json()
    assert data["asset_tag"] == "STAMP-P04-5000T"
    assert "prediction" in data
    assert len(data["sensors"]) >= 4


def test_agent_query_endpoint():
    response = client.post("/api/v1/agent/query", json={
        "user_message": "Give me an overview of highest risk machines",
        "machine_id": None
    })
    assert response.status_code == 200
    data = response.json()
    assert data["response_type"] == "PLANT_OVERVIEW"
    assert len(data["message"]) > 20


def test_feedback_submission():
    response = client.post("/api/v1/predictions/pred-123/feedback", json={
        "user_id": "u-test-engineer",
        "outcome_classification": "TRUE_POSITIVE_PREVENTED",
        "root_cause": "BEARING_INNER_RACE_WEAR",
        "notes": "Verified on shop floor with acoustic strobe"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FEEDBACK_RECORDED"


def test_anomaly_injection_and_clear():
    # Inject fault
    inject_res = client.post("/api/v1/simulator/inject_anomaly", json={
        "machine_id": "m-stamp-02",
        "failure_mode": "BEARING_INNER_RACE",
        "severity": 0.88,
        "rate_per_hour": 0.02
    })
    assert inject_res.status_code == 200

    # Clear fault
    clear_res = client.post("/api/v1/simulator/clear_fault/m-stamp-02")
    assert clear_res.status_code == 200
