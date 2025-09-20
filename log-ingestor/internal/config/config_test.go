package config

import (
	"os"
	"testing"
	"time"

	"github.com/sirupsen/logrus"
)

func TestNewConfig(t *testing.T) {
	// Clear all environment variables
	clearTestEnvs()

	config := NewConfig()

	// Test default values
	if config.ServerPort != 8080 {
		t.Errorf("Expected ServerPort to be 8080, got %d", config.ServerPort)
	}
	if config.LogLevel != "info" {
		t.Errorf("Expected LogLevel to be 'info', got %s", config.LogLevel)
	}
	if config.MilvusAddress != "milvus:19530" {
		t.Errorf("Expected MilvusAddress to be 'milvus:19530', got %s", config.MilvusAddress)
	}
	if config.BatchSize != 100 {
		t.Errorf("Expected BatchSize to be 100, got %d", config.BatchSize)
	}
	if config.BatchTimeout != 5*time.Second {
		t.Errorf("Expected BatchTimeout to be 5s, got %v", config.BatchTimeout)
	}
	if config.MaxRequestSize != 10*1024*1024 {
		t.Errorf("Expected MaxRequestSize to be 10MB, got %d", config.MaxRequestSize)
	}
	if config.MetricsPort != 9090 {
		t.Errorf("Expected MetricsPort to be 9090, got %d", config.MetricsPort)
	}
	if config.ReadTimeout != 10*time.Second {
		t.Errorf("Expected ReadTimeout to be 10s, got %v", config.ReadTimeout)
	}
	if config.WriteTimeout != 10*time.Second {
		t.Errorf("Expected WriteTimeout to be 10s, got %v", config.WriteTimeout)
	}
	if config.RateLimitRPS != 1000 {
		t.Errorf("Expected RateLimitRPS to be 1000, got %d", config.RateLimitRPS)
	}
	if config.SimilarityThreshold != 0.95 {
		t.Errorf("Expected SimilarityThreshold to be 0.95, got %f", config.SimilarityThreshold)
	}
}

func TestNewConfigWithEnvironmentVariables(t *testing.T) {
	// Clear all environment variables first
	clearTestEnvs()

	// Set test environment variables
	testEnvs := map[string]string{
		"SERVER_PORT":          "9080",
		"LOG_LEVEL":            "debug",
		"MILVUS_ADDRESS":       "localhost:19530",
		"BATCH_SIZE":           "200",
		"BATCH_TIMEOUT":        "10s",
		"MAX_REQUEST_SIZE":     "20971520", // 20MB
		"METRICS_PORT":         "9091",
		"READ_TIMEOUT":         "15s",
		"WRITE_TIMEOUT":        "20s",
		"RATE_LIMIT_RPS":       "500",
		"SIMILARITY_THRESHOLD": "0.90",
	}

	for key, value := range testEnvs {
		_ = os.Setenv(key, value)
	}
	defer clearTestEnvs()

	config := NewConfig()

	if config.ServerPort != 9080 {
		t.Errorf("Expected ServerPort to be 9080, got %d", config.ServerPort)
	}
	if config.LogLevel != "debug" {
		t.Errorf("Expected LogLevel to be 'debug', got %s", config.LogLevel)
	}
	if config.MilvusAddress != "localhost:19530" {
		t.Errorf("Expected MilvusAddress to be 'localhost:19530', got %s", config.MilvusAddress)
	}
	if config.BatchSize != 200 {
		t.Errorf("Expected BatchSize to be 200, got %d", config.BatchSize)
	}
	if config.BatchTimeout != 10*time.Second {
		t.Errorf("Expected BatchTimeout to be 10s, got %v", config.BatchTimeout)
	}
	if config.MaxRequestSize != 20*1024*1024 {
		t.Errorf("Expected MaxRequestSize to be 20MB, got %d", config.MaxRequestSize)
	}
	if config.MetricsPort != 9091 {
		t.Errorf("Expected MetricsPort to be 9091, got %d", config.MetricsPort)
	}
	if config.ReadTimeout != 15*time.Second {
		t.Errorf("Expected ReadTimeout to be 15s, got %v", config.ReadTimeout)
	}
	if config.WriteTimeout != 20*time.Second {
		t.Errorf("Expected WriteTimeout to be 20s, got %v", config.WriteTimeout)
	}
	if config.RateLimitRPS != 500 {
		t.Errorf("Expected RateLimitRPS to be 500, got %d", config.RateLimitRPS)
	}
	if config.SimilarityThreshold != 0.90 {
		t.Errorf("Expected SimilarityThreshold to be 0.90, got %f", config.SimilarityThreshold)
	}
}

