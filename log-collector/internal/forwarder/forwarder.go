package forwarder

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
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
	return &HTTPForwarder{
		url:        url,
		maxRetries: 3,
		client:     &http.Client{Timeout: 30 * time.Second},
	}
}

// Forward implements the Interface
func (h *HTTPForwarder) Forward(entries []*models.LogEntry) error {
	if len(entries) == 0 {
		return nil // nothing to send
	}

	// Create a batch according to the log-ingestor API specification
	batch := &models.LogBatch{
		Logs: entries,
	}

	data, err := json.Marshal(batch)
	if err != nil {
		return err
	}

	var lastErr error
	for attempt := 0; attempt <= h.maxRetries; attempt++ {
		if attempt > 0 {
			// Exponential backoff: 100ms, 200ms, 400ms
			backoff := time.Duration(100*(1<<uint(attempt-1))) * time.Millisecond
			time.Sleep(backoff)
		}

		resp, err := h.client.Post(h.url, "application/json", bytes.NewBuffer(data))
		if err != nil {
			lastErr = err
			continue
		}
		defer func() {
			if err := resp.Body.Close(); err != nil {
				// Log or handle error if needed, but don't break flow
				_ = err
			}
		}()

		if resp.StatusCode >= 200 && resp.StatusCode < 300 {
			return nil // Success
		}

		lastErr = fmt.Errorf("HTTP forwarder: received status %d", resp.StatusCode)

		// Only retry on server errors (5xx), not client errors (4xx)
		if resp.StatusCode < 500 {
			break
		}
	}

	return lastErr
}

// Stop implements the Interface - for HTTPForwarder, this is a no-op
func (h *HTTPForwarder) Stop(ctx context.Context) error {
	// HTTP forwarder has no persistent connections to close
	return nil
}

// New creates a new forwarder based on configuration
func New(cfg config.CollectorConfig, logger *logrus.Logger) (Interface, error) {
	return NewHTTPForwarder(cfg.ForwarderURL), nil
}
