package main

import (
    "encoding/json"
    "fmt"
    "log"
    "net/http"
    "os"
    "strconv"
    "time"

    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promhttp"
)

var (
    nexusRepoCount = prometheus.NewGaugeVec(
        prometheus.GaugeOpts{
            Name: "nexus_repositories_count",
            Help: "Number of repositories in Nexus",
        },
        []string{"name"},
    )

    nexusRepoSize = prometheus.NewGaugeVec(
        prometheus.GaugeOpts{
            Name: "nexus_repositories_size_bytes",
            Help: "Size of the repository in bytes",
        },
        []string{"name"},
    )

    nexusRepoLastDownloadAge = prometheus.NewGaugeVec(
        prometheus.GaugeOpts{
            Name: "nexus_repositories_last_download_age_day",
            Help: "Age in days since the last download",
        },
        []string{"name"},
    )

    nexusBlobstoreCount = prometheus.NewGaugeVec(
        prometheus.GaugeOpts{
            Name: "nexus_blobstores_count",
            Help: "Number of blobstores",
        },
        []string{"name"},
    )

    nexusBlobstoreSize = prometheus.NewGaugeVec(
        prometheus.GaugeOpts{
            Name: "nexus_blobstores_size_bytes",
            Help: "Size of blobstore in bytes",
        },
        []string{"name"},
    )

    nexusBlobstoreUsage = prometheus.NewGaugeVec(
        prometheus.GaugeOpts{
            Name: "nexus_blobstores_usage_percent",
            Help: "Usage of blobstore in percent",
        },
        []string{"name"},
    )
)

func init() {
    prometheus.MustRegister(nexusRepoCount, nexusRepoSize, nexusRepoLastDownloadAge, nexusBlobstoreCount, nexusBlobstoreSize, nexusBlobstoreUsage)
}

func fetchMetrics() {
    // Ganti sesuai config
    baseURL := os.Getenv("NEXUS_URL")
    username := os.Getenv("NEXUS_USER")
    password := os.Getenv("NEXUS_PASS")

    client := &http.Client{Timeout: 10 * time.Second}
    req, err := http.NewRequest("GET", baseURL+"/service/rest/v1/repositories", nil)
    if err != nil {
        log.Println("Failed to create request:", err)
        return
    }
    req.SetBasicAuth(username, password)

    resp, err := client.Do(req)
    if err != nil {
        log.Println("Request error:", err)
        return
    }
    defer resp.Body.Close()

    var repositories []map[string]interface{}
    if err := json.NewDecoder(resp.Body).Decode(&repositories); err != nil {
        log.Println("Decode error:", err)
        return
    }

    for _, repo := range repositories {
        name := repo["name"].(string)

        // Dummy data. Ganti sesuai endpoint dan parsing sebenarnya.
        nexusRepoCount.WithLabelValues(name).Set(1)
        nexusRepoSize.WithLabelValues(name).Set(12345678)                          // ganti sesuai data sebenarnya
        nexusRepoLastDownloadAge.WithLabelValues(name).Set(3)                     // dummy: 3 hari
    }

    // Blobstore: Ganti dengan endpoint blobstore Nexus Anda
    req2, _ := http.NewRequest("GET", baseURL+"/service/rest/v1/blobstores", nil)
    req2.SetBasicAuth(username, password)
    resp2, err := client.Do(req2)
    if err != nil {
        log.Println("Blobstore request error:", err)
        return
    }
    defer resp2.Body.Close()

    var blobstores []map[string]interface{}
    if err := json.NewDecoder(resp2.Body).Decode(&blobstores); err != nil {
        log.Println("Blobstore decode error:", err)
        return
    }

    for _, bs := range blobstores {
        name := bs["name"].(string)
        // Dummy data. Ganti parsing sesuai struktur JSON nyata
        nexusBlobstoreCount.WithLabelValues(name).Set(1)
        nexusBlobstoreSize.WithLabelValues(name).Set(987654321)
        nexusBlobstoreUsage.WithLabelValues(name).Set(75.5)
    }
}

func main() {
    go func() {
        for {
            fetchMetrics()
            time.Sleep(30 * time.Second)
        }
    }()

    http.Handle("/metrics", promhttp.Handler())
    fmt.Println("Exporter running at :9103/metrics")
    log.Fatal(http.ListenAndServe(":9103", nil))
}
