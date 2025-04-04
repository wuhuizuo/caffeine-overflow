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
COPY src/vector_search/app.py vector_search/
COPY src/vector_search/tidb_vector_util.py vector_search/
COPY src/vector_search/document_loader.py vector_search/

# Set environment variables
ENV FLASK_APP=vector_search/app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5000

# Expose the port the app runs on
EXPOSE 5000

# Run the application using Gunicorn
# Gunicorn should be listed as a dependency in pyproject.toml
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5000", "vector_search.app:app"]
