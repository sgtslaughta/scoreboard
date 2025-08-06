# Use Python 3.11 slim image as base
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user for security
RUN groupadd -r ctf && useradd -r -g ctf -d /app -s /bin/bash ctf

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for data persistence
RUN mkdir -p /app/data /app/logs && \
    chown -R ctf:ctf /app

# Switch to non-root user
USER ctf

# Create volume mount points
VOLUME ["/app/data", "/app/logs"]

# Expose ports
EXPOSE 8080 8081

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('localhost', 8081)); s.close()" || exit 1

# Default command
CMD ["python", "app.py", "--host", "0.0.0.0", "--socket-port", "8080", "--web-port", "8081", "--db", "/app/data/scoreboard.db", "--config", "/app/data/ctf_config.json"]