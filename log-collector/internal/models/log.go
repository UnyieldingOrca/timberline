package models

import (
	"time"
)

// LogEntry represents a structured log entry matching the log-ingestor API specification
type LogEntry struct {
	Timestamp int64                  `json:"timestamp"`           // Unix timestamp in milliseconds
	Message   string                 `json:"message"`             // The actual log message
	Source    string                 `json:"source"`              // Source identifier (service, application, etc.)
	Metadata  map[string]interface{} `json:"metadata,omitempty"`  // Generic metadata for additional context
}

// NewLogEntry creates a new LogEntry with current timestamp
func NewLogEntry(message, source string) *LogEntry {
	return &LogEntry{
		Timestamp: time.Now().UnixMilli(),
		Message:   message,
		Source:    source,
		Metadata:  make(map[string]interface{}),
	}
}

// SetLevel sets the log level in metadata
func (l *LogEntry) SetLevel(level string) {
	if l.Metadata == nil {
		l.Metadata = make(map[string]interface{})
	}
	l.Metadata["level"] = level
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
	
	return "INFO"
}

// SetKubernetesMetadata adds Kubernetes-specific metadata
func (l *LogEntry) SetKubernetesMetadata(podName, namespace, nodeName string, labels map[string]string) {
	if l.Metadata == nil {
		l.Metadata = make(map[string]interface{})
	}
	
	l.Metadata["pod_name"] = podName
	l.Metadata["namespace"] = namespace
	l.Metadata["node_name"] = nodeName
	
	if labels != nil && len(labels) > 0 {
		l.Metadata["labels"] = labels
	}
}

// SetMetadata sets a generic metadata key-value pair
func (l *LogEntry) SetMetadata(key string, value interface{}) {
	if l.Metadata == nil {
		l.Metadata = make(map[string]interface{})
	}
	l.Metadata[key] = value
}

// GetMetadata returns a metadata value with fallback
func (l *LogEntry) GetMetadata(key string, fallback interface{}) interface{} {
	if l.Metadata == nil {
		return fallback
	}
	
	if value, exists := l.Metadata[key]; exists {
		return value
	}
	
	return fallback
}

// LogBatch represents a batch of log entries for the ingestor API
type LogBatch struct {
	Logs []*LogEntry `json:"logs"`
}
