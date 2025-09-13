package k8s

import (
	"testing"
	"time"

	"github.com/sirupsen/logrus"
	"github.com/stretchr/testify/assert"
)

func TestClient_parseContainerLogPath(t *testing.T) {
	logger := logrus.New()
	logger.SetLevel(logrus.PanicLevel) // Suppress debug output in tests
	client := &Client{logger: logger}

	tests := []struct {
		name    string
		logPath string
		wantPod string
		wantNS  string
	}{
		{
			name:    "valid container log path",
			logPath: "/var/log/containers/nginx-pod_default_nginx-container-abc123.log",
			wantPod: "nginx-pod",
			wantNS:  "default",
		},
		{
			name:    "container log with dashes in pod name",
			logPath: "/var/log/containers/my-app-pod_kube-system_app-container-def456.log",
			wantPod: "my-app-pod",
			wantNS:  "kube-system",
		},
		{
			name:    "invalid format - too few parts",
			logPath: "/var/log/containers/nginx_default.log",
			wantPod: "",
			wantNS:  "",
		},
		{
			name:    "empty path",
			logPath: "",
			wantPod: "",
			wantNS:  "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gotPod, gotNS := client.parseContainerLogPath(tt.logPath)
			assert.Equal(t, tt.wantPod, gotPod)
			assert.Equal(t, tt.wantNS, gotNS)
		})
	}
}

func TestClient_parsePodLogPath(t *testing.T) {
	logger := logrus.New()
	logger.SetLevel(logrus.PanicLevel) // Suppress debug output in tests
	client := &Client{logger: logger}

	tests := []struct {
		name    string
		logPath string
		wantPod string
		wantNS  string
	}{
		{
			name:    "valid pod log path",
			logPath: "/var/log/pods/default_nginx-pod_12345678-1234-1234-1234-123456789012/nginx/0.log",
			wantPod: "nginx-pod",
			wantNS:  "default",
		},
		{
			name:    "pod log with dashes in names",
			logPath: "/var/log/pods/kube-system_my-app-pod_87654321-4321-4321-4321-210987654321/app-container/1.log",
			wantPod: "my-app-pod",
			wantNS:  "kube-system",
		},
		{
			name:    "invalid format",
			logPath: "/var/log/pods/invalid-format.log",
			wantPod: "",
			wantNS:  "",
		},
		{
			name:    "empty path",
			logPath: "",
			wantPod: "",
			wantNS:  "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gotPod, gotNS := client.parsePodLogPath(tt.logPath)
			assert.Equal(t, tt.wantPod, gotPod)
			assert.Equal(t, tt.wantNS, gotNS)
		})
	}
}

func TestClient_GetPodInfo_PathParsing(t *testing.T) {
	logger := logrus.New()
	logger.SetLevel(logrus.PanicLevel) // Suppress debug output in tests
	client := &Client{
		logger:        logger,
		metadataCache: make(map[string]*PodInfo),
		cacheExpiry:   5 * time.Minute,
	}

	tests := []struct {
		name    string
		logPath string
		wantNil bool
	}{
		{
			name:    "container log path - should return nil without k8s API",
			logPath: "/var/log/containers/nginx-pod_default_nginx-abc123.log",
			wantNil: true, // Will be nil because we can't reach k8s API in unit test
		},
		{
			name:    "pod log path - should return nil without k8s API",
			logPath: "/var/log/pods/default_nginx-pod_12345/nginx/0.log",
			wantNil: true, // Will be nil because we can't reach k8s API in unit test
		},
		{
			name:    "invalid path format",
			logPath: "/some/other/path/file.log",
			wantNil: true,
		},
		{
			name:    "empty path",
			logPath: "",
			wantNil: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := client.GetPodInfo(tt.logPath)
			if tt.wantNil {
				assert.Nil(t, result)
			} else {
				assert.NotNil(t, result)
			}
		})
	}
}

func TestClient_Cache(t *testing.T) {
	logger := logrus.New()
	logger.SetLevel(logrus.PanicLevel) // Suppress debug output in tests
	client := &Client{
		logger:        logger,
		metadataCache: make(map[string]*PodInfo),
		cacheExpiry:   5 * time.Minute,
	}

	// Test cache functionality by manually adding entries
	podInfo := &PodInfo{
		PodName:   "test-pod",
		Namespace: "test-namespace",
		NodeName:  "test-node",
		Labels: map[string]string{
			"app": "test",
		},
	}

	cacheKey := "test-namespace/test-pod"

	// Manually add to cache to test cache retrieval
	client.cacheMutex.Lock()
	client.metadataCache[cacheKey] = podInfo
	client.cacheMutex.Unlock()

	// Verify cache hit
	client.cacheMutex.RLock()
	cached, exists := client.metadataCache[cacheKey]
	client.cacheMutex.RUnlock()

	assert.True(t, exists)
	assert.Equal(t, podInfo, cached)
}

func TestNewClient_Integration(t *testing.T) {
	// This test will fail in most environments since it requires in-cluster config
	// It's included to document the expected behavior
	t.Skip("Skipping NewClient test - requires Kubernetes in-cluster config")

	client, err := NewClient()
	if err != nil {
		// Expected in most test environments
		assert.Contains(t, err.Error(), "failed to get in-cluster config")
		assert.Nil(t, client)
	} else {
		// If we somehow have in-cluster config
		assert.NotNil(t, client)
		assert.NotNil(t, client.clientset)
		assert.NotNil(t, client.logger)
		assert.NotNil(t, client.metadataCache)
		assert.Equal(t, 5*time.Minute, client.cacheExpiry)
	}
}

// Benchmark tests for performance
func BenchmarkClient_parseContainerLogPath(b *testing.B) {
	client := &Client{}
	logPath := "/var/log/containers/nginx-pod_default_nginx-container-abc123.log"

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		client.parseContainerLogPath(logPath)
	}
}

func BenchmarkClient_parsePodLogPath(b *testing.B) {
	client := &Client{}
	logPath := "/var/log/pods/default_nginx-pod_12345678-1234-1234-1234-123456789012/nginx/0.log"

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		client.parsePodLogPath(logPath)
	}
}
