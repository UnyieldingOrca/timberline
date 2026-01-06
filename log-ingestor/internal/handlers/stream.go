package handlers

import (
	"bufio"
	"context"
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/sirupsen/logrus"
	"github.com/timberline/log-ingestor/internal/models"
	"github.com/timberline/log-ingestor/internal/storage"
)

// FlexibleTimestamp can unmarshal both string and numeric timestamps
type FlexibleTimestamp int64

func (ft *FlexibleTimestamp) UnmarshalJSON(data []byte) error {
	// Try to unmarshal as int64 first
	var intVal int64
	if err := json.Unmarshal(data, &intVal); err == nil {
		*ft = FlexibleTimestamp(intVal)
		return nil
	}

	// Try to unmarshal as string and parse
	var strVal string
	if err := json.Unmarshal(data, &strVal); err == nil {
		// Try parsing as ISO 8601 timestamp
		if t, err := time.Parse(time.RFC3339, strVal); err == nil {
			*ft = FlexibleTimestamp(t.Unix() * 1000) // Convert to milliseconds
			return nil
		}
		// Try parsing as other common formats
		formats := []string{
			"2006-01-02T15:04:05Z",
			"2006-01-02 15:04:05",
			"2006/01/02 15:04:05",
		}
		for _, format := range formats {
			if t, err := time.Parse(format, strVal); err == nil {
				*ft = FlexibleTimestamp(t.Unix() * 1000)
				return nil
			}
		}
		// Try parsing as numeric string
		if intVal, err := strconv.ParseInt(strVal, 10, 64); err == nil {
			*ft = FlexibleTimestamp(intVal)
			return nil
		}
	}

	// If all else fails, set to current time
	*ft = FlexibleTimestamp(time.Now().Unix() * 1000)
	return nil
}

// FluentBitLogEntry represents the standard format that Fluent Bit sends
type FluentBitLogEntry struct {
	Date       float64                `json:"date,omitempty"`       // Unix timestamp with microseconds
	Timestamp  FlexibleTimestamp      `json:"timestamp,omitempty"`  // Alternative timestamp field (flexible)
	Log        string                 `json:"log"`                  // The log message content
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

	// Handle timestamp - Fluent Bit can send either 'date' (float64) or 'timestamp' (flexible)
	if fb.Date > 0 {
		// Convert float64 Unix timestamp (seconds) to int64 milliseconds
		entry.Timestamp = int64(fb.Date * 1000)
	} else if fb.Timestamp > 0 {
		// FlexibleTimestamp is already processed and converted to milliseconds
		timestamp := int64(fb.Timestamp)
		// Check if timestamp is in seconds or milliseconds
		if timestamp < 1e12 { // Less than year 2001 in milliseconds means it's in seconds
			entry.Timestamp = timestamp * 1000
		} else {
			entry.Timestamp = timestamp
		}
	}

	// Set default source if not provided
	if entry.Source == "" {
		entry.Source = "unknown"
	}

	return entry
}

type StreamHandler struct {
	storage      storage.StorageInterface
	logger       *logrus.Logger
	metrics      *StreamMetrics
	maxBatchSize int
	logChannel   chan *models.LogEntry
}

type StreamMetrics struct {
	requestsTotal   prometheus.Counter
	requestDuration prometheus.Histogram
	linesProcessed  prometheus.Counter
	batchesCreated  prometheus.Counter
	errorsTotal     prometheus.Counter
	invalidLines    prometheus.Counter
	queueSize       prometheus.Gauge
}

func NewStreamHandler(storage storage.StorageInterface, maxBatchSize int, logChannel chan *models.LogEntry) *StreamHandler {
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

	// Register metrics, ignoring duplicate registration errors for tests
	_ = prometheus.DefaultRegisterer.Register(metrics.requestsTotal)
	_ = prometheus.DefaultRegisterer.Register(metrics.requestDuration)
	_ = prometheus.DefaultRegisterer.Register(metrics.linesProcessed)
	_ = prometheus.DefaultRegisterer.Register(metrics.batchesCreated)
	_ = prometheus.DefaultRegisterer.Register(metrics.errorsTotal)
	_ = prometheus.DefaultRegisterer.Register(metrics.invalidLines)
	_ = prometheus.DefaultRegisterer.Register(metrics.queueSize)

	return &StreamHandler{
		storage:      storage,
		logger:       logrus.StandardLogger(),
		metrics:      metrics,
		maxBatchSize: maxBatchSize,
		logChannel:   logChannel,
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
	defer func() { _ = r.Body.Close() }()

	totalProcessed := 0

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

		// Publish to channel for async processing
		select {
		case h.logChannel <- logEntry:
			h.metrics.linesProcessed.Inc()
			totalProcessed++
		default:
			// Channel is full, log warning but don't block
			h.logger.Warn("Log channel full, dropping log entry")
			h.metrics.errorsTotal.Inc()
		}
	}

	// Check for scanner errors
	if err := scanner.Err(); err != nil {
		return totalProcessed, err
	}

	return totalProcessed, nil
}

// StartWorker starts a worker goroutine that processes log entries from the channel
func (h *StreamHandler) StartWorker(ctx context.Context) {
	// Update queue size metric periodically
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			// Context cancelled, exit
			return

		case logEntry, ok := <-h.logChannel:
			if !ok {
				// Channel closed, exit
				return
			}

			// Update queue size metric
			h.metrics.queueSize.Set(float64(len(h.logChannel)))

			// Store log entry directly
			if err := h.storage.StoreLog(ctx, logEntry); err != nil {
				h.logger.WithError(err).Error("Failed to store log")
				h.metrics.errorsTotal.Inc()
			}

		case <-ticker.C:
			// Periodic queue size update (in case queue is idle)
			h.metrics.queueSize.Set(float64(len(h.logChannel)))
		}
	}
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
