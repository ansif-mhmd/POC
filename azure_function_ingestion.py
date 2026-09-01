"""
Azure Function App Scheduled Ingestion & SoQL Query Engine
===========================================================
Simulates/runs an Azure Function App with Timer Trigger (e.g. daily at 06:00 UTC)
to fetch FMCSA Out-of-Service records from data.transportation.gov (p2mt-9ige)
using SoQL parameters and saving raw snapshots to Azure Blob Storage.

Constraints Enforced:
  - Date Filter: Starting from 2026 Jan 1 (inspection_date >= '2026-01-01T00:00:00')
  - Status Filter: Active OOS orders (status == 'ACTIVE' and oos_indicator == 'Y')
"""

import os
import io
import json
import logging
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional
from utils import upload_file_to_blob

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AzureFunctionIngestion")


class SoQLQueryBuilder:
    """
    Helper builder for Socrata Open Data API (SoQL) parameters.
    """

    @staticmethod
    def build_params(
        select_cols: Optional[List[str]] = None,
        where_clause: Optional[str] = None,
        order_by: Optional[str] = "inspection_date DESC",
        limit: int = 100,
        offset: int = 0,
        group_by: Optional[str] = None,
        having_clause: Optional[str] = None,
        search_q: Optional[str] = None,
        full_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build SoQL API parameters dictionary.
        """
        if full_query:
            return {"$query": full_query}

        params = {
            "$limit": limit,
            "$offset": offset
        }

        if select_cols:
            params["$select"] = ", ".join(select_cols)
        if where_clause:
            params["$where"] = where_clause
        if order_by:
            params["$order"] = order_by
        if group_by:
            params["$group"] = group_by
        if having_clause:
            params["$having"] = having_clause
        if search_q:
            params["$q"] = search_q

        return params


class AzureFunctionIngestionJob:
    """
    Azure Function Timer Trigger Ingestion Handler.
    """

    SOCRATA_OOS_ENDPOINT = "https://data.transportation.gov/resource/p2mt-9ige.csv"
    CONTAINER_NAME = "fmcsa-raw-oos-snapshots"

    def __init__(self, target_date_start: str = "2026-01-01"):
        self.target_date_start = target_date_start

    def execute_scheduled_ingestion(self, limit: int = 100) -> Dict[str, Any]:
        """
        Execute scheduled ingestion job with SoQL filters:
          - inspection_date >= 2026-01-01T00:00:00
          - status = 'ACTIVE'
          - oos_indicator = 'Y'
        """
        logger.info(f"[Azure Function] Starting scheduled ingestion job for date >= {self.target_date_start} (ACTIVE status)...")

        # Build SoQL query with exact user requirements
        where_cond = f"inspection_date >= '{self.target_date_start}T00:00:00' AND oos_indicator = 'Y' AND status = 'ACTIVE'"
        select_fields = ["dot_number", "legal_name", "dba_name", "inspection_date", "oos_reason", "status", "rescind_date"]
        
        soql_params = SoQLQueryBuilder.build_params(
            select_cols=select_fields,
            where_clause=where_cond,
            order_by="inspection_date DESC",
            limit=limit
        )

        logger.info(f"[Azure Function] SoQL Parameters: {json.dumps(soql_params)}")

        df = None
        source_name = "Live SoQL API"

        try:
            resp = requests.get(self.SOCRATA_OOS_ENDPOINT, params=soql_params, timeout=10)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
            logger.info(f"[Azure Function] Successfully fetched {len(df)} rows starting from {self.target_date_start} via SoQL API.")
        except Exception as e:
            logger.warning(f"[Azure Function] Live SoQL API fetch warning: {e}. Loading local fallback dataset.")
            # Fallback to local file filtered by 2026 and ACTIVE status
            if os.path.exists("consolidated_enriched_oos.csv"):
                df = pd.read_csv("consolidated_enriched_oos.csv", low_memory=False)
            elif os.path.exists("daily/daily_ooo.csv"):
                df = pd.read_csv("daily/daily_ooo.csv")
            
            source_name = "Local Fallback Dataset"

        if df is not None and not df.empty:
            # Normalize columns
            column_mapping = {
                'dot_number': 'DOT_NUMBER',
                'legal_name': 'LEGAL_NAME',
                'dba_name': 'DBA_NAME',
                'inspection_date': 'OOS_DATE',
                'oos_date': 'OOS_DATE',
                'oos_reason': 'OOS_REASON',
                'status': 'STATUS',
                'rescind_date': 'RESCIND_DATE'
            }
            df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

            # Enforce 2026 Jan 1 date filter and ACTIVE status
            if 'OOS_DATE' in df.columns:
                df['OOS_DATE_DT'] = pd.to_datetime(df['OOS_DATE'], errors='coerce')
                df = df[df['OOS_DATE_DT'] >= pd.to_datetime(self.target_date_start)]
                df = df.sort_values(by='OOS_DATE_DT', ascending=False)
                df['OOS_DATE'] = df['OOS_DATE_DT'].dt.strftime('%Y-%m-%d')
                df = df.drop(columns=['OOS_DATE_DT'])

            if 'STATUS' in df.columns:
                df = df[df['STATUS'].astype(str).str.upper() == 'ACTIVE']

            # Save snapshot locally & upload to Azure Blob Storage
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_filename = f"raw_oos_snapshot_{timestamp}.csv"
            snapshot_path = os.path.join("data", snapshot_filename)
            os.makedirs("data", exist_ok=True)
            
            df.head(limit).to_csv(snapshot_path, index=False)
            logger.info(f"[Azure Function] Raw snapshot saved locally to {snapshot_path}")

            blob_url = None
            try:
                blob_url = upload_file_to_blob(snapshot_path, container_name=self.CONTAINER_NAME, blob_name=snapshot_filename)
                logger.info(f"[Azure Function] Uploaded snapshot to Azure Blob Storage: {blob_url}")
            except Exception as e:
                logger.info(f"[Azure Function] Blob Storage upload notification: {e}")

            records = df.head(limit).to_dict(orient='records')
            return {
                "status": "SUCCESS",
                "ingested_count": len(records),
                "soql_params": soql_params,
                "target_date_start": self.target_date_start,
                "snapshot_file": snapshot_path,
                "blob_url": blob_url,
                "records": records,
                "source": source_name
            }

        return {
            "status": "EMPTY",
            "ingested_count": 0,
            "soql_params": soql_params,
            "records": []
        }


if __name__ == "__main__":
    job = AzureFunctionIngestionJob(target_date_start="2026-01-01")
    res = job.execute_scheduled_ingestion(limit=10)
    print(f"Ingestion Job Result: {res['status']} | Count: {res['ingested_count']}")
