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
	nexusRepoCount = prometheus.NewGauge(
		prometheus.GaugeOpts{
			Name: "nexus_repositories_count",
			Help: "Total number of repositories in Nexus",
		},
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
		nexusRepoCount,
		nexusRepoSize,
		nexusRepoLastDownloadAge,
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

	// === Repositories ===
	repos := []map[string]interface{}{}
	if err := fetchJSON(client, baseURL+"/service/rest/v1/repositories", username, password, &repos); err != nil {
		log.Println("Failed to fetch repositories:", err)
		return
	}
	nexusRepoCount.Set(float64(len(repos)))

	// === Blobstores ===
	blobstores := []map[string]interface{}{}
	if err := fetchJSON(client, baseURL+"/service/rest/v1/blobstores", username, password, &blobstores); err != nil {
		log.Println("Failed to fetch blobstores:", err)
		return
	}
	nexusBlobstoreCount.Set(float64(len(blobstores)))
	for _, bs := range blobstores {
		name := bs["name"].(string)

		// Fetch blobstore capacity details
		capacityURL := fmt.Sprintf("%s/service/rest/v1/blobstores/%s/capacity", baseURL, name)
		capacity := map[string]interface{}{}
		if err := fetchJSON(client, capacityURL, username, password, &capacity); err != nil {
			log.Printf("⚠️ Failed to fetch capacity for blobstore '%s': %v", name, err)
			continue
		}

		totalSize := getFloat(capacity["totalSpace"])
		usedSpace := getFloat(capacity["usedSpace"])
		fileCount := getFloat(capacity["itemCount"])

		usagePercent := 0.0
		if totalSize > 0 {
			usagePercent = (usedSpace / totalSize) * 100
		}

		nexusBlobstoreSize.WithLabelValues(name).Set(totalSize)
		nexusBlobstoreUsed.WithLabelValues(name).Set(usedSpace)
		nexusBlobstoreUsage.WithLabelValues(name).Set(usagePercent)
		nexusBlobstoreFileCount.WithLabelValues(name).Set(fileCount)
	}

	// === Assets ===
	assets, err := fetchAllAssets(client, baseURL, username, password)
	if err != nil {
		log.Println("Failed to fetch assets:", err)
		return
	}

	repoSize := make(map[string]float64)
	repoAge := make(map[string]float64)
	repoAgeCount := make(map[string]int)
	now := time.Now()

	for _, asset := range assets {
		repo := asset["repository"].(string)

		if sz, ok := asset["size"].(float64); ok {
			repoSize[repo] += sz
		}

		if lastDLStr, ok := asset["lastDownloaded"].(string); ok {
			if lastDL, err := time.Parse(time.RFC3339, lastDLStr); err == nil {
				ageDays := now.Sub(lastDL).Hours() / 24
				repoAge[repo] += ageDays
				repoAgeCount[repo]++
			}
		}
	}

	for repo, size := range repoSize {
		nexusRepoSize.WithLabelValues(repo).Set(size)
	}

	for repo, ageTotal := range repoAge {
		if count := repoAgeCount[repo]; count > 0 {
			nexusRepoLastDownloadAge.WithLabelValues(repo).Set(ageTotal / float64(count))
		}
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

func fetchAllAssets(client *http.Client, baseURL, user, pass string) ([]map[string]interface{}, error) {
	var assets []map[string]interface{}
	token := ""

	for {
		url := baseURL + "/service/rest/v1/search/assets"
		if token != "" {
			url += "?continuationToken=" + token
		}

		req, _ := http.NewRequest("GET", url, nil)
		req.SetBasicAuth(user, pass)
		resp, err := client.Do(req)
		if err != nil {
			return nil, err
		}
		defer resp.Body.Close()

		var result map[string]interface{}
		if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
			return nil, err
		}

		for _, item := range result["items"].([]interface{}) {
			assets = append(assets, item.(map[string]interface{}))
		}

		if next, ok := result["continuationToken"].(string); ok && next != "" {
			token = next
		} else {
			break
		}
	}
	return assets, nil
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
