package config

import (
	"os"
	"strconv"
	"time"

	"github.com/sirupsen/logrus"
)

type Config struct {
	ServerPort       int           `json:"server_port"`
	LogLevel         string        `json:"log_level"`
	MilvusAddress    string        `json:"milvus_address"`
	BatchSize        int           `json:"batch_size"`
	BatchTimeout     time.Duration `json:"batch_timeout"`
	MaxRequestSize   int64         `json:"max_request_size"`
	MetricsPort      int           `json:"metrics_port"`
	ReadTimeout      time.Duration `json:"read_timeout"`
	WriteTimeout     time.Duration `json:"write_timeout"`
	RateLimitRPS     int           `json:"rate_limit_rps"`
}

func NewConfig() *Config {
	return &Config{
		ServerPort:       getEnvAsInt("SERVER_PORT", 8080),
		LogLevel:         getEnv("LOG_LEVEL", "info"),
		MilvusAddress:    getEnv("MILVUS_ADDRESS", "milvus:19530"),
		BatchSize:        getEnvAsInt("BATCH_SIZE", 100),
		BatchTimeout:     getEnvAsDuration("BATCH_TIMEOUT", 5*time.Second),
		MaxRequestSize:   getEnvAsInt64("MAX_REQUEST_SIZE", 10*1024*1024), // 10MB
		MetricsPort:      getEnvAsInt("METRICS_PORT", 9090),
		ReadTimeout:      getEnvAsDuration("READ_TIMEOUT", 10*time.Second),
		WriteTimeout:     getEnvAsDuration("WRITE_TIMEOUT", 10*time.Second),
		RateLimitRPS:     getEnvAsInt("RATE_LIMIT_RPS", 1000),
	}
}

func (c *Config) Validate() error {
	if c.ServerPort <= 0 || c.ServerPort > 65535 {
		return &ConfigError{Field: "SERVER_PORT", Message: "must be between 1 and 65535"}
	}
	if c.MetricsPort <= 0 || c.MetricsPort > 65535 {
		return &ConfigError{Field: "METRICS_PORT", Message: "must be between 1 and 65535"}
	}
	if c.BatchSize <= 0 {
		return &ConfigError{Field: "BATCH_SIZE", Message: "must be greater than 0"}
	}
	if c.MaxRequestSize <= 0 {
		return &ConfigError{Field: "MAX_REQUEST_SIZE", Message: "must be greater than 0"}
	}
	if c.RateLimitRPS <= 0 {
		return &ConfigError{Field: "RATE_LIMIT_RPS", Message: "must be greater than 0"}
	}

	return nil
}

func (c *Config) SetupLogging() {
	level, err := logrus.ParseLevel(c.LogLevel)
	if err != nil {
		logrus.WithError(err).Warn("Invalid log level, defaulting to info")
		level = logrus.InfoLevel
	}
	
	logrus.SetLevel(level)
	logrus.SetFormatter(&logrus.JSONFormatter{
		TimestampFormat: time.RFC3339,
	})
}

type ConfigError struct {
	Field   string
	Message string
}

func (e *ConfigError) Error() string {
	return "config error for " + e.Field + ": " + e.Message
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvAsInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if parsed, err := strconv.Atoi(value); err == nil {
			return parsed
		}
		logrus.WithField("key", key).WithField("value", value).Warn("Invalid integer value, using default")
	}
	return defaultValue
}

func getEnvAsInt64(key string, defaultValue int64) int64 {
	if value := os.Getenv(key); value != "" {
		if parsed, err := strconv.ParseInt(value, 10, 64); err == nil {
			return parsed
		}
		logrus.WithField("key", key).WithField("value", value).Warn("Invalid int64 value, using default")
	}
	return defaultValue
}

func getEnvAsDuration(key string, defaultValue time.Duration) time.Duration {
	if value := os.Getenv(key); value != "" {
		if parsed, err := time.ParseDuration(value); err == nil {
			return parsed
		}
		logrus.WithField("key", key).WithField("value", value).Warn("Invalid duration value, using default")
	}
	return defaultValue
}