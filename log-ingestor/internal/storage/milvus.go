package storage

import (
	"context"
	"fmt"
	"strconv"
	"time"

	"github.com/milvus-io/milvus-sdk-go/v2/client"
	"github.com/milvus-io/milvus-sdk-go/v2/entity"
	"github.com/sirupsen/logrus"
	"github.com/timberline/log-ingestor/internal/embedding"
	"github.com/timberline/log-ingestor/internal/models"
	"google.golang.org/grpc"
)

const (
	// Collection schema field names
	FieldID        = "id"
	FieldTimestamp = "timestamp"
	FieldMessage   = "message"
	FieldSource    = "source"
	FieldMetadata  = "metadata"
	FieldEmbedding = "embedding"

	// Collection settings
	DefaultShards       = int32(1)
	IndexType           = "HNSW"
	MetricType          = "COSINE"
	IndexM              = 16
	IndexEfConstruction = 200
)

type MilvusClient struct {
	client              client.Client
	collection          string
	address             string
	embeddingDim        int
	embeddingService    embedding.Interface
	logger              *logrus.Logger
	connected           bool
	similarityThreshold float32
}

type StorageInterface interface {
	Connect(ctx context.Context) error
	Close() error
	StoreBatch(ctx context.Context, batch *models.LogBatch) error
	HealthCheck(ctx context.Context) error
	CreateCollection(ctx context.Context) error
}

func NewMilvusClient(address string, embeddingService embedding.Interface, embeddingDim int, similarityThreshold float32) *MilvusClient {
	return &MilvusClient{
		collection:          "timberline_logs",
		embeddingDim:        embeddingDim,
		embeddingService:    embeddingService,
		logger:              logrus.New(),
		connected:           false,
		similarityThreshold: similarityThreshold,
		address:             address, // Store the address for connection
	}
}

func (m *MilvusClient) Connect(ctx context.Context) error {
	m.logger.WithField("address", m.address).Info("Connecting to Milvus")

	// Use the provided address, with fallback to default
	address := m.address
	if address == "" {
		address = "milvus:19530" // Default Milvus address
	}

	cfg := client.Config{
		Address: address,
		// Add connection options for improved reliability
		DialOptions: []grpc.DialOption{
			grpc.WithTimeout(30 * time.Second),
			grpc.WithBlock(),
		},
		// Add retry configuration for rate limiting
		RetryRateLimit: &client.RetryRateLimitOption{
			MaxRetry:   3,
			MaxBackoff: 60 * time.Second,
		},
	}

	c, err := client.NewClient(ctx, cfg)
	if err != nil {
		m.logger.WithError(err).WithField("address", address).Error("Failed to create Milvus client")
		return fmt.Errorf("failed to create Milvus client for address %s: %w", address, err)
	}

	m.client = c
	m.connected = true

	m.logger.WithField("address", address).Info("Successfully connected to Milvus")
	return nil
}

func (m *MilvusClient) Close() error {
	m.logger.Info("Closing Milvus connection")
	if m.client != nil {
		err := m.client.Close()
		m.connected = false
		if err != nil {
			m.logger.WithError(err).Error("Error closing Milvus connection")
			return fmt.Errorf("failed to close Milvus connection: %w", err)
		}
		m.logger.Info("Milvus connection closed successfully")
	}
	return nil
}

func (m *MilvusClient) CreateCollection(ctx context.Context) error {
	m.logger.WithFields(logrus.Fields{
		"collection":    m.collection,
		"embeddingDim": m.embeddingDim,
	}).Info("Creating Milvus collection")

	if !m.connected {
		return fmt.Errorf("not connected to Milvus")
	}

	// Check if collection already exists
	hasCollection, err := m.client.HasCollection(ctx, m.collection)
	if err != nil {
		m.logger.WithError(err).WithField("collection", m.collection).Error("Failed to check collection existence")
		return fmt.Errorf("failed to check collection existence: %w", err)
	}

	if hasCollection {
		m.logger.WithField("collection", m.collection).Info("Collection already exists")
		return nil
	}

	// Define collection schema
	schema := &entity.Schema{
		CollectionName: m.collection,
		Description:    "Timberline log entries with embeddings for semantic search",
		Fields: []*entity.Field{
			{
				Name:       FieldID,
				DataType:   entity.FieldTypeInt64,
				PrimaryKey: true,
				AutoID:     true,
			},
			{
				Name:     FieldTimestamp,
				DataType: entity.FieldTypeInt64,
			},
			{
				Name:     FieldMessage,
				DataType: entity.FieldTypeVarChar,
				TypeParams: map[string]string{
					"max_length": "65535",
				},
			},
			{
				Name:     FieldSource,
				DataType: entity.FieldTypeVarChar,
				TypeParams: map[string]string{
					"max_length": "255",
				},
			},
			{
				Name:     FieldMetadata,
				DataType: entity.FieldTypeJSON,
			},
			{
				Name:     FieldEmbedding,
				DataType: entity.FieldTypeFloatVector,
				TypeParams: map[string]string{
					"dim": strconv.Itoa(m.embeddingDim),
				},
			},
		},
	}

	// Create collection
	err = m.client.CreateCollection(ctx, schema, DefaultShards)
	if err != nil {
		return fmt.Errorf("failed to create collection: %w", err)
	}

	m.logger.WithField("collection", m.collection).Info("Collection created successfully")

	// Create index on embedding field for vector search
	if err := m.createEmbeddingIndex(ctx); err != nil {
		m.logger.WithError(err).Warn("Failed to create embedding index, search performance may be affected")
	}

	return nil
}

