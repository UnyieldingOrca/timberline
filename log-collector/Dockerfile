# Use Go 1.23 Alpine as base image
FROM golang:1.23-alpine AS builder

# Set working directory
WORKDIR /app

# Install git and ca-certificates (needed for go modules)
RUN apk add --no-cache git ca-certificates

# Copy go mod files
COPY go.mod go.sum ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o log-collector ./cmd/main.go

# Final stage
FROM alpine:3.18

# Install ca-certificates for HTTPS requests
RUN apk --no-cache add ca-certificates

# Create non-root user
RUN adduser -D -s /bin/sh collector

# Set working directory
WORKDIR /app

# Copy binary from builder stage
COPY --from=builder /app/log-collector .

# Change ownership
RUN chown collector:collector /app/log-collector

# Switch to non-root user
USER collector

# Expose metrics port
EXPOSE 9090

# Run the application
ENTRYPOINT ["/app/log-collector"]
