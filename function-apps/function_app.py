import asyncio
import json
import logging
import os
import time
import uuid
from collections.abc import Callable
from functools import wraps
from typing import Any, cast

import aiohttp
import azure.functions as func
from azure.cosmos import CosmosClient
from azure.cosmos import exceptions as cosmos_exceptions
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
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

# Configuration constants
MAX_REQUEST_SIZE_MB = int(os.getenv("MAX_REQUEST_SIZE_MB", "10"))
MAX_REQUEST_SIZE_BYTES = MAX_REQUEST_SIZE_MB * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("DEFAULT_TIMEOUT_SECONDS", "30"))
AISEARCH_TIMEOUT_SECONDS = int(os.getenv("AISEARCH_TIMEOUT_SECONDS", "60"))
HEALTH_CHECK_TIMEOUT_SECONDS = int(os.getenv("HEALTH_CHECK_TIMEOUT_SECONDS", "5"))
COSMOS_RETRY_MAX_ATTEMPTS = int(os.getenv("COSMOS_RETRY_MAX_ATTEMPTS", "3"))
COSMOS_RETRY_BASE_DELAY = float(os.getenv("COSMOS_RETRY_BASE_DELAY", "1.0"))
RRF_WEIGHTS = [10, 1]  # Weights for full-text score and vector distance in RRF ranking

# Module-level client cache (singleton pattern)
_cosmos_clients: dict[str, CosmosClient] = {}
_blob_service_clients: dict[str, BlobServiceClient] = {}
_openai_clients: dict[str, AzureOpenAI] = {}
_credential: DefaultAzureCredential = DefaultAzureCredential()


def _get_cosmos_client(endpoint: str) -> CosmosClient:
    """Get or create a cached Cosmos DB client."""
    if endpoint not in _cosmos_clients:
        _cosmos_clients[endpoint] = CosmosClient(url=endpoint, credential=_credential)
        logger.info(f"Created new Cosmos DB client for endpoint: {endpoint[:30]}...")
    return _cosmos_clients[endpoint]


def _get_blob_service_client(account_url: str) -> BlobServiceClient:
    """Get or create a cached Blob Service client."""
    if account_url not in _blob_service_clients:
        _blob_service_clients[account_url] = BlobServiceClient(
            account_url=account_url, credential=_credential
        )
        logger.info(f"Created new Blob Service client for account: {account_url[:30]}...")
    return _blob_service_clients[account_url]


def _get_openai_client(azure_endpoint: str, api_key: str) -> AzureOpenAI:
    """Get or create a cached OpenAI client."""
    client_key = f"{azure_endpoint}:{api_key[:8]}"
    if client_key not in _openai_clients:
        _openai_clients[client_key] = AzureOpenAI(
            azure_endpoint=azure_endpoint, api_key=api_key, api_version="2024-02-01"
        )
        logger.info(f"Created new OpenAI client for endpoint: {azure_endpoint[:30]}...")
    return _openai_clients[client_key]


def _generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())[:8]


def _validate_url_parameter(value: str | None, param_name: str) -> tuple[bool, str | None]:
    """
    Validate URL format for endpoint parameters.

    Args:
        value: The URL value to validate
        param_name: Name of the parameter for error messages

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is None.
    """
    if not value:
        return False, f"Missing required parameter: {param_name}"

    if not value.startswith(("http://", "https://")):
        return False, f"{param_name} must be a valid URL starting with http:// or https://"

    return True, None


def _validate_api_key_and_size(
    req: func.HttpRequest, request_id: str
) -> func.HttpResponse | None:
    """
    Common validation logic for API key and request size.
    Returns HttpResponse with error if validation fails, None if valid.
    """
    # Validate request size
    try:
        headers = cast(dict[str, str], req.headers)
        content_length = int(headers.get("Content-Length", "0"))
        if content_length > MAX_REQUEST_SIZE_BYTES:
            logger.warning(
                f"[{request_id}] Request size {content_length} bytes exceeds limit {MAX_REQUEST_SIZE_BYTES} bytes"
            )
            return func.HttpResponse(
                body=json.dumps(
                    {
                        "error": "Request too large",
                        "message": f"Request size exceeds maximum allowed size of {MAX_REQUEST_SIZE_MB} MB",
                    }
                ),
                mimetype="application/json",
                status_code=413,
            )
    except (ValueError, TypeError):
        pass  # If Content-Length is missing or invalid, proceed anyway

    # Get the expected API key from environment
    expected_api_key: str | None = os.getenv("API_KEY")

    if not expected_api_key:
        logger.error(f"[{request_id}] Configuration error: API_KEY not set in environment")
        return func.HttpResponse(
            body=json.dumps({"error": "Server authentication not configured"}),
            mimetype="application/json",
            status_code=500,
        )

    # Check for API key in header or query parameter
    headers = cast(dict[str, str], req.headers)
    api_key: str | None = headers.get("X-API-Key") or req.params.get("api_key")

    if not api_key:
        logger.warning(f"[{request_id}] Authentication failed: No API key provided")
        return func.HttpResponse(
            body=json.dumps({"error": "Missing API key"}),
            mimetype="application/json",
            status_code=401,
        )

    if api_key != expected_api_key:
        logger.warning(f"[{request_id}] Authentication failed: Invalid API key")
        return func.HttpResponse(
            body=json.dumps({"error": "Invalid API key"}),
            mimetype="application/json",
            status_code=403,
        )

    # Validation passed
    return None


def require_api_key(
    func_to_wrap: Callable[[func.HttpRequest], func.HttpResponse | Any],
) -> Callable[[func.HttpRequest], func.HttpResponse | Any]:
    """
    Decorator to require API key authentication for Azure Functions.
    Checks for 'X-API-Key' header or 'api_key' query parameter.
    Supports both sync and async functions.
    """

    @wraps(func_to_wrap)
    async def async_wrapper(req: func.HttpRequest) -> func.HttpResponse:
        request_id = _generate_request_id()
        error_response = _validate_api_key_and_size(req, request_id)
        if error_response:
            return error_response
        return await func_to_wrap(req)  # type: ignore[misc]

    @wraps(func_to_wrap)
    def sync_wrapper(req: func.HttpRequest) -> func.HttpResponse:
        request_id = _generate_request_id()
        error_response = _validate_api_key_and_size(req, request_id)
        if error_response:
            return error_response
        return func_to_wrap(req)

    # Return async wrapper if function is a coroutine, else return sync wrapper
    return async_wrapper if asyncio.iscoroutinefunction(func_to_wrap) else sync_wrapper


