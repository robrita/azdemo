# SharePoint Search Function App

Azure Function App that provides semantic search capabilities over SharePoint content stored in Cosmos DB using hybrid search (vector + full-text).

## Features

- **Hybrid Search**: Combines vector embeddings with full-text search using Rank Reciprocal Fusion (RRF)
- **Batch Queries**: Process multiple search queries in parallel for efficiency
- **Entity Filtering**: Filter results by specific entities (e.g., "Cosmos DB", "vector search")
- **Deduplication**: Automatically removes duplicate results across queries
- **API Key Authentication**: Secure endpoints with header or query parameter authentication
- **Structured Logging**: Request ID tracking and performance metrics

## Endpoints

### `POST /api/search_cosmosdb`
Search for content using hybrid vector + full-text search.

**Authentication**: Required (X-API-Key header or api_key query parameter)

**Request Body**:
```json
{
  "search": [
    "How do I configure Cosmos DB?",
    "vector search setup"
  ],
  "entities": ["Cosmos DB", "vector search"]
}
```

**Response**:
```json
{
  "results": [...],
  "total_results": 15,
  "unique_results": 12,
  "duplicates_removed": 3,
  "query_details": [...],
  "performance": {
    "total_embedding_ms": 245.5,
    "total_query_ms": 89.2,
    "total_ms": 456.8
  }
}
```

### `GET /api/health`
Health check endpoint.

**Authentication**: Required

## Environment Variables

```
API_KEY=<your-api-key>
AZURE_OPENAI_ENDPOINT=<your-openai-endpoint>
AZURE_OPENAI_API_KEY=<your-openai-key>
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=<embedding-model-deployment>
COSMOS_DB_ENDPOINT=<cosmos-endpoint>
COSMOS_DB_DATABASE_NAME=<database-name>
COSMOS_DB_CONTAINER_NAME=<container-name>
```

## Local Development

### Prerequisites

**Install uv** (recommended package manager):

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Alternative: via pip
pip install uv
```

**Install Make** (optional but recommended for easier workflows):

```bash
# Windows (using Chocolatey)
choco install make

# Windows (using Scoop)
scoop install make

# macOS (via Xcode Command Line Tools - usually pre-installed)
xcode-select --install

# Linux (usually pre-installed, or via package manager)
# Debian/Ubuntu
sudo apt-get install build-essential
# Fedora/RHEL
sudo dnf install make
```

> **Note**: On Windows, you can also use WSL (Windows Subsystem for Linux) or Git Bash which includes make.

### Setup

1. **Create virtual environment and install dependencies**:
   ```bash
   # Using uv (recommended)
   uv venv
   uv sync

   # Or using traditional pip
   pip install -r requirements.txt
   ```

2. **Activate virtual environment**:
   ```bash
   # Windows (PowerShell)
   .venv\Scripts\Activate.ps1

   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Configure settings**:
   Create a `.env` file or update `local.settings.json` with your environment variables.

4. **Run locally**:
   ```bash
   func start
   ```

5. **Test the endpoint**:
   ```bash
   curl -X POST http://localhost:7071/api/search_cosmosdb \
     -H "X-API-Key: your-key" \
     -H "Content-Type: application/json" \
     -d @testdata.json
   ```

### Development Commands

#### Using Make (Recommended)

The project includes a `Makefile` with common development tasks:

```bash
# Show all available commands
make help

# Install dependencies (auto-detects uv or pip)
make install

# Run linter
make lint

# Format code
make format

# Start Azure Functions host
make run          # or: make start, make func-start

# Lint then start (recommended workflow)
make check-and-run

# Run tests
make test                  # Run all tests
make test-unit            # Unit tests only
make test-integration     # Integration tests only
make test-cov             # Tests with coverage report
make test-fast            # Skip slow tests

# Clean Python cache files
make clean

# Git operations
make push         # Stage, commit, and push (prompts for message)
make revert       # Revert local.settings.json changes
```

#### Manual Commands (Without Make)

```bash
# Install/update dependencies
uv sync

# Add a new dependency
uv add <package-name>

# Add a dev dependency
uv add --dev <package-name>

# Run linting
uv run ruff check .

# Run formatting
uv run ruff format .

# Run tests
uv run pytest

# Start Azure Functions
func start
```

## Deployment

Deploy to Azure Functions using Azure CLI or VS Code Azure Functions extension.

## Requirements

- Python 3.11+
- Azure Functions Core Tools
- Azure Cosmos DB with vector search enabled
- Azure OpenAI with embedding model deployment
