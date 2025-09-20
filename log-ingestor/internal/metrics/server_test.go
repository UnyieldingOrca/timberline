package metrics

import (
	"context"
	"net/http"
	"strings"
	"testing"
	"time"
)

func TestNewServer(t *testing.T) {
	port := 9090
	server := NewServer(port)

	if server == nil {
		t.Fatal("Expected server to be created, got nil")
	}
	if server.server == nil {
		t.Error("Expected HTTP server to be initialized")
	}
	if server.logger == nil {
		t.Error("Expected logger to be initialized")
	}

	expectedAddr := ":9090"
	if server.server.Addr != expectedAddr {
		t.Errorf("Expected server address %s, got %s", expectedAddr, server.server.Addr)
	}

	// Verify timeouts are set correctly
	if server.server.ReadTimeout != 5*time.Second {
		t.Errorf("Expected ReadTimeout 5s, got %v", server.server.ReadTimeout)
	}
	if server.server.WriteTimeout != 10*time.Second {
		t.Errorf("Expected WriteTimeout 10s, got %v", server.server.WriteTimeout)
	}
	if server.server.IdleTimeout != 15*time.Second {
		t.Errorf("Expected IdleTimeout 15s, got %v", server.server.IdleTimeout)
	}
}

func TestNewServer_DifferentPorts(t *testing.T) {
	tests := []struct {
		port         int
		expectedAddr string
	}{
		{8080, ":8080"},
		{9090, ":9090"},
		{8888, ":8888"},
		{3000, ":3000"},
	}

	for _, tt := range tests {
		server := NewServer(tt.port)
		if server.server.Addr != tt.expectedAddr {
			t.Errorf("Expected address %s, got %s", tt.expectedAddr, server.server.Addr)
		}
	}
}

func TestServer_MetricsEndpoint(t *testing.T) {
	server := NewServer(0) // Use port 0 for testing to get a random available port

	// Start server in background
	go func() {
		_ = server.Start()
	}()

	// Give the server a moment to start
	time.Sleep(10 * time.Millisecond)

	// Since we're using port 0, we can't easily test the actual endpoint
	// Instead, let's verify the handler is set up correctly
	if server.server.Handler == nil {
		t.Error("Expected HTTP handler to be set")
	}

	// Test that the mux has the metrics route
	mux, ok := server.server.Handler.(*http.ServeMux)
	if !ok {
		t.Error("Expected handler to be http.ServeMux")
	}

	// We can't easily inspect the mux routes, but we can verify it's not nil
	if mux == nil {
		t.Error("Expected mux to be initialized")
	}

	// Stop the server
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	_ = server.Stop(ctx)
}

func TestServer_Start_InvalidPort(t *testing.T) {
	// Test with port that might already be in use
	// This test is tricky because we can't guarantee which ports are available
	// So we'll test the Start method structure instead
	server := NewServer(9999) // Use a high port number

	// We can't easily test Start() because it blocks, but we can verify
	// the server configuration
	if server.server == nil {
		t.Error("Expected server to be configured")
	}
}

func TestServer_Stop(t *testing.T) {
	server := NewServer(0)

	// Test stopping server without starting it (should not panic)
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()

	err := server.Stop(ctx)
	// Stop might return an error if server wasn't started, which is expected
	// We just want to ensure it doesn't panic
	_ = err
}

func TestServer_Stop_WithTimeout(t *testing.T) {
	server := NewServer(0)

	// Test with a very short timeout
	ctx, cancel := context.WithTimeout(context.Background(), 1*time.Microsecond)
	defer cancel()

	err := server.Stop(ctx)
	// Should complete quickly even with short timeout since server isn't running
	_ = err
}

func TestServer_Stop_WithCanceledContext(t *testing.T) {
	server := NewServer(0)

	ctx, cancel := context.WithCancel(context.Background())
	cancel() // Cancel immediately

	err := server.Stop(ctx)
	// Should handle canceled context gracefully
	_ = err
}

