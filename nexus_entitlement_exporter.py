import os
import time
import datetime
import socket
from prometheus_client import start_http_server, Gauge
from pathlib import Path

# === Constants ===
ENTITLEMENT_DIR = "/etc/pki/entitlement"
EXPORT_PORT = 9102
SLEEP_INTERVAL = 5

# === Hostname from environment (real host), fallback to container hostname ===
HOSTNAME = os.environ.get("HOSTNAME", socket.gethostname())
LABELS = {'hostname': HOSTNAME}

# === Prometheus Gauges (with hostname label only) ===
pem_file_count = Gauge('entitlement_pem_file_count', 'Number of .pem files in entitlement directory', ['hostname'])
p12_file_count = Gauge('entitlement_p12_file_count', 'Number of .p12 files in entitlement directory', ['hostname'])
total_file_size_bytes = Gauge('entitlement_total_file_size_bytes', 'Total size of all files in bytes', ['hostname'])
last_modified_timestamp = Gauge('entitlement_last_modified_epoch', 'Latest modification time (epoch) in local time', ['hostname'])
pem_more_than_p12 = Gauge('entitlement_pem_more_than_p12', '1 if .pem files > .p12 files, else 0', ['hostname'])
pem_newer_than_p12 = Gauge('entitlement_pem_newer_than_p12', '1 if newest .pem is newer than newest .p12, else 0', ['hostname'])

def to_local_epoch(utc_epoch):
    if utc_epoch == 0:
        return 0, "N/A"
    utc_dt = datetime.datetime.utcfromtimestamp(utc_epoch)
    local_dt = utc_dt.astimezone()
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
        print(f"[ERROR] Failed scanning directory: {e}")
        return

    # Set metrics with hostname label
    pem_file_count.labels(**LABELS).set(pem_count)
    p12_file_count.labels(**LABELS).set(p12_count)
    total_file_size_bytes.labels(**LABELS).set(total_size)

    local_epoch, local_str = to_local_epoch(latest_mtime)
    last_modified_timestamp.labels(**LABELS).set(local_epoch)

    pem_more_than_p12.labels(**LABELS).set(1 if pem_count > p12_count else 0)
    pem_newer_than_p12.labels(**LABELS).set(1 if pem_latest_mtime > p12_latest_mtime else 0)

    # Optional log to console
    print(f"[INFO] Host: {HOSTNAME} | Last modified: {local_str} | "
          f"PEM: {pem_count} (newest: {pem_latest_mtime}) | "
          f"P12: {p12_count} (newest: {p12_latest_mtime}) | Total size: {total_size} bytes")

if __name__ == "__main__":
    print(f"Starting exporter on port {EXPORT_PORT} with hostname: {HOSTNAME}")
    start_http_server(EXPORT_PORT)

    while True:
        collect_entitlement_metrics()
        time.sleep(SLEEP_INTERVAL)
