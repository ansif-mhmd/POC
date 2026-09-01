# AI Expert Technical Assessment: Solution Design & Cloud Architecture Proposal

## Executive Summary
This document presents the revamped **Azure Cloud Architecture**, SoQL API ingestion pipeline, Azure AI Search indexing, and Microsoft Azure AI Foundry Agent integration for the **FMCSA Out-of-Service (OOS) Sales Opportunity AI Solution**.

---

# SECTION 1: ARCHITECTURE DESIGN

### 1. Purpose of the Agent & Primary Users
* **Primary Purpose**: To automatically ingest, enrich, index, and route Federal Motor Carrier Safety Administration (FMCSA) Out-of-Service (OOS) notices starting from **Jan 1, 2026** with **Active** status. The solution converts regulatory enforcement notices into actionable, high-conversion commercial sales opportunities.
* **Primary Users**:
  * **Sales Representatives & Account Executives**: Access Screen 1 to view territory-filtered OOS carriers from Azure AI Search and select target carriers for custom AI email generation.
  * **Sales Managers**: Require automated lead distribution, territory mapping, and pipeline tracking.
  * **Fleet Solutions Advisors**: Require context on carrier fleet size (`DRIVER_TOTAL`, `VEHICLE_TOTAL`), safety ratings, and specific OOS violation reasons.

### 2. Business Problem & Expected Outcomes
* **Business Problem**: When FMCSA issues an Out-of-Service order, a carrier is legally prohibited from operating its vehicles until safety or compliance issues are remediated. This creates urgent demand for replacement trucks, leasing, maintenance support, and compliance consulting.
* **Expected Outcome**:
  * **Speed-to-Lead**: Reduces lead discovery and email drafting time from weeks to seconds.
  * **Targeted Customization**: Employs Microsoft Azure AI Foundry Agents to generate custom outreach emails tailored to the specific OOS date, carrier location, fleet size, and violation context.
  * **Cost & Performance Optimization**: Implements SoQL query options and local lookup caching to minimize API costs and eliminate redundant lookups.

### 3. Data Sources & SoQL API Query Parameters
The Azure Function scheduled job queries the FMCSA Socrata API (`p2mt-9ige.csv`) utilizing standard SoQL query parameters:

| SoQL Option | Function & Purpose | Implementation Example |
| :--- | :--- | :--- |
| `$select` | Chooses specific columns for lean network bandwidth | `dot_number, legal_name, dba_name, inspection_date, oos_reason, status` |
| `$where` | Filters records by date and active status | `inspection_date >= '2026-01-01T00:00:00' AND oos_indicator = 'Y' AND status = 'ACTIVE'` |
| `$order` | Sorts results by recency | `inspection_date DESC` |
| `$limit` | Limits batch row count | `$limit=100` |
| `$offset` | Manages pagination | `$offset=0` |
| `$group` | Aggregates carriers by state | `$group=phy_state` |
| `$having` | Filters aggregated state counts | `$having=count(dot_number) > 10` |
| `$q` | Full-text search across legal names and cities | `$q=TRUCKING` |
| `$query` | Combines complete SoQL SELECT + WHERE + ORDER queries | Complete SoQL statement string |

---

### 4. End-to-End Azure Cloud Architecture

```mermaid
graph TD
    subgraph 1. Scheduled Ingestion Layer
        A["data.transportation.gov (p2mt-9ige)"] -->|SoQL Query: Date>=2026-01-01 & Status==ACTIVE| B[Azure Function App: Timer Trigger]
        B -->|Persist Raw Snapshot| C[(Azure Blob Storage: fmcsa-raw-oos-snapshots)]
    end

    subgraph 2. Enrichment & Search Indexing Layer
        B -->|Raw OOS Data| D[Child Agent Enrichment Microservice]
        D -->|Query az4n-8mr2 & consolidated_enriched_oos.csv| E[Enriched Carrier Profile]
        E -->|Ingest Search Documents| F[Azure AI Search Index: fmcsa-oos-index]
    end

    subgraph 3. User & Agent Interaction Layer (Streamlit App)
        F -->|Screen 1: Territory Filtered Search| G[Streamlit Cloud Portal]
        G -->|Salesperson Multi-Selects Target Carriers| H[Microsoft Azure AI Foundry Agent]
        H -->|Generate Custom Email Campaigns| I[Targeted Email Output & CRM Push]
    end
```

