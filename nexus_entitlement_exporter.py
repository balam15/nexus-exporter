import os
import time
import datetime
from prometheus_client import start_http_server, Gauge
from pathlib import Path

ENTITLEMENT_DIR = "/etc/pki/entitlement"

pem_file_count = Gauge('entitlement_pem_file_count', 'Number of .pem files in entitlement directory')
p12_file_count = Gauge('entitlement_p12_file_count', 'Number of .p12 files in entitlement directory')
total_file_size_bytes = Gauge('entitlement_total_file_size_bytes', 'Total size of all files in bytes')
last_modified_timestamp = Gauge('entitlement_last_modified_epoch', 'Latest modification time (epoch) in local time')
pem_more_than_p12 = Gauge('entitlement_pem_more_than_p12', '1 if .pem files > .p12 files, else 0')
pem_newer_than_p12 = Gauge('entitlement_pem_newer_than_p12', '1 if newest .pem is newer than newest .p12, else 0')

def to_local_epoch(utc_epoch):
    """Convert UTC-based epoch to local time epoch"""
    if utc_epoch == 0:
        return 0, "N/A"
    utc_dt = datetime.datetime.utcfromtimestamp(utc_epoch)
    local_dt = utc_dt.astimezone()  # use system's local timezone
    return local_dt.timestamp(), local_dt.strftime('%Y-%m-%d %H:%M:%S %Z')

def collect_entitlement_metrics():
    pem_count = 0
    p12_count = 0
    total_size = 0
    latest_mtime = 0
    pem_latest_mtime = 0
    p12_latest_mtime = 0

    try:
        for file in Path(ENTITLEMENT_DIR).iterdir():
            if file.is_file():
                stat = file.stat()
                total_size += stat.st_size
                latest_mtime = max(latest_mtime, stat.st_mtime)
                if file.name.endswith(".pem"):
                    pem_count += 1
                    pem_latest_mtime = max(pem_latest_mtime, stat.st_mtime)
                elif file.name.endswith(".p12"):
                    p12_count += 1
                    p12_latest_mtime = max(p12_latest_mtime, stat.st_mtime)
    except Exception as e:
        print(f"Error scanning directory: {e}")
        return

    # Set metrics
    pem_file_count.set(pem_count)
    p12_file_count.set(p12_count)
    total_file_size_bytes.set(total_size)

    local_epoch, local_str = to_local_epoch(latest_mtime)
    last_modified_timestamp.set(local_epoch)

    pem_more_than_p12.set(1 if pem_count > p12_count else 0)
    pem_newer_than_p12.set(1 if pem_latest_mtime > p12_latest_mtime else 0)

    pem_ts_str = datetime.datetime.fromtimestamp(pem_latest_mtime).strftime('%Y-%m-%d %H:%M:%S') if pem_latest_mtime else "-"
    p12_ts_str = datetime.datetime.fromtimestamp(p12_latest_mtime).strftime('%Y-%m-%d %H:%M:%S') if p12_latest_mtime else "-"

    print(f"[INFO] Last modified (local): {local_str} | PEM: {pem_count} (latest: {pem_ts_str}) | "
          f"P12: {p12_count} (latest: {p12_ts_str}) | Size: {total_size} bytes")

if __name__ == "__main__":
    start_http_server(9102)
    print("Entitlement Exporter running at http://localhost:9102/metrics")

    while True:
        collect_entitlement_metrics()
        time.sleep(5)
