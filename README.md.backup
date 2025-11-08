# Azure Data Services Function App

Azure Function App providing unified REST API access to Azure Cosmos DB, Azure Blob Storage, and Azure AI Search with hybrid vector search capabilities.

## Features

- **Cosmos DB Operations**: Query, upsert, batch upsert, and batch delete documents
- **Hybrid Vector Search**: Combine vector embeddings with full-text search using RRF
- **Blob Storage**: Read and write operations with metadata support
- **AI Search Integration**: Hybrid queries with text and vector fields
- **Content Extraction**: Document and image analysis using Azure Content Understanding
- **Parallel Execution**: Batch operations execute concurrently using async/await
- **API Key Authentication**: Secure endpoints with X-API-Key header (query param fallback)
- **Structured Logging**: Request ID tracking and performance metrics
- **SQL Injection Protection**: Read-only query validation for Cosmos DB
- **Retry Logic**: Automatic exponential backoff for Cosmos DB 429 rate limits
- **Async Polling**: Long-running operations with configurable timeout and interval

## Endpoints

All endpoints require authentication via `X-API-Key` header (or `api_key` query parameter).

### Cosmos DB Operations

#### `POST /api/query_cosmosdb`
Execute read-only SQL query (SELECT/WITH only - write operations blocked).

**Query Parameters**: `cosmos_endpoint`, `cosmos_database`, `cosmos_container`

**Request Body** (raw SQL):
```sql
SELECT * FROM c WHERE c.status = 'active'
```

#### `POST /api/upsert_cosmosdb`
Upsert single document or batch (via `documents` array).

**Query Parameters**: `cosmos_endpoint`, `cosmos_database`, `cosmos_container`

**Single Document**:
```json
{"id": "doc123", "name": "Sample"}
```

**Batch**:
```json
{"documents": [{"id": "doc1", ...}, {"id": "doc2", ...}]}
```

#### `DELETE /api/delete_cosmosdb`
Batch delete documents.

**Query Parameters**: `cosmos_endpoint`, `cosmos_database`, `cosmos_container`

**Request Body**:
```json
{"documents": [{"id": "doc1", "partition": "key1"}, ...]}
```

#### `POST /api/search_cosmosdb`
Hybrid vector + full-text search using RRF.

**Query Parameters**: `cosmos_endpoint`, `cosmos_database`, `cosmos_container`, `openai_endpoint`, `openai_embedding_deployment`

**Headers**: `X-OpenAI-Key` (or `openai_key` param)

**Request Body**:
```json
{
  "search": ["query1", "query2"],
  "entities": ["entity1", "entity2"]
}
```

### Blob Storage Operations

#### `GET /api/get_blob`
Read blob content.

**Query Parameters**: `blob_endpoint`, `blob_container`, `blob_name`

#### `POST /api/save_blob`
Write blob content (overwrites existing).

**Query Parameters**: `blob_endpoint`, `blob_container`, `blob_name`

**Request Body**: Raw content (any format)

#### `DELETE /api/delete_blob`
Batch delete blobs.

**Query Parameters**: `blob_endpoint`

**Request Body** (JSON array or single path):
```json
{"blobs": ["container/blob1", "container/blob2"]}
```

### AI Search Operations

#### `POST /api/query_aisearch`
Hybrid text + vector search using Azure AI Search.

**Query Parameters**: `search_endpoint`, `top` (default: 10), `vector_fields` (comma-separated)

**Headers**: `X-Search-Key` (or `search_api_key` param)

**Request Body**:
```json
{"search": ["query1", "query2"]}
```

### Content Extraction Operations

#### `POST /api/extract_content`
Extract content from documents or images using Azure Content Understanding service. Submits analysis job and polls for results until completion or timeout.

**Query Parameters**: 
- `acu_endpoint`: Azure Content Understanding endpoint URL (required)
- `polling_timeout`: Maximum polling time in seconds (default: 300)
- `polling_interval`: Polling interval in seconds (default: 2)

**Headers**: `X-ACU-Key` (or `acu_key` param)

**Request Body**: Base64-encoded document/image content (text/plain)

