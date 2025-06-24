import os
import time
import requests
from prometheus_client import start_http_server, Gauge
from datetime import datetime, timezone

NEXUS_URL = os.getenv("NEXUS_URL")
NEXUS_USER = os.getenv("NEXUS_USER")
NEXUS_PASS = os.getenv("NEXUS_PASS")
SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL", "60"))  # seconds

# Metrics
repo_size = Gauge("nexus_repositories_size_bytes", "Total size of repository in bytes", ["repository"])
repo_assets_count = Gauge("nexus_repositories_assets_count", "Total number of assets in repository", ["repository"])

def fetch_all_assets_size(repository):
    session = requests.Session()
    continuation_token = None
    total_size = 0
    total_assets = 0
    page = 1

    while True:
        params = {"repository": repository}
        if continuation_token:
            params["continuationToken"] = continuation_token

        url = f"{NEXUS_URL}/service/rest/v1/search/assets"
        try:
            resp = session.get(url, auth=(NEXUS_USER, NEXUS_PASS), params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"❌ Error fetching assets page {page} for repo {repository}: {e}")
            break

        items = data.get("items", [])
        count_items = len(items)
        page_size = sum(int(item.get("fileSize", 0)) for item in items)
        total_size += page_size
        total_assets += count_items

        print(f"[{repository}] Page {page}: {count_items} assets, {page_size} bytes")

        continuation_token = data.get("continuationToken")
        if not continuation_token:
            break
        page += 1

    return total_size, total_assets

def fetch_repositories_and_update_metrics():
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
        print(f"▶ Processing repository: {repo_name}")

        size, count = fetch_all_assets_size(repo_name)
        size_gb = size / (1024 ** 3)
        print(f"✔ Repository {repo_name} size: {size} bytes ({size_gb:.2f} GB), assets count: {count}")

        repo_size.labels(repository=repo_name).set(size)
        repo_assets_count.labels(repository=repo_name).set(count)

def main():
    print("🚀 Starting Nexus exporter on :9103/metrics")
    start_http_server(9103)
    while True:
        fetch_repositories_and_update_metrics()
        time.sleep(SCRAPE_INTERVAL)

if __name__ == "__main__":
    main()
