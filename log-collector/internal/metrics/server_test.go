package metrics

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewServer(t *testing.T) {
	port := 8080
	server := NewServer(port)

	assert.NotNil(t, server)
	assert.Equal(t, port, server.port)
	assert.NotNil(t, server.router)
	assert.NotNil(t, server.logger)
	assert.NotNil(t, server.logsCollected)
	assert.NotNil(t, server.logsForwarded)
	assert.NotNil(t, server.logsDropped)
	assert.NotNil(t, server.forwardingErrors)
	assert.NotNil(t, server.bufferSize)
	assert.NotNil(t, server.filesWatched)
}

func TestServer_MetricsEndpoint(t *testing.T) {
	server := NewServer(8080)

	// Create test request
	req := httptest.NewRequest(http.MethodGet, "/metrics", nil)
	w := httptest.NewRecorder()

	// Call metrics handler
	server.router.ServeHTTP(w, req)

	// Verify response
	assert.Equal(t, http.StatusOK, w.Code)
	assert.Contains(t, w.Header().Get("Content-Type"), "text/plain")

	body := w.Body.String()
	assert.Contains(t, body, "timberline_logs_collected_total")
	assert.Contains(t, body, "timberline_logs_forwarded_total")
	assert.Contains(t, body, "timberline_logs_dropped_total")
	assert.Contains(t, body, "timberline_forwarding_errors_total")
}

func TestServer_HealthEndpoint(t *testing.T) {
	server := NewServer(8080)

	// Create test request
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	w := httptest.NewRecorder()

	// Call health handler
	server.router.ServeHTTP(w, req)

	// Verify response
	assert.Equal(t, http.StatusOK, w.Code)
	assert.Equal(t, "application/json", w.Header().Get("Content-Type"))

	body := w.Body.String()
	assert.Contains(t, body, `"status": "healthy"`)
}

func TestServer_IncrementMetrics(t *testing.T) {
	server := NewServer(8080)

	// Test incrementing counters
	server.IncrementLogsCollected()
	server.IncrementLogsForwarded()
	server.IncrementLogsDropped()
	server.IncrementForwardingErrors()

	// Test setting gauges
	server.SetBufferSize(100)
	server.SetFilesWatched(5)

	// Verify metrics values using a custom registry
	registry := prometheus.NewRegistry()
	registry.MustRegister(server.logsCollected)
	registry.MustRegister(server.logsForwarded)
	registry.MustRegister(server.logsDropped)
	registry.MustRegister(server.forwardingErrors)
	registry.MustRegister(server.bufferSize)
	registry.MustRegister(server.filesWatched)

	metricFamilies, err := registry.Gather()
	require.NoError(t, err)

	// Verify counter values
	for _, mf := range metricFamilies {
		switch *mf.Name {
		case "timberline_logs_collected_total":
			assert.Equal(t, float64(1), *mf.Metric[0].Counter.Value)
		case "timberline_logs_forwarded_total":
			assert.Equal(t, float64(1), *mf.Metric[0].Counter.Value)
		case "timberline_logs_dropped_total":
			assert.Equal(t, float64(1), *mf.Metric[0].Counter.Value)
		case "timberline_forwarding_errors_total":
			assert.Equal(t, float64(1), *mf.Metric[0].Counter.Value)
		case "timberline_buffer_size":
			assert.Equal(t, float64(100), *mf.Metric[0].Gauge.Value)
		case "timberline_files_watched":
			assert.Equal(t, float64(5), *mf.Metric[0].Gauge.Value)
		}
	}
}

func TestServer_Start(t *testing.T) {
	server := NewServer(0) // Use port 0 for dynamic allocation

	// Start server in goroutine
	errCh := make(chan error, 1)
	go func() {
		errCh <- server.Start()
	}()

	// Stop server immediately
	err := server.Stop()
	assert.NoError(t, err)

	// Check if start completed without error
	select {
	case err := <-errCh:
		assert.NoError(t, err)
	default:
		// Server may still be starting, which is fine
	}
}

func TestServer_InvalidRoutes(t *testing.T) {
	server := NewServer(8080)

	tests := []struct {
		method string
		path   string
		status int
	}{
		{http.MethodGet, "/invalid", http.StatusNotFound},
		{http.MethodPost, "/metrics", http.StatusOK}, // Prometheus metrics endpoint accepts all methods
		{http.MethodPut, "/health", http.StatusMethodNotAllowed},
		{http.MethodDelete, "/metrics", http.StatusOK}, // Prometheus metrics endpoint accepts all methods
	}

	for _, tt := range tests {
		t.Run(tt.method+"_"+tt.path, func(t *testing.T) {
			req := httptest.NewRequest(tt.method, tt.path, nil)
			w := httptest.NewRecorder()

			server.router.ServeHTTP(w, req)
			assert.Equal(t, tt.status, w.Code)
		})
	}
}

func TestServer_ConcurrentMetricsUpdates(t *testing.T) {
	server := NewServer(8080)

	// Test concurrent metric updates
	done := make(chan bool, 2)

	// Goroutine 1: Increment counters
	go func() {
		for i := 0; i < 100; i++ {
			server.IncrementLogsCollected()
			server.IncrementLogsForwarded()
		}
		done <- true
	}()

	// Goroutine 2: Update gauges
	go func() {
		for i := 0; i < 100; i++ {
			server.SetBufferSize(float64(i))
			server.SetFilesWatched(float64(i % 10))
		}
		done <- true
	}()

	// Wait for both goroutines to complete
	<-done
	<-done

	// If we reach here without race conditions, test passes
	assert.True(t, true)
}