---

# SECTION 2: CUSTOM LLM AGENT & AZURE FOUNDRY RAG TASK

### 1. Large Language Model & Azure AI Foundry Selection
* **Selected Framework**: **Microsoft Azure AI Foundry** (`azure-ai-projects` & `azure-ai-agents` SDK) running **Azure OpenAI GPT-4o-mini** (for routine search parsing and structured extraction) and **GPT-4o** (for custom executive email generation).

### 2. Azure AI Foundry System Instructions
```text
System Prompt:
You are an Enterprise Sales AI Agent hosted on Azure AI Foundry.
Your task is to draft personalized, professional sales outreach emails to commercial motor carriers placed Out of Service (OOS) by FMCSA.

Rules:
1. Include the mandated business opening template:
   "Hi <Business Name>,
   I see your operations were recently impacted by an out-of-service notice dated <Out of Service Date>. Can we set up a call to discuss new sales opportunities?"
2. Tailor the secondary pitch specifically to the carrier's violation reason, fleet vehicle/driver total, city, state, and the salesperson's designated focus offering.
3. Keep tone consultative, urgent, helpful, and professional.
```

---

### 3. Step 5 & Step 6 Solution Demonstration

#### **Step 5: Screen 1 — Azure AI Search Results (Filtered by Salesperson Location)**
* **Logged-in Sales Rep**: Sarah Connor (Midwest Territory: `IL, IN, MI, OH, WI...`)
* **Applied Constraints**: Date $\ge$ **2026-01-01** | Status == **ACTIVE**

| USDOT # | Carrier Company | City, State | OOS Date | Violation Reason | Status | Fleet Units |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `176064` | **PACIFIC COMMERCIAL EQUIPMENT** | SNOHOMISH, WA | 2026-06-23 | Intrastate Out of Service | ACTIVE | 12 |
| `284408` | **CROSSTOWN TRANSPORTATION SERVICES INC** | KNIGHTDALE, NC | 2026-04-29 | Denial of Access | ACTIVE | 8 |
| `250267` | **LLOYD L GASKILL** | WILLCOX, AZ | 2026-03-31 | 90 day failure to pay fine | ACTIVE | 15 |

---

#### **Step 6: Target Carrier Multi-Selection & Custom AI Foundry Email Output**

```text
Subject: Urgent Fleet Support & Opportunity Discussion — USDOT #176064 (PACIFIC COMMERCIAL EQUIPMENT)

Hi PACIFIC COMMERCIAL EQUIPMENT,

I see your operations were recently impacted by an out-of-service notice dated 2026-06-23. Can we set up a call to discuss new sales opportunities?

Given that your notice relates to safety fitness and inspection compliance in SNOHOMISH, WA, our team can immediately dispatch certified mobile fleet technicians and supply fully compliant replacement power units (12 vehicles tracked in your fleet) to remediate violations.

Would you have 10 minutes this week for a brief call to explore how we can support your business?

Best regards,

Sarah Connor
Midwest Enterprise Account Executive — MIDWEST
📧 sarah.connor@fleet-solutions.com | Fleet Solutions Group
```

---

# SECTION 3: PRODUCTION DEPLOYMENT & COST GOVERNANCE

1. **Scheduled Ingestion**: Azure Function Timer Trigger running daily at 06:00 UTC with SoQL query parameters (`$select`, `$where`, `$order`, `$limit`).
2. **Blob Storage Archival**: Raw snapshots stored in `fmcsa-raw-oos-snapshots` container for compliance auditability.
3. **Azure AI Search Indexing**: Vector/keyword hybrid search index (`fmcsa-oos-index`) refreshed daily.
4. **Azure AI Foundry Agents**: Scalable agent runtime with Managed Identity authentication and prompt safety guardrails.
5. **Cost Optimization**: 95%+ API cost savings by using local lookup CSV caching and SoQL `$select` parameter filtering.
