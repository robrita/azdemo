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
import cv2
import fitz  # PyMuPDF  # type: ignore[import-untyped]
import numpy as np
import numpy.typing as npt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure structured logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress verbose Azure SDK logging
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Configuration constants
MAX_REQUEST_SIZE_MB = int(os.getenv("MAX_REQUEST_SIZE_MB", "10"))
MAX_REQUEST_SIZE_BYTES = MAX_REQUEST_SIZE_MB * 1024 * 1024
AISEARCH_TIMEOUT_SECONDS = int(os.getenv("AISEARCH_TIMEOUT_SECONDS", "60"))

# Signature comparison constants
SIGNATURE_NORMALIZED_WIDTH = 300
SIGNATURE_NORMALIZED_HEIGHT = 150
ALLOWED_FILE_TYPES = {".png", ".jpg", ".jpeg", ".pdf"}


def _generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())[:8]


def _load_image_from_bytes(image_bytes: bytes, filename: str) -> Any:
    """
    Load image from bytes, handling both regular images and PDFs.

    Args:
        image_bytes: Raw file bytes
        filename: Original filename to determine file type

    Returns:
        numpy array (OpenCV format) or None if loading fails
    """
    file_ext = os.path.splitext(filename.lower())[1]

    try:
        if file_ext == ".pdf":
            # Extract first page of PDF as image
            pdf_document: Any = fitz.open(stream=image_bytes, filetype="pdf")
            if pdf_document.page_count == 0:
                return None

            # Render first page to image (150 DPI)
            page: Any = pdf_document[0]
            pix: Any = page.get_pixmap(dpi=150)
            img_bytes: bytes = pix.tobytes("png")

            # Convert to numpy array
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        # Load regular image formats
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def _extract_signatures(image: Any, debug_prefix: str = "") -> list[Any]:
    """
    Extract signature regions from an image using contour detection.

    Args:
        image: Input image as numpy array (OpenCV format)
        debug_prefix: Optional prefix for saved debug images (e.g., "valid_id", "specimen")

    Returns:
        List of extracted signature images as numpy arrays
    """
    # Convert to grayscale
    gray: Any = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)  # type: ignore[assignment]

    # Apply Gaussian blur to reduce noise
    blurred: Any = cv2.GaussianBlur(gray, (5, 5), 0)  # type: ignore[arg-type]

    # Apply adaptive thresholding
    thresh: Any = cv2.adaptiveThreshold(  # type: ignore[assignment]
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2  # type: ignore[arg-type]
    )

    # Find contours
    contours_result: Any = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)  # type: ignore[arg-type]
    contours: Any = contours_result[0]  # type: ignore[assignment]

    # Filter contours by area and aspect ratio (typical signature characteristics)
    min_area = 500
    signatures: list[Any] = []

    for contour in contours:  # type: ignore[attr-defined]
        area = cv2.contourArea(contour)  # type: ignore[arg-type]
        if area < min_area:
            continue

        x, y, w, h = cv2.boundingRect(contour)  # type: ignore[arg-type]
        aspect_ratio = w / float(h) if h > 0 else 0

        # Signatures typically have aspect ratio between 1.5 and 5.0
        if 1.5 <= aspect_ratio <= 5.0 and w > 50 and h > 20:
            # Extract signature region with some padding
            padding = 10
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(image.shape[1], x + w + padding)
            y2 = min(image.shape[0], y + h + padding)

            signature_img = image[y1:y2, x1:x2]
            signatures.append(signature_img)

    # Sort by area (largest first) and return top 3
    signatures.sort(key=lambda s: s.shape[0] * s.shape[1], reverse=True)
    top_signatures = signatures[:3]

    # Save extracted signatures for local debugging (only in local development)
    enable_local = os.getenv("ENABLE_LOCAL", "false").lower() == "true"
    if debug_prefix and enable_local:
        try:
            tmp_dir = "./tmp"
            os.makedirs(tmp_dir, exist_ok=True)
            timestamp = str(int(time.time() * 1000))
            for idx, sig_img in enumerate(top_signatures):
                filename = f"{tmp_dir}/{debug_prefix}_sig_{idx + 1}_{timestamp}.png"
                cv2.imwrite(filename, sig_img)  # type: ignore[arg-type]
                logger.debug(f"Saved debug signature: {filename}")
        except Exception as e:
            # Don't fail the request if debug saving fails
            logger.warning(f"Failed to save debug signature: {str(e)}")

    return top_signatures


