"""
FMCSA Out-of-Service Data Connector
====================================
Fetches and normalizes Out-of-Service (OOS) carrier records from
data.transportation.gov (Socrata API dataset p2mt-9ige) with robust
offline local dataset fallback.
"""

import os
import io
import logging
import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FMCSADataConnector")


class FMCSADataConnector:
    """
    Connector to retrieve FMCSA Out of Service (OOS) inspection orders.
    """

    SOCRATA_OOS_URL = "https://data.transportation.gov/resource/p2mt-9ige.csv"
    LOCAL_DAILY_PATH = os.path.join("daily", "daily_ooo.csv")
    LOCAL_HISTORICAL_PATH = os.path.join("data", "ooo.csv")

    def __init__(self, use_live_api: bool = True):
        self.use_live_api = use_live_api

    def fetch_latest_oos_records(self, limit: int = 10, state_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch the most recent Out-of-Service carrier records.
        """
        df = None
        source_used = "Offline Dataset"

        if self.use_live_api:
            try:
                logger.info(f"Attempting live API fetch from {self.SOCRATA_OOS_URL}...")
                resp = requests.get(self.SOCRATA_OOS_URL, params={"$limit": 100, "$order": "inspection_date DESC"}, timeout=10)
                resp.raise_for_status()
                df = pd.read_csv(io.StringIO(resp.text))
                source_used = "Live FMCSA API (transportation.gov)"
                logger.info(f"Successfully fetched {len(df)} rows from live API.")
            except Exception as e:
                logger.warning(f"Live API fetch failed: {e}. Falling back to local offline data.")
                df = None

        if df is None:
            if os.path.exists(self.LOCAL_DAILY_PATH):
                logger.info(f"Loading local daily OOS file: {self.LOCAL_DAILY_PATH}")
                df = pd.read_csv(self.LOCAL_DAILY_PATH)
                source_used = "Local Daily CSV (daily/daily_ooo.csv)"
            elif os.path.exists(self.LOCAL_HISTORICAL_PATH):
                logger.info(f"Loading local historical OOS file: {self.LOCAL_HISTORICAL_PATH}")
                df = pd.read_csv(self.LOCAL_HISTORICAL_PATH)
                source_used = "Local Historical CSV (data/ooo.csv)"
            else:
                raise FileNotFoundError("No live API connection or local OOS CSV datasets found.")

        # Normalize column names to standard keys
        column_mapping = {
            'dot_number': 'DOT_NUMBER',
            'legal_name': 'LEGAL_NAME',
            'dba_name': 'DBA_NAME',
            'oos_date': 'OOS_DATE',
            'oos_reason': 'OOS_REASON',
            'status': 'STATUS',
            'rescind_date': 'RESCIND_DATE'
        }
        df = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

        # Filter by OOS indicator if column exists
        if 'oos_indicator' in df.columns:
            df = df[df['oos_indicator'] == 'Y']

        # Ensure DOT_NUMBER is clean
        if 'DOT_NUMBER' in df.columns:
            df['DOT_NUMBER'] = pd.to_numeric(df['DOT_NUMBER'], errors='coerce')
            df = df.dropna(subset=['DOT_NUMBER'])
            df['DOT_NUMBER'] = df['DOT_NUMBER'].astype(int)

        # Sort by OOS / Inspection Date if available
        date_col = 'OOS_DATE' if 'OOS_DATE' in df.columns else ('inspection_date' if 'inspection_date' in df.columns else None)
        if date_col and date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            df = df.sort_values(by=date_col, ascending=False)
            df[date_col] = df[date_col].dt.strftime('%Y-%m-%d')

        records = df.head(limit).to_dict(orient='records')
        
        # Annotate record source metadata
        for record in records:
            record['DATA_SOURCE'] = source_used

        logger.info(f"Retrieved {len(records)} OOS carrier records via {source_used}.")
        return records


if __name__ == "__main__":
    connector = FMCSADataConnector(use_live_api=False)
    latest = connector.fetch_latest_oos_records(limit=5)
    print(f"Fetched {len(latest)} records.")
