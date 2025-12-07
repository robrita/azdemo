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
{ "id": "doc123", "name": "Sample" }
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
{ "blobs": ["container/blob1", "container/blob2"] }
```

### AI Search Operations

#### `POST /api/query_aisearch`

Hybrid text + vector search using Azure AI Search.

**Query Parameters**: `search_endpoint`, `top` (default: 10), `vector_fields` (comma-separated)

**Headers**: `X-Search-Key` (or `search_api_key` param)

**Request Body**:

```json
{ "search": ["query1", "query2"] }
```

### Content Extraction Operations

#### `POST /api/extract_content`

Extract content from documents or images using Azure Content Understanding service. Submits analysis job and polls for results until completion or timeout. Supports resume mode to poll an existing job.

**Query Parameters**:

- `operation_location`: Optional polling URL from a previous extraction job. When provided, skips job submission and directly polls for results (resume mode)
- `acu_endpoint`: Azure Content Understanding endpoint URL (required if `operation_location` not provided)
- `polling_timeout`: Maximum polling time in seconds (default: 300)
- `polling_interval`: Polling interval in seconds (default: 5)
- `min_chunk_size`: Minimum characters per chunk for unknown file types (default: 10000)
- `timeout`: HTTP request timeout in seconds (default: 30)

**Headers**: `X-ACU-Key` (or `acu_key` param) - required for both new jobs and resume mode

**Request Body** (JSON):

- New job mode: `{"content": "<base64-encoded content>", "content-type": "<optional MIME type>"}`
- Resume mode: Optional `{"content-type": "<MIME type>"}` for file type detection

**Response**:

```json
{
  "markdown": "Extracted text in markdown format",
  "pages": [{ "page_number": 1, "content": "..." }],
  "page_count": 5,
  "file_type": "pdf",
  "fields": { "field1": "value1", "field2": "value2" },
  "entities": ["entity1", "entity2"],
  "request_id": "abc12345",
  "operation_location": "https://...",
  "performance": {
    "submit_ms": 150.23,
    "poll_ms": 2500.45,
    "total_ms": 2650.68,
    "poll_attempts": 5
  }
}
```

**Notes**:

- **New Job Mode**: Requires `acu_endpoint` and base64-encoded content in request body
- **Resume Mode**: Provide `operation_location` to poll an existing job (useful for resuming after timeout)
- Supports various document formats (PDF, DOCX, etc.) and images (JPG, PNG, etc.)
- Uses async polling with configurable timeout to handle long-running extractions
- Returns 408 if extraction exceeds `polling_timeout`
- The `operation_location` in response can be used to resume polling if the request times out

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
MAX_REQUEST_SIZE_MB=100                # Default: 100
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

# Extract content from document (new job)
curl -X POST "http://localhost:7071/api/extract_content?acu_endpoint=https://your-acu.cognitiveservices.azure.com/contentunderstanding/analyzers/your-analyzer:analyze?api-version=2025-09-01&polling_timeout=300&polling_interval=5" \
  -H "X-API-Key: your-key" \
  -H "X-ACU-Key: your-acu-key" \
  -H "Content-Type: application/json" \
  -d '{"content": "BASE64_ENCODED_CONTENT", "content-type": "application/pdf"}'

# Resume polling an existing job
curl -X POST "http://localhost:7071/api/extract_content?operation_location=https://your-acu.cognitiveservices.azure.com/...&polling_timeout=300" \
  -H "X-API-Key: your-key" \
  -H "X-ACU-Key: your-acu-key" \
  -H "Content-Type: application/json" \
  -d '{"content-type": "application/pdf"}'
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
