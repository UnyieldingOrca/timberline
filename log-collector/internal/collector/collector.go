package collector

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/fsnotify/fsnotify"
	"github.com/sirupsen/logrus"
	"github.com/timberline/log-collector/internal/config"
	"github.com/timberline/log-collector/internal/forwarder"
	"github.com/timberline/log-collector/internal/k8s"
	"github.com/timberline/log-collector/internal/models"
)

// Collector manages log collection from multiple sources
type Collector struct {
	config    config.CollectorConfig
	forwarder forwarder.Interface
	logger    *logrus.Logger
	watcher   *fsnotify.Watcher
	k8sClient *k8s.Client
	buffer    chan *models.LogEntry
	tailFiles map[string]*TailFile
	mu        sync.RWMutex
	stopCh    chan struct{}
}

// TailFile represents a file being tailed
type TailFile struct {
	path     string
	file     *os.File
	reader   *bufio.Reader
	position int64
	lastMod  time.Time
}

// New creates a new collector instance
func New(cfg config.CollectorConfig, fwd forwarder.Interface, logger *logrus.Logger) (*Collector, error) {
	logger.Debug("Creating new collector instance...")

	logger.Debug("Initializing file system watcher...")
	watcher, err := fsnotify.NewWatcher()
	if err != nil {
		return nil, fmt.Errorf("failed to create file watcher: %w", err)
	}
	logger.Debug("File system watcher created successfully")

	logger.Debug("Initializing Kubernetes client...")
	k8sClient, err := k8s.NewClient()
	if err != nil {
		logger.WithError(err).Warn("Failed to initialize Kubernetes client, metadata enrichment disabled")
	} else {
		logger.Debug("Kubernetes client initialized successfully")
	}

	logger.WithFields(logrus.Fields{
		"buffer_size":     cfg.BufferSize,
		"flush_interval":  cfg.FlushInterval,
		"max_batch_size": cfg.MaxBatchSize,
	}).Debug("Creating collector instance with configuration")

	return &Collector{
		config:    cfg,
		forwarder: fwd,
		logger:    logger,
		watcher:   watcher,
		k8sClient: k8sClient,
		buffer:    make(chan *models.LogEntry, cfg.BufferSize),
		tailFiles: make(map[string]*TailFile),
		stopCh:    make(chan struct{}),
	}, nil
}

// Start begins log collection
func (c *Collector) Start(ctx context.Context) error {
	c.logger.Info("Starting log collector")

	// Start buffer processor
	c.logger.Debug("Starting buffer processor...")
	go c.processBuffer(ctx)

	// Start file watcher
	c.logger.Debug("Starting file watcher...")
	go c.watchFiles(ctx)

	// Discover and start tailing existing log files
	c.logger.Debug("Discovering existing log files...")
	if err := c.discoverLogFiles(); err != nil {
		return fmt.Errorf("failed to discover log files: %w", err)
	}
	c.logger.Debug("Log file discovery completed")

	<-ctx.Done()
	return nil
}

// Stop gracefully stops the collector
func (c *Collector) Stop(ctx context.Context) error {
	c.logger.Info("Stopping log collector")

	close(c.stopCh)

	if c.watcher != nil {
		if err := c.watcher.Close(); err != nil {
			c.logger.WithError(err).Error("Error closing file watcher")
		}
	}

	// Close all tailed files
	c.mu.Lock()
	for _, tf := range c.tailFiles {
		if tf.file != nil {
			if err := tf.file.Close(); err != nil {
				c.logger.WithError(err).WithField("path", tf.path).Error("Error closing file")
			}
		}
	}
	c.mu.Unlock()

	// Flush remaining buffer
	c.flushBuffer()

	// Acknowledge the parameter is used for timeout context
	_ = ctx
	return nil
}

// discoverLogFiles finds and starts tailing log files matching configured patterns
func (c *Collector) discoverLogFiles() error {
	c.logger.WithField("patterns", c.config.LogPaths).Debug("Starting log file discovery")
	for _, pattern := range c.config.LogPaths {
		c.logger.WithField("pattern", pattern).Debug("Processing pattern")
		matches, err := filepath.Glob(pattern)
		if err != nil {
			c.logger.WithError(err).WithField("pattern", pattern).Error("Failed to glob pattern")
			continue
		}
		c.logger.WithFields(logrus.Fields{
			"pattern":    pattern,
			"match_count": len(matches),
		}).Debug("Pattern matches found")

		for _, path := range matches {
			c.logger.WithField("path", path).Debug("Starting to tail file")
			if err := c.startTailing(path); err != nil {
				c.logger.WithError(err).WithField("path", path).Error("Failed to start tailing file")
			}
		}

		// Watch directory for new files
		dir := filepath.Dir(pattern)
		c.logger.WithField("directory", dir).Debug("Adding directory to file watcher")
		if err := c.watcher.Add(dir); err != nil {
			c.logger.WithError(err).WithField("dir", dir).Error("Failed to watch directory")
		} else {
			c.logger.WithField("directory", dir).Debug("Directory added to watcher successfully")
		}
	}

	return nil
}

// startTailing begins tailing a specific log file
func (c *Collector) startTailing(path string) error {
	c.logger.WithField("path", path).Debug("Attempting to start tailing file")
	c.mu.Lock()
	defer c.mu.Unlock()

	if _, exists := c.tailFiles[path]; exists {
		c.logger.WithField("path", path).Debug("File already being tailed, skipping")
		return nil // Already tailing this file
	}

	c.logger.WithField("path", path).Debug("Opening file for tailing")
	file, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("failed to open file %s: %w", path, err)
	}

	// Seek to end of file to only capture new logs
	c.logger.WithField("path", path).Debug("Getting file stats...")
	stat, err := file.Stat()
	if err != nil {
		if err := file.Close(); err != nil {
			return fmt.Errorf("failed to close file after stat error %s: %w", path, err)
		}
		return fmt.Errorf("failed to stat file %s: %w", path, err)
	}
	c.logger.WithFields(logrus.Fields{
		"path": path,
		"size": stat.Size(),
		"mod_time": stat.ModTime(),
	}).Debug("File stats retrieved")

	c.logger.WithField("path", path).Debug("Seeking to end of file")
	position, err := file.Seek(0, io.SeekEnd)
	if err != nil {
		if err := file.Close(); err != nil {
			return fmt.Errorf("failed to close file after seek error %s: %w", path, err)
		}
		return fmt.Errorf("failed to seek to end of file %s: %w", path, err)
	}
	c.logger.WithFields(logrus.Fields{
		"path": path,
		"position": position,
	}).Debug("File positioned at end for new log capture")

	tailFile := &TailFile{
		path:     path,
		file:     file,
		reader:   bufio.NewReader(file),
		position: position,
		lastMod:  stat.ModTime(),
	}

	c.tailFiles[path] = tailFile
	c.logger.WithFields(logrus.Fields{
		"path": path,
		"total_files_tailing": len(c.tailFiles),
	}).Debug("File added to tail tracking map")

	// Start goroutine to tail this file
	c.logger.WithField("path", path).Debug("Starting tail goroutine")
	go c.tailFile(tailFile)

	c.logger.WithField("path", path).Info("Started tailing log file")
	return nil
}

// tailFile continuously reads from a log file
func (c *Collector) tailFile(tf *TailFile) {
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-c.stopCh:
			return
		case <-ticker.C:
			if err := c.readNewLines(tf); err != nil {
				// Check if file was deleted or closed
				if os.IsNotExist(err) || strings.Contains(err.Error(), "file deleted") || strings.Contains(err.Error(), "file already closed") {
					c.logger.WithField("path", tf.path).Info("File deleted or closed, cleaning up tail")
					c.cleanupTailFile(tf.path)
					return
				}
				c.logger.WithError(err).WithField("path", tf.path).Error("Error reading file")
			}
		}
	}
}

// readNewLines reads new lines from a tailed file
func (c *Collector) readNewLines(tf *TailFile) error {
	c.logger.WithField("path", tf.path).Debug("Checking for new lines")
	stat, err := tf.file.Stat()
	if err != nil {
		// Check if the file was deleted or file handle is closed
		if os.IsNotExist(err) || strings.Contains(err.Error(), "file already closed") {
			c.logger.WithField("path", tf.path).Info("File was deleted or closed, stopping tail")
			return fmt.Errorf("file deleted: %w", err)
		}
		return err
	}

	// Check if file was truncated or rotated
	if stat.Size() < tf.position {
		c.logger.WithFields(logrus.Fields{
			"path": tf.path,
			"current_size": stat.Size(),
			"last_position": tf.position,
		}).Debug("File truncated/rotated, resetting position")
		tf.position = 0
		if _, err := tf.file.Seek(0, io.SeekStart); err != nil {
			return err
		}
		tf.reader = bufio.NewReader(tf.file)
	}

	// Check if file has new content
	if stat.ModTime().After(tf.lastMod) || stat.Size() > tf.position {
		c.logger.WithFields(logrus.Fields{
			"path": tf.path,
			"size": stat.Size(),
			"position": tf.position,
			"mod_time_changed": stat.ModTime().After(tf.lastMod),
		}).Debug("File has new content, reading lines")
		lineCount := 0
		for {
			line, err := tf.reader.ReadString('\n')
			if err != nil {
				if err == io.EOF {
					c.logger.WithFields(logrus.Fields{
						"path": tf.path,
						"lines_read": lineCount,
					}).Debug("Reached end of file")
					break
				}
				return err
			}
			lineCount++

			// Process the log line
			if logEntry := c.processLogLine(strings.TrimSpace(line), tf.path); logEntry != nil {
				c.logger.WithFields(logrus.Fields{
					"path": tf.path,
					"source": logEntry.Source,
					"level": logEntry.GetLevel(),
				}).Debug("Log entry processed, adding to buffer")
				select {
				case c.buffer <- logEntry:
				case <-c.stopCh:
					return nil
				default:
					// Buffer is full, drop the log
					c.logger.WithField("path", tf.path).Warn("Buffer full, dropping log entry")
				}
			} else {
				c.logger.WithField("path", tf.path).Debug("Log line filtered out or could not be processed")
			}
		}

		tf.lastMod = stat.ModTime()
		tf.position, _ = tf.file.Seek(0, io.SeekCurrent)
	}

	return nil
}

// processLogLine parses and enriches a log line
func (c *Collector) processLogLine(line, filePath string) *models.LogEntry {
	if line == "" {
		c.logger.WithField("path", filePath).Debug("Empty line, skipping")
		return nil
	}

	// Create entry with current timestamp and extract source from file path
	c.logger.WithField("path", filePath).Debug("Processing log line")
	source := c.extractSource(filePath)
	entry := models.NewLogEntry(line, source)
	c.logger.WithFields(logrus.Fields{
		"path": filePath,
		"source": source,
		"timestamp": entry.Timestamp,
	}).Debug("Log entry created")

	// Try to parse as JSON first
	var jsonLog map[string]interface{}
	if err := json.Unmarshal([]byte(line), &jsonLog); err == nil {
		c.logger.WithField("path", filePath).Debug("Log line parsed as JSON")
		// JSON log parsed successfully - use structured data for level/timestamp extraction

		// Extract log level if present
		if level, ok := jsonLog["level"].(string); ok {
			entry.SetLevel(strings.ToUpper(level))
			c.logger.WithFields(logrus.Fields{
				"path": filePath,
				"extracted_level": level,
			}).Debug("Extracted log level from JSON")
		} else if severity, ok := jsonLog["severity"].(string); ok {
			entry.SetLevel(strings.ToUpper(severity))
			c.logger.WithFields(logrus.Fields{
				"path": filePath,
				"extracted_severity": severity,
			}).Debug("Extracted log severity from JSON")
		}

		// Extract timestamp if present (convert to Unix milliseconds if it's RFC3339)
		if ts, ok := jsonLog["timestamp"].(string); ok {
			if parsedTime, err := time.Parse(time.RFC3339, ts); err == nil {
				entry.Timestamp = parsedTime.UnixMilli()
			}
		}

		// Extract any additional metadata from the JSON log
		for key, value := range jsonLog {
			if key != "level" && key != "severity" && key != "timestamp" && key != "message" {
				entry.SetMetadata(key, value)
			}
		}
	} else {
		c.logger.WithField("path", filePath).Debug("Log line is not JSON, extracting level from text")
		// Try to extract log level from unstructured log
		level := c.extractLogLevel(line)
		entry.SetLevel(level)
		c.logger.WithFields(logrus.Fields{
			"path": filePath,
			"extracted_level": level,
		}).Debug("Extracted log level from unstructured text")
	}

	// Filter logs based on configured levels
	if !c.shouldCollectLevel(entry.GetLevel()) {
		c.logger.WithFields(logrus.Fields{
			"path": filePath,
			"level": entry.GetLevel(),
			"configured_levels": c.config.LogLevels,
		}).Debug("Log entry filtered out due to level filtering")
		return nil
	}

	// Enrich with Kubernetes metadata
	if c.k8sClient != nil {
		c.logger.WithField("path", filePath).Debug("Enriching log with Kubernetes metadata")
		if podInfo := c.k8sClient.GetPodInfo(filePath); podInfo != nil {
			entry.SetKubernetesMetadata(
				podInfo.PodName,
				podInfo.Namespace,
				podInfo.NodeName,
				podInfo.Labels,
			)
			c.logger.WithFields(logrus.Fields{
				"path": filePath,
				"pod_name": podInfo.PodName,
				"namespace": podInfo.Namespace,
				"node_name": podInfo.NodeName,
			}).Debug("Log entry enriched with Kubernetes metadata")
		} else {
			c.logger.WithField("path", filePath).Debug("No Kubernetes metadata found for file")
		}
	} else {
		c.logger.WithField("path", filePath).Debug("Kubernetes client not available, skipping metadata enrichment")
	}

	return entry
}

// extractSource derives a clean source identifier from the file path
func (c *Collector) extractSource(filePath string) string {
	// Extract meaningful source from file path
	// e.g., /var/log/pods/default_nginx-pod_123/nginx/0.log -> nginx
	
	fileName := filepath.Base(filePath)
	dir := filepath.Dir(filePath)
	
	// For Kubernetes pod logs, try to extract service name from path
	pathParts := strings.Split(dir, string(filepath.Separator))
	for i, part := range pathParts {
		if part == "pods" && i+1 < len(pathParts) {
			// Extract pod info from path like: default_nginx-pod_123
			podInfo := pathParts[i+1]
			parts := strings.Split(podInfo, "_")
			if len(parts) >= 2 {
				// Use the pod name without the hash
				podName := parts[1]
				// Remove hash suffix if present
				if idx := strings.LastIndex(podName, "-"); idx > 0 {
					return podName[:idx]
				}
				return podName
			}
		}
	}
	
	// Fallback: use filename without extension
	if idx := strings.LastIndex(fileName, "."); idx > 0 {
		return fileName[:idx]
	}
	
	return fileName
}

// extractLogLevel attempts to extract log level from unstructured log line
func (c *Collector) extractLogLevel(line string) string {
	line = strings.ToUpper(line)
	levels := []string{"FATAL", "ERROR", "WARN", "WARNING", "INFO", "DEBUG", "TRACE"}

	for _, level := range levels {
		if strings.Contains(line, level) {
			return level
		}
	}

	return "INFO" // Default level
}

// shouldCollectLevel determines if a log level should be collected
func (c *Collector) shouldCollectLevel(level string) bool {
	if len(c.config.LogLevels) == 0 {
		return true // Collect all if no filter specified
	}

	for _, configLevel := range c.config.LogLevels {
		if strings.EqualFold(level, configLevel) {
			return true
		}
	}

	return false
}

// processBuffer processes buffered log entries
func (c *Collector) processBuffer(ctx context.Context) {
	ticker := time.NewTicker(c.config.FlushInterval)
	defer ticker.Stop()

	batch := make([]*models.LogEntry, 0, c.config.BufferSize)

	for {
		select {
		case <-ctx.Done():
			return
		case entry := <-c.buffer:
			batch = append(batch, entry)
			if len(batch) >= c.config.BufferSize {
				c.sendBatch(batch)
				batch = batch[:0]
			}
		case <-ticker.C:
			if len(batch) > 0 {
				c.sendBatch(batch)
				batch = batch[:0]
			}
		}
	}
}

// sendBatch sends a batch of log entries to the forwarder
func (c *Collector) sendBatch(batch []*models.LogEntry) {
	if len(batch) == 0 {
		c.logger.Debug("Empty batch, nothing to send")
		return
	}

	c.logger.WithField("batch_size", len(batch)).Debug("Preparing to send batch")

	// Split into smaller batches if necessary
	maxBatchSize := c.config.MaxBatchSize
	if maxBatchSize <= 0 {
		maxBatchSize = len(batch) // Send all if not configured
	}
	c.logger.WithFields(logrus.Fields{
		"total_entries": len(batch),
		"max_batch_size": maxBatchSize,
	}).Debug("Batch size configuration")

	for i := 0; i < len(batch); i += maxBatchSize {
		end := i + maxBatchSize
		if end > len(batch) {
			end = len(batch)
		}

		subBatch := batch[i:end]
		c.logger.WithFields(logrus.Fields{
			"sub_batch_size": len(subBatch),
			"batch_index": i,
			"forwarder_url": c.config.ForwarderURL,
		}).Debug("Forwarding sub-batch")
		if err := c.forwarder.Forward(subBatch); err != nil {
			c.logger.WithError(err).WithFields(logrus.Fields{
				"batch_size":    len(subBatch),
				"total_entries": len(batch),
				"forwarder_url": c.config.ForwarderURL,
			}).Error("Failed to forward log batch")
		} else {
			c.logger.WithFields(logrus.Fields{
				"sub_batch_size": len(subBatch),
				"forwarder_url": c.config.ForwarderURL,
			}).Debug("Sub-batch forwarded successfully")
		}
	}
}

// flushBuffer flushes any remaining entries in the buffer
func (c *Collector) flushBuffer() {
	var batch []*models.LogEntry

	for {
		select {
		case entry := <-c.buffer:
			batch = append(batch, entry)
		default:
			if len(batch) > 0 {
				c.sendBatch(batch)
			}
			return
		}
	}
}

// watchFiles monitors for new log files
func (c *Collector) watchFiles(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		case event, ok := <-c.watcher.Events:
			if !ok {
				return
			}

			if event.Op&fsnotify.Create == fsnotify.Create {
				// Check if new file matches our patterns
				for _, pattern := range c.config.LogPaths {
					if matched, _ := filepath.Match(filepath.Base(pattern), filepath.Base(event.Name)); matched {
						if err := c.startTailing(event.Name); err != nil {
							c.logger.WithError(err).WithField("path", event.Name).Error("Failed to start tailing new file")
						}
					}
				}
			}

			if event.Op&fsnotify.Remove == fsnotify.Remove {
				// File was deleted, clean up if we're tailing it
				c.mu.RLock()
				_, exists := c.tailFiles[event.Name]
				c.mu.RUnlock()
				if exists {
					c.logger.WithField("path", event.Name).Info("File deleted, cleaning up tail")
					c.cleanupTailFile(event.Name)
				}
			}

		case err, ok := <-c.watcher.Errors:
			if !ok {
				return
			}
			c.logger.WithError(err).Error("File watcher error")
		}
	}
}

// cleanupTailFile removes a tail file from tracking and closes the file handle
func (c *Collector) cleanupTailFile(path string) {
	c.mu.Lock()
	defer c.mu.Unlock()

	tf, exists := c.tailFiles[path]
	if !exists {
		return
	}

	if tf.file != nil {
		if err := tf.file.Close(); err != nil {
			c.logger.WithError(err).WithField("path", path).Error("Error closing deleted file")
		}
	}

	delete(c.tailFiles, path)
	c.logger.WithField("path", path).Debug("Cleaned up tail file")
}
