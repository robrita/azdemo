import asyncio
import base64
import json
import logging
import os
import re
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
MAX_REQUEST_SIZE_MB = int(os.getenv("MAX_REQUEST_SIZE_MB", "100"))
MAX_REQUEST_SIZE_BYTES = MAX_REQUEST_SIZE_MB * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = int(os.getenv("DEFAULT_TIMEOUT_SECONDS", "60"))
AISEARCH_TIMEOUT_SECONDS = int(os.getenv("AISEARCH_TIMEOUT_SECONDS", "60"))
HEALTH_CHECK_TIMEOUT_SECONDS = int(os.getenv("HEALTH_CHECK_TIMEOUT_SECONDS", "5"))
COSMOS_RETRY_MAX_ATTEMPTS = int(os.getenv("COSMOS_RETRY_MAX_ATTEMPTS", "3"))
COSMOS_RETRY_BASE_DELAY = float(os.getenv("COSMOS_RETRY_BASE_DELAY", "1.0"))

# LLM Filter System Prompt for filtering search results
LLM_FILTER_SYSTEM_PROMPT = """You are a relevance evaluator. Analyze the retrieved document and determine if it contains information that directly answers or is relevant to the user's query.

Respond with only "true" if the document is relevant, or "false" if it is not relevant."""

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


def _generate_cosmosdb_id(value: str) -> str:
    """
    Generate a Cosmos DB-safe document ID from a value using base64 encoding.

    Cosmos DB document IDs have the following restrictions:
    - Cannot contain: '/', '\\', '?', '#'
    - Cannot end with a space
    - Maximum length of 255 characters

    Args:
        value: The value to convert to a Cosmos DB-safe ID

    Returns:
        A base64-encoded, sanitized string suitable for use as a Cosmos DB document ID
    """
    # Encode the value to base64 (URL-safe variant to avoid / and +)
    encoded = base64.urlsafe_b64encode(value.encode("utf-8")).decode("utf-8")

    # Remove padding characters (=) which are safe but can be omitted
    encoded = encoded.rstrip("=")

    # Ensure the ID doesn't exceed the 100 character limit
    if len(encoded) > 100:
        encoded = encoded[:100]

    return encoded


def _detect_file_type(content_type: str | None) -> str:
    """
    Detect file type based on content_type value.

    Args:
        content_type: The MIME type or content-type string

    Returns:
        File type identifier: 'pdf', 'image', 'docx', 'xlsx', 'pptx', 'csv', 'json', 'audio', 'video', 'text', or 'unknown'
    """
    if not content_type:
        return "unknown"

    content_type_lower = content_type.lower()

    # PDF files
    if "/pdf" in content_type_lower or content_type_lower.endswith(".pdf"):
        return "pdf"

    # Image files
    if "image/" in content_type_lower:
        return "image"

    # Microsoft Office documents
    if ".document" in content_type_lower or "wordprocessingml" in content_type_lower:
        return "docx"
    if ".sheet" in content_type_lower or "spreadsheetml" in content_type_lower:
        return "xlsx"
    if ".presentation" in content_type_lower or "presentationml" in content_type_lower:
        return "pptx"

    # CSV files
    if "/csv" in content_type_lower or "/csv" in content_type_lower or content_type_lower.endswith(".csv"):
        return "csv"

    # JSON files
    if "/json" in content_type_lower or "/json" in content_type_lower or content_type_lower.endswith(".json"):
        return "json"

    # Audio files
    if "audio/" in content_type_lower:
        return "audio"

    # Video files
    if "video/" in content_type_lower:
        return "video"

    # Plain text files
    if "text/plain" in content_type_lower or "text/" in content_type_lower:
        return "text"

    return "unknown"


def _default_pagination(
    content: str,
    min_chunk_size: int = 10000,
    request_id: str = "",
    min_chunk_threshold: int = 15000,
) -> list[dict[str, Any]]:
    """
    Default pagination for unknown file types using a multi-strategy approach.

    Strategy:
    1. First, try to split by PageBreak markers (<!-- PageBreak -->)
    2. If no PageBreak markers and content length > min_chunk_threshold, use sentence-based chunking
    3. Fallback to single page if content is empty, too short for chunking, or chunking fails

    A sentence is defined as each item when splitting by newline characters (\\n or \\n\\n).
    Sentences are grouped together until the chunk reaches at least min_chunk_size characters,
    then a new page is started.

    Args:
        content: The content to chunk
        min_chunk_size: Minimum number of characters per chunk before starting a new page (default: 10000)
        request_id: Request ID for logging
        min_chunk_threshold: Minimum content length required for sentence-based chunking (default: 15000)

    Returns:
        List of page dictionaries with 'page_number' and 'content' keys
    """
    import re

    pages: list[dict[str, Any]] = []

    if not content or not content.strip():
        logger.info(f"[{request_id}] Content chunking: empty content")
        return pages

    # Strategy 1: Try PageBreak markers first
    page_delimiter = "<!-- PageBreak -->"

    if page_delimiter in content:
        page_contents = content.split(page_delimiter)
        for idx, page_content in enumerate(page_contents):
            stripped_content = page_content.strip()
            if stripped_content:
                pages.append({
                    "page_number": idx + 1,
                    "content": stripped_content,
                })
        logger.info(f"[{request_id}] Content chunking (PageBreak): {len(pages)} pages")
        return pages

    # Check if content length qualifies for sentence-based chunking (> min_chunk_threshold)
    content_length = len(content.strip())
    if content_length <= min_chunk_threshold:
        # Fallback to single page for shorter content
        pages.append({
            "page_number": 1,
            "content": content.strip(),
        })
        logger.info(f"[{request_id}] Content chunking: 1 page (content length {content_length} <= {min_chunk_threshold} chars)")
        return pages

    # Strategy 2: Sentence-based chunking (only for content > min_chunk_threshold)
    # Split by one or more newlines to get sentences/paragraphs
    sentences = re.split(r'\n+', content.strip())

    # Filter out empty sentences
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        # Strategy 3: Fallback to single page
        pages.append({
            "page_number": 1,
            "content": content.strip(),
        })
        logger.info(f"[{request_id}] Content chunking: 1 page (no sentences found)")
        return pages

    def _split_oversized_sentence(text: str, target_size: int) -> list[str]:
        """
        Split an oversized sentence into smaller parts at word boundaries.
        Each part will be approximately target_size characters.
        """
        if len(text) <= target_size:
            return [text]

        parts: list[str] = []
        remaining = text

        while remaining:
            if len(remaining) <= target_size:
                parts.append(remaining)
                break

            # Find a good split point near target_size
            # Look for the last space before target_size
            split_point = remaining.rfind(' ', 0, target_size)

            if split_point == -1:
                # No space found, try to find punctuation
                for punct in ['.', ',', ';', ':', '!', '?', '-']:
                    split_point = remaining.rfind(punct, 0, target_size)
                    if split_point != -1:
                        split_point += 1  # Include the punctuation
                        break

            if split_point <= 0:
                # No good split point found, force split at target_size
                split_point = target_size

            parts.append(remaining[:split_point].strip())
            remaining = remaining[split_point:].strip()

        return [p for p in parts if p]  # Filter out empty parts

    current_chunk: list[str] = []
    current_size = 0
    page_number = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        # Handle oversized sentences by splitting them
        if sentence_len > min_chunk_size:
            # First, save current chunk if not empty
            if current_chunk:
                page_number += 1
                pages.append({
                    "page_number": page_number,
                    "content": "\n\n".join(current_chunk),
                })
                current_chunk = []
                current_size = 0

            # Split the oversized sentence into parts
            sentence_parts = _split_oversized_sentence(sentence, min_chunk_size)
            logger.info(f"[{request_id}] Split oversized sentence ({sentence_len} chars) into {len(sentence_parts)} parts")

            # Add each part as a separate page (except possibly the last one)
            for i, part in enumerate(sentence_parts):
                if i < len(sentence_parts) - 1:
                    # Not the last part - add as its own page
                    page_number += 1
                    pages.append({
                        "page_number": page_number,
                        "content": part,
                    })
                else:
                    # Last part - start a new chunk with it (may be merged with next sentences)
                    current_chunk = [part]
                    current_size = len(part)
            continue

        # Account for the newline separator between sentences
        separator_len = 2 if current_chunk else 0  # "\n\n" between sentences

        # Add sentence to current chunk
        current_chunk.append(sentence)
        current_size += separator_len + sentence_len

        # Check if current chunk has reached the minimum size threshold
        # If so, save it and start a new chunk
        if current_size >= min_chunk_size:
            page_number += 1
            pages.append({
                "page_number": page_number,
                "content": "\n\n".join(current_chunk),
            })
            current_chunk = []
            current_size = 0

    # Handle the last chunk - merge with previous page if too small, otherwise create new page
    if current_chunk:
        last_chunk_content = "\n\n".join(current_chunk)
        if pages and current_size < min_chunk_size:
            # Merge with the previous page since the last chunk is too small
            previous_page = pages[-1]
            previous_page["content"] = previous_page["content"] + "\n\n" + last_chunk_content
            logger.info(f"[{request_id}] Merged small last chunk ({current_size} chars) with previous page")
        else:
            # Create a new page (either no previous pages or chunk is large enough)
            page_number += 1
            pages.append({
                "page_number": page_number,
                "content": last_chunk_content,
            })

    if pages:
        logger.info(f"[{request_id}] Content chunking: {len(pages)} chunks (min_size={min_chunk_size})")
    else:
        # Fallback to single page if no chunks were created
        pages.append({
            "page_number": 1,
            "content": content.strip(),
        })
        logger.info(f"[{request_id}] Content chunking: 1 page (fallback)")

    return pages


