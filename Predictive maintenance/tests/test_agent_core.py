"""
Unit Tests for AI Maintenance Agent, Diagnostic Reasoning, and Copilot.
"""
import pytest
from src.agent.tools import MaintenanceAgentTools
from src.agent.reasoning_engine import MaintenanceReasoningEngine
from src.agent.copilot import MaintenanceCopilot


def test_agent_telemetry_tool():
    telemetry = MaintenanceAgentTools.get_machine_telemetry("m-stamp-04")
    assert telemetry["machine_id"] == "m-stamp-04"
    assert "live_sensors" in telemetry
    assert "prediction" in telemetry


def test_agent_fft_diagnostics_tool():
    fft_diag = MaintenanceAgentTools.run_fft_diagnostics("m-stamp-04")
    assert "dominant_frequency_hz" in fft_diag
    assert "spectral_fault_diagnosis" in fft_diag
    assert "evidence" in fft_diag


def test_reasoning_engine_deep_diagnosis():
    diag = MaintenanceReasoningEngine.execute_deep_diagnosis("m-stamp-04")
    assert diag["machine_id"] == "m-stamp-04"
    assert "executive_summary" in diag
    assert "prescriptive_repair_plan" in diag
    assert "sap_work_order_draft" in diag
    assert len(diag["agent_reasoning_trace"]) >= 5


def test_copilot_conversational_queries():
    # Test plant overview intent
    res_overview = MaintenanceCopilot.process_query("Give me an overview of highest risk machines")
    assert res_overview["response_type"] == "PLANT_OVERVIEW"
    assert "Plant Status Overview" in res_overview["message"]

    # Test specific asset diagnosis
    res_diag = MaintenanceCopilot.process_query("What is wrong with Stamping Press 04?", current_machine_id="m-stamp-04")
    assert res_diag["response_type"] == "ASSET_DIAGNOSIS"
    assert "STAMP-P04" in res_diag["message"]
