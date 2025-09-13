package embedding

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/sirupsen/logrus"
)

// EmbeddingRequest represents a request to the embedding service
type EmbeddingRequest struct {
	Model string   `json:"model"`
	Input []string `json:"input"`
}

// EmbeddingResponse represents a response from the embedding service
type EmbeddingResponse struct {
	Data  []EmbeddingData `json:"data"`
	Model string          `json:"model"`
	Usage Usage          `json:"usage,omitempty"`
}

// EmbeddingData represents a single embedding result
type EmbeddingData struct {
	Embedding []float32 `json:"embedding"`
	Index     int       `json:"index"`
	Object    string    `json:"object"`
}

// Usage represents token usage information
type Usage struct {
	PromptTokens int `json:"prompt_tokens"`
	TotalTokens  int `json:"total_tokens"`
}

// Service handles communication with the external embedding service
type Service struct {
	endpoint   string
	model      string
	dimension  int
	client     *http.Client
	logger     *logrus.Logger
}

// NewService creates a new embedding service client
func NewService(endpoint, model string, dimension int) *Service {
	return &Service{
		endpoint:  endpoint,
		model:     model,
		dimension: dimension,
		client: &http.Client{
			Timeout: 30 * time.Second,
		},
		logger: logrus.New(),
	}
}

// GetEmbeddings retrieves embeddings for a batch of text inputs
func (s *Service) GetEmbeddings(ctx context.Context, texts []string) ([][]float32, error) {
	if len(texts) == 0 {
		return nil, fmt.Errorf("no texts provided")
	}

	s.logger.WithField("text_count", len(texts)).Debug("Requesting embeddings")

	request := EmbeddingRequest{
		Model: s.model,
		Input: texts,
	}

	jsonData, err := json.Marshal(request)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, "POST", s.endpoint, bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := s.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("embedding service returned status %d", resp.StatusCode)
	}

	var response EmbeddingResponse
	if err := json.NewDecoder(resp.Body).Decode(&response); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	if len(response.Data) != len(texts) {
		return nil, fmt.Errorf("expected %d embeddings, got %d", len(texts), len(response.Data))
	}

	embeddings := make([][]float32, len(response.Data))
	for i, data := range response.Data {
		if len(data.Embedding) != s.dimension {
			return nil, fmt.Errorf("expected embedding dimension %d, got %d for text %d", s.dimension, len(data.Embedding), i)
		}
		embeddings[i] = data.Embedding
	}

	s.logger.WithFields(logrus.Fields{
		"text_count":    len(texts),
		"embedding_dim": s.dimension,
		"usage":         response.Usage,
	}).Debug("Successfully retrieved embeddings")

	return embeddings, nil
}

// GetEmbedding retrieves embedding for a single text input
func (s *Service) GetEmbedding(ctx context.Context, text string) ([]float32, error) {
	embeddings, err := s.GetEmbeddings(ctx, []string{text})
	if err != nil {
		return nil, err
	}
	return embeddings[0], nil
}

// HealthCheck verifies that the embedding service is available
func (s *Service) HealthCheck(ctx context.Context) error {
	s.logger.Debug("Performing embedding service health check")
	
	// Send a minimal test request
	testTexts := []string{"health check"}
	_, err := s.GetEmbeddings(ctx, testTexts)
	if err != nil {
		return fmt.Errorf("embedding service health check failed: %w", err)
	}
	
	return nil
}

// SetTimeout sets the HTTP client timeout
func (s *Service) SetTimeout(timeout time.Duration) {
	s.client.Timeout = timeout
}

// Interface defines the embedding service contract
type Interface interface {
	GetEmbeddings(ctx context.Context, texts []string) ([][]float32, error)
	GetEmbedding(ctx context.Context, text string) ([]float32, error)
	HealthCheck(ctx context.Context) error
}

// Ensure Service implements Interface
var _ Interface = (*Service)(nil)