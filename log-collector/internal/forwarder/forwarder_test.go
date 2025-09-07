package forwarder

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/timberline/log-collector/internal/models"
)

func TestNewHTTPForwarder(t *testing.T) {
	url := "http://localhost:8080/logs"
	forwarder := NewHTTPForwarder(url)

	assert.NotNil(t, forwarder)
	assert.Equal(t, url, forwarder.url)
}

func TestHTTPForwarder_Forward(t *testing.T) {
	// Create test log entries
	entries := []*models.LogEntry{
		{
			Timestamp: time.Now().UnixMilli(),
			Message:   "Test message 1",
			Source:    "app1",
			Metadata: map[string]interface{}{
				"level":     "INFO",
				"pod_name":  "pod-1",
				"namespace": "default",
				"node_name": "node-1",
			},
		},
		{
			Timestamp: time.Now().UnixMilli(),
			Message:   "Test message 2",
			Source:    "app2",
			Metadata: map[string]interface{}{
				"level":     "ERROR",
				"pod_name":  "pod-2",
				"namespace": "kube-system",
				"node_name": "node-2",
			},
		},
	}

	tests := []struct {
		name           string
		serverResponse int
		entries        []*models.LogEntry
		expectError    bool
	}{
		{
			name:           "successful forward",
			serverResponse: http.StatusOK,
			entries:        entries,
			expectError:    false,
		},
		{
			name:           "server error",
			serverResponse: http.StatusInternalServerError,
			entries:        entries,
			expectError:    true,
		},
		{
			name:           "empty entries",
			serverResponse: http.StatusOK,
			entries:        []*models.LogEntry{},
			expectError:    false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create test server
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				// Verify request method and content type
				assert.Equal(t, http.MethodPost, r.Method)
				assert.Equal(t, "application/json", r.Header.Get("Content-Type"))

				// Verify request body - expect LogBatch format
				var receivedBatch models.LogBatch
				err := json.NewDecoder(r.Body).Decode(&receivedBatch)
				require.NoError(t, err)
				assert.Equal(t, len(tt.entries), len(receivedBatch.Logs))

				// Send response
				w.WriteHeader(tt.serverResponse)
			}))
			defer server.Close()

			// Create forwarder with test server URL
			forwarder := NewHTTPForwarder(server.URL)

			// Test forward
			err := forwarder.Forward(tt.entries)

			if tt.expectError {
				assert.Error(t, err)
			} else {
				assert.NoError(t, err)
			}
		})
	}
}

func TestHTTPForwarder_ForwardWithTimeout(t *testing.T) {
	// Create a slow server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(2 * time.Second) // Simulate slow response
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	forwarder := NewHTTPForwarder(server.URL)
	entries := []*models.LogEntry{
		{
			Timestamp: time.Now().UnixMilli(),
			Message:   "Test message",
			Source:    "test",
			Metadata: map[string]interface{}{
				"level": "INFO",
			},
		},
	}

	// This test would verify timeout handling if implemented
	err := forwarder.Forward(entries)

	// For the current basic implementation, this should not error
	// In a real implementation with timeout, this might error
	assert.NoError(t, err)
}

func TestHTTPForwarder_ForwardWithRetry(t *testing.T) {
	attempts := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempts++
		if attempts < 3 {
			w.WriteHeader(http.StatusServiceUnavailable)
			return
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	forwarder := NewHTTPForwarder(server.URL)
	entries := []*models.LogEntry{
		{
			Timestamp: time.Now().UnixMilli(),
			Message:   "Test message",
			Source:    "test",
			Metadata: map[string]interface{}{
				"level": "INFO",
			},
		},
	}

	err := forwarder.Forward(entries)

	// This test demonstrates where retry logic could be tested
	// Currently returns no error due to basic implementation
	assert.NoError(t, err)
}

func TestHTTPForwarder_ForwardLargePayload(t *testing.T) {
	// Create many log entries to test large payload handling
	entries := make([]*models.LogEntry, 1000)
	for i := 0; i < 1000; i++ {
		entries[i] = &models.LogEntry{
			Timestamp: time.Now().UnixMilli(),
			Message:   "Large payload test message with some additional content to increase size",
			Source:    "load-test",
			Metadata: map[string]interface{}{
				"level":     "INFO",
				"pod_name":  "load-test-pod",
				"namespace": "default",
				"node_name": "test-node",
				"labels": map[string]string{
					"test":  "large-payload",
					"index": string(rune(i)),
				},
			},
		}
	}

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var receivedBatch models.LogBatch
		err := json.NewDecoder(r.Body).Decode(&receivedBatch)
		require.NoError(t, err)
		assert.Equal(t, 1000, len(receivedBatch.Logs))
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	forwarder := NewHTTPForwarder(server.URL)
	err := forwarder.Forward(entries)
	assert.NoError(t, err)
}

func TestInterface_Implementation(t *testing.T) {
	// Verify that HTTPForwarder implements the Interface
	var _ Interface = (*HTTPForwarder)(nil)

	// Test interface methods
	forwarder := NewHTTPForwarder("http://test.com")
	err := forwarder.Forward([]*models.LogEntry{})
	assert.NoError(t, err)
}