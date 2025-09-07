package models

import (
	"encoding/json"
	"testing"
	"time"
)

func TestLogEntryValidate(t *testing.T) {
	now := time.Now().UnixMilli()
	
	tests := []struct {
		name        string
		logEntry    LogEntry
		expectError bool
		errorMsg    string
	}{
		{
			name: "Valid log entry",
			logEntry: LogEntry{
				Timestamp: now,
				Message:   "Test message",
				Source:    "test-service",
			},
			expectError: false,
		},
		{
			name: "Valid log entry with metadata",
			logEntry: LogEntry{
				Timestamp: now,
				Message:   "Test message",
				Source:    "test-service",
				Metadata: map[string]interface{}{
					"level": "ERROR",
					"pod_name": "test-pod",
					"namespace": "default",
				},
			},
			expectError: false,
		},
		{
			name: "Missing timestamp",
			logEntry: LogEntry{
				Message: "Test message",
				Source:  "test-service",
			},
			expectError: true,
			errorMsg:    "timestamp is required",
		},
		{
			name: "Missing message",
			logEntry: LogEntry{
				Timestamp: now,
				Source:    "test-service",
			},
			expectError: true,
			errorMsg:    "message is required",
		},
		{
			name: "Missing source",
			logEntry: LogEntry{
				Timestamp: now,
				Message:   "Test message",
			},
			expectError: true,
			errorMsg:    "source is required",
		},
		{
			name: "Timestamp too far in future",
			logEntry: LogEntry{
				Timestamp: now + (2 * 60 * 60 * 1000), // 2 hours in future
				Message:   "Test message",
				Source:    "test-service",
			},
			expectError: true,
			errorMsg:    "timestamp cannot be more than 1 hour in the future",
		},
		{
			name: "Timestamp too old",
			logEntry: LogEntry{
				Timestamp: now - (11 * 365 * 24 * 60 * 60 * 1000), // 11 years ago
				Message:   "Test message",
				Source:    "test-service",
			},
			expectError: true,
			errorMsg:    "timestamp cannot be older than 10 years",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.logEntry.Validate()
			if tt.expectError {
				if err == nil {
					t.Errorf("Expected error for %s, got nil", tt.name)
				} else if err.Error() != tt.errorMsg {
					t.Errorf("Expected error message '%s', got '%s'", tt.errorMsg, err.Error())
				}
			} else {
				if err != nil {
					t.Errorf("Expected no error for %s, got %v", tt.name, err)
				}
			}
		})
	}
}

func TestLogEntryGetLevel(t *testing.T) {
	tests := []struct {
		name     string
		logEntry LogEntry
		expected string
	}{
		{
			name: "Level in metadata",
			logEntry: LogEntry{
				Timestamp: time.Now().UnixMilli(),
				Message:   "Test message",
				Source:    "test-service",
				Metadata: map[string]interface{}{
					"level": "ERROR",
				},
			},
			expected: "ERROR",
		},
		{
			name: "Log_level in metadata",
			logEntry: LogEntry{
				Timestamp: time.Now().UnixMilli(),
				Message:   "Test message",
				Source:    "test-service",
				Metadata: map[string]interface{}{
					"log_level": "WARN",
				},
			},
			expected: "WARN",
		},
		{
			name: "No level in metadata",
			logEntry: LogEntry{
				Timestamp: time.Now().UnixMilli(),
				Message:   "Test message",
				Source:    "test-service",
				Metadata: map[string]interface{}{
					"pod_name": "test-pod",
				},
			},
			expected: "INFO",
		},
		{
			name: "No metadata",
			logEntry: LogEntry{
				Timestamp: time.Now().UnixMilli(),
				Message:   "Test message",
				Source:    "test-service",
			},
			expected: "INFO",
		},
		{
			name: "Non-string level in metadata",
			logEntry: LogEntry{
				Timestamp: time.Now().UnixMilli(),
				Message:   "Test message",
				Source:    "test-service",
				Metadata: map[string]interface{}{
					"level": 123,
				},
			},
			expected: "INFO",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result := tt.logEntry.GetLevel()
			if result != tt.expected {
				t.Errorf("Expected level '%s', got '%s'", tt.expected, result)
			}
		})
	}
}

