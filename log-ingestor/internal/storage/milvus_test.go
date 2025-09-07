package storage

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/timberline/log-ingestor/internal/models"
)

func TestNewMilvusClient(t *testing.T) {
	address := "localhost:19530"
	client := NewMilvusClient(address)

	if client == nil {
		t.Fatal("Expected client to be created, got nil")
	}
	if client.address != address {
		t.Errorf("Expected address %s, got %s", address, client.address)
	}
	if client.collection != "logs" {
		t.Errorf("Expected collection 'logs', got %s", client.collection)
	}
	if client.logger == nil {
		t.Error("Expected logger to be initialized")
	}
}

func TestMilvusClient_Connect(t *testing.T) {
	client := NewMilvusClient("test:19530")
	ctx := context.Background()

	// Test successful connection
	start := time.Now()
	err := client.Connect(ctx)
	duration := time.Since(start)

	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
	
	// Verify it takes approximately the expected time (100ms simulation)
	if duration < 90*time.Millisecond || duration > 200*time.Millisecond {
		t.Errorf("Connection took unexpected duration: %v", duration)
	}
}

func TestMilvusClient_Connect_WithTimeout(t *testing.T) {
	client := NewMilvusClient("test:19530")
	
	// Create a context with a very short timeout
	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()

	err := client.Connect(ctx)
	
	if err != context.DeadlineExceeded {
		t.Errorf("Expected context.DeadlineExceeded, got %v", err)
	}
}

func TestMilvusClient_Connect_WithCancellation(t *testing.T) {
	client := NewMilvusClient("test:19530")
	
	ctx, cancel := context.WithCancel(context.Background())
	
	// Cancel the context immediately
	cancel()

	err := client.Connect(ctx)
	
	if err != context.Canceled {
		t.Errorf("Expected context.Canceled, got %v", err)
	}
}

func TestMilvusClient_Close(t *testing.T) {
	client := NewMilvusClient("test:19530")
	
	err := client.Close()
	if err != nil {
		t.Errorf("Expected no error from Close(), got %v", err)
	}
}

func TestMilvusClient_StoreBatch_Success(t *testing.T) {
	client := NewMilvusClient("test:19530")
	ctx := context.Background()

	batch := &models.LogBatch{
		Logs: []models.LogEntry{
			{
				Timestamp: 1704110400000,
				Message:   "Test log message",
				
				Source:    "test-source",
			},
		},
	}

	start := time.Now()
	err := client.StoreBatch(ctx, batch)
	duration := time.Since(start)

	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
	
	// Verify it takes approximately the expected time (50ms simulation)
	if duration < 40*time.Millisecond || duration > 100*time.Millisecond {
		t.Errorf("StoreBatch took unexpected duration: %v", duration)
	}
}

func TestMilvusClient_StoreBatch_NilBatch(t *testing.T) {
	client := NewMilvusClient("test:19530")
	ctx := context.Background()

	err := client.StoreBatch(ctx, nil)
	
	if err == nil {
		t.Error("Expected error for nil batch, got nil")
	}
	if err.Error() != "batch cannot be nil" {
		t.Errorf("Expected 'batch cannot be nil' error, got '%s'", err.Error())
	}
}

func TestMilvusClient_StoreBatch_InvalidBatch(t *testing.T) {
	client := NewMilvusClient("test:19530")
	ctx := context.Background()

	// Create batch with invalid log entry (missing timestamp)
	batch := &models.LogBatch{
		Logs: []models.LogEntry{
			{
				Message: "Test message",
				Source:  "test-source",
				Metadata: map[string]interface{}{
					"level": "INFO",
				},
				// Missing timestamp
			},
		},
	}

	err := client.StoreBatch(ctx, batch)
	
	if err == nil {
		t.Error("Expected validation error, got nil")
	}
	if !strings.Contains(err.Error(), "batch validation failed") {
		t.Errorf("Expected validation error, got '%s'", err.Error())
	}
}

func TestMilvusClient_StoreBatch_WithTimeout(t *testing.T) {
	client := NewMilvusClient("test:19530")
	
	// Create a context with a very short timeout
	ctx, cancel := context.WithTimeout(context.Background(), 25*time.Millisecond)
	defer cancel()

	batch := &models.LogBatch{
		Logs: []models.LogEntry{
			{
				Timestamp: 1704110400000,
				Message:   "Test message",
				
				Source:    "test-source",
			},
		},
	}

	err := client.StoreBatch(ctx, batch)
	
	if err != context.DeadlineExceeded {
		t.Errorf("Expected context.DeadlineExceeded, got %v", err)
	}
}

func TestMilvusClient_StoreBatch_WithCancellation(t *testing.T) {
	client := NewMilvusClient("test:19530")
	
	ctx, cancel := context.WithCancel(context.Background())
	
	batch := &models.LogBatch{
		Logs: []models.LogEntry{
			{
				Timestamp: 1704110400000,
				Message:   "Test message",
				
				Source:    "test-source",
			},
		},
	}

	// Cancel the context immediately
	cancel()

	err := client.StoreBatch(ctx, batch)
	
	if err != context.Canceled {
		t.Errorf("Expected context.Canceled, got %v", err)
	}
}

