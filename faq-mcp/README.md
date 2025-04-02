# TiDB Documentation MCP

A Model Control Protocol (MCP) tool for retrieving relevant TiDB documentation. This tool uses TiDB Vector to store document embeddings and provides semantic search functionality to assist with responses.

## Features

- Semantic search for relevant documentation
- TiDB Vector integration for efficient vector storage and retrieval
- Relevance scoring and filtering of search results
- Support for multiple embedding models (OpenAI and Google Gemini)

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package and project manager)
- TiDB database with Vector support enabled
- OpenAI API key or Google API key for embeddings

## Environment Variables

Set the following environment variables:

- `TIDB_VECTOR_CONNECTION_STRING`: Connection string for TiDB (required)
- `OPENAI_API_KEY` or `GOOGLE_API_KEY`: API key for embedding model (at least one required)
- `MCP_PORT`: Port for SSE server mode (optional, default: 8000)

## Installation

This project uses `uv` for package management. If you don't have `uv` installed, you can install it following the [official installation guide](https://github.com/astral-sh/uv?tab=readme-ov-file#installation).

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/faq-mcp.git
   cd faq-mcp
   ```

2. Create virtual environment and install dependencies:
   ```bash
   uv venv
   uv pip sync
   ```

## Usage

1. Prepare your documentation in the `docs` directory (Markdown format is supported)

2. Run the MCP in standard I/O mode:
   ```bash
   uv run src/main.py
   ```

3. For Server-Sent Events (SSE) mode:
   ```bash
   # Run the tool in SSE mode, default port is 8000
   # You can change the port by setting the MCP_PORT environment variable
   uv run src/main.py --sse
   ```

## Cursor IDE Integration

To use this MCP with Cursor IDE:

1. Open Cursor IDE settings
2. Navigate to the MCP section
3. Add a new MCP with the following configuration:
   - Name: TiDB Documentation Assistant
   - Command: `uv run src/main.py`
   - Working Directory: `./faq-mcp`

4. Make sure your environment variables are properly set in your shell or in the MCP configuration

## Available Tools

The MCP provides the following tool:

- `query_docs`: Search documentation for relevant information
  - Parameters:
    - `query`: The question or search query
    - `max_results`: Maximum number of results to return (default: 3)
    - `distance_threshold`: Maximum distance threshold for relevance filtering (default: 0.5)

## License

Apache License 2.0
