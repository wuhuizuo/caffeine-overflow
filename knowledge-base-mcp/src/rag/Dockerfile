# Backend Dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies needed for mysqlclient build and potentially others
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv and dependencies in one step with path export and verification
# 使用 pip 安装 uv
RUN pip install uv


# Copy pyproject.toml first for layer caching
# Correct path relative to the build context (workspace root)
COPY pyproject.toml pyproject.toml
COPY uv.lock uv.lock

# Install dependencies step is now combined above
RUN uv pip install --system .

# Remove curl after use (No longer needed as curl wasn't installed)

# Copy the rest of the backend application code
COPY src/rag/web_app.py .
COPY src/rag/tidb_vector_util.py ./rag/
COPY src/rag/document_loader.py ./rag/

# Set environment variables
ENV FLASK_APP=web_app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000
# Add environment variables needed by the app (e.g., for default connection strings or API keys if not passed at runtime)
# ENV TIDB_VECTOR_CONNECTION_STRING="..."
# ENV OPENAI_API_KEY="..."
# ENV GOOGLE_API_KEY="..."

# Expose the port the app runs on
EXPOSE 5000

# Run the application using Gunicorn
# Gunicorn should be listed as a dependency in pyproject.toml
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "web_app:app"] 