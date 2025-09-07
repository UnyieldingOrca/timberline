package main

import (
	"context"
	"os"
	"os/signal"
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
	logger.SetLevel(logrus.InfoLevel)
	logger.SetFormatter(&logrus.JSONFormatter{})

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		logger.WithError(err).Fatal("Failed to load configuration")
	}

	logger.WithField("config", cfg).Info("Starting Timberline Log Collector")

	// Initialize metrics
	metricsServer := metrics.NewServer(cfg.MetricsPort)
	go func() {
		if err := metricsServer.Start(); err != nil {
			logger.WithError(err).Error("Failed to start metrics server")
		}
	}()

	// Initialize forwarder
	fwd, err := forwarder.New(cfg.ForwarderConfig, logger)
	if err != nil {
		logger.WithError(err).Fatal("Failed to initialize forwarder")
	}

	// Initialize collector
	col, err := collector.New(cfg.CollectorConfig, fwd, logger)
	if err != nil {
		logger.WithError(err).Fatal("Failed to initialize collector")
	}

	// Start collector
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	go func() {
		if err := col.Start(ctx); err != nil {
			logger.WithError(err).Error("Collector stopped with error")
		}
	}()

	// Wait for shutdown signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	logger.Info("Shutting down...")
	cancel()

	// Graceful shutdown with timeout
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()

	if err := col.Stop(shutdownCtx); err != nil {
		logger.WithError(err).Error("Error during collector shutdown")
	}

	if err := fwd.Stop(shutdownCtx); err != nil {
		logger.WithError(err).Error("Error during forwarder shutdown")
	}

	logger.Info("Shutdown complete")
}
