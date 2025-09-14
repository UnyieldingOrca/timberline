FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY analyzer/ ./analyzer/
COPY config/ ./config/

# Create non-root user
RUN useradd -m -u 1000 analyzer
USER analyzer

CMD ["ai-analyzer", "analyze-daily"]