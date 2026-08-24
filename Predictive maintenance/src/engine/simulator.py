"""
Industrial Automotive Machine & Sensor Telemetry Simulator.
Generates realistic multi-channel industrial streams, baseline histories, and supports fault injection.
"""
import time
import math
import random
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from src.config import ShopType, CriticalityTier, FailureMode, CONFIG
from src.engine.signal_processor import SignalProcessor
from src.engine.sliding_window import SlidingWindowBuffer


class SimulatedMachine:
    def __init__(
        self,
        machine_id: str,
        asset_tag: str,
        name: str,
        shop: ShopType,
        criticality: CriticalityTier,
        nominal_rpm: float,
        nominal_temp: float,
        nominal_current: float,
        nominal_pressure: float,
        bearing_type: str = "SKF-6312",
        failure_mode: FailureMode = FailureMode.NORMAL_OPERATION,
        fault_severity: float = 0.0,  # 0.0 = Healthy, 1.0 = Catastrophic
        degradation_rate_per_hour: float = 0.0
    ):
        self.machine_id = machine_id
        self.asset_tag = asset_tag
        self.name = name
        self.shop = shop
        self.criticality = criticality
        self.nominal_rpm = nominal_rpm
        self.nominal_temp = nominal_temp
        self.nominal_current = nominal_current
        self.nominal_pressure = nominal_pressure
        self.bearing_type = bearing_type
        self.failure_mode = failure_mode
        self.fault_severity = fault_severity
        self.degradation_rate_per_hour = degradation_rate_per_hour
        self.operational_status = "RUNNING"
        self.buffer = SlidingWindowBuffer(machine_id)
        self.bearing_kinematics = SignalProcessor.calculate_bearing_fault_frequencies(nominal_rpm)

    def generate_high_frequency_waveform(self, sample_rate_hz: float = 4000.0, duration_sec: float = 0.5) -> np.ndarray:
        """
        Synthesizes a realistic high-frequency mechanical vibration acceleration waveform.
        Includes 1X/2X shaft harmonics, bearing characteristic defect impacts (if faulted), and Gaussian noise.
        """
        n_samples = int(sample_rate_hz * duration_sec)
        t = np.linspace(0, duration_sec, n_samples, endpoint=False)

        # Baseline rotational harmonics
        f1 = self.nominal_rpm / 60.0
        waveform = 0.8 * np.sin(2 * np.pi * f1 * t) + 0.3 * np.sin(2 * np.pi * (2 * f1) * t)

        # Ambient sensor white noise
        waveform += np.random.normal(0, 0.25, n_samples)

        # Injected defect physical dynamics
        if self.fault_severity > 0.0:
            if self.failure_mode == FailureMode.BEARING_INNER_RACE:
                # BPFI sharp impulsive shocks with exponentially decaying ring-down
                f_bpfi = self.bearing_kinematics["bpfi_inner_race_hz"]
                f_resonance = 1850.0  # structural resonance carrier frequency
                # Generate impulse train at BPFI
                impulse_period = int(sample_rate_hz / f_bpfi)
                decay_len = int(sample_rate_hz * 0.005)  # 5ms decay
                decay_t = np.linspace(0, 0.005, decay_len)
                ring_down = np.exp(-decay_t * 800) * np.sin(2 * np.pi * f_resonance * decay_t)

                for idx in range(0, n_samples - decay_len, impulse_period):
                    # Add random jitter to impulse amplitude
                    shock_amp = (5.5 * self.fault_severity) * (1.0 + 0.2 * np.random.randn())
                    waveform[idx : idx + decay_len] += shock_amp * ring_down

            elif self.failure_mode == FailureMode.BEARING_OUTER_RACE:
                f_bpfo = self.bearing_kinematics["bpfo_outer_race_hz"]
                f_resonance = 1450.0
                impulse_period = int(sample_rate_hz / f_bpfo)
                decay_len = int(sample_rate_hz * 0.006)
                decay_t = np.linspace(0, 0.006, decay_len)
                ring_down = np.exp(-decay_t * 600) * np.sin(2 * np.pi * f_resonance * decay_t)

                for idx in range(0, n_samples - decay_len, impulse_period):
                    shock_amp = (4.0 * self.fault_severity) * (1.0 + 0.15 * np.random.randn())
                    waveform[idx : idx + decay_len] += shock_amp * ring_down

            elif self.failure_mode == FailureMode.MECHANICAL_LOOSENESS:
                # Strong 2X, 3X, 4X, 0.5X sub-harmonics
                waveform += (3.5 * self.fault_severity) * np.sin(2 * np.pi * (2 * f1) * t)
                waveform += (2.2 * self.fault_severity) * np.sin(2 * np.pi * (3 * f1) * t)
                waveform += (1.8 * self.fault_severity) * np.sin(2 * np.pi * (0.5 * f1) * t)

        return waveform

    def step_simulation(self, dt_minutes: float = 3.0) -> Dict[str, Any]:
        """
        Advances the machine state by dt_minutes, computes sensor readings, and appends to sliding buffer.
        """
        # Progress fault degradation if active
        if self.fault_severity > 0.0 and self.degradation_rate_per_hour > 0.0:
            self.fault_severity = min(1.0, self.fault_severity + (self.degradation_rate_per_hour * (dt_minutes / 60.0)))

        # Generate high-frequency waveform and extract real-time features
        waveform = self.generate_high_frequency_waveform()
        time_feats = SignalProcessor.calculate_time_domain_features(waveform)

        # Baseline physics + fault offsets
        vib_rms = max(0.5, time_feats["rms"] + (3.8 * self.fault_severity if self.failure_mode != FailureMode.NORMAL_OPERATION else 0.0))
        kurtosis = max(2.8, time_feats["kurtosis"])
        crest_factor = max(1.8, time_feats["crest_factor"])

        # Temperature
        temp_rise = 0.0
        if self.failure_mode == FailureMode.LUBRICATION_STARVATION:
            temp_rise = 38.0 * self.fault_severity
        elif self.failure_mode in [FailureMode.BEARING_INNER_RACE, FailureMode.STATOR_WINDING_FAULT]:
            temp_rise = 18.0 * self.fault_severity
        current_temp = self.nominal_temp + temp_rise + random.uniform(-0.4, 0.4)

        # Motor Current & THD
        current_offset = 0.0
        thd_val = 1.6 + random.uniform(-0.2, 0.2)
        if self.failure_mode == FailureMode.STATOR_WINDING_FAULT:
            current_offset = 15.0 * self.fault_severity
            thd_val += 8.5 * self.fault_severity
        elif self.fault_severity > 0.0:
            current_offset = 4.0 * self.fault_severity
            thd_val += 2.0 * self.fault_severity

        current_a = self.nominal_current + current_offset + random.uniform(-0.8, 0.8)
        current_rpm = self.nominal_rpm + random.uniform(-5.0, 5.0)
        current_pressure = self.nominal_pressure + random.uniform(-1.5, 1.5)

        now_iso = datetime.now(timezone.utc).isoformat()
        self.buffer.append_observation(
            timestamp_iso=now_iso,
            vib_rms=vib_rms,
            vib_kurtosis=kurtosis,
            vib_crest_factor=crest_factor,
            temp_c=current_temp,
            current_a=current_a,
            rpm_val=current_rpm,
            pressure_bar=current_pressure,
            thd_val=thd_val
        )

        return {
            "machine_id": self.machine_id,
            "asset_tag": self.asset_tag,
            "name": self.name,
            "shop": self.shop.value,
            "criticality": self.criticality.value,
            "timestamp": now_iso,
            "vibration_rms": round(vib_rms, 3),
            "vibration_kurtosis": round(kurtosis, 3),
            "vibration_crest_factor": round(crest_factor, 3),
            "temperature_c": round(current_temp, 2),
            "current_a": round(current_a, 2),
            "current_thd": round(thd_val, 2),
            "rpm": round(current_rpm, 1),
            "pressure_bar": round(current_pressure, 1),
            "fault_severity": round(self.fault_severity, 3),
            "failure_mode": self.failure_mode.value
        }


