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
)

const (
	// Collection schema field names
	FieldID         = "id"
	FieldTimestamp  = "timestamp"
	FieldMessage    = "message"
	FieldSource     = "source"
	FieldMetadata   = "metadata"
	FieldEmbedding  = "embedding"
	
	// Collection settings
	DefaultShards  = int32(1)
	IndexType      = "IVF_FLAT"
	MetricType     = "L2"
	IndexNlist     = 1024
)

type MilvusClient struct {
	client         client.Client
	collection     string
	embeddingDim   int
	embeddingService embedding.Interface
	logger         *logrus.Logger
	connected      bool
}

type StorageInterface interface {
	Connect(ctx context.Context) error
	Close() error
	StoreBatch(ctx context.Context, batch *models.LogBatch) error
	HealthCheck(ctx context.Context) error
	CreateCollection(ctx context.Context) error
}

func NewMilvusClient(address string, embeddingService embedding.Interface, embeddingDim int) *MilvusClient {
	return &MilvusClient{
		collection:       "timberline_logs",
		embeddingDim:     embeddingDim,
		embeddingService: embeddingService,
		logger:           logrus.New(),
		connected:        false,
	}
}

func (m *MilvusClient) Connect(ctx context.Context) error {
	m.logger.Info("Connecting to Milvus")
	
	cfg := &client.Config{
		Address: "milvus:19530", // Default Milvus address
	}
	
	c, err := client.NewClient(ctx, *cfg)
	if err != nil {
		return fmt.Errorf("failed to create Milvus client: %w", err)
	}
	
	m.client = c
	m.connected = true
	
	m.logger.Info("Successfully connected to Milvus")
	return nil
}

func (m *MilvusClient) Close() error {
	m.logger.Info("Closing Milvus connection")
	if m.client != nil {
		err := m.client.Close()
		m.connected = false
		return err
	}
	return nil
}

func (m *MilvusClient) CreateCollection(ctx context.Context) error {
	m.logger.WithField("collection", m.collection).Info("Creating Milvus collection")
	
	if !m.connected {
		return fmt.Errorf("not connected to Milvus")
	}
	
	// Check if collection already exists
	hasCollection, err := m.client.HasCollection(ctx, m.collection)
	if err != nil {
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
	m.logger.Info("Creating embedding vector index")
	
	idx, err := entity.NewIndexIvfFlat(MetricType, IndexNlist)
	if err != nil {
		return fmt.Errorf("failed to create index: %w", err)
	}
	
	err = m.client.CreateIndex(ctx, m.collection, FieldEmbedding, idx, false)
	if err != nil {
		return fmt.Errorf("failed to create embedding index: %w", err)
	}
	
	m.logger.Info("Embedding index created successfully")
	return nil
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
	
	// Prepare data for insertion
	timestampColumn := make([]int64, 0, batch.Size())
	messageColumn := make([]string, 0, batch.Size())
	sourceColumn := make([]string, 0, batch.Size())
	metadataColumn := make([][]byte, 0, batch.Size())
	embeddingColumn := make([][]float32, 0, batch.Size())
	
	for i, log := range batch.Logs {
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
		"processed_count": batch.Size(),
		"insert_result":   result != nil,
	}).Info("Batch stored successfully")
	
	return nil
}

func (m *MilvusClient) HealthCheck(ctx context.Context) error {
	m.logger.Debug("Performing Milvus health check")
	
	if !m.connected {
		return fmt.Errorf("not connected to Milvus")
	}
	
	// Check if client is connected and responsive
	version, err := m.client.GetVersion(ctx)
	if err != nil {
		return fmt.Errorf("failed to get Milvus version: %w", err)
	}
	
	m.logger.WithField("version", version).Debug("Milvus health check passed")
	
	// Check if collection exists and is accessible
	hasCollection, err := m.client.HasCollection(ctx, m.collection)
	if err != nil {
		return fmt.Errorf("failed to check collection: %w", err)
	}
	
	if !hasCollection {
		m.logger.WithField("collection", m.collection).Warn("Collection does not exist")
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