func TestLogEntrySetLevel(t *testing.T) {
	logEntry := LogEntry{
		Timestamp: time.Now().UnixMilli(),
		Message:   "Test message",
		Source:    "test-service",
	}

	// Test setting level on entry without metadata
	logEntry.SetLevel("ERROR")
	if logEntry.GetLevel() != "ERROR" {
		t.Errorf("Expected level 'ERROR', got '%s'", logEntry.GetLevel())
	}

	// Test setting level on entry with existing metadata
	logEntry.Metadata["pod_name"] = "test-pod"
	logEntry.SetLevel("WARN")
	if logEntry.GetLevel() != "WARN" {
		t.Errorf("Expected level 'WARN', got '%s'", logEntry.GetLevel())
	}

	// Verify other metadata is preserved
	if podName := logEntry.GetStringFromMetadata("pod_name", ""); podName != "test-pod" {
		t.Errorf("Expected pod_name 'test-pod', got '%s'", podName)
	}
}

func TestLogEntryGetStringFromMetadata(t *testing.T) {
	logEntry := LogEntry{
		Timestamp: time.Now().UnixMilli(),
		Message:   "Test message",
		Source:    "test-service",
		Metadata: map[string]interface{}{
			"pod_name":  "test-pod",
			"namespace": "default",
			"port":      8080,
		},
	}

	// Test existing string value
	if result := logEntry.GetStringFromMetadata("pod_name", "fallback"); result != "test-pod" {
		t.Errorf("Expected 'test-pod', got '%s'", result)
	}

	// Test fallback for missing key
	if result := logEntry.GetStringFromMetadata("missing", "fallback"); result != "fallback" {
		t.Errorf("Expected 'fallback', got '%s'", result)
	}

	// Test fallback for non-string value
	if result := logEntry.GetStringFromMetadata("port", "fallback"); result != "fallback" {
		t.Errorf("Expected 'fallback', got '%s'", result)
	}

	// Test with no metadata
	emptyEntry := LogEntry{
		Timestamp: time.Now().UnixMilli(),
		Message:   "Test message",
		Source:    "test-service",
	}
	if result := emptyEntry.GetStringFromMetadata("any", "fallback"); result != "fallback" {
		t.Errorf("Expected 'fallback', got '%s'", result)
	}
}

func TestLogEntryJSON(t *testing.T) {
	now := time.Now().UnixMilli()
	logEntry := LogEntry{
		Timestamp: now,
		Message:   "Test message with JSON",
		Source:    "test-service",
		Metadata: map[string]interface{}{
			"level":     "INFO",
			"pod_name":  "test-pod",
			"namespace": "default",
			"labels": map[string]interface{}{
				"app": "test",
				"env": "dev",
			},
		},
	}

	// Test JSON marshaling
	data, err := json.Marshal(logEntry)
	if err != nil {
		t.Fatalf("Failed to marshal LogEntry: %v", err)
	}

	// Test JSON unmarshaling
	var unmarshaled LogEntry
	err = json.Unmarshal(data, &unmarshaled)
	if err != nil {
		t.Fatalf("Failed to unmarshal LogEntry: %v", err)
	}

	if unmarshaled.Timestamp != logEntry.Timestamp {
		t.Errorf("Expected Timestamp %d, got %d", logEntry.Timestamp, unmarshaled.Timestamp)
	}
	if unmarshaled.Message != logEntry.Message {
		t.Errorf("Expected Message '%s', got '%s'", logEntry.Message, unmarshaled.Message)
	}
	if unmarshaled.Source != logEntry.Source {
		t.Errorf("Expected Source '%s', got '%s'", logEntry.Source, unmarshaled.Source)
	}

	// Check metadata
	if unmarshaled.GetLevel() != "INFO" {
		t.Errorf("Expected level 'INFO', got '%s'", unmarshaled.GetLevel())
	}
	if unmarshaled.GetStringFromMetadata("pod_name", "") != "test-pod" {
		t.Errorf("Expected pod_name 'test-pod', got '%s'", unmarshaled.GetStringFromMetadata("pod_name", ""))
	}
}