def _normalize_signature(signature: Any, debug_prefix: str = "", index: int = 0) -> Any:
    """
    Normalize a signature image for consistent comparison.

    Args:
        signature: Input signature image as numpy array
        debug_prefix: Optional prefix for saved debug images (e.g., "valid_id", "specimen")
        index: Index of the signature for unique naming

    Returns:
        Normalized signature image
    """
    # Resize to standard dimensions
    normalized: Any = cv2.resize(  # type: ignore[assignment]
        signature, (SIGNATURE_NORMALIZED_WIDTH, SIGNATURE_NORMALIZED_HEIGHT)
    )

    # Convert to grayscale if needed
    if len(normalized.shape) == 3:  # type: ignore[arg-type]  # type: ignore[arg-type]
        normalized = cv2.cvtColor(normalized, cv2.COLOR_BGR2GRAY)  # type: ignore[arg-type,assignment]

    # Apply histogram equalization for consistent contrast
    normalized = cv2.equalizeHist(normalized)  # type: ignore[arg-type,assignment]

    # Convert back to BGR for CLIP model (expects 3 channels)
    normalized = cv2.cvtColor(normalized, cv2.COLOR_GRAY2BGR)  # type: ignore[arg-type,assignment]

    # Save normalized signature for local debugging (only in local development)
    enable_local = os.getenv("ENABLE_LOCAL", "false").lower() == "true"
    if debug_prefix and enable_local:
        try:
            tmp_dir = "./tmp"
            os.makedirs(tmp_dir, exist_ok=True)
            timestamp = str(int(time.time() * 1000))
            filename = f"{tmp_dir}/{debug_prefix}_normalized_{index}_{timestamp}.png"
            cv2.imwrite(filename, normalized)  # type: ignore[arg-type]
            logger.debug(f"Saved normalized signature: {filename}")
        except Exception as e:
            # Don't fail the request if debug saving fails
            logger.warning(f"Failed to save normalized signature: {str(e)}")

    return normalized  # type: ignore[return-value]


def _extract_image_features(image: Any) -> list[float]:
    """
    Extract feature vector from image using OpenCV.
    Uses HOG (Histogram of Oriented Gradients) and pixel intensity features.

    Args:
        image: Input image as numpy array (OpenCV format)

    Returns:
        Feature vector as list of floats
    """
    # Convert to grayscale
    gray: Any = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image  # type: ignore[assignment]

    # Calculate HOG features
    win_size = (gray.shape[1] // 16 * 16, gray.shape[0] // 16 * 16)  # type: ignore[attr-defined]
    if win_size[0] < 16 or win_size[1] < 16:  # type: ignore[misc]
        win_size = (64, 64)
        gray = cv2.resize(gray, win_size)  # type: ignore[assignment]

    hog = cv2.HOGDescriptor(
        win_size,  # type: ignore[arg-type]
        (16, 16),  # block size
        (8, 8),    # block stride
        (8, 8),    # cell size
        9          # number of bins
    )
    hog_features_raw: Any = hog.compute(gray)  # type: ignore[arg-type]

    # Flatten and normalize HOG features
    hog_vector: npt.NDArray[np.floating[Any]] = np.array(hog_features_raw).flatten()
    hog_vector = hog_vector / (np.linalg.norm(hog_vector) + 1e-8)

    # Calculate histogram features (additional texture information)
    hist_raw: Any = cv2.calcHist([gray], [0], None, [64], [0, 256])  # type: ignore[list-item]
    hist: npt.NDArray[np.floating[Any]] = np.array(hist_raw)
    hist = hist.flatten()
    hist = hist / (np.sum(hist) + 1e-8)

    # Combine features
    combined_features = np.concatenate([hog_vector, hist])

    return combined_features.tolist()


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    Calculate cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity score (0 to 1, where 1 is identical)
    """
    arr1 = np.array(vec1)
    arr2 = np.array(vec2)

    # Calculate cosine similarity
    dot_product = np.dot(arr1, arr2)
    norm1 = np.linalg.norm(arr1)
    norm2 = np.linalg.norm(arr2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


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
    start_time = time.time()
    logger.info(f"[{request_id}] Health check endpoint invoked")

    total_time = time.time() - start_time

    health_status: dict[str, Any] = {
        "status": "healthy",
        "timestamp": time.time(),
        "request_id": request_id,
        "performance": {
            "total_ms": round(total_time * 1000, 2),
        },
    }

    return func.HttpResponse(
        json.dumps(health_status),
        mimetype="application/json",
        status_code=200,
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


@app.route(route="compare_signatures", methods=["POST"])
@require_api_key
async def compare_signatures(req: func.HttpRequest) -> func.HttpResponse:
    """
    Compare signatures between specimen signatures on ID and selfie with ID.

    Accepts multipart/form-data with 3 files:
    - valid_id: Image of valid ID (front)
    - specimen_signatures: Image of valid ID with 3 specimen signatures
    - selfie_with_id: Selfie photo holding valid ID

    Returns similarity scores between signatures using computer vision features.
    """
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] Signature comparison request initiated")

    try:
        # Parse multipart form data
        files = req.files

        # Validate required files
        required_files = ["valid_id", "specimen_signatures"]
        for file_key in required_files:
            if file_key not in files:
                logger.warning(f"[{request_id}] Missing required file: {file_key}")
                return func.HttpResponse(
                    json.dumps({
                        "error": "Missing required files",
                        "message": f"Please provide all required files: {', '.join(required_files)}",
                        "request_id": request_id,
                    }),
                    mimetype="application/json",
                    status_code=400,
                )

        # Load and validate files
        valid_id_file = files["valid_id"]
        specimen_file = files["specimen_signatures"]
        selfie_file = files.get("selfie_with_id")

        # Validate file types
        files_to_validate = [
            (valid_id_file, "valid_id"),
            (specimen_file, "specimen_signatures"),
        ]
        if selfie_file:
            files_to_validate.append((selfie_file, "selfie_with_id"))
        
        for file_obj, name in files_to_validate:
            filename = file_obj.filename or ""
            file_ext = os.path.splitext(filename.lower())[1]
            if file_ext not in ALLOWED_FILE_TYPES:
                logger.warning(f"[{request_id}] Invalid file type for {name}: {file_ext}")
                return func.HttpResponse(
                    json.dumps({
                        "error": "Invalid file type",
                        "message": f"{name} must be one of: {', '.join(ALLOWED_FILE_TYPES)}",
                        "request_id": request_id,
                    }),
                    mimetype="application/json",
                    status_code=400,
                )

        logger.info(f"[{request_id}] Loading images from uploaded files")

        # Load images
        valid_id_bytes = valid_id_file.read()
        specimen_bytes = specimen_file.read()
        selfie_bytes = selfie_file.read() if selfie_file else None

        valid_id_img = _load_image_from_bytes(valid_id_bytes, valid_id_file.filename or "valid_id")
        specimen_img = _load_image_from_bytes(specimen_bytes, specimen_file.filename or "specimen_signatures")
        selfie_img = _load_image_from_bytes(selfie_bytes, selfie_file.filename or "selfie_with_id") if selfie_file and selfie_bytes else None

        if valid_id_img is None or specimen_img is None:
            logger.error(f"[{request_id}] Failed to load one or more images")
            return func.HttpResponse(
                json.dumps({
                    "error": "Image loading failed",
                    "message": "Failed to load one or more uploaded images. Please check file format.",
                    "request_id": request_id,
                }),
                mimetype="application/json",
                status_code=400,
            )

        # Extract signatures from images
        extraction_start = time.time()
        logger.info(f"[{request_id}] Extracting signatures from images")

        valid_id_signatures = _extract_signatures(valid_id_img, f"{request_id}_valid_id")
        specimen_signatures = _extract_signatures(specimen_img, f"{request_id}_specimen")
        selfie_signatures = _extract_signatures(selfie_img, f"{request_id}_selfie") if selfie_img is not None else []

        extraction_time = time.time() - extraction_start

        logger.info(
            f"[{request_id}] Extracted signatures: valid_id={len(valid_id_signatures)}, "
            f"specimen={len(specimen_signatures)}, selfie={len(selfie_signatures)}"
        )

        if len(specimen_signatures) < 3:
            logger.warning(f"[{request_id}] Expected 3 specimen signatures, found {len(specimen_signatures)}")
            return func.HttpResponse(
                json.dumps({
                    "error": "Insufficient specimen signatures",
                    "message": f"Expected 3 specimen signatures, found only {len(specimen_signatures)}. "
                               "Please ensure the image clearly shows 3 specimen signatures.",
                    "request_id": request_id,
                }),
                mimetype="application/json",
                status_code=400,
            )

        # Normalize all signatures
        normalization_start = time.time()
        logger.info(f"[{request_id}] Normalizing signatures")

        normalized_specimen = [_normalize_signature(sig, f"{request_id}_specimen", i) for i, sig in enumerate(specimen_signatures[:3])]
        normalized_valid_id = [_normalize_signature(sig, f"{request_id}_valid_id", i) for i, sig in enumerate(valid_id_signatures)] if valid_id_signatures else []
        normalized_selfie = [_normalize_signature(sig, f"{request_id}_selfie", i) for i, sig in enumerate(selfie_signatures)] if selfie_signatures else []

        normalization_time = time.time() - normalization_start

        # Extract features from all signatures (using OpenCV - no external API needed)
        feature_start = time.time()
        logger.info(f"[{request_id}] Extracting image features")
        # # this is for debugging purposes only
        # if normalized_valid_id:
        #     raise Exception("this is for debugging purposes only")

        # Extract features using OpenCV (runs locally, no API calls)
        specimen_features = [_extract_image_features(sig) for sig in normalized_specimen]
        valid_id_features = [_extract_image_features(sig) for sig in normalized_valid_id]
        selfie_features = [_extract_image_features(sig) for sig in normalized_selfie]

        feature_time = time.time() - feature_start

        # Calculate similarities
        similarity_start = time.time()
        logger.info(f"[{request_id}] Calculating similarity scores")

        # 1. Check if specimen signatures match each other
        specimen_similarity_matrix: list[list[float]] = []
        for i in range(3):
            row: list[float] = []
            for j in range(3):
                if i == j:
                    row.append(1.0)
                else:
                    similarity = _cosine_similarity(specimen_features[i], specimen_features[j])
                    row.append(round(similarity, 4))
            specimen_similarity_matrix.append(row)

        # Average similarity between specimen signatures
        specimen_avg_similarity = sum(
            specimen_similarity_matrix[i][j]
            for i in range(3)
            for j in range(i + 1, 3)
        ) / 3

        # 2. Compare specimen signatures against valid ID signature(s)
        valid_id_similarities: list[float] = []
        if valid_id_features:
            for spec_feat in specimen_features:
                best_match = max(
                    _cosine_similarity(spec_feat, id_feat) for id_feat in valid_id_features
                )
                valid_id_similarities.append(round(best_match, 4))

        # 3. Compare specimen signatures against selfie signature(s)
        selfie_similarities: list[float] = []
        if selfie_features:
            for spec_feat in specimen_features:
                best_match = max(
                    _cosine_similarity(spec_feat, selfie_feat) for selfie_feat in selfie_features
                )
                selfie_similarities.append(round(best_match, 4))

        similarity_time = time.time() - similarity_start
        total_time = time.time() - start_time

        # Prepare response
        result: dict[str, Any] = {
            "request_id": request_id,
            "specimen_signatures_count": 3,
            "valid_id_signatures_count": len(valid_id_signatures),
            "selfie_signatures_count": len(selfie_signatures),
            "specimen_internal_consistency": {
                "similarity_matrix": specimen_similarity_matrix,
                "average_similarity": round(specimen_avg_similarity, 4),
                "status": "MATCH" if specimen_avg_similarity >= 0.85 else "MISMATCH",
            },
            "specimen_vs_valid_id": {
                "similarities": valid_id_similarities,
                "average_similarity": round(sum(valid_id_similarities) / len(valid_id_similarities), 4) if valid_id_similarities else 0.0,
                "status": "MATCH" if valid_id_similarities and sum(valid_id_similarities) / len(valid_id_similarities) >= 0.80 else "MISMATCH",
            } if valid_id_similarities else {"status": "NO_SIGNATURE_FOUND"},
            "specimen_vs_selfie": {
                "similarities": selfie_similarities,
                "average_similarity": round(sum(selfie_similarities) / len(selfie_similarities), 4) if selfie_similarities else 0.0,
                "status": "MATCH" if selfie_similarities and sum(selfie_similarities) / len(selfie_similarities) >= 0.80 else "MISMATCH",
            } if selfie_similarities else {"status": "NO_SIGNATURE_FOUND"},
            "performance": {
                "extraction_ms": round(extraction_time * 1000, 2),
                "normalization_ms": round(normalization_time * 1000, 2),
                "feature_extraction_ms": round(feature_time * 1000, 2),
                "similarity_ms": round(similarity_time * 1000, 2),
                "total_ms": round(total_time * 1000, 2),
            },
        }

        logger.info(
            f"[{request_id}] Signature comparison completed: "
            f"specimen_consistency={specimen_avg_similarity:.4f}, "
            f"valid_id_match={sum(valid_id_similarities) / len(valid_id_similarities) if valid_id_similarities else 0:.4f}, "
            f"selfie_match={sum(selfie_similarities) / len(selfie_similarities) if selfie_similarities else 0:.4f}"
        )

        return func.HttpResponse(
            json.dumps(result),
            mimetype="application/json",
            status_code=200,
        )

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] Signature comparison failed after {total_time:.3f}s: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return func.HttpResponse(
            json.dumps({
                "error": "Signature comparison failed",
                "message": str(e),
                "request_id": request_id,
            }),
            mimetype="application/json",
            status_code=500,
        )
