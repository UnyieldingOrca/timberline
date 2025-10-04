FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY analyzer/ ./analyzer/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY start-api.sh .

# Expose API port
EXPOSE 8000

# Create non-root user
RUN useradd -m -u 1000 analyzer && \
    chown -R analyzer:analyzer /app
USER analyzer

# Default to running the API (can be overridden)
CMD ["./start-api.sh"]