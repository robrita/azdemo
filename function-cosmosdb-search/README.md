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

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure settings**:
   Create a `.env` file or update `local.settings.json` with your environment variables.

3. **Run locally**:
   ```bash
   func start
   ```

4. **Test the endpoint**:
   ```bash
   curl -X POST http://localhost:7071/api/search_cosmosdb \
     -H "X-API-Key: your-key" \
     -H "Content-Type: application/json" \
     -d @testdata.json
   ```

## Deployment

Deploy to Azure Functions using Azure CLI or VS Code Azure Functions extension.

## Requirements

- Python 3.11+
- Azure Functions Core Tools
- Azure Cosmos DB with vector search enabled
- Azure OpenAI with embedding model deployment
