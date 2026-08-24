"""
Conversational AI Maintenance Copilot.
Handles natural language inquiries, plant triage questions, and diagnostic investigations.
"""
from typing import Dict, Any, List, Optional
import re
from src.config import CONFIG, CriticalityTier, ShopType
from src.engine.simulator import PLANT_SIMULATOR
from src.agent.reasoning_engine import MaintenanceReasoningEngine
from src.agent.tools import MaintenanceAgentTools


class MaintenanceCopilot:
    """
    Conversational assistant for Maintenance Managers and Reliability Engineers.
    """

    @classmethod
    def process_query(cls, user_message: str, current_machine_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Interprets natural language queries, resolves context, and executes diagnostic workflows.
        """
        msg_lower = user_message.lower().strip()
        matched_machine_id = current_machine_id

        # 1. Machine Tag / Name Slot Resolution
        if not matched_machine_id or "all" in msg_lower or "highest" in msg_lower or "overall" in msg_lower:
            if "stamp" in msg_lower and "04" in msg_lower:
                matched_machine_id = "m-stamp-04"
            elif "stamp" in msg_lower and "02" in msg_lower:
                matched_machine_id = "m-stamp-02"
            elif "biw" in msg_lower or "robot 08" in msg_lower or "framing" in msg_lower:
                matched_machine_id = "m-biw-08"
            elif "paint" in msg_lower or "e-coat" in msg_lower or "conveyor" in msg_lower:
                matched_machine_id = "m-pnt-02"
            elif "cnc" in msg_lower or "spindle" in msg_lower or "powertrain" in msg_lower:
                matched_machine_id = "m-pwt-14"
            elif "agv" in msg_lower or "assembly" in msg_lower:
                matched_machine_id = "m-asm-05"

        # 2. Plant-wide / Triage Inquiries
        if any(term in msg_lower for term in ["overview", "summary", "highest risk", "top machines", "status of plant", "how is the plant"]):
            # Rank all machines by composite risk
            ranked_assets = []
            for mid, m in PLANT_SIMULATOR.machines.items():
                agg = m.buffer.get_aggregated_features()
                pred = MaintenanceAgentTools.get_machine_telemetry(mid)["prediction"]
                ranked_assets.append({
                    "machine_id": mid,
                    "asset_tag": m.asset_tag,
                    "name": m.name,
                    "shop": m.shop.value,
                    "criticality": m.criticality.value,
                    "risk_tier": pred["risk_tier"],
                    "failure_prob": pred["failure_probability"],
                    "horizon_hours": pred["predicted_horizon_hours"],
                    "composite_risk": pred["composite_risk_score"]
                })

            ranked_assets.sort(key=lambda x: x["composite_risk"], reverse=True)
            critical_count = sum(1 for a in ranked_assets if a["risk_tier"] == "CRITICAL")
            top_critical = [a for a in ranked_assets if a["risk_tier"] == "CRITICAL"]

            response_text = (
                f"**Plant Status Overview**: The plant is currently operating with **{critical_count} critical high-risk machine(s)** "
                f"requiring planned intervention in the next 24–72 hours:\n\n"
            )
            for a in top_critical:
                response_text += (
                    f"- **{a['asset_tag']} ({a['name']})** in *{a['shop']}*: "
                    f"**{round(a['failure_prob'] * 100, 1)}% failure probability** within **{a['horizon_hours']} hours** "
                    f"(Risk Score: {a['composite_risk']}).\n"
                )

            response_text += "\n*Would you like me to generate a prescriptive repair plan or draft an SAP PM work order for any of these assets?*"

            return {
                "response_type": "PLANT_OVERVIEW",
                "message": response_text,
                "ranked_assets": ranked_assets[:5],
                "diagnostic_card": None
            }

        # 3. Specific Machine Deep Diagnostics
        if matched_machine_id:
            diag = MaintenanceReasoningEngine.execute_deep_diagnosis(matched_machine_id)
            if "error" in diag:
                return {
                    "response_type": "ERROR",
                    "message": f"Could not analyze asset: {diag['error']}",
                    "diagnostic_card": None
                }

            # Tailor conversation message based on specific inquiry
            if "repair" in msg_lower or "prescription" in msg_lower or "how to fix" in msg_lower or "loto" in msg_lower:
                rx = diag["prescriptive_repair_plan"]
                msg = (
                    f"### Prescriptive Repair Plan for **{diag['asset_tag']}**\n"
                    f"**Title**: {rx['prescription_title']}\n"
                    f"**Required Part**: `{rx['recommended_part_number']}`\n"
                    f"**Estimated Labor**: {rx['estimated_labor_hours']} hours ({rx['required_crew_size']} technicians)\n\n"
                    f"**LOTO Safety Protocols**:\n" + "\n".join([f"- {s}" for s in rx['loto_safety_steps']]) + "\n\n"
                    f"**Step-by-Step Procedure**:\n" + "\n".join([f"{s}" for s in rx['execution_steps']]) + "\n\n"
                    f"**Post-Repair Validation**: {rx['post_repair_validation']}"
                )
            elif "cost" in msg_lower or "financial" in msg_lower or "roi" in msg_lower or "money" in msg_lower:
                fin = diag["financial_impact"]
                msg = (
                    f"### Financial Impact & Downtime Risk for **{diag['asset_tag']}**\n"
                    f"- **Shop / Criticality**: {diag['shop']} ({diag['criticality']})\n"
                    f"- **Downtime Cost Rate**: **${int(fin['downtime_cost_per_minute_usd']):,}/minute**\n"
                    f"- **Catastrophic Unplanned Failure Exposure**: **${int(fin['estimated_unplanned_failure_cost_usd']):,} USD** (4.0 hours line halt)\n"
                    f"- **Planned Shift Intervention Cost**: **${int(fin['estimated_planned_intervention_cost_usd']):,} USD**\n"
                    f"- **Net Projected Savings**: **${int(fin['net_roi_savings_usd']):,} USD**"
                )
            else:
                msg = diag["executive_summary"]

            return {
                "response_type": "ASSET_DIAGNOSIS",
                "message": msg,
                "diagnostic_card": diag
            }

        # 4. Fallback General Assistance
        return {
            "response_type": "GENERAL_HELP",
            "message": (
                "I am **AutoPredict Copilot**, your autonomous predictive maintenance intelligence assistant. "
                "You can ask me to:\n\n"
                "- *'Give me an overview of highest risk machines in the plant'*\n"
                "- *'What is causing the critical alert on Stamping Press 04?'*\n"
                "- *'Generate a step-by-step repair prescription and LOTO safety guide for Framing Robot 08'*\n"
                "- *'Calculate the downtime financial cost if Powertrain CNC Spindle 14 fails'*."
            ),
            "diagnostic_card": None
        }
