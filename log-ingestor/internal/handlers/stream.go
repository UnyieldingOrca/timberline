package handlers

import (
	"bufio"
	"context"
	"encoding/json"
	"net/http"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/sirupsen/logrus"
	"github.com/timberline/log-ingestor/internal/models"
	"github.com/timberline/log-ingestor/internal/storage"
)

// FluentBitLogEntry represents the standard format that Fluent Bit sends
type FluentBitLogEntry struct {
	Date       float64                `json:"date,omitempty"`       // Unix timestamp with microseconds
	Timestamp  int64                  `json:"timestamp,omitempty"`  // Alternative timestamp field
	Log        string                 `json:"log"`                  // The actual log message
	Kubernetes map[string]interface{} `json:"kubernetes,omitempty"` // Kubernetes metadata
	Source     string                 `json:"source,omitempty"`     // Source identifier
}

// transformFluentBitEntry converts a Fluent Bit log entry to our internal format
func (fb *FluentBitLogEntry) transformToLogEntry() *models.LogEntry {
	entry := &models.LogEntry{
		Message:  fb.Log,
		Source:   fb.Source,
		Metadata: fb.Kubernetes,
	}

	// Handle timestamp - Fluent Bit can send either 'date' (float64) or 'timestamp' (int64)
	if fb.Date > 0 {
		// Convert float64 Unix timestamp (seconds) to int64 milliseconds
		entry.Timestamp = int64(fb.Date * 1000)
	} else if fb.Timestamp > 0 {
		// Check if timestamp is in seconds or milliseconds
		if fb.Timestamp < 1e12 { // Less than year 2001 in milliseconds means it's in seconds
			entry.Timestamp = fb.Timestamp * 1000
		} else {
			entry.Timestamp = fb.Timestamp
		}
	}

	// Ensure source is set if not provided
	if entry.Source == "" {
		entry.Source = "fluent-bit"
	}

	return entry
}

type StreamHandler struct {
	storage      storage.StorageInterface
	logger       *logrus.Logger
	metrics      *StreamMetrics
	maxBatchSize int
}

type StreamMetrics struct {
	requestsTotal    prometheus.Counter
	requestDuration  prometheus.Histogram
	linesProcessed   prometheus.Counter
	batchesCreated   prometheus.Counter
	errorsTotal      prometheus.Counter
	invalidLines     prometheus.Counter
}

func NewStreamHandler(storage storage.StorageInterface, maxBatchSize int) *StreamHandler {
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
	}

	// Register metrics, ignoring duplicate registration errors for tests
	prometheus.DefaultRegisterer.Register(metrics.requestsTotal)
	prometheus.DefaultRegisterer.Register(metrics.requestDuration)
	prometheus.DefaultRegisterer.Register(metrics.linesProcessed)
	prometheus.DefaultRegisterer.Register(metrics.batchesCreated)
	prometheus.DefaultRegisterer.Register(metrics.errorsTotal)
	prometheus.DefaultRegisterer.Register(metrics.invalidLines)

	return &StreamHandler{
		storage:      storage,
		logger:       logrus.StandardLogger(),
		metrics:      metrics,
		maxBatchSize: maxBatchSize,
	}
}

func (h *StreamHandler) HandleStream(w http.ResponseWriter, r *http.Request) {
	startTime := time.Now()
	h.metrics.requestsTotal.Inc()

	// Ensure proper content type for JSON Lines
	contentType := r.Header.Get("Content-Type")
	if contentType != "application/x-ndjson" && contentType != "application/json" {
		h.writeErrorResponse(w, http.StatusBadRequest, "Content-Type must be application/x-ndjson or application/json")
		h.metrics.errorsTotal.Inc()
		return
	}

	// Process the stream
	processedCount, err := h.processStream(r)
	if err != nil {
		h.logger.WithError(err).Error("Failed to process stream")
		h.writeErrorResponse(w, http.StatusInternalServerError, "Stream processing error")
		h.metrics.errorsTotal.Inc()
		return
	}

	// Update metrics
	h.metrics.requestDuration.Observe(time.Since(startTime).Seconds())

	// Send success response
	response := models.BatchResponse{
		Success:        true,
		ProcessedCount: processedCount,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(response)

	h.logger.WithFields(logrus.Fields{
		"processed_count": processedCount,
		"duration":        time.Since(startTime),
	}).Info("Stream processed successfully")
}

func (h *StreamHandler) processStream(r *http.Request) (int, error) {
	scanner := bufio.NewScanner(r.Body)
	defer r.Body.Close()

	var batch []*models.LogEntry
	totalProcessed := 0

	// Create timeout context for storage operations
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()

	for scanner.Scan() {
		line := scanner.Text()

		// Skip empty lines
		if len(line) == 0 {
			continue
		}

		// DEBUG: Log raw line from Fluent Bit
		h.logger.WithField("raw_line", line).Debug("Received raw line from Fluent Bit")

		// Try to parse as LogEntry format first (for backward compatibility)
		var logEntry *models.LogEntry
		var directLogEntry models.LogEntry

		if err := json.Unmarshal([]byte(line), &directLogEntry); err == nil && directLogEntry.Message != "" {
			// Successfully parsed as direct LogEntry format
			logEntry = &directLogEntry
		} else {
			// Try to parse as Fluent Bit format
			var fluentBitEntry FluentBitLogEntry
			if err := json.Unmarshal([]byte(line), &fluentBitEntry); err != nil {
				h.logger.WithError(err).WithField("line", line).Warn("Failed to parse JSON line")
				h.metrics.invalidLines.Inc()
				continue
			}

			// Transform Fluent Bit format to our internal format
			logEntry = fluentBitEntry.transformToLogEntry()
		}

		// DEBUG: Log transformed entry structure
		h.logger.WithField("transformed_entry", logEntry).Debug("Transformed log entry structure")

		// Validate log entry
		if err := logEntry.Validate(); err != nil {
			h.logger.WithError(err).WithField("entry", logEntry).Warn("Invalid log entry")
			h.metrics.invalidLines.Inc()
			continue
		}

		batch = append(batch, logEntry)
		h.metrics.linesProcessed.Inc()

		// Process batch when it reaches max size
		if len(batch) >= h.maxBatchSize {
			if err := h.storeBatch(ctx, batch); err != nil {
				return totalProcessed, err
			}
			totalProcessed += len(batch)
			batch = batch[:0] // Reset batch
		}
	}

	// Process remaining entries in final batch
	if len(batch) > 0 {
		if err := h.storeBatch(ctx, batch); err != nil {
			return totalProcessed, err
		}
		totalProcessed += len(batch)
	}

	// Check for scanner errors
	if err := scanner.Err(); err != nil {
		return totalProcessed, err
	}

	return totalProcessed, nil
}

func (h *StreamHandler) storeBatch(ctx context.Context, entries []*models.LogEntry) error {
	if len(entries) == 0 {
		return nil
	}

	batch := &models.LogBatch{
		Logs: entries,
	}

	if err := h.storage.StoreBatch(ctx, batch); err != nil {
		return err
	}

	h.metrics.batchesCreated.Inc()
	return nil
}

func (h *StreamHandler) writeErrorResponse(w http.ResponseWriter, statusCode int, message string) {
	response := models.BatchResponse{
		Success: false,
		Errors:  []string{message},
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	_ = json.NewEncoder(w).Encode(response)
}