func TestLogBatchValidate(t *testing.T) {
	now := time.Now().UnixMilli()
	validLogEntry := LogEntry{
		Timestamp: now,
		Message:   "Test message",
		Source:    "test-service",
	}

	invalidLogEntry := LogEntry{
		Message: "Test message without timestamp",
		Source:  "test-service",
	}

	tests := []struct {
		name        string
		batch       LogBatch
		expectError bool
		errorSubstr string
	}{
		{
			name: "Valid batch with single log",
			batch: LogBatch{
				Logs: []LogEntry{validLogEntry},
			},
			expectError: false,
		},
		{
			name: "Valid batch with multiple logs",
			batch: LogBatch{
				Logs: []LogEntry{validLogEntry, validLogEntry},
			},
			expectError: false,
		},
		{
			name:        "Empty batch",
			batch:       LogBatch{Logs: []LogEntry{}},
			expectError: true,
			errorSubstr: "batch cannot be empty",
		},
		{
			name: "Batch with invalid log entry",
			batch: LogBatch{
				Logs: []LogEntry{invalidLogEntry},
			},
			expectError: true,
			errorSubstr: "validation error for logs[",
		},
		{
			name: "Batch with mix of valid and invalid entries",
			batch: LogBatch{
				Logs: []LogEntry{validLogEntry, invalidLogEntry},
			},
			expectError: true,
			errorSubstr: "validation error for logs[",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.batch.Validate()
			if tt.expectError {
				if err == nil {
					t.Errorf("Expected error for %s, got nil", tt.name)
				} else if tt.errorSubstr != "" && !containsSubstring(err.Error(), tt.errorSubstr) {
					t.Errorf("Expected error to contain '%s', got '%s'", tt.errorSubstr, err.Error())
				}
			} else {
				if err != nil {
					t.Errorf("Expected no error for %s, got %v", tt.name, err)
				}
			}
		})
	}
}

func TestLogBatchSize(t *testing.T) {
	now := time.Now().UnixMilli()
	batch := LogBatch{
		Logs: []LogEntry{
			{Timestamp: now, Message: "msg1", Source: "src1"},
			{Timestamp: now + 1, Message: "msg2", Source: "src2"},
			{Timestamp: now + 2, Message: "msg3", Source: "src3"},
		},
	}

	expectedSize := 3
	if batch.Size() != expectedSize {
		t.Errorf("Expected batch size %d, got %d", expectedSize, batch.Size())
	}

	// Test empty batch
	emptyBatch := LogBatch{Logs: []LogEntry{}}
	if emptyBatch.Size() != 0 {
		t.Errorf("Expected empty batch size 0, got %d", emptyBatch.Size())
	}
}

func TestLogBatchToJSON(t *testing.T) {
	now := time.Now().UnixMilli()
	batch := LogBatch{
		Logs: []LogEntry{
			{
				Timestamp: now,
				Message:   "Test message",
				Source:    "test-service",
				Metadata: map[string]interface{}{
					"level": "INFO",
				},
			},
		},
	}

	data, err := batch.ToJSON()
	if err != nil {
		t.Fatalf("Failed to convert batch to JSON: %v", err)
	}

	// Verify we can unmarshal it back
	var unmarshaled LogBatch
	err = json.Unmarshal(data, &unmarshaled)
	if err != nil {
		t.Fatalf("Failed to unmarshal JSON: %v", err)
	}

	if len(unmarshaled.Logs) != len(batch.Logs) {
		t.Errorf("Expected %d logs, got %d", len(batch.Logs), len(unmarshaled.Logs))
	}

	if unmarshaled.Logs[0].Message != batch.Logs[0].Message {
		t.Errorf("Expected message '%s', got '%s'", batch.Logs[0].Message, unmarshaled.Logs[0].Message)
	}
}

func TestBatchResponse(t *testing.T) {
	response := BatchResponse{
		Success:        true,
		ProcessedCount: 5,
		Errors:         []string{"error1", "error2"},
	}

	data, err := json.Marshal(response)
	if err != nil {
		t.Fatalf("Failed to marshal BatchResponse: %v", err)
	}

	var unmarshaled BatchResponse
	err = json.Unmarshal(data, &unmarshaled)
	if err != nil {
		t.Fatalf("Failed to unmarshal BatchResponse: %v", err)
	}

	if unmarshaled.Success != response.Success {
		t.Errorf("Expected Success %v, got %v", response.Success, unmarshaled.Success)
	}
	if unmarshaled.ProcessedCount != response.ProcessedCount {
		t.Errorf("Expected ProcessedCount %d, got %d", response.ProcessedCount, unmarshaled.ProcessedCount)
	}
	if len(unmarshaled.Errors) != len(response.Errors) {
		t.Errorf("Expected %d errors, got %d", len(response.Errors), len(unmarshaled.Errors))
	}
}

