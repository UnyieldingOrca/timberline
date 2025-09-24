package storage

import (
	"context"
	"testing"
	"time"

	"github.com/sirupsen/logrus"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
	"github.com/timberline/log-ingestor/internal/models"
)

// MockEmbeddingService is a mock implementation of the embedding service
type MockEmbeddingService struct {
	mock.Mock
}

func (m *MockEmbeddingService) GetEmbeddings(ctx context.Context, texts []string) ([][]float32, error) {
	args := m.Called(ctx, texts)
	return args.Get(0).([][]float32), args.Error(1)
}

func (m *MockEmbeddingService) GetEmbedding(ctx context.Context, text string) ([]float32, error) {
	args := m.Called(ctx, text)
	return args.Get(0).([]float32), args.Error(1)
}

func (m *MockEmbeddingService) HealthCheck(ctx context.Context) error {
	args := m.Called(ctx)
	return args.Error(0)
}

func TestNewMilvusClient(t *testing.T) {
	address := "localhost:19530"
	mockEmbedding := &MockEmbeddingService{}
	dimension := 768

	client := NewMilvusClient(address, mockEmbedding, dimension, 0.95, 3, logrus.New())

	assert.NotNil(t, client)
	assert.Equal(t, "timberline_logs", client.collection)
	assert.Equal(t, dimension, client.embeddingDim)
	assert.Equal(t, mockEmbedding, client.embeddingService)
	assert.NotNil(t, client.logger)
	assert.False(t, client.connected)
	assert.Equal(t, float32(0.95), client.similarityThreshold)
	assert.Equal(t, 3, client.minExamplesBeforeExclusion)
}

func TestMilvusClient_StoreLog_ValidationErrors(t *testing.T) {
	mockEmbedding := &MockEmbeddingService{}
	client := NewMilvusClient("test:19530", mockEmbedding, 768, 0.95, 3, logrus.New())
	ctx := context.Background()

	tests := []struct {
		name        string
		log         *models.LogEntry
		expectError string
	}{
		{
			name:        "nil log",
			log:         nil,
			expectError: "log cannot be nil",
		},
		{
			name: "invalid log entry - missing message",
			log: &models.LogEntry{
				Timestamp: time.Now().UnixMilli(),
				Source:    "test",
				// Missing message
			},
			expectError: "log validation failed",
		},
		{
			name: "invalid log entry - missing source",
			log: &models.LogEntry{
				Timestamp: time.Now().UnixMilli(),
				Message:   "test message",
				// Missing source
			},
			expectError: "log validation failed",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := client.StoreLog(ctx, tt.log)
			assert.Error(t, err)
			assert.Contains(t, err.Error(), tt.expectError)
		})
	}
}

func TestMilvusClient_StoreLog_NotConnected(t *testing.T) {
	mockEmbedding := &MockEmbeddingService{}
	client := NewMilvusClient("test:19530", mockEmbedding, 768, 0.95, 3, logrus.New())

	log := &models.LogEntry{
		Timestamp: time.Now().UnixMilli(),
		Message:   "test message",
		Source:    "test",
		Metadata:  map[string]interface{}{"level": "INFO"},
	}

	err := client.StoreLog(context.Background(), log)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "not connected to Milvus")
}

func TestMilvusClient_StoreLog_EmbeddingFailure(t *testing.T) {
	mockEmbedding := &MockEmbeddingService{}
	client := NewMilvusClient("test:19530", mockEmbedding, 768, 0.95, 3, logrus.New())
	client.connected = true // Simulate connection

	log := &models.LogEntry{
		Timestamp: time.Now().UnixMilli(),
		Message:   "test message",
		Source:    "test",
		Metadata:  map[string]interface{}{"level": "INFO"},
	}

	// Mock embedding service failure
	mockEmbedding.On("GetEmbedding", mock.Anything, "test message").
		Return([]float32{}, assert.AnError)

	err := client.StoreLog(context.Background(), log)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to get embedding")

	mockEmbedding.AssertExpectations(t)
}

func TestMilvusClient_HealthCheck_NotConnected(t *testing.T) {
	mockEmbedding := &MockEmbeddingService{}
	client := NewMilvusClient("test:19530", mockEmbedding, 768, 0.95, 3, logrus.New())

	err := client.HealthCheck(context.Background())
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "not connected to Milvus")
}

