package handlers

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/sirupsen/logrus"
	"github.com/timberline/log-ingestor/internal/models"
	"github.com/timberline/log-ingestor/internal/storage"
)

var testCounter int

// createTestBatchHandler creates a batch handler with unique metrics names to avoid conflicts
func createTestBatchHandler(storage storage.StorageInterface, maxBatchSize int) *BatchHandler {
	testCounter++
	
	metrics := &BatchMetrics{
		requestsTotal: prometheus.NewCounter(prometheus.CounterOpts{
			Name: fmt.Sprintf("test_log_ingestor_batch_requests_total_%d", testCounter),
			Help: "Total number of batch requests",
		}),
		requestDuration: prometheus.NewHistogram(prometheus.HistogramOpts{
			Name:    fmt.Sprintf("test_log_ingestor_batch_request_duration_seconds_%d", testCounter),
			Help:    "Duration of batch requests",
			Buckets: []float64{0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0},
		}),
		batchSizeHist: prometheus.NewHistogram(prometheus.HistogramOpts{
			Name:    fmt.Sprintf("test_log_ingestor_batch_size_%d", testCounter),
			Help:    "Size of log batches",
			Buckets: []float64{1, 5, 10, 50, 100, 500, 1000},
		}),
		errorsTotal: prometheus.NewCounter(prometheus.CounterOpts{
			Name: fmt.Sprintf("test_log_ingestor_batch_errors_total_%d", testCounter),
			Help: "Total number of batch processing errors",
		}),
		logsProcessed: prometheus.NewCounter(prometheus.CounterOpts{
			Name: fmt.Sprintf("test_log_ingestor_logs_processed_total_%d", testCounter),
			Help: "Total number of logs processed",
		}),
	}

	// Create a test registry and register metrics there
	testRegistry := prometheus.NewRegistry()
	testRegistry.MustRegister(metrics.requestsTotal)
	testRegistry.MustRegister(metrics.requestDuration)
	testRegistry.MustRegister(metrics.batchSizeHist)
	testRegistry.MustRegister(metrics.errorsTotal)
	testRegistry.MustRegister(metrics.logsProcessed)

	return &BatchHandler{
		storage:      storage,
		logger:       logrus.New(),
		metrics:      metrics,
		maxBatchSize: maxBatchSize,
	}
}

// Mock storage interface for testing
type mockStorage struct {
	shouldError      bool
	errorMessage     string
	healthCheckError bool
}

func (m *mockStorage) Connect(ctx context.Context) error {
	return nil
}

func (m *mockStorage) Close() error {
	return nil
}

func (m *mockStorage) StoreBatch(ctx context.Context, batch *models.LogBatch) error {
	if m.shouldError {
		return fmt.Errorf(m.errorMessage)
	}
	return nil
}

func (m *mockStorage) HealthCheck(ctx context.Context) error {
	if m.healthCheckError {
		return fmt.Errorf("health check failed")
	}
	return nil
}

func (m *mockStorage) CreateCollection(ctx context.Context) error {
	return nil
}

func TestNewBatchHandler(t *testing.T) {
	storage := &mockStorage{}
	maxBatchSize := 100

	handler := createTestBatchHandler(storage, maxBatchSize)

	if handler == nil {
		t.Fatal("Expected handler to be created, got nil")
	}
	if handler.storage != storage {
		t.Error("Expected storage to be set correctly")
	}
	if handler.maxBatchSize != maxBatchSize {
		t.Errorf("Expected maxBatchSize %d, got %d", maxBatchSize, handler.maxBatchSize)
	}
	if handler.logger == nil {
		t.Error("Expected logger to be initialized")
	}
	if handler.metrics == nil {
		t.Error("Expected metrics to be initialized")
	}
}

func TestBatchHandler_HandleBatch_Success(t *testing.T) {
	storage := &mockStorage{}
	handler := createTestBatchHandler(storage, 100)

	// Create a valid log batch
	batch := models.LogBatch{
		Logs: []*models.LogEntry{
			&models.LogEntry{
				Timestamp: 1704110400000, // 2024-01-01T12:00:00Z
				Message:   "Test log message",
				Source:    "test-source",
				Metadata: map[string]interface{}{
					"level": "INFO",
				},
			},
		},
	}

	jsonData, _ := json.Marshal(batch)
	req := httptest.NewRequest(http.MethodPost, "/batch", bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	
	rr := httptest.NewRecorder()
	handler.HandleBatch(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("Expected status %d, got %d", http.StatusOK, rr.Code)
	}

	var response models.BatchResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	if err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}

	if !response.Success {
		t.Error("Expected success to be true")
	}
	if response.ProcessedCount != 1 {
		t.Errorf("Expected processed count 1, got %d", response.ProcessedCount)
	}
	if len(response.Errors) != 0 {
		t.Errorf("Expected no errors, got %d", len(response.Errors))
	}
}

