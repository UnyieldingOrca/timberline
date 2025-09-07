package models

import (
	"encoding/json"
	"errors"
	"time"
)

// LogEntry represents a generic log entry with minimal required fields
// and flexible metadata for different log sources
type LogEntry struct {
	Timestamp int64                  `json:"timestamp"`           // Unix timestamp in milliseconds
	Message   string                 `json:"message"`             // The actual log message
	Source    string                 `json:"source"`              // Source identifier (service, application, etc.)
	Metadata  map[string]interface{} `json:"metadata,omitempty"`  // Generic metadata for additional context
}


type LogBatch struct {
	Logs []LogEntry `json:"logs"`
}

type BatchResponse struct {
	Success      bool     `json:"success"`
	ProcessedCount int    `json:"processed_count"`
	Errors       []string `json:"errors,omitempty"`
}

type HealthResponse struct {
	Status    string    `json:"status"`
	Timestamp time.Time `json:"timestamp"`
	Version   string    `json:"version"`
	Uptime    string    `json:"uptime"`
	Checks    []HealthCheck `json:"checks"`
}

type HealthCheck struct {
	Name    string `json:"name"`
	Status  string `json:"status"`
	Message string `json:"message,omitempty"`
}

func (l *LogEntry) Validate() error {
	if l.Timestamp == 0 {
		return errors.New("timestamp is required")
	}
	if l.Message == "" {
		return errors.New("message is required")
	}
	if l.Source == "" {
		return errors.New("source is required")
	}
	
	// Validate timestamp is reasonable (not in the future by more than 1 hour, not older than 10 years)
	now := time.Now().UnixMilli()
	oneHourFromNow := now + (60 * 60 * 1000)        // 1 hour in milliseconds
	tenYearsAgo := now - (10 * 365 * 24 * 60 * 60 * 1000) // 10 years in milliseconds
	
	if l.Timestamp > oneHourFromNow {
		return errors.New("timestamp cannot be more than 1 hour in the future")
	}
	if l.Timestamp < tenYearsAgo {
		return errors.New("timestamp cannot be older than 10 years")
	}
	
	return nil
}

// GetLevel returns the log level from metadata, with a default fallback
func (l *LogEntry) GetLevel() string {
	if l.Metadata == nil {
		return "INFO"
	}
	
	if level, exists := l.Metadata["level"]; exists {
		if levelStr, ok := level.(string); ok {
			return levelStr
		}
	}
	
	// Check alternative metadata keys
	if level, exists := l.Metadata["log_level"]; exists {
		if levelStr, ok := level.(string); ok {
			return levelStr
		}
	}
	
	return "INFO"
}

// SetLevel sets the log level in metadata
func (l *LogEntry) SetLevel(level string) {
	if l.Metadata == nil {
		l.Metadata = make(map[string]interface{})
	}
	l.Metadata["level"] = level
}

// GetStringFromMetadata returns a string value from metadata with a fallback
func (l *LogEntry) GetStringFromMetadata(key, fallback string) string {
	if l.Metadata == nil {
		return fallback
	}
	
	if value, exists := l.Metadata[key]; exists {
		if str, ok := value.(string); ok {
			return str
		}
	}
	
	return fallback
}

func (b *LogBatch) Validate() error {
	if len(b.Logs) == 0 {
		return errors.New("batch cannot be empty")
	}
	
	for i, log := range b.Logs {
		if err := log.Validate(); err != nil {
			return &ValidationError{
				Field:   "logs[" + string(rune(i)) + "]",
				Message: err.Error(),
			}
		}
	}
	
	return nil
}

func (b *LogBatch) Size() int {
	return len(b.Logs)
}

func (b *LogBatch) ToJSON() ([]byte, error) {
	return json.Marshal(b)
}

type ValidationError struct {
	Field   string
	Message string
}

func (e *ValidationError) Error() string {
	return "validation error for " + e.Field + ": " + e.Message
}