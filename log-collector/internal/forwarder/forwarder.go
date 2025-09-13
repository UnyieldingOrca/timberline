package forwarder

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/sirupsen/logrus"
	"github.com/timberline/log-collector/internal/config"
	"github.com/timberline/log-collector/internal/models"
)

// Interface defines the contract for log forwarders
type Interface interface {
	// Forward sends a batch of log entries to the destination
	Forward(entries []*models.LogEntry) error
	// Stop gracefully stops the forwarder
	Stop(ctx context.Context) error
}

// HTTPForwarder forwards logs via HTTP
type HTTPForwarder struct {
	url        string
	maxRetries int
	client     *http.Client
}

// NewHTTPForwarder creates a new HTTP forwarder
func NewHTTPForwarder(url string) *HTTPForwarder {
	forwarder := &HTTPForwarder{
		url:        url,
		maxRetries: 3,
		client:     &http.Client{Timeout: 30 * time.Second},
	}
	// Note: Logger is not available in this constructor, debug logging will happen in Forward method
	return forwarder
}

// Forward implements the Interface
func (h *HTTPForwarder) Forward(entries []*models.LogEntry) error {
	// Create a logger for this method (since we don't have one in the struct)
	logger := logrus.New()
	logger.WithFields(logrus.Fields{
		"entries_count": len(entries),
		"url": h.url,
	}).Debug("HTTPForwarder.Forward called")

	if len(entries) == 0 {
		logger.Debug("No entries to forward, returning")
		return nil // nothing to send
	}

	// Create a batch according to the log-ingestor API specification
	logger.Debug("Creating log batch for forwarding")
	batch := &models.LogBatch{
		Logs: entries,
	}

	logger.Debug("Marshaling batch to JSON")
	data, err := json.Marshal(batch)
	if err != nil {
		logger.WithError(err).Error("Failed to marshal batch to JSON")
		return err
	}
	logger.WithField("payload_size", len(data)).Debug("Batch marshaled successfully")

	var lastErr error
	logger.WithField("max_retries", h.maxRetries).Debug("Starting HTTP forwarding with retries")
	for attempt := 0; attempt <= h.maxRetries; attempt++ {
		logger.WithField("attempt", attempt+1).Debug("Making HTTP request attempt")
		if attempt > 0 {
			// Exponential backoff: 100ms, 200ms, 400ms
			backoff := time.Duration(100*(1<<uint(attempt-1))) * time.Millisecond
			logger.WithFields(logrus.Fields{
				"attempt": attempt+1,
				"backoff_ms": backoff.Milliseconds(),
			}).Debug("Applying exponential backoff before retry")
			time.Sleep(backoff)
		}

		logger.WithFields(logrus.Fields{
			"url": h.url,
			"attempt": attempt+1,
			"payload_size": len(data),
		}).Debug("Making POST request to ingestor")
		resp, err := h.client.Post(h.url, "application/json", bytes.NewBuffer(data))
		if err != nil {
			logger.WithError(err).WithField("attempt", attempt+1).Debug("HTTP request failed")
			lastErr = err
			continue
		}
		defer func() {
			if err := resp.Body.Close(); err != nil {
				logger.WithError(err).Debug("Error closing response body")
			}
		}()

		logger.WithFields(logrus.Fields{
			"status_code": resp.StatusCode,
			"attempt": attempt+1,
		}).Debug("Received HTTP response")

		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			logger.WithFields(logrus.Fields{
				"status_code": resp.StatusCode,
				"attempt": attempt+1,
				"entries_count": len(entries),
			}).Debug("HTTP forward successful")
			return nil // Success
		}

		// Read response body for error details (limit to 1KB to avoid memory issues)
		logger.WithField("status_code", resp.StatusCode).Debug("Reading response body for error details")
		body, bodyErr := io.ReadAll(io.LimitReader(resp.Body, 1024))
		var bodyStr string
		if bodyErr == nil && len(body) > 0 {
			bodyStr = string(body)
			logger.WithField("response_body_length", len(body)).Debug("Read response body")
		} else {
			bodyStr = "no response body"
			logger.Debug("No response body available")
		}

		lastErr = fmt.Errorf("HTTP forwarder: received status %d from %s, response: %s, attempt %d/%d",
			resp.StatusCode, h.url, bodyStr, attempt+1, h.maxRetries+1)

		logger.WithFields(logrus.Fields{
			"status_code": resp.StatusCode,
			"is_server_error": resp.StatusCode >= 500,
			"will_retry": resp.StatusCode >= 500,
		}).Debug("Evaluating retry conditions")

		// Only retry on server errors (5xx), not client errors (4xx)
		if resp.StatusCode < 500 {
			logger.WithField("status_code", resp.StatusCode).Debug("Client error, not retrying")
			break
		}
		logger.WithField("status_code", resp.StatusCode).Debug("Server error, will retry if attempts remain")
	}

	logger.WithError(lastErr).WithField("final_attempt", h.maxRetries+1).Error("All HTTP forward attempts failed")
	return lastErr
}

// Stop implements the Interface - for HTTPForwarder, this is a no-op
func (h *HTTPForwarder) Stop(ctx context.Context) error {
	// HTTP forwarder has no persistent connections to close
	return nil
}

// New creates a new forwarder based on configuration
func New(cfg config.CollectorConfig, logger *logrus.Logger) (Interface, error) {
	logger.WithFields(logrus.Fields{
		"forwarder_url": cfg.ForwarderURL,
		"type": "HTTPForwarder",
	}).Debug("Creating new forwarder")
	forwarder := NewHTTPForwarder(cfg.ForwarderURL)
	logger.Debug("HTTPForwarder created successfully")
	return forwarder, nil
}
