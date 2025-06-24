import os
import time
import requests
from prometheus_client import start_http_server, Gauge
from datetime import datetime, timezone

NEXUS_URL = os.getenv("NEXUS_URL")
NEXUS_USER = os.getenv("NEXUS_USER")
NEXUS_PASS = os.getenv("NEXUS_PASS")

# Blobstore metrics
blobstore_count = Gauge("nexus_blobstores_count", "Total number of blobstores")
blobstore_size = Gauge("nexus_blobstores_size_bytes", "Total size in bytes", ["name"])
blobstore_used = Gauge("nexus_blobstores_used_space_bytes", "Used space in bytes", ["name"])
blobstore_usage = Gauge("nexus_blobstores_usage_percent", "Blobstore usage percentage", ["name"])
blobstore_files = Gauge("nexus_blobstores_file_count", "Number of files (blobs) in blobstore", ["name"])

# Repository metrics
repo_size = Gauge("nexus_repositories_size_bytes", "Total size of repository in bytes", ["name"])
repo_last_download_age = Gauge("nexus_repositories_last_download_age_day", "Average age in days since last download", ["name"])

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

    except Exception as e:
        print(f"❌ Error fetching blobstores: {e}")

def fetch_repositories():
    # Kita akan kumpulkan size dan last download per repository dari /search/assets
    url = f"{NEXUS_URL}/service/rest/v1/repositories"
    try:
        resp = requests.get(url, auth=(NEXUS_USER, NEXUS_PASS), timeout=10)
        resp.raise_for_status()
        repos = resp.json()
    except Exception as e:
        print(f"❌ Error fetching repository list: {e}")
        return

    for repo in repos:
        repo_name = repo.get("name")
        if not repo_name:
            continue

        # Paging untuk assets dalam repo ini
        size_total = 0
        last_download_ages = []
        continuation_token = None

        while True:
            params = {}
            if continuation_token:
                params["continuationToken"] = continuation_token
            url_assets = f"{NEXUS_URL}/service/rest/v1/search/assets?repository={repo_name}"
            try:
                resp_assets = requests.get(url_assets, auth=(NEXUS_USER, NEXUS_PASS), params=params, timeout=10)
                resp_assets.raise_for_status()
                assets_data = resp_assets.json()
            except Exception as e:
                print(f"❌ Error fetching assets for repo {repo_name}: {e}")
                break

            items = assets_data.get("items", [])
            now = datetime.now(timezone.utc)
            for asset in items:
                size_total += asset.get("fileSize", 0)

                last_dl_str = asset.get("lastDownloaded")
                if last_dl_str:
                    try:
                        last_dl_time = datetime.fromisoformat(last_dl_str.rstrip('Z')).replace(tzinfo=timezone.utc)
                        age_days = (now - last_dl_time).total_seconds() / 86400
                        last_download_ages.append(age_days)
                    except Exception as e:
                        # skip parsing error
                        pass

            continuation_token = assets_data.get("continuationToken")
            if not continuation_token:
                break

        repo_size.labels(repo_name).set(size_total)
        if last_download_ages:
            avg_age = sum(last_download_ages) / len(last_download_ages)
            repo_last_download_age.labels(repo_name).set(avg_age)
        else:
            repo_last_download_age.labels(repo_name).set(0)

def main():
    print("✅ Starting Nexus exporter on :9103/metrics")
    start_http_server(9103)
    while True:
        fetch_blobstores()
        fetch_repositories()
        time.sleep(30)

if __name__ == "__main__":
    main()