def validate_readonly_query(query: str, request_id: str) -> tuple[bool, str | None]:
    """
    Validate that a SQL query is read-only (SELECT or WITH statements only).
    Prevents SQL injection by blocking DML/DDL operations.

    Args:
        query: The SQL query string to validate
        request_id: Request ID for logging purposes

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is None.
    """
    if not query or not query.strip():
        return False, "Query cannot be empty"

    # Normalize query: remove leading/trailing whitespace and convert to uppercase for checking
    normalized_query = query.strip().upper()

    # Remove leading comments and whitespace
    lines = normalized_query.split("\n")
    first_statement_line = None
    for line in lines:
        stripped = line.strip()
        # Skip empty lines and comments
        if stripped and not stripped.startswith("--") and not stripped.startswith("//"):
            first_statement_line = stripped
            break

    if not first_statement_line:
        return False, "Query contains no valid statements"

    # Allow only SELECT or WITH (Common Table Expressions) statements
    if not (first_statement_line.startswith("SELECT") or first_statement_line.startswith("WITH")):
        logger.warning(
            f"[{request_id}] Query validation failed: Query must start with SELECT or WITH"
        )
        return False, "Query must be a read-only SELECT or WITH statement"

    # Block dangerous keywords that indicate write operations
    dangerous_keywords = [
        "INSERT",
        "UPDATE",
        "DELETE",
        "UPSERT",
        "REPLACE",
        "CREATE",
        "DROP",
        "ALTER",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
        "EXEC",
        "EXECUTE",
    ]

    for keyword in dangerous_keywords:
        # Use word boundaries to avoid false positives (e.g., "DESCRIPTION" contains "SCRIPT")
        # Check for keyword as a standalone word
        if (
            f" {keyword} " in f" {normalized_query} "
            or normalized_query.startswith(f"{keyword} ")
            or normalized_query.endswith(f" {keyword}")
        ):
            logger.warning(
                f"[{request_id}] Query validation failed: Dangerous keyword '{keyword}' detected"
            )
            return False, f"Query contains forbidden operation: {keyword}"

    logger.info(f"[{request_id}] Query validation passed")
    return True, None


async def _retry_cosmos_operation(
    operation: Callable[[], Any],
    request_id: str,
    operation_name: str = "operation",
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """
    Execute a Cosmos DB operation with timeout and exponential backoff retry logic for 429 errors.

    Args:
        operation: The operation to execute
        request_id: Request ID for logging
        operation_name: Name of the operation for logging
        timeout: Timeout in seconds for the operation

    Returns:
        The result of the operation

    Raises:
        asyncio.TimeoutError: If operation exceeds timeout
        The last exception if all retries are exhausted
    """
    last_exception = None
    for attempt in range(COSMOS_RETRY_MAX_ATTEMPTS):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(operation),
                timeout=timeout,
            )
        except cosmos_exceptions.CosmosHttpResponseError as e:
            if e.status_code == 429:
                # Rate limited - retry with exponential backoff
                headers_attr: Any = getattr(e, "headers", {})
                error_headers = cast(dict[str, Any], headers_attr)
                retry_after = float(error_headers.get("x-ms-retry-after-ms", 1000)) / 1000.0
                delay = max(retry_after, COSMOS_RETRY_BASE_DELAY * (2**attempt))
                logger.warning(
                    f"[{request_id}] {operation_name} rate limited (429), "
                    f"retrying in {delay:.2f}s (attempt {attempt + 1}/{COSMOS_RETRY_MAX_ATTEMPTS})"
                )
                await asyncio.sleep(delay)
                last_exception = e
            else:
                # Non-retryable error
                raise
        except Exception:
            # Non-retryable error
            raise

    # All retries exhausted
    if last_exception:
        logger.error(f"[{request_id}] {operation_name} failed after {COSMOS_RETRY_MAX_ATTEMPTS} retries")
        raise last_exception
    raise RuntimeError(f"{operation_name} failed with unknown error")


def get_cosmos_container(req: func.HttpRequest, request_id: str) -> Any | func.HttpResponse:
    """
    Extract Cosmos DB parameters from request and initialize container client with Azure AD authentication.

    Args:
        req: HTTP request object
        request_id: Request ID for logging purposes

    Returns:
        Container client instance if successful, or HttpResponse with error if parameters are missing or initialization fails
    """
    try:
        # Extract and validate Cosmos DB connection details from query parameters
        cosmos_endpoint = req.params.get("cosmos_endpoint")
        cosmos_db_name = req.params.get("cosmos_database")
        cosmos_container_name = req.params.get("cosmos_container")

        if not cosmos_db_name or not cosmos_container_name:
            logger.warning(f"[{request_id}] Missing required Cosmos DB query parameters")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Missing required parameters",
                        "message": "Please provide cosmos_endpoint, cosmos_database, and cosmos_container query parameters",
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Validate cosmos_endpoint URL format
        is_valid, error_message = _validate_url_parameter(cosmos_endpoint, "cosmos_endpoint")
        if not is_valid:
            logger.warning(f"[{request_id}] Invalid cosmos_endpoint: {error_message}")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid parameter",
                        "message": error_message,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Use cached client (cosmos_endpoint is guaranteed to be str after validation)
        cosmos_client = _get_cosmos_client(cast(str, cosmos_endpoint))
        database = cosmos_client.get_database_client(cosmos_db_name)
        container = database.get_container_client(cosmos_container_name)

        logger.info(f"[{request_id}] Cosmos DB container client retrieved")

        return container

    except Exception as e:
        logger.error(f"[{request_id}] Failed to initialize Cosmos DB client: {str(e)}")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Initialization error",
                    "message": "Failed to initialize Cosmos DB client",
                }
            ),
            mimetype="application/json",
            status_code=500,
        )


def get_openai_client(
    req: func.HttpRequest, request_id: str
) -> tuple[AzureOpenAI, str] | func.HttpResponse:
    """
    Extract Azure OpenAI parameters from request and initialize OpenAI client.
    API keys are accepted via X-OpenAI-Key header (preferred) or openai_key query parameter (deprecated).

    Args:
        req: HTTP request object
        request_id: Request ID for logging purposes

    Returns:
        Tuple of (OpenAI client instance, embedding deployment name) if successful,
        or HttpResponse with error if parameters are missing or initialization fails
    """
    try:
        # Extract Azure OpenAI connection details
        # Endpoint from query parameter
        azure_endpoint = req.params.get("openai_endpoint")

        # API key from header (preferred) or query parameter (fallback)
        headers = cast(dict[str, str], req.headers)
        api_key = headers.get("X-OpenAI-Key") or req.params.get("openai_key")

        embedding_deployment = req.params.get("openai_embedding_deployment")

        if not api_key or not embedding_deployment:
            logger.warning(f"[{request_id}] Missing required Azure OpenAI parameters")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Missing required parameters",
                        "message": "Please provide openai_endpoint, X-OpenAI-Key header (or openai_key param), and openai_embedding_deployment parameters",
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Validate azure_endpoint URL format
        is_valid, error_message = _validate_url_parameter(azure_endpoint, "openai_endpoint")
        if not is_valid:
            logger.warning(f"[{request_id}] Invalid openai_endpoint: {error_message}")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid parameter",
                        "message": error_message,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Use cached client (azure_endpoint is guaranteed to be str after validation)
        openai_client = _get_openai_client(cast(str, azure_endpoint), api_key)

        logger.info(f"[{request_id}] Azure OpenAI client retrieved")

        return (openai_client, embedding_deployment)

    except Exception as e:
        logger.error(f"[{request_id}] Failed to initialize Azure OpenAI client: {str(e)}")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Initialization error",
                    "message": "Failed to initialize Azure OpenAI client",
                }
            ),
            mimetype="application/json",
            status_code=500,
        )


