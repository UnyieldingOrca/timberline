package embedding

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestNewService(t *testing.T) {
	endpoint := "http://test.com/embed"
	model := "test-model"
	dimension := 512

	service := NewService(endpoint, model, dimension)

	assert.Equal(t, endpoint, service.endpoint)
	assert.Equal(t, model, service.model)
	assert.Equal(t, dimension, service.dimension)
	assert.NotNil(t, service.client)
	assert.NotNil(t, service.logger)
}

func TestService_GetEmbeddings_Success(t *testing.T) {
	// Create mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify request
		assert.Equal(t, "POST", r.Method)
		assert.Equal(t, "application/json", r.Header.Get("Content-Type"))

		var req EmbeddingRequest
		err := json.NewDecoder(r.Body).Decode(&req)
		require.NoError(t, err)

		assert.Equal(t, "test-model", req.Model)
		assert.Equal(t, []string{"hello", "world"}, req.Input)

		// Send mock response
		response := EmbeddingResponse{
			Data: []EmbeddingData{
				{
					Embedding: []float32{0.1, 0.2, 0.3},
					Index:     0,
					Object:    "embedding",
				},
				{
					Embedding: []float32{0.4, 0.5, 0.6},
					Index:     1,
					Object:    "embedding",
				},
			},
			Model: "test-model",
			Usage: Usage{
				PromptTokens: 4,
				TotalTokens:  4,
			},
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	service := NewService(server.URL, "test-model", 3)
	embeddings, err := service.GetEmbeddings(context.Background(), []string{"hello", "world"})

	require.NoError(t, err)
	assert.Len(t, embeddings, 2)
	assert.Equal(t, []float32{0.1, 0.2, 0.3}, embeddings[0])
	assert.Equal(t, []float32{0.4, 0.5, 0.6}, embeddings[1])
}

func TestService_GetEmbedding_Success(t *testing.T) {
	// Create mock server
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var req EmbeddingRequest
		_ = json.NewDecoder(r.Body).Decode(&req)

		assert.Equal(t, []string{"single text"}, req.Input)

		response := EmbeddingResponse{
			Data: []EmbeddingData{
				{
					Embedding: []float32{0.1, 0.2},
					Index:     0,
					Object:    "embedding",
				},
			},
			Model: "test-model",
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	service := NewService(server.URL, "test-model", 2)
	embedding, err := service.GetEmbedding(context.Background(), "single text")

	require.NoError(t, err)
	assert.Equal(t, []float32{0.1, 0.2}, embedding)
}

func TestService_GetEmbeddings_EmptyTexts(t *testing.T) {
	service := NewService("http://test.com", "test-model", 768)
	_, err := service.GetEmbeddings(context.Background(), []string{})

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "no texts provided")
}

func TestService_GetEmbeddings_ServerError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer server.Close()

	service := NewService(server.URL, "test-model", 768)
	_, err := service.GetEmbeddings(context.Background(), []string{"test"})

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "embedding service returned status 500")
}

func TestService_GetEmbeddings_WrongDimension(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		response := EmbeddingResponse{
			Data: []EmbeddingData{
				{
					Embedding: []float32{0.1, 0.2}, // Dimension 2, but service expects 3
					Index:     0,
					Object:    "embedding",
				},
			},
			Model: "test-model",
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	service := NewService(server.URL, "test-model", 3) // Expects dimension 3
	_, err := service.GetEmbeddings(context.Background(), []string{"test"})

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "expected embedding dimension 3, got 2")
}

func TestService_GetEmbeddings_MismatchedCount(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		response := EmbeddingResponse{
			Data: []EmbeddingData{
				{
					Embedding: []float32{0.1, 0.2, 0.3},
					Index:     0,
					Object:    "embedding",
				},
				// Missing second embedding for second text
			},
			Model: "test-model",
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	service := NewService(server.URL, "test-model", 3)
	_, err := service.GetEmbeddings(context.Background(), []string{"text1", "text2"})

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "expected 2 embeddings, got 1")
}

func TestService_GetEmbeddings_Timeout(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(100 * time.Millisecond) // Simulate slow response
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	service := NewService(server.URL, "test-model", 768)
	service.SetTimeout(50 * time.Millisecond) // Shorter than server delay

	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()

	_, err := service.GetEmbeddings(ctx, []string{"test"})
	assert.Error(t, err)
}

func TestService_HealthCheck_Success(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		response := EmbeddingResponse{
			Data: []EmbeddingData{
				{
					Embedding: []float32{0.1, 0.2, 0.3},
					Index:     0,
					Object:    "embedding",
				},
			},
			Model: "test-model",
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(response)
	}))
	defer server.Close()

	service := NewService(server.URL, "test-model", 3)
	err := service.HealthCheck(context.Background())

	assert.NoError(t, err)
}

func TestService_HealthCheck_Failure(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer server.Close()

	service := NewService(server.URL, "test-model", 768)
	err := service.HealthCheck(context.Background())

	assert.Error(t, err)
	assert.Contains(t, err.Error(), "embedding service health check failed")
}

func TestService_SetTimeout(t *testing.T) {
	service := NewService("http://test.com", "test-model", 768)
	originalTimeout := service.client.Timeout

	newTimeout := 5 * time.Second
	service.SetTimeout(newTimeout)

	assert.Equal(t, newTimeout, service.client.Timeout)
	assert.NotEqual(t, originalTimeout, service.client.Timeout)
}

func TestService_Interface(t *testing.T) {
	// Verify that Service implements Interface
	var _ Interface = (*Service)(nil)
}