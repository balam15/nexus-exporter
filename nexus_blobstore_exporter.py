import os
import time
import requests
from prometheus_client import start_http_server, Gauge
from datetime import datetime, timezone

# Env config
NEXUS_URL = os.getenv("NEXUS_URL")
NEXUS_USER = os.getenv("NEXUS_USER")
NEXUS_PASS = os.getenv("NEXUS_PASS")

# Blobstore metrics
blobstore_count = Gauge("nexus_blobstores_count", "Total number of blobstores")
blobstore_size = Gauge("nexus_blobstores_size_bytes", "Total size in bytes", ["name"])
blobstore_used = Gauge("nexus_blobstores_used_space_bytes", "Used space in bytes", ["name"])
blobstore_usage = Gauge("nexus_blobstores_usage_percent", "Blobstore usage percentage", ["name"])
blobstore_files = Gauge("nexus_blobstores_file_count", "Number of files (blobs) in blobstore", ["name"])

# Optional (repository-based)
repo_size = Gauge("nexus_repositories_size_bytes", "Total size of repository in bytes", ["name"])
repo_last_download_age = Gauge("nexus_repositories_last_download_age_day", "Average age in days since last download", ["name"])

# System health metrics
status_healthy = Gauge("nexus_status_check_healthy", "Nexus system component health status (1 = healthy)", ["component"])

def fetch_blobstores():
    url = f"{NEXUS_URL}/service/rest/v1/blobstores"
    try:
        resp = requests.get(url, auth=(NEXUS_USER, NEXUS_PASS), timeout=10)
        resp.raise_for_status()
        data = resp.json()

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

            print(f"🧊 Blobstore '{name}': used={total:.0f}, available={available:.0f}, usage={usage_percent:.2f}%")

    except Exception as e:
        print(f"❌ Error fetching blobstores: {e}")

def fetch_status_check():
    url = f"{NEXUS_URL}/service/rest/v1/status/check"
    try:
        resp = requests.get(url, auth=(NEXUS_USER, NEXUS_PASS), timeout=10)
        resp.raise_for_status()
        data = resp.json()

        for component, status in data.items():
            healthy = 1 if status.get("healthy") else 0
            status_healthy.labels(component=component).set(healthy)

            print(f"🔍 Status '{component}': healthy={healthy}")

    except Exception as e:
        print(f"❌ Error fetching status check: {e}")

def main():
    print("✅ Starting Nexus exporter on :9103/metrics")
    start_http_server(9103)
    while True:
        fetch_blobstores()
        fetch_status_check()
        # fetch_repositories()  # Uncomment if needed in future
        time.sleep(300)  # Collect every 5 minutes

if __name__ == "__main__":
    main()
