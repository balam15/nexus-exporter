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
	nexusBlobstoreCount = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "nexus_blobstores_count",
			Help: "Total number of blobstores",
		},
	)

	nexusBlobstoreSize = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "nexus_blobstores_size_bytes",
			Help: "Size of blobstore in bytes",
		},
		[]string{"name"},
	)

	nexusBlobstoreUsed = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "nexus_blobstores_used_space_bytes",
			Help: "Used space of blobstore in bytes",
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

	nexusBlobstoreFileCount = prometheus.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "nexus_blobstores_file_count",
			Help: "Number of files stored in each blobstore",
		},
		[]string{"name"},
	)
)

func init() {
	prometheus.MustRegister(
		nexusBlobstoreCount,
		nexusBlobstoreSize,
		nexusBlobstoreUsed,
		nexusBlobstoreUsage,
		nexusBlobstoreFileCount,
	)
}

func main() {
	go func() {
		for {
			fetchMetrics()
			time.Sleep(30 * time.Second)
		}
	}()

	http.Handle("/metrics", promhttp.Handler())
	fmt.Println("✅ Nexus exporter running on :9103/metrics")
	log.Fatal(http.ListenAndServe(":9103", nil))
}

func fetchMetrics() {
	baseURL := os.Getenv("NEXUS_URL")
	username := os.Getenv("NEXUS_USER")
	password := os.Getenv("NEXUS_PASS")

	if baseURL == "" || username == "" || password == "" {
		log.Println("❌ NEXUS_URL, NEXUS_USER, and NEXUS_PASS must be set")
		return
	}

	client := &http.Client{Timeout: 15 * time.Second}

	// === Blobstores ===
	blobstores := []map[string]interface{}{}
	if err := fetchJSON(client, baseURL+"/service/rest/v1/blobstores", username, password, &blobstores); err != nil {
		log.Println("Failed to fetch blobstores:", err)
		return
	}
	nexusBlobstoreCount.Set(float64(len(blobstores)))
	for _, bs := range blobstores {
		name := bs["name"].(string)
		usedSpace := getFloat(bs["totalSizeInBytes"])
		available := getFloat(bs["availableSpaceInBytes"])
		fullSize := usedSpace + available
		fileCount := getFloat(bs["blobCount"])

		usagePercent := 0.0
		if fullSize > 0 {
			usagePercent = (usedSpace / fullSize) * 100
		}

		nexusBlobstoreSize.WithLabelValues(name).Set(fullSize)
		nexusBlobstoreUsed.WithLabelValues(name).Set(usedSpace)
		nexusBlobstoreUsage.WithLabelValues(name).Set(usagePercent)
		nexusBlobstoreFileCount.WithLabelValues(name).Set(fileCount)
	}
}

func fetchJSON(client *http.Client, url, user, pass string, target interface{}) error {
	req, _ := http.NewRequest("GET", url, nil)
	req.SetBasicAuth(user, pass)
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	return json.NewDecoder(resp.Body).Decode(target)
}

func getFloat(val interface{}) float64 {
	switch v := val.(type) {
	case float64:
		return v
	case int:
		return float64(v)
	case int64:
		return float64(v)
	case string:
		f, _ := strconv.ParseFloat(v, 64)
		return f
	default:
		return 0
	}
}
