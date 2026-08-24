"""
Industrial Tool Suite for the AI Maintenance Agent.
Gives the agent capabilities to inspect telemetry, run FFT diagnostics, query plant schedules, and draft CMMS plans.
"""
import random
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
from src.config import CONFIG, CriticalityTier, ShopType, FailureMode
from src.engine.simulator import PLANT_SIMULATOR
from src.engine.signal_processor import SignalProcessor
from src.ml.predictor import PREDICTION_ENGINE


class MaintenanceAgentTools:
    """
    Collection of deterministic industrial domain tools for the AI Agent.
    """

    @staticmethod
    def get_machine_telemetry(machine_id: str) -> Dict[str, Any]:
        """
        Retrieves real-time sensor metrics and sliding window statistics for a machine.
        """
        if machine_id not in PLANT_SIMULATOR.machines:
            return {"error": f"Machine ID '{machine_id}' not found."}

        m = PLANT_SIMULATOR.machines[machine_id]
        agg = m.buffer.get_aggregated_features()
        prediction = PREDICTION_ENGINE.predict(machine_id, agg, m.criticality.value)

        return {
            "machine_id": m.machine_id,
            "asset_tag": m.asset_tag,
            "name": m.name,
            "shop": m.shop.value,
            "criticality": m.criticality.value,
            "operational_status": m.operational_status,
            "bearing_type": m.bearing_type,
            "live_sensors": {
                "vibration_rms_mm_s": agg["vib_rms_current"],
                "vibration_kurtosis": agg["kurtosis_current"],
                "vibration_crest_factor": agg["crest_factor_current"],
                "temperature_celsius": agg["temp_current"],
                "temp_rate_of_rise_c_per_hour": agg["temp_rate_of_rise_c_per_hour"],
                "motor_current_amperes": agg["current_rms"],
                "current_thd_percent": agg["current_thd"],
                "rpm": agg["rpm"],
                "hydraulic_pressure_bar": agg["hydraulic_pressure"]
            },
            "iso_vibration_status": "CRITICAL_UNACCEPTABLE" if agg["vib_rms_current"] >= CONFIG.ISO_VIBRATION_WARNING else "NORMAL_GOOD",
            "prediction": prediction
        }

    @staticmethod
    def run_fft_diagnostics(machine_id: str) -> Dict[str, Any]:
        """
        Executes Fast Fourier Transform (FFT) on current vibration waveform, identifying harmonic and bearing peaks.
        """
        if machine_id not in PLANT_SIMULATOR.machines:
            return {"error": f"Machine ID '{machine_id}' not found."}

        m = PLANT_SIMULATOR.machines[machine_id]
        waveform = m.generate_high_frequency_waveform(sample_rate_hz=4000.0, duration_sec=0.5)
        freqs, amps, metrics = SignalProcessor.compute_fft_spectrum(waveform, sample_rate_hz=4000.0)
        bearing_freqs = SignalProcessor.calculate_bearing_fault_frequencies(m.nominal_rpm)

        # Detect closest bearing frequency match to the dominant peak
        dominant_freq = metrics["peak_frequency_hz"]
        detected_fault = "NONE_NORMAL"
        fault_evidence = []

        bpfi = bearing_freqs["bpfi_inner_race_hz"]
        bpfo = bearing_freqs["bpfo_outer_race_hz"]
        f1 = bearing_freqs["shaft_rotational_1x_hz"]
        f2 = bearing_freqs["shaft_rotational_2x_hz"]

        if abs(dominant_freq - bpfi) < 12.0:
            detected_fault = "BEARING_INNER_RACE_DEFECT (BPFI)"
            fault_evidence.append(f"Dominant spectral peak at {dominant_freq} Hz matches theoretical BPFI ({bpfi} Hz ± 5%).")
        elif abs(dominant_freq - bpfo) < 10.0:
            detected_fault = "BEARING_OUTER_RACE_DEFECT (BPFO)"
            fault_evidence.append(f"Dominant spectral peak at {dominant_freq} Hz matches theoretical BPFO ({bpfo} Hz ± 5%).")
        elif abs(dominant_freq - f2) < 5.0:
            detected_fault = "MECHANICAL_LOOSENESS_OR_MISALIGNMENT"
            fault_evidence.append(f"Dominant peak at 2X shaft rotational harmonic ({f2} Hz).")
        elif metrics["spectral_energy_high_hz"] > 15.0:
            detected_fault = "LUBRICATION_BREAKDOWN_FRICTION"
            fault_evidence.append("Elevated high-frequency broadband friction energy (> 1000 Hz).")

        return {
            "machine_id": machine_id,
            "asset_tag": m.asset_tag,
            "dominant_frequency_hz": dominant_freq,
            "dominant_amplitude": metrics["peak_amplitude"],
            "bearing_fault_kinematics": bearing_freqs,
            "spectral_energy_distribution": {
                "low_band_0_100hz": metrics["spectral_energy_low_hz"],
                "mid_band_100_1000hz": metrics["spectral_energy_mid_hz"],
                "high_band_1000_10000hz": metrics["spectral_energy_high_hz"]
            },
            "spectral_fault_diagnosis": detected_fault,
            "evidence": fault_evidence
        }

    @staticmethod
    def calculate_downtime_financial_impact(machine_id: str) -> Dict[str, Any]:
        """
        Calculates production line downtime cost rate, bottleneck status, and risk impact.
        """
        if machine_id not in PLANT_SIMULATOR.machines:
            return {"error": f"Machine ID '{machine_id}' not found."}

        m = PLANT_SIMULATOR.machines[machine_id]
        cost_per_min = CONFIG.DOWNTIME_COST_PER_MINUTE.get(m.criticality.value, 15000.0)

        # 4-hour typical unplanned catastrophic repair vs 1-hour planned repair
        unplanned_downtime_min = 240.0
        planned_downtime_min = 60.0

        unplanned_cost = unplanned_downtime_min * cost_per_min
        planned_cost = planned_downtime_min * (cost_per_min * 0.15)  # performed during buffer/changeover
        potential_savings = unplanned_cost - planned_cost

        return {
            "machine_id": machine_id,
            "asset_tag": m.asset_tag,
            "shop": m.shop.value,
            "criticality_tier": m.criticality.value,
            "is_bottleneck": m.criticality == CriticalityTier.TIER_1_BOTTLENECK,
            "downtime_cost_per_minute_usd": cost_per_min,
            "estimated_unplanned_failure_cost_usd": unplanned_cost,
            "estimated_planned_intervention_cost_usd": planned_cost,
            "net_roi_savings_usd": potential_savings,
            "financial_urgency": "EXTREME_BOTTLENECK" if m.criticality == CriticalityTier.TIER_1_BOTTLENECK else "MODERATE"
        }

    @staticmethod
    def query_scheduled_maintenance_windows(shop: str) -> List[Dict[str, Any]]:
        """
        Returns upcoming scheduled non-production windows and shift changeovers in the next 72 hours.
        """
        now = datetime.now(timezone.utc)
        windows = [
            {
                "window_id": "WIN-TONIGHT-01",
                "shop": shop,
                "window_type": "Night Tooling & Die Changeover (Shift 3 Buffer)",
                "start_time_iso": (now + timedelta(hours=6.5)).isoformat(),
                "duration_hours": 2.0,
                "production_impact": "ZERO_PLANNED_BUFFER",
                "available_technicians": 4,
                "recommended_for_horizon": "24-48 Hours"
            },
            {
                "window_id": "WIN-TOMORROW-LUNCH",
                "shop": shop,
                "window_type": "Scheduled Midday Line Maintenance Break",
                "start_time_iso": (now + timedelta(hours=22.0)).isoformat(),
                "duration_hours": 1.5,
                "production_impact": "ZERO_PLANNED_BUFFER",
                "available_technicians": 3,
                "recommended_for_horizon": "24-36 Hours"
            },
            {
                "window_id": "WIN-WEEKEND-PLANNED",
                "shop": shop,
                "window_type": "Weekend Plant Overhaul Window",
                "start_time_iso": (now + timedelta(hours=54.0)).isoformat(),
                "duration_hours": 8.0,
                "production_impact": "PLANNED_DOWNTIME",
                "available_technicians": 8,
                "recommended_for_horizon": "48-72 Hours"
            }
        ]
        return windows

    @staticmethod
    def generate_prescriptive_repair_plan(machine_id: str, failure_mode: str) -> Dict[str, Any]:
        """
        Generates a step-by-step physical maintenance prescription with spare parts and safety steps.
        """
        if machine_id not in PLANT_SIMULATOR.machines:
            return {"error": f"Machine ID '{machine_id}' not found."}

        m = PLANT_SIMULATOR.machines[machine_id]

        if "INNER_RACE" in failure_mode.upper() or "BEARING" in failure_mode.upper():
            plan = {
                "prescription_title": f"Replace Drive End Bearing Assembly on {m.asset_tag}",
                "recommended_part_number": f"{m.bearing_type} (C3 Radial Internal Clearance)",
                "required_consumables": ["Mobil Polyrex EM Synthetic Grease (45g)", "SKF Bearing Induction Heater TIH-030M"],
                "estimated_labor_hours": 1.5,
                "required_crew_size": 2,
                "loto_safety_steps": [
                    "Isolate 480V 3-Phase Main Breaker at Disconnect Switch MCP-4.",
                    "Apply Personal Lockout/Tagout (LOTO) Hasps and verify zero-energy state with calibrated multimeter.",
                    "Bleed and lock hydraulic bolster safety accumulator valve."
                ],
                "execution_steps": [
                    "1. Disengage shaft flexible coupling and record baseline dial-indicator alignment offsets.",
                    "2. Remove bearing housing end-cover; extract degraded bearing using mechanical hydraulic puller.",
                    "3. Inspect shaft journal surface for fretting or galling; wipe clean with lint-free solvent cloth.",
                    "4. Heat replacement bearing to 110°C (230°F) using induction heater and slide firmly onto shaft shoulder.",
                    "5. Pack with 45g specified synthetic polyurea grease; re-torque end-cover bolts to 145 Nm.",
                    "6. Laser re-align shaft coupling to < 0.05 mm radial / angular tolerance; run 15-minute uncoupled test."
                ],
                "post_repair_validation": "Collect 2-minute baseline vibration recording; verify Kurtosis < 3.20 and RMS < 2.5 mm/s."
            }
        elif "LUBRICATION" in failure_mode.upper():
            plan = {
                "prescription_title": f"Purge and Replenish Gearbox Lubrication on {m.asset_tag}",
                "recommended_part_number": "Shell Omala S4 GXV 220 Synthetic Gear Oil (15 Liters)",
                "required_consumables": ["Replacement Oil Filter Cartridge (10 Micron)", "Magnetic Drain Plug Washer"],
                "estimated_labor_hours": 0.75,
                "required_crew_size": 1,
                "loto_safety_steps": ["Lockout robot controller main breaker; engage axis mechanical safety pins."],
                "execution_steps": [
                    "1. Drain degraded gearbox lubricant into waste container; inspect magnetic plug for metal swarf.",
                    "2. Flush gear chamber with clean low-viscosity flushing oil.",
                    "3. Install new 10-micron filter cartridge and torque drain plug to 45 Nm.",
                    "4. Refill with 15L fresh synthetic ISO VG 220 lubricant up to sight glass midpoint."
                ],
                "post_repair_validation": "Run axis at 50% speed for 10 minutes; verify temperature rate of rise < 0.3°C/hr."
            }
        else:
            plan = {
                "prescription_title": f"Electrical Inspection & Stator Insulation Resistance Test on {m.asset_tag}",
                "recommended_part_number": "Standard Stator Terminal Lug Kit / Re-torque hardware",
                "required_consumables": ["Contact Cleaner Spray", "Insulation Heat-Shrink Sleeve"],
                "estimated_labor_hours": 1.0,
                "required_crew_size": 2,
                "loto_safety_steps": ["Lockout 480V VFD input line filter breaker."],
                "execution_steps": [
                    "1. Open motor junction box and inspect for thermal discoloration or loose phase studs.",
                    "2. Perform Megohmmeter (Megger) insulation test at 1000V DC Phase-to-Ground (> 100 MΩ required).",
                    "3. Measure phase-to-phase resistance balance with micro-ohmmeter (< 1.5% imbalance allowed).",
                    "4. Re-torque phase lugs to 28 Nm with calibrated torque wrench and seal junction box."
                ],
                "post_repair_validation": "Power up on VFD; verify Current THD < 2.5% across full speed sweep."
            }

        return plan

    @staticmethod
    def draft_cmms_work_order(machine_id: str, prescription: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formats a structured work order draft ready for SAP PM or IBM Maximo ingestion.
        """
        if machine_id not in PLANT_SIMULATOR.machines:
            return {"error": f"Machine ID '{machine_id}' not found."}

        m = PLANT_SIMULATOR.machines[machine_id]
        now = datetime.now(timezone.utc)
        wo_id = f"WO-SAP-{now.strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

        return {
            "work_order_id": wo_id,
            "cmms_target_system": "SAP_PM_ENTERPRISE",
            "asset_tag": m.asset_tag,
            "machine_name": m.name,
            "shop_location": m.shop.value,
            "order_type": "PM02_PREDICTIVE_MAINTENANCE",
            "priority": "1_HIGH_CRITICAL" if m.criticality == CriticalityTier.TIER_1_BOTTLENECK else "2_MEDIUM",
            "created_at_iso": now.isoformat(),
            "target_execution_window": "WIN-TONIGHT-01 (22:00 - 00:00 UTC)",
            "title": prescription.get("prescription_title", "Predictive Component Replacement"),
            "required_parts": [prescription.get("recommended_part_number", "N/A")],
            "estimated_hours": prescription.get("estimated_labor_hours", 1.5),
            "safety_instructions": prescription.get("loto_safety_steps", []),
            "work_instructions": prescription.get("execution_steps", []),
            "status": "DRAFT_READY_FOR_APPROVAL"
        }
