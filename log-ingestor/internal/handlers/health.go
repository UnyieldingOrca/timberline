package handlers

import (
	"context"
	"encoding/json"
	"net/http"
	"time"

	"github.com/sirupsen/logrus"
	"github.com/timberline/log-ingestor/internal/models"
	"github.com/timberline/log-ingestor/internal/storage"
)

type HealthHandler struct {
	storage   storage.StorageInterface
	logger    *logrus.Logger
	startTime time.Time
	version   string
}

func NewHealthHandler(storage storage.StorageInterface, version string, logger *logrus.Logger) *HealthHandler {
	return &HealthHandler{
		storage:   storage,
		logger:    logger,
		startTime: time.Now(),
		version:   version,
	}
}

func (h *HealthHandler) HandleHealth(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second)
	defer cancel()

	checks := []models.HealthCheck{
		h.checkStorage(ctx),
	}

	overallStatus := "healthy"
	for _, check := range checks {
		if check.Status != "healthy" {
			overallStatus = "unhealthy"
			break
		}
	}

	response := models.HealthResponse{
		Status:    overallStatus,
		Timestamp: time.Now(),
		Version:   h.version,
		Uptime:    time.Since(h.startTime).String(),
		Checks:    checks,
	}

	statusCode := http.StatusOK
	if overallStatus != "healthy" {
		statusCode = http.StatusServiceUnavailable
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	_ = json.NewEncoder(w).Encode(response)

	h.logger.WithFields(logrus.Fields{
		"status":      overallStatus,
		"status_code": statusCode,
	}).Debug("Health check completed")
}

func (h *HealthHandler) checkStorage(ctx context.Context) models.HealthCheck {
	if err := h.storage.HealthCheck(ctx); err != nil {
		h.logger.WithError(err).Warn("Storage health check failed")
		return models.HealthCheck{
			Name:    "storage",
			Status:  "unhealthy",
			Message: err.Error(),
		}
	}

	return models.HealthCheck{
		Name:   "storage",
		Status: "healthy",
	}
}

func (h *HealthHandler) HandleLiveness(w http.ResponseWriter, r *http.Request) {
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("OK"))
}

func (h *HealthHandler) HandleReadiness(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()

	if err := h.storage.HealthCheck(ctx); err != nil {
		h.logger.WithError(err).Warn("Readiness check failed")
		w.WriteHeader(http.StatusServiceUnavailable)
		_, _ = w.Write([]byte("Not Ready"))
		return
	}

	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte("Ready"))
}
