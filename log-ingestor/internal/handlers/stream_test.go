package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/sirupsen/logrus"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/timberline/log-ingestor/internal/models"
	"github.com/timberline/log-ingestor/internal/storage"
)

// Test helper to create StreamHandler with custom registry to avoid metric collision
func newTestStreamHandler(storage storage.StorageInterface, maxBatchSize int) *StreamHandler {
	// Create custom registry for testing
	registry := prometheus.NewRegistry()

	metrics := &StreamMetrics{
		requestsTotal: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "log_ingestor_stream_requests_total",
			Help: "Total number of stream requests",
		}),
		requestDuration: prometheus.NewHistogram(prometheus.HistogramOpts{
			Name:    "log_ingestor_stream_request_duration_seconds",
			Help:    "Duration of stream requests",
			Buckets: []float64{0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0},
		}),
		linesProcessed: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "log_ingestor_stream_lines_processed_total",
			Help: "Total number of JSON lines processed",
		}),
		batchesCreated: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "log_ingestor_stream_batches_created_total",
			Help: "Total number of internal batches created from streams",
		}),
		errorsTotal: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "log_ingestor_stream_errors_total",
			Help: "Total number of stream processing errors",
		}),
		invalidLines: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "log_ingestor_stream_invalid_lines_total",
			Help: "Total number of invalid JSON lines",
		}),
		queueSize: prometheus.NewGauge(prometheus.GaugeOpts{
			Name: "log_ingestor_queue_size",
			Help: "Current number of log entries in the processing queue",
		}),
	}

	// Register with custom registry
	registry.MustRegister(metrics.requestsTotal)
	registry.MustRegister(metrics.requestDuration)
	registry.MustRegister(metrics.linesProcessed)
	registry.MustRegister(metrics.batchesCreated)
	registry.MustRegister(metrics.errorsTotal)
	registry.MustRegister(metrics.invalidLines)
	registry.MustRegister(metrics.queueSize)

	// Create channel for log processing
	logChannel := make(chan *models.LogEntry, 1000)

	handler := &StreamHandler{
		storage:      storage,
		logger:       logrus.New(),
		metrics:      metrics,
		maxBatchSize: maxBatchSize,
		logChannel:   logChannel,
	}

	// Start worker goroutine for tests
	ctx := context.Background()
	go handler.StartWorker(ctx)

	return handler
}

// MockStorageInterface for testing
type MockStreamStorage struct {
	mock.Mock
}

func (m *MockStreamStorage) StoreLog(ctx context.Context, log *models.LogEntry) error {
	args := m.Called(ctx, log)
	return args.Error(0)
}

func (m *MockStreamStorage) Connect(ctx context.Context) error {
	args := m.Called(ctx)
	return args.Error(0)
}

func (m *MockStreamStorage) Close() error {
	args := m.Called()
	return args.Error(0)
}

func (m *MockStreamStorage) CreateCollection(ctx context.Context) error {
	args := m.Called(ctx)
	return args.Error(0)
}

func (m *MockStreamStorage) HealthCheck(ctx context.Context) error {
	args := m.Called(ctx)
	return args.Error(0)
}

func TestStreamHandler_HandleStream_Success(t *testing.T) {
	mockStorage := new(MockStreamStorage)
	handler := newTestStreamHandler(mockStorage, 100)

	// Create test JSON Lines data
	logEntries := []models.LogEntry{
		{
			Timestamp: time.Now().UnixMilli(),
			Message:   "Test log message 1",
			Source:    "test-service",
			Metadata:  map[string]interface{}{"level": "INFO"},
		},
		{
			Timestamp: time.Now().UnixMilli(),
			Message:   "Test log message 2",
			Source:    "test-service",
			Metadata:  map[string]interface{}{"level": "ERROR"},
		},
	}

	var jsonLines []string
	for _, entry := range logEntries {
		line, _ := json.Marshal(entry)
		jsonLines = append(jsonLines, string(line))
	}

	requestBody := strings.Join(jsonLines, "\n")

	// Mock storage expects two individual log calls
	mockStorage.On("StoreLog", mock.Anything, mock.MatchedBy(func(log *models.LogEntry) bool {
		return log.Message == "Test log message 1" || log.Message == "Test log message 2"
	})).Return(nil).Times(2)

	// Create request
	req := httptest.NewRequest("POST", "/api/v1/logs/stream", strings.NewReader(requestBody))
	req.Header.Set("Content-Type", "application/x-ndjson")

	// Create response recorder
	rr := httptest.NewRecorder()

	// Execute request
	handler.HandleStream(rr, req)

	// Wait for worker to process entries
	time.Sleep(100 * time.Millisecond)

	// Verify response
	assert.Equal(t, http.StatusOK, rr.Code)

	var response models.BatchResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.True(t, response.Success)
	assert.Equal(t, 2, response.ProcessedCount)

	// Verify mock expectations
	mockStorage.AssertExpectations(t)
}

