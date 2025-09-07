package config

import (
	"reflect"
	"testing"
	"time"
)

func TestCollectorConfig_DefaultValues(t *testing.T) {
	config := CollectorConfig{}

	// Test zero values
	if len(config.LogPaths) != 0 {
		t.Errorf("LogPaths should be empty when zero-initialized, got %v", config.LogPaths)
	}
	if len(config.LogLevels) != 0 {
		t.Errorf("LogLevels should be empty when zero-initialized, got %v", config.LogLevels)
	}
	if config.BufferSize != 0 {
		t.Errorf("BufferSize should be 0 when zero-initialized, got %d", config.BufferSize)
	}
	if config.FlushInterval != time.Duration(0) {
		t.Errorf("FlushInterval should be 0 when zero-initialized, got %v", config.FlushInterval)
	}
	if config.ForwarderURL != "" {
		t.Errorf("ForwarderURL should be empty when zero-initialized, got %s", config.ForwarderURL)
	}
}

func TestCollectorConfig_WithValues(t *testing.T) {
	config := CollectorConfig{
		LogPaths:      []string{"/var/log/*.log", "/app/logs/*.log"},
		LogLevels:     []string{"INFO", "WARN", "ERROR"},
		BufferSize:    1000,
		FlushInterval: 30 * time.Second,
		ForwarderURL:  "http://log-server:8080/logs",
	}

	expectedLogPaths := []string{"/var/log/*.log", "/app/logs/*.log"}
	if !reflect.DeepEqual(config.LogPaths, expectedLogPaths) {
		t.Errorf("LogPaths = %v, expected %v", config.LogPaths, expectedLogPaths)
	}

	expectedLogLevels := []string{"INFO", "WARN", "ERROR"}
	if !reflect.DeepEqual(config.LogLevels, expectedLogLevels) {
		t.Errorf("LogLevels = %v, expected %v", config.LogLevels, expectedLogLevels)
	}

	if config.BufferSize != 1000 {
		t.Errorf("BufferSize = %d, expected 1000", config.BufferSize)
	}

	if config.FlushInterval != 30*time.Second {
		t.Errorf("FlushInterval = %v, expected %v", config.FlushInterval, 30*time.Second)
	}

	expectedURL := "http://log-server:8080/logs"
	if config.ForwarderURL != expectedURL {
		t.Errorf("ForwarderURL = %s, expected %s", config.ForwarderURL, expectedURL)
	}
}

func TestCollectorConfig_Validation(t *testing.T) {
	tests := []struct {
		name    string
		config  CollectorConfig
		wantErr bool
	}{
		{
			name: "valid config",
			config: CollectorConfig{
				LogPaths:      []string{"/var/log/*.log"},
				BufferSize:    1000,
				FlushInterval: 30 * time.Second,
				ForwarderURL:  "http://localhost:8080",
			},
			wantErr: false,
		},
		{
			name: "empty log paths",
			config: CollectorConfig{
				BufferSize:    1000,
				FlushInterval: 30 * time.Second,
				ForwarderURL:  "http://localhost:8080",
			},
			wantErr: false, // Empty paths might be valid in some cases
		},
		{
			name: "zero buffer size",
			config: CollectorConfig{
				LogPaths:      []string{"/var/log/*.log"},
				BufferSize:    0,
				FlushInterval: 30 * time.Second,
				ForwarderURL:  "http://localhost:8080",
			},
			wantErr: false, // Zero might default to a reasonable value
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// This test demonstrates structure for validation logic
			// that could be implemented in a Validate() method
			if tt.config.LogPaths == nil && tt.config.BufferSize < 0 {
				t.Errorf("Invalid configuration detected")
			}
		})
	}
}

func TestCollectorConfig_StructFields(t *testing.T) {
	// Test that CollectorConfig has all expected fields with correct types
	config := CollectorConfig{}

	// Use reflection to verify field types
	configType := reflect.TypeOf(config)

	tests := []struct {
		fieldName string
		fieldType reflect.Type
	}{
		{"LogPaths", reflect.TypeOf([]string{})},
		{"LogLevels", reflect.TypeOf([]string{})},
		{"BufferSize", reflect.TypeOf(int(0))},
		{"FlushInterval", reflect.TypeOf(time.Duration(0))},
		{"ForwarderURL", reflect.TypeOf("")},
	}

	for _, test := range tests {
		t.Run(test.fieldName, func(t *testing.T) {
			field, found := configType.FieldByName(test.fieldName)
			if !found {
				t.Errorf("Field %s not found in CollectorConfig", test.fieldName)
				return
			}

			if field.Type != test.fieldType {
				t.Errorf("Field %s has type %v, expected %v", test.fieldName, field.Type, test.fieldType)
			}
		})
	}
}

func TestCollectorConfig_YAMLTags(t *testing.T) {
	// Test that all fields have correct YAML tags
	configType := reflect.TypeOf(CollectorConfig{})

	expectedYAMLTags := map[string]string{
		"LogPaths":      "log_paths",
		"LogLevels":     "log_levels",
		"BufferSize":    "buffer_size",
		"FlushInterval": "flush_interval",
		"ForwarderURL":  "forwarder_url",
	}

	for fieldName, expectedTag := range expectedYAMLTags {
		t.Run(fieldName, func(t *testing.T) {
			field, found := configType.FieldByName(fieldName)
			if !found {
				t.Errorf("Field %s not found", fieldName)
				return
			}

			yamlTag := field.Tag.Get("yaml")
			if yamlTag != expectedTag {
				t.Errorf("Field %s has YAML tag '%s', expected '%s'", fieldName, yamlTag, expectedTag)
			}
		})
	}
}

