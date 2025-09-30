package storage

import (
	"context"
	"fmt"
	"strconv"
	"strings"

	"github.com/milvus-io/milvus/client/v2/column"
	"github.com/milvus-io/milvus/client/v2/entity"
	"github.com/milvus-io/milvus/client/v2/index"
	"github.com/milvus-io/milvus/client/v2/milvusclient"
	"github.com/sirupsen/logrus"
	"github.com/timberline/log-ingestor/internal/embedding"
	"github.com/timberline/log-ingestor/internal/models"
)

const (
	// Collection schema field names
	FieldID             = "id"
	FieldTimestamp      = "timestamp"
	FieldMessage        = "message"
	FieldSource         = "source"
	FieldMetadata       = "metadata"
	FieldEmbedding      = "embedding"
	FieldDuplicateCount = "duplicate_count"

	// Collection settings
	DefaultShards       = int32(1)
	IndexType           = "HNSW"
	MetricType          = "COSINE"
	IndexM              = 16
	IndexEfConstruction = 200
)

type MilvusClient struct {
	client                     *milvusclient.Client
	collection                 string
	embeddingDim               int
	embeddingService           embedding.Interface
	logger                     *logrus.Logger
	connected                  bool
	similarityThreshold        float32
	minExamplesBeforeExclusion int
}

// SearchResult represents a search result with ID and similarity score
type SearchResult struct {
	ID    int64   // Log entry ID
	Score float32 // Similarity score
}

type StorageInterface interface {
	Connect(ctx context.Context) error
	Close() error
	StoreLog(ctx context.Context, log *models.LogEntry) error
	HealthCheck(ctx context.Context) error
	CreateCollection(ctx context.Context) error
}

func NewMilvusClient(address string, embeddingService embedding.Interface, embeddingDim int, similarityThreshold float32, minExamplesBeforeExclusion int, logger *logrus.Logger) *MilvusClient {
	return &MilvusClient{
		collection:                 "timberline_logs",
		embeddingDim:               embeddingDim,
		embeddingService:           embeddingService,
		logger:                     logger,
		connected:                  false,
		similarityThreshold:        similarityThreshold,
		minExamplesBeforeExclusion: minExamplesBeforeExclusion,
	}
}

func (m *MilvusClient) Connect(ctx context.Context) error {
	m.logger.Info("Connecting to Milvus")

	c, err := milvusclient.New(ctx, &milvusclient.ClientConfig{
		Address: "milvus:19530", // Default Milvus address
	})
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
		err := m.client.Close(context.Background())
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
	hasCollection, err := m.client.HasCollection(ctx, milvusclient.NewHasCollectionOption(m.collection))
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
				Name:     FieldDuplicateCount,
				DataType: entity.FieldTypeInt64,
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
	err = m.client.CreateCollection(ctx, milvusclient.NewCreateCollectionOption(m.collection, schema))
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
	m.logger.Info("Creating HNSW embedding vector index")

	// Create HNSW index for the embedding field
	hnswIndex := index.NewHNSWIndex(entity.MetricType(MetricType), IndexM, IndexEfConstruction)

	// Create index task
	indexTask, err := m.client.CreateIndex(ctx,
		milvusclient.NewCreateIndexOption(m.collection, FieldEmbedding, hnswIndex))
	if err != nil {
		return fmt.Errorf("failed to create index task: %w", err)
	}

	// Wait for index creation to complete
	err = indexTask.Await(ctx)
	if err != nil {
		return fmt.Errorf("index creation task failed: %w", err)
	}

	m.logger.Info("HNSW embedding vector index created successfully")
	return nil
}

// SearchSimilarLogs searches for logs similar to the given embedding
func (m *MilvusClient) SearchSimilarLogs(ctx context.Context, embedding []float32, topK int) ([]SearchResult, error) {
	if !m.connected {
		return nil, fmt.Errorf("not connected to Milvus")
	}

	// Create search option with the new client API
	searchOption := milvusclient.NewSearchOption(
		m.collection,
		topK,
		[]entity.Vector{entity.FloatVector(embedding)},
	).WithOutputFields(FieldID)

	// Perform search
	results, err := m.client.Search(ctx, searchOption)
	if err != nil {
		// Check if error is due to collection not being loaded
		errMsg := err.Error()
		if strings.Contains(errMsg, "collection not loaded") || strings.Contains(errMsg, "CollectionNotLoaded") {
			m.logger.WithField("collection", m.collection).Info("Collection not loaded, loading now")

			// Try to load the collection
			loadTask, loadErr := m.client.LoadCollection(ctx, milvusclient.NewLoadCollectionOption(m.collection))
			if loadErr != nil {
				return nil, fmt.Errorf("failed to load collection: %w", loadErr)
			}
			loadErr = loadTask.Await(ctx)
			if loadErr != nil {
				return nil, fmt.Errorf("collection load task failed: %w", loadErr)
			}

			// Retry the search
			results, err = m.client.Search(ctx, searchOption)
			if err != nil {
				return nil, fmt.Errorf("failed to search similar logs after loading collection: %w", err)
			}
		} else {
			return nil, fmt.Errorf("failed to search similar logs: %w", err)
		}
	}

	if len(results) == 0 {
		return []SearchResult{}, nil
	}

	// Extract IDs and scores from the first result set
	result := results[0]

	// Get the ID column from results
	idColumn := result.GetColumn(FieldID)
	idCol, ok := idColumn.(*column.ColumnInt64)
	if !ok {
		return nil, fmt.Errorf("failed to extract ID column from search results")
	}

	idData := idCol.Data()
	scores := result.Scores
	searchResults := make([]SearchResult, len(idData))

	for i := range searchResults {
		searchResults[i] = SearchResult{
			ID:    idData[i],
			Score: scores[i],
		}
	}

	return searchResults, nil
}