func (m *MilvusClient) createEmbeddingIndex(ctx context.Context) error {
	m.logger.Info("Creating HNSW embedding vector index with cosine similarity")

	idx, err := entity.NewIndexHNSW(entity.COSINE, IndexM, IndexEfConstruction)
	if err != nil {
		return fmt.Errorf("failed to create HNSW index: %w", err)
	}

	err = m.client.CreateIndex(ctx, m.collection, FieldEmbedding, idx, false)
	if err != nil {
		return fmt.Errorf("failed to create embedding index: %w", err)
	}

	m.logger.Info("HNSW embedding index with cosine similarity created successfully")
	return nil
}

// SearchSimilarLogs searches for logs similar to the given embedding
func (m *MilvusClient) SearchSimilarLogs(ctx context.Context, embedding []float32, topK int) ([]float32, error) {
	if !m.connected {
		return nil, fmt.Errorf("not connected to Milvus")
	}

	// Create search vector
	searchVectors := []entity.Vector{
		entity.FloatVector(embedding),
	}

	// Set search parameters for HNSW
	sp, _ := entity.NewIndexHNSWSearchParam(64) // ef parameter for search

	// Perform search
	results, err := m.client.Search(
		ctx,
		m.collection,
		[]string{},        // partition names (empty for all partitions)
		"",                // expression filter (empty for all)
		[]string{FieldID}, // output fields
		searchVectors,
		FieldEmbedding, // vector field name
		entity.COSINE,  // metric type
		topK,           // topK results
		sp,             // search parameters
	)

	if err != nil {
		return nil, fmt.Errorf("failed to search similar logs: %w", err)
	}

	if len(results) == 0 {
		return []float32{}, nil
	}

	// Extract distances/scores
	scores := make([]float32, len(results[0].Scores))
	copy(scores, results[0].Scores)

	return scores, nil
}

