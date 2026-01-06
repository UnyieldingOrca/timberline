FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry
RUN poetry config virtualenvs.create false

# Install Python dependencies
COPY pyproject.toml .
COPY poetry.lock .
RUN poetry install --no-root --no-cache

# Copy application code
COPY analyzer/ ./analyzer/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY start_server.py .
COPY start-api.sh .

# Expose API port
EXPOSE 8000

# Create non-root user
RUN useradd -m -u 1000 analyzer && \
    chown -R analyzer:analyzer /app && \
    chmod +x /app/start-api.sh && \
    chmod +x /app/start_server.py
USER analyzer

# Default to running the API (can be overridden)
CMD ["./start-api.sh"]