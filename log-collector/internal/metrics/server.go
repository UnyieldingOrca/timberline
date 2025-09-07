package metrics

import (
	"context"
	"fmt"
	"net/http"
	"strconv"
	"sync"
	"time"

	"github.com/gorilla/mux"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"github.com/sirupsen/logrus"
)

// Server provides metrics endpoint for monitoring
type Server struct {
	port   int
	router *mux.Router
	logger *logrus.Logger
	server *http.Server
	mu     sync.RWMutex

	// Prometheus metrics
	logsCollected    prometheus.Counter
	logsForwarded    prometheus.Counter
	logsDropped      prometheus.Counter
	forwardingErrors prometheus.Counter
	bufferSize       prometheus.Gauge
	filesWatched     prometheus.Gauge
}

// NewServer creates a new metrics server
func NewServer(port int) *Server {
	logger := logrus.New()

	logsCollected := prometheus.NewCounter(prometheus.CounterOpts{
		Name: "timberline_logs_collected_total",
		Help: "Total number of log entries collected",
	})

	logsForwarded := prometheus.NewCounter(prometheus.CounterOpts{
		Name: "timberline_logs_forwarded_total",
		Help: "Total number of log entries successfully forwarded",
	})

	logsDropped := prometheus.NewCounter(prometheus.CounterOpts{
		Name: "timberline_logs_dropped_total",
		Help: "Total number of log entries dropped due to buffer overflow",
	})

	forwardingErrors := prometheus.NewCounter(prometheus.CounterOpts{
		Name: "timberline_forwarding_errors_total",
		Help: "Total number of log forwarding errors",
	})

	bufferSize := prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "timberline_buffer_size",
		Help: "Current number of log entries in buffer",
	})

	filesWatched := prometheus.NewGauge(prometheus.GaugeOpts{
		Name: "timberline_files_watched",
		Help: "Number of log files currently being watched",
	})

	// Try to register metrics, ignore if already registered (for tests)
	prometheus.Register(logsCollected)
	prometheus.Register(logsForwarded)
	prometheus.Register(logsDropped)
	prometheus.Register(forwardingErrors)
	prometheus.Register(bufferSize)
	prometheus.Register(filesWatched)

	router := mux.NewRouter()

	server := &Server{
		port:             port,
		router:           router,
		logger:           logger,
		logsCollected:    logsCollected,
		logsForwarded:    logsForwarded,
		logsDropped:      logsDropped,
		forwardingErrors: forwardingErrors,
		bufferSize:       bufferSize,
		filesWatched:     filesWatched,
	}

	server.setupRoutes()
	return server
}

// setupRoutes configures HTTP routes
func (s *Server) setupRoutes() {
	s.router.Handle("/metrics", promhttp.Handler())
	s.router.HandleFunc("/health", s.healthHandler).Methods("GET")
	s.router.HandleFunc("/ready", s.readinessHandler).Methods("GET")
}

// Start starts the metrics server
func (s *Server) Start() error {
	addr := ":" + strconv.Itoa(s.port)
	
	s.mu.Lock()
	s.server = &http.Server{
		Addr:    addr,
		Handler: s.router,
	}
	server := s.server
	s.mu.Unlock()
	
	s.logger.WithField("port", s.port).Info("Starting metrics server")
	return server.ListenAndServe()
}

// Stop gracefully stops the metrics server
func (s *Server) Stop() error {
	s.mu.RLock()
	server := s.server
	s.mu.RUnlock()
	
	if server == nil {
		return nil
	}
	s.logger.Info("Stopping metrics server")
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	return server.Shutdown(ctx)
}

// healthHandler handles health check requests
func (s *Server) healthHandler(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `{"status": "healthy", "service": "timberline-log-collector"}`)
}

// readinessHandler handles readiness check requests
func (s *Server) readinessHandler(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	fmt.Fprintf(w, `{"status": "ready", "service": "timberline-log-collector"}`)
}

// IncrementLogsCollected increments the logs collected counter
func (s *Server) IncrementLogsCollected() {
	s.logsCollected.Inc()
}

// IncrementLogsForwarded increments the logs forwarded counter
func (s *Server) IncrementLogsForwarded() {
	s.logsForwarded.Inc()
}

// IncrementLogsDropped increments the logs dropped counter
func (s *Server) IncrementLogsDropped() {
	s.logsDropped.Inc()
}

// IncrementForwardingErrors increments the forwarding errors counter
func (s *Server) IncrementForwardingErrors() {
	s.forwardingErrors.Inc()
}

// SetBufferSize sets the current buffer size
func (s *Server) SetBufferSize(size float64) {
	s.bufferSize.Set(size)
}

// SetFilesWatched sets the number of files being watched
func (s *Server) SetFilesWatched(count float64) {
	s.filesWatched.Set(count)
}