func TestHealthResponse(t *testing.T) {
	now := time.Now()
	checks := []HealthCheck{
		{Name: "storage", Status: "healthy"},
		{Name: "database", Status: "unhealthy", Message: "connection failed"},
	}

	response := HealthResponse{
		Status:    "healthy",
		Timestamp: now,
		Version:   "1.0.0",
		Uptime:    "5m30s",
		Checks:    checks,
	}

	data, err := json.Marshal(response)
	if err != nil {
		t.Fatalf("Failed to marshal HealthResponse: %v", err)
	}

	var unmarshaled HealthResponse
	err = json.Unmarshal(data, &unmarshaled)
	if err != nil {
		t.Fatalf("Failed to unmarshal HealthResponse: %v", err)
	}

	if unmarshaled.Status != response.Status {
		t.Errorf("Expected Status %s, got %s", response.Status, unmarshaled.Status)
	}
	if unmarshaled.Version != response.Version {
		t.Errorf("Expected Version %s, got %s", response.Version, unmarshaled.Version)
	}
	if unmarshaled.Uptime != response.Uptime {
		t.Errorf("Expected Uptime %s, got %s", response.Uptime, unmarshaled.Uptime)
	}
	if len(unmarshaled.Checks) != len(response.Checks) {
		t.Errorf("Expected %d checks, got %d", len(response.Checks), len(unmarshaled.Checks))
	}
	
	// Verify timestamp is properly serialized/deserialized
	timeDiff := unmarshaled.Timestamp.Sub(response.Timestamp)
	if timeDiff > time.Millisecond || timeDiff < -time.Millisecond {
		t.Errorf("Timestamp serialization issue: expected %v, got %v (diff: %v)", 
			response.Timestamp, unmarshaled.Timestamp, timeDiff)
	}
}

func TestHealthCheck(t *testing.T) {
	// Test healthy check
	healthyCheck := HealthCheck{
		Name:   "database",
		Status: "healthy",
	}

	data, err := json.Marshal(healthyCheck)
	if err != nil {
		t.Fatalf("Failed to marshal HealthCheck: %v", err)
	}

	var unmarshaled HealthCheck
	err = json.Unmarshal(data, &unmarshaled)
	if err != nil {
		t.Fatalf("Failed to unmarshal HealthCheck: %v", err)
	}

	if unmarshaled.Name != healthyCheck.Name {
		t.Errorf("Expected Name %s, got %s", healthyCheck.Name, unmarshaled.Name)
	}
	if unmarshaled.Status != healthyCheck.Status {
		t.Errorf("Expected Status %s, got %s", healthyCheck.Status, unmarshaled.Status)
	}
	if unmarshaled.Message != "" {
		t.Errorf("Expected empty Message, got %s", unmarshaled.Message)
	}

	// Test unhealthy check with message
	unhealthyCheck := HealthCheck{
		Name:    "storage",
		Status:  "unhealthy",
		Message: "connection timeout",
	}

	data, err = json.Marshal(unhealthyCheck)
	if err != nil {
		t.Fatalf("Failed to marshal HealthCheck: %v", err)
	}

	err = json.Unmarshal(data, &unmarshaled)
	if err != nil {
		t.Fatalf("Failed to unmarshal HealthCheck: %v", err)
	}

	if unmarshaled.Message != unhealthyCheck.Message {
		t.Errorf("Expected Message %s, got %s", unhealthyCheck.Message, unmarshaled.Message)
	}
}

func TestValidationError(t *testing.T) {
	err := &ValidationError{
		Field:   "test_field",
		Message: "test error message",
	}

	expected := "validation error for test_field: test error message"
	if err.Error() != expected {
		t.Errorf("Expected error message '%s', got '%s'", expected, err.Error())
	}
}


// Helper function to check if string contains substring
func containsSubstring(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || 
		(len(substr) > 0 && len(s) > 0 && 
			(s[:len(substr)] == substr || 
			 s[len(s)-len(substr):] == substr ||
			 func() bool {
				for i := 1; i < len(s)-len(substr)+1; i++ {
					if s[i:i+len(substr)] == substr {
						return true
					}
				}
				return false
			}())))
}