# TiDB Vector Document Processing System

A clean and elegant web interface for managing and processing document vectorization and storage in TiDB Vector database.

## Features

- Database connection testing and management
- Table creation, viewing, and deletion
- Document uploading and processing (supports local file uploads or specifying server directories)
- Vector retrieval testing
- Support for OpenAI and Google Embeddings API

## Installation Dependencies

Ensure the following Python libraries are installed:

```bash
pip install flask langchain langchain-openai langchain-google-genai langchain-community sqlalchemy pymysql werkzeug
```

## Usage

1. Start the application from the command line:

```bash
# Change to the web_ui directory
cd faq-mcp/src/rag/web_ui

# Start the service (default address: http://127.0.0.1:5000)
python run.py

# Optional parameters
python run.py --host 0.0.0.0 --port 8080 --debug
```

2. Access the application in your browser (default address: http://127.0.0.1:5000)

## System Workflow

1. **Database Connection**
   - Enter the TiDB connection string (e.g.: `mysql+pymysql://username:password@host:port/dbname`)
   - Click "Test Connection" to confirm the connection is working

2. **Table Management**
   - Click "List Tables" to view existing tables
   - You can delete unwanted tables

3. **Document Processing**
   - Enter a new table name
   - Select API type (OpenAI or Google) and enter the API key
   - Choose document source (upload files or specify server directory)
   - Click "Process Documents" to start processing

4. **Retrieval Testing**
   - Enter table name, query content, and parameters
   - Click "Execute Query" to test vector retrieval effectiveness

## Important Notes

- API keys are temporarily stored in server environment variables but are not persistently saved
- Uploaded files are saved in a temporary directory and will be deleted after application restart
- Ensure that the TiDB database has vector search capabilities enabled
- Currently supported file formats: Markdown (.md)

## Technical Architecture

- Frontend: HTML, CSS, JavaScript, Bootstrap 5
- Backend: Flask (Python)
- Vector Processing: LangChain, OpenAI/Google Embeddings
- Database: TiDB Serverless Cluster (TiDB Vector Search)