// UpdateDuplicateCount increments the duplicate count for a specific log entry
func (m *MilvusClient) UpdateDuplicateCount(ctx context.Context, logID int64) error {
	if !m.connected {
		return fmt.Errorf("not connected to Milvus")
	}

	m.logger.WithField("log_id", logID).Debug("Updating duplicate count for log entry")

	// First, query the current record to get all its fields
	queryOption := milvusclient.NewQueryOption(m.collection).
		WithFilter(fmt.Sprintf("%s == %d", FieldID, logID)).
		WithOutputFields(FieldTimestamp, FieldMessage, FieldSource, FieldMetadata, FieldDuplicateCount, FieldEmbedding)

	queryResult, err := m.client.Query(ctx, queryOption)
	if err != nil {
		return fmt.Errorf("failed to query existing log entry: %w", err)
	}

	if queryResult.ResultCount == 0 {
		return fmt.Errorf("log entry with ID %d not found", logID)
	}

	// Extract the current data from the result set
	result := queryResult

	// Get current duplicate count
	duplicateCountCol, ok := result.GetColumn(FieldDuplicateCount).(*column.ColumnInt64)
	if !ok {
		return fmt.Errorf("failed to extract duplicate count column")
	}
	currentCount := duplicateCountCol.Data()[0]
	newCount := currentCount + 1

	// Get all other fields for upsert
	timestampCol, ok := result.GetColumn(FieldTimestamp).(*column.ColumnInt64)
	if !ok {
		return fmt.Errorf("failed to extract timestamp column")
	}

	messageCol, ok := result.GetColumn(FieldMessage).(*column.ColumnVarChar)
	if !ok {
		return fmt.Errorf("failed to extract message column")
	}

	sourceCol, ok := result.GetColumn(FieldSource).(*column.ColumnVarChar)
	if !ok {
		return fmt.Errorf("failed to extract source column")
	}

	metadataCol, ok := result.GetColumn(FieldMetadata).(*column.ColumnJSONBytes)
	if !ok {
		return fmt.Errorf("failed to extract metadata column")
	}

	embeddingCol, ok := result.GetColumn(FieldEmbedding).(*column.ColumnFloatVector)
	if !ok {
		return fmt.Errorf("failed to extract embedding column")
	}

	// Convert embedding data to [][]float32
	embeddingData := embeddingCol.Data()
	embeddings := make([][]float32, len(embeddingData))
	for i, vec := range embeddingData {
		embeddings[i] = []float32(vec)
	}

	// Create columns for upsert with updated duplicate count
	upsertColumns := []column.Column{
		column.NewColumnInt64(FieldID, []int64{logID}),
		column.NewColumnInt64(FieldTimestamp, timestampCol.Data()),
		column.NewColumnVarChar(FieldMessage, messageCol.Data()),
		column.NewColumnVarChar(FieldSource, sourceCol.Data()),
		column.NewColumnJSONBytes(FieldMetadata, metadataCol.Data()),
		column.NewColumnInt64(FieldDuplicateCount, []int64{newCount}),
		column.NewColumnFloatVector(FieldEmbedding, m.embeddingDim, embeddings),
	}

	// Perform upsert operation with explicit ID (Milvus will update if ID exists)
	upsertOption := milvusclient.NewColumnBasedInsertOption(m.collection).WithColumns(upsertColumns...)
	upsertResult, err := m.client.Upsert(ctx, upsertOption)
	if err != nil {
		return fmt.Errorf("failed to update log entry: %w", err)
	}

	m.logger.WithFields(logrus.Fields{
		"log_id":       logID,
		"old_count":    currentCount,
		"new_count":    newCount,
		"insert_count": upsertResult.UpsertCount,
	}).Info("Successfully updated duplicate count")

	return nil
}

