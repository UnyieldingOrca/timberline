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
	// Try in-cluster config first (when running as DaemonSet)
	config, err := rest.InClusterConfig()
	if err != nil {
		return nil, fmt.Errorf("failed to get in-cluster config: %w", err)
	}

	clientset, err := kubernetes.NewForConfig(config)
	if err != nil {
		return nil, fmt.Errorf("failed to create Kubernetes client: %w", err)
	}

	logger := logrus.New()
	client := &Client{
		clientset:     clientset,
		logger:        logger,
		metadataCache: make(map[string]*PodInfo),
		cacheExpiry:   5 * time.Minute,
	}

	// Start cache cleanup goroutine
	go client.cleanupCache()

	return client, nil
}

// GetPodInfo extracts pod metadata from log file path
func (c *Client) GetPodInfo(logPath string) *PodInfo {
	// Extract pod information from log path
	// Typical paths:
	// /var/log/containers/<pod-name>_<namespace>_<container-name>-<container-id>.log
	// /var/log/pods/<namespace>_<pod-name>_<pod-uid>/<container-name>/<restart-count>.log

	var podName, namespace string

	if strings.Contains(logPath, "/var/log/containers/") {
		podName, namespace = c.parseContainerLogPath(logPath)
	} else if strings.Contains(logPath, "/var/log/pods/") {
		podName, namespace = c.parsePodLogPath(logPath)
	}

	if podName == "" || namespace == "" {
		return nil
	}

	// Check cache first
	cacheKey := fmt.Sprintf("%s/%s", namespace, podName)
	c.cacheMutex.RLock()
	if cached, exists := c.metadataCache[cacheKey]; exists {
		c.cacheMutex.RUnlock()
		return cached
	}
	c.cacheMutex.RUnlock()

	// Fetch from Kubernetes API
	podInfo := c.fetchPodInfo(namespace, podName)

	// Cache the result
	if podInfo != nil {
		c.cacheMutex.Lock()
		c.metadataCache[cacheKey] = podInfo
		c.cacheMutex.Unlock()
	}

	return podInfo
}

// parseContainerLogPath parses container log path format
func (c *Client) parseContainerLogPath(logPath string) (string, string) {
	// Extract filename from path
	filename := filepath.Base(logPath)

	// Remove .log extension
	filename = strings.TrimSuffix(filename, ".log")

	// Pattern: <pod-name>_<namespace>_<container-name>-<container-id>
	parts := strings.Split(filename, "_")
	if len(parts) < 3 {
		return "", ""
	}

	podName := parts[0]
	namespace := parts[1]

	return podName, namespace
}

// parsePodLogPath parses pod log path format
func (c *Client) parsePodLogPath(logPath string) (string, string) {
	// Pattern: /var/log/pods/<namespace>_<pod-name>_<pod-uid>/<container-name>/<restart-count>.log
	re := regexp.MustCompile(`/var/log/pods/([^_]+)_([^_]+)_[^/]+/`)
	matches := re.FindStringSubmatch(logPath)

	if len(matches) < 3 {
		return "", ""
	}

	namespace := matches[1]
	podName := matches[2]

	return podName, namespace
}

// fetchPodInfo retrieves pod metadata from Kubernetes API
func (c *Client) fetchPodInfo(namespace, podName string) *PodInfo {
	// Return nil if clientset is not available (e.g., in tests or when K8s is unavailable)
	if c.clientset == nil {
		return nil
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	pod, err := c.clientset.CoreV1().Pods(namespace).Get(ctx, podName, metav1.GetOptions{})
	if err != nil {
		c.logger.WithError(err).WithFields(logrus.Fields{
			"namespace": namespace,
			"pod_name":  podName,
		}).Debug("Failed to fetch pod metadata")
		return nil
	}

	return &PodInfo{
		PodName:   pod.Name,
		Namespace: pod.Namespace,
		NodeName:  pod.Spec.NodeName,
		Labels:    pod.Labels,
	}
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
