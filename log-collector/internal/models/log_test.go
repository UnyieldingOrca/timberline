package models

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewLogEntry(t *testing.T) {
	message := "Test message"
	source := "test-app"
	
	entry := NewLogEntry(message, source)
	
	assert.Equal(t, message, entry.Message)
	assert.Equal(t, source, entry.Source)
	assert.NotZero(t, entry.Timestamp)
	assert.NotNil(t, entry.Metadata)
}

func TestLogEntry_SetLevel(t *testing.T) {
	entry := NewLogEntry("test", "test-app")
	
	entry.SetLevel("ERROR")
	
	assert.Equal(t, "ERROR", entry.GetLevel())
}

func TestLogEntry_GetLevel(t *testing.T) {
	tests := []struct {
		name     string
		metadata map[string]interface{}
		expected string
	}{
		{
			name:     "no metadata",
			metadata: nil,
			expected: "INFO",
		},
		{
			name:     "empty metadata",
			metadata: make(map[string]interface{}),
			expected: "INFO",
		},
		{
			name:     "level set",
			metadata: map[string]interface{}{"level": "ERROR"},
			expected: "ERROR",
		},
		{
			name:     "level not string",
			metadata: map[string]interface{}{"level": 123},
			expected: "INFO",
		},
	}
	
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			entry := &LogEntry{
				Timestamp: time.Now().UnixMilli(),
				Message:   "test",
				Source:    "test-app",
				Metadata:  tt.metadata,
			}
			
			assert.Equal(t, tt.expected, entry.GetLevel())
		})
	}
}

func TestLogEntry_SetKubernetesMetadata(t *testing.T) {
	entry := NewLogEntry("test", "test-app")
	
	podName := "test-pod"
	namespace := "default"
	nodeName := "worker-1"
	labels := map[string]string{"app": "test"}
	
	entry.SetKubernetesMetadata(podName, namespace, nodeName, labels)
	
	assert.Equal(t, podName, entry.Metadata["pod_name"])
	assert.Equal(t, namespace, entry.Metadata["namespace"])
	assert.Equal(t, nodeName, entry.Metadata["node_name"])
	assert.Equal(t, labels, entry.Metadata["labels"])
}

func TestLogEntry_SetMetadata(t *testing.T) {
	entry := NewLogEntry("test", "test-app")
	
	entry.SetMetadata("custom_key", "custom_value")
	
	assert.Equal(t, "custom_value", entry.Metadata["custom_key"])
}

func TestLogEntry_GetMetadata(t *testing.T) {
	entry := NewLogEntry("test", "test-app")
	entry.SetMetadata("existing_key", "existing_value")
	
	// Test existing key
	value := entry.GetMetadata("existing_key", "fallback")
	assert.Equal(t, "existing_value", value)
	
	// Test non-existing key
	value = entry.GetMetadata("missing_key", "fallback")
	assert.Equal(t, "fallback", value)
	
	// Test nil metadata
	entry.Metadata = nil
	value = entry.GetMetadata("any_key", "fallback")
	assert.Equal(t, "fallback", value)
}

func TestLogEntry_JSONMarshaling(t *testing.T) {
	timestamp := time.Now().UnixMilli()
	entry := &LogEntry{
		Timestamp: timestamp,
		Message:   "Test log message",
		Source:    "test-app",
		Metadata: map[string]interface{}{
			"level":     "INFO",
			"pod_name":  "test-pod",
			"namespace": "default",
		},
	}
	
	// Test marshaling
	data, err := json.Marshal(entry)
	require.NoError(t, err)
	
	// Test unmarshaling
	var unmarshaled LogEntry
	err = json.Unmarshal(data, &unmarshaled)
	require.NoError(t, err)
	
	// Verify fields
	assert.Equal(t, entry.Timestamp, unmarshaled.Timestamp)
	assert.Equal(t, entry.Message, unmarshaled.Message)
	assert.Equal(t, entry.Source, unmarshaled.Source)
	assert.Equal(t, entry.Metadata, unmarshaled.Metadata)
}

func TestLogEntry_OmitEmptyMetadata(t *testing.T) {
	entry := &LogEntry{
		Timestamp: time.Now().UnixMilli(),
		Message:   "Test message",
		Source:    "test",
		// Metadata is nil, should be omitted
	}
	
	data, err := json.Marshal(entry)
	require.NoError(t, err)
	
	// Verify that empty metadata field is omitted
	jsonStr := string(data)
	assert.NotContains(t, jsonStr, "metadata")
	
	// Verify required fields are present
	assert.Contains(t, jsonStr, "timestamp")
	assert.Contains(t, jsonStr, "message")
	assert.Contains(t, jsonStr, "source")
}

func TestLogBatch(t *testing.T) {
	entry1 := NewLogEntry("message 1", "app1")
	entry2 := NewLogEntry("message 2", "app2")
	
	batch := &LogBatch{
		Logs: []*LogEntry{entry1, entry2},
	}
	
	// Test marshaling
	data, err := json.Marshal(batch)
	require.NoError(t, err)
	
	// Test unmarshaling
	var unmarshaled LogBatch
	err = json.Unmarshal(data, &unmarshaled)
	require.NoError(t, err)
	
	assert.Len(t, unmarshaled.Logs, 2)
	assert.Equal(t, entry1.Message, unmarshaled.Logs[0].Message)
	assert.Equal(t, entry2.Message, unmarshaled.Logs[1].Message)
}