class PlantSimulator:
    """
    Simulates the entire automotive manufacturing plant fleet across 5 shops.
    """

    def __init__(self):
        self.machines: Dict[str, SimulatedMachine] = {}
        self._initialize_fleet()

    def _initialize_fleet(self):
        # 12 representative automotive machines
        fleet_configs = [
            # Stamping Shop
            SimulatedMachine(
                machine_id="m-stamp-04",
                asset_tag="STAMP-P04-5000T",
                name="Stamping Press 04 Main Drive",
                shop=ShopType.STAMPING,
                criticality=CriticalityTier.TIER_1_BOTTLENECK,
                nominal_rpm=1780.0,
                nominal_temp=62.0,
                nominal_current=145.0,
                nominal_pressure=210.0,
                bearing_type="SKF-22220-Spherical",
                failure_mode=FailureMode.BEARING_INNER_RACE,
                fault_severity=0.72,  # Configured with active incipient defect for MVP demo
                degradation_rate_per_hour=0.008
            ),
            SimulatedMachine(
                machine_id="m-stamp-02",
                asset_tag="STAMP-P02-HYD",
                name="Stamping Press 02 Hydraulic Pump A",
                shop=ShopType.STAMPING,
                criticality=CriticalityTier.TIER_2_MAJOR,
                nominal_rpm=1450.0,
                nominal_temp=58.0,
                nominal_current=68.0,
                nominal_pressure=190.0,
                bearing_type="SKF-6312",
                failure_mode=FailureMode.NORMAL_OPERATION,
                fault_severity=0.0
            ),
            SimulatedMachine(
                machine_id="m-stamp-feed-01",
                asset_tag="STAMP-FEED-01",
                name="Coil Feeder & Straightener Servo",
                shop=ShopType.STAMPING,
                criticality=CriticalityTier.TIER_2_MAJOR,
                nominal_rpm=1200.0,
                nominal_temp=52.0,
                nominal_current=38.0,
                nominal_pressure=85.0,
                bearing_type="SKF-6208",
                failure_mode=FailureMode.NORMAL_OPERATION,
                fault_severity=0.0
            ),

            # Body-in-White (BIW)
            SimulatedMachine(
                machine_id="m-biw-08",
                asset_tag="BIW-R08-FRM",
                name="Framing Robot 08 Servo Axis 3",
                shop=ShopType.BIW,
                criticality=CriticalityTier.TIER_1_BOTTLENECK,
                nominal_rpm=2400.0,
                nominal_temp=56.0,
                nominal_current=28.0,
                nominal_pressure=0.0,
                bearing_type="KUKA-Cycloidal-J3",
                failure_mode=FailureMode.LUBRICATION_STARVATION,
                fault_severity=0.64,
                degradation_rate_per_hour=0.010
            ),
            SimulatedMachine(
                machine_id="m-biw-19",
                asset_tag="BIW-R19-WLD",
                name="Spot Weld Gun Transformer B",
                shop=ShopType.BIW,
                criticality=CriticalityTier.TIER_3_BUFFER,
                nominal_rpm=0.0,
                nominal_temp=48.0,
                nominal_current=210.0,
                nominal_pressure=6.5,
                bearing_type="N/A",
                failure_mode=FailureMode.NORMAL_OPERATION,
                fault_severity=0.0
            ),
            SimulatedMachine(
                machine_id="m-biw-04",
                asset_tag="BIW-R04-HDL",
                name="Body Panel Transfer Robot Arm J1",
                shop=ShopType.BIW,
                criticality=CriticalityTier.TIER_2_MAJOR,
                nominal_rpm=1800.0,
                nominal_temp=54.0,
                nominal_current=32.0,
                nominal_pressure=0.0,
                bearing_type="KUKA-RV-Gear-J1",
                failure_mode=FailureMode.NORMAL_OPERATION,
                fault_severity=0.0
            ),

            # Paint Shop
            SimulatedMachine(
                machine_id="m-pnt-02",
                asset_tag="PNT-CNV-02",
                name="E-Coat Dip Tank Conveyor Drive",
                shop=ShopType.PAINT,
                criticality=CriticalityTier.TIER_2_MAJOR,
                nominal_rpm=950.0,
                nominal_temp=64.0,
                nominal_current=72.0,
                nominal_pressure=0.0,
                bearing_type="SKF-22216",
                failure_mode=FailureMode.MECHANICAL_LOOSENESS,
                fault_severity=0.48,
                degradation_rate_per_hour=0.005
            ),
            SimulatedMachine(
                machine_id="m-pnt-air-01",
                asset_tag="PNT-AIR-01",
                name="Paint Booth Exhaust Blower Motor",
                shop=ShopType.PAINT,
                criticality=CriticalityTier.TIER_3_BUFFER,
                nominal_rpm=1750.0,
                nominal_temp=59.0,
                nominal_current=55.0,
                nominal_pressure=4.2,
                bearing_type="SKF-6310",
                failure_mode=FailureMode.NORMAL_OPERATION,
                fault_severity=0.0
            ),

            # Powertrain Machining
            SimulatedMachine(
                machine_id="m-pwt-14",
                asset_tag="PWT-CNC-14",
                name="Cylinder Block 5-Axis Milling Spindle",
                shop=ShopType.POWERTRAIN,
                criticality=CriticalityTier.TIER_1_BOTTLENECK,
                nominal_rpm=12000.0,
                nominal_temp=46.0,
                nominal_current=84.0,
                nominal_pressure=70.0,
                bearing_type="NSK-Ceramic-Hybrid-7014",
                failure_mode=FailureMode.STATOR_WINDING_FAULT,
                fault_severity=0.68,
                degradation_rate_per_hour=0.009
            ),
            SimulatedMachine(
                machine_id="m-pwt-02",
                asset_tag="PWT-CNC-02",
                name="Cylinder Head Boring Spindle",
                shop=ShopType.POWERTRAIN,
                criticality=CriticalityTier.TIER_2_MAJOR,
                nominal_rpm=8000.0,
                nominal_temp=44.0,
                nominal_current=58.0,
                nominal_pressure=60.0,
                bearing_type="NSK-7012",
                failure_mode=FailureMode.NORMAL_OPERATION,
                fault_severity=0.0
            ),

            # Final Assembly
            SimulatedMachine(
                machine_id="m-asm-05",
                asset_tag="ASM-AGV-05",
                name="Chassis Marriage AGV Traction Drive",
                shop=ShopType.ASSEMBLY,
                criticality=CriticalityTier.TIER_2_MAJOR,
                nominal_rpm=1500.0,
                nominal_temp=51.0,
                nominal_current=42.0,
                nominal_pressure=0.0,
                bearing_type="SKF-6206",
                failure_mode=FailureMode.NORMAL_OPERATION,
                fault_severity=0.0
            ),
            SimulatedMachine(
                machine_id="m-asm-torq-11",
                asset_tag="ASM-TORQ-11",
                name="Rear Axle Multi-Spindle Nutrunner",
                shop=ShopType.ASSEMBLY,
                criticality=CriticalityTier.TIER_3_BUFFER,
                nominal_rpm=650.0,
                nominal_temp=41.0,
                nominal_current=19.0,
                nominal_pressure=6.0,
                bearing_type="Atlas-Copco-Gear",
                failure_mode=FailureMode.NORMAL_OPERATION,
                fault_severity=0.0
            )
        ]

        for m in fleet_configs:
            self.machines[m.machine_id] = m
            # Preload 72 hours of historical baseline telemetry so charts render immediately
            self._preload_historical_telemetry(m)

    def _preload_historical_telemetry(self, machine: SimulatedMachine, total_hours: int = 72):
        """
        Fills the 72-hour sliding window with realistic baseline and progressive drift history.
        """
        now = datetime.now(timezone.utc)
        n_points = 240  # 1 point per ~18 minutes for historical curve
        final_fault = machine.fault_severity

        for i in range(n_points):
            t_offset_hours = total_hours * (1.0 - (i / n_points))
            hist_time = now - timedelta(hours=t_offset_hours)

            # Progressive degradation curve towards current fault severity
            progress_factor = (i / n_points) ** 2.5
            curr_severity = final_fault * progress_factor if final_fault > 0 else 0.0

            # Temporary set severity to synthesize historical point
            temp_severity = machine.fault_severity
            machine.fault_severity = curr_severity
            waveform = machine.generate_high_frequency_waveform()
            t_feats = SignalProcessor.calculate_time_domain_features(waveform)

            vib_rms = max(0.6, t_feats["rms"] + (3.5 * curr_severity if machine.failure_mode != FailureMode.NORMAL_OPERATION else 0.0))
            kurt = max(2.8, t_feats["kurtosis"])
            crest = max(1.8, t_feats["crest_factor"])
            temp_rise = 18.0 * curr_severity if machine.failure_mode != FailureMode.NORMAL_OPERATION else 0.0
            temp = machine.nominal_temp + temp_rise + random.uniform(-0.3, 0.3)
            current = machine.nominal_current + (5.0 * curr_severity) + random.uniform(-0.5, 0.5)
            thd = 1.6 + (7.0 * curr_severity if machine.failure_mode == FailureMode.STATOR_WINDING_FAULT else 0.0)

            machine.buffer.append_observation(
                timestamp_iso=hist_time.isoformat(),
                vib_rms=round(vib_rms, 3),
                vib_kurtosis=round(kurt, 3),
                vib_crest_factor=round(crest, 3),
                temp_c=round(temp, 2),
                current_a=round(current, 2),
                rpm_val=machine.nominal_rpm + random.uniform(-3, 3),
                pressure_bar=machine.nominal_pressure + random.uniform(-1, 1),
                thd_val=round(thd, 2)
            )

            machine.fault_severity = temp_severity

    def inject_fault(self, machine_id: str, mode: FailureMode, severity: float = 0.75, rate_per_hour: float = 0.01) -> bool:
        """
        Dynamically injects a mechanical or electrical failure into a machine at runtime.
        """
        if machine_id not in self.machines:
            return False
        m = self.machines[machine_id]
        m.failure_mode = mode
        m.fault_severity = severity
        m.degradation_rate_per_hour = rate_per_hour
        return True

    def clear_fault(self, machine_id: str) -> bool:
        """
        Resets machine to healthy baseline after simulated repair.
        """
        if machine_id not in self.machines:
            return False
        m = self.machines[machine_id]
        m.failure_mode = FailureMode.NORMAL_OPERATION
        m.fault_severity = 0.0
        m.degradation_rate_per_hour = 0.0
        return True

    def step_all(self) -> List[Dict[str, Any]]:
        """
        Advances all machines by one simulation step.
        """
        results = []
        for m in self.machines.values():
            reading = m.step_simulation(dt_minutes=3.0)
            results.append(reading)
        return results


# Global plant simulation singleton
PLANT_SIMULATOR = PlantSimulator()
