package handlers

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/timberline/log-ingestor/internal/models"
)

func TestStreamHandler_FluentBitRealData(t *testing.T) {
	// Create mock storage
	mockStorage := new(MockStreamStorage)
	handler := newTestStreamHandler(mockStorage, 100)

	// Real data captured from Fluent Bit in kind cluster (using 'date' field instead of 'timestamp')
	fluentBitData := `{"date":1758402234.132,"log":"2025-09-20T21:03:54.132201507Z stderr F time=\"2025-09-20T21:03:54Z\" level=warning msg=\"Invalid log entry\"","kubernetes":{"pod_name":"log-ingestor-68b874f5df-p448n","namespace_name":"timberline","pod_id":"4e1ed8d6-e55f-4e8c-8af9-a92c9bbb4006","labels":{"app":"log-ingestor","pod-template-hash":"68b874f5df"},"host":"timberline-test-worker","pod_ip":"10.244.1.13","container_name":"log-ingestor","docker_id":"9edc32d6f0098c36c371dc23c7e2cc9ff8994f9fbd89b6a9a883fa119cc1f20e","container_hash":"sha256:784156a830ef6d365fa46f9a025f8f7581713d57130623d6b6b21a94bac4a8de","container_image":"docker.io/timberline/log-ingestor:latest"},"source":"fluent-bit"}
{"date":1758402235.456,"log":"2025-09-20T21:03:55.456789012Z stdout F {\"level\":\"info\",\"msg\":\"Processing request\",\"service\":\"log-ingestor\"}","kubernetes":{"pod_name":"log-ingestor-68b874f5df-p448n","namespace_name":"timberline","container_name":"log-ingestor"},"source":"fluent-bit"}`

	// Mock storage expects two individual log calls with transformed entries
	mockStorage.On("StoreLog", mock.Anything, mock.AnythingOfType("*models.LogEntry")).Return(nil).Times(2)

	// Create request
	req := httptest.NewRequest("POST", "/api/v1/logs/stream", bytes.NewBufferString(fluentBitData))
	req.Header.Set("Content-Type", "application/x-ndjson")

	// Create response recorder
	w := httptest.NewRecorder()

	// Call handler
	handler.HandleStream(w, req)

	// Verify response
	assert.Equal(t, http.StatusOK, w.Code)

	var response models.BatchResponse
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.True(t, response.Success)
	assert.Equal(t, 2, response.ProcessedCount)

	// Verify mock expectations
	mockStorage.AssertExpectations(t)
}

func TestStreamHandler_ExpectedFormat(t *testing.T) {
	// Create mock storage
	mockStorage := new(MockStreamStorage)
	handler := newTestStreamHandler(mockStorage, 100)

	// Expected format that our log-ingestor needs (after transformation)
	expectedData := `{"timestamp":1758402234132,"message":"2025-09-20T21:03:54.132201507Z stderr F time=\"2025-09-20T21:03:54Z\" level=warning msg=\"Invalid log entry\"","source":"fluent-bit","metadata":{"level":"warning","container_name":"log-ingestor","namespace":"timberline","pod_name":"log-ingestor-68b874f5df-p448n","labels":{"app":"log-ingestor"}}}
{"timestamp":1758402235456,"message":"{\"level\":\"info\",\"msg\":\"Processing request\",\"service\":\"log-ingestor\"}","source":"fluent-bit","metadata":{"level":"info","container_name":"log-ingestor","namespace":"timberline","pod_name":"log-ingestor-68b874f5df-p448n"}}`

	// Mock storage expects two individual log calls
	mockStorage.On("StoreLog", mock.Anything, mock.AnythingOfType("*models.LogEntry")).Return(nil).Times(2)

	// Create request
	req := httptest.NewRequest("POST", "/api/v1/logs/stream", bytes.NewBufferString(expectedData))
	req.Header.Set("Content-Type", "application/x-ndjson")

	// Create response recorder
	w := httptest.NewRecorder()

	// Call handler
	handler.HandleStream(w, req)

	// Verify response
	assert.Equal(t, http.StatusOK, w.Code)

	var response models.BatchResponse
	err := json.Unmarshal(w.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.True(t, response.Success)
	assert.Equal(t, 2, response.ProcessedCount)

	// Verify mock expectations
	mockStorage.AssertExpectations(t)
}

func TestFluentBitDataStructure(t *testing.T) {
	// This test documents the actual Fluent Bit data structure for reference
	realFluentBitJSON := `{
		"date": 1758402234.132,
		"log": "2025-09-20T21:03:54.132201507Z stderr F time=\"2025-09-20T21:03:54Z\" level=warning msg=\"Invalid log entry\"",
		"kubernetes": {
			"pod_name": "log-ingestor-68b874f5df-p448n",
			"namespace_name": "timberline",
			"pod_id": "4e1ed8d6-e55f-4e8c-8af9-a92c9bbb4006",
			"labels": {
				"app": "log-ingestor",
				"pod-template-hash": "68b874f5df"
			},
			"host": "timberline-test-worker",
			"pod_ip": "10.244.1.13",
			"container_name": "log-ingestor",
			"docker_id": "9edc32d6f0098c36c371dc23c7e2cc9ff8994f9fbd89b6a9a883fa119cc1f20e",
			"container_hash": "sha256:784156a830ef6d365fa46f9a025f8f7581713d57130623d6b6b21a94bac4a8de",
			"container_image": "docker.io/timberline/log-ingestor:latest"
		},
		"source": "fluent-bit"
	}`

	t.Logf("Fluent Bit sends this structure:\n%s", realFluentBitJSON)
	t.Log("The log-ingestor automatically transforms this to our expected format:")
	t.Log("  - 'date' field (float64 seconds) → 'timestamp' (int64 milliseconds)")
	t.Log("  - 'log' field → 'message' field")
	t.Log("  - 'kubernetes' object → 'metadata' field")
	t.Log("  - 'source' field preserved as-is")
}

func TestFluentBitTransformation(t *testing.T) {
	// Test the transformation logic directly
	fluentBitEntry := FluentBitLogEntry{
		Date: 1758402234.567,
		Log:  "Test log message",
		Kubernetes: map[string]interface{}{
			"pod_name":       "test-pod",
			"namespace_name": "test-namespace",
			"container_name": "test-container",
		},
		Source: "fluent-bit",
	}

	// Transform to LogEntry
	logEntry := fluentBitEntry.transformToLogEntry()

	// Verify transformation
	assert.Equal(t, int64(1758402234567), logEntry.Timestamp) // Converted to milliseconds
	assert.Equal(t, "Test log message", logEntry.Message)
	assert.Equal(t, "fluent-bit", logEntry.Source)
	assert.Equal(t, "test-pod", logEntry.Metadata["pod_name"])
	assert.Equal(t, "test-namespace", logEntry.Metadata["namespace_name"])
	assert.Equal(t, "test-container", logEntry.Metadata["container_name"])

	// Test source fallback
	entryNoSource := FluentBitLogEntry{
		Date: 1758402234.567,
		Log:  "Test log message",
	}
	transformedNoSource := entryNoSource.transformToLogEntry()
	assert.Equal(t, "fluent-bit", transformedNoSource.Source) // Should default to fluent-bit
}
