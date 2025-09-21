package handlers

import (
	"context"

	"github.com/stretchr/testify/mock"
	"github.com/timberline/log-ingestor/internal/models"
)

// MockStreamStorage is a mock implementation of StorageInterface for testing
type MockStreamStorage struct {
	mock.Mock
}

func (m *MockStreamStorage) StoreBatch(ctx context.Context, batch *models.LogBatch) error {
	args := m.Mock.Called(ctx, batch)
	return args.Error(0)
}

func (m *MockStreamStorage) Connect(ctx context.Context) error {
	args := m.Mock.Called(ctx)
	return args.Error(0)
}

func (m *MockStreamStorage) Close() error {
	args := m.Mock.Called()
	return args.Error(0)
}

func (m *MockStreamStorage) CreateCollection(ctx context.Context) error {
	args := m.Mock.Called(ctx)
	return args.Error(0)
}

func (m *MockStreamStorage) HealthCheck(ctx context.Context) error {
	args := m.Mock.Called(ctx)
	return args.Error(0)
}

// Add proxy methods for mock functionality
func (m *MockStreamStorage) On(methodName string, arguments ...interface{}) *mock.Call {
	return m.Mock.On(methodName, arguments...)
}

func (m *MockStreamStorage) AssertExpectations(t mock.TestingT) bool {
	return m.Mock.AssertExpectations(t)
}

func (m *MockStreamStorage) AssertNotCalled(t mock.TestingT, methodName string, arguments ...interface{}) bool {
	return m.Mock.AssertNotCalled(t, methodName, arguments...)
}