func TestBatchHandler_HandleBatch_InvalidContentType(t *testing.T) {
	storage := &mockStorage{}
	handler := createTestBatchHandler(storage, 100)

	req := httptest.NewRequest(http.MethodPost, "/batch", bytes.NewBuffer([]byte("test")))
	req.Header.Set("Content-Type", "text/plain")
	
	rr := httptest.NewRecorder()
	handler.HandleBatch(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("Expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var response models.BatchResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	if err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}

	if response.Success {
		t.Error("Expected success to be false")
	}
	if len(response.Errors) == 0 {
		t.Error("Expected error message")
	}
	if response.Errors[0] != "Content-Type must be application/json" {
		t.Errorf("Unexpected error message: %s", response.Errors[0])
	}
}

func TestBatchHandler_HandleBatch_InvalidJSON(t *testing.T) {
	storage := &mockStorage{}
	handler := createTestBatchHandler(storage, 100)

	req := httptest.NewRequest(http.MethodPost, "/batch", bytes.NewBuffer([]byte("invalid json")))
	req.Header.Set("Content-Type", "application/json")
	
	rr := httptest.NewRecorder()
	handler.HandleBatch(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("Expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var response models.BatchResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	if err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}

	if response.Success {
		t.Error("Expected success to be false")
	}
	if len(response.Errors) == 0 {
		t.Error("Expected error message")
	}
}

func TestBatchHandler_HandleBatch_EmptyBatch(t *testing.T) {
	storage := &mockStorage{}
	handler := createTestBatchHandler(storage, 100)

	batch := models.LogBatch{Logs: []*models.LogEntry{}}
	jsonData, _ := json.Marshal(batch)
	
	req := httptest.NewRequest(http.MethodPost, "/batch", bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	
	rr := httptest.NewRecorder()
	handler.HandleBatch(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("Expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var response models.BatchResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	if err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}

	if response.Success {
		t.Error("Expected success to be false")
	}
	if len(response.Errors) == 0 {
		t.Error("Expected error message")
	}
}

func TestBatchHandler_HandleBatch_ExceedsMaxSize(t *testing.T) {
	storage := &mockStorage{}
	maxBatchSize := 2
	handler := createTestBatchHandler(storage, maxBatchSize)

	// Create a batch that exceeds the limit
	batch := models.LogBatch{
		Logs: []*models.LogEntry{
			&models.LogEntry{Timestamp: 1704110400000, Message: "msg1", Source: "src1", Metadata: map[string]interface{}{"level": "INFO"}},
			&models.LogEntry{Timestamp: 1704110401000, Message: "msg2", Source: "src2", Metadata: map[string]interface{}{"level": "INFO"}},
			&models.LogEntry{Timestamp: 1704110402000, Message: "msg3", Source: "src3", Metadata: map[string]interface{}{"level": "INFO"}},
		},
	}

	jsonData, _ := json.Marshal(batch)
	req := httptest.NewRequest(http.MethodPost, "/batch", bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	
	rr := httptest.NewRecorder()
	handler.HandleBatch(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("Expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var response models.BatchResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	if err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}

	if response.Success {
		t.Error("Expected success to be false")
	}
	if len(response.Errors) == 0 {
		t.Error("Expected error message")
	}
}

func TestBatchHandler_HandleBatch_ValidationFailed(t *testing.T) {
	storage := &mockStorage{}
	handler := createTestBatchHandler(storage, 100)

	// Create a batch with invalid log entry (missing timestamp)
	batch := models.LogBatch{
		Logs: []*models.LogEntry{
			&models.LogEntry{
				Message: "Test log message",
				Source:  "test-source",
				Metadata: map[string]interface{}{"level": "INFO"},
				// Missing timestamp
			},
		},
	}

	jsonData, _ := json.Marshal(batch)
	req := httptest.NewRequest(http.MethodPost, "/batch", bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	
	rr := httptest.NewRecorder()
	handler.HandleBatch(rr, req)

	if rr.Code != http.StatusBadRequest {
		t.Errorf("Expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var response models.BatchResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	if err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}

	if response.Success {
		t.Error("Expected success to be false")
	}
	if len(response.Errors) == 0 {
		t.Error("Expected error message")
	}
}

func TestBatchHandler_HandleBatch_StorageError(t *testing.T) {
	storage := &mockStorage{shouldError: true, errorMessage: "storage failure"}
	handler := createTestBatchHandler(storage, 100)

	batch := models.LogBatch{
		Logs: []*models.LogEntry{
			&models.LogEntry{
				Timestamp: 1704110400000, // 2024-01-01T12:00:00Z
				Message:   "Test log message",
				Source:    "test-source",
				Metadata: map[string]interface{}{
					"level": "INFO",
				},
			},
		},
	}

	jsonData, _ := json.Marshal(batch)
	req := httptest.NewRequest(http.MethodPost, "/batch", bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	
	rr := httptest.NewRecorder()
	handler.HandleBatch(rr, req)

	if rr.Code != http.StatusInternalServerError {
		t.Errorf("Expected status %d, got %d", http.StatusInternalServerError, rr.Code)
	}

	var response models.BatchResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	if err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}

	if response.Success {
		t.Error("Expected success to be false")
	}
	if len(response.Errors) == 0 {
		t.Error("Expected error message")
	}
}

func TestBatchHandler_HandleBatch_MultipleLogs(t *testing.T) {
	storage := &mockStorage{}
	handler := createTestBatchHandler(storage, 100)

	batch := models.LogBatch{
		Logs: []*models.LogEntry{
			&models.LogEntry{Timestamp: 1704110400000, Message: "msg1", Source: "src1", Metadata: map[string]interface{}{"level": "INFO"}},
			&models.LogEntry{Timestamp: 1704110401000, Message: "msg2", Source: "src2", Metadata: map[string]interface{}{"level": "WARN"}},
			&models.LogEntry{Timestamp: 1704110402000, Message: "msg3", Source: "src3", Metadata: map[string]interface{}{"level": "ERROR"}},
		},
	}

	jsonData, _ := json.Marshal(batch)
	req := httptest.NewRequest(http.MethodPost, "/batch", bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	
	rr := httptest.NewRecorder()
	handler.HandleBatch(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("Expected status %d, got %d", http.StatusOK, rr.Code)
	}

	var response models.BatchResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	if err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}

	if !response.Success {
		t.Error("Expected success to be true")
	}
	if response.ProcessedCount != 3 {
		t.Errorf("Expected processed count 3, got %d", response.ProcessedCount)
	}
}

func TestBatchHandler_HandleBatch_WithMetadata(t *testing.T) {
	storage := &mockStorage{}
	handler := createTestBatchHandler(storage, 100)

	batch := models.LogBatch{
		Logs: []*models.LogEntry{
			&models.LogEntry{
				Timestamp: 1704110400000, // 2024-01-01T12:00:00Z
				Message:   "Test log message",
				Source:    "test-source",
				Metadata: map[string]interface{}{
					"level":     "INFO",
					"pod_name":  "test-pod",
					"namespace": "default",
					"node_name": "node-1",
					"labels": map[string]interface{}{
						"app": "test",
					},
				},
			},
		},
	}

	jsonData, _ := json.Marshal(batch)
	req := httptest.NewRequest(http.MethodPost, "/batch", bytes.NewBuffer(jsonData))
	req.Header.Set("Content-Type", "application/json")
	
	rr := httptest.NewRecorder()
	handler.HandleBatch(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("Expected status %d, got %d", http.StatusOK, rr.Code)
	}

	var response models.BatchResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	if err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}

	if !response.Success {
		t.Error("Expected success to be true")
	}
	if response.ProcessedCount != 1 {
		t.Errorf("Expected processed count 1, got %d", response.ProcessedCount)
	}
}

func TestBatchHandler_writeErrorResponse(t *testing.T) {
	storage := &mockStorage{}
	handler := createTestBatchHandler(storage, 100)

	rr := httptest.NewRecorder()
	handler.writeErrorResponse(rr, http.StatusBadRequest, "test error message")

	if rr.Code != http.StatusBadRequest {
		t.Errorf("Expected status %d, got %d", http.StatusBadRequest, rr.Code)
	}

	var response models.BatchResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	if err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}

	if response.Success {
		t.Error("Expected success to be false")
	}
	if len(response.Errors) != 1 {
		t.Errorf("Expected 1 error, got %d", len(response.Errors))
	}
	if response.Errors[0] != "test error message" {
		t.Errorf("Expected error message 'test error message', got '%s'", response.Errors[0])
	}

	contentType := rr.Header().Get("Content-Type")
	if contentType != "application/json" {
		t.Errorf("Expected Content-Type 'application/json', got '%s'", contentType)
	}
}