func TestValidate(t *testing.T) {
	tests := []struct {
		name        string
		config      *Config
		expectError bool
		errorField  string
	}{
		{
			name:        "Valid config",
			config:      NewConfig(),
			expectError: false,
		},
		{
			name: "Invalid ServerPort - zero",
			config: &Config{
				ServerPort:     0,
				MetricsPort:    9090,
				BatchSize:      100,
				MaxRequestSize: 1024,
				RateLimitRPS:   1000,
			},
			expectError: true,
			errorField:  "SERVER_PORT",
		},
		{
			name: "Invalid ServerPort - too high",
			config: &Config{
				ServerPort:     70000,
				MetricsPort:    9090,
				BatchSize:      100,
				MaxRequestSize: 1024,
				RateLimitRPS:   1000,
			},
			expectError: true,
			errorField:  "SERVER_PORT",
		},
		{
			name: "Invalid MetricsPort - zero",
			config: &Config{
				ServerPort:     8080,
				MetricsPort:    0,
				BatchSize:      100,
				MaxRequestSize: 1024,
				RateLimitRPS:   1000,
			},
			expectError: true,
			errorField:  "METRICS_PORT",
		},
		{
			name: "Invalid BatchSize - zero",
			config: &Config{
				ServerPort:     8080,
				MetricsPort:    9090,
				BatchSize:      0,
				MaxRequestSize: 1024,
				RateLimitRPS:   1000,
			},
			expectError: true,
			errorField:  "BATCH_SIZE",
		},
		{
			name: "Invalid MaxRequestSize - zero",
			config: &Config{
				ServerPort:     8080,
				MetricsPort:    9090,
				BatchSize:      100,
				MaxRequestSize: 0,
				RateLimitRPS:   1000,
			},
			expectError: true,
			errorField:  "MAX_REQUEST_SIZE",
		},
		{
			name: "Invalid RateLimitRPS - zero",
			config: &Config{
				ServerPort:     8080,
				MetricsPort:    9090,
				BatchSize:      100,
				MaxRequestSize: 1024,
				RateLimitRPS:   0,
			},
			expectError: true,
			errorField:  "RATE_LIMIT_RPS",
		},
		{
			name: "Invalid SimilarityThreshold - negative",
			config: &Config{
				ServerPort:          8080,
				MetricsPort:         9090,
				BatchSize:           100,
				MaxRequestSize:      1024,
				RateLimitRPS:        1000,
				EmbeddingEndpoint:   "http://test",
				EmbeddingDimension:  768,
				SimilarityThreshold: -0.1,
			},
			expectError: true,
			errorField:  "SIMILARITY_THRESHOLD",
		},
		{
			name: "Invalid SimilarityThreshold - too high",
			config: &Config{
				ServerPort:          8080,
				MetricsPort:         9090,
				BatchSize:           100,
				MaxRequestSize:      1024,
				RateLimitRPS:        1000,
				EmbeddingEndpoint:   "http://test",
				EmbeddingDimension:  768,
				SimilarityThreshold: 1.1,
			},
			expectError: true,
			errorField:  "SIMILARITY_THRESHOLD",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.config.Validate()
			if tt.expectError {
				if err == nil {
					t.Errorf("Expected error for %s, got nil", tt.name)
				}
				if configErr, ok := err.(*ConfigError); ok {
					if configErr.Field != tt.errorField {
						t.Errorf("Expected error field %s, got %s", tt.errorField, configErr.Field)
					}
				} else {
					t.Errorf("Expected ConfigError type, got %T", err)
				}
			} else {
				if err != nil {
					t.Errorf("Expected no error for %s, got %v", tt.name, err)
				}
			}
		})
	}
}

func TestSetupLogging(t *testing.T) {
	originalLevel := logrus.GetLevel()
	originalFormatter := logrus.StandardLogger().Formatter
	defer func() {
		logrus.SetLevel(originalLevel)
		logrus.SetFormatter(originalFormatter)
	}()

	tests := []struct {
		name          string
		logLevel      string
		expectedLevel logrus.Level
	}{
		{"Debug level", "debug", logrus.DebugLevel},
		{"Info level", "info", logrus.InfoLevel},
		{"Warn level", "warn", logrus.WarnLevel},
		{"Error level", "error", logrus.ErrorLevel},
		{"Invalid level defaults to info", "invalid", logrus.InfoLevel},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			config := &Config{LogLevel: tt.logLevel}
			config.SetupLogging()

			if logrus.GetLevel() != tt.expectedLevel {
				t.Errorf("Expected log level %v, got %v", tt.expectedLevel, logrus.GetLevel())
			}

			// Check that JSON formatter is set
			if _, ok := logrus.StandardLogger().Formatter.(*logrus.JSONFormatter); !ok {
				t.Error("Expected JSONFormatter to be set")
			}
		})
	}
}

func TestConfigError(t *testing.T) {
	err := &ConfigError{
		Field:   "TEST_FIELD",
		Message: "test message",
	}

	expected := "config error for TEST_FIELD: test message"
	if err.Error() != expected {
		t.Errorf("Expected error message '%s', got '%s'", expected, err.Error())
	}
}

