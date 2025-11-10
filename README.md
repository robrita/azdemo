# Azure Functions App - AI Search & Signature Comparison

Azure Function App providing REST API access to Azure AI Search with hybrid vector search capabilities and signature verification using computer vision and AI embeddings.

## Features

- **AI Search Integration**: Hybrid queries with text and vector fields
- **Signature Comparison**: Automated signature verification using OpenCV and OpenAI CLIP embeddings
- **Parallel Execution**: Batch operations execute concurrently using async/await
- **Multi-Format Support**: Handles PNG, JPG, JPEG, and PDF files
- **API Key Authentication**: Secure endpoints with X-API-Key header (query param fallback)
- **Structured Logging**: Request ID tracking and performance metrics

## Endpoints

All endpoints require authentication via `X-API-Key` header (or `api_key` query parameter).

### Signature Comparison Operations

#### `POST /api/compare_signatures`
Compare signatures between specimen signatures, valid ID, and selfie with ID using computer vision feature extraction.

**Use Case**: Verify identity documents by comparing signatures from:
1. **Specimen signatures** (3 signatures on ID) - Source of truth
2. **Valid ID signature** - Compare against specimens
3. **Selfie with ID signature** - Compare against specimens

**Headers**: 
- `X-API-Key`: API key for authentication (required)

**Request Body** (multipart/form-data):
- `valid_id`: Image file of valid ID (front) - PNG, JPG, JPEG, or PDF
- `specimen_signatures`: Image file with 3 specimen signatures - PNG, JPG, JPEG, or PDF
- `selfie_with_id`: Selfie photo holding valid ID - PNG, JPG, JPEG, or PDF

**Response**:
```json
{
  "request_id": "abc12345",
  "specimen_signatures_count": 3,
  "valid_id_signatures_count": 1,
  "selfie_signatures_count": 1,
  "specimen_internal_consistency": {
    "similarity_matrix": [
      [1.0, 0.92, 0.89],
      [0.92, 1.0, 0.91],
      [0.89, 0.91, 1.0]
    ],
    "average_similarity": 0.9067,
    "status": "MATCH"
  },
  "specimen_vs_valid_id": {
    "similarities": [0.88, 0.87, 0.86],
    "average_similarity": 0.8700,
    "status": "MATCH"
  },
  "specimen_vs_selfie": {
    "similarities": [0.85, 0.84, 0.83],
    "average_similarity": 0.8400,
    "status": "MATCH"
  },
  "performance": {
    "extraction_ms": 250.12,
    "normalization_ms": 45.23,
    "feature_extraction_ms": 120.45,
    "similarity_ms": 12.34,
    "total_ms": 428.14
  }
}
```

**Similarity Thresholds**:
- **Specimen Internal Consistency**: ≥0.85 = MATCH (all 3 specimen signatures should match)
- **Specimen vs Valid ID**: ≥0.80 = MATCH
- **Specimen vs Selfie**: ≥0.80 = MATCH

**Status Values**:
- `MATCH`: Signatures match (confidence score above threshold)
- `MISMATCH`: Signatures do not match (confidence score below threshold)
- `NO_SIGNATURE_FOUND`: No signature detected in the image

**Important Notes**:
1. The function automatically extracts signatures from images using contour detection
2. All signatures are normalized to 300x150 pixels for consistent comparison
3. Features are extracted using HOG (Histogram of Oriented Gradients) and histogram analysis - **no external API calls required**
4. Cosine similarity is used to calculate confidence scores (0.0 to 1.0)
5. At least 3 specimen signatures must be detected from the specimen_signatures image
6. All processing is done locally using OpenCV - no cloud API dependencies

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

# Local Development
ENABLE_LOCAL=true                      # Default: false (enables local-only features)
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

- **Python 3.10 or 3.11** (Python 3.12+ requires Azure Functions Core Tools v4.0.6464+)
- **Azure Functions Core Tools v4** ([Install/Update](https://learn.microsoft.com/azure/azure-functions/functions-run-local))
- **uv** (recommended) or pip

**Important**: 
- Azure Functions now supports Python 3.10-3.13 (GA), but your Core Tools version determines which Python versions work
- If using Core Tools v4.0.6280 or earlier, use Python 3.11
- For Python 3.12+, update Core Tools to v4.0.6464 or later:
  ```bash
  # Windows (using npm)
  npm install -g azure-functions-core-tools@4 --unsafe-perm true
  
  # Or download latest MSI installer:
  # https://go.microsoft.com/fwlink/?linkid=2174087
  ```

### Setup

```bash
# Create and activate virtual environment
# Using uv (recommended):
uv venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Linux/Mac: source .venv/bin/activate

# Or using standard venv:
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# Linux/Mac: source .venv/bin/activate

# Install dependencies
# Using uv:
uv sync
# Or using pip:
pip install -r requirements.txt

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

# Compare signatures (using multipart form data)
curl -X POST "http://localhost:7071/api/compare_signatures" \
  -H "X-API-Key: your-key" \
  -F "valid_id=@./testdata/valid_id.jpg" \
  -F "specimen_signatures=@./testdata/specimen_signatures.jpg" \
  -F "selfie_with_id=@./testdata/selfie_with_id.jpg"

# Query AI Search
curl -X POST "http://localhost:7071/api/query_aisearch?search_endpoint=https://your-search.search.windows.net/indexes/your-index/docs/search?api-version=2025-08-01-preview&top=10&vector_fields=vector1,vector2" \
  -H "X-API-Key: your-key" \
  -H "X-Search-Key: your-search-key" \
  -H "Content-Type: application/json" \
  -d '{"search": ["azure functions best practices"]}'
```

**Note**: For signature comparison testing, you'll need to prepare test images:
- Create a `testdata/` directory
- Add sample images: `valid_id.jpg`, `specimen_signatures.jpg`, `selfie_with_id.jpg`
- Supported formats: PNG, JPG, JPEG, PDF

### Local Debugging

For local development, you can enable local-only features by setting `ENABLE_LOCAL=true` in your `.env` file. When enabled, extracted signature images are automatically saved to `./tmp/` directory for debugging and verification purposes. 

Each extracted signature is saved with:
- Prefix indicating source image (`valid_id`, `specimen`, `selfie`)
- Request ID for tracking
- Signature index (1, 2, 3)
- Timestamp in milliseconds

Example filenames:
```
./tmp/abc12345_valid_id_sig_1_1699632000123.png
./tmp/abc12345_specimen_sig_1_1699632000123.png
./tmp/abc12345_specimen_sig_2_1699632000123.png
./tmp/abc12345_specimen_sig_3_1699632000123.png
./tmp/abc12345_selfie_sig_1_1699632000123.png
```

**Important**: 
- Local features are disabled by default (`ENABLE_LOCAL=false`)
- This should only be enabled in local development
- Do not enable in Azure Functions production environment to avoid file system operations

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