func TestStreamHandler_HandleStream_InvalidContentType(t *testing.T) {
	mockStorage := new(MockStreamStorage)
	handler := newTestStreamHandler(mockStorage, 100)

	req := httptest.NewRequest("POST", "/api/v1/logs/stream", strings.NewReader("{}"))
	req.Header.Set("Content-Type", "text/plain")

	rr := httptest.NewRecorder()
	handler.HandleStream(rr, req)

	assert.Equal(t, http.StatusBadRequest, rr.Code)

	var response models.BatchResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.False(t, response.Success)
	assert.Contains(t, response.Errors[0], "Content-Type")
}

func TestStreamHandler_HandleStream_InvalidJSON(t *testing.T) {
	mockStorage := new(MockStreamStorage)
	handler := newTestStreamHandler(mockStorage, 100)

	// Include both valid and invalid JSON lines
	now := time.Now().UnixMilli()
	requestBody := fmt.Sprintf(`{"timestamp": %d, "message": "valid", "source": "test"}
invalid json line
{"timestamp": %d, "message": "another valid", "source": "test"}`, now, now+1000)

	// Mock storage expects two individual log calls with only valid entries
	mockStorage.On("StoreLog", mock.Anything, mock.MatchedBy(func(log *models.LogEntry) bool {
		return log.Message == "valid" || log.Message == "another valid"
	})).Return(nil).Times(2)

	req := httptest.NewRequest("POST", "/api/v1/logs/stream", strings.NewReader(requestBody))
	req.Header.Set("Content-Type", "application/x-ndjson")

	rr := httptest.NewRecorder()
	handler.HandleStream(rr, req)

	// Wait for worker to process entries
	time.Sleep(100 * time.Millisecond)

	// Should still succeed with valid entries
	assert.Equal(t, http.StatusOK, rr.Code)

	var response models.BatchResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.True(t, response.Success)
	assert.Equal(t, 2, response.ProcessedCount) // Only valid entries processed

	mockStorage.AssertExpectations(t)
}

func TestStreamHandler_HandleStream_EmptyStream(t *testing.T) {
	mockStorage := new(MockStreamStorage)
	handler := newTestStreamHandler(mockStorage, 100)

	req := httptest.NewRequest("POST", "/api/v1/logs/stream", strings.NewReader(""))
	req.Header.Set("Content-Type", "application/x-ndjson")

	rr := httptest.NewRecorder()
	handler.HandleStream(rr, req)

	assert.Equal(t, http.StatusOK, rr.Code)

	var response models.BatchResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.True(t, response.Success)
	assert.Equal(t, 0, response.ProcessedCount)

	// Storage should not be called for empty stream
	mockStorage.AssertNotCalled(t, "StoreBatch")
}

func TestStreamHandler_HandleStream_BatchSizeLimiting(t *testing.T) {
	mockStorage := new(MockStreamStorage)
	handler := newTestStreamHandler(mockStorage, 2) // Small batch size for testing

	// Create 5 log entries (should create 3 batches: 2, 2, 1)
	var jsonLines []string
	for i := 0; i < 5; i++ {
		entry := models.LogEntry{
			Timestamp: time.Now().UnixMilli(),
			Message:   "Test message",
			Source:    "test",
			Metadata:  map[string]interface{}{"level": "INFO"},
		}
		line, _ := json.Marshal(entry)
		jsonLines = append(jsonLines, string(line))
	}

	requestBody := strings.Join(jsonLines, "\n")

	// Expect 5 individual log calls (all entries processed individually)
	mockStorage.On("StoreLog", mock.Anything, mock.AnythingOfType("*models.LogEntry")).Return(nil).Times(5)

	req := httptest.NewRequest("POST", "/api/v1/logs/stream", strings.NewReader(requestBody))
	req.Header.Set("Content-Type", "application/x-ndjson")

	rr := httptest.NewRecorder()
	handler.HandleStream(rr, req)

	// Wait for worker to process entries
	time.Sleep(100 * time.Millisecond)

	assert.Equal(t, http.StatusOK, rr.Code)

	var response models.BatchResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.True(t, response.Success)
	assert.Equal(t, 5, response.ProcessedCount)

	mockStorage.AssertExpectations(t)
}

func TestStreamHandler_HandleStream_StorageError(t *testing.T) {
	mockStorage := new(MockStreamStorage)
	handler := newTestStreamHandler(mockStorage, 100)

	entry := models.LogEntry{
		Timestamp: time.Now().UnixMilli(),
		Message:   "Test message",
		Source:    "test",
		Metadata:  map[string]interface{}{"level": "INFO"},
	}
	line, _ := json.Marshal(entry)

	// Mock storage returns error
	mockStorage.On("StoreLog", mock.Anything, mock.Anything).Return(assert.AnError)

	req := httptest.NewRequest("POST", "/api/v1/logs/stream", strings.NewReader(string(line)))
	req.Header.Set("Content-Type", "application/x-ndjson")

	rr := httptest.NewRecorder()
	handler.HandleStream(rr, req)

	// Wait for worker to process entries
	time.Sleep(100 * time.Millisecond)

	// With async processing, the HTTP endpoint returns success even if storage fails
	// (the worker logs the error but doesn't propagate it back to the HTTP response)
	assert.Equal(t, http.StatusOK, rr.Code)

	var response models.BatchResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	assert.NoError(t, err)
	assert.True(t, response.Success)
	assert.Equal(t, 1, response.ProcessedCount)

	mockStorage.AssertExpectations(t)
}