def get_aisearch_config(
    req: func.HttpRequest, request_id: str
) -> tuple[str, str, int, list[str]] | func.HttpResponse:
    """
    Extract and validate Azure AI Search configuration from request parameters.

    Args:
        req: HTTP request object
        request_id: Request ID for logging purposes

    Returns:
        Tuple of (search_endpoint, search_api_key, top, vector_fields) if successful,
        or HttpResponse with error if parameters are missing or invalid
    """
    try:
        # Extract Azure AI Search configuration
        search_endpoint = req.params.get("search_endpoint")

        # API key from header (preferred) or query parameter (fallback)
        headers = cast(dict[str, str], req.headers)
        search_api_key = headers.get("X-Search-Key") or req.params.get("search_api_key")

        top_param = req.params.get("top", "10")
        vector_fields_param = req.params.get("vector_fields", "")

        # Validate required parameters
        if not search_api_key:
            logger.warning(f"[{request_id}] Missing required Azure AI Search parameters")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Missing required parameters",
                        "message": "Please provide search_endpoint and X-Search-Key header (or search_api_key param)",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Validate search_endpoint URL format
        is_valid, error_message = _validate_url_parameter(search_endpoint, "search_endpoint")
        if not is_valid:
            logger.warning(f"[{request_id}] Invalid search_endpoint: {error_message}")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid parameter",
                        "message": error_message,
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Parse top parameter
        try:
            top = int(top_param)
            if top <= 0:
                raise ValueError("top must be greater than 0")
        except ValueError as e:
            logger.warning(f"[{request_id}] Invalid top parameter: {top_param}")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid parameter",
                        "message": f"top parameter must be a positive integer: {str(e)}",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Parse vector_fields parameter (comma-separated)
        if not vector_fields_param:
            logger.warning(f"[{request_id}] Missing vector_fields parameter")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Missing required parameters",
                        "message": "Please provide vector_fields query parameter (comma-separated field names)",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        vector_fields = [field.strip() for field in vector_fields_param.split(",") if field.strip()]
        if not vector_fields:
            logger.warning(f"[{request_id}] vector_fields parameter is empty after parsing")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid parameter",
                        "message": "vector_fields must contain at least one field name",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        logger.info(f"[{request_id}] Azure AI Search configuration validated")
        # Type assertion: search_endpoint is guaranteed to be str after validation
        return (cast(str, search_endpoint), search_api_key, top, vector_fields)

    except Exception as e:
        logger.error(f"[{request_id}] Failed to parse Azure AI Search configuration: {str(e)}")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Configuration error",
                    "message": "Failed to parse Azure AI Search request parameters",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )


async def _execute_search_query(
    search_text: str,
    entities: list[str],
    openai_client: AzureOpenAI,
    container: Any,
    embedding_deployment: str,
    request_id: str,
    top: int = 10,
    select_fields: str = "c.fileName, c.pageLink, c.pageNumber, c.pageContent",
) -> tuple[str, list[dict[str, Any]], float, float]:
    """
    Execute a single search query with embedding generation and database lookup.
    Returns (search_text, results, embed_time, query_time).
    """
    # Generate embedding (wrap sync call in async thread)
    embed_start = time.time()
    response = await asyncio.to_thread(
        openai_client.embeddings.create, input=search_text, model=embedding_deployment
    )
    embedding = response.data[0].embedding
    embed_time = time.time() - embed_start

    logger.info(
        f"[{request_id}] Embedding generated (dimensions={len(embedding)}, duration={embed_time:.3f}s)"
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

    # Use Reciprocal Rank Fusion (RRF) to combine full-text search and vector similarity scores
    # RRF provides better ranking than single methods by merging multiple relevance signals
    query = f"""
    SELECT TOP @k {select_fields}
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
        {"name": "@k", "value": top},
        {"name": "@embedding", "value": embedding},
        {"name": "@search", "value": search_text},
        {"name": "@weights", "value": RRF_WEIGHTS},
    ]

    # Add entity parameters if entities are provided
    if entities:
        for i, entity in enumerate(entities):
            parameters.append({"name": f"@entity{i}", "value": entity})

    # Execute query with retry logic
    query_start = time.time()

    def _query_operation() -> list[dict[str, Any]]:
        return list(
            container.query_items(
                query=query, parameters=parameters, enable_cross_partition_query=True
            )
        )

    items = await _retry_cosmos_operation(_query_operation, request_id, "Cosmos DB query")
    query_time = time.time() - query_start

    logger.info(f"[{request_id}] Query returned {len(items)} results (duration={query_time:.3f}s)")

    return (search_text, items, embed_time, query_time)


async def _upsert_document(
    document: dict[str, Any],
    container: Any,
    request_id: str,
) -> tuple[str, bool, dict[str, Any] | None, str | None, float]:
    """
    Upsert a single document to Cosmos DB with retry logic.
    Returns (doc_id, success, upserted_item, error_message, upsert_time).
    """
    upsert_start = time.time()
    doc_id = document.get("id", "unknown")
    try:

        def _upsert_operation() -> dict[str, Any]:
            return container.upsert_item(body=document)

        upserted_item: dict[str, Any] = await _retry_cosmos_operation(
            _upsert_operation, request_id, f"Upsert document id={doc_id}"
        )
        upsert_time = time.time() - upsert_start

        logger.info(f"[{request_id}] Document upserted (id={doc_id}, duration={upsert_time:.3f}s)")
        return (doc_id, True, upserted_item, None, upsert_time)
    except Exception as e:
        upsert_time = time.time() - upsert_start
        error_msg = str(e)
        logger.error(f"[{request_id}] Failed to upsert document (id={doc_id}): {error_msg}")
        return (doc_id, False, None, error_msg, upsert_time)


async def _delete_document(
    doc_id: str,
    partition_key: str,
    container: Any,
    request_id: str,
) -> tuple[str, str, bool, str | None, float]:
    """
    Delete a single document from Cosmos DB with retry logic.
    Returns (doc_id, partition_key, success, error_message, delete_time).
    """
    delete_start = time.time()
    try:

        def _delete_operation() -> None:
            container.delete_item(item=doc_id, partition_key=partition_key)

        await _retry_cosmos_operation(
            _delete_operation, request_id, f"Delete document id={doc_id}"
        )
        delete_time = time.time() - delete_start

        logger.info(
            f"[{request_id}] Document deleted (id={doc_id}, partition={partition_key}, duration={delete_time:.3f}s)"
        )
        return (doc_id, partition_key, True, None, delete_time)
    except Exception as e:
        delete_time = time.time() - delete_start
        error_msg = str(e)
        logger.error(
            f"[{request_id}] Failed to delete document (id={doc_id}, partition={partition_key}): {error_msg}"
        )
        return (doc_id, partition_key, False, error_msg, delete_time)


async def _delete_blob(
    blob_path: str,
    blob_service_client: BlobServiceClient,
    request_id: str,
) -> tuple[str, str, str, bool, str | None, float]:
    """
    Delete a single blob from Azure Blob Storage.
    Returns (blob_path, container_name, blob_name, success, error_message, delete_time).
    """
    delete_start = time.time()

    # Remove leading slash if present
    if blob_path.startswith("/"):
        blob_path = blob_path[1:]

    # Parse container and blob name from path
    path_parts = blob_path.split("/", 1)
    if len(path_parts) < 2:
        delete_time = time.time() - delete_start
        error_msg = "Blob path must be in format: container_name/blob_name"
        logger.warning(f"[{request_id}] Invalid blob path format (length={len(blob_path)})")
        return (blob_path, "", "", False, error_msg, delete_time)

    container_name = path_parts[0]
    blob_name = path_parts[1]

    try:
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        await asyncio.to_thread(blob_client.delete_blob)
        delete_time = time.time() - delete_start
        logger.info(
            f"[{request_id}] Blob deleted (container={container_name}, duration={delete_time:.3f}s)"
        )
        return (blob_path, container_name, blob_name, True, None, delete_time)
    except Exception as e:
        delete_time = time.time() - delete_start
        error_msg = str(e)
        logger.error(f"[{request_id}] Failed to delete blob (container={container_name}): {error_msg}")
        return (blob_path, container_name, blob_name, False, error_msg, delete_time)


async def _execute_aisearch_query(
    search_text: str,
    search_endpoint: str,
    search_api_key: str,
    top: int,
    vector_fields: list[str],
    request_id: str,
) -> tuple[str, list[dict[str, Any]], float]:
    """
    Execute a single Azure AI Search hybrid query using aiohttp.
    Returns (search_text, results, query_time).
    """
    # Build Azure AI Search request payload
    search_payload: dict[str, Any] = {
        "search": search_text,
        "count": True,
        "top": top,
        "vectorQueries": [
            {
                "kind": "text",
                "text": search_text,
                "fields": ", ".join(vector_fields),
            }
        ],
    }

    # Execute Azure AI Search query
    query_start = time.time()
    try:
        timeout = aiohttp.ClientTimeout(total=AISEARCH_TIMEOUT_SECONDS)
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                search_endpoint,
                headers={
                    "Content-Type": "application/json",
                    "api-key": search_api_key,
                },
                json=search_payload,
                timeout=timeout,
            ) as response,
        ):
            response.raise_for_status()
            search_results_raw = await response.json()
            search_results: dict[str, Any] = cast(dict[str, Any], search_results_raw)
            items: list[dict[str, Any]] = cast(
                list[dict[str, Any]], search_results.get("value", [])
            )
            query_time = time.time() - query_start

            logger.info(f"[{request_id}] AI Search query returned {len(items)} results (duration={query_time:.3f}s)")

            return (search_text, items, query_time)
    except aiohttp.ClientError as e:
        query_time = time.time() - query_start
        logger.error(f"[{request_id}] AI Search query failed: {str(e)}")
        raise


@app.route(route="health")
async def health_check(req: func.HttpRequest) -> func.HttpResponse:
    request_id = _generate_request_id()
    logger.info(f"[{request_id}] Health check endpoint invoked")

    health_status: dict[str, Any] = {"status": "healthy", "timestamp": time.time(), "checks": {}}

    # Check Cosmos DB connectivity (if endpoint configured)
    cosmos_endpoint = os.getenv("COSMOS_ENDPOINT")
    if cosmos_endpoint:
        try:
            cosmos_client = _get_cosmos_client(cosmos_endpoint)
            # Quick connectivity test with timeout
            await asyncio.wait_for(
                asyncio.to_thread(list, cosmos_client.list_databases()),
                timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
            )
            health_status["checks"]["cosmos_db"] = "healthy"
        except asyncio.TimeoutError:
            health_status["checks"]["cosmos_db"] = "unhealthy: timeout"
            health_status["status"] = "degraded"
        except Exception as e:
            health_status["checks"]["cosmos_db"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"

    # Check Blob Storage connectivity (if endpoint configured)
    blob_endpoint = os.getenv("BLOB_ENDPOINT")
    if blob_endpoint:
        try:
            blob_client = _get_blob_service_client(blob_endpoint)
            # Quick connectivity test with timeout
            await asyncio.wait_for(
                asyncio.to_thread(list, blob_client.list_containers(max_results=1)),
                timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
            )
            health_status["checks"]["blob_storage"] = "healthy"
        except asyncio.TimeoutError:
            health_status["checks"]["blob_storage"] = "unhealthy: timeout"
            health_status["status"] = "degraded"
        except Exception as e:
            health_status["checks"]["blob_storage"] = f"unhealthy: {str(e)}"
            health_status["status"] = "degraded"

    # Return appropriate status code
    status_code = 200 if health_status["status"] == "healthy" else 503

    return func.HttpResponse(
        json.dumps(health_status),
        mimetype="application/json",
        status_code=status_code,
    )


@app.route(route="query_cosmosdb", methods=["POST"])
@require_api_key
async def query_cosmosdb(req: func.HttpRequest) -> func.HttpResponse:
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] Query request initiated")

    try:
        # Initialize Cosmos DB container client
        container = get_cosmos_container(req, request_id)
        if isinstance(container, func.HttpResponse):
            return container

        # Get query text directly from request body as string
        query_text = req.get_body().decode("utf-8")

    except Exception as e:
        logger.error(f"[{request_id}] Failed to initialize clients or read request body: {str(e)}")
        return func.HttpResponse(
            json.dumps(
                {"error": "Initialization error", "message": "Failed to initialize Azure services", "request_id": request_id}
            ),
            mimetype="application/json",
            status_code=500,
        )

    # Validate query text
    if not query_text or not query_text.strip():
        logger.warning(f"[{request_id}] Validation failed: query text is empty")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Validation error",
                    "message": "Request body must contain a non-empty SQL query string",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )

    # Validate that query is read-only to prevent SQL injection
    is_valid, error_message = validate_readonly_query(query_text, request_id)
    if not is_valid:
        logger.warning(f"[{request_id}] Query validation failed")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Query validation error",
                    "message": error_message,
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )

    try:
        logger.info(f"[{request_id}] Executing query (length={len(query_text)} chars)")

        # Execute query with retry logic
        query_start = time.time()

        def _query_operation() -> list[dict[str, Any]]:
            return list(container.query_items(query=query_text, enable_cross_partition_query=True))

        items = await _retry_cosmos_operation(_query_operation, request_id, "Cosmos DB query")
        query_time = time.time() - query_start

        total_time = time.time() - start_time

        logger.info(
            f"[{request_id}] Query completed: {len(items)} results (duration={query_time:.3f}s)"
        )

        return func.HttpResponse(
            body=json.dumps(
                {
                    "query": query_text,
                    "results": items,
                    "result_count": len(items),
                    "request_id": request_id,
                    "performance": {
                        "query_ms": round(query_time * 1000, 2),
                        "total_ms": round(total_time * 1000, 2),
                    },
                }
            ),
            mimetype="application/json",
            status_code=200,
        )

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] Query operation failed after {total_time:.3f}s: {type(e).__name__}",
            exc_info=True,
        )
        return func.HttpResponse(
            body=json.dumps(
                {"error": "Query operation failed", "message": str(e), "request_id": request_id}
            ),
            mimetype="application/json",
            status_code=500,
        )


@app.route(route="upsert_cosmosdb", methods=["POST"])
@require_api_key
async def upsert_cosmosdb(req: func.HttpRequest) -> func.HttpResponse:
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] Upsert request initiated")

    try:
        # Initialize Cosmos DB container client
        container = get_cosmos_container(req, request_id)
        if isinstance(container, func.HttpResponse):
            return container

        # Get document(s) from request body as JSON
        req_body: dict[str, Any] = req.get_json()

    except ValueError as e:
        logger.error(f"[{request_id}] Invalid JSON in request body: {str(e)}")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Invalid request body",
                    "message": "Please provide valid JSON document(s) to upsert",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )
    except Exception as e:
        logger.error(f"[{request_id}] Failed to initialize clients or read request body: {str(e)}")
        return func.HttpResponse(
            json.dumps(
                {"error": "Initialization error", "message": "Failed to initialize Cosmos DB container", "request_id": request_id}
            ),
            mimetype="application/json",
            status_code=500,
        )

    # Check if this is a batch operation (has 'documents' array) or single document
    documents: list[dict[str, Any]] | None = req_body.get("documents")

    if documents is not None:
        # BATCH OPERATION
        if not documents:
            logger.warning(f"[{request_id}] Validation failed: documents array is empty")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Validation error",
                        "message": "'documents' array must contain at least one document to upsert",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Validate each document has required 'id' field
        for idx, doc in enumerate(documents):
            if not doc or "id" not in doc:
                logger.warning(
                    f"[{request_id}] Validation failed: document at index {idx} is invalid or missing 'id' field"
                )
                return func.HttpResponse(
                    json.dumps(
                        {
                            "error": "Validation error",
                            "message": f"Document at index {idx} must be an object with an 'id' field",
                            "request_id": request_id,
                        }
                    ),
                    mimetype="application/json",
                    status_code=400,
                )

        try:
            logger.info(
                f"[{request_id}] Processing batch upsert for {len(documents)} documents in parallel"
            )

            # Execute all upserts in parallel using asyncio.gather
            successful_upserts: list[dict[str, Any]] = []
            failed_upserts: list[dict[str, Any]] = []
            total_upsert_time = 0.0

            # Create tasks for all upserts
            tasks = [_upsert_document(doc, container, request_id) for doc in documents]

            # Execute all tasks in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for result in results:
                if isinstance(result, Exception):
                    failed_upserts.append(
                        {
                            "id": "unknown",
                            "error": str(result),
                            "upsert_ms": 0.0,
                        }
                    )
                elif isinstance(result, tuple) and len(result) == 5:
                    doc_id, success, upserted_item_result, error_msg, upsert_time = result
                    total_upsert_time += upsert_time

                    if success and upserted_item_result is not None:
                        successful_upserts.append(
                            {
                                "id": doc_id,
                                "document": upserted_item_result,
                                "upsert_ms": round(upsert_time * 1000, 2),
                            }
                        )
                    else:
                        failed_upserts.append(
                            {
                                "id": doc_id,
                                "error": error_msg if error_msg else "Unknown error",
                                "upsert_ms": round(upsert_time * 1000, 2),
                            }
                        )

            total_time = time.time() - start_time

            logger.info(
                f"[{request_id}] Batch upsert completed: {len(successful_upserts)} successful, {len(failed_upserts)} failed"
            )

            return func.HttpResponse(
                body=json.dumps(
                    {
                        "message": "Batch upsert operation completed",
                        "total_documents": len(documents),
                        "successful_upserts": len(successful_upserts),
                        "failed_upserts": len(failed_upserts),
                        "successful": successful_upserts,
                        "failed": failed_upserts,
                        "request_id": request_id,
                        "performance": {
                            "total_upsert_ms": round(total_upsert_time * 1000, 2),
                            "total_ms": round(total_time * 1000, 2),
                        },
                    }
                ),
                mimetype="application/json",
                status_code=200,
            )

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(
                f"[{request_id}] Batch upsert operation failed after {total_time:.3f}s: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Batch upsert operation failed",
                        "message": str(e),
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=500,
            )
    else:
        # SINGLE DOCUMENT OPERATION
        # Validate single document
        if not req_body:
            logger.warning(f"[{request_id}] Validation failed: request body is empty")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Validation error",
                        "message": "Request body must be a valid JSON object or contain a 'documents' array",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Check for required 'id' field (Cosmos DB requires an 'id' for upsert)
        if "id" not in req_body:
            logger.warning(
                f"[{request_id}] Validation failed: document missing required 'id' field"
            )
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Validation error",
                        "message": "Document must contain an 'id' field for upsert operation",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        try:
            logger.info(
                f"[{request_id}] Upserting single document with id: {req_body.get('id', 'unknown')}"
            )

            # Use the shared _upsert_document function
            doc_id, success, upserted_item, error_msg, upsert_time = await _upsert_document(
                req_body, container, request_id
            )

            total_time = time.time() - start_time

            if success and upserted_item is not None:
                return func.HttpResponse(
                    body=json.dumps(
                        {
                            "message": "Document upserted successfully",
                            "document": upserted_item,
                            "request_id": request_id,
                            "performance": {
                                "upsert_ms": round(upsert_time * 1000, 2),
                                "total_ms": round(total_time * 1000, 2),
                            },
                        }
                    ),
                    mimetype="application/json",
                    status_code=200,
                )

            logger.error(
                f"[{request_id}] Upsert operation failed after {total_time:.3f}s: {error_msg}",
                exc_info=True,
            )
            return func.HttpResponse(
                body=json.dumps(
                    {
                        "error": "Upsert operation failed",
                        "message": error_msg,
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=500,
            )

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(
                f"[{request_id}] Upsert operation failed after {total_time:.3f}s: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            return func.HttpResponse(
                body=json.dumps(
                    {
                        "error": "Upsert operation failed",
                        "message": str(e),
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=500,
            )


@app.route(route="search_cosmosdb", methods=["POST"])
@require_api_key
async def search_cosmosdb(req: func.HttpRequest) -> func.HttpResponse:
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] Search request initiated")

    search_queries = None
    try:
        # Initialize Cosmos DB container client
        container = get_cosmos_container(req, request_id)
        if isinstance(container, func.HttpResponse):
            return container

        # Initialize Azure OpenAI client
        openai_result = get_openai_client(req, request_id)
        if isinstance(openai_result, func.HttpResponse):
            return openai_result
        openai_client, embedding_deployment = openai_result

        # Extract query parameters
        top_param = req.params.get("top", "10")
        select_fields_param = req.params.get("select_fields")

        # Validate and parse top parameter
        try:
            top = int(top_param)
            if top <= 0:
                raise ValueError("top must be greater than 0")
        except ValueError as e:
            logger.warning(f"[{request_id}] Invalid top parameter: {top_param}")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid parameter",
                        "message": f"top parameter must be a positive integer: {str(e)}",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Validate and parse select_fields parameter (required)
        if not select_fields_param:
            logger.warning(f"[{request_id}] Missing required select_fields parameter")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Missing required parameters",
                        "message": "Please provide select_fields query parameter (comma-separated field names)",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Parse select_fields and convert to SQL syntax (e.g., "fileName, pageLink" -> "c.fileName, c.pageLink")
        field_names = [field.strip() for field in select_fields_param.split(",") if field.strip()]
        if not field_names:
            logger.warning(f"[{request_id}] select_fields parameter is empty after parsing")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid parameter",
                        "message": "select_fields must contain at least one field name",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Convert field names to SQL syntax with 'c.' prefix
        select_fields = ", ".join([f"c.{field}" for field in field_names])

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
                    "request_id": request_id,
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
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )

    try:
        logger.info(f"[{request_id}] Processing {len(search_queries)} search queries in parallel")

        # Execute all searches in parallel using asyncio.gather
        all_results: list[dict[str, Any]] = []
        total_embed_time = 0.0
        total_query_time = 0.0
        query_details: list[dict[str, Any]] = []
        failed_queries: list[dict[str, Any]] = []

        # Create tasks for all searches
        tasks = [
            _execute_search_query(
                search_text,
                entities,
                openai_client,
                container,
                embedding_deployment,
                request_id,
                top,
                select_fields,
            )
            for search_text in search_queries
        ]

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_queries.append(
                    {
                        "query": search_queries[i],
                        "error": str(result),
                    }
                )
                logger.error(f"[{request_id}] Search query failed: {search_queries[i]}: {str(result)}")
                continue

            if isinstance(result, tuple) and len(result) == 4:
                search_text, items, embed_time, query_time = result
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
                    "failed_queries": failed_queries,
                    "queries_failed": len(failed_queries),
                    "performance": {
                        "total_embedding_ms": round(total_embed_time * 1000, 2),
                        "total_query_ms": round(total_query_time * 1000, 2),
                        "total_ms": round(total_time * 1000, 2),
                        "queries_executed": len(search_queries),
                        "queries_succeeded": len(query_details),
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


@app.route(route="delete_cosmosdb", methods=["DELETE"])
@require_api_key
async def delete_cosmosdb(req: func.HttpRequest) -> func.HttpResponse:
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] Batch delete request initiated")

    try:
        # Initialize Cosmos DB container client
        container = get_cosmos_container(req, request_id)
        if isinstance(container, func.HttpResponse):
            return container

        # Get documents list from request body as JSON
        req_body: dict[str, Any] = req.get_json()

    except ValueError as e:
        logger.error(f"[{request_id}] Invalid JSON in request body: {str(e)}")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Invalid request body",
                    "message": "Please provide valid JSON with a 'documents' array",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )
    except Exception as e:
        logger.error(f"[{request_id}] Failed to initialize clients or read request body: {str(e)}")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Initialization error",
                    "message": "Failed to initialize Cosmos DB container",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )

    # Validate documents array
    documents: list[dict[str, Any]] | None = req_body.get("documents")
    if not isinstance(documents, list):
        logger.warning(f"[{request_id}] Validation failed: 'documents' is not a list")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Validation error",
                    "message": "'documents' must be an array of objects with 'id' and 'partition' fields",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )

    if len(documents) == 0:
        logger.warning(f"[{request_id}] Validation failed: documents array is empty")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Validation error",
                    "message": "'documents' array must contain at least one document to delete",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )

    # Validate each document has required fields
    for idx, doc in enumerate(documents):
        if not doc or "id" not in doc or "partition" not in doc:
            logger.warning(
                f"[{request_id}] Validation failed: document at index {idx} is invalid or missing required fields"
            )
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Validation error",
                        "message": f"Document at index {idx} must be an object with 'id' and 'partition' fields",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

    try:
        logger.info(
            f"[{request_id}] Processing batch delete for {len(documents)} documents in parallel"
        )

        # Execute all deletions in parallel using asyncio.gather
        successful_deletes: list[dict[str, Any]] = []
        failed_deletes: list[dict[str, Any]] = []
        total_delete_time = 0.0

        # Create tasks for all deletions
        tasks = [
            _delete_document(
                doc["id"],
                doc["partition"],
                container,
                request_id,
            )
            for doc in documents
        ]

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                failed_deletes.append(
                    {
                        "id": "unknown",
                        "partition": "unknown",
                        "error": str(result),
                        "delete_ms": 0.0,
                    }
                )
            elif isinstance(result, tuple) and len(result) == 5:
                doc_id, partition_key, success, error_msg, delete_time = result
                total_delete_time += delete_time

                if success:
                    successful_deletes.append(
                        {
                            "id": doc_id,
                            "partition": partition_key,
                            "delete_ms": round(delete_time * 1000, 2),
                        }
                    )
                else:
                    failed_deletes.append(
                        {
                            "id": doc_id,
                            "partition": partition_key,
                            "error": error_msg,
                            "delete_ms": round(delete_time * 1000, 2),
                        }
                    )

        total_time = time.time() - start_time

        logger.info(
            f"[{request_id}] Batch delete completed: {len(successful_deletes)} successful, {len(failed_deletes)} failed"
        )

        return func.HttpResponse(
            body=json.dumps(
                {
                    "message": "Batch delete operation completed",
                    "total_documents": len(documents),
                    "successful_deletes": len(successful_deletes),
                    "failed_deletes": len(failed_deletes),
                    "successful": successful_deletes,
                    "failed": failed_deletes,
                    "request_id": request_id,
                    "performance": {
                        "total_delete_ms": round(total_delete_time * 1000, 2),
                        "total_ms": round(total_time * 1000, 2),
                    },
                }
            ),
            mimetype="application/json",
            status_code=200,
        )

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] Batch delete operation failed after {total_time:.3f}s: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return func.HttpResponse(
            body=json.dumps(
                {
                    "error": "Batch delete operation failed",
                    "message": str(e),
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )


@app.route(route="get_blob", methods=["GET"])
@require_api_key
async def get_blob(req: func.HttpRequest) -> func.HttpResponse:
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] Get blob content request initiated")

    try:
        # Extract blob storage configuration from query parameters
        blob_endpoint = req.params.get("blob_endpoint")
        container_name = req.params.get("blob_container")
        blob_name = req.params.get("blob_name")

        # Validate required parameters
        if not blob_endpoint or not container_name or not blob_name:
            logger.warning(f"[{request_id}] Missing required blob storage query parameters")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Missing required parameters",
                        "message": "Please provide blob_endpoint, blob_container, and blob_name query parameters",
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        logger.info(f"[{request_id}] Retrieving blob from container={container_name}")

        # Use cached client
        blob_service_client = _get_blob_service_client(blob_endpoint)

        # Get blob client and download content
        download_start = time.time()
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

        # Download blob content (async)
        blob_data = await asyncio.to_thread(blob_client.download_blob)
        content_bytes: bytes = await asyncio.to_thread(blob_data.readall)
        content: str = content_bytes.decode("utf-8")
        download_time = time.time() - download_start

        total_time = time.time() - start_time

        logger.info(
            f"[{request_id}] Blob content retrieved (size={len(content)} bytes, duration={download_time:.3f}s)"
        )

        return func.HttpResponse(
            body=json.dumps(
                {
                    "container": container_name,
                    "blob_name": blob_name,
                    "content": content,
                    "content_length": len(content),
                    "request_id": request_id,
                    "performance": {
                        "download_ms": round(download_time * 1000, 2),
                        "total_ms": round(total_time * 1000, 2),
                    },
                }
            ),
            mimetype="application/json",
            status_code=200,
        )

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] Blob content retrieval failed after {total_time:.3f}s: {type(e).__name__}",
            exc_info=True,
        )
        return func.HttpResponse(
            body=json.dumps(
                {"error": "Blob retrieval failed", "message": str(e), "request_id": request_id}
            ),
            mimetype="application/json",
            status_code=500,
        )


@app.route(route="save_blob", methods=["POST"])
@require_api_key
async def save_blob(req: func.HttpRequest) -> func.HttpResponse:
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] Save blob content request initiated")

    try:
        # Extract blob storage configuration from query parameters
        blob_endpoint = req.params.get("blob_endpoint")
        container_name = req.params.get("blob_container")
        blob_name = req.params.get("blob_name")

        # Validate required parameters
        if not blob_endpoint or not container_name or not blob_name:
            logger.warning(f"[{request_id}] Missing required blob storage query parameters")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Missing required parameters",
                        "message": "Please provide blob_endpoint, blob_container, and blob_name query parameters",
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Get blob content from request body
        blob_content = req.get_body()

        if not blob_content:
            logger.warning(f"[{request_id}] Validation failed: blob content is empty")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Validation error",
                        "message": "Request body must contain non-empty blob content",
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        logger.info(
            f"[{request_id}] Saving blob to container={container_name} (size={len(blob_content)} bytes)"
        )

        # Use cached client
        blob_service_client = _get_blob_service_client(blob_endpoint)

        # Get blob client
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

        # Upload blob content with metadata parameters (async)
        upload_start = time.time()
        await asyncio.to_thread(
            blob_client.upload_blob,
            data=blob_content,
            overwrite=True,
            metadata={"queryParametersSingleEncoded": "true", "ReadFileMetadataFromServer": "true"},
        )
        upload_time = time.time() - upload_start

        total_time = time.time() - start_time

        # Construct blob URL
        blob_url = f"{blob_endpoint.rstrip('/')}/{container_name}/{blob_name}"

        logger.info(f"[{request_id}] Blob content saved (duration={upload_time:.3f}s)")

        return func.HttpResponse(
            body=json.dumps(
                {
                    "message": "Blob content saved successfully",
                    "container": container_name,
                    "blob_name": blob_name,
                    "content_length": len(blob_content),
                    "blob_url": blob_url,
                    "request_id": request_id,
                    "performance": {
                        "upload_ms": round(upload_time * 1000, 2),
                        "total_ms": round(total_time * 1000, 2),
                    },
                }
            ),
            mimetype="application/json",
            status_code=200,
        )

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] Blob save operation failed after {total_time:.3f}s: {type(e).__name__}",
            exc_info=True,
        )
        return func.HttpResponse(
            body=json.dumps(
                {"error": "Blob save operation failed", "message": str(e), "request_id": request_id}
            ),
            mimetype="application/json",
            status_code=500,
        )


@app.route(route="delete_blob", methods=["DELETE"])
@require_api_key
async def delete_blob(req: func.HttpRequest) -> func.HttpResponse:
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] Delete blob request initiated")

    try:
        # Extract blob storage endpoint from query parameters
        blob_endpoint = req.params.get("blob_endpoint")

        if not blob_endpoint:
            logger.warning(f"[{request_id}] Missing required blob storage endpoint parameter")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Missing required parameters",
                        "message": "Please provide blob_endpoint query parameter",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Use cached Blob Service Client
        blob_service_client = _get_blob_service_client(blob_endpoint)

        # Get request body
        req_body_text = req.get_body().decode("utf-8").strip()

        if not req_body_text:
            logger.warning(f"[{request_id}] Validation failed: request body is empty")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Validation error",
                        "message": "Request body must contain blob path(s) to delete",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

    except Exception as e:
        logger.error(
            f"[{request_id}] Failed to initialize blob service client or read request body: {str(e)}"
        )
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Initialization error",
                    "message": "Failed to initialize Azure Blob Storage service",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )

    # Try to parse as JSON first (for batch operations)
    blob_paths: list[str] = []
    try:
        req_body_json: Any = json.loads(req_body_text)

        # Handle different input formats
        if isinstance(req_body_json, dict):
            # Format: {"blobs": ["path1", "path2", ...]}
            blobs_array: Any = cast(dict[str, Any], req_body_json).get("blobs")
            if isinstance(blobs_array, list):
                # Cast list elements to ensure type safety
                blob_paths = [str(item).strip() for item in cast(list[Any], blobs_array) if item]
            else:
                logger.warning(f"[{request_id}] Validation failed: 'blobs' field is not an array")
                return func.HttpResponse(
                    json.dumps(
                        {
                            "error": "Validation error",
                            "message": "'blobs' must be an array of blob path strings",
                            "request_id": request_id,
                        }
                    ),
                    mimetype="application/json",
                    status_code=400,
                )
        elif isinstance(req_body_json, list):
            # Format: ["path1", "path2", ...]
            blob_paths = [str(item).strip() for item in cast(list[Any], req_body_json) if item]
        else:
            # Single string in JSON format
            blob_paths = [str(req_body_json).strip()]

    except json.JSONDecodeError:
        # Not JSON, treat as plain text (single blob path)
        blob_paths = [req_body_text]

    # Validate that we have at least one blob path
    if not blob_paths or len(blob_paths) == 0:
        logger.warning(f"[{request_id}] Validation failed: no valid blob paths provided")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Validation error",
                    "message": "At least one blob path must be provided",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )

    try:
        logger.info(f"[{request_id}] Processing deletion for {len(blob_paths)} blob(s) in parallel")

        # Execute all deletions in parallel using asyncio.gather
        successful_deletes: list[dict[str, Any]] = []
        failed_deletes: list[dict[str, Any]] = []
        total_delete_time = 0.0

        # Create tasks for all deletions
        tasks = [
            _delete_blob(
                blob_path,
                blob_service_client,
                request_id,
            )
            for blob_path in blob_paths
        ]

        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for result in results:
            if isinstance(result, Exception):
                failed_deletes.append(
                    {
                        "blob_path": "unknown",
                        "container": "unknown",
                        "blob_name": "unknown",
                        "error": str(result),
                        "delete_ms": 0.0,
                    }
                )
            elif isinstance(result, tuple) and len(result) == 6:
                blob_path, container_name, blob_name, success, error_msg, delete_time = result
                total_delete_time += delete_time

                if success:
                    successful_deletes.append(
                        {
                            "blob_path": blob_path,
                            "container": container_name,
                            "blob_name": blob_name,
                            "delete_ms": round(delete_time * 1000, 2),
                        }
                    )
                else:
                    failed_deletes.append(
                        {
                            "blob_path": blob_path,
                            "container": container_name,
                            "blob_name": blob_name,
                            "error": error_msg,
                            "delete_ms": round(delete_time * 1000, 2),
                        }
                    )

        total_time = time.time() - start_time

        logger.info(
            f"[{request_id}] Blob deletion completed: {len(successful_deletes)} successful, {len(failed_deletes)} failed"
        )

        return func.HttpResponse(
            body=json.dumps(
                {
                    "message": "Blob deletion operation completed",
                    "total_blobs": len(blob_paths),
                    "successful_deletes": len(successful_deletes),
                    "failed_deletes": len(failed_deletes),
                    "successful": successful_deletes,
                    "failed": failed_deletes,
                    "request_id": request_id,
                    "performance": {
                        "total_delete_ms": round(total_delete_time * 1000, 2),
                        "total_ms": round(total_time * 1000, 2),
                    },
                }
            ),
            mimetype="application/json",
            status_code=200,
        )

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] Blob deletion operation failed after {total_time:.3f}s: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return func.HttpResponse(
            body=json.dumps(
                {
                    "error": "Blob deletion operation failed",
                    "message": str(e),
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )


@app.route(route="query_aisearch", methods=["POST"])
@require_api_key
async def query_aisearch(req: func.HttpRequest) -> func.HttpResponse:
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] Azure AI Search query request initiated")

    search_queries = None
    try:
        # Extract and validate Azure AI Search configuration using helper
        aisearch_config = get_aisearch_config(req, request_id)
        if isinstance(aisearch_config, func.HttpResponse):
            return aisearch_config
        search_endpoint, search_api_key, top, vector_fields = aisearch_config

        # Get request body
        req_body = req.get_json()
        search_queries: list[str] | None = req_body.get("search")

    except ValueError as e:
        logger.error(f"[{request_id}] Invalid JSON in request body: {str(e)}")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Invalid request body",
                    "message": "Please provide valid JSON with a 'search' parameter",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )
    except Exception as e:
        logger.error(f"[{request_id}] Failed to parse request: {str(e)}")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Initialization error",
                    "message": "Failed to parse Azure AI Search request",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )

    # Validate search parameter - expecting an array
    if not isinstance(search_queries, list):
        logger.warning(f"[{request_id}] Validation failed: search parameter is not a list/array")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Validation error",
                    "message": "'search' parameter must be an array of strings",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )

    # Type narrowing: at this point, search_queries is list[str] after isinstance check
    if len(search_queries) == 0:
        logger.warning(f"[{request_id}] Validation failed: search array is empty")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Validation error",
                    "message": "'search' array must contain at least one query",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )

    try:
        logger.info(
            f"[{request_id}] Processing {len(search_queries)} Azure AI Search queries in parallel"
        )

        # Execute all searches in parallel using asyncio
        all_results: list[dict[str, Any]] = []
        total_query_time = 0.0
        query_details: list[dict[str, Any]] = []
        failed_queries: list[dict[str, Any]] = []

        # Create tasks for all search queries
        tasks = [
            _execute_aisearch_query(
                search_text,
                search_endpoint,
                search_api_key,
                top,
                vector_fields,
                request_id,
            )
            for search_text in search_queries
        ]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed_queries.append(
                    {
                        "query": search_queries[i],
                        "error": str(result),
                    }
                )
                logger.error(f"[{request_id}] AI Search query failed: {search_queries[i]}: {str(result)}")
                continue

            # Type guard: ensure result is a tuple with expected length
            if isinstance(result, tuple) and len(result) == 3:
                search_text_result, items_result, query_time_result = result
                all_results.extend(items_result)
                total_query_time += query_time_result
                query_details.append(
                    {
                        "query": search_text_result,
                        "result_count": len(items_result),
                        "query_ms": round(query_time_result * 1000, 2),
                    }
                )

        # Remove duplicates based on unique document identifier
        # Azure AI Search typically uses '@search.score' and a document id field
        seen: set[str] = set()
        unique_results: list[dict[str, Any]] = []
        for item in all_results:
            # Try common id fields - adjust based on your index schema
            doc_id = item.get("id") or item.get("@search.documentKey") or str(item)
            if doc_id not in seen:
                seen.add(doc_id)
                unique_results.append(item)

        total_time = time.time() - start_time

        logger.info(
            f"[{request_id}] Azure AI Search completed: {len(all_results)} total results, {len(unique_results)} unique results"
        )

        return func.HttpResponse(
            body=json.dumps(
                {
                    "search_queries": search_queries,
                    "vector_fields": vector_fields,
                    "top": top,
                    "results": unique_results,
                    "total_results": len(all_results),
                    "unique_results": len(unique_results),
                    "duplicates_removed": len(all_results) - len(unique_results),
                    "request_id": request_id,
                    "query_details": query_details,
                    "failed_queries": failed_queries,
                    "queries_failed": len(failed_queries),
                    "performance": {
                        "total_query_ms": round(total_query_time * 1000, 2),
                        "total_ms": round(total_time * 1000, 2),
                        "queries_executed": len(search_queries),
                        "queries_succeeded": len(query_details),
                    },
                }
            ),
            mimetype="application/json",
            status_code=200,
        )

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] Azure AI Search operation failed after {total_time:.3f}s: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return func.HttpResponse(
            body=json.dumps(
                {
                    "error": "Azure AI Search operation failed",
                    "message": str(e),
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )
