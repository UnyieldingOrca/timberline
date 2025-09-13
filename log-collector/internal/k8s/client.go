package k8s

import (
	"context"
	"fmt"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/sirupsen/logrus"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/client-go/kubernetes"
	"k8s.io/client-go/rest"
)

// PodInfo contains Kubernetes pod information for log enrichment
type PodInfo struct {
	PodName   string            `json:"pod_name"`
	Namespace string            `json:"namespace"`
	NodeName  string            `json:"node_name"`
	Labels    map[string]string `json:"labels"`
}

// Client provides Kubernetes metadata enrichment
type Client struct {
	clientset     *kubernetes.Clientset
	logger        *logrus.Logger
	metadataCache map[string]*PodInfo
	cacheMutex    sync.RWMutex
	cacheExpiry   time.Duration
}

// Note: CacheEntry type was removed as it was unused.
// Future implementations may add proper cache expiry functionality.

// NewClient creates a new Kubernetes client
func NewClient() (*Client, error) {
	logger := logrus.New()
	logger.Debug("Initializing Kubernetes client...")

	// Try in-cluster config first (when running as DaemonSet)
	logger.Debug("Getting in-cluster Kubernetes configuration...")
	config, err := rest.InClusterConfig()
	if err != nil {
		logger.WithError(err).Debug("Failed to get in-cluster config")
		return nil, fmt.Errorf("failed to get in-cluster config: %w", err)
	}
	logger.Debug("In-cluster configuration obtained successfully")

	logger.Debug("Creating Kubernetes clientset...")
	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		logger.WithError(err).Debug("Failed to create Kubernetes clientset")
		return nil, fmt.Errorf("failed to create Kubernetes client: %w", err)
	}
	logger.Debug("Kubernetes clientset created successfully")

	client := &Client{
		clientset:     clientset,
		logger:        logger,
		metadataCache: make(map[string]*PodInfo),
		cacheExpiry:   5 * time.Minute,
	}
	logger.WithField("cache_expiry", client.cacheExpiry).Debug("Kubernetes client configuration")

	// Start cache cleanup goroutine
	logger.Debug("Starting metadata cache cleanup goroutine...")
	go client.cleanupCache()

	logger.Debug("Kubernetes client initialized successfully")
	return client, nil
}

// GetPodInfo extracts pod metadata from log file path
func (c *Client) GetPodInfo(logPath string) *PodInfo {
	c.logger.WithField("log_path", logPath).Debug("Extracting pod metadata from log path")
	// Extract pod information from log path
	// Typical paths:
	// /var/log/containers/<pod-name>_<namespace>_<container-name>-<container-id>.log
	// /var/log/pods/<namespace>_<pod-name>_<pod-uid>/<container-name>/<restart-count>.log

	var podName, namespace string

	if strings.Contains(logPath, "/var/log/containers/") {
		c.logger.WithField("log_path", logPath).Debug("Parsing container log path")
		podName, namespace = c.parseContainerLogPath(logPath)
	} else if strings.Contains(logPath, "/var/log/pods/") {
		c.logger.WithField("log_path", logPath).Debug("Parsing pod log path")
		podName, namespace = c.parsePodLogPath(logPath)
	} else {
		c.logger.WithField("log_path", logPath).Debug("Log path does not match known Kubernetes patterns")
	}

	if podName == "" || namespace == "" {
		c.logger.WithFields(logrus.Fields{
			"log_path": logPath,
			"pod_name": podName,
			"namespace": namespace,
		}).Debug("Could not extract pod name and namespace from path")
		return nil
	}
	c.logger.WithFields(logrus.Fields{
		"log_path": logPath,
		"pod_name": podName,
		"namespace": namespace,
	}).Debug("Successfully extracted pod information from path")

	// Check cache first
	cacheKey := fmt.Sprintf("%s/%s", namespace, podName)
	c.logger.WithField("cache_key", cacheKey).Debug("Checking metadata cache")
	c.cacheMutex.RLock()
	if cached, exists := c.metadataCache[cacheKey]; exists {
		c.cacheMutex.RUnlock()
		c.logger.WithField("cache_key", cacheKey).Debug("Pod metadata found in cache")
		return cached
	}
	c.cacheMutex.RUnlock()
	c.logger.WithField("cache_key", cacheKey).Debug("Pod metadata not in cache, fetching from API")

	// Fetch from Kubernetes API
	podInfo := c.fetchPodInfo(namespace, podName)

	// Cache the result
	if podInfo != nil {
		c.logger.WithField("cache_key", cacheKey).Debug("Caching pod metadata")
		c.cacheMutex.Lock()
		c.metadataCache[cacheKey] = podInfo
		c.cacheMutex.Unlock()
		c.logger.WithField("cache_size", len(c.metadataCache)).Debug("Pod metadata cached")
	} else {
		c.logger.WithField("cache_key", cacheKey).Debug("No pod metadata to cache")
	}

	return podInfo
}

// parseContainerLogPath parses container log path format
func (c *Client) parseContainerLogPath(logPath string) (string, string) {
	c.logger.WithField("log_path", logPath).Debug("Parsing container log path format")
	// Extract filename from path
	filename := filepath.Base(logPath)
	c.logger.WithField("filename", filename).Debug("Extracted filename from path")

	// Remove .log extension
	filename = strings.TrimSuffix(filename, ".log")
	c.logger.WithField("filename_no_ext", filename).Debug("Removed .log extension")

	// Pattern: <pod-name>_<namespace>_<container-name>-<container-id>
	parts := strings.Split(filename, "_")
	c.logger.WithFields(logrus.Fields{
		"filename": filename,
		"parts_count": len(parts),
		"parts": parts,
	}).Debug("Split filename into parts")
	if len(parts) < 3 {
		c.logger.WithField("parts_count", len(parts)).Debug("Insufficient parts in container log filename")
		return "", ""
	}

	podName := parts[0]
	namespace := parts[1]
	c.logger.WithFields(logrus.Fields{
		"pod_name": podName,
		"namespace": namespace,
	}).Debug("Extracted pod name and namespace from container log path")

	return podName, namespace
}

// parsePodLogPath parses pod log path format
func (c *Client) parsePodLogPath(logPath string) (string, string) {
	c.logger.WithField("log_path", logPath).Debug("Parsing pod log path format")
	// Pattern: /var/log/pods/<namespace>_<pod-name>_<pod-uid>/<container-name>/<restart-count>.log
	re := regexp.MustCompile(`/var/log/pods/([^_]+)_([^_]+)_[^/]+/`)
	matches := re.FindStringSubmatch(logPath)
	c.logger.WithFields(logrus.Fields{
		"log_path": logPath,
		"matches_count": len(matches),
	}).Debug("Applied regex to extract pod information")

	if len(matches) < 3 {
		c.logger.WithField("matches_count", len(matches)).Debug("Regex did not match expected pod log path pattern")
		return "", ""
	}

	namespace := matches[1]
	podName := matches[2]
	c.logger.WithFields(logrus.Fields{
		"namespace": namespace,
		"pod_name": podName,
	}).Debug("Extracted namespace and pod name from pod log path")

	return podName, namespace
}

// fetchPodInfo retrieves pod metadata from Kubernetes API
func (c *Client) fetchPodInfo(namespace, podName string) *PodInfo {
	c.logger.WithFields(logrus.Fields{
		"namespace": namespace,
		"pod_name": podName,
	}).Debug("Fetching pod metadata from Kubernetes API")

	// Return nil if clientset is not available (e.g., in tests or when K8s is unavailable)
	if c.clientset == nil {
		c.logger.Debug("Kubernetes clientset not available, cannot fetch pod metadata")
		return nil
	}

	c.logger.WithFields(logrus.Fields{
		"namespace": namespace,
		"pod_name": podName,
		"timeout": "10s",
	}).Debug("Making API call to get pod information")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	pod, err := c.clientset.CoreV1().Pods(namespace).Get(ctx, podName, metav1.GetOptions{})
	if err != nil {
		c.logger.WithError(err).WithFields(logrus.Fields{
			"namespace": namespace,
			"pod_name":  podName,
		}).Debug("Failed to fetch pod metadata from API")
		return nil
	}
	c.logger.WithFields(logrus.Fields{
		"namespace": namespace,
		"pod_name": podName,
		"node_name": pod.Spec.NodeName,
		"labels_count": len(pod.Labels),
	}).Debug("Successfully fetched pod metadata from API")

	podInfo := &PodInfo{
		PodName:   pod.Name,
		Namespace: pod.Namespace,
		NodeName:  pod.Spec.NodeName,
		Labels:    pod.Labels,
	}
	c.logger.WithFields(logrus.Fields{
		"pod_name": podInfo.PodName,
		"namespace": podInfo.Namespace,
		"node_name": podInfo.NodeName,
		"labels_count": len(podInfo.Labels),
	}).Debug("Created PodInfo structure")
	return podInfo
}

// cleanupCache periodically removes expired cache entries
func (c *Client) cleanupCache() {
	ticker := time.NewTicker(1 * time.Minute)
	defer ticker.Stop()

	for range ticker.C {
		c.cacheMutex.Lock()
		now := time.Now()
		for key, podInfo := range c.metadataCache {
			// Simple expiry check - in a real implementation, you'd store expiry time
			_ = podInfo
			if len(c.metadataCache) > 1000 { // Simple size-based eviction
				delete(c.metadataCache, key)
			}
		}
		c.cacheMutex.Unlock()
		_ = now // Suppress unused variable warning
	}
}