func TestGetEnvHelpers(t *testing.T) {
	// Clear environment first
	clearTestEnvs()

	t.Run("getEnv", func(t *testing.T) {
		// Test with default
		result := getEnv("NON_EXISTENT", "default")
		if result != "default" {
			t.Errorf("Expected 'default', got '%s'", result)
		}

		// Test with existing env
		_ = os.Setenv("TEST_STRING", "test_value")
		defer func() { _ = os.Unsetenv("TEST_STRING") }()
		result = getEnv("TEST_STRING", "default")
		if result != "test_value" {
			t.Errorf("Expected 'test_value', got '%s'", result)
		}
	})

	t.Run("getEnvAsInt", func(t *testing.T) {
		// Test with default
		result := getEnvAsInt("NON_EXISTENT_INT", 42)
		if result != 42 {
			t.Errorf("Expected 42, got %d", result)
		}

		// Test with valid int
		_ = os.Setenv("TEST_INT", "100")
		defer func() { _ = os.Unsetenv("TEST_INT") }()
		result = getEnvAsInt("TEST_INT", 42)
		if result != 100 {
			t.Errorf("Expected 100, got %d", result)
		}

		// Test with invalid int (should use default)
		_ = os.Setenv("TEST_INVALID_INT", "not_a_number")
		defer func() { _ = os.Unsetenv("TEST_INVALID_INT") }()
		result = getEnvAsInt("TEST_INVALID_INT", 42)
		if result != 42 {
			t.Errorf("Expected 42 (default), got %d", result)
		}
	})

	t.Run("getEnvAsInt64", func(t *testing.T) {
		// Test with default
		result := getEnvAsInt64("NON_EXISTENT_INT64", 1000)
		if result != 1000 {
			t.Errorf("Expected 1000, got %d", result)
		}

		// Test with valid int64
		_ = os.Setenv("TEST_INT64", "9223372036854775807")
		defer func() { _ = os.Unsetenv("TEST_INT64") }()
		result = getEnvAsInt64("TEST_INT64", 1000)
		if result != 9223372036854775807 {
			t.Errorf("Expected 9223372036854775807, got %d", result)
		}

		// Test with invalid int64 (should use default)
		_ = os.Setenv("TEST_INVALID_INT64", "not_a_number")
		defer func() { _ = os.Unsetenv("TEST_INVALID_INT64") }()
		result = getEnvAsInt64("TEST_INVALID_INT64", 1000)
		if result != 1000 {
			t.Errorf("Expected 1000 (default), got %d", result)
		}
	})

	t.Run("getEnvAsDuration", func(t *testing.T) {
		// Test with default
		result := getEnvAsDuration("NON_EXISTENT_DURATION", 5*time.Second)
		if result != 5*time.Second {
			t.Errorf("Expected 5s, got %v", result)
		}

		// Test with valid duration
		_ = os.Setenv("TEST_DURATION", "30s")
		defer func() { _ = os.Unsetenv("TEST_DURATION") }()
		result = getEnvAsDuration("TEST_DURATION", 5*time.Second)
		if result != 30*time.Second {
			t.Errorf("Expected 30s, got %v", result)
		}

		// Test with invalid duration (should use default)
		_ = os.Setenv("TEST_INVALID_DURATION", "not_a_duration")
		defer func() { _ = os.Unsetenv("TEST_INVALID_DURATION") }()
		result = getEnvAsDuration("TEST_INVALID_DURATION", 5*time.Second)
		if result != 5*time.Second {
			t.Errorf("Expected 5s (default), got %v", result)
		}
	})

	t.Run("getEnvAsFloat32", func(t *testing.T) {
		// Test with default
		result := getEnvAsFloat32("NON_EXISTENT_FLOAT32", 0.75)
		if result != 0.75 {
			t.Errorf("Expected 0.75, got %f", result)
		}

		// Test with valid float32
		_ = os.Setenv("TEST_FLOAT32", "0.123")
		defer func() { _ = os.Unsetenv("TEST_FLOAT32") }()
		result = getEnvAsFloat32("TEST_FLOAT32", 0.75)
		if result != 0.123 {
			t.Errorf("Expected 0.123, got %f", result)
		}

		// Test with invalid float32 (should use default)
		_ = os.Setenv("TEST_INVALID_FLOAT32", "not_a_float")
		defer func() { _ = os.Unsetenv("TEST_INVALID_FLOAT32") }()
		result = getEnvAsFloat32("TEST_INVALID_FLOAT32", 0.75)
		if result != 0.75 {
			t.Errorf("Expected 0.75 (default), got %f", result)
		}
	})
}

// Helper function to clear test environment variables
func clearTestEnvs() {
	envs := []string{
		"SERVER_PORT", "LOG_LEVEL", "MILVUS_ADDRESS", "BATCH_SIZE",
		"BATCH_TIMEOUT", "MAX_REQUEST_SIZE", "METRICS_PORT", "READ_TIMEOUT",
		"WRITE_TIMEOUT", "RATE_LIMIT_RPS", "SIMILARITY_THRESHOLD", "TEST_STRING", "TEST_INT",
		"TEST_INVALID_INT", "TEST_INT64", "TEST_INVALID_INT64",
		"TEST_DURATION", "TEST_INVALID_DURATION", "TEST_FLOAT32", "TEST_INVALID_FLOAT32",
	}
	for _, env := range envs {
		_ = os.Unsetenv(env)
	}
}