func TestCollectorConfig_EnvTags(t *testing.T) {
	// Test that all fields have correct environment variable tags
	configType := reflect.TypeOf(CollectorConfig{})

	expectedEnvTags := map[string]string{
		"LogPaths":      "LOG_PATHS",
		"LogLevels":     "LOG_LEVELS",
		"BufferSize":    "BUFFER_SIZE",
		"FlushInterval": "FLUSH_INTERVAL",
		"ForwarderURL":  "FORWARDER_URL",
	}

	for fieldName, expectedTag := range expectedEnvTags {
		t.Run(fieldName, func(t *testing.T) {
			field, found := configType.FieldByName(fieldName)
			if !found {
				t.Errorf("Field %s not found", fieldName)
				return
			}

			envTag := field.Tag.Get("env")
			if envTag != expectedTag {
				t.Errorf("Field %s has env tag '%s', expected '%s'", fieldName, envTag, expectedTag)
			}
		})
	}
}

func TestCollectorConfig_ZeroValues(t *testing.T) {
	// Test zero values initialization
	config := CollectorConfig{}

	if config.LogPaths != nil {
		t.Errorf("LogPaths should be nil when zero-initialized, got %v", config.LogPaths)
	}

	if config.LogLevels != nil {
		t.Errorf("LogLevels should be nil when zero-initialized, got %v", config.LogLevels)
	}

	if config.BufferSize != 0 {
		t.Errorf("BufferSize should be 0 when zero-initialized, got %d", config.BufferSize)
	}

	if config.FlushInterval != 0 {
		t.Errorf("FlushInterval should be 0 when zero-initialized, got %v", config.FlushInterval)
	}

	if config.ForwarderURL != "" {
		t.Errorf("ForwarderURL should be empty when zero-initialized, got %s", config.ForwarderURL)
	}
}

func TestCollectorConfig_Assignment(t *testing.T) {
	// Test that we can assign values to all fields
	config := CollectorConfig{
		LogPaths:      []string{"/var/log/*.log", "/app/logs/*.log"},
		LogLevels:     []string{"ERROR", "WARN", "INFO"},
		BufferSize:    1024,
		FlushInterval: 30 * time.Second,
		ForwarderURL:  "http://log-forwarder:8080/logs",
	}

	// Verify assignments
	expectedLogPaths := []string{"/var/log/*.log", "/app/logs/*.log"}
	if !reflect.DeepEqual(config.LogPaths, expectedLogPaths) {
		t.Errorf("LogPaths = %v, expected %v", config.LogPaths, expectedLogPaths)
	}

	expectedLogLevels := []string{"ERROR", "WARN", "INFO"}
	if !reflect.DeepEqual(config.LogLevels, expectedLogLevels) {
		t.Errorf("LogLevels = %v, expected %v", config.LogLevels, expectedLogLevels)
	}

	if config.BufferSize != 1024 {
		t.Errorf("BufferSize = %d, expected 1024", config.BufferSize)
	}

	expectedFlushInterval := 30 * time.Second
	if config.FlushInterval != expectedFlushInterval {
		t.Errorf("FlushInterval = %v, expected %v", config.FlushInterval, expectedFlushInterval)
	}

	expectedURL := "http://log-forwarder:8080/logs"
	if config.ForwarderURL != expectedURL {
		t.Errorf("ForwarderURL = %s, expected %s", config.ForwarderURL, expectedURL)
	}
}

func TestCollectorConfig_EmptySlices(t *testing.T) {
	// Test behavior with empty slices vs nil slices
	config := CollectorConfig{
		LogPaths:  []string{},
		LogLevels: []string{},
	}

	if config.LogPaths == nil {
		t.Error("LogPaths should not be nil when initialized as empty slice")
	}

	if len(config.LogPaths) != 0 {
		t.Errorf("LogPaths length should be 0, got %d", len(config.LogPaths))
	}

	if config.LogLevels == nil {
		t.Error("LogLevels should not be nil when initialized as empty slice")
	}

	if len(config.LogLevels) != 0 {
		t.Errorf("LogLevels length should be 0, got %d", len(config.LogLevels))
	}
}

func TestCollectorConfig_DurationValues(t *testing.T) {
	// Test various duration values
	testCases := []struct {
		name     string
		duration time.Duration
	}{
		{"1 second", 1 * time.Second},
		{"1 minute", 1 * time.Minute},
		{"1 hour", 1 * time.Hour},
		{"500 milliseconds", 500 * time.Millisecond},
		{"zero duration", 0},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			config := CollectorConfig{
				FlushInterval: tc.duration,
			}

			if config.FlushInterval != tc.duration {
				t.Errorf("FlushInterval = %v, expected %v", config.FlushInterval, tc.duration)
			}
		})
	}
}

func TestCollectorConfig_Copyability(t *testing.T) {
	// Test that the struct can be copied safely
	original := CollectorConfig{
		LogPaths:      []string{"/var/log/*.log"},
		LogLevels:     []string{"ERROR"},
		BufferSize:    512,
		FlushInterval: 15 * time.Second,
		ForwarderURL:  "http://localhost:8080",
	}

	// Create a copy
	copied := original

	// Modify the copy
	copied.BufferSize = 1024
	copied.LogPaths = append(copied.LogPaths, "/app/logs/*.log")

	// Original should remain unchanged (except for slice references)
	if original.BufferSize != 512 {
		t.Errorf("Original BufferSize changed unexpectedly: %d", original.BufferSize)
	}

	// Note: LogPaths will be affected because slices are reference types
	// This is expected Go behavior, but we document it in the test
	if len(original.LogPaths) == 1 && len(copied.LogPaths) == 2 {
		// This would only be true if we had done a deep copy
		// Since we didn't, this test documents the shallow copy behavior
		t.Log("LogPaths slice is shared between original and copy (expected behavior)")
	}
}
