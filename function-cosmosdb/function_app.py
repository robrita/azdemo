import json
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import wraps
from typing import Any

import azure.functions as func
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment variables
load_dotenv()

# Configure structured logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress verbose Azure SDK logging
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
logging.getLogger("azure.cosmos").setLevel(logging.WARNING)
logging.getLogger("azure.identity").setLevel(logging.WARNING)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def require_api_key(func_to_wrap):  # type: ignore[no-untyped-def]
    """
    Decorator to require API key authentication for Azure Functions.
    Checks for 'X-API-Key' header or 'api_key' query parameter.
    """

    @wraps(func_to_wrap)  # type: ignore[arg-type]
    def wrapper(req: func.HttpRequest) -> func.HttpResponse:
        request_id = str(uuid.uuid4())[:8]

        # Get the expected API key from environment
        expected_api_key: str | None = os.getenv("API_KEY")

        if not expected_api_key:
            logger.error(f"[{request_id}] Configuration error: API_KEY not set in environment")
            return func.HttpResponse(
                body=json.dumps({"error": "Server authentication not configured"}),
                mimetype="application/json",
                status_code=500,
            )

        # Check for API key in header
        provided_api_key: str | None = req.headers.get("X-API-Key")  # type: ignore[no-any-return]

        # If not in header, check query parameters
        if not provided_api_key:
            provided_api_key = req.params.get("api_key")  # type: ignore[no-any-return]

        # Validate API key
        if not provided_api_key:
            logger.warning(
                f"[{request_id}] Authentication failed: No API key provided in request (method={req.method}, route={req.route_params})"
            )
            return func.HttpResponse(
                body=json.dumps(
                    {
                        "error": "Authentication required",
                        "message": "Please provide API key in 'X-API-Key' header or 'api_key' query parameter",
                    }
                ),
                mimetype="application/json",
                status_code=401,
            )

        if provided_api_key != expected_api_key:
            logger.warning(f"[{request_id}] Authentication failed: Invalid API key provided")
            return func.HttpResponse(
                body=json.dumps(
                    {
                        "error": "Invalid authentication",
                        "message": "The provided API key is invalid",
                    }
                ),
                mimetype="application/json",
                status_code=403,
            )

        # Authentication successful, call the original function
        logger.info(
            f"[{request_id}] Authentication successful, proceeding to {func_to_wrap.__name__}"
        )  # type: ignore[attr-defined]
        return func_to_wrap(req)  # type: ignore[no-any-return]

    return wrapper  # type: ignore[return-value]


@app.route(route="health")
@require_api_key
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[{request_id}] Health check endpoint invoked")
    return func.HttpResponse(
        json.dumps({"status": "healthy", "timestamp": time.time()}),
        mimetype="application/json",
        status_code=200,
    )


def _execute_search_query(
    search_text: str,
    entities: list[str],
    openai_client: AzureOpenAI,
    container: Any,
    embedding_deployment: str,
    request_id: str,
) -> tuple[str, list[dict[str, Any]], float, float]:
    """
    Execute a single search query with embedding generation and database lookup.
    Returns (search_text, results, embed_time, query_time).
    """
    # Generate embedding
    embed_start = time.time()
    response = openai_client.embeddings.create(input=search_text, model=embedding_deployment)
    embedding = response.data[0].embedding
    embed_time = time.time() - embed_start

    logger.info(
        f"[{request_id}] Embedding for '{search_text[:50]}...' generated (dimensions={len(embedding)}, duration={embed_time:.3f}s)"
    )

    # Build the FullTextContainsAny and FullTextScore clauses with entities
    if entities:
        # Create parameter placeholders for each entity
        entity_params = ", ".join([f"@entity{i}" for i in range(len(entities))])
        fulltext_clause = f"FullTextContainsAny(c.chunkContent, {entity_params})"
        fulltext_score = f"FullTextScore(c.chunkContent, {entity_params})"
    else:
        # Fallback to search parameter if no entities provided
        fulltext_clause = "FullTextContainsAny(c.chunkContent, @search)"
        fulltext_score = "FullTextScore(c.chunkContent, @search)"

    query = f"""
    SELECT TOP @k c.fileName, c.pageLink, c.pageNumber, c.pageContent
    FROM c
    WHERE {fulltext_clause}
    ORDER BY RANK RRF(
        {fulltext_score},
        VectorDistance(c.vector, @embedding),
        @weights
    )
    """

    # Build parameters list
    parameters: list[dict[str, Any]] = [
        {"name": "@k", "value": 10},
        {"name": "@embedding", "value": embedding},
        {"name": "@search", "value": search_text},
        {"name": "@weights", "value": [10, 1]},  # Weights for full-text score and vector distance
    ]

    # Add entity parameters if entities are provided
    if entities:
        for i, entity in enumerate(entities):
            parameters.append({"name": f"@entity{i}", "value": entity})

    # Execute query
    query_start = time.time()
    items = list(
        container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True)
    )
    query_time = time.time() - query_start

    logger.info(
        f"[{request_id}] Query for '{search_text[:50]}...' returned {len(items)} results (duration={query_time:.3f}s)"
    )

    return (search_text, items, embed_time, query_time)