func (m *MilvusClient) StoreBatch(ctx context.Context, batch *models.LogBatch) error {
	if batch == nil {
		return fmt.Errorf("batch cannot be nil")
	}

	if err := batch.Validate(); err != nil {
		return fmt.Errorf("batch validation failed: %w", err)
	}

	if !m.connected {
		return fmt.Errorf("not connected to Milvus")
	}

	m.logger.WithField("batch_size", batch.Size()).Debug("Storing log batch to Milvus")

	// Extract texts for embedding
	texts := make([]string, 0, batch.Size())
	for _, log := range batch.Logs {
		texts = append(texts, log.Message)
	}

	// Get embeddings for all log messages
	embeddings, err := m.embeddingService.GetEmbeddings(ctx, texts)
	if err != nil {
		return fmt.Errorf("failed to get embeddings: %w", err)
	}

	if len(embeddings) != batch.Size() {
		return fmt.Errorf("embedding count mismatch: expected %d, got %d", batch.Size(), len(embeddings))
	}

	// Filter out duplicate logs based on similarity
	timestampColumn := make([]int64, 0, batch.Size())
	messageColumn := make([]string, 0, batch.Size())
	sourceColumn := make([]string, 0, batch.Size())
	metadataColumn := make([][]byte, 0, batch.Size())
	embeddingColumn := make([][]float32, 0, batch.Size())

	skippedCount := 0

	// For cosine similarity, higher scores mean more similar
	// We want to skip logs that are above the similarity threshold
	cosineThreshold := m.similarityThreshold

	for i, log := range batch.Logs {
		// Check for similar logs if similarity threshold is enabled (> 0)
		if m.similarityThreshold > 0 {
			distances, err := m.SearchSimilarLogs(ctx, embeddings[i], 1)
			if err != nil {
				m.logger.WithError(err).Warn("Failed to search for similar logs, proceeding with insertion")
			} else if len(distances) > 0 && distances[0] > cosineThreshold {
				// Skip this log as it's too similar to an existing one
				// Note: cosine similarity scores are higher for more similar vectors
				skippedCount++
				m.logger.WithFields(logrus.Fields{
					"message":    log.Message,
					"similarity": distances[0],
					"threshold":  cosineThreshold,
				}).Debug("Skipping duplicate log based on cosine similarity")
				continue
			}
		}

		timestampColumn = append(timestampColumn, log.Timestamp)
		messageColumn = append(messageColumn, log.Message)
		sourceColumn = append(sourceColumn, log.Source)

		// Serialize metadata as JSON
		metadataBytes, err := log.MetadataAsJSON()
		if err != nil {
			return fmt.Errorf("failed to serialize metadata for log %d: %w", i, err)
		}
		metadataColumn = append(metadataColumn, metadataBytes)

		embeddingColumn = append(embeddingColumn, embeddings[i])
	}

	// If all logs were filtered out, return early
	if len(timestampColumn) == 0 {
		m.logger.WithFields(logrus.Fields{
			"original_count": batch.Size(),
			"skipped_count":  skippedCount,
		}).Info("All logs skipped due to similarity, no insertion needed")
		return nil
	}

	// Create column data
	columns := []entity.Column{
		entity.NewColumnInt64(FieldTimestamp, timestampColumn),
		entity.NewColumnVarChar(FieldMessage, messageColumn),
		entity.NewColumnVarChar(FieldSource, sourceColumn),
		entity.NewColumnJSONBytes(FieldMetadata, metadataColumn),
		entity.NewColumnFloatVector(FieldEmbedding, m.embeddingDim, embeddingColumn),
	}

	// Insert data
	result, err := m.client.Insert(ctx, m.collection, "", columns...)
	if err != nil {
		return fmt.Errorf("failed to insert batch: %w", err)
	}

	m.logger.WithFields(logrus.Fields{
		"original_count": batch.Size(),
		"inserted_count": len(timestampColumn),
		"skipped_count":  skippedCount,
		"insert_result":  result != nil,
	}).Info("Batch stored successfully")

	return nil
}

func (m *MilvusClient) HealthCheck(ctx context.Context) error {
	m.logger.WithFields(logrus.Fields{
		"collection": m.collection,
		"address":    m.address,
	}).Debug("Performing Milvus health check")

	if !m.connected {
		return fmt.Errorf("not connected to Milvus")
	}

	// Check if client is connected and responsive
	version, err := m.client.GetVersion(ctx)
	if err != nil {
		m.logger.WithError(err).Error("Failed to get Milvus version during health check")
		return fmt.Errorf("failed to get Milvus version: %w", err)
	}

	m.logger.WithField("version", version).Debug("Milvus health check passed")

	// Check if collection exists and is accessible
	hasCollection, err := m.client.HasCollection(ctx, m.collection)
	if err != nil {
		m.logger.WithError(err).WithField("collection", m.collection).Error("Failed to check collection existence during health check")
		return fmt.Errorf("failed to check collection: %w", err)
	}

	if !hasCollection {
		m.logger.WithField("collection", m.collection).Warn("Collection does not exist")
	} else {
		m.logger.WithField("collection", m.collection).Debug("Collection exists and is accessible")
	}

	return nil
}

// LoadCollection ensures the collection is loaded into memory for search operations
func (m *MilvusClient) LoadCollection(ctx context.Context) error {
	if !m.connected {
		return fmt.Errorf("not connected to Milvus")
	}

	m.logger.WithField("collection", m.collection).Info("Loading collection into memory")

	err := m.client.LoadCollection(ctx, m.collection, false)
	if err != nil {
		return fmt.Errorf("failed to load collection: %w", err)
	}

	// Wait for collection to be loaded
	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(100 * time.Millisecond):
			progress, err := m.client.GetLoadingProgress(ctx, m.collection, []string{})
			if err != nil {
				return fmt.Errorf("failed to get loading progress: %w", err)
			}

			if progress == 100 {
				m.logger.Info("Collection loaded successfully")
				return nil
			}

			m.logger.WithField("progress", progress).Debug("Loading collection...")
		}
	}
}

// Ensure MilvusClient implements StorageInterface
var _ StorageInterface = (*MilvusClient)(nil)