func (m *MilvusClient) StoreLog(ctx context.Context, log *models.LogEntry) error {
	if log == nil {
		return fmt.Errorf("log cannot be nil")
	}

	if err := log.Validate(); err != nil {
		return fmt.Errorf("log validation failed: %w", err)
	}

	if !m.connected {
		return fmt.Errorf("not connected to Milvus")
	}

	m.logger.WithField("message", log.Message).Debug("Storing log entry to Milvus")

	// Get embedding for the log message
	emb, err := m.embeddingService.GetEmbedding(ctx, log.Message)
	if err != nil {
		return fmt.Errorf("failed to get embedding: %w", err)
	}

	// Initialize duplicate count to 1 (first occurrence)
	log.DuplicateCount = 1

	// Check for similar logs if similarity threshold is enabled (> 0)
	if m.similarityThreshold > 0 {
		// Search for similar logs with a reasonable limit to count them and find the most similar
		searchResults, err := m.SearchSimilarLogs(ctx, emb, 100)
		if err != nil {
			m.logger.WithError(err).Warn("Failed to search for similar logs, proceeding with insertion")
		} else if len(searchResults) > 0 {
			// Count similar logs above threshold and find the most similar
			var mostSimilarLog *SearchResult
			similarCount := 0

			for i := range searchResults {
				if searchResults[i].Score > m.similarityThreshold {
					similarCount++
					if mostSimilarLog == nil || searchResults[i].Score > mostSimilarLog.Score {
						mostSimilarLog = &searchResults[i]
					}
				}
			}

			if mostSimilarLog != nil {
				// Check if we have enough examples stored already
				if similarCount >= m.minExamplesBeforeExclusion {
					// We have enough examples, just increment duplicate count and don't store
					m.logger.WithFields(logrus.Fields{
						"message":       log.Message,
						"similarity":    mostSimilarLog.Score,
						"threshold":     m.similarityThreshold,
						"similar_id":    mostSimilarLog.ID,
						"similar_count": similarCount,
						"min_examples":  m.minExamplesBeforeExclusion,
					}).Debug("Detected duplicate log with sufficient examples, excluding from storage")

					// Update duplicate count for the most similar existing log
					if updateErr := m.UpdateDuplicateCount(ctx, mostSimilarLog.ID); updateErr != nil {
						m.logger.WithError(updateErr).Warn("Failed to update duplicate count")
					}

					m.logger.WithFields(logrus.Fields{
						"message":    log.Message,
						"similar_id": mostSimilarLog.ID,
					}).Info("Log is duplicate with sufficient examples, count updated")
					return nil
				} else {
					// We don't have enough examples yet, store this log as another example
					m.logger.WithFields(logrus.Fields{
						"message":       log.Message,
						"similarity":    mostSimilarLog.Score,
						"threshold":     m.similarityThreshold,
						"similar_count": similarCount,
						"min_examples":  m.minExamplesBeforeExclusion,
					}).Debug("Detected similar log but storing as additional example")
				}
			}
		}
	}

	// Serialize metadata as JSON
	metadataBytes, err := log.MetadataAsJSON()
	if err != nil {
		return fmt.Errorf("failed to serialize metadata: %w", err)
	}

	// Create column data for single record
	columns := []column.Column{
		column.NewColumnInt64(FieldTimestamp, []int64{log.Timestamp}),
		column.NewColumnVarChar(FieldMessage, []string{log.Message}),
		column.NewColumnVarChar(FieldSource, []string{log.Source}),
		column.NewColumnJSONBytes(FieldMetadata, [][]byte{metadataBytes}),
		column.NewColumnInt64(FieldDuplicateCount, []int64{log.DuplicateCount}),
		column.NewColumnFloatVector(FieldEmbedding, m.embeddingDim, [][]float32{emb}),
	}

	// Insert data using the new client API
	insertResult, err := m.client.Insert(ctx, milvusclient.NewColumnBasedInsertOption(m.collection).WithColumns(columns...))
	if err != nil {
		return fmt.Errorf("failed to insert data: %w", err)
	}

	m.logger.WithFields(logrus.Fields{
		"message":      log.Message,
		"insert_count": insertResult.InsertCount,
		"primary_key":  insertResult.IDs.(*column.ColumnInt64).Data()[0],
	}).Info("Log stored successfully")

	return nil
}

func (m *MilvusClient) HealthCheck(ctx context.Context) error {
	m.logger.Debug("Performing Milvus health check")

	if !m.connected {
		return fmt.Errorf("not connected to Milvus")
	}

	// Check if client is connected and responsive by checking collection
	// Note: GetVersion is not available in the new client, so we use HasCollection as a health check

	// Check if collection exists and is accessible
	hasCollection, err := m.client.HasCollection(ctx, milvusclient.NewHasCollectionOption(m.collection))
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

	loadOption := milvusclient.NewLoadCollectionOption(m.collection)
	_, err := m.client.LoadCollection(ctx, loadOption)
	if err != nil {
		return fmt.Errorf("failed to load collection: %w", err)
	}

	m.logger.Info("Collection load request sent successfully")
	return nil
}

// Ensure MilvusClient implements StorageInterface
var _ StorageInterface = (*MilvusClient)(nil)