def _paginate_markdown_content(
    content_markdown: str,
    file_type: str,
    request_id: str,
    min_chunk_size: int = 10000,
) -> list[dict[str, Any]]:
    """
    Split markdown content into pages based on file type.

    Args:
        content_markdown: The full markdown content to paginate
        file_type: The detected file type ('pdf', 'image', 'docx', 'xlsx', 'pptx', etc.)
        request_id: Request ID for logging
        min_chunk_size: Minimum characters per chunk for sentence-based splitting (default: 10000)

    Returns:
        List of page dictionaries with 'page_number' and 'content' keys
    """
    pages: list[dict[str, Any]] = []

    if not content_markdown or not content_markdown.strip():
        logger.info(f"[{request_id}] No content to paginate")
        return pages

    # If content is shorter than min_chunk_size, use default pagination (returns single page)
    content_length = len(content_markdown.strip())
    if content_length < min_chunk_size:
        logger.info(f"[{request_id}] Content length {content_length} < {min_chunk_size}, using default pagination")
        return _default_pagination(content_markdown, min_chunk_size, request_id)

    if file_type == "pdf":
        pages = _default_pagination(content_markdown, min_chunk_size, request_id)
        logger.info(f"[{request_id}] PDF pagination: {len(pages)} pages extracted")

    elif file_type == "xlsx":
        # Excel: Split by H1 headers as worksheet/section markers
        section_pattern = re.compile(r'^#\s+.+$', re.MULTILINE)
        parts = section_pattern.split(content_markdown)
        matches = section_pattern.findall(content_markdown)

        if len(matches) > 1:  # Multiple sections
            page_number = 0

            if parts and parts[0].strip():
                page_number += 1
                pages.append({
                    "page_number": page_number,
                    "content": parts[0].strip(),
                })

            for i, match in enumerate(matches):
                page_number += 1
                content_idx = i + 1 if i + 1 < len(parts) else -1
                section_content = parts[content_idx].strip() if content_idx > 0 and content_idx < len(parts) else ""

                # Extract sheet name from H1 header (remove leading # and whitespace)
                sheet_name = match.strip().lstrip('#').strip()

                pages.append({
                    "page_number": page_number,
                    "content": f"{match.strip()}\n\n{section_content}".strip(),
                    "sheet_name": sheet_name,
                })
        else:
            # Single section or no headers, use default pagination
            pages = _default_pagination(content_markdown, min_chunk_size, request_id)

        logger.info(f"[{request_id}] Excel pagination: {len(pages)} worksheets extracted")

    elif file_type == "pptx":
        # PowerPoint: Split by slide markers (## Slide or <!-- Slide)
        import re

        # Pattern to match slide headers or markers
        slide_pattern = re.compile(
            r'(^#{1,2}\s*Slide\s*\d*[:\s]?|<!-- Slide \d+ -->)',
            re.MULTILINE | re.IGNORECASE
        )

        parts = slide_pattern.split(content_markdown)
        matches = slide_pattern.findall(content_markdown)

        if matches:
            page_number = 0

            # Check if there's content before the first slide marker
            if parts and parts[0].strip():
                page_number += 1
                pages.append({
                    "page_number": page_number,
                    "content": parts[0].strip(),
                    "slide_title": "Title Slide",
                })

            # Process each slide
            for i, match in enumerate(matches):
                page_number += 1
                content_idx = i + 1 if i + 1 < len(parts) else -1
                slide_content = parts[content_idx].strip() if content_idx > 0 and content_idx < len(parts) else ""

                pages.append({
                    "page_number": page_number,
                    "content": f"{match.strip()}\n\n{slide_content}".strip(),
                })
        else:
            # No slide markers found, use default pagination
            pages = _default_pagination(content_markdown, min_chunk_size, request_id)

        logger.info(f"[{request_id}] PowerPoint pagination: {len(pages)} slides extracted")

    elif file_type == "docx":
        # Word documents: Split by H1 headers as section markers
        section_pattern = re.compile(r'^#\s+.+$', re.MULTILINE)
        parts = section_pattern.split(content_markdown)
        matches = section_pattern.findall(content_markdown)

        if len(matches) > 1:  # Multiple sections
            page_number = 0

            if parts and parts[0].strip():
                page_number += 1
                pages.append({
                    "page_number": page_number,
                    "content": parts[0].strip(),
                })

            for i, match in enumerate(matches):
                page_number += 1
                content_idx = i + 1 if i + 1 < len(parts) else -1
                section_content = parts[content_idx].strip() if content_idx > 0 and content_idx < len(parts) else ""

                pages.append({
                    "page_number": page_number,
                    "content": f"{match.strip()}\n\n{section_content}".strip(),
                })
        else:
            # Single section or no headers, use default pagination
            pages = _default_pagination(content_markdown, min_chunk_size, request_id)

        logger.info(f"[{request_id}] Word document pagination: {len(pages)} pages/sections extracted")

    elif file_type == "image":
        # Images: Treat as single page
        pages.append({
            "page_number": 1,
            "content": content_markdown.strip(),
        })
        logger.info(f"[{request_id}] Image pagination: 1 page")

    elif file_type in ["csv", "json"]:
        # CSV/JSON: Treat as single page (structured data)
        pages.append({
            "page_number": 1,
            "content": content_markdown.strip(),
        })
        logger.info(f"[{request_id}] {file_type.upper()} pagination: 1 page (structured data)")

    elif file_type in ["audio", "video"]:
        # Audio/Video: Usually transcription, treat as single page or split by timestamps
        import re

        # Look for timestamp patterns like [00:00:00] or (00:00)
        timestamp_pattern = re.compile(r'(^\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s*)', re.MULTILINE)
        matches = timestamp_pattern.findall(content_markdown)

        if len(matches) > 5:  # Has significant timestamps, could split by segments
            # For now, keep as single page but could implement time-based chunking
            pages.append({
                "page_number": 1,
                "content": content_markdown.strip(),
                "has_timestamps": True,
            })
        else:
            pages.append({
                "page_number": 1,
                "content": content_markdown.strip(),
            })

        logger.info(f"[{request_id}] {file_type.capitalize()} pagination: {len(pages)} segment(s)")

    else:
        # Unknown file type: Use the default chunking helper
        pages = _default_pagination(content_markdown, min_chunk_size, request_id)

    return pages


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


