# Azure AI Search Function App

Azure Function App providing REST API access to Azure AI Search with hybrid vector search capabilities.

## Features

- **AI Search Integration**: Hybrid queries with text and vector fields
- **Parallel Execution**: Batch operations execute concurrently using async/await
- **API Key Authentication**: Secure endpoints with X-API-Key header (query param fallback)
- **Structured Logging**: Request ID tracking and performance metrics

## Endpoints

All endpoints require authentication via `X-API-Key` header (or `api_key` query parameter).

### AI Search Operations

#### `POST /api/query_aisearch`
Hybrid text + vector search using Azure AI Search.

**Query Parameters**: 
- `search_endpoint`: Azure AI Search endpoint URL (required)
- `top`: Number of results to return (default: 10)
- `vector_fields`: Comma-separated list of vector field names (required)

**Headers**: 
- `X-API-Key`: API key for authentication (required)
- `X-Search-Key`: Azure AI Search API key (or use `search_api_key` query param)

**Request Body**:
```json
{
  "search": [
    "query1",
    "query2"
  ]
}
```

**Response**:
```json
{
  "search_queries": ["query1", "query2"],
  "vector_fields": ["vector1", "vector2"],
  "top": 10,
  "results": [...],
  "total_results": 25,
  "unique_results": 20,
  "duplicates_removed": 5,
  "request_id": "abc12345",
  "query_details": [
    {
      "query": "query1",
      "result_count": 12,
      "query_ms": 150.23
    }
  ],
  "failed_queries": [],
  "queries_failed": 0,
  "performance": {
    "total_query_ms": 300.45,
    "total_ms": 320.67,
    "queries_executed": 2,
    "queries_succeeded": 2
  }
}
```

### Health Check

#### `GET /api/health`
Service health status.

**Note**: This endpoint does NOT require authentication for monitoring purposes.

**Response**: 
- `200` (healthy)

```json
{
  "status": "healthy",
  "timestamp": 1234567890.123,
  "request_id": "abc12345",
  "performance": {
    "total_ms": 0.23
  }
}
```

## Configuration

### Required Environment Variables

```bash
# Authentication
API_KEY=your-api-key-here
```

### Optional Environment Variables

```bash
# Performance Tuning
MAX_REQUEST_SIZE_MB=10                 # Default: 10
AISEARCH_TIMEOUT_SECONDS=60            # Default: 60
```

### Authentication & Authorization

- **API Key**: All endpoints require `X-API-Key` header (or `api_key` query param)
- **Service-Specific Keys**: AI Search requires separate API key per request

### Connection Parameters

Service connection details (endpoints, API keys) are provided as **query parameters per request**, not in environment variables. This enables multi-tenant scenarios and dynamic routing.

## Security

- **Request Size Limits**: Configurable max request size (default 10MB)
- **Secure Credentials**: API key authentication

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
# Health check
curl http://localhost:7071/api/health \
  -H "X-API-Key: your-key"

# Query AI Search
curl -X POST "http://localhost:7071/api/query_aisearch?search_endpoint=https://your-search.search.windows.net/indexes/your-index/docs/search?api-version=2025-08-01-preview&top=10&vector_fields=vector1,vector2" \
  -H "X-API-Key: your-key" \
  -H "X-Search-Key: your-search-key" \
  -H "Content-Type: application/json" \
  -d '{"search": ["azure functions best practices"]}'
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

Deploy using Azure CLI, VS Code Azure Functions extension, or Azure DevOps pipelines.
