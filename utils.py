"""
Azure Blob Storage Utility Module
=================================
Uploads raw and enriched dataset files to Azure Blob Storage containers
using credentials configured in .env (AZURE_STORAGE_CONNECTION_STRING,
CONTAINER_OOS_RAW, CONTAINER_OOS_ENRICHED).
"""

import os
import ssl
import urllib3
import logging
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError

# Disable SSL warnings for enterprise proxies if applicable
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings()

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AzureBlobUtility")


def get_blob_service_client() -> BlobServiceClient:
    """Initialize BlobServiceClient using AZURE_STORAGE_CONNECTION_STRING from .env."""
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING not found in .env")
    return BlobServiceClient.from_connection_string(connection_string, connection_verify=False)


def upload_file_to_blob(
    local_file_path: str,
    container_name: str | None = None,
    blob_name: str | None = None
) -> str:
    """
    Upload a local file to Azure Blob Storage.

    Parameters
    ----------
    local_file_path : str
        Path to the local file.
    container_name : str, optional
        Azure Blob container name. Defaults to CONTAINER_OOS_RAW from .env.
    blob_name : str, optional
        Name of the blob in Azure. Defaults to local filename.

    Returns
    -------
    str
        URL of the uploaded blob.
    """
    if not os.path.exists(local_file_path):
        raise FileNotFoundError(f"Local file not found: {local_file_path}")

    # Fallback to CONTAINER_OOS_RAW if container_name not specified
    if not container_name:
        container_name = os.getenv("CONTAINER_OOS_RAW", "oos-raw")

    if not blob_name:
        blob_name = os.path.basename(local_file_path)

    blob_service_client = get_blob_service_client()
    container_client = blob_service_client.get_container_client(container_name)

    try:
        container_client.create_container()
        logger.info(f"Created Azure Storage container: '{container_name}'")
    except ResourceExistsError:
        pass
    except Exception as e:
        logger.debug(f"Container exists note: {e}")

    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

    with open(local_file_path, "rb") as data:
        blob_client.upload_blob(data, overwrite=True)

    logger.info(f"Successfully uploaded '{local_file_path}' to container '{container_name}' -> Blob: {blob_client.url}")
    return blob_client.url


if __name__ == "__main__":
    test_file = "requirements.txt"
    if os.path.exists(test_file):
        url = upload_file_to_blob(test_file, container_name=os.getenv("CONTAINER_OOS_RAW", "oos-raw"))
        print("Uploaded Test File URL:", url)