func TestMilvusClient_CreateCollection_NotConnected(t *testing.T) {
	mockEmbedding := &MockEmbeddingService{}
	client := NewMilvusClient("test:19530", mockEmbedding, 768, 0.95, 3, logrus.New())

	err := client.CreateCollection(context.Background())
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "not connected to Milvus")
}

func TestMilvusClient_LoadCollection_NotConnected(t *testing.T) {
	mockEmbedding := &MockEmbeddingService{}
	client := NewMilvusClient("test:19530", mockEmbedding, 768, 0.95, 3, logrus.New())

	err := client.LoadCollection(context.Background())
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "not connected to Milvus")
}

func TestMilvusClient_Close(t *testing.T) {
	mockEmbedding := &MockEmbeddingService{}
	client := NewMilvusClient("test:19530", mockEmbedding, 768, 0.95, 3, logrus.New())

	// Test closing when client is nil (should not error)
	err := client.Close()
	assert.NoError(t, err)
}

func TestMilvusClient_SchemaConstants(t *testing.T) {
	// Test that schema constants are properly defined
	assert.Equal(t, "id", FieldID)
	assert.Equal(t, "timestamp", FieldTimestamp)
	assert.Equal(t, "message", FieldMessage)
	assert.Equal(t, "source", FieldSource)
	assert.Equal(t, "metadata", FieldMetadata)
	assert.Equal(t, "embedding", FieldEmbedding)

	assert.Equal(t, int32(1), DefaultShards)
	assert.Equal(t, "HNSW", IndexType)
	assert.Equal(t, "COSINE", MetricType)
	assert.Equal(t, 16, IndexM)
	assert.Equal(t, 200, IndexEfConstruction)
}

func TestLogEntry_MetadataAsJSON(t *testing.T) {
	tests := []struct {
		name     string
		entry    *models.LogEntry
		expected string
	}{
		{
			name: "nil metadata",
			entry: &models.LogEntry{
				Timestamp: time.Now().UnixMilli(),
				Message:   "test",
				Source:    "test",
				Metadata:  nil,
			},
			expected: "{}",
		},
		{
			name: "empty metadata",
			entry: &models.LogEntry{
				Timestamp: time.Now().UnixMilli(),
				Message:   "test",
				Source:    "test",
				Metadata:  map[string]interface{}{},
			},
			expected: "{}",
		},
		{
			name: "with metadata",
			entry: &models.LogEntry{
				Timestamp: time.Now().UnixMilli(),
				Message:   "test",
				Source:    "test",
				Metadata: map[string]interface{}{
					"level":     "INFO",
					"pod_name":  "test-pod",
					"namespace": "default",
				},
			},
			expected: `{"level":"INFO","namespace":"default","pod_name":"test-pod"}`,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			jsonBytes, err := tt.entry.MetadataAsJSON()
			require.NoError(t, err)

			jsonString := string(jsonBytes)
			assert.JSONEq(t, tt.expected, jsonString)
		})
	}
}

func TestMilvusClient_DuplicateCountingWorkflow(t *testing.T) {
	mockEmbedding := &MockEmbeddingService{}
	client := NewMilvusClient("test:19530", mockEmbedding, 768, 0.0, 3, logrus.New()) // Disable similarity threshold for this test

	log := &models.LogEntry{
		Timestamp: time.Now().UnixMilli(),
		Message:   "test message",
		Source:    "test",
		Metadata:  map[string]interface{}{"level": "INFO"},
	}

	// Test should fail because client is not connected
	err := client.StoreLog(context.Background(), log)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "not connected to Milvus")
}

func TestSearchResult_Structure(t *testing.T) {
	result := SearchResult{
		ID:    12345,
		Score: 0.95,
	}

	assert.Equal(t, int64(12345), result.ID)
	assert.Equal(t, float32(0.95), result.Score)
}

func TestStorageInterface_Implementation(t *testing.T) {
	// Ensure MilvusClient implements StorageInterface
	var _ StorageInterface = (*MilvusClient)(nil)
}