func TestMilvusClient_StoreBatch_LargeBatch(t *testing.T) {
	client := NewMilvusClient("test:19530")
	ctx := context.Background()

	// Create a large batch
	logs := make([]models.LogEntry, 100)
	for i := 0; i < 100; i++ {
		logs[i] = models.LogEntry{
			Timestamp: 1704110400000,
			Message:   "Test log message",
			
			Source:    "test-source",
		}
	}

	batch := &models.LogBatch{Logs: logs}

	err := client.StoreBatch(ctx, batch)
	if err != nil {
		t.Errorf("Expected no error for large batch, got %v", err)
	}
}

func TestMilvusClient_StoreBatch_WithMetadata(t *testing.T) {
	client := NewMilvusClient("test:19530")
	ctx := context.Background()

	batch := &models.LogBatch{
		Logs: []models.LogEntry{
			{
				Timestamp: 1704110400000,
				Message:   "Test log message",
				
				Source:    "test-source",
				Metadata: map[string]interface{}{
					"pod_name":  "test-pod",
					"namespace": "default",
					"node_name": "node-1",
					"labels": map[string]interface{}{
						"app": "test",
					},
				},
			},
		},
	}

	err := client.StoreBatch(ctx, batch)
	if err != nil {
		t.Errorf("Expected no error for batch with metadata, got %v", err)
	}
}

func TestMilvusClient_HealthCheck_Success(t *testing.T) {
	client := NewMilvusClient("test:19530")
	ctx := context.Background()

	start := time.Now()
	err := client.HealthCheck(ctx)
	duration := time.Since(start)

	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
	
	// Verify it takes approximately the expected time (10ms simulation)
	if duration < 5*time.Millisecond || duration > 50*time.Millisecond {
		t.Errorf("HealthCheck took unexpected duration: %v", duration)
	}
}

func TestMilvusClient_HealthCheck_WithTimeout(t *testing.T) {
	client := NewMilvusClient("test:19530")
	
	// Create a context with a very short timeout
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Millisecond)
	defer cancel()

	err := client.HealthCheck(ctx)
	
	if err != context.DeadlineExceeded {
		t.Errorf("Expected context.DeadlineExceeded, got %v", err)
	}
}

func TestMilvusClient_HealthCheck_WithCancellation(t *testing.T) {
	client := NewMilvusClient("test:19530")
	
	ctx, cancel := context.WithCancel(context.Background())
	
	// Cancel the context immediately
	cancel()

	err := client.HealthCheck(ctx)
	
	if err != context.Canceled {
		t.Errorf("Expected context.Canceled, got %v", err)
	}
}

func TestMilvusClient_CreateCollection(t *testing.T) {
	client := NewMilvusClient("test:19530")
	ctx := context.Background()

	// Since CreateCollection is not yet implemented, it should return nil
	err := client.CreateCollection(ctx)
	if err != nil {
		t.Errorf("Expected no error from CreateCollection, got %v", err)
	}
}

func TestStorageInterface_Implementation(t *testing.T) {
	// Verify that MilvusClient implements StorageInterface
	var _ StorageInterface = (*MilvusClient)(nil)
	
	// This test will fail to compile if MilvusClient doesn't implement
	// all methods required by StorageInterface
	client := NewMilvusClient("test:19530")
	if client == nil {
		t.Error("Expected client to implement StorageInterface")
	}
}

func TestMilvusClient_ConcurrentOperations(t *testing.T) {
	client := NewMilvusClient("test:19530")
	ctx := context.Background()

	batch := &models.LogBatch{
		Logs: []models.LogEntry{
			{
				Timestamp: 1704110400000,
				Message:   "Test message",
				
				Source:    "test-source",
			},
		},
	}

	// Test concurrent StoreBatch operations
	concurrency := 10
	errChan := make(chan error, concurrency)

	for i := 0; i < concurrency; i++ {
		go func() {
			err := client.StoreBatch(ctx, batch)
			errChan <- err
		}()
	}

	// Collect results
	for i := 0; i < concurrency; i++ {
		err := <-errChan
		if err != nil {
			t.Errorf("Concurrent operation %d failed: %v", i, err)
		}
	}
}

func TestMilvusClient_DifferentLogLevels(t *testing.T) {
	client := NewMilvusClient("test:19530")
	ctx := context.Background()

	logLevels := []string{"ERROR", "WARN", "INFO", "DEBUG", "TRACE", "error", "warn", "info", "debug", "trace"}

	for _, level := range logLevels {
		batch := &models.LogBatch{
			Logs: []models.LogEntry{
				{
					Timestamp: 1704110400000,
					Message:   "Test message for " + level,
					
					Source:    "test-source",
				},
			},
		}

		err := client.StoreBatch(ctx, batch)
		if err != nil {
			t.Errorf("Expected no error for level %s, got %v", level, err)
		}
	}
}