**Response**:
```json
{
  "content_markdown": "Extracted text in markdown format",
  "fields": {"field1": "value1", "field2": "value2"},
  "pages": [...],
  "request_id": "abc12345",
  "performance": {
    "submit_ms": 150.23,
    "poll_ms": 2500.45,
    "total_ms": 2650.68,
    "poll_attempts": 5
  }
}
```

**Notes**:
- Request body must contain base64-encoded document/image binary content
- Supports various document formats (PDF, DOCX, etc.) and images (JPG, PNG, etc.)
- Uses async polling with configurable timeout to handle long-running extractions
- Returns 408 if extraction exceeds `polling_timeout`

### Health Check

#### `GET /api/health`
Service health status (tests Cosmos DB and Blob Storage connectivity if configured).

**Response**: `200` (healthy) or `503` (degraded)

## Configuration

### Required Environment Variables

```bash
# Authentication
API_KEY=your-api-key-here
```

### Optional Environment Variables

```bash
# Connection Configuration (for health checks)
COSMOS_ENDPOINT=https://your-cosmos.documents.azure.com:443/
BLOB_ENDPOINT=https://your-storage.blob.core.windows.net

# Performance Tuning
MAX_REQUEST_SIZE_MB=10                 # Default: 10
DEFAULT_TIMEOUT_SECONDS=30             # Default: 30
AISEARCH_TIMEOUT_SECONDS=30            # Default: 30
HEALTH_CHECK_TIMEOUT_SECONDS=5         # Default: 5
COSMOS_RETRY_MAX_ATTEMPTS=3            # Default: 3
COSMOS_RETRY_BASE_DELAY=1.0            # Default: 1.0 seconds
```

### Authentication & Authorization

- **API Key**: All endpoints require `X-API-Key` header (or `api_key` query param)
- **Azure AD**: Uses `DefaultAzureCredential` for Cosmos DB and Blob Storage access
- **Service-Specific Keys**: OpenAI and AI Search require separate API keys per request

### Connection Parameters

Service connection details (endpoints, database names, containers) are provided as **query parameters per request**, not in environment variables. This enables multi-tenant scenarios and dynamic routing.

## Security

- **SQL Injection Protection**: Only SELECT/WITH queries allowed; all write operations blocked
- **Request Size Limits**: Configurable max request size (default 10MB)
- **Rate Limiting**: Automatic retry with exponential backoff for Cosmos DB 429 errors
- **Secure Credentials**: Azure AD authentication; no connection strings in config
- **Client Pooling**: Singleton pattern prevents resource exhaustion

## Local Development

### Prerequisites

- **Python 3.11+**
- **Azure Functions Core Tools** ([Install](https://learn.microsoft.com/azure/azure-functions/functions-run-local))
- **uv** (recommended) or pip

### Setup

```bash
# Install dependencies
uv venv && uv sync
# or: pip install -r requirements.txt

# Configure API key
echo 'API_KEY=your-api-key' > .env

# Start function host
func start
# or: make run
```

### Testing

Use `test.http` (REST Client extension) or curl:

```bash
# Query Cosmos DB
curl -X POST http://localhost:7071/api/query_cosmosdb \
  ?cosmos_endpoint=https://your-cosmos.documents.azure.com:443/ \
  &cosmos_database=db &cosmos_container=container \
  -H "X-API-Key: your-key" \
  -d "SELECT * FROM c"

# Extract content from document
curl -X POST "http://localhost:7071/api/extract_content?acu_endpoint=https://your-acu.cognitiveservices.azure.com/contentunderstanding/analyzers/your-analyzer:analyze?api-version=2025-09-01&polling_timeout=300&polling_interval=2" \
  -H "X-API-Key: your-key" \
  -H "X-ACU-Key: your-acu-key" \
  -H "Content-Type: text/plain" \
  -d "BASE64_ENCODED_DOCUMENT_CONTENT"
```

### Common Commands

```bash
make help          # List all available commands
make lint          # Run ruff linter
make format        # Format code
make run           # Start function host
make check-and-run # Lint then start
```

## Deployment

Deploy using Azure CLI, VS Code Azure Functions extension, or Azure DevOps pipelines. The app uses `DefaultAzureCredential` for Azure service authentication.
