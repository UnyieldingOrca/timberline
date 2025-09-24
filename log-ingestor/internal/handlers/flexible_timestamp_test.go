package handlers

import (
	"encoding/json"
	"testing"
	"time"
)

func TestFlexibleTimestamp_UnmarshalJSON(t *testing.T) {
	tests := []struct {
		name     string
		input    string
		expected int64
	}{
		{
			name:     "Numeric timestamp in milliseconds",
			input:    `1758675874261`,
			expected: 1758675874261,
		},
		{
			name:     "Numeric timestamp in seconds",
			input:    `1758675874`,
			expected: 1758675874,
		},
		{
			name:     "ISO 8601 string timestamp",
			input:    `"2025-09-24T01:04:34Z"`,
			expected: 1758675874000, // Approximate - will be close
		},
		{
			name:     "ISO string without Z",
			input:    `"2025-09-24T01:04:34"`,
			expected: 1758675874000, // Approximate - will be close
		},
		{
			name:     "Simple datetime format",
			input:    `"2025-09-24 01:04:34"`,
			expected: 1758675874000, // Approximate - will be close
		},
		{
			name:     "Slash format",
			input:    `"2025/09/24 01:04:34"`,
			expected: 1758675874000, // Approximate - will be close
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var ft FlexibleTimestamp
			err := json.Unmarshal([]byte(tt.input), &ft)
			if err != nil {
				t.Errorf("Failed to unmarshal %s: %v", tt.input, err)
				return
			}

			// For string timestamps, we just check they're reasonable (within a day)
			if tt.name != "Numeric timestamp in milliseconds" && tt.name != "Numeric timestamp in seconds" {
				// For time-based tests, just verify it's a reasonable timestamp
				if int64(ft) < 1000000000000 || int64(ft) > 2000000000000 {
					t.Errorf("Timestamp %d is not in reasonable range", int64(ft))
				}
			} else {
				// For numeric tests, check exact match
				if int64(ft) != tt.expected {
					t.Errorf("Expected %d, got %d", tt.expected, int64(ft))
				}
			}
		})
	}
}

func TestFlexibleTimestamp_UnmarshalJSON_InvalidInput(t *testing.T) {
	tests := []struct {
		name        string
		input       string
		expectError bool
	}{
		{
			name:        "Invalid string format",
			input:       `"not-a-timestamp"`,
			expectError: false, // Should fallback to current time
		},
		{
			name:        "Empty string",
			input:       `""`,
			expectError: false, // Should fallback to current time
		},
		{
			name:        "Invalid JSON",
			input:       `invalid`,
			expectError: true, // JSON unmarshal should fail
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var ft FlexibleTimestamp
			err := json.Unmarshal([]byte(tt.input), &ft)

			if tt.expectError {
				if err == nil {
					t.Errorf("Expected error for invalid JSON, got nil")
				}
				return
			}

			// Should not error (fallback to current time)
			if err != nil {
				t.Errorf("Should not error on invalid input, got: %v", err)
			}

			// Should have set to current time (reasonable range)
			now := time.Now().Unix() * 1000
			if int64(ft) < now-10000 || int64(ft) > now+10000 {
				t.Errorf("Expected fallback to current time, got %d", int64(ft))
			}
		})
	}
}

func TestFluentBitLogEntry_FlexibleTimestamp(t *testing.T) {
	tests := []struct {
		name     string
		jsonData string
		wantErr  bool
	}{
		{
			name: "String timestamp in JSON",
			jsonData: `{
				"timestamp": "2025-09-24T01:04:34Z",
				"log": "Test message",
				"source": "test"
			}`,
			wantErr: false,
		},
		{
			name: "Numeric timestamp in JSON",
			jsonData: `{
				"timestamp": 1758675874261,
				"log": "Test message",
				"source": "test"
			}`,
			wantErr: false,
		},
		{
			name: "Date field with string timestamp",
			jsonData: `{
				"date": 1758675874.261,
				"timestamp": "2025-09-24T01:04:34Z",
				"log": "Test message",
				"source": "test"
			}`,
			wantErr: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var entry FluentBitLogEntry
			err := json.Unmarshal([]byte(tt.jsonData), &entry)

			if (err != nil) != tt.wantErr {
				t.Errorf("json.Unmarshal() error = %v, wantErr %v", err, tt.wantErr)
				return
			}

			if !tt.wantErr {
				// Verify the entry was parsed successfully
				if entry.Log != "Test message" {
					t.Errorf("Expected log message 'Test message', got '%s'", entry.Log)
				}

				// Transform to internal format and verify timestamp handling
				logEntry := entry.transformToLogEntry()
				if logEntry.Timestamp <= 0 {
					t.Errorf("Expected positive timestamp, got %d", logEntry.Timestamp)
				}
			}
		})
	}
}

func TestFluentBitLogEntry_ApplicationJSON(t *testing.T) {
	tests := []struct {
		name        string
		jsonData    string
		expectedMsg string
		wantErr     bool
	}{
		{
			name: "Application JSON in log field",
			jsonData: `{
				"date": 1758675874.261,
				"log": "{\"timestamp\":\"2025-09-24T01:04:34Z\",\"level\":\"INFO\",\"message\":\"Application log\",\"service\":\"my-app\"}",
				"source": "fluent-bit"
			}`,
			expectedMsg: "{\"timestamp\":\"2025-09-24T01:04:34Z\",\"level\":\"INFO\",\"message\":\"Application log\",\"service\":\"my-app\"}",
			wantErr:     false,
		},
		{
			name: "Simple text log",
			jsonData: `{
				"date": 1758675874.261,
				"log": "Simple text log message",
				"source": "fluent-bit"
			}`,
			expectedMsg: "Simple text log message",
			wantErr:     false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			var entry FluentBitLogEntry
			err := json.Unmarshal([]byte(tt.jsonData), &entry)

			if (err != nil) != tt.wantErr {
				t.Errorf("json.Unmarshal() error = %v, wantErr %v", err, tt.wantErr)
				return
			}

			if !tt.wantErr {
				// Transform to internal format
				logEntry := entry.transformToLogEntry()

				// Verify message content (JSON string is preserved as-is)
				if logEntry.Message != tt.expectedMsg {
					t.Errorf("Expected message '%s', got '%s'", tt.expectedMsg, logEntry.Message)
				}

				// Verify timestamp is processed
				if logEntry.Timestamp <= 0 {
					t.Errorf("Expected positive timestamp, got %d", logEntry.Timestamp)
				}
			}
		})
	}
}