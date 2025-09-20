package handlers

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/timberline/log-ingestor/internal/models"
)

// mockStorage implements storage.StorageInterface for testing
type mockStorage struct {
	healthCheckError bool
}

func (m *mockStorage) StoreBatch(ctx context.Context, batch *models.LogBatch) error {
	if m.healthCheckError {
		return errors.New("storage error")
	}
	return nil
}

func (m *mockStorage) Connect(ctx context.Context) error {
	if m.healthCheckError {
		return errors.New("connection error")
	}
	return nil
}

func (m *mockStorage) Close() error {
	return nil
}

func (m *mockStorage) CreateCollection(ctx context.Context) error {
	if m.healthCheckError {
		return errors.New("create collection error")
	}
	return nil
}

func (m *mockStorage) HealthCheck(ctx context.Context) error {
	if m.healthCheckError {
		return errors.New("health check failed")
	}
	return nil
}

func TestNewHealthHandler(t *testing.T) {
	storage := &mockStorage{}
	version := "1.0.0"

	handler := NewHealthHandler(storage, version)

	if handler == nil {
		t.Fatal("Expected handler to be created, got nil")
	}
	if handler.storage != storage {
		t.Error("Expected storage to be set correctly")
	}
	if handler.version != version {
		t.Errorf("Expected version %s, got %s", version, handler.version)
	}
	if handler.logger == nil {
		t.Error("Expected logger to be initialized")
	}
	if handler.startTime.IsZero() {
		t.Error("Expected start time to be set")
	}
}

func TestHealthHandler_HandleHealth_Healthy(t *testing.T) {
	storage := &mockStorage{}
	handler := NewHealthHandler(storage, "1.0.0")

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rr := httptest.NewRecorder()

	handler.HandleHealth(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("Expected status %d, got %d", http.StatusOK, rr.Code)
	}

	var response models.HealthResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	if err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}

	if response.Status != "healthy" {
		t.Errorf("Expected status 'healthy', got '%s'", response.Status)
	}
	if response.Version != "1.0.0" {
		t.Errorf("Expected version '1.0.0', got '%s'", response.Version)
	}
	if response.Uptime == "" {
		t.Error("Expected uptime to be set")
	}
	if len(response.Checks) == 0 {
		t.Error("Expected at least one health check")
	}

	// Verify storage check
	found := false
	for _, check := range response.Checks {
		if check.Name == "storage" {
			found = true
			if check.Status != "healthy" {
				t.Errorf("Expected storage check to be healthy, got '%s'", check.Status)
			}
			break
		}
	}
	if !found {
		t.Error("Expected storage health check to be present")
	}

	// Verify timestamp is recent (within last second)
	timeDiff := time.Since(response.Timestamp)
	if timeDiff > time.Second {
		t.Errorf("Timestamp seems too old: %v", timeDiff)
	}
}

func TestHealthHandler_HandleHealth_Unhealthy(t *testing.T) {
	storage := &mockStorage{healthCheckError: true}
	handler := NewHealthHandler(storage, "1.0.0")

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rr := httptest.NewRecorder()

	handler.HandleHealth(rr, req)

	if rr.Code != http.StatusServiceUnavailable {
		t.Errorf("Expected status %d, got %d", http.StatusServiceUnavailable, rr.Code)
	}

	var response models.HealthResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	if err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}

	if response.Status != "unhealthy" {
		t.Errorf("Expected status 'unhealthy', got '%s'", response.Status)
	}

	// Verify storage check is unhealthy
	found := false
	for _, check := range response.Checks {
		if check.Name == "storage" {
			found = true
			if check.Status != "unhealthy" {
				t.Errorf("Expected storage check to be unhealthy, got '%s'", check.Status)
			}
			if check.Message == "" {
				t.Error("Expected error message in unhealthy check")
			}
			break
		}
	}
	if !found {
		t.Error("Expected storage health check to be present")
	}
}

func TestHealthHandler_HandleLiveness(t *testing.T) {
	storage := &mockStorage{}
	handler := NewHealthHandler(storage, "1.0.0")

	req := httptest.NewRequest(http.MethodGet, "/liveness", nil)
	rr := httptest.NewRecorder()

	handler.HandleLiveness(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("Expected status %d, got %d", http.StatusOK, rr.Code)
	}

	body := rr.Body.String()
	if body != "OK" {
		t.Errorf("Expected body 'OK', got '%s'", body)
	}
}

