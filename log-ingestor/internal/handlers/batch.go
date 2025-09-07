package handlers

import (
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

type BatchHandler struct {
	storage      storage.StorageInterface
	logger       *logrus.Logger
	metrics      *BatchMetrics
	maxBatchSize int
}

type BatchMetrics struct {
	requestsTotal    prometheus.Counter
	requestDuration  prometheus.Histogram
	batchSizeHist    prometheus.Histogram
	errorsTotal      prometheus.Counter
	logsProcessed    prometheus.Counter
}

func NewBatchHandler(storage storage.StorageInterface, maxBatchSize int) *BatchHandler {
	metrics := &BatchMetrics{
		requestsTotal: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "log_ingestor_batch_requests_total",
			Help: "Total number of batch requests",
		}),
		requestDuration: prometheus.NewHistogram(prometheus.HistogramOpts{
			Name:    "log_ingestor_batch_request_duration_seconds",
			Help:    "Duration of batch requests",
			Buckets: []float64{0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0},
		}),
		batchSizeHist: prometheus.NewHistogram(prometheus.HistogramOpts{
			Name:    "log_ingestor_batch_size",
			Help:    "Size of log batches",
			Buckets: []float64{1, 5, 10, 50, 100, 500, 1000},
		}),
		errorsTotal: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "log_ingestor_batch_errors_total",
			Help: "Total number of batch processing errors",
		}),
		logsProcessed: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "log_ingestor_logs_processed_total",
			Help: "Total number of logs processed",
		}),
	}

	// Register metrics
	prometheus.MustRegister(metrics.requestsTotal)
	prometheus.MustRegister(metrics.requestDuration)
	prometheus.MustRegister(metrics.batchSizeHist)
	prometheus.MustRegister(metrics.errorsTotal)
	prometheus.MustRegister(metrics.logsProcessed)

	return &BatchHandler{
		storage:      storage,
		logger:       logrus.New(),
		metrics:      metrics,
		maxBatchSize: maxBatchSize,
	}
}

func (h *BatchHandler) HandleBatch(w http.ResponseWriter, r *http.Request) {
	startTime := time.Now()
	h.metrics.requestsTotal.Inc()

	// Ensure proper content type
	if r.Header.Get("Content-Type") != "application/json" {
		h.writeErrorResponse(w, http.StatusBadRequest, "Content-Type must be application/json")
		h.metrics.errorsTotal.Inc()
		return
	}

	// Parse request body
	var batch models.LogBatch
	decoder := json.NewDecoder(r.Body)
	decoder.DisallowUnknownFields()

	if err := decoder.Decode(&batch); err != nil {
		h.logger.WithError(err).Warn("Failed to decode batch request")
		h.writeErrorResponse(w, http.StatusBadRequest, "Invalid JSON format")
		h.metrics.errorsTotal.Inc()
		return
	}

	// Validate batch size
	if batch.Size() == 0 {
		h.writeErrorResponse(w, http.StatusBadRequest, "Batch cannot be empty")
		h.metrics.errorsTotal.Inc()
		return
	}

	if batch.Size() > h.maxBatchSize {
		h.writeErrorResponse(w, http.StatusBadRequest, 
			"Batch size ("+strconv.Itoa(batch.Size())+") exceeds maximum ("+strconv.Itoa(h.maxBatchSize)+")")
		h.metrics.errorsTotal.Inc()
		return
	}

	// Validate batch content
	if err := batch.Validate(); err != nil {
		h.logger.WithError(err).Warn("Batch validation failed")
		h.writeErrorResponse(w, http.StatusBadRequest, "Validation failed: "+err.Error())
		h.metrics.errorsTotal.Inc()
		return
	}

	// Store batch with timeout
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()

	if err := h.storage.StoreBatch(ctx, &batch); err != nil {
		h.logger.WithError(err).Error("Failed to store batch")
		h.writeErrorResponse(w, http.StatusInternalServerError, "Storage error")
		h.metrics.errorsTotal.Inc()
		return
	}

	// Update metrics
	h.metrics.batchSizeHist.Observe(float64(batch.Size()))
	h.metrics.logsProcessed.Add(float64(batch.Size()))
	h.metrics.requestDuration.Observe(time.Since(startTime).Seconds())

	// Send success response
	response := models.BatchResponse{
		Success:        true,
		ProcessedCount: batch.Size(),
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(response)

	h.logger.WithFields(logrus.Fields{
		"processed_count": batch.Size(),
		"duration":        time.Since(startTime),
	}).Info("Batch processed successfully")
}

func (h *BatchHandler) writeErrorResponse(w http.ResponseWriter, statusCode int, message string) {
	response := models.BatchResponse{
		Success: false,
		Errors:  []string{message},
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	json.NewEncoder(w).Encode(response)
}