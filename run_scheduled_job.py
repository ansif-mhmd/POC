"""
Azure Web App Scheduled Raw Fetch, Blob Storage, Enrichment & AI Search Pipeline
==================================================================================
This pipeline executes automatically inside your deployed Azure Web App:
 1. Scheduled Raw Data Fetch (SoQL: Date >= 2026-01-01 & status == ACTIVE).
 2. Store Raw Data to Azure Blob Storage container 'oos-raw'.
 3. Enrich Data via Child Agent and store enriched dataset to container 'oos-enriched'.
 4. Ingest Enriched Data into Azure AI Search index 'poc_oos_enriched'.

Usage:
  python run_scheduled_job.py          Execute complete 4-step pipeline once
  python run_scheduled_job.py --loop   Run continuously on a 24-hour background timer
"""

import os
import sys
import time
import pandas as pd
import argparse
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AzureWebAppPipeline")

from azure_function_ingestion import AzureFunctionIngestionJob
from child_agent_enrichment import CarrierEnrichmentChildAgent
from azure_ai_search_service import AzureAISearchService
from utils import upload_file_to_blob


def execute_pipeline() -> dict:
    """
    Executes the complete 4-step Azure Web App data pipeline.
    """
    logger.info("==========================================================================")
    logger.info(" 🚀 STARTING AZURE WEB APP SCHEDULED PIPELINE")
    logger.info("==========================================================================")

    container_raw = os.getenv("CONTAINER_OOS_RAW", "oos-raw")
    container_enriched = os.getenv("CONTAINER_OOS_ENRICHED", "oos-enriched")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # STEP 1: Scheduled Raw Data Fetch (Date >= 2026-01-01 & status == ACTIVE)
    logger.info("[Step 1/4] Fetching raw OOS records starting from 2026-01-01 (ACTIVE status)...")
    ingestion_job = AzureFunctionIngestionJob(target_date_start="2026-01-01")
    ingest_result = ingestion_job.execute_scheduled_ingestion(limit=100)
    raw_records = ingest_result.get("records", [])

    if not raw_records:
        logger.warning("No raw OOS records fetched. Exiting pipeline run.")
        return {"status": "EMPTY"}

    # STEP 2: Store Raw Data to Azure Blob Storage ("oos-raw")
    logger.info(f"[Step 2/4] Uploading raw snapshot to Azure Blob Storage container '{container_raw}'...")
    raw_df = pd.DataFrame(raw_records)
    os.makedirs("data", exist_ok=True)
    raw_filename = f"raw_oos_snapshot_{timestamp}.csv"
    raw_path = os.path.join("data", raw_filename)
    raw_df.to_csv(raw_path, index=False)

    raw_blob_url = None
    try:
        raw_blob_url = upload_file_to_blob(raw_path, container_name=container_raw, blob_name=raw_filename)
        logger.info(f"Successfully uploaded raw data to Blob: {raw_blob_url}")
    except Exception as e:
        logger.warning(f"Raw Blob upload note: {e}")

    # STEP 3: Enrich Data & Store to Azure Blob Storage ("oos-enriched")
    logger.info(f"[Step 3/4] Enriching carrier data and uploading to container '{container_enriched}'...")
    child_agent = CarrierEnrichmentChildAgent(use_live_api=False)
    enriched_records = []

    for rec in raw_records:
        dot = rec.get("DOT_NUMBER")
        if dot:
            enr = child_agent.enrich_carrier_by_dot(int(dot))
            combined = {**rec, **enr}
            enriched_records.append(combined)

    enriched_df = pd.DataFrame(enriched_records)
    enriched_filename = f"enriched_oos_snapshot_{timestamp}.csv"
    enriched_path = os.path.join("data", enriched_filename)
    enriched_df.to_csv(enriched_path, index=False)

    enriched_blob_url = None
    try:
        enriched_blob_url = upload_file_to_blob(enriched_path, container_name=container_enriched, blob_name=enriched_filename)
        logger.info(f"Successfully uploaded enriched data to Blob: {enriched_blob_url}")
    except Exception as e:
        logger.warning(f"Enriched Blob upload note: {e}")

    # STEP 4: Ingest Enriched Data to Azure AI Search ("poc_oos_enriched")
    logger.info("[Step 4/4] Indexing enriched documents into Azure AI Search ('poc_oos_enriched')...")
    search_service = AzureAISearchService()
    indexed_docs = search_service.index_enriched_records(enriched_records)
    logger.info(f"Successfully indexed {len(indexed_docs)} documents into Azure AI Search.")

    logger.info("==========================================================================")
    logger.info(" ✅ AZURE WEB APP 4-STEP PIPELINE EXECUTION COMPLETE!")
    logger.info("==========================================================================\n")

    return {
        "status": "SUCCESS",
        "raw_count": len(raw_records),
        "enriched_count": len(enriched_records),
        "indexed_count": len(indexed_docs),
        "raw_blob_url": raw_blob_url,
        "enriched_blob_url": enriched_blob_url
    }


def main():
    parser = argparse.ArgumentParser(description="Azure Web App Scheduled Pipeline")
    parser.add_argument("--loop", action="store_true", help="Run continuously every 24 hours")
    parser.add_argument("--interval_hours", type=int, default=24, help="Schedule interval in hours")
    args = parser.parse_args()

    if args.loop:
        logger.info(f"Starting continuous Azure Web App background scheduler (Interval: {args.interval_hours}h)...")
        while True:
            try:
                execute_pipeline()
                time.sleep(args.interval_hours * 3600)
            except (KeyboardInterrupt, SystemExit):
                logger.info("Scheduler stopped by user.")
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}. Retrying in 1 hour...")
                time.sleep(3600)
    else:
        execute_pipeline()


if __name__ == "__main__":
    main()