@app.route(route="search_cosmosdb", methods=["POST"])
@require_api_key
def search_cosmosdb(req: func.HttpRequest) -> func.HttpResponse:
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    logger.info(f"[{request_id}] Search request initiated")

    search_queries = None
    try:
        # Initialize Azure OpenAI client
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        if not azure_endpoint or not api_key:
            raise ValueError(
                "Missing required environment variables: AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_API_KEY"
            )

        openai_client = AzureOpenAI(
            azure_endpoint=azure_endpoint, api_key=api_key, api_version="2024-02-01"
        )

        # Initialize Cosmos DB client with Azure AD authentication
        credential = DefaultAzureCredential()
        cosmos_endpoint = os.getenv("COSMOS_DB_ENDPOINT")
        cosmos_db_name = os.getenv("COSMOS_DB_DATABASE_NAME")
        cosmos_container_name = os.getenv("COSMOS_DB_CONTAINER_NAME")
        if not cosmos_endpoint or not cosmos_db_name or not cosmos_container_name:
            raise ValueError(
                "Missing required environment variables: COSMOS_DB_ENDPOINT, COSMOS_DB_DATABASE_NAME, or COSMOS_DB_CONTAINER_NAME"
            )

        cosmos_client = CosmosClient(url=cosmos_endpoint, credential=credential)
        database = cosmos_client.get_database_client(cosmos_db_name)
        container = database.get_container_client(cosmos_container_name)

        req_body = req.get_json()
        search_queries: list[str] | None = req_body.get("search")
        entities: list[str] = req_body.get("entities", [])
    except ValueError as e:
        logger.error(f"[{request_id}] Invalid JSON in request body: {str(e)}")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Invalid request body",
                    "message": "Please provide valid JSON with a 'search' parameter",
                }
            ),
            mimetype="application/json",
            status_code=400,
        )
    except Exception as e:
        logger.error(f"[{request_id}] Failed to initialize clients: {str(e)}")
        return func.HttpResponse(
            json.dumps(
                {"error": "Initialization error", "message": "Failed to initialize Azure services"}
            ),
            mimetype="application/json",
            status_code=500,
        )

    # Validate search parameter - now expecting an array
    if not isinstance(search_queries, list):
        logger.warning(f"[{request_id}] Validation failed: search parameter is not a list/array")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Validation error",
                    "message": "'search' parameter must be an array of strings",
                }
            ),
            mimetype="application/json",
            status_code=400,
        )

    if len(search_queries) == 0:
        logger.warning(f"[{request_id}] Validation failed: search array is empty")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Validation error",
                    "message": "'search' array must contain at least one query",
                }
            ),
            mimetype="application/json",
            status_code=400,
        )

    try:
        embedding_deployment = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
        if not embedding_deployment:
            raise ValueError(
                "Missing required environment variable: AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
            )

        logger.info(f"[{request_id}] Processing {len(search_queries)} search queries in parallel")

        # Execute all searches in parallel using ThreadPoolExecutor
        all_results: list[dict[str, Any]] = []
        total_embed_time = 0.0
        total_query_time = 0.0
        query_details: list[dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=min(len(search_queries), 10)) as executor:
            # Submit all search tasks
            future_to_search = {
                executor.submit(
                    _execute_search_query,
                    search_text,
                    entities,
                    openai_client,
                    container,
                    embedding_deployment,
                    request_id,
                ): search_text
                for search_text in search_queries
            }

            # Collect results as they complete
            for future in as_completed(future_to_search):
                search_text, items, embed_time, query_time = future.result()
                all_results.extend(items)
                total_embed_time += embed_time
                total_query_time += query_time
                query_details.append(
                    {
                        "query": search_text,
                        "result_count": len(items),
                        "embedding_ms": round(embed_time * 1000, 2),
                        "query_ms": round(query_time * 1000, 2),
                    }
                )

        # Remove duplicates based on fileName and pageNumber
        seen: set[tuple[str, str]] = set()
        unique_results: list[dict[str, Any]] = []
        for item in all_results:
            # Create a unique key from fileName and pageNumber
            key = (item.get("fileName", ""), item.get("pageNumber", ""))
            if key not in seen:
                seen.add(key)
                unique_results.append(item)

        total_time = time.time() - start_time

        logger.info(
            f"[{request_id}] Search completed: {len(all_results)} total results, {len(unique_results)} unique results"
        )

        return func.HttpResponse(
            body=json.dumps(
                {
                    "search_queries": search_queries,
                    "entities": entities,
                    "results": unique_results,
                    "total_results": len(all_results),
                    "unique_results": len(unique_results),
                    "duplicates_removed": len(all_results) - len(unique_results),
                    "request_id": request_id,
                    "query_details": query_details,
                    "performance": {
                        "total_embedding_ms": round(total_embed_time * 1000, 2),
                        "total_query_ms": round(total_query_time * 1000, 2),
                        "total_ms": round(total_time * 1000, 2),
                        "queries_executed": len(search_queries),
                    },
                }
            ),
            mimetype="application/json",
            status_code=200,
        )

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] Search operation failed after {total_time:.3f}s: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return func.HttpResponse(
            body=json.dumps(
                {"error": "Search operation failed", "message": str(e), "request_id": request_id}
            ),
            mimetype="application/json",
            status_code=500,
        )
