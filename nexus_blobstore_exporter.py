import os
import time
import requests
from prometheus_client import start_http_server, Gauge

NEXUS_URL = os.getenv("NEXUS_URL")
NEXUS_USER = os.getenv("NEXUS_USER")
NEXUS_PASS = os.getenv("NEXUS_PASS")

# Define Prometheus metrics
blobstore_count = Gauge("nexus_blobstores_count", "Total number of blobstores")
blobstore_size = Gauge("nexus_blobstores_size_bytes", "Total size in bytes", ["name"])
blobstore_used = Gauge("nexus_blobstores_used_space_bytes", "Used space in bytes", ["name"])
blobstore_usage = Gauge("nexus_blobstores_usage_percent", "Blobstore usage percentage", ["name"])
blobstore_files = Gauge("nexus_blobstores_file_count", "Number of files (blobs) in blobstore", ["name"])

def fetch_blobstores():
    url = f"{NEXUS_URL}/service/rest/v1/blobstores"
    try:
        response = requests.get(url, auth=(NEXUS_USER, NEXUS_PASS), timeout=10)
        response.raise_for_status()
        data = response.json()

        blobstore_count.set(len(data))
        for blob in data:
            name = blob["name"]
            total = float(blob.get("totalSizeInBytes", 0))
            available = float(blob.get("availableSpaceInBytes", 0))
            blob_count = float(blob.get("blobCount", 0))
            full = total + available
            usage_percent = (total / full * 100) if full > 0 else 0

            blobstore_size.labels(name).set(full)
            blobstore_used.labels(name).set(total)
            blobstore_usage.labels(name).set(usage_percent)
            blobstore_files.labels(name).set(blob_count)

    except Exception as e:
        print(f"❌ Error fetching blobstores: {e}")

if __name__ == "__main__":
    print("✅ Starting Nexus blobstore exporter on :9103/metrics")
    start_http_server(9103)
    while True:
        fetch_blobstores()
        time.sleep(30)
