"""
Carrier Fix — Commercial Fleet Sales & Regional Analytics Portal
=================================================================
Company Name: Carrier Fix
Executive Portal Features:
 1. 📊 Regional Analytics Dashboard: OOS counts by territory (MIDWEST, SOUTH, WEST, NORTHEAST).
 2. 🎯 Sales Representative Portal: Screen 1 territory opportunities & Azure OpenAI email generator.
 3. 🔐 Sidebar Admin Authentication: Protected System Prompts Inspector & Pipeline Trigger.
"""

import os
import io
import time
import json
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from azure_function_ingestion import AzureFunctionIngestionJob
from azure_ai_search_service import AzureAISearchService
from azure_foundry_agent import (
    AzureFoundrySalesAgent,
    DEFAULT_SALES_AGENT_PROMPT,
    DEFAULT_ENRICHMENT_AGENT_PROMPT,
    DEFAULT_TERRITORY_MAPPER_PROMPT
)

# Page Configuration
st.set_page_config(
    page_title="Carrier Fix | Executive Portal",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# PREDEFINED SALES REPRESENTATIVE DIRECTORY & TERRITORIES (CARRIER FIX)
# ---------------------------------------------------------------------------
SALES_REPS = {
    "Sarah Connor (Midwest)": {
        "name": "Sarah Connor",
        "email": "sarah.connor@carrierfix.com",
        "title": "Midwest Enterprise Account Executive",
        "region": "MIDWEST",
        "states": ["IL", "IN", "MI", "OH", "WI", "MO", "IA", "MN", "ND", "SD", "NE", "KS"],
        "avatar": "👩‍💼",
        "focus_offering": "Fleet Compliance & Maintenance Support"
    },
    "John Doe (South)": {
        "name": "John Doe",
        "email": "john.doe@carrierfix.com",
        "title": "Southern Region Fleet Replacement Specialist",
        "region": "SOUTH",
        "states": ["TX", "OK", "AR", "LA", "MS", "AL", "TN", "GA", "FL", "NC", "SC"],
        "avatar": "👨‍💼",
        "focus_offering": "Asset Replacement & Rapid Lease Program"
    },
    "Alex Rivera (West)": {
        "name": "Alex Rivera",
        "email": "alex.rivera@carrierfix.com",
        "title": "West Coast Territory Director",
        "region": "WEST",
        "states": ["CA", "OR", "WA", "AZ", "NV", "ID", "UT", "CO", "NM", "MT", "WY", "AK", "HI"],
        "avatar": "👨‍💻",
        "focus_offering": "FMCSA Regulatory Compliance & Asset Leasing"
    },
    "Emily Taylor (Northeast)": {
        "name": "Emily Taylor",
        "email": "emily.taylor@carrierfix.com",
        "title": "Northeast Commercial Solutions Rep",
        "region": "NORTHEAST",
        "states": ["NY", "PA", "NJ", "MA", "CT", "RI", "VT", "NH", "ME", "DE", "MD", "VA", "WV"],
        "avatar": "👩‍💻",
        "focus_offering": "Turnkey Maintenance & Fleet Safety Consulting"
    }
}

VALID_TERRITORIES = ["MIDWEST", "SOUTH", "WEST", "NORTHEAST"]

STATE_TO_REGION = {}
for r_key, r_info in SALES_REPS.items():
    for st_code in r_info['states']:
        STATE_TO_REGION[st_code] = r_info['region']

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")


# Initialize Services
@st.cache_resource
def get_cloud_services():
    ingestion_job = AzureFunctionIngestionJob(target_date_start="2026-01-01")
    search_service = AzureAISearchService()
    foundry_agent = AzureFoundrySalesAgent()
    return ingestion_job, search_service, foundry_agent


# ---------------------------------------------------------------------------
# STREAMLIT UI IMPLEMENTATION
# ---------------------------------------------------------------------------
def main():
    ingestion_job, search_service, foundry_agent = get_cloud_services()

    # Initialize System Prompts in Session State
    if 'prompt_sales_agent' not in st.session_state:
        st.session_state['prompt_sales_agent'] = DEFAULT_SALES_AGENT_PROMPT
    if 'prompt_enrichment_agent' not in st.session_state:
        st.session_state['prompt_enrichment_agent'] = DEFAULT_ENRICHMENT_AGENT_PROMPT
    if 'prompt_territory_agent' not in st.session_state:
        st.session_state['prompt_territory_agent'] = DEFAULT_TERRITORY_MAPPER_PROMPT
    if 'admin_logged_in' not in st.session_state:
        st.session_state['admin_logged_in'] = False

    # --- SIDEBAR: SALESPERSON LOGIN ---
    st.sidebar.image("https://img.icons8.com/color/96/wrench.png", width=60)
    st.sidebar.title("Carrier Fix Portal")
    
    selected_rep_key = st.sidebar.selectbox(
        "👤 Select Active Profile:",
        options=list(SALES_REPS.keys()),
        index=0
    )
    rep = SALES_REPS[selected_rep_key]

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"### {rep['avatar']} {rep['name']}")
    st.sidebar.caption(f"**Title**: {rep['title']}")
    st.sidebar.caption(f"**Company**: Carrier Fix")
    st.sidebar.caption(f"**Email**: `{rep['email']}`")
    st.sidebar.markdown(f"**Territory Area**: `{rep['region']}`")
    st.sidebar.markdown(f"**Covered States ({len(rep['states'])}):**")
    st.sidebar.info(", ".join(rep["states"]))

    st.sidebar.markdown("---")

    # --- SIDEBAR: PROTECTED ADMIN LOGIN ---
    st.sidebar.markdown("### 🔐 Admin Console")
    
    if not st.session_state['admin_logged_in']:
        with st.sidebar.expander("🔑 Admin Login Required", expanded=False):
            input_user = st.text_input("Username:", key="admin_user_input")
            input_pass = st.text_input("Password:", type="password", key="admin_pass_input")
            if st.button("Log In as Admin", use_container_width=True):
                if input_user == ADMIN_USERNAME and input_pass == ADMIN_PASSWORD:
                    st.session_state['admin_logged_in'] = True
                    st.success("Admin Authenticated!")
                    st.rerun()
                else:
                    st.error("Invalid Username or Password.")
    else:
        st.sidebar.success("Logged in as Admin ✅")
        if st.sidebar.button("Log Out Admin", use_container_width=True):
            st.session_state['admin_logged_in'] = False
            st.rerun()

        st.sidebar.markdown("---")
        st.sidebar.markdown("#### ⚙️ Admin System Controls")
        
        # Pipeline Trigger
        if st.sidebar.button("⚡ Run Scheduled 4-Step Pipeline", use_container_width=True, type="primary"):
            from run_scheduled_job import execute_pipeline
            with st.sidebar.status("Executing 4-Step Azure Pipeline..."):
                res = execute_pipeline()
                st.sidebar.success(
                    f"✅ Pipeline Completed! "
                    f"Raw -> 'oos-raw' | Enriched -> 'oos-enriched' | AI Search -> Indexed ({res.get('indexed_count', 0)} docs)"
                )
                st.cache_data.clear()
                if 'generated_campaigns' in st.session_state:
                    del st.session_state['generated_campaigns']
                st.rerun()

        # System Prompts Editor Expander
        with st.sidebar.expander("📝 Modify Agent System Prompts", expanded=False):
            st.markdown("**1. Sales Outreach Agent Prompt**")
            p_sales = st.text_area("Sales Prompt:", value=st.session_state['prompt_sales_agent'], height=130, key="sb_prompt_sales")
            if p_sales != st.session_state['prompt_sales_agent']:
                st.session_state['prompt_sales_agent'] = p_sales

            st.markdown("**2. Carrier Enrichment Agent Prompt**")
            p_enr = st.text_area("Enrichment Prompt:", value=st.session_state['prompt_enrichment_agent'], height=100, key="sb_prompt_enr")
            if p_enr != st.session_state['prompt_enrichment_agent']:
                st.session_state['prompt_enrichment_agent'] = p_enr

            st.markdown("**3. Territory Agent Prompt**")
            p_terr = st.text_area("Territory Prompt:", value=st.session_state['prompt_territory_agent'], height=100, key="sb_prompt_terr")
            if p_terr != st.session_state['prompt_territory_agent']:
                st.session_state['prompt_territory_agent'] = p_terr

            if st.button("Reset Prompts to Default", use_container_width=True):
                st.session_state['prompt_sales_agent'] = DEFAULT_SALES_AGENT_PROMPT
                st.session_state['prompt_enrichment_agent'] = DEFAULT_ENRICHMENT_AGENT_PROMPT
                st.session_state['prompt_territory_agent'] = DEFAULT_TERRITORY_MAPPER_PROMPT
                st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Refresh View & Reset Cache", use_container_width=True):
        st.cache_data.clear()
        if 'generated_campaigns' in st.session_state:
            del st.session_state['generated_campaigns']
        st.rerun()

    # --- MAIN NAVIGATION TABS ---
    tab_dashboard, tab_sales = st.tabs([
        "📊 Regional OOS Analytics Dashboard",
        "🎯 Sales Representative Portal"
    ])

    # Load Master Dataset for Dashboard
    df_master = pd.DataFrame()
    if os.path.exists("consolidated_enriched_oos.csv"):
        df_master = pd.read_csv("consolidated_enriched_oos.csv", low_memory=False)

    # ---------------------------------------------------------------------------
    # TAB 1: REGIONAL OOS ANALYTICS DASHBOARD (EXCLUDING OTHER/INTERNATIONAL)
    # ---------------------------------------------------------------------------
    with tab_dashboard:
        st.title("📊 Out-of-Service Regional Analytics Dashboard")
        st.caption("Insights on Out-of-Service (OOS) filings across sales territories based on the latest data fetch.")

        if df_master.empty:
            st.warning("No master dataset found. Run scheduled pipeline in admin console to fetch latest data.")
        else:
            # Map Region
            df_dash = df_master.copy()
            df_dash['PHY_STATE_CLEAN'] = df_dash['PHY_STATE'].astype(str).str.strip().str.upper()
            df_dash['REGION'] = df_dash['PHY_STATE_CLEAN'].map(STATE_TO_REGION)

            # FILTER OUT OTHER / INTERNATIONAL (STRICTLY VALID TERRITORIES)
            df_dash = df_dash[df_dash['REGION'].isin(VALID_TERRITORIES)]

            # Filter for 2026 ACTIVE
            if 'OOS_DATE' in df_dash.columns:
                df_dash['OOS_DATE_DT'] = pd.to_datetime(df_dash['OOS_DATE'], errors='coerce')
                df_dash_2026 = df_dash[df_dash['OOS_DATE_DT'] >= pd.to_datetime('2026-01-01')]
            else:
                df_dash_2026 = df_dash

            if 'STATUS' in df_dash_2026.columns:
                df_dash_active = df_dash_2026[df_dash_2026['STATUS'].astype(str).str.upper() == 'ACTIVE']
            else:
                df_dash_active = df_dash_2026

            # Metrics
            d1, d2, d3, d4 = st.columns(4)
            d1.metric("Territory OOS Carriers (2026 Active)", f"{len(df_dash_active):,}")
            
            top_reg = df_dash_active['REGION'].value_counts().idxmax() if not df_dash_active.empty else "N/A"
            d2.metric("Highest OOS Volume Region", top_reg)

            tot_vehicles = int(df_dash_active['VEHICLE_TOTAL'].fillna(0).sum()) if 'VEHICLE_TOTAL' in df_dash_active.columns else 0
            d3.metric("Impacted Fleet Vehicles", f"{tot_vehicles:,}")

            tot_drivers = int(df_dash_active['DRIVER_TOTAL'].fillna(0).sum()) if 'DRIVER_TOTAL' in df_dash_active.columns else 0
            d4.metric("Impacted Fleet Drivers", f"{tot_drivers:,}")

            st.markdown("---")

            # Region Breakdown Bar Chart & Table (STRICTLY MIDWEST, SOUTH, WEST, NORTHEAST)
            col_d1, col_d2 = st.columns([3, 2])
            with col_d1:
                st.markdown("#### 🗺️ Out-of-Service Carrier Filings by Sales Territory (2026 Active)")
                
                # Enforce strictly 4 territory rows even if zero count
                reg_counts_dict = {reg: 0 for reg in VALID_TERRITORIES}
                actual_counts = df_dash_active['REGION'].value_counts().to_dict()
                reg_counts_dict.update(actual_counts)
                
                region_counts = pd.DataFrame(list(reg_counts_dict.items()), columns=['Sales Territory', 'OOS Carrier Count'])
                region_counts = region_counts.sort_values(by='OOS Carrier Count', ascending=False)
                
                st.bar_chart(region_counts.set_index('Sales Territory'))

            with col_d2:
                st.markdown("#### 📋 Regional Distribution Table")
                st.dataframe(region_counts, use_container_width=True, hide_index=True)

            st.markdown("---")

            # Top Violation Reasons & Fleet Impact
            col_v1, col_v2 = st.columns(2)
            with col_v1:
                st.markdown("#### ⚠️ Top 5 Out-of-Service Violation Reasons")
                if 'OOS_REASON' in df_dash_active.columns:
                    top_reasons = df_dash_active['OOS_REASON'].value_counts().head(5).reset_index()
                    top_reasons.columns = ['Violation Reason', 'Count']
                    st.dataframe(top_reasons, use_container_width=True, hide_index=True)

            with col_v2:
                st.markdown("#### 🚛 Fleet Impact Metrics by Sales Territory")
                if 'VEHICLE_TOTAL' in df_dash_active.columns and 'DRIVER_TOTAL' in df_dash_active.columns:
                    fleet_summary = df_dash_active.groupby('REGION')[['VEHICLE_TOTAL', 'DRIVER_TOTAL']].sum().reset_index()
                    fleet_summary.columns = ['Sales Territory', 'Total Vehicles', 'Total Drivers']
                    st.dataframe(fleet_summary, use_container_width=True, hide_index=True)

    # ---------------------------------------------------------------------------
    # TAB 2: SALES REPRESENTATIVE PORTAL & EMAIL GENERATOR
    # ---------------------------------------------------------------------------
    with tab_sales:
        st.title("🛠️ Carrier Fix — Out-of-Service Opportunity Portal")
        st.caption("Identify Out-of-Service motor carriers in your territory and generate custom sales outreach email drafts.")

        st.markdown(f"### 📍 Out-of-Service Carrier Opportunities — {rep['region']} Area")
        
        col_s1, col_s2, col_s3 = st.columns([3, 2, 2])
        with col_s1:
            search_keyword = st.text_input("🔎 Search Carriers (Name, City, or Violation):", value="", placeholder="e.g. Austin, Trucking, Safety")
        with col_s2:
            filter_territory_only = st.checkbox("🎯 Show ONLY My Territory States", value=True)
        with col_s3:
            max_search_results = st.number_input("Max Leads Displayed:", min_value=5, max_value=100, value=25)

        # Query Search Service
        target_states = rep['states'] if filter_territory_only else None
        query_term = search_keyword.strip() if search_keyword.strip() else "*"
        
        search_results = search_service.search_by_territory_states(
            territory_states=target_states,
            start_date="2026-01-01",
            status="ACTIVE",
            search_query=query_term,
            limit=max_search_results
        )

        df_search = pd.DataFrame(search_results)

        m1, m2, m3 = st.columns(3)
        m1.metric("Available Territory Opportunities", len(df_search))
        m2.metric("Assigned Territory Area", rep['region'])
        m3.metric("Assigned Sales Executive", rep['name'])

        if df_search.empty:
            st.warning(f"No active out-of-service carrier opportunities found matching search filters for {rep['region']}.")
        else:
            st.markdown("---")
            st.markdown("### 🎯 Select Target Carriers to Generate AI Outreach Emails")
            st.caption("Check the box next to one or multiple carriers below, then click **Generate Custom AI Emails**.")

            df_search["SELECT"] = False
            display_columns = [
                "SELECT", "DOT_NUMBER", "LEGAL_NAME", "PHY_CITY", "PHY_STATE", "OOS_DATE",
                "OOS_REASON", "TELEPHONE", "EMAIL", "DRIVER_TOTAL", "VEHICLE_TOTAL"
            ]
            avail_cols = [c for c in display_columns if c in df_search.columns]

            edited_df = st.data_editor(
                df_search[avail_cols],
                column_config={
                    "SELECT": st.column_config.CheckboxColumn(
                        "Target?",
                        help="Select carrier to draft custom outreach email",
                        default=False
                    ),
                    "DOT_NUMBER": "USDOT #",
                    "LEGAL_NAME": "Carrier Company Name",
                    "PHY_CITY": "City",
                    "PHY_STATE": "State",
                    "OOS_DATE": "OOS Date",
                    "OOS_REASON": "OOS Violation Reason",
                    "TELEPHONE": "Phone Number",
                    "EMAIL": "Email Address",
                    "DRIVER_TOTAL": "Drivers",
                    "VEHICLE_TOTAL": "Vehicles"
                },
                disabled=[c for c in avail_cols if c != "SELECT"],
                hide_index=True,
                use_container_width=True,
                key="target_carriers_editor"
            )

            selected_carriers = edited_df[edited_df["SELECT"] == True].to_dict(orient="records")

            col_b1, col_b2 = st.columns([3, 2])
            with col_b1:
                st.info(f"Target Carriers Selected: **{len(selected_carriers)} company(ies)**")
            with col_b2:
                generate_email_btn = st.button(
                    f"✨ Generate Custom AI Emails ({len(selected_carriers)})",
                    type="primary",
                    disabled=(len(selected_carriers) == 0),
                    use_container_width=True
                )

            # Trigger Generation & Store in Session State
            if generate_email_btn and selected_carriers:
                with st.spinner(f"Carrier Fix AI Agent generating personalized outreach emails for {len(selected_carriers)} target carrier company(ies)..."):
                    campaigns = foundry_agent.batch_generate_emails_for_selected_carriers(
                        selected_carriers=selected_carriers,
                        salesperson_info=rep,
                        custom_system_prompt=st.session_state.get('prompt_sales_agent')
                    )
                    st.session_state['generated_campaigns'] = campaigns
                    st.session_state['gen_timestamp'] = int(time.time())

            # DISPLAY GENERATED CAMPAIGNS FROM SESSION STATE
            if 'generated_campaigns' in st.session_state and st.session_state['generated_campaigns']:
                campaigns = st.session_state['generated_campaigns']
                ts = st.session_state.get('gen_timestamp', int(time.time()))
                
                st.markdown(f"### 📧 Generated Sales Outreach Drafts ({len(campaigns)}) — Carrier Fix")
                
                for i, campaign in enumerate(campaigns, start=1):
                    company = campaign.get("LEGAL_NAME", "Carrier Company")
                    dot_num = campaign.get("DOT_NUMBER", "N/A")
                    subject = campaign.get("SUBJECT", "Urgent Fleet Support")
                    body_text = campaign.get("FULL_EMAIL_BODY", "").strip()

                    with st.container():
                        st.markdown(f"#### ✉️ Outreach Email #{i}: **{company}** (USDOT #{dot_num})")
                        st.markdown(f"**Subject Line**: `{subject}`")
                        
                        st.info(body_text)

                        st.text_area(
                            label=f"Edit Draft for {company}:",
                            value=body_text,
                            height=260,
                            key=f"ta_{dot_num}_{ts}_{i}"
                        )

                        col_e1, col_e2 = st.columns(2)
                        with col_e1:
                            st.download_button(
                                label=f"💾 Download Email Draft ({company})",
                                data=body_text,
                                file_name=f"carrierfix_email_dot_{dot_num}.txt",
                                mime="text/plain",
                                key=f"dl_btn_{dot_num}_{ts}_{i}"
                            )
                        with col_e2:
                            st.success(f"✅ Carrier Fix Draft Ready ({rep['name']} — {rep['region']} Territory)")
                        
                        st.markdown("---")


if __name__ == "__main__":
    main()
