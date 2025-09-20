package main

import (
	"context"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/gorilla/mux"
	"github.com/sirupsen/logrus"
	"github.com/timberline/log-ingestor/internal/config"
	"github.com/timberline/log-ingestor/internal/embedding"
	"github.com/timberline/log-ingestor/internal/handlers"
	"github.com/timberline/log-ingestor/internal/metrics"
	"github.com/timberline/log-ingestor/internal/storage"
)

const Version = "1.0.0"

func main() {
	// Load configuration
	cfg := config.NewConfig()
	if err := cfg.Validate(); err != nil {
		logrus.WithError(err).Fatal("Configuration validation failed")
	}

	cfg.SetupLogging()
	logger := logrus.WithField("component", "main")

	logger.WithField("version", Version).Info("Starting log ingestor service")

	// Initialize embedding service
	embeddingService := embedding.NewService(cfg.EmbeddingEndpoint, cfg.EmbeddingModel, cfg.EmbeddingDimension)
	
	// Test embedding service connection
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	if err := embeddingService.HealthCheck(ctx); err != nil {
		logger.WithError(err).Warn("Embedding service health check failed, proceeding anyway")
	}
	cancel()

	// Initialize storage
	storageClient := storage.NewMilvusClient(cfg.MilvusAddress, embeddingService, cfg.EmbeddingDimension)
	
	// Connect to storage with retry
	ctx, cancel = context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	
	if err := storageClient.Connect(ctx); err != nil {
		logger.WithError(err).Fatal("Failed to connect to storage")
	}
	defer func() {
		if err := storageClient.Close(); err != nil {
			logger.WithError(err).Error("Failed to close storage client")
		}
	}()
	
	// Create collection if it doesn't exist
	if err := storageClient.CreateCollection(ctx); err != nil {
		logger.WithError(err).Fatal("Failed to create collection")
	}

	// Initialize handlers
	streamHandler := handlers.NewStreamHandler(storageClient, cfg.BatchSize)
	healthHandler := handlers.NewHealthHandler(storageClient, Version)

	// Setup HTTP router
	router := mux.NewRouter()

	// API routes
	api := router.PathPrefix("/api/v1").Subrouter()
	api.HandleFunc("/logs/stream", streamHandler.HandleStream).Methods("POST")
	api.HandleFunc("/health", healthHandler.HandleHealth).Methods("GET")
	api.HandleFunc("/healthz", healthHandler.HandleLiveness).Methods("GET")
	api.HandleFunc("/ready", healthHandler.HandleReadiness).Methods("GET")

	// Add middleware
	router.Use(loggingMiddleware)
	router.Use(func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Add CORS headers
			w.Header().Set("Access-Control-Allow-Origin", "*")
			w.Header().Set("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
			w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
			
			// Handle preflight requests
			if r.Method == "OPTIONS" {
				w.WriteHeader(http.StatusOK)
				return
			}
			
			next.ServeHTTP(w, r)
		})
	})

	// Create main server
	server := &http.Server{
		Addr:         ":" + strconv.Itoa(cfg.ServerPort),
		Handler:      router,
		ReadTimeout:  cfg.ReadTimeout,
		WriteTimeout: cfg.WriteTimeout,
		IdleTimeout:  15 * time.Second,
	}

	// Start metrics server
	metricsServer := metrics.NewServer(cfg.MetricsPort)
	go func() {
		if err := metricsServer.Start(); err != nil {
			logger.WithError(err).Error("Metrics server failed")
		}
	}()

	// Start main server
	go func() {
		logger.WithField("address", server.Addr).Info("Starting HTTP server")
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.WithError(err).Fatal("HTTP server failed")
		}
	}()

	// Wait for interrupt signal
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)
	<-c

	logger.Info("Shutdown signal received")

	// Graceful shutdown with timeout
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer shutdownCancel()

	// Shutdown servers
	if err := server.Shutdown(shutdownCtx); err != nil {
		logger.WithError(err).Error("HTTP server shutdown failed")
	}

	if err := metricsServer.Stop(shutdownCtx); err != nil {
		logger.WithError(err).Error("Metrics server shutdown failed")
	}

	logger.Info("Service stopped")
}

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		
		// Wrap ResponseWriter to capture status code
		wrapped := &responseWriter{ResponseWriter: w, statusCode: http.StatusOK}
		
		next.ServeHTTP(wrapped, r)
		
		logrus.WithFields(logrus.Fields{
			"method":      r.Method,
			"path":        r.URL.Path,
			"status_code": wrapped.statusCode,
			"duration":    time.Since(start),
			"user_agent":  r.UserAgent(),
			"remote_addr": r.RemoteAddr,
		}).Info("HTTP request")
	})
}

type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}