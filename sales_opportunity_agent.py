"""
Sales Opportunity Agent (Main Orchestrator)
===========================================
Primary natural-language AI Agent for Sales Representatives.
Orchestrates FMCSA data ingestion, "Find my City" child agent enrichment,
sales territory mapping, summary reports (Mode 1), and outreach script generation (Mode 2).
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from fmcsa_connector import FMCSADataConnector
from child_agent_enrichment import CarrierEnrichmentChildAgent
from sales_territory_mapper import SalesTerritoryMapper

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SalesOpportunityAgent")

# Optional OpenAI / Azure OpenAI Integration
HAS_OPENAI = False
try:
    import openai
    if os.getenv("OPENAI_API_KEY") or os.getenv("AZURE_OPENAI_KEY"):
        HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class SalesOpportunityAgent:
    """
    Main Sales Opportunity Agent.
    """

    SYSTEM_PROMPT = """You are the Sales Opportunity Agent for a commercial fleet services company.
Your goal is to provide sales representatives early visibility into motor carriers recently placed Out of Service (OOS) by FMCSA.

You coordinate with a specialized "Find my City" Child Agent to enrich carrier records with physical location, contact info, and fleet size, and route each lead to the correct regional salesperson.

You operate in two core modes:
Mode 1: Summarize the last X Out of Service notifications with enriched city/state and assigned salesperson.
Mode 2: Generate a personalized Lead Outreach Script adhering strictly to the business template:
"Hi <Business Name>,
I see your operations were recently impacted by an out-of-service notice dated <Out of Service Date>. Can we set up a call to discuss new sales opportunities?"
"""

    def __init__(self, use_live_api: bool = False):
        self.connector = FMCSADataConnector(use_live_api=use_live_api)
        self.child_agent = CarrierEnrichmentChildAgent(use_live_api=use_live_api)
        self.territory_mapper = SalesTerritoryMapper()

    def process_request(self, user_query: str, limit: int = 5) -> Dict[str, Any]:
        """
        Process a natural language request from a sales representative.
        
        Parameters
        ----------
        user_query : str
            Natural language prompt (e.g. "Find last 5 carriers placed out of service", "Generate script for DOT 1438").
        limit : int
            Number of notifications to process.
            
        Returns
        -------
        Dict[str, Any]
            Structured response containing mode, summary table/list, enriched records, and outreach scripts.
        """
        query_lower = user_query.lower()
        
        # Determine intent: Mode 2 (Outreach Script) vs Mode 1 (Summary)
        if "script" in query_lower or "outreach" in query_lower or "email" in query_lower or "message" in query_lower:
            return self.execute_mode_2_outreach_script(user_query, limit=limit)
        else:
            return self.execute_mode_1_summary(limit=limit)

    def fetch_and_enrich_leads(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Ingest daily OOS records, invoke Child Agent for location/fleet enrichment,
        and assign sales representative by state.
        """
        oos_records = self.connector.fetch_latest_oos_records(limit=limit)
        enriched_leads = []

        for record in oos_records:
            dot_num = record.get("DOT_NUMBER")
            legal_name = record.get("LEGAL_NAME", "UNKNOWN")

            # 1. Invoke Child Agent ("Find my City")
            enrichment = self.child_agent.enrich_carrier_by_dot(dot_num)

            # Resolve best City & State
            city = enrichment.get("PHY_CITY") or record.get("PHY_CITY") or "Dallas"
            state = enrichment.get("PHY_STATE") or record.get("PHY_STATE") or "TX"
            phone = enrichment.get("TELEPHONE") or "Not Available"
            email = enrichment.get("EMAIL") or "Not Available"

            # 2. Map State to Sales Representative
            salesperson_info = self.territory_mapper.get_salesperson_for_state(state)

            lead = {
                "DOT_NUMBER": dot_num,
                "LEGAL_NAME": legal_name,
                "DBA_NAME": record.get("DBA_NAME"),
                "OOS_DATE": record.get("OOS_DATE") or "Recently",
                "OOS_REASON": record.get("OOS_REASON") or "Unsatisfactory = Unfit / Safety Compliance",
                "STATUS": record.get("STATUS", "ACTIVE"),
                "RESCIND_DATE": record.get("RESCIND_DATE"),
                # Enriched location & contacts from Child Agent
                "CITY": city,
                "STATE": state,
                "STREET": enrichment.get("PHY_STREET"),
                "ZIP": enrichment.get("PHY_ZIP"),
                "PHONE": phone,
                "EMAIL": email,
                "DRIVER_TOTAL": enrichment.get("DRIVER_TOTAL", "N/A"),
                "VEHICLE_TOTAL": enrichment.get("VEHICLE_TOTAL", "N/A"),
                "SAFETY_RATING": enrichment.get("SAFETY_RATING", "Unrated"),
                # Sales routing info
                "ASSIGNED_SALESPERSON": salesperson_info["salesperson"],
                "SALESPERSON_TITLE": salesperson_info["title"],
                "SALESPERSON_EMAIL": salesperson_info["email"],
                "SALES_REGION": salesperson_info["region"],
                "RECOMMENDED_OFFERING": salesperson_info["recommended_offering"]
            }
            enriched_leads.append(lead)

        return enriched_leads

    def execute_mode_1_summary(self, limit: int = 5) -> Dict[str, Any]:
        """
        Response Mode 1: Summary of the last X Out-of-Service Notifications.
        """
        leads = self.fetch_and_enrich_leads(limit=limit)

        summary_lines = []
        summary_lines.append(f"### 🚚 Summary of the Last {len(leads)} Out of Service (OOS) Notifications\n")
        summary_lines.append("| USDOT # | Carrier Name | City, State | OOS Date | Reason | Assigned Salesperson |")
        summary_lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

        for lead in leads:
            summary_lines.append(
                f"| `{lead['DOT_NUMBER']}` | **{lead['LEGAL_NAME']}** | {lead['CITY']}, {lead['STATE']} | "
                f"{lead['OOS_DATE']} | {lead['OOS_REASON']} | **{lead['ASSIGNED_SALESPERSON']}** ({lead['SALES_REGION']}) |"
            )

        summary_text = "\n".join(summary_lines)

        return {
            "mode": "MODE_1_SUMMARY",
            "title": f"Summary of Last {len(leads)} Out of Service Notifications",
            "formatted_output": summary_text,
            "leads": leads
        }

    def execute_mode_2_outreach_script(self, user_query: str, limit: int = 1) -> Dict[str, Any]:
        """
        Response Mode 2: Generate personalized lead outreach script adhering to required template.
        """
        leads = self.fetch_and_enrich_leads(limit=limit)
        if not leads:
            return {"mode": "MODE_2_OUTREACH", "formatted_output": "No recent OOS leads found."}

        # Select target lead
        lead = leads[0]
        business_name = lead["LEGAL_NAME"]
        oos_date = lead["OOS_DATE"]
        city_state = f"{lead['CITY']}, {lead['STATE']}"
        salesperson = lead["ASSIGNED_SALESPERSON"]
        offering = lead["RECOMMENDED_OFFERING"]
        reason = lead["OOS_REASON"]

        # Exact mandated template:
        # Hi <Business Name>,
        # I see your operations were recently impacted by an out-of-service notice dated <Out of Service Date>. Can we set up a call to discuss new sales opportunities?
        mandatory_template = (
            f"Hi {business_name},\n\n"
            f"I see your operations were recently impacted by an out-of-service notice dated {oos_date}. "
            f"Can we set up a call to discuss new sales opportunities?"
        )

        tailored_value_prop = (
            f"\n\n--- Tailored Value Proposition for Sales Rep ({salesperson}) ---\n"
            f"📍 Location: {city_state}\n"
            f"⚠️ Reason for OOS: {reason}\n"
            f"💡 Recommended Pitch: Our team specializes in '{offering}'. "
            f"We can assist with rapid vehicle replacement, FMCSA compliance remediation, and maintenance audits "
            f"to help get your fleet back on the road safely and quickly."
        )

        full_script = f"### 📧 Generated Lead Outreach Script\n\n```text\n{mandatory_template}\n```\n{tailored_value_prop}"

        return {
            "mode": "MODE_2_OUTREACH",
            "target_lead": lead,
            "mandatory_template": mandatory_template,
            "formatted_output": full_script
        }


if __name__ == "__main__":
    agent = SalesOpportunityAgent(use_live_api=False)
    
    print("=== TESTING MODE 1 (SUMMARY) ===")
    res_m1 = agent.process_request("Summarize last 3 out of service notifications")
    print(res_m1["formatted_output"])
    
    print("\n=== TESTING MODE 2 (OUTREACH SCRIPT) ===")
    res_m2 = agent.process_request("Generate lead outreach script for latest OOS carrier")
    print(res_m2["formatted_output"])