func TestHealthHandler_HandleReadiness_Ready(t *testing.T) {
	storage := &mockStorage{}
	handler := NewHealthHandler(storage, "1.0.0")

	req := httptest.NewRequest(http.MethodGet, "/readiness", nil)
	rr := httptest.NewRecorder()

	handler.HandleReadiness(rr, req)

	if rr.Code != http.StatusOK {
		t.Errorf("Expected status %d, got %d", http.StatusOK, rr.Code)
	}

	body := rr.Body.String()
	if body != "Ready" {
		t.Errorf("Expected body 'Ready', got '%s'", body)
	}
}

func TestHealthHandler_HandleReadiness_NotReady(t *testing.T) {
	storage := &mockStorage{healthCheckError: true}
	handler := NewHealthHandler(storage, "1.0.0")

	req := httptest.NewRequest(http.MethodGet, "/readiness", nil)
	rr := httptest.NewRecorder()

	handler.HandleReadiness(rr, req)

	if rr.Code != http.StatusServiceUnavailable {
		t.Errorf("Expected status %d, got %d", http.StatusServiceUnavailable, rr.Code)
	}

	body := rr.Body.String()
	if body != "Not Ready" {
		t.Errorf("Expected body 'Not Ready', got '%s'", body)
	}
}

func TestHealthHandler_checkStorage_Healthy(t *testing.T) {
	storage := &mockStorage{}
	handler := NewHealthHandler(storage, "1.0.0")

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	check := handler.checkStorage(req.Context())

	if check.Name != "storage" {
		t.Errorf("Expected check name 'storage', got '%s'", check.Name)
	}
	if check.Status != "healthy" {
		t.Errorf("Expected check status 'healthy', got '%s'", check.Status)
	}
	if check.Message != "" {
		t.Errorf("Expected empty message for healthy check, got '%s'", check.Message)
	}
}

func TestHealthHandler_checkStorage_Unhealthy(t *testing.T) {
	storage := &mockStorage{healthCheckError: true}
	handler := NewHealthHandler(storage, "1.0.0")

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	check := handler.checkStorage(req.Context())

	if check.Name != "storage" {
		t.Errorf("Expected check name 'storage', got '%s'", check.Name)
	}
	if check.Status != "unhealthy" {
		t.Errorf("Expected check status 'unhealthy', got '%s'", check.Status)
	}
	if check.Message == "" {
		t.Error("Expected error message for unhealthy check")
	}
}

func TestHealthHandler_ContentType(t *testing.T) {
	storage := &mockStorage{}
	handler := NewHealthHandler(storage, "1.0.0")

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rr := httptest.NewRecorder()

	handler.HandleHealth(rr, req)

	contentType := rr.Header().Get("Content-Type")
	if contentType != "application/json" {
		t.Errorf("Expected Content-Type 'application/json', got '%s'", contentType)
	}
}

func TestHealthHandler_UptimeCalculation(t *testing.T) {
	storage := &mockStorage{}
	handler := NewHealthHandler(storage, "1.0.0")

	// Wait a small amount of time to ensure uptime is measurable
	time.Sleep(10 * time.Millisecond)

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rr := httptest.NewRecorder()

	handler.HandleHealth(rr, req)

	var response models.HealthResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	if err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}

	if response.Uptime == "" {
		t.Error("Expected uptime to be set")
	}

	// Parse uptime to verify it's a valid duration string
	_, err = time.ParseDuration(response.Uptime)
	if err != nil {
		t.Errorf("Expected uptime to be a valid duration, got error: %v", err)
	}
}

func TestHealthHandler_MultipleHealthChecks(t *testing.T) {
	// This test verifies that the health check system can handle multiple checks
	// Currently only storage is implemented, but the structure supports more
	storage := &mockStorage{}
	handler := NewHealthHandler(storage, "1.0.0")

	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rr := httptest.NewRecorder()

	handler.HandleHealth(rr, req)

	var response models.HealthResponse
	err := json.Unmarshal(rr.Body.Bytes(), &response)
	if err != nil {
		t.Fatalf("Failed to unmarshal response: %v", err)
	}

	// Verify the checks array structure
	if len(response.Checks) == 0 {
		t.Error("Expected at least one health check")
	}

	for _, check := range response.Checks {
		if check.Name == "" {
			t.Error("Health check name should not be empty")
		}
		if check.Status != "healthy" && check.Status != "unhealthy" {
			t.Errorf("Invalid health check status: %s", check.Status)
		}
	}
}
