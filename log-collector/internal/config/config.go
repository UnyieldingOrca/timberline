package config

import (
	"os"
	"strconv"
	"strings"
	"time"
)

// CollectorConfig holds configuration for the log collector
type CollectorConfig struct {
	// LogPaths specifies file patterns to watch for logs
	LogPaths []string `yaml:"log_paths" env:"LOG_PATHS"`

	// LogLevels specifies which log levels to collect (empty = all)
	LogLevels []string `yaml:"log_levels" env:"LOG_LEVELS"`

	// BufferSize is the size of the internal log buffer
	BufferSize int `yaml:"buffer_size" env:"BUFFER_SIZE"`

	// FlushInterval is how often to flush buffered logs
	FlushInterval time.Duration `yaml:"flush_interval" env:"FLUSH_INTERVAL"`

	// ForwarderURL is the endpoint to forward logs to
	ForwarderURL string `yaml:"forwarder_url" env:"FORWARDER_URL"`
}

// Config represents the main configuration structure
type Config struct {
	ForwarderConfig CollectorConfig
	CollectorConfig CollectorConfig
	MetricsPort     int
}

// Load loads configuration from environment variables
func Load() (*Config, error) {
	collectorConfig := CollectorConfig{
		LogPaths:      getStringSliceFromEnv("LOG_PATHS", []string{"/var/log/containers/*", "/var/log/pods/*"}),
		LogLevels:     getStringSliceFromEnv("LOG_LEVELS", []string{"ERROR", "WARN", "FATAL"}),
		BufferSize:    getIntFromEnv("BUFFER_SIZE", 1000),
		FlushInterval: getDurationFromEnv("FLUSH_INTERVAL", 5*time.Second),
		ForwarderURL:  getStringFromEnv("FORWARDER_URL", "http://log-ingestor:8080"),
	}

	config := &Config{
		ForwarderConfig: collectorConfig,
		CollectorConfig: collectorConfig,
		MetricsPort:     getIntFromEnv("METRICS_PORT", 9090),
	}
	return config, nil
}

func getStringFromEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getStringSliceFromEnv(key string, defaultValue []string) []string {
	if value := os.Getenv(key); value != "" {
		return strings.Split(value, ",")
	}
	return defaultValue
}

func getIntFromEnv(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

func getDurationFromEnv(key string, defaultValue time.Duration) time.Duration {
	if value := os.Getenv(key); value != "" {
		if duration, err := time.ParseDuration(value); err == nil {
			return duration
		}
	}
	return defaultValue
}