def _validate_api_key_and_size(req: func.HttpRequest, request_id: str) -> func.HttpResponse | None:
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
        logger.error(
            f"[{request_id}] {operation_name} failed after {COSMOS_RETRY_MAX_ATTEMPTS} retries"
        )
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
    req: func.HttpRequest,
    request_id: str,
    require_embedding: bool = True,
) -> tuple[AzureOpenAI, str | None] | func.HttpResponse:
    """
    Extract Azure OpenAI parameters from request and initialize OpenAI client.
    API keys are accepted via X-OpenAI-Key header (preferred) or openai_key query parameter (deprecated).

    Args:
        req: HTTP request object
        request_id: Request ID for logging purposes
        require_embedding: If True, embedding_deployment is required. If False, it's optional.

    Returns:
        Tuple of (OpenAI client instance, embedding deployment name or None) if successful,
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

        # Check required parameters based on require_embedding flag
        if require_embedding:
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
        else:
            if not azure_endpoint or not api_key:
                logger.warning(f"[{request_id}] Missing required Azure OpenAI parameters (endpoint/key)")
                return func.HttpResponse(
                    json.dumps(
                        {
                            "error": "Missing required parameters",
                            "message": "Please provide openai_endpoint and X-OpenAI-Key header (or openai_key param)",
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
) -> tuple[str, str, int, int, int, list[str], str, AzureOpenAI | None, list[str] | None] | func.HttpResponse:
    """
    Extract and validate Azure AI Search configuration from request parameters.

    Args:
        req: HTTP request object
        request_id: Request ID for logging purposes

    Returns:
        Tuple of (search_endpoint, search_api_key, top_search, top_k, top_results, vector_fields, llm_filter, openai_client, select) if successful,
        or HttpResponse with error if parameters are missing or invalid.
        When llm_filter is specified, openai_client will be initialized; otherwise it's None.
        select is an optional list of fields to return from search results.
    """
    try:
        # Extract Azure AI Search configuration
        search_endpoint = req.params.get("search_endpoint")

        # API key from header (preferred) or query parameter (fallback)
        headers = cast(dict[str, str], req.headers)
        search_api_key = headers.get("X-Search-Key") or req.params.get("search_api_key")

        top_search_param = req.params.get("top_search", "50")
        top_k_param = req.params.get("top_k", "50")
        top_results_param = req.params.get("top_results", "20")
        vector_fields_param = req.params.get("vector_fields", "")
        llm_filter_param = req.params.get("llm_filter", "")
        select_param = req.params.get("select_fields", "")

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

        # Parse top_search parameter
        try:
            top_search = int(top_search_param)
            if top_search <= 0:
                raise ValueError("top_search must be greater than 0")
        except ValueError as e:
            logger.warning(f"[{request_id}] Invalid top_search parameter: {top_search_param}")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid parameter",
                        "message": f"top_search parameter must be a positive integer: {str(e)}",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Parse top_k parameter
        try:
            top_k = int(top_k_param)
            if top_k <= 0:
                raise ValueError("top_k must be greater than 0")
        except ValueError as e:
            logger.warning(f"[{request_id}] Invalid top_k parameter: {top_k_param}")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid parameter",
                        "message": f"top_k parameter must be a positive integer: {str(e)}",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Parse top_results parameter (optional, default: 20)
        try:
            top_results = int(top_results_param)
            if top_results <= 0:
                raise ValueError("top_results must be greater than 0")
        except ValueError as e:
            logger.warning(f"[{request_id}] Invalid top_results parameter: {top_results_param}")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid parameter",
                        "message": f"top_results parameter must be a positive integer: {str(e)}",
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

        # Initialize OpenAI client if llm_filter is specified
        openai_client: AzureOpenAI | None = None
        if llm_filter_param:
            openai_result = get_openai_client(req, request_id, require_embedding=False)
            if isinstance(openai_result, func.HttpResponse):
                return openai_result
            openai_client, _ = openai_result
            logger.info(f"[{request_id}] LLM filter enabled with model: {llm_filter_param}")

        # Parse select parameter (comma-separated, optional)
        select_fields: list[str] | None = None
        if select_param:
            select_fields = [field.strip() for field in select_param.split(",") if field.strip()]
            if select_fields:
                logger.info(f"[{request_id}] Select fields configured: {select_fields}")
            else:
                select_fields = None

        logger.info(f"[{request_id}] Azure AI Search configuration validated")
        # Type assertion: search_endpoint is guaranteed to be str after validation
        return (cast(str, search_endpoint), search_api_key, top_search, top_k, top_results, vector_fields, llm_filter_param, openai_client, select_fields)

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


async def _apply_llm_filter(
    search_text: str,
    document_content: str,
    openai_client: AzureOpenAI,
    llm_filter_model: str,
    request_id: str,
) -> tuple[bool, float]:
    """
    Apply LLM-based filtering to a single document to determine relevance.

    Args:
        search_text: The user's search query
        document_content: The document content with metadata to evaluate
        openai_client: Azure OpenAI client instance
        llm_filter_model: The GPT model deployment name to use for filtering
        request_id: Request ID for logging

    Returns:
        Tuple of (is_relevant, filter_time_seconds)
    """
    filter_start = time.time()

    try:
        # Prepare the user message with query and document
        user_content = f"USER QUERY: {search_text}\n\n<Retrieved_Document>{document_content}</Retrieved_Document>"

        # Make the LLM call
        response = await asyncio.to_thread(
            openai_client.chat.completions.create,
            model=llm_filter_model,
            messages=[
                {"role": "system", "content": LLM_FILTER_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0,
            top_p=1,
            response_format={"type": "text"},
        )

        filter_time = time.time() - filter_start

        # Parse the response - expecting "true" or "false"
        response_content = response.choices[0].message.content
        if not response_content:
            logger.warning(f"[{request_id}] LLM filter returned empty response")
            return False, filter_time

        is_relevant = response_content.strip().lower() == "true"
        return is_relevant, filter_time

    except Exception as e:
        filter_time = time.time() - filter_start
        logger.error(f"[{request_id}] LLM filter failed: {type(e).__name__}: {str(e)}")
        # Return False if LLM call fails
        return False, filter_time


def _deduplicate_results(
    all_results: list[dict[str, Any]],
    top_results: int,
    request_id: str,
) -> tuple[list[dict[str, Any]], int]:
    """
    Remove duplicate results based on unique document identifier (pageId).

    Args:
        all_results: List of search results to deduplicate
        top_results: Maximum number of unique results to return
        request_id: Request ID for logging

    Returns:
        Tuple of (deduplicated results limited by top_results, total unique count before limiting)
    """
    seen: set[str] = set()
    unique_results: list[dict[str, Any]] = []
    for item in all_results:
        page_id = item.get("pageId") or item.get("pageContent") or str(item)
        if page_id not in seen:
            seen.add(page_id)
            unique_results.append(item)

    unique_results_count = len(unique_results)
    limited_results = unique_results[:top_results]

    logger.info(
        f"[{request_id}] Deduplication: {len(all_results)} total -> {unique_results_count} unique -> {len(limited_results)} returned (top_results={top_results})"
    )

    return limited_results, unique_results_count


async def _apply_llm_filter_to_results(
    results: list[dict[str, Any]],
    search_queries: list[str],
    openai_client: AzureOpenAI,
    llm_filter_model: str,
    request_id: str,
) -> tuple[list[dict[str, Any]], float, int]:
    """
    Apply LLM-based filtering to search results to determine relevance.

    Args:
        results: List of search results to filter
        search_queries: List of user search queries (first one is used for filtering)
        openai_client: Azure OpenAI client instance
        llm_filter_model: The GPT model deployment name to use for filtering
        request_id: Request ID for logging

    Returns:
        Tuple of (filtered results, filter_time_seconds, pre_filter_count)
    """
    pre_filter_count = len(results)

    if not results:
        return results, 0.0, pre_filter_count

    # Track actual wall-clock time for the entire LLM filter block
    llm_filter_start = time.time()

    # Use first search query as user query for LLM filter
    user_query = search_queries[0] if search_queries else ""

    # Prepare document contents with metadata for each result
    async def filter_single_result(
        idx: int, result: dict[str, Any]
    ) -> tuple[int, bool, float]:
        """Filter a single result and return (index, is_relevant, filter_time)."""
        # Combine pageContent with metadata
        content = result.get("pageContent", "")
        metadata = result.get("metadata", "")
        document_content = f"Content:\n{content}\n\nMetadata:\n{metadata}"

        is_relevant, filter_time = await _apply_llm_filter(
            user_query,
            document_content,
            openai_client,
            llm_filter_model,
            request_id,
        )
        return idx, is_relevant, filter_time

    # Execute all LLM filter calls in parallel
    filter_tasks = [
        filter_single_result(idx, result)
        for idx, result in enumerate(results)
    ]
    filter_results = await asyncio.gather(*filter_tasks, return_exceptions=True)

    # Collect results that returned true
    filtered_results: list[dict[str, Any]] = []
    for filter_result in filter_results:
        if isinstance(filter_result, Exception):
            logger.error(
                f"[{request_id}] LLM filter task failed: {str(filter_result)}"
            )
            continue
        idx, is_relevant, _ = filter_result
        if is_relevant:
            # Extract only pageContent, pageNumber, pageLink fields
            original_result = results[idx]
            filtered_results.append({
                "pageContent": original_result.get("pageContent", ""),
                "pageNumber": original_result.get("pageNumber", ""),
                "pageLink": original_result.get("pageLink", ""),
            })

    # Calculate actual wall-clock time for the entire LLM filter block
    llm_filter_time = time.time() - llm_filter_start

    # If filtered_results is empty, return "Not Found" placeholder
    if len(filtered_results) == 0:
        filtered_results = [
            {
                "pageContent": "Not Found",
                "pageNumber": None,
                "pageLink": None,
            }
        ]

    logger.info(
        f"[{request_id}] LLM filter applied: {pre_filter_count} -> {len(filtered_results)} results (total_duration={llm_filter_time:.3f}s)"
    )

    return filtered_results, llm_filter_time, pre_filter_count


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
    Execute a hybrid search query combining vector similarity and full-text search.

    This function uses Reciprocal Rank Fusion (RRF) to merge three ranking signals:
    1. Search text full-text score (user's natural language query)
    2. Entity-based full-text score (keywords, document types)
    3. Vector distance (semantic similarity)

    The WHERE clause is removed to allow RRF to rank all documents, not just
    pre-filtered ones, which improves recall for semantic queries.

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

    # Build query components
    parameters: list[dict[str, Any]] = [
        {"name": "@k", "value": top},
        {"name": "@embedding", "value": embedding},
        {"name": "@searchText", "value": search_text},
    ]

    # Build FullTextScore for search text (natural language query)
    searchtext_fulltext_score = "FullTextScore(c.chunkContent, @searchText)"
    searchtext_entities_score = "FullTextScore(c.entities, @searchText)"

    # Build FullTextScore for entities (keywords, document types)
    if entities:
        entity_params = ", ".join([f"@entity{i}" for i in range(len(entities))])
        entity_fulltext_score = f"FullTextScore(c.chunkContent, {entity_params})"
        entity_entities_score = f"FullTextScore(c.entities, {entity_params})"
        for i, entity in enumerate(entities):
            parameters.append({"name": f"@entity{i}", "value": entity})
    else:
        # Use search text as fallback for entity scoring if no entities provided
        entity_fulltext_score = "FullTextScore(c.chunkContent, @searchText)"
        entity_entities_score = "FullTextScore(c.entities, @searchText)"

    # Use pure RRF ranking without WHERE clause to avoid excluding semantically
    # relevant documents that don't contain exact keywords
    # Weights: [chunkContent:searchText, chunkContent:entities, entities:searchText, entities:entities, vector]
    query = f"""
    SELECT TOP @k {select_fields}
    FROM c
    ORDER BY RANK RRF(
        {searchtext_fulltext_score},
        {entity_fulltext_score},
        {searchtext_entities_score},
        {entity_entities_score},
        VectorDistance(c.vector, @embedding),
        [1, 2, 2, 3, 4]
    )
    """

    logger.info(
        f"[{request_id}] Hybrid search: searchText='{search_text[:50]}...', entities={entities}"
    )

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

        await _retry_cosmos_operation(_delete_operation, request_id, f"Delete document id={doc_id}")
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
        logger.error(
            f"[{request_id}] Failed to delete blob (container={container_name}): {error_msg}"
        )
        return (blob_path, container_name, blob_name, False, error_msg, delete_time)


async def _execute_aisearch_query(
    search_text: str,
    search_endpoint: str,
    search_api_key: str,
    top_search: int,
    top_k: int,
    vector_fields: list[str],
    request_id: str,
    select_fields: list[str] | None = None,
) -> tuple[str, list[dict[str, Any]], float]:
    """
    Execute a single Azure AI Search hybrid query using aiohttp.
    Returns (search_text, results, query_time).

    Args:
        search_text: The search query text
        search_endpoint: Azure AI Search endpoint URL
        search_api_key: API key for authentication
        top_search: Number of results to return from search
        top_k: Number of nearest neighbors for vector search
        vector_fields: List of vector field names to search
        request_id: Request ID for logging
        select_fields: Optional list of fields to return (e.g., ["pageContent", "pageNumber", "pageLink"])
    """
    # Build Azure AI Search request payload
    search_payload: dict[str, Any] = {
        "search": search_text,
        "count": True,
        "top": top_search,
        "vectorQueries": [
            {
                "kind": "text",
                "text": search_text,
                "fields": ", ".join(vector_fields),
                "k": top_k,
            }
        ],
    }

    # Add select fields if specified
    if select_fields:
        search_payload["select"] = ",".join(select_fields)

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

            logger.info(
                f"[{request_id}] AI Search query returned {len(items)} results (duration={query_time:.3f}s)"
            )

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
                {
                    "error": "Initialization error",
                    "message": "Failed to initialize Azure services",
                    "request_id": request_id,
                }
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
                {
                    "error": "Initialization error",
                    "message": "Failed to initialize Cosmos DB container",
                    "request_id": request_id,
                }
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

        # Check for optional 'generate_id' parameter to auto-generate document ID
        generate_id_value = req.params.get("generate_id")
        if generate_id_value:
            # Use the parameter value directly to generate Cosmos DB-safe ID
            generated_id = _generate_cosmosdb_id(generate_id_value)
            req_body["id"] = generated_id
            logger.info(
                f"[{request_id}] Generated document ID from 'generate_id' parameter: {generated_id[:50]}..."
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
                        "message": "Document must contain an 'id' field for upsert operation, or use 'generate_id' parameter to auto-generate from a field",
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
                            "id": doc_id,
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
        top_param = req.params.get("top_search", "50")
        top_results_param = req.params.get("top_results", "20")
        select_fields_param = req.params.get("select_fields")
        llm_filter_param = req.params.get("llm_filter", "")

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

        # Parse top_results parameter (optional, default: 20)
        try:
            top_results = int(top_results_param)
            if top_results <= 0:
                raise ValueError("top_results must be greater than 0")
        except ValueError as e:
            logger.warning(f"[{request_id}] Invalid top_results parameter: {top_results_param}")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid parameter",
                        "message": f"top_results parameter must be a positive integer: {str(e)}",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Initialize LLM filter OpenAI client if llm_filter is specified
        llm_openai_client: AzureOpenAI | None = None
        if llm_filter_param:
            llm_openai_result = get_openai_client(req, request_id, require_embedding=False)
            if isinstance(llm_openai_result, func.HttpResponse):
                return llm_openai_result
            llm_openai_client, _ = llm_openai_result
            logger.info(f"[{request_id}] LLM filter enabled with model: {llm_filter_param}")

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
                logger.error(
                    f"[{request_id}] Search query failed: {search_queries[i]}: {str(result)}"
                )
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

        # Deduplicate results and limit by top_results
        unique_results, unique_results_count = _deduplicate_results(
            all_results, top_results, request_id
        )

        # Apply LLM filter if configured
        llm_filter_time = 0.0
        pre_filter_count = len(unique_results)
        if llm_filter_param and llm_openai_client and len(unique_results) > 0:
            unique_results, llm_filter_time, pre_filter_count = await _apply_llm_filter_to_results(
                unique_results,
                search_queries,
                llm_openai_client,
                llm_filter_param,
                request_id,
            )

        total_time = time.time() - start_time

        logger.info(
            f"[{request_id}] Search completed: {len(all_results)} total results, {unique_results_count} unique results, {len(unique_results)} returned (top_results={top_results})"
        )

        # Build response with optional LLM filter info
        response_data: dict[str, Any] = {
            "search_queries": search_queries,
            "entities": entities,
            "top_results": top_results,
            "results": unique_results,
            "total_results": len(all_results),
            "unique_results": unique_results_count,
            "results_returned": len(unique_results),
            "duplicates_removed": len(all_results) - unique_results_count,
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

        # Add LLM filter info if it was applied
        if llm_filter_param:
            response_data["llm_filter"] = {
                "model": llm_filter_param,
                "applied": llm_openai_client is not None and pre_filter_count > 0,
                "pre_filter_count": pre_filter_count,
                "post_filter_count": len(unique_results),
                "filter_ms": round(llm_filter_time * 1000, 2),
            }

        return func.HttpResponse(
            body=json.dumps(response_data),
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
        total_time = time.time() - start_time
        logger.info(f"[{request_id}] No documents to delete: input array is empty")
        return func.HttpResponse(
            json.dumps(
                {
                    "message": "No documents deleted: input array is empty",
                    "total_documents": 0,
                    "successful_deletes": 0,
                    "failed_deletes": 0,
                    "successful": [],
                    "failed": [],
                    "request_id": request_id,
                    "performance": {
                        "total_delete_ms": 0.0,
                        "total_ms": round(total_time * 1000, 2),
                    },
                }
            ),
            mimetype="application/json",
            status_code=200,
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
        search_endpoint, search_api_key, top_search, top_k, top_results, vector_fields, llm_filter, openai_client, select_fields = aisearch_config

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
                top_search,
                top_k,
                vector_fields,
                request_id,
                select_fields,
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
                logger.error(
                    f"[{request_id}] AI Search query failed: {search_queries[i]}: {str(result)}"
                )
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

        # Deduplicate results and limit by top_results
        unique_results, unique_results_count = _deduplicate_results(
            all_results, top_results, request_id
        )

        # Apply LLM filter if configured
        llm_filter_time = 0.0
        pre_filter_count = len(unique_results)
        if llm_filter and openai_client and len(unique_results) > 0:
            unique_results, llm_filter_time, pre_filter_count = await _apply_llm_filter_to_results(
                unique_results,
                search_queries,
                openai_client,
                llm_filter,
                request_id,
            )

        total_time = time.time() - start_time

        logger.info(
            f"[{request_id}] Azure AI Search completed: {len(all_results)} total results, {unique_results_count} unique results, {len(unique_results)} returned (top_results={top_results})"
        )

        # Build response with optional LLM filter info
        response_data: dict[str, Any] = {
            "search_queries": search_queries,
            "vector_fields": vector_fields,
            "top_search": top_search,
            "top_k": top_k,
            "top_results": top_results,
            "results": unique_results,
            "total_results": len(all_results),
            "unique_results": unique_results_count,
            "results_returned": len(unique_results),
            "duplicates_removed": len(all_results) - unique_results_count,
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

        # Add LLM filter info if it was applied
        if llm_filter:
            response_data["llm_filter"] = {
                "model": llm_filter,
                "applied": openai_client is not None and pre_filter_count > 0,
                "pre_filter_count": pre_filter_count,
                "post_filter_count": len(unique_results),
                "filter_ms": round(llm_filter_time * 1000, 2),
            }

        return func.HttpResponse(
            body=json.dumps(response_data),
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


@app.route(route="index_aisearch", methods=["POST"])
@require_api_key
async def index_aisearch(req: func.HttpRequest) -> func.HttpResponse:
    """
    Submit documents for indexing in Azure AI Search.

    Query parameters:
    - search_endpoint: Azure AI Search endpoint URL (required)
                       Format: https://<service>.search.windows.net/indexes/<index>/docs/index?api-version=2024-07-01
    - action: The search action to apply to all documents (required)
              Valid values: 'mergeOrUpload', 'upload', 'merge', 'delete'

    Headers:
    - X-Search-Key: Azure AI Search admin API key (required)
    - X-API-Key: API key for this function (required)

    Request body (JSON):
    {
        "value": [
            {"id": "1", "title": "Doc 1", "content": "..."},
            {"id": "2", "title": "Doc 2", "content": "..."}
        ]
    }

    Returns:
    - Indexing results from Azure AI Search
    - Performance metrics
    """
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] Azure AI Search indexing request initiated")

    try:
        # Extract Azure AI Search configuration
        search_endpoint = req.params.get("search_endpoint")
        action = req.params.get("action")

        # API key from header (preferred) or query parameter (fallback)
        headers = cast(dict[str, str], req.headers)
        search_api_key = headers.get("X-Search-Key") or req.params.get("search_api_key")

        # Validate required parameters
        if not search_api_key:
            logger.warning(f"[{request_id}] Missing required Azure AI Search API key")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Missing required parameters",
                        "message": "Please provide X-Search-Key header (or search_api_key param)",
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

        # Validate action parameter
        valid_actions = ["mergeOrUpload", "upload", "merge", "delete"]
        if not action:
            logger.warning(f"[{request_id}] Missing required action parameter")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Missing required parameters",
                        "message": f"Please provide 'action' query parameter. Valid values: {', '.join(valid_actions)}",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        if action not in valid_actions:
            logger.warning(f"[{request_id}] Invalid action parameter: {action}")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid parameter",
                        "message": f"Invalid action '{action}'. Valid values: {', '.join(valid_actions)}",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Get request body
        req_body = req.get_json()
        documents: list[dict[str, Any]] | None = req_body.get("value")

        # Validate documents
        if not isinstance(documents, list):
            logger.warning(f"[{request_id}] Validation failed: 'value' parameter is not a list/array")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Validation error",
                        "message": "'value' parameter must be an array of documents",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        if len(documents) == 0:
            total_time = time.time() - start_time
            logger.info(f"[{request_id}] No documents to index: input array is empty")
            return func.HttpResponse(
                json.dumps(
                    {
                        "message": "No documents indexed: input array is empty",
                        "action": action,
                        "total_documents": 0,
                        "results": [],
                        "request_id": request_id,
                        "performance": {
                            "index_ms": 0.0,
                            "total_ms": round(total_time * 1000, 2),
                        },
                    }
                ),
                mimetype="application/json",
                status_code=200,
            )

        # Add @search.action to each document
        for doc in documents:
            doc["@search.action"] = action

        logger.info(
            f"[{request_id}] Submitting {len(documents)} documents for indexing with action '{action}'"
        )

        # Build the index payload
        index_payload: dict[str, Any] = {"value": documents}

        # Execute indexing request
        index_start = time.time()
        timeout = aiohttp.ClientTimeout(total=AISEARCH_TIMEOUT_SECONDS)

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                cast(str, search_endpoint),
                headers={
                    "Content-Type": "application/json",
                    "api-key": search_api_key,
                },
                json=index_payload,
                timeout=timeout,
            ) as response,
        ):
            index_time = time.time() - index_start
            response_body = await response.json()

            # Check for partial failures (207 Multi-Status)
            if response.status == 207:
                # Some documents may have failed
                results = response_body.get("value", [])
                succeeded = sum(1 for r in results if r.get("status", False))
                failed = len(results) - succeeded

                total_time = time.time() - start_time
                logger.warning(
                    f"[{request_id}] Partial indexing success: {succeeded} succeeded, {failed} failed"
                )

                return func.HttpResponse(
                    body=json.dumps(
                        {
                            "message": "Partial indexing success",
                            "action": action,
                            "total_documents": len(documents),
                            "succeeded": succeeded,
                            "failed": failed,
                            "results": results,
                            "request_id": request_id,
                            "performance": {
                                "index_ms": round(index_time * 1000, 2),
                                "total_ms": round(total_time * 1000, 2),
                            },
                        }
                    ),
                    mimetype="application/json",
                    status_code=207,
                )

            # Check for errors
            if response.status >= 400:
                total_time = time.time() - start_time
                error_message = response_body.get("error", {}).get("message", str(response_body))
                logger.error(
                    f"[{request_id}] Indexing failed with status {response.status}: {error_message}"
                )

                return func.HttpResponse(
                    body=json.dumps(
                        {
                            "error": "Indexing failed",
                            "message": error_message,
                            "status_code": response.status,
                            "request_id": request_id,
                            "performance": {
                                "index_ms": round(index_time * 1000, 2),
                                "total_ms": round(total_time * 1000, 2),
                            },
                        }
                    ),
                    mimetype="application/json",
                    status_code=response.status,
                )

            # Success
            total_time = time.time() - start_time
            results = response_body.get("value", [])

            logger.info(
                f"[{request_id}] Indexing completed successfully: {len(documents)} documents indexed"
            )

            return func.HttpResponse(
                body=json.dumps(
                    {
                        "message": "Indexing completed successfully",
                        "action": action,
                        "total_documents": len(documents),
                        "results": results,
                        "request_id": request_id,
                        "performance": {
                            "index_ms": round(index_time * 1000, 2),
                            "total_ms": round(total_time * 1000, 2),
                        },
                    }
                ),
                mimetype="application/json",
                status_code=200,
            )

    except ValueError as e:
        logger.error(f"[{request_id}] Invalid JSON in request body: {str(e)}")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Invalid request body",
                    "message": "Please provide valid JSON with a 'value' array of documents",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )
    except aiohttp.ClientError as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] Azure AI Search indexing request failed after {total_time:.3f}s: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return func.HttpResponse(
            body=json.dumps(
                {
                    "error": "Azure AI Search indexing request failed",
                    "message": str(e),
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=502,
        )
    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] Azure AI Search indexing operation failed after {total_time:.3f}s: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return func.HttpResponse(
            body=json.dumps(
                {
                    "error": "Azure AI Search indexing operation failed",
                    "message": str(e),
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )


@app.route(route="extract_content", methods=["POST"])
@require_api_key
async def extract_content(req: func.HttpRequest) -> func.HttpResponse:
    """
    Extract content from documents or images using Azure Content Understanding service.

    Request body (JSON) - required only when operation_location is not provided:
    {
        "content": "<base64-encoded file content>",
        "content-type": "<optional MIME type for file type detection>"
    }

    Query parameters:
    - operation_location: Optional polling URL from a previous extraction job. When provided,
                          skips job submission and directly polls for results. acu_endpoint
                          and request body content become optional.
    - acu_endpoint: Azure Content Understanding endpoint URL (required if operation_location not provided)
    - acu_key: API key for ACU (can also be provided via X-ACU-Key header)
    - timeout: HTTP request timeout in seconds (default: DEFAULT_TIMEOUT_SECONDS)
    - polling_timeout: Maximum time to poll for results in seconds (default: 300)
    - polling_interval: Interval between polling attempts in seconds (default: 5)
    - min_chunk_size: Minimum characters per chunk for unknown file types (default: 10000)

    Returns:
    - pages: List of page objects with 'page_number' and 'content' keys
    - page_count: Total number of pages
    - file_type: Detected file type identifier
    - fields: Extracted fields/metadata from the document
    - normalized_entities: List of extracted entity strings
    """
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] Content extraction request initiated")

    try:
        # Extract Azure Content Understanding configuration from parameters
        acu_endpoint = req.params.get("acu_endpoint")
        operation_location_param = req.params.get("operation_location")

        # API key from header (preferred) or query parameter (fallback)
        headers = cast(dict[str, str], req.headers)
        acu_key = headers.get("X-ACU-Key") or req.params.get("acu_key")

        timeout_str = req.params.get("timeout")
        polling_timeout_str = req.params.get("polling_timeout", "300")
        polling_interval_str = req.params.get("polling_interval", "5")
        min_chunk_size_str = req.params.get("min_chunk_size", "10000")

        # Determine if we're resuming an existing job or starting a new one
        resume_mode = bool(operation_location_param)

        if resume_mode:
            # Resume mode: validate operation_location URL format
            is_valid, error_message = _validate_url_parameter(operation_location_param, "operation_location")
            if not is_valid:
                logger.warning(f"[{request_id}] Invalid operation_location: {error_message}")
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
            # API key is still required for polling
            if not acu_key:
                logger.warning(f"[{request_id}] Missing ACU API key for resume mode")
                return func.HttpResponse(
                    json.dumps(
                        {
                            "error": "Missing required parameters",
                            "message": "Please provide X-ACU-Key header (or acu_key param) for polling",
                            "request_id": request_id,
                        }
                    ),
                    mimetype="application/json",
                    status_code=400,
                )
            logger.info(f"[{request_id}] Resume mode: polling existing job at {operation_location_param}")
        else:
            # New job mode: validate required parameters
            if not acu_endpoint or not acu_key:
                logger.warning(f"[{request_id}] Missing required ACU parameters")
                return func.HttpResponse(
                    json.dumps(
                        {
                            "error": "Missing required parameters",
                            "message": "Please provide acu_endpoint and X-ACU-Key header (or acu_key param), or provide operation_location to resume an existing job",
                            "request_id": request_id,
                        }
                    ),
                    mimetype="application/json",
                    status_code=400,
                )

            # Validate acu_endpoint URL format
            is_valid, error_message = _validate_url_parameter(acu_endpoint, "acu_endpoint")
            if not is_valid:
                logger.warning(f"[{request_id}] Invalid acu_endpoint: {error_message}")
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

        # Parse timeout parameter (optional, defaults to DEFAULT_TIMEOUT_SECONDS)
        request_timeout = DEFAULT_TIMEOUT_SECONDS
        if timeout_str:
            try:
                request_timeout = float(timeout_str)
                if request_timeout <= 0:
                    raise ValueError("timeout must be greater than 0")
            except ValueError as e:
                logger.warning(f"[{request_id}] Invalid timeout parameter: {str(e)}")
                return func.HttpResponse(
                    json.dumps(
                        {
                            "error": "Invalid parameter",
                            "message": f"timeout must be a positive number: {str(e)}",
                            "request_id": request_id,
                        }
                    ),
                    mimetype="application/json",
                    status_code=400,
                )

        # Parse polling parameters
        try:
            polling_timeout = int(polling_timeout_str)
            polling_interval = int(polling_interval_str)
            if polling_timeout <= 0 or polling_interval <= 0:
                raise ValueError("Polling parameters must be greater than 0")
        except ValueError as e:
            logger.warning(f"[{request_id}] Invalid polling parameters: {str(e)}")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid parameter",
                        "message": f"polling_timeout and polling_interval must be positive integers: {str(e)}",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Parse min_chunk_size parameter (for sentence-based chunking of unknown file types)
        try:
            min_chunk_size = int(min_chunk_size_str)
            if min_chunk_size <= 0:
                raise ValueError("min_chunk_size must be greater than 0")
        except ValueError as e:
            logger.warning(f"[{request_id}] Invalid min_chunk_size parameter: {str(e)}")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid parameter",
                        "message": f"min_chunk_size must be a positive integer: {str(e)}",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Initialize variables for tracking
        submit_time = 0.0
        operation_location: str | None = None
        content_type: str | None = None

        if resume_mode:
            # Resume mode: use provided operation_location, skip document submission
            operation_location = operation_location_param
            logger.info(f"[{request_id}] Skipping job submission, using provided operation_location")

            # Try to extract content-type from request body if provided (optional)
            try:
                raw_body_bytes = req.get_body()
                if raw_body_bytes:
                    raw_body = raw_body_bytes.decode("utf-8")
                    req_body = json.loads(raw_body)
                    content_type = req_body.get("content-type")
                    if content_type:
                        logger.info(f"[{request_id}] Request content-type: {content_type}")
            except Exception:
                # Content-type is optional in resume mode, ignore errors
                pass
        else:
            # New job mode: get document content from request body
            # JSON format: {"content": "<base64-encoded content>"}
            document_content: bytes | None = None

            try:
                raw_body_bytes = req.get_body()

                if not raw_body_bytes:
                    logger.warning(f"[{request_id}] Validation failed: request body is empty")
                    return func.HttpResponse(
                        json.dumps(
                            {
                                "error": "Validation error",
                                "message": "Request body is empty",
                                "request_id": request_id,
                            }
                        ),
                        mimetype="application/json",
                        status_code=400,
                    )

                # Try to decode as UTF-8 and parse as JSON first
                try:
                    raw_body = raw_body_bytes.decode("utf-8")
                    req_body = json.loads(raw_body)

                    # JSON format with 'content' field containing base64-encoded data
                    document_content_base64 = req_body.get("content")

                    # Optional content-type field for logging purposes
                    content_type = req_body.get("content-type")
                    if content_type:
                        logger.info(f"[{request_id}] Request content-type: {content_type}")

                    if document_content_base64:
                        # Decode base64 content to binary
                        try:
                            document_content = base64.b64decode(document_content_base64)
                            logger.info(f"[{request_id}] Parsed JSON format with base64 content")
                        except Exception as e:
                            logger.warning(f"[{request_id}] Failed to decode base64 content: {str(e)}")
                            return func.HttpResponse(
                                json.dumps(
                                    {
                                        "error": "Validation error",
                                        "message": "The 'content' field must be valid base64-encoded content",
                                        "request_id": request_id,
                                    }
                                ),
                                mimetype="application/json",
                                status_code=400,
                            )
                    else:
                        # JSON but missing required 'content' field
                        logger.warning(f"[{request_id}] JSON body missing 'content' field")
                        return func.HttpResponse(
                            json.dumps(
                                {
                                    "error": "Validation error",
                                    "message": "JSON request body must contain 'content' field with base64-encoded data",
                                    "request_id": request_id,
                                }
                            ),
                            mimetype="application/json",
                            status_code=400,
                        )

                except (UnicodeDecodeError, json.JSONDecodeError) as e:
                    # Not valid UTF-8 or not valid JSON - return error for debugging
                    error_type = type(e).__name__
                    error_message = str(e)

                    # Try to get a preview of the body for debugging (first 500 bytes, safely encoded)
                    try:
                        body_preview = raw_body_bytes[:500].decode("utf-8", errors="replace")
                    except Exception:
                        body_preview = repr(raw_body_bytes[:500])

                    logger.warning(
                        f"[{request_id}] Failed to parse request body as JSON: {error_type}: {error_message}"
                    )
                    return func.HttpResponse(
                        json.dumps(
                            {
                                "error": "Invalid request body format",
                                "message": f"Request body must be valid JSON with 'content' field. Parse error: {error_message}",
                                "error_type": error_type,
                                "body_preview": body_preview,
                                "request_id": request_id,
                            }
                        ),
                        mimetype="application/json",
                        status_code=400,
                    )

            except Exception as e:
                logger.warning(f"[{request_id}] Failed to read request body: {str(e)}")
                return func.HttpResponse(
                    json.dumps(
                        {
                            "error": "Invalid request body",
                            "message": f"Failed to read request body: {str(e)}",
                            "request_id": request_id,
                        }
                    ),
                    mimetype="application/json",
                    status_code=400,
                )

            if not document_content:
                logger.warning(f"[{request_id}] Validation failed: no document content found")
                return func.HttpResponse(
                    json.dumps(
                        {
                            "error": "Validation error",
                            "message": "No document content found in request body",
                            "request_id": request_id,
                        }
                    ),
                    mimetype="application/json",
                    status_code=400,
                )

            logger.info(
                f"[{request_id}] Submitting content extraction job (size={len(document_content)} bytes)"
            )

            # STEP 1: Submit the analysis job
            submit_start = time.time()

            try:
                timeout = aiohttp.ClientTimeout(total=request_timeout)
                async with (
                    aiohttp.ClientSession() as session,
                    session.post(
                        acu_endpoint,
                        headers={
                            "Ocp-Apim-Subscription-Key": acu_key,
                            "Content-Type": "application/octet-stream",
                            "x-ms-useragent": "content-understanding-document-extraction",
                        },
                        data=document_content,
                        timeout=timeout,
                    ) as response,
                ):
                    response.raise_for_status()

                    # Get the Operation-Location header for polling
                    operation_location = response.headers.get("Operation-Location")

                    if not operation_location:
                        logger.error(
                            f"[{request_id}] ACU service did not return Operation-Location header"
                        )
                        return func.HttpResponse(
                            json.dumps(
                                {
                                    "error": "Service error",
                                    "message": "Azure Content Understanding service did not return polling URL",
                                    "request_id": request_id,
                                }
                            ),
                            mimetype="application/json",
                            status_code=500,
                        )

                    submit_time = time.time() - submit_start
                    logger.info(
                        f"[{request_id}] Content extraction job submitted (duration={submit_time:.3f}s, operation_location={operation_location})"
                    )

            except aiohttp.ClientError as e:
                submit_time = time.time() - submit_start
                logger.error(f"[{request_id}] Failed to submit ACU job: {str(e)}")
                return func.HttpResponse(
                    json.dumps(
                        {
                            "error": "Submission failed",
                            "message": f"Failed to submit content extraction job: {str(e)}",
                            "request_id": request_id,
                        }
                    ),
                    mimetype="application/json",
                    status_code=500,
                )

        # STEP 2: Poll for results
        logger.info(
            f"[{request_id}] Polling for results (timeout={polling_timeout}s, interval={polling_interval}s)"
        )

        poll_start = time.time()
        poll_attempts = 0
        poll_time = 0.0
        result_data: dict[str, Any] | None = None

        try:
            timeout_obj = aiohttp.ClientTimeout(total=request_timeout)
            async with aiohttp.ClientSession() as session:
                while True:
                    poll_attempts += 1
                    elapsed = time.time() - poll_start

                    # Check if we've exceeded the polling timeout
                    if elapsed > polling_timeout:
                        logger.warning(
                            f"[{request_id}] Polling timeout exceeded after {poll_attempts} attempts"
                        )
                        return func.HttpResponse(
                            json.dumps(
                                {
                                    "error": "Timeout",
                                    "message": f"Content extraction timed out after {polling_timeout} seconds",
                                    "request_id": request_id,
                                    "poll_attempts": poll_attempts,
                                }
                            ),
                            mimetype="application/json",
                            status_code=408,
                        )

                    async with session.get(
                        operation_location,
                        headers={
                            "Ocp-Apim-Subscription-Key": acu_key,
                        },
                        timeout=timeout_obj,
                    ) as poll_response:
                        poll_response.raise_for_status()
                        poll_data_raw = await poll_response.json()
                        poll_data = cast(dict[str, Any], poll_data_raw)

                        status = poll_data.get("status", "").lower()

                        logger.info(f"[{request_id}] Poll attempt {poll_attempts}: status={status}")

                        if status == "succeeded":
                            result_data = poll_data
                            poll_time = time.time() - poll_start
                            logger.info(
                                f"[{request_id}] Content extraction completed (duration={poll_time:.3f}s, attempts={poll_attempts})"
                            )
                            break

                        if status == "failed":
                            error_info = poll_data.get("error", {})
                            logger.error(f"[{request_id}] Content extraction failed: {error_info}")
                            return func.HttpResponse(
                                json.dumps(
                                    {
                                        "error": "Extraction failed",
                                        "message": "Azure Content Understanding service reported failure",
                                        "details": error_info,
                                        "request_id": request_id,
                                    }
                                ),
                                mimetype="application/json",
                                status_code=500,
                            )

                        if status in ["running", "notstarted"]:
                            # Wait before next poll
                            await asyncio.sleep(polling_interval)
                        else:
                            logger.warning(f"[{request_id}] Unknown status: {status}")
                            await asyncio.sleep(polling_interval)

        except aiohttp.ClientError as e:
            poll_time = time.time() - poll_start
            logger.error(f"[{request_id}] Polling failed: {str(e)}")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Polling failed",
                        "message": f"Failed to poll content extraction results: {str(e)}",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=500,
            )

        # Extract content and fields from result
        if not result_data:
            logger.error(f"[{request_id}] No result data available after polling")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "No results",
                        "message": "Content extraction completed but no results were returned",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=500,
            )

        # Extract content_markdown, fields, and page count from the result
        # Structure: result_data.result.contents[] where each content has kind, fields, markdown
        result_obj = result_data.get("result", {})
        contents = result_obj.get("contents", [])

        # Extract fields from the first content item with fields (typically kind="document" at page 0)
        fields: dict[str, Any] = {}
        content_markdown_parts: list[str] = []
        total_pages = 0

        for content_item in contents:
            # Extract fields if present
            if "fields" in content_item and not fields:
                fields = content_item.get("fields", {})

            # Extract markdown content if present
            if "markdown" in content_item:
                content_markdown_parts.append(content_item.get("markdown", ""))

            # Track max page number to determine total pages
            end_page = content_item.get("endPageNumber", 0)
            if end_page > total_pages:
                total_pages = end_page

        # Combine all markdown parts
        content_markdown = "\n\n".join(content_markdown_parts)

        # Also check usage.documentPages for accurate page count
        usage = result_data.get("usage", {})
        document_pages = usage.get("documentPages", total_pages)
        if document_pages > total_pages:
            total_pages = document_pages

        # Normalize entities: extract valueString from each entity in the entities array
        normalized_entities: list[str] = []
        entities_field = fields.get("entities", {})
        if entities_field.get("type") == "array":
            value_array = entities_field.get("valueArray", [])
            for entity_item in value_array:
                if isinstance(entity_item, dict) and "valueString" in entity_item:
                    normalized_entities.append(entity_item["valueString"])

        # Normalize fields: extract valueString from each field and remove entities
        normalized_fields: dict[str, Any] = {}
        for field_name, field_value in fields.items():
            # Skip entities field since we already have normalized_entities
            if field_name == "entities":
                continue
            # Extract valueString if the field has the expected structure
            if isinstance(field_value, dict) and "valueString" in field_value:
                value_string = field_value["valueString"]
                # Only add if valueString has data (not empty or None)
                if value_string:
                    normalized_fields[field_name] = value_string
            elif field_value:
                # Keep the original value if it doesn't match the expected structure and has data
                normalized_fields[field_name] = field_value

        # Detect file type and paginate content
        file_type = _detect_file_type(content_type)
        logger.info(f"[{request_id}] Detected file type: {file_type} (content_type: {content_type})")

        # Paginate the markdown content based on file type
        paginated_pages = _paginate_markdown_content(content_markdown, file_type, request_id, min_chunk_size)

        total_time = time.time() - start_time

        logger.info(
            f"[{request_id}] Content extraction successful (content_length={len(content_markdown)}, fields_count={len(normalized_fields)}, pages={len(paginated_pages)}, entities={len(normalized_entities)})"
        )

        return func.HttpResponse(
            body=json.dumps(
                {
                    "markdown": content_markdown,
                    "pages": paginated_pages,
                    "page_count": len(paginated_pages),
                    "file_type": file_type,
                    "fields": normalized_fields,
                    "entities": normalized_entities,
                    "request_id": request_id,
                    "operation_location": operation_location,
                    "performance": {
                        "submit_ms": round(submit_time * 1000, 2),
                        "poll_ms": round(poll_time * 1000, 2),
                        "total_ms": round(total_time * 1000, 2),
                        "poll_attempts": poll_attempts,
                    },
                }
            ),
            mimetype="application/json",
            status_code=200,
        )

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] Content extraction operation failed after {total_time:.3f}s: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return func.HttpResponse(
            body=json.dumps(
                {
                    "error": "Content extraction operation failed",
                    "message": str(e),
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )
