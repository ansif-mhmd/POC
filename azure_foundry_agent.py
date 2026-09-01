"""
Microsoft Azure AI Foundry & Azure OpenAI Agent Runtime
======================================================
Connects live to Azure OpenAI using credentials from .env:
  AZURE_OPENAI_ENDPOINT="https://wyn-p1-fndry.services.ai.azure.com/"
  AZURE_OPENAI_API_KEY="..."
  AZURE_OPENAI_DEPLOYMENT="gpt-5-mini"
  AZURE_OPENAI_API_VERSION="2024-02-15-preview"

Generates custom sales outreach email campaigns using model gpt-5-mini.
Company Name: Carrier Fix
"""

import os
import ssl
import urllib3
import logging
import httpx
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings()

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AzureFoundryAgent")

# OpenAI SDK Import
HAS_AZURE_OPENAI = False
try:
    from openai import AzureOpenAI
    HAS_AZURE_OPENAI = True
except ImportError:
    HAS_AZURE_OPENAI = False


DEFAULT_SALES_AGENT_PROMPT = """You are an AI Sales Agent working for company 'Carrier Fix' (Fleet Solutions Group).
Your objective is to draft a personalized, professional sales outreach email to commercial motor carriers placed Out of Service (OOS) by FMCSA.

Rules:
1. Always start the email body verbatim with the Mandated Opening Line provided.
2. Tailor the secondary pitch specifically to the carrier's violation reason, location (City, State), fleet size (vehicles/drivers), and salesperson focus offering.
3. Keep the tone consultative, professional, and helpful.
4. Sign off with the representative name, title, territory area, and Carrier Fix branding.
"""

DEFAULT_ENRICHMENT_AGENT_PROMPT = """You are a Child Agent for Carrier Enrichment.
Your objective is to look up missing carrier address, city, state, telephone, email, and fleet vehicle/driver totals from available caches or Socrata API endpoints.
Return uniform JSON fields with high accuracy.
"""

DEFAULT_TERRITORY_MAPPER_PROMPT = """You are a Territory Sales Opportunity Agent.
Your objective is to analyze Out-of-Service carrier records and assign them to salesperson territory regions (MIDWEST, SOUTH, WEST, NORTHEAST) based on physical state boundaries.
"""


class AzureFoundrySalesAgent:
    """
    Azure AI Foundry & Azure OpenAI Custom Sales Agent for Carrier Fix.
    """

    COMPANY_NAME = "Carrier Fix"

    def __init__(self):
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "https://wyn-p1-fndry.services.ai.azure.com/")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        self.ai_client = None

        if HAS_AZURE_OPENAI and self.endpoint and self.api_key:
            try:
                http_client = httpx.Client(verify=False)
                self.ai_client = AzureOpenAI(
                    azure_endpoint=self.endpoint,
                    api_key=self.api_key,
                    api_version=self.api_version,
                    http_client=http_client
                )
                logger.info(f"[Azure OpenAI Agent] Connected to deployment '{self.deployment}'.")
            except Exception as e:
                logger.warning(f"[Azure OpenAI Agent] Client initialization warning: {e}")

    def generate_custom_email_for_carrier(
        self,
        carrier_info: Dict[str, Any],
        salesperson_info: Dict[str, Any],
        custom_system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate custom tailored sales outreach email for a targeted carrier company
        using Carrier Fix business identity and salesperson territory parameters.
        """
        business_name = carrier_info.get("LEGAL_NAME") or "Valued Commercial Carrier"
        dot_num = carrier_info.get("DOT_NUMBER")
        oos_date = carrier_info.get("OOS_DATE") or "Recently"
        city = carrier_info.get("PHY_CITY") or carrier_info.get("CITY") or "Dallas"
        state = carrier_info.get("PHY_STATE") or carrier_info.get("STATE") or "TX"
        reason = carrier_info.get("OOS_REASON") or "Safety Fitness / Operational Order"
        vehicles = carrier_info.get("VEHICLE_TOTAL") or 0
        drivers = carrier_info.get("DRIVER_TOTAL") or 0

        rep_name = salesperson_info.get("name", "Sales Representative")
        rep_title = salesperson_info.get("title", "Commercial Account Executive")
        rep_region = salesperson_info.get("region", "National")
        rep_email = salesperson_info.get("email", "sales@carrierfix.com")
        rep_offering = salesperson_info.get("focus_offering", "Fleet Maintenance & Asset Replacement")

        # Mandated Opening Line
        mandated_opening = (
            f"Hi {business_name},\n\n"
            f"I see your operations were recently impacted by an out-of-service notice dated {oos_date}. "
            f"Can we set up a call to discuss new sales opportunities?"
        )

        subject_line = f"Urgent Fleet Compliance & Opportunity Discussion — USDOT #{dot_num} ({business_name})"
        email_text = ""

        system_instruction = custom_system_prompt or DEFAULT_SALES_AGENT_PROMPT

        # 1. Try Live Azure OpenAI Chat Completion call
        if self.ai_client:
            try:
                user_prompt = (
                    f"System Directives:\n{system_instruction}\n\n"
                    f"Draft a professional sales outreach email for carrier '{business_name}' (USDOT #{dot_num}).\n"
                    f"Mandated Opening Line (Include verbatim at start of email body):\n"
                    f"'{mandated_opening}'\n\n"
                    f"Context Details:\n"
                    f"- Company Name: {self.COMPANY_NAME}\n"
                    f"- Sales Representative Name: {rep_name}\n"
                    f"- Sales Representative Title: {rep_title}\n"
                    f"- Sales Territory / Area: {rep_region}\n"
                    f"- Representative Email: {rep_email}\n"
                    f"- Carrier Location: {city}, {state}\n"
                    f"- Out of Service Date: {oos_date}\n"
                    f"- OOS Reason: {reason}\n"
                    f"- Fleet Sizing: {vehicles} vehicles, {drivers} drivers\n"
                    f"- Focus Offering: {rep_offering}\n\n"
                    f"Draft a complete, consultative, professional outreach email body signed by {rep_name} from {self.COMPANY_NAME}."
                )

                response = self.ai_client.chat.completions.create(
                    model=self.deployment,
                    messages=[{"role": "user", "content": user_prompt}],
                    max_completion_tokens=2500
                )

                if response.choices and response.choices[0].message:
                    email_text = (response.choices[0].message.content or "").strip()
                    if email_text:
                        logger.info(f"[Azure OpenAI Agent] Live LLM email generated via model '{self.deployment}' for DOT #{dot_num}.")

            except Exception as e:
                logger.warning(f"[Azure OpenAI Agent] Live LLM call note: {e}. Fallback renderer activated.")

        # 2. Fallback Agent Template Renderer if live text is empty
        if not email_text:
            reason_lower = str(reason).lower()
            if "unsatisfactory" in reason_lower or "unfit" in reason_lower or "safety" in reason_lower:
                custom_solution = (
                    f"At {self.COMPANY_NAME}, we specialize in rapid fleet safety remediation and compliance consulting. "
                    f"Given your notice in {city}, {state}, our team can immediately dispatch mobile mechanics and supply "
                    f"fully compliant replacement vehicles ({vehicles} vehicles tracked in your fleet) to remediate violations."
                )
            elif "fine" in reason_lower or "pay" in reason_lower:
                custom_solution = (
                    f"We understand administrative delays can disrupt your routes. Through {self.COMPANY_NAME}'s "
                    f"'{rep_offering}' program, we provide short-term vehicle leases and legal compliance advisory "
                    f"to restore your USDOT operating status without capital strain."
                )
            else:
                custom_solution = (
                    f"With operations impacted in {city}, {state}, {self.COMPANY_NAME} offers turnkey asset substitution, "
                    f"DOT compliance audits, and priority maintenance support to return your fleet of {vehicles} vehicles to revenue service."
                )

            email_text = (
                f"{mandated_opening}\n\n"
                f"{custom_solution}\n\n"
                f"Would you be available for a brief 10-minute call this week to review how {self.COMPANY_NAME} can support your business?\n\n"
                f"Best regards,\n\n"
                f"{rep_name}\n"
                f"{rep_title} — {rep_region} Territory\n"
                f"🏢 {self.COMPANY_NAME} | Fleet Solutions Group\n"
                f"📧 {rep_email}"
            )

        return {
            "DOT_NUMBER": dot_num,
            "LEGAL_NAME": business_name,
            "SUBJECT": subject_line,
            "MANDATED_TEMPLATE": mandated_opening,
            "FULL_EMAIL_BODY": email_text,
            "SALESPERSON": rep_name,
            "SALES_REGION": rep_region,
            "COMPANY_NAME": self.COMPANY_NAME,
            "GENERATION_ENGINE": f"Azure OpenAI ({self.deployment})" if self.ai_client else f"{self.COMPANY_NAME} AI Agent"
        }

    def batch_generate_emails_for_selected_carriers(
        self,
        selected_carriers: List[Dict[str, Any]],
        salesperson_info: Dict[str, Any],
        custom_system_prompt: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Batch generate custom emails for multiple target selected carrier companies.
        """
        logger.info(f"[Azure AI Foundry Agent] Generating batch emails for {len(selected_carriers)} target carriers...")
        generated_emails = []
        for carrier in selected_carriers:
            email_payload = self.generate_custom_email_for_carrier(carrier, salesperson_info, custom_system_prompt)
            generated_emails.append(email_payload)
        return generated_emails


if __name__ == "__main__":
    foundry_agent = AzureFoundrySalesAgent()
    sample_carrier = {
        "DOT_NUMBER": 1438,
        "LEGAL_NAME": "AUSTIN URETHANE INC",
        "OOS_DATE": "2026-02-15",
        "OOS_REASON": "Unsatisfactory = Unfit",
        "PHY_CITY": "Austin",
        "PHY_STATE": "TX",
        "VEHICLE_TOTAL": 14
    }
    sample_rep = {
        "name": "John Doe",
        "title": "Southern Region Fleet Replacement Specialist",
        "region": "SOUTH",
        "email": "john.doe@carrierfix.com",
        "focus_offering": "Asset Replacement & Rapid Lease Program"
    }
    res = foundry_agent.generate_custom_email_for_carrier(sample_carrier, sample_rep)
    print("Company:", res["COMPANY_NAME"])
    print("Subject:", res["SUBJECT"])
    print("\nFull Email Body:\n", res["FULL_EMAIL_BODY"])
