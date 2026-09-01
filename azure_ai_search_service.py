"""
Azure AI Search Service
=======================
Connects to live Azure AI Search (endpoint, key, index from .env: AZURE_SEARCH_ENDPOINT,
AZURE_SEARCH_KEY, AZURE_SEARCH_INDEX="poc_oos_enriched").
Manages index creation, document indexing, and territory state filtered queries.
"""

import os
import ssl
import urllib3
import logging
import pandas as pd
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from child_agent_enrichment import CarrierEnrichmentChildAgent

ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings()

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AzureAISearchService")

# Azure Search SDK Imports
HAS_AZURE_SEARCH = False
try:
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        SearchIndex, SimpleField, SearchableField, SearchFieldDataType
    )
    from azure.core.credentials import AzureKeyCredential
    HAS_AZURE_SEARCH = True
except ImportError:
    HAS_AZURE_SEARCH = False


class AzureAISearchService:
    """
    Azure AI Search Client & Index Management Service.
    """

    def __init__(self):
        self.endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "https://wyn-p1-ai-search.search.windows.net")
        self.key = os.getenv("AZURE_SEARCH_KEY")
        self.index_name = os.getenv("AZURE_SEARCH_INDEX", "poc_oos_enriched")
        self.child_agent = CarrierEnrichmentChildAgent(use_live_api=False)
        self.search_client = None

        if HAS_AZURE_SEARCH and self.endpoint and self.key:
            try:
                self._ensure_index_exists()
                self.search_client = SearchClient(
                    endpoint=self.endpoint,
                    index_name=self.index_name,
                    credential=AzureKeyCredential(self.key),
                    connection_verify=False
                )
                logger.info(f"[Azure AI Search] Successfully connected to live search index '{self.index_name}' at {self.endpoint}.")
            except Exception as e:
                logger.warning(f"[Azure AI Search] Live search initialization warning: {e}")

    def _ensure_index_exists(self):
        """Create Azure AI Search Index if it does not exist."""
        try:
            index_client = SearchIndexClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.key),
                connection_verify=False
            )
            existing_indexes = list(index_client.list_index_names())
            if self.index_name not in existing_indexes:
                logger.info(f"[Azure AI Search] Index '{self.index_name}' not found. Creating index schema...")
                fields = [
                    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                    SimpleField(name="DOT_NUMBER", type=SearchFieldDataType.Int64, filterable=True, sortable=True),
                    SearchableField(name="LEGAL_NAME", type=SearchFieldDataType.String, filterable=True, sortable=True),
                    SearchableField(name="PHY_CITY", type=SearchFieldDataType.String, filterable=True, sortable=True),
                    SearchableField(name="PHY_STATE", type=SearchFieldDataType.String, filterable=True, sortable=True),
                    SimpleField(name="OOS_DATE", type=SearchFieldDataType.String, filterable=True, sortable=True),
                    SearchableField(name="OOS_REASON", type=SearchFieldDataType.String, filterable=True),
                    SimpleField(name="STATUS", type=SearchFieldDataType.String, filterable=True, sortable=True),
                    SimpleField(name="DRIVER_TOTAL", type=SearchFieldDataType.Int64, filterable=True, sortable=True),
                    SimpleField(name="VEHICLE_TOTAL", type=SearchFieldDataType.Int64, filterable=True, sortable=True)
                ]
                idx = SearchIndex(name=self.index_name, fields=fields)
                index_client.create_or_update_index(idx)
                logger.info(f"[Azure AI Search] Successfully created index '{self.index_name}'.")
        except Exception as e:
            logger.warning(f"[Azure AI Search] Index schema creation note: {e}")

    def index_enriched_records(self, raw_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich raw OOS records and ingest documents into live Azure AI Search index.
        """
        logger.info(f"[Azure AI Search] Indexing {len(raw_records)} documents into '{self.index_name}'...")
        documents = []

        for record in raw_records:
            dot_num = record.get("DOT_NUMBER")
            if not dot_num:
                continue

            enrichment = self.child_agent.enrich_carrier_by_dot(int(dot_num))
            city = enrichment.get("PHY_CITY") or record.get("PHY_CITY") or "Dallas"
            state = enrichment.get("PHY_STATE") or record.get("PHY_STATE") or "TX"

            doc = {
                "id": str(dot_num),
                "DOT_NUMBER": int(dot_num),
                "LEGAL_NAME": str(record.get("LEGAL_NAME", "UNKNOWN CARRIER")),
                "PHY_CITY": str(city),
                "PHY_STATE": str(state),
                "OOS_DATE": str(record.get("OOS_DATE", "2026-01-01")),
                "OOS_REASON": str(record.get("OOS_REASON", "Safety Fitness / Operational Order")),
                "STATUS": str(record.get("STATUS", "ACTIVE")).upper(),
                "DRIVER_TOTAL": int(enrichment.get("DRIVER_TOTAL") or 0),
                "VEHICLE_TOTAL": int(enrichment.get("VEHICLE_TOTAL") or 0)
            }
            documents.append(doc)

        # Ingest documents live to Azure AI Search if client available
        if self.search_client and documents:
            try:
                # Batch upload documents
                result = self.search_client.upload_documents(documents=documents)
                logger.info(f"[Azure AI Search] Successfully uploaded {len(result)} documents to live index '{self.index_name}'.")
            except Exception as e:
                logger.warning(f"[Azure AI Search] Live document upload warning: {e}")

        return documents

    def search_by_territory_states(
        self,
        territory_states: Optional[List[str]] = None,
        start_date: str = "2026-01-01",
        status: str = "ACTIVE",
        search_query: str = "*",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Query Azure AI Search index filtering by salesperson territory states,
        date >= 2026-01-01, and status == ACTIVE.
        """
        logger.info(f"[Azure AI Search] Searching '{self.index_name}' | States: {territory_states} | Date >= {start_date}")

        # 1. Try Live Azure AI Search query first
        if self.search_client:
            try:
                results_list = list(self.search_client.search(search_text=search_query, top=limit))
                if results_list:
                    results = [dict(doc) for doc in results_list]
                    logger.info(f"[Azure AI Search] Live query returned {len(results)} search documents!")
                    
                    # Apply territory state & date filter on retrieved docs
                    filtered = []
                    for doc in results:
                        st_val = str(doc.get("PHY_STATE", "")).upper().strip()
                        stat_val = str(doc.get("STATUS", "")).upper().strip()
                        date_val = str(doc.get("OOS_DATE", ""))
                        
                        state_ok = True if not territory_states else st_val in [s.upper() for s in territory_states]
                        status_ok = True if status == "ALL" else stat_val == status.upper()
                        date_ok = date_val >= start_date
                        
                        if state_ok and status_ok and date_ok:
                            doc["SEARCH_SOURCE"] = f"Live Azure AI Search Index ({self.index_name})"
                            filtered.append(doc)

                    if filtered:
                        return filtered
            except Exception as e:
                logger.warning(f"[Azure AI Search] Live search query note: {e}")

        # 2. Fallback to local master consolidated dataset
        if os.path.exists("consolidated_enriched_oos.csv"):
            df = pd.read_csv("consolidated_enriched_oos.csv", low_memory=False)
        else:
            return []

        if df.empty:
            return []

        if 'STATUS' in df.columns and status != "ALL":
            df = df[df['STATUS'].astype(str).str.upper() == status.upper()]

        if 'OOS_DATE' in df.columns:
            df['OOS_DATE_DT'] = pd.to_datetime(df['OOS_DATE'], errors='coerce')
            df = df[df['OOS_DATE_DT'] >= pd.to_datetime(start_date)]
            df = df.sort_values(by='OOS_DATE_DT', ascending=False)
            df['OOS_DATE'] = df['OOS_DATE_DT'].dt.strftime('%Y-%m-%d')
            df = df.drop(columns=['OOS_DATE_DT'])

        if 'PHY_STATE' in df.columns and territory_states:
            territory_clean = [s.strip().upper() for s in territory_states]
            df['PHY_STATE_CLEAN'] = df['PHY_STATE'].astype(str).str.strip().str.upper()
            df = df[df['PHY_STATE_CLEAN'].isin(territory_clean)]

        if search_query and search_query != "*":
            q_clean = search_query.strip().lower()
            df = df[
                df['LEGAL_NAME'].astype(str).str.lower().str.contains(q_clean) |
                df['PHY_CITY'].astype(str).str.lower().str.contains(q_clean) |
                df['OOS_REASON'].astype(str).str.lower().str.contains(q_clean)
            ]

        results = df.head(limit).to_dict(orient='records')
        for r in results:
            r["SEARCH_SOURCE"] = "Master Consolidated Cache (Azure Sync Pending)"
        return results


if __name__ == "__main__":
    search_service = AzureAISearchService()
    res = search_service.search_by_territory_states(territory_states=["TX", "FL", "IL"], start_date="2026-01-01")
    print(f"Azure Search Results Returned: {len(res)}")
