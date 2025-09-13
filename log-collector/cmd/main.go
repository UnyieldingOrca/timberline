package main

import (
	"context"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"github.com/sirupsen/logrus"
	"github.com/timberline/log-collector/internal/collector"
	"github.com/timberline/log-collector/internal/config"
	"github.com/timberline/log-collector/internal/forwarder"
	"github.com/timberline/log-collector/internal/metrics"
)

func main() {
	// Initialize logger
	logger := logrus.New()

	// Set log level from environment variable, default to Info
	logLevel := os.Getenv("LOG_LEVEL")
	switch strings.ToUpper(logLevel) {
	case "DEBUG":
		logger.SetLevel(logrus.DebugLevel)
	case "INFO":
		logger.SetLevel(logrus.InfoLevel)
	case "WARN", "WARNING":
		logger.SetLevel(logrus.WarnLevel)
	case "ERROR":
		logger.SetLevel(logrus.ErrorLevel)
	case "FATAL":
		logger.SetLevel(logrus.FatalLevel)
	case "PANIC":
		logger.SetLevel(logrus.PanicLevel)
	default:
		logger.SetLevel(logrus.InfoLevel) // Default level
	}

	logger.SetFormatter(&logrus.JSONFormatter{})

	// Load configuration
	logger.Debug("Loading configuration...")
	cfg, err := config.Load()
	if err != nil {
		logger.WithError(err).Fatal("Failed to load configuration")
	}
	logger.WithFields(logrus.Fields{
		"log_paths":      cfg.CollectorConfig.LogPaths,
		"log_levels":     cfg.CollectorConfig.LogLevels,
		"buffer_size":    cfg.CollectorConfig.BufferSize,
		"flush_interval": cfg.CollectorConfig.FlushInterval,
		"forwarder_url":  cfg.CollectorConfig.ForwarderURL,
		"metrics_port":   cfg.MetricsPort,
	}).Debug("Configuration loaded successfully")

	logger.WithField("config", cfg).Info("Starting Timberline Log Collector")

	// Initialize metrics
	logger.WithField("metrics_port", cfg.MetricsPort).Debug("Initializing metrics server...")
	metricsServer := metrics.NewServer(cfg.MetricsPort)
	go func() {
		logger.Debug("Starting metrics server...")
		if err := metricsServer.Start(); err != nil {
			logger.WithError(err).Error("Failed to start metrics server")
		} else {
			logger.WithField("port", cfg.MetricsPort).Debug("Metrics server started successfully")
		}
	}()

	// Initialize forwarder
	logger.WithField("forwarder_url", cfg.CollectorConfig.ForwarderURL).Debug("Initializing forwarder...")
	fwd, err := forwarder.New(cfg.CollectorConfig, logger)
	if err != nil {
		logger.WithError(err).Fatal("Failed to initialize forwarder")
	}
	logger.Debug("Forwarder initialized successfully")

	// Initialize collector
	logger.Debug("Initializing collector...")
	col, err := collector.New(cfg.CollectorConfig, fwd, logger)
	if err != nil {
		logger.WithError(err).Fatal("Failed to initialize collector")
	}
	logger.Debug("Collector initialized successfully")

	// Start collector
	logger.Debug("Creating application context...")
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go func() {
		logger.Debug("Starting collector in goroutine...")
		if err := col.Start(ctx); err != nil {
			logger.WithError(err).Error("Collector stopped with error")
		} else {
			logger.Debug("Collector started successfully")
		}
	}()

	// Wait for shutdown signal
	logger.Debug("Setting up signal handlers...")
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	logger.Debug("Waiting for shutdown signal...")
	sig := <-sigChan

	logger.WithField("signal", sig.String()).Info("Shutting down...")
	cancel()

	// Graceful shutdown with timeout
	logger.Debug("Starting graceful shutdown with 30s timeout...")
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()

	logger.Debug("Stopping collector...")
	if err := col.Stop(shutdownCtx); err != nil {
		logger.WithError(err).Error("Error during collector shutdown")
	} else {
		logger.Debug("Collector stopped successfully")
	}

	logger.Debug("Stopping forwarder...")
	if err := fwd.Stop(shutdownCtx); err != nil {
		logger.WithError(err).Error("Error during forwarder shutdown")
	} else {
		logger.Debug("Forwarder stopped successfully")
	}

	logger.Info("Shutdown complete")
}
