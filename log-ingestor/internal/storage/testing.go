package storage

import (
	"context"

	"github.com/stretchr/testify/mock"
)

// MockEmbeddingService is a mock implementation of the embedding.Interface for testing
type MockEmbeddingService struct {
	mock.Mock
}

func (m *MockEmbeddingService) GetEmbeddings(ctx context.Context, texts []string) ([][]float32, error) {
	args := m.Mock.Called(ctx, texts)
	return args.Get(0).([][]float32), args.Error(1)
}

func (m *MockEmbeddingService) GetEmbedding(ctx context.Context, text string) ([]float32, error) {
	args := m.Mock.Called(ctx, text)
	return args.Get(0).([]float32), args.Error(1)
}

func (m *MockEmbeddingService) HealthCheck(ctx context.Context) error {
	args := m.Mock.Called(ctx)
	return args.Error(0)
}

// Add proxy methods for mock functionality
func (m *MockEmbeddingService) On(methodName string, arguments ...interface{}) *mock.Call {
	return m.Mock.On(methodName, arguments...)
}

func (m *MockEmbeddingService) AssertExpectations(t mock.TestingT) bool {
	return m.Mock.AssertExpectations(t)
}
