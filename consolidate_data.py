"""
Consolidated Enriched OOS Dataset Consolidation Script
======================================================
Consolidates historical OOS records, daily OOS records, master carrier details cache,
and all batch ingestion files (enriched_batches and ooo_enriched_batches) into a single,
unified, standardized CSV dataset with maximum information per carrier.
"""

import os
import glob
import logging
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ConsolidateOOSData")

OUTPUT_CONSOLIDATED_FILE = "consolidated_enriched_oos.csv"


def clean_dot_number(val):
    """Normalize DOT numbers to clean string/int representations."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s.endswith('.0'):
        s = s[:-2]
    if s.isdigit():
        return int(s)
    return None


def sanitize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Uppercase column names and drop any duplicate columns within the DataFrame."""
    df.columns = [str(c).upper().strip() for c in df.columns]
    # Remove duplicated columns (keeps the first occurrence)
    df = df.loc[:, ~df.columns.duplicated(keep='first')].copy()
    return df


def consolidate():
    logger.info("Starting dataset consolidation across all batch and historical sources...")

    # ---------------------------------------------------------
    # 1. Ingest OOS Events (data/ooo.csv & daily/daily_ooo.csv)
    # ---------------------------------------------------------
    oos_records = []
    
    if os.path.exists("data/ooo.csv"):
        logger.info("Reading data/ooo.csv...")
        df_hist = pd.read_csv("data/ooo.csv", low_memory=False)
        df_hist = sanitize_dataframe_columns(df_hist)
        oos_records.append(df_hist)

    if os.path.exists("daily/daily_ooo.csv"):
        logger.info("Reading daily/daily_ooo.csv...")
        df_daily = pd.read_csv("daily/daily_ooo.csv", low_memory=False)
        df_daily = sanitize_dataframe_columns(df_daily)
        oos_records.append(df_daily)

    if oos_records:
        df_oos_all = pd.concat(oos_records, ignore_index=True, sort=False)
    else:
        df_oos_all = pd.DataFrame()

    logger.info(f"Total raw OOS event records loaded: {len(df_oos_all):,}")

    if not df_oos_all.empty:
        df_oos_all["DOT_NUMBER"] = df_oos_all["DOT_NUMBER"].apply(clean_dot_number)
        df_oos_all = df_oos_all.dropna(subset=["DOT_NUMBER"])
        df_oos_all["DOT_NUMBER"] = df_oos_all["DOT_NUMBER"].astype(int)

        # Calculate OOS Event Count per DOT_NUMBER
        event_counts = df_oos_all.groupby("DOT_NUMBER").size().to_dict()

        # Keep the latest OOS event record per carrier
        if "OOS_DATE" in df_oos_all.columns:
            df_oos_all["OOS_DATE_DT"] = pd.to_datetime(df_oos_all["OOS_DATE"], errors="coerce")
            df_oos_all = df_oos_all.sort_values(by=["OOS_DATE_DT"], ascending=False)
            df_oos_all = df_oos_all.drop(columns=["OOS_DATE_DT"])

        df_oos_unique = df_oos_all.drop_duplicates(subset=["DOT_NUMBER"], keep="first").copy()
        df_oos_unique["OOS_EVENT_COUNT"] = df_oos_unique["DOT_NUMBER"].map(event_counts)
    else:
        df_oos_unique = pd.DataFrame()

    logger.info(f"Unique OOS carriers identified: {len(df_oos_unique):,}")

    # ---------------------------------------------------------
    # 2. Ingest All Enriched Carrier Profile Sources
    # ---------------------------------------------------------
    enriched_dfs = []

    # A. Master cache: carrier_details.csv
    if os.path.exists("carrier_details.csv"):
        logger.info("Reading master cache carrier_details.csv...")
        cd = pd.read_csv("carrier_details.csv", low_memory=False)
        cd = sanitize_dataframe_columns(cd)
        enriched_dfs.append(cd)

    # B. Batch directories: enriched_batches/ & ooo_enriched_batches/
    for folder in ["enriched_batches", "ooo_enriched_batches"]:
        if os.path.exists(folder):
            batch_files = sorted(glob.glob(os.path.join(folder, "*.csv")))
            logger.info(f"Loading {len(batch_files)} batch files from {folder}/...")
            for bf in batch_files:
                try:
                    bdf = pd.read_csv(bf, low_memory=False)
                    bdf = sanitize_dataframe_columns(bdf)
                    enriched_dfs.append(bdf)
                except Exception as e:
                    logger.warning(f"Error loading batch file {bf}: {e}")

    if enriched_dfs:
        df_enriched_all = pd.concat(enriched_dfs, ignore_index=True, sort=False)
        logger.info(f"Total raw enriched records loaded across all batches: {len(df_enriched_all):,}")
        
        df_enriched_all = sanitize_dataframe_columns(df_enriched_all)
        
        df_enriched_all["DOT_NUMBER"] = df_enriched_all["DOT_NUMBER"].apply(clean_dot_number)
        df_enriched_all = df_enriched_all.dropna(subset=["DOT_NUMBER"])
        df_enriched_all["DOT_NUMBER"] = df_enriched_all["DOT_NUMBER"].astype(int)

        # Count non-null attributes per row to prioritize rows with maximum information
        df_enriched_all["NON_NULL_COUNT"] = df_enriched_all.notna().sum(axis=1)
        df_enriched_all = df_enriched_all.sort_values(by=["NON_NULL_COUNT"], ascending=False)
        df_enriched_unique = df_enriched_all.drop_duplicates(subset=["DOT_NUMBER"], keep="first").copy()
        df_enriched_unique = df_enriched_unique.drop(columns=["NON_NULL_COUNT"])
    else:
        df_enriched_unique = pd.DataFrame()

    logger.info(f"Unique enriched carrier profiles available: {len(df_enriched_unique):,}")

    # ---------------------------------------------------------
    # 3. Merge OOS Events and Enriched Profiles (Full Consolidation)
    # ---------------------------------------------------------
    if not df_oos_unique.empty and not df_enriched_unique.empty:
        merged_df = pd.merge(df_oos_unique, df_enriched_unique, on="DOT_NUMBER", how="outer", suffixes=("_OOS", "_PROFILE"))
    elif not df_oos_unique.empty:
        merged_df = df_oos_unique
    else:
        merged_df = df_enriched_unique

    # Combine duplicate columns created by merge (e.g. LEGAL_NAME_OOS vs LEGAL_NAME_PROFILE)
    target_columns = [
        "DOT_NUMBER", "LEGAL_NAME", "DBA_NAME", "OOS_DATE", "OOS_REASON", "STATUS", "RESCIND_DATE",
        "PHY_STREET", "PHY_CITY", "PHY_STATE", "PHY_ZIP", "MAILING_STREET", "MAILING_CITY", "MAILING_STATE", "MAILING_ZIP",
        "TELEPHONE", "FAX", "EMAIL", "CARRIER_OPERATION", "CARRIER_OPERATION_DESC", "ENTITY_TYPE",
        "OPERATING_STATUS", "OPERATING_STATUS_DESC", "USDOT_STATUS", "MCS150_DATE",
        "DRIVER_TOTAL", "VEHICLE_TOTAL", "OUT_OF_SERVICE_DATE", "SAFETY_RATING", "OOS_EVENT_COUNT"
    ]

    final_cols = {}
    for col in target_columns:
        if col in merged_df.columns:
            final_cols[col] = merged_df[col]
        elif f"{col}_PROFILE" in merged_df.columns and f"{col}_OOS" in merged_df.columns:
            final_cols[col] = merged_df[f"{col}_PROFILE"].combine_first(merged_df[f"{col}_OOS"])
        elif f"{col}_OOS" in merged_df.columns:
            final_cols[col] = merged_df[f"{col}_OOS"]
        elif f"{col}_PROFILE" in merged_df.columns:
            final_cols[col] = merged_df[f"{col}_PROFILE"]
        else:
            final_cols[col] = np.nan

    consolidated_df = pd.DataFrame(final_cols)

    # Clean data types
    consolidated_df["DOT_NUMBER"] = consolidated_df["DOT_NUMBER"].astype(int)
    
    # Enrich status indicator
    has_city = consolidated_df["PHY_CITY"].notna() | consolidated_df["MAILING_CITY"].notna()
    consolidated_df["ENRICHMENT_STATUS"] = np.where(has_city, "ENRICHED", "PENDING")

    # Sort by DOT_NUMBER
    consolidated_df = consolidated_df.sort_values(by="DOT_NUMBER", ascending=True)

    # Save to consolidated file
    consolidated_df.to_csv(OUTPUT_CONSOLIDATED_FILE, index=False)
    logger.info(f"SUCCESS: Consolidated dataset saved to '{OUTPUT_CONSOLIDATED_FILE}'.")
    logger.info(f"Final shape: {consolidated_df.shape[0]:,} rows x {consolidated_df.shape[1]} uniform columns.")
    
    return consolidated_df


if __name__ == "__main__":
    consolidate()
