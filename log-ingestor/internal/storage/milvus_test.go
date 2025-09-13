package storage

import (
	"context"
	"testing"
	"time"

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

	client := NewMilvusClient(address, mockEmbedding, dimension)

	assert.NotNil(t, client)
	assert.Equal(t, "timberline_logs", client.collection)
	assert.Equal(t, dimension, client.embeddingDim)
	assert.Equal(t, mockEmbedding, client.embeddingService)
	assert.NotNil(t, client.logger)
	assert.False(t, client.connected)
}

func TestMilvusClient_StoreBatch_ValidationErrors(t *testing.T) {
	mockEmbedding := &MockEmbeddingService{}
	client := NewMilvusClient("test:19530", mockEmbedding, 768)
	ctx := context.Background()

	tests := []struct {
		name        string
		batch       *models.LogBatch
		expectError string
	}{
		{
			name:        "nil batch",
			batch:       nil,
			expectError: "batch cannot be nil",
		},
		{
			name: "empty batch",
			batch: &models.LogBatch{
				Logs: []*models.LogEntry{},
			},
			expectError: "batch validation failed",
		},
		{
			name: "invalid log entry - missing message",
			batch: &models.LogBatch{
				Logs: []*models.LogEntry{
					{
						Timestamp: time.Now().UnixMilli(),
						Source:    "test",
						// Missing message
					},
				},
			},
			expectError: "batch validation failed",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := client.StoreBatch(ctx, tt.batch)
			assert.Error(t, err)
			assert.Contains(t, err.Error(), tt.expectError)
		})
	}
}

func TestMilvusClient_StoreBatch_NotConnected(t *testing.T) {
	mockEmbedding := &MockEmbeddingService{}
	client := NewMilvusClient("test:19530", mockEmbedding, 768)
	
	batch := &models.LogBatch{
		Logs: []*models.LogEntry{
			{
				Timestamp: time.Now().UnixMilli(),
				Message:   "test message",
				Source:    "test",
				Metadata:  map[string]interface{}{"level": "INFO"},
			},
		},
	}

	err := client.StoreBatch(context.Background(), batch)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "not connected to Milvus")
}

func TestMilvusClient_StoreBatch_EmbeddingFailure(t *testing.T) {
	mockEmbedding := &MockEmbeddingService{}
	client := NewMilvusClient("test:19530", mockEmbedding, 768)
	client.connected = true // Simulate connection
	
	batch := &models.LogBatch{
		Logs: []*models.LogEntry{
			{
				Timestamp: time.Now().UnixMilli(),
				Message:   "test message",
				Source:    "test",
				Metadata:  map[string]interface{}{"level": "INFO"},
			},
		},
	}

	// Mock embedding service failure
	mockEmbedding.On("GetEmbeddings", mock.Anything, []string{"test message"}).
		Return([][]float32{}, assert.AnError)

	err := client.StoreBatch(context.Background(), batch)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "failed to get embeddings")

	mockEmbedding.AssertExpectations(t)
}

func TestMilvusClient_StoreBatch_EmbeddingCountMismatch(t *testing.T) {
	mockEmbedding := &MockEmbeddingService{}
	client := NewMilvusClient("test:19530", mockEmbedding, 768)
	client.connected = true // Simulate connection
	
	batch := &models.LogBatch{
		Logs: []*models.LogEntry{
			{
				Timestamp: time.Now().UnixMilli(),
				Message:   "test message 1",
				Source:    "test",
				Metadata:  map[string]interface{}{"level": "INFO"},
			},
			{
				Timestamp: time.Now().UnixMilli(),
				Message:   "test message 2",
				Source:    "test",
				Metadata:  map[string]interface{}{"level": "ERROR"},
			},
		},
	}

	// Mock embedding service returning wrong number of embeddings
	mockEmbedding.On("GetEmbeddings", mock.Anything, []string{"test message 1", "test message 2"}).
		Return([][]float32{{0.1, 0.2, 0.3}}, nil) // Only 1 embedding for 2 messages

	err := client.StoreBatch(context.Background(), batch)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "embedding count mismatch")

	mockEmbedding.AssertExpectations(t)
}

func TestMilvusClient_HealthCheck_NotConnected(t *testing.T) {
	mockEmbedding := &MockEmbeddingService{}
	client := NewMilvusClient("test:19530", mockEmbedding, 768)

	err := client.HealthCheck(context.Background())
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "not connected to Milvus")
}

func TestMilvusClient_CreateCollection_NotConnected(t *testing.T) {
	mockEmbedding := &MockEmbeddingService{}
	client := NewMilvusClient("test:19530", mockEmbedding, 768)

	err := client.CreateCollection(context.Background())
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "not connected to Milvus")
}

func TestMilvusClient_LoadCollection_NotConnected(t *testing.T) {
	mockEmbedding := &MockEmbeddingService{}
	client := NewMilvusClient("test:19530", mockEmbedding, 768)

	err := client.LoadCollection(context.Background())
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "not connected to Milvus")
}

func TestMilvusClient_Close(t *testing.T) {
	mockEmbedding := &MockEmbeddingService{}
	client := NewMilvusClient("test:19530", mockEmbedding, 768)

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
	assert.Equal(t, "IVF_FLAT", IndexType)
	assert.Equal(t, "L2", MetricType)
	assert.Equal(t, 1024, IndexNlist)
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

func TestStorageInterface_Implementation(t *testing.T) {
	// Ensure MilvusClient implements StorageInterface
	var _ StorageInterface = (*MilvusClient)(nil)
}

// Integration test helper functions
func createTestBatch(size int) *models.LogBatch {
	logs := make([]*models.LogEntry, size)
	for i := 0; i < size; i++ {
		logs[i] = &models.LogEntry{
			Timestamp: time.Now().UnixMilli(),
			Message:   "test message " + string(rune(i)),
			Source:    "test-source",
			Metadata: map[string]interface{}{
				"level":     "INFO",
				"pod_name":  "test-pod-" + string(rune(i)),
				"namespace": "default",
				"index":     i,
			},
		}
	}
	return &models.LogBatch{Logs: logs}
}

func createMockEmbeddings(count, dimension int) [][]float32 {
	embeddings := make([][]float32, count)
	for i := 0; i < count; i++ {
		embedding := make([]float32, dimension)
		for j := 0; j < dimension; j++ {
			embedding[j] = float32(i)*0.1 + float32(j)*0.01
		}
		embeddings[i] = embedding
	}
	return embeddings
}