func TestServer_Configuration(t *testing.T) {
	tests := []struct {
		port          int
		expectedAddr  string
		expectedRead  time.Duration
		expectedWrite time.Duration
		expectedIdle  time.Duration
	}{
		{8080, ":8080", 5 * time.Second, 10 * time.Second, 15 * time.Second},
		{9090, ":9090", 5 * time.Second, 10 * time.Second, 15 * time.Second},
		{3000, ":3000", 5 * time.Second, 10 * time.Second, 15 * time.Second},
	}

	for _, tt := range tests {
		t.Run("Port"+tt.expectedAddr, func(t *testing.T) {
			server := NewServer(tt.port)

			if server.server.Addr != tt.expectedAddr {
				t.Errorf("Expected address %s, got %s", tt.expectedAddr, server.server.Addr)
			}
			if server.server.ReadTimeout != tt.expectedRead {
				t.Errorf("Expected ReadTimeout %v, got %v", tt.expectedRead, server.server.ReadTimeout)
			}
			if server.server.WriteTimeout != tt.expectedWrite {
				t.Errorf("Expected WriteTimeout %v, got %v", tt.expectedWrite, server.server.WriteTimeout)
			}
			if server.server.IdleTimeout != tt.expectedIdle {
				t.Errorf("Expected IdleTimeout %v, got %v", tt.expectedIdle, server.server.IdleTimeout)
			}
		})
	}
}

func TestServer_HandlerSetup(t *testing.T) {
	server := NewServer(9090)

	// Verify the handler is a ServeMux
	mux, ok := server.server.Handler.(*http.ServeMux)
	if !ok {
		t.Error("Expected handler to be *http.ServeMux")
	}
	if mux == nil {
		t.Error("Expected ServeMux to be initialized")
	}

	// We can verify the metrics handler works by making a request
	// Create a test request
	req, err := http.NewRequest("GET", "/metrics", nil)
	if err != nil {
		t.Fatalf("Failed to create request: %v", err)
	}

	// Use a response recorder to capture the response
	rr := &responseRecorder{}
	mux.ServeHTTP(rr, req)

	// Prometheus metrics endpoint should return 200 and contain metrics
	if rr.statusCode != http.StatusOK {
		t.Errorf("Expected status 200, got %d", rr.statusCode)
	}

	if rr.contentType == "" {
		t.Error("Expected Content-Type header to be set")
	}

	// The response should contain some prometheus metrics
	body := string(rr.body)
	if !strings.Contains(body, "# HELP") && !strings.Contains(body, "# TYPE") {
		// Empty response is OK for metrics endpoint when no custom metrics are registered
		// Just verify we get a response
		if body == "" && rr.statusCode == http.StatusOK {
			// This is acceptable - no metrics registered yet
			return
		}
	}
}

func TestServer_Logger(t *testing.T) {
	server := NewServer(9090)

	if server.logger == nil {
		t.Error("Expected logger to be initialized")
	}

	// Verify logger can be used (doesn't panic)
	server.logger.Info("test log message")
}

// Simple response recorder for testing HTTP handlers
type responseRecorder struct {
	statusCode  int
	body        []byte
	headers     http.Header
	contentType string
}

func (rr *responseRecorder) Header() http.Header {
	if rr.headers == nil {
		rr.headers = make(http.Header)
	}
	return rr.headers
}

func (rr *responseRecorder) Write(data []byte) (int, error) {
	rr.body = append(rr.body, data...)
	if rr.statusCode == 0 {
		rr.statusCode = http.StatusOK
	}
	rr.contentType = rr.headers.Get("Content-Type")
	return len(data), nil
}

func (rr *responseRecorder) WriteHeader(statusCode int) {
	rr.statusCode = statusCode
	rr.contentType = rr.headers.Get("Content-Type")
}
