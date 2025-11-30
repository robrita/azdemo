import asyncio
import base64
import io
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
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
from openai import AzureOpenAI
from PIL import Image

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

# Signature comparison constants
SIGNATURE_NORMALIZED_WIDTH = 300
SIGNATURE_NORMALIZED_HEIGHT = 150
ALLOWED_FILE_TYPES = {".png", ".jpg", ".jpeg", ".pdf"}

# Azure Document Intelligence configuration (optional)
AZURE_DI_ENDPOINT = os.getenv("AZURE_DI_ENDPOINT")
AZURE_DI_KEY = os.getenv("AZURE_DI_KEY")
AZURE_DI_MODEL_ID = os.getenv("AZURE_DI_MODEL_ID", "prebuilt-layout")
PDF_RENDER_DPI = 200  # DPI for PDF rendering
PADDING_PIXELS = 4  # Extra padding around crop

# Azure OpenAI configuration (for vision-based signature extraction)
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
AZURE_OPENAI_MODEL = os.getenv("AZURE_OPENAI_MODEL", "gpt-4.1")

# OpenCV post-processing configuration
LAPSRN_MODEL_PATH = os.getenv("LAPSRN_MODEL_PATH", "./LapSRN_x2.pb")

# Azure Face API configuration (for face detection and masking)
AZURE_FACE_API_KEY = os.getenv("AZURE_FACE_API_KEY")
AZURE_FACE_ENDPOINT = os.getenv("AZURE_FACE_ENDPOINT")
FACE_API_TIMEOUT_SECONDS = int(os.getenv("FACE_API_TIMEOUT_SECONDS", "60"))

# Signature extraction prompt for Azure OpenAI Vision API
SIGNATURE_EXTRACTION_PROMPT = """
Look for the owner handwritten signature from this image. It may look like unreadable cursive black ink strokes close to the ID owner headshot. Tell me the exact location.

## Output Format

Provide your response in the following JSON structure:

```json
{
  "signatures_found": <number>,
  "signatures": [
    {
      "id": 1,
      "location_description": "<descriptive location>",
      "bounding_box": {
        "x": <percentage from left>,
        "y": <percentage from top>,
        "width": <percentage of image width>,
        "height": <percentage of image height>
      },
      "confidence": "<High|Medium|Low>",
      "characteristics": "<description>",
      "legible": <true|false>,
      "estimated_name": "<name if legible, otherwise null>",
      "is_owner_signature": <true|false>
    }
  ],
  "analysis_notes": "<any additional observations>"
}
```
"""

# Client singleton cache
_openai_client: AzureOpenAI | None = None


def _generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())[:8]


def _get_openai_client() -> AzureOpenAI:
    """
    Get or create singleton Azure OpenAI client instance.
    Uses module-level cache to prevent resource exhaustion.

    Returns:
        AzureOpenAI client instance

    Raises:
        ValueError: If Azure OpenAI credentials are not configured
    """
    global _openai_client

    if _openai_client is None:
        if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
            raise ValueError(
                "Azure OpenAI is not configured. Please set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT environment variables."
            )

        _openai_client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
        )
        logger.info("Initialized Azure OpenAI client singleton")

    return _openai_client


async def _extract_signature_with_openai(
    image_bytes: bytes, request_id: str, model: str | None = None, prompt: str | None = None
) -> dict[str, Any]:
    """
    Extract handwritten signatures from an image using Azure OpenAI Vision API.
    Uses asyncio.to_thread to wrap the synchronous OpenAI SDK call.

    Args:
        image_bytes: Image file bytes (PNG, JPG, etc.)
        request_id: Request ID for logging
        model: Azure OpenAI model deployment name (defaults to AZURE_OPENAI_MODEL)
        prompt: Custom prompt for signature extraction (defaults to SIGNATURE_EXTRACTION_PROMPT)

    Returns:
        Dictionary containing signature extraction results with structure:
        {
            "signatures_found": int,
            "signatures": [{"id": int, "bounding_box": {...}, ...}],
            "analysis_notes": str
        }

    Raises:
        ValueError: If OpenAI is not configured
        Exception: If API call fails
    """
    if model is None:
        model = AZURE_OPENAI_MODEL

    # Get OpenAI client (singleton pattern)
    client = _get_openai_client()

    # Encode image to base64
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    # Use custom prompt if provided, otherwise use default
    selected_prompt = prompt if prompt else SIGNATURE_EXTRACTION_PROMPT

    # Wrap synchronous OpenAI call in asyncio.to_thread for non-blocking execution
    def _call_openai() -> dict[str, Any]:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing documents and detecting handwritten signatures. Always respond with valid JSON.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": selected_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
            timeout=60,
        )

        # Extract and parse response
        content = response.choices[0].message.content

        # Handle None content
        if content is None:
            return {
                "signatures_found": 0,
                "signatures": [],
                "analysis_notes": "No content returned from API",
            }

        # Try to extract JSON from response (in case it's wrapped in markdown)
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()
        elif "```" in content:
            json_start = content.find("```") + 3
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()

        result: dict[str, Any] = json.loads(content)
        return result

    logger.info(f"[{request_id}] Calling Azure OpenAI Vision API for signature extraction")
    result = await asyncio.to_thread(_call_openai)
    logger.info(
        f"[{request_id}] Azure OpenAI returned {result.get('signatures_found', 0)} signature(s)"
    )

    return result


def _opencv_crop_signature(
    image_bytes: bytes, request_id: str
) -> tuple[bytes, list[dict[str, Any]]]:
    """
    Crop the signature region from an image using OpenCV contour detection.
    Uses adaptive thresholding, morphological operations, and contour filtering
    to isolate the handwritten signature.

    Implementation follows crop_signatures_opencv() from signature_extraction_opencv.ipynb:
    - Extracts individual signature regions with padding
    - Sorts by area and keeps top 3 candidates
    - Returns largest signature by area (or combined image for multiple signatures)

    All processing is done in-memory (serverless-compatible).

    Args:
        image_bytes: PNG image bytes
        request_id: Request ID for logging

    Returns:
        Tuple of:
        - Cropped PNG image bytes containing the signature region(s)
        - List of OpenCV-extracted signatures with structure:
          [{"content": str}, ...] where content is base64-encoded PNG image

    Raises:
        ValueError: If image processing fails or no signature found
    """
    # Load image from bytes
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Failed to decode image bytes")

    img_height, img_width = image.shape[:2]
    logger.info(f"[{request_id}] OpenCV signature cropping: input size {img_width}x{img_height}")

    # Convert to grayscale
    gray: Any = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply Gaussian blur to reduce noise
    blurred: Any = cv2.GaussianBlur(gray, (5, 5), 0)

    # Apply adaptive thresholding
    thresh: Any = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11,
        2,
    )

    # Find contours
    contours_result: Any = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours: Any = contours_result[0]

    # Filter contours by area and aspect ratio (typical signature characteristics)
    min_area = 500
    original_image_area = img_width * img_height
    signatures: list[dict[str, Any]] = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = w / float(h) if h > 0 else 0

        # Signatures typically have aspect ratio between 1.5 and 5.0
        if 1.5 <= aspect_ratio <= 5.0 and w > 50 and h > 20:
            # Extract signature region with padding
            padding = 10
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(img_width, x + w + padding)
            y2 = min(img_height, y + h + padding)

            # Calculate cropped area (with padding) for size filtering
            cropped_width = x2 - x1
            cropped_height = y2 - y1
            cropped_area = cropped_width * cropped_height

            signature_img = image[y1:y2, x1:x2]
            signatures.append({
                "image": signature_img,
                "bbox": (x1, y1, x2, y2),
                "area": area,
                "cropped_area": cropped_area,
                "aspect_ratio": aspect_ratio,
            })

    # If no valid contours found, return original image with empty bounding boxes
    if not signatures:
        logger.warning(f"[{request_id}] No signature contours found, returning original image")
        return image_bytes, []

    logger.info(f"[{request_id}] Detected {len(signatures)} signature candidate(s)")

    # When multiple signatures are detected, filter out those that are too small or too large
    # relative to the original image size (< 25% or > 80%)
    if len(signatures) > 1:
        min_size_ratio = 0.25
        max_size_ratio = 0.80

        filtered_signatures = [
            sig for sig in signatures
            if min_size_ratio <= (sig["cropped_area"] / original_image_area) <= max_size_ratio
        ]

        excluded_count = len(signatures) - len(filtered_signatures)
        if excluded_count > 0:
            logger.info(
                f"[{request_id}] Excluded {excluded_count} signature(s) outside size range "
                f"({min_size_ratio * 100:.0f}%-{max_size_ratio * 100:.0f}% of original image)"
            )

        # Only use filtered list if we still have at least one signature
        if filtered_signatures:
            signatures = filtered_signatures
        else:
            logger.warning(
                f"[{request_id}] All signatures were filtered out by size constraint, "
                f"keeping original {len(signatures)} signature(s)"
            )

    # Sort by area (largest first) and keep top 3
    signatures.sort(key=lambda s: s["area"], reverse=True)
    top_signatures = signatures[:3]

    logger.info(
        f"[{request_id}] Keeping top {len(top_signatures)} signature(s) by area"
    )

    # If there are 2 or more signatures, combine them vertically with index labels
    if len(signatures) >= 2:
        logger.info(f"[{request_id}] Multiple signatures detected, combining vertically with 100px padding")

        # Convert OpenCV images to PIL for easier combining
        pil_images = []
        for sig in signatures:
            # Convert BGR to RGB for PIL
            rgb_img = cv2.cvtColor(sig["image"], cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_img)
            pil_images.append(pil_img)

        # Calculate canvas dimensions
        # Reserve space on the left for index numbers (120px margin for 48pt font)
        index_margin = 120
        max_img_width = max(img.width for img in pil_images)
        padding = 100
        total_height = sum(img.height for img in pil_images) + padding * (len(pil_images) - 1)
        canvas_width = index_margin + max_img_width

        logger.info(
            f"[{request_id}] Canvas size: {canvas_width}x{total_height} "
            f"({len(pil_images)} signatures with {padding}px padding, {index_margin}px index margin)"
        )

        # Create white canvas (RGB mode)
        combined_canvas = Image.new("RGB", (canvas_width, total_height), (255, 255, 255))

        # Import ImageDraw and ImageFont for drawing index numbers
        from PIL import ImageDraw, ImageFont

        draw = ImageDraw.Draw(combined_canvas)

        # Use Pillow's bundled font (Aileron Regular) - works in serverless environments
        # Pillow 10.1+ bundles this font and supports the size parameter
        font_size = 48
        font = ImageFont.load_default(size=font_size)
        logger.info(f"[{request_id}] Using Pillow bundled font (Aileron) at size {font_size}")

        # Paste each signature right-aligned with index number on the left
        current_y = 0
        for idx, pil_img in enumerate(pil_images):
            # Right-align: place image at the rightmost position
            x_offset = canvas_width - pil_img.width
            combined_canvas.paste(pil_img, (x_offset, current_y))

            # Draw index number on the left side, vertically centered with the signature
            index_text = str(idx)
            # Get text bounding box for centering
            text_bbox = draw.textbbox((0, 0), index_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            # Center the index number vertically with the signature image
            # and place it in the left margin area
            text_x = (index_margin - text_width) // 2
            text_y = current_y + (pil_img.height - text_height) // 2

            # Draw the index number in RED with stroke to simulate bold effect
            # stroke_width adds thickness to the text, making it appear bold
            draw.text(
                (text_x, text_y),
                index_text,
                fill=(255, 0, 0),
                font=font,
                stroke_width=3,
                stroke_fill=(255, 0, 0),
            )

            logger.info(
                f"[{request_id}] Pasted signature {idx}/{len(pil_images) - 1}: "
                f"size={pil_img.width}x{pil_img.height}, position=({x_offset}, {current_y}), "
                f"index at ({text_x}, {text_y})"
            )

            current_y += pil_img.height + padding

        # Convert back to OpenCV format
        cropped_img = cv2.cvtColor(np.array(combined_canvas), cv2.COLOR_RGB2BGR)

        logger.info(
            f"[{request_id}] Combined signature: output_size={cropped_img.shape[1]}x{cropped_img.shape[0]}"
        )

        # Build opencv_signatures list with base64 content for each signature
        opencv_signatures = []
        for idx, sig in enumerate(signatures):
            # Encode individual signature image to base64
            sig_success, sig_encoded = cv2.imencode(".png", sig["image"])
            sig_base64 = base64.b64encode(sig_encoded.tobytes()).decode("utf-8") if sig_success else ""
            opencv_signatures.append({
                "content": sig_base64,
            })
            logger.debug(f"[{request_id}] Added signature {idx} to opencv_signatures")
    else:
        # Single signature - return the largest one
        largest_signature = top_signatures[0]
        cropped_img = largest_signature["image"]
        x1, y1, x2, y2 = largest_signature["bbox"]

        logger.info(
            f"[{request_id}] Single signature: "
            f"position=({x1}, {y1}), "
            f"output_size={cropped_img.shape[1]}x{cropped_img.shape[0]}, "
            f"area={largest_signature['area']:.0f}, "
            f"aspect_ratio={largest_signature['aspect_ratio']:.2f}"
        )

        # Build opencv_signatures list with base64 content for single signature
        # Encode individual signature image to base64
        sig_success, sig_encoded = cv2.imencode(".png", cropped_img)
        sig_base64 = base64.b64encode(sig_encoded.tobytes()).decode("utf-8") if sig_success else ""
        opencv_signatures = [{
            "content": sig_base64,
        }]

    # Encode cropped signature to PNG bytes
    success, encoded = cv2.imencode(".png", cropped_img)
    if not success:
        raise ValueError("Failed to encode cropped signature to PNG")

    return encoded.tobytes(), opencv_signatures


def _opencv_postprocess_image(
    image_bytes: bytes, request_id: str
) -> bytes:
    """
    Apply OpenCV post-processing to enhance signature image:
    1. Convert to grayscale
    2. Sharpen using unsharp masking
    3. Upscale 2x using LapSRN model

    All processing is done in-memory (serverless-compatible).

    Args:
        image_bytes: PNG image bytes
        request_id: Request ID for logging

    Returns:
        Processed PNG image bytes (grayscale, sharpened, upscaled 2x)

    Raises:
        FileNotFoundError: If LapSRN model file not found
        ValueError: If image processing fails
    """
    # Load image from bytes
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image bytes")

    logger.info(f"[{request_id}] OpenCV post-processing: input size {img.shape[1]}x{img.shape[0]}")

    # 1. Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    logger.info(f"[{request_id}] Converted to grayscale")

    # 2. Sharpen using unsharp masking
    # Parameters tuned for signature clarity
    gaussian_radius = 1.5
    amount = 1.5

    blur = cv2.GaussianBlur(gray, ksize=(0, 0), sigmaX=gaussian_radius)
    mask = cv2.subtract(gray, blur)
    sharpened = cv2.add(gray, cv2.multiply(mask, amount))
    sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
    logger.info(f"[{request_id}] Applied unsharp masking (radius={gaussian_radius}, amount={amount})")

    # 3. Convert back to BGR for LapSRN (requires 3-channel input)
    sharpened_bgr = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)

    # 4. Load and apply LapSRN model for 2x upscaling
    sr_obj: Any = cv2.dnn_superres.DnnSuperResImpl_create()  # type: ignore[attr-defined]
    sr = cast(Any, sr_obj)
    sr.readModel(LAPSRN_MODEL_PATH)
    sr.setModel("lapsrn", 2)  # 2x upscaling

    upscaled = sr.upsample(sharpened_bgr)
    logger.info(f"[{request_id}] Upscaled 2x using LapSRN: output size {upscaled.shape[1]}x{upscaled.shape[0]}")

    # Convert back to grayscale for final output
    final_gray = cv2.cvtColor(upscaled, cv2.COLOR_BGR2GRAY)

    # Encode to PNG bytes
    success, encoded = cv2.imencode(".png", final_gray)
    if not success:
        raise ValueError("Failed to encode processed image to PNG")

    return encoded.tobytes()


async def _detect_faces_with_azure_face_api(
    image_bytes: bytes, request_id: str
) -> dict[str, Any]:
    """
    Detect faces in an image using Azure Face API.

    SERVERLESS COMPATIBLE: All processing is done in-memory using aiohttp.

    Args:
        image_bytes: Image file bytes (JPEG, PNG, GIF, or BMP)
        request_id: Request ID for logging

    Returns:
        Dictionary containing:
        - faces_found: Number of faces detected
        - faces: List of face detection results with bounding boxes
        - message: Status message
        - error: Error message if detection failed
    """
    if not AZURE_FACE_API_KEY:
        logger.warning(f"[{request_id}] Azure Face API key not configured")
        return {
            "faces_found": 0,
            "faces": [],
            "error": "Azure Face API key not configured",
            "message": "Set AZURE_FACE_API_KEY environment variable",
        }

    if not AZURE_FACE_ENDPOINT:
        logger.warning(f"[{request_id}] Azure Face API endpoint not configured")
        return {
            "faces_found": 0,
            "faces": [],
            "error": "Azure Face API endpoint not configured",
            "message": "Set AZURE_FACE_ENDPOINT environment variable",
        }

    logger.info(
        f"[{request_id}] Detecting faces using Azure Face API ({len(image_bytes):,} bytes)"
    )

    # Construct API endpoint
    endpoint_url = f"{AZURE_FACE_ENDPOINT.rstrip('/')}/face/v1.0/detect"

    # Construct query parameters
    params = {
        "returnFaceId": "false",
        "returnFaceLandmarks": "false",
        "returnFaceAttributes": "glasses,headpose,blur,exposure,noise,qualityforrecognition",
        "detectionModel": "detection_01",
        "recognitionModel": "recognition_04",
    }

    # Prepare headers
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_FACE_API_KEY,
        "Content-Type": "application/octet-stream",
    }

    try:
        # Make async HTTP request using aiohttp
        timeout = aiohttp.ClientTimeout(total=FACE_API_TIMEOUT_SECONDS)
        async with (
            aiohttp.ClientSession() as session,
            session.post(
                endpoint_url,
                params=params,
                headers=headers,
                data=image_bytes,
                timeout=timeout,
            ) as response,
        ):
            response_text = await response.text()

            if response.status != 200:
                # Handle error response
                logger.error(
                    f"[{request_id}] Face API error: HTTP {response.status} - {response.reason}"
                )

                try:
                    error_body = json.loads(response_text)
                    error_details = error_body.get("error", {})
                    error_message = f"Face API error: {error_details.get('code', response.status)} - {error_details.get('message', response.reason)}"
                except json.JSONDecodeError:
                    error_message = f"Face API error: {response.status} {response.reason}"

                return {
                    "faces_found": 0,
                    "faces": [],
                    "error": error_message,
                    "message": "Face detection failed",
                }

            # Success - parse face data
            faces = json.loads(response_text)

            logger.info(f"[{request_id}] Face API detected {len(faces)} face(s)")

            return {
                "faces_found": len(faces),
                "faces": faces,
                "message": f"Successfully detected {len(faces)} face(s)",
            }

    except asyncio.TimeoutError:
        logger.error(
            f"[{request_id}] Face API request timed out after {FACE_API_TIMEOUT_SECONDS} seconds"
        )
        return {
            "faces_found": 0,
            "faces": [],
            "error": f"Request timed out after {FACE_API_TIMEOUT_SECONDS} seconds",
            "message": "Face detection failed",
        }

    except Exception as e:
        logger.error(f"[{request_id}] Face API unexpected error: {type(e).__name__}: {str(e)}")
        return {
            "faces_found": 0,
            "faces": [],
            "error": f"Unexpected error: {str(e)}",
            "message": "Face detection failed",
        }


def _erase_faces_from_image(
    image_bytes: bytes, face_detection_result: dict[str, Any], request_id: str
) -> bytes:
    """
    Erase detected faces from an image by replacing bounding box regions with white color.

    SERVERLESS COMPATIBLE: All processing is done in-memory using PIL.

    Args:
        image_bytes: Original image bytes
        face_detection_result: Face detection result dictionary containing 'faces' list
        request_id: Request ID for logging

    Returns:
        Modified image bytes with faces erased (white rectangles)
    """
    from PIL import ImageDraw

    # Load image from bytes
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image)

    faces = face_detection_result.get("faces", [])

    if not faces:
        logger.info(f"[{request_id}] No faces to erase")
        # Return original image bytes as PNG
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    logger.info(f"[{request_id}] Erasing {len(faces)} face(s) from image")

    # Erase each face by drawing white rectangle
    for idx, face in enumerate(faces, start=1):
        rect = face.get("faceRectangle", {})
        if not rect:
            continue

        left = rect.get("left", 0)
        top = rect.get("top", 0)
        width = rect.get("width", 0)
        height = rect.get("height", 0)

        # Expand bounding box to cover the whole head (add 20% padding to width/height, 40% to top)
        padding_width = int(width * 0.2)
        padding_height = int(height * 0.2)
        padding_top = int(height * 0.4)  # Extra padding at top for hair/forehead

        # Calculate expanded rectangle coordinates
        x1 = max(0, left - padding_width)
        y1 = max(0, top - padding_top)
        x2 = left + width + padding_width
        y2 = top + height + padding_height

        # Draw white rectangle to erase face
        draw.rectangle([x1, y1, x2, y2], fill="white", outline=None)

        logger.debug(
            f"[{request_id}] Erased face #{idx} at ({x1}, {y1}, {x2-x1}x{y2-y1}) "
            f"[expanded from ({left}, {top}, {width}x{height})]"
        )

    # Convert back to bytes
    output = io.BytesIO()
    image.save(output, format="PNG")

    logger.info(f"[{request_id}] Face erasure complete")

    return output.getvalue()


def _mask_regions_with_white(
    image_bytes: bytes,
    regions: list[tuple[str, int, list[float]]],
    padding: int,
    request_id: str,
) -> bytes:
    """
    Mask specified regions in an image with white color.

    SERVERLESS COMPATIBLE: All processing is done in-memory using PIL.

    Args:
        image_bytes: Original image bytes
        regions: List of tuples (field_name, page_number, polygon)
        padding: Extra padding around each region in pixels
        request_id: Request ID for logging

    Returns:
        Modified image bytes with regions masked (white rectangles)
    """
    from PIL import ImageDraw

    # Load image from bytes
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image)

    if not regions:
        logger.info(f"[{request_id}] No regions to mask")
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()

    logger.info(f"[{request_id}] Masking {len(regions)} region(s) from image")

    # Mask each region by drawing white rectangle
    for field_name, _page_no, polygon in regions:
        if not polygon:
            continue

        # Convert polygon to bounding box
        min_x, min_y, max_x, max_y = _polygon_to_bbox(polygon)

        # Apply padding
        x1 = max(0, int(min_x) - padding)
        y1 = max(0, int(min_y) - padding)
        x2 = min(int(max_x) + padding, image.width)
        y2 = min(int(max_y) + padding, image.height)

        # Draw white rectangle to mask field
        draw.rectangle([x1, y1, x2, y2], fill="white", outline=None)

        logger.debug(f"[{request_id}] Masked field '{field_name}' at ({x1}, {y1}) - ({x2}, {y2})")

    # Convert back to bytes
    output = io.BytesIO()
    image.save(output, format="PNG")

    logger.info(f"[{request_id}] Field masking complete")

    return output.getvalue()


async def _mask_id_details_with_doc_intelligence(
    image_bytes: bytes, request_id: str, model_id: str | None = None, padding: int = 4
) -> dict[str, Any]:
    """
    Mask all detected fields EXCEPT signature fields with white color using Azure Document Intelligence.

    This function analyzes a document, finds all fields from the custom model,
    and masks every field that does NOT contain 'signature' in its name.

    SERVERLESS COMPATIBLE: All processing is done in-memory.
    Uses asyncio.to_thread to wrap the synchronous Azure DI SDK call.

    Args:
        image_bytes: Image file bytes (PNG, JPG, etc.)
        request_id: Request ID for logging
        model_id: Document Intelligence model ID (should be a custom model with field definitions)
        padding: Extra padding around each masked region in pixels (default: 4)

    Returns:
        Dictionary containing masking results with masked image bytes
    """
    if not AZURE_DI_ENDPOINT or not AZURE_DI_KEY:
        raise ValueError(
            "Azure Document Intelligence is not configured. Please set AZURE_DI_ENDPOINT and AZURE_DI_KEY environment variables."
        )

    if model_id is None:
        model_id = AZURE_DI_MODEL_ID

    logger.info(
        f"[{request_id}] Masking ID details with Azure Document Intelligence (model: {model_id})"
    )

    # Wrap synchronous Azure DI call in asyncio.to_thread for non-blocking execution
    def _analyze_and_mask() -> dict[str, Any]:
        # Initialize Document Intelligence client
        client = DocumentIntelligenceClient(
            AZURE_DI_ENDPOINT, AzureKeyCredential(AZURE_DI_KEY)
        )

        # Analyze document
        image_stream = io.BytesIO(image_bytes)
        poller = client.begin_analyze_document(
            model_id, body=image_stream, content_type="application/octet-stream"
        )
        result: Any = poller.result()

        # Collect NON-SIGNATURE field regions to mask
        regions_to_mask: list[tuple[str, int, list[float]]] = []
        signature_fields_found: list[str] = []

        # Look for fields in custom model documents
        documents_attr: Any = getattr(result, "documents", None)
        if documents_attr:
            for doc in documents_attr:
                fields_attr: Any = getattr(doc, "fields", None)
                if fields_attr:
                    for field_name, field_value in fields_attr.items():
                        fname_str: str = str(field_name)

                        # Skip signature fields - we want to preserve them
                        if "signature" in fname_str.lower():
                            signature_fields_found.append(fname_str)
                            logger.debug(f"[{request_id}] Preserving signature field: {fname_str}")
                            continue

                        # Get bounding regions for non-signature fields
                        regions_attr: Any = getattr(field_value, "bounding_regions", None)
                        if regions_attr:
                            for region in regions_attr:
                                page_number: int = int(getattr(region, "page_number", 1))
                                polygon_raw: Any = getattr(region, "polygon", [])
                                polygon: list[float] = list(polygon_raw) if polygon_raw else []
                                if polygon:
                                    regions_to_mask.append((fname_str, page_number, polygon))
                                    logger.debug(f"[{request_id}] Will mask field: {fname_str}")

        return {
            "regions_to_mask": regions_to_mask,
            "signature_fields_found": signature_fields_found,
        }

    # Execute Document Intelligence analysis in thread pool
    analysis_result = await asyncio.to_thread(_analyze_and_mask)

    regions_to_mask: list[tuple[str, int, list[float]]] = analysis_result["regions_to_mask"]
    signature_fields_found: list[str] = analysis_result["signature_fields_found"]

    if not regions_to_mask:
        logger.info(
            f"[{request_id}] No fields to mask (all are signature fields or no fields found)"
        )
        return {
            "fields_masked": 0,
            "masked_fields": [],
            "signature_fields_preserved": signature_fields_found,
            "masked_image_bytes": image_bytes,  # Return original if nothing to mask
            "message": "No non-signature fields detected to mask",
        }

    # Mask non-signature regions with white color
    logger.info(f"[{request_id}] Masking {len(regions_to_mask)} non-signature field(s)")
    masked_image_bytes = _mask_regions_with_white(
        image_bytes, regions_to_mask, padding, request_id
    )

    # Build list of masked field details
    masked_fields: list[dict[str, Any]] = []
    for i, (name, page_no, poly) in enumerate(regions_to_mask, start=1):
        min_x, min_y, max_x, max_y = _polygon_to_bbox(poly)
        masked_fields.append(
            {
                "index": i,
                "field_name": name,
                "page_number": page_no,
                "bbox": {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y},
            }
        )

    logger.info(
        f"[{request_id}] Masked {len(regions_to_mask)} field(s), "
        f"preserved {len(signature_fields_found)} signature field(s)"
    )

    return {
        "fields_masked": len(regions_to_mask),
        "masked_fields": masked_fields,
        "signature_fields_preserved": signature_fields_found,
        "masked_image_bytes": masked_image_bytes,
        "message": f"Successfully masked {len(regions_to_mask)} field(s)",
    }


async def _extract_signature_with_doc_intelligence(
    image_bytes: bytes, request_id: str, model_id: str | None = None
) -> dict[str, Any]:
    """
    Extract handwritten signatures from an image using Azure Document Intelligence.
    Uses asyncio.to_thread to wrap the synchronous Azure DI SDK call.

    Args:
        image_bytes: Image file bytes (PNG, JPG, etc.)
        request_id: Request ID for logging
        model_id: Azure Document Intelligence model ID (defaults to AZURE_DI_MODEL_ID)

    Returns:
        Dictionary containing signature extraction results with structure:
        {
            "signatures_found": int,
            "signatures": [{"id": int, "bounding_box": {...}, "polygon": [...], ...}],
            "message": str
        }

    Raises:
        ValueError: If Azure DI is not configured
        Exception: If API call fails
    """
    if not AZURE_DI_ENDPOINT or not AZURE_DI_KEY:
        raise ValueError(
            "Azure Document Intelligence is not configured. Please set AZURE_DI_ENDPOINT and AZURE_DI_KEY environment variables."
        )

    if model_id is None:
        model_id = AZURE_DI_MODEL_ID

    # Wrap synchronous Azure DI call in asyncio.to_thread for non-blocking execution
    def _call_doc_intelligence() -> dict[str, Any]:
        # Initialize Document Intelligence client
        client = DocumentIntelligenceClient(
            AZURE_DI_ENDPOINT, AzureKeyCredential(AZURE_DI_KEY)
        )

        # Analyze document
        image_stream = io.BytesIO(image_bytes)
        poller = client.begin_analyze_document(
            model_id, body=image_stream, content_type="application/octet-stream"
        )
        result: Any = poller.result()

        # Collect signature regions
        regions: list[tuple[str, int, list[float]]] = []

        # Strategy 1: Try to find Signature fields from custom model
        documents_attr: Any = getattr(result, "documents", None)
        if documents_attr:
            for doc in documents_attr:
                fields_attr: Any = getattr(doc, "fields", None)
                if fields_attr:
                    for field_name, field_value in fields_attr.items():
                        # Match signature fields by name
                        fname_str: str = str(field_name)
                        if "signature" in fname_str.lower():
                            # Extract content and confidence to validate signature
                            content: str = str(getattr(field_value, "content", "") or "")
                            confidence: float = float(getattr(field_value, "confidence", 0) or 0)

                            # Skip invalid signatures: 1 character content with confidence < 8%
                            if len(content) == 1 and confidence < 0.08:
                                logger.info(
                                    f"[{request_id}] Skipping invalid signature '{fname_str}': "
                                    f"content='{content}' (1 char), confidence={confidence:.2%}"
                                )
                                continue

                            regions_attr: Any = getattr(field_value, "bounding_regions", None)
                            if regions_attr:
                                for region in regions_attr:
                                    page_number: int = int(getattr(region, "page_number", 1))
                                    polygon_raw: Any = getattr(region, "polygon", [])
                                    polygon: list[float] = (
                                        list(polygon_raw) if polygon_raw else []
                                    )
                                    if polygon:
                                        regions.append((fname_str, page_number, polygon))

        if not regions:
            return {
                "signatures_found": 0,
                "signatures": [],
                "message": "No signature regions detected by Document Intelligence",
            }

        # Process detected regions
        signatures: list[dict[str, Any]] = []
        for i, (name, page_no, poly) in enumerate(regions, start=1):
            # Convert polygon to bounding box
            xs = poly[::2]
            ys = poly[1::2]
            min_x, min_y, max_x, max_y = min(xs), min(ys), max(xs), max(ys)

            # Calculate width and height
            width = max_x - min_x
            height = max_y - min_y

            signatures.append(
                {
                    "id": i,
                    "field_name": name,
                    "page_number": page_no,
                    "bounding_box": {
                        "min_x": min_x,
                        "min_y": min_y,
                        "max_x": max_x,
                        "max_y": max_y,
                        "width": width,
                        "height": height,
                    },
                    "polygon": poly,
                }
            )

        logger.info(
            f"[{request_id}] Azure OpenAI Vision identified {len(signatures)} signature(s) "
            f"in the image using model {model_id}"
        )

        return {
            "signatures_found": len(signatures),
            "signatures": signatures,
            "message": f"Successfully detected {len(signatures)} signature region(s)",
        }

    logger.info(
        f"[{request_id}] Calling Azure Document Intelligence for signature extraction (model: {model_id})"
    )
    result = await asyncio.to_thread(_call_doc_intelligence)
    logger.info(
        f"[{request_id}] Azure Document Intelligence returned {result.get('signatures_found', 0)} signature(s)"
    )

    return result


def _crop_signature_from_gpt(
    image_bytes: bytes,
    bounding_box: dict[str, float],
    padding: int = 100,
    opencv_upscale: bool = False,
    opencv_crop: bool = False,
    request_id: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Crop signature region from image based on bounding box and return as base64 string.
    All processing is done in-memory (serverless-compatible).

    Args:
        image_bytes: Image file bytes
        bounding_box: Dict with keys 'x', 'y', 'width', 'height' (all as percentages 0-100)
        padding: Additional padding to add around bounding box in pixels (default: 100)
        opencv_upscale: If True, apply OpenCV post-processing (grayscale, sharpen, upscale 2x)
        opencv_crop: If True, apply OpenCV signature cropping using contour detection to isolate handwritten signature
        request_id: Request ID for logging (required if opencv_upscale=True or opencv_crop=True)

    Returns:
        Tuple of:
        - Base64-encoded PNG image string of the cropped signature
        - List of OpenCV-extracted signatures [{"content": str}, ...] (empty if opencv_crop=False)

    Raises:
        ValueError: If bounding box is invalid
    """
    # Load image from bytes (serverless pattern)
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img_width, img_height = image.size

    # Extract bounding box percentages
    x_pct = bounding_box.get("x", 0)
    y_pct = bounding_box.get("y", 0)
    width_pct = bounding_box.get("width", 0)
    height_pct = bounding_box.get("height", 0)

    # Validate bounding box
    if not (0 <= x_pct <= 100 and 0 <= y_pct <= 100):
        raise ValueError(f"Invalid bounding box position: x={x_pct}, y={y_pct}")
    if not (0 < width_pct <= 100 and 0 < height_pct <= 100):
        raise ValueError(f"Invalid bounding box dimensions: width={width_pct}, height={height_pct}")

    # Convert percentage-based coordinates to pixel coordinates
    x1 = int((x_pct / 100) * img_width)
    y1 = int((y_pct / 100) * img_height)
    x2 = int(((x_pct + width_pct) / 100) * img_width)
    y2 = int(((y_pct + height_pct) / 100) * img_height)

    # Add padding (in pixels)
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(img_width, x2 + padding)
    y2 = min(img_height, y2 + padding)

    # Crop the signature region
    cropped = image.crop((x1, y1, x2, y2))

    # Convert to PNG bytes
    img_byte_arr = io.BytesIO()
    cropped.save(img_byte_arr, format="PNG")
    png_bytes = img_byte_arr.getvalue()

    # Apply OpenCV post-processing if requested
    if opencv_upscale:
        if request_id is None:
            raise ValueError("request_id is required when opencv_upscale=True")
        png_bytes = _opencv_postprocess_image(png_bytes, request_id)

    # Apply OpenCV signature cropping if requested
    opencv_signatures: list[dict[str, Any]] = []
    if opencv_crop:
        if request_id is None:
            raise ValueError("request_id is required when opencv_crop=True")
        png_bytes, opencv_signatures = _opencv_crop_signature(png_bytes, request_id)

    # Encode to base64 string
    base64_string = base64.b64encode(png_bytes).decode("utf-8")

    return base64_string, opencv_signatures


def _crop_signature_from_adi(
    image_bytes: bytes,
    bbox: dict[str, float] | None,
    padding: int = 4,
    opencv_upscale: bool = False,
    opencv_crop: bool = False,
    request_id: str | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Crop signature region from image using pixel coordinates and return as base64 string.
    Used for Azure Document Intelligence results which return pixel coordinates.
    All processing is done in-memory (serverless-compatible).

    Args:
        image_bytes: Image file bytes
        bbox: Dict with keys 'min_x', 'min_y', 'max_x', 'max_y' (in pixels), or None to process entire image
        padding: Additional padding to add around bounding box in pixels (default: 4)
        opencv_upscale: If True, apply OpenCV post-processing (grayscale, sharpen, upscale 2x)
        opencv_crop: If True, apply OpenCV signature cropping using contour detection to isolate handwritten signature
        request_id: Request ID for logging (required if opencv_upscale=True or opencv_crop=True)

    Returns:
        Tuple of:
        - Base64-encoded PNG image string of the cropped signature
        - List of OpenCV-extracted signatures [{"content": str}, ...] (empty if opencv_crop=False)

    Raises:
        ValueError: If bounding box is provided but invalid
    """
    # Load image from bytes (serverless pattern)
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img_width, img_height = image.size

    # If no bounding box provided, use the entire image
    if bbox is None:
        # Process entire image (no cropping, just apply OpenCV processing)
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format="PNG")
        png_bytes = img_byte_arr.getvalue()
    else:
        # Extract bounding box pixel coordinates
        min_x = bbox.get("min_x", 0)
        min_y = bbox.get("min_y", 0)
        max_x = bbox.get("max_x", 0)
        max_y = bbox.get("max_y", 0)

        # Validate bounding box
        if not (0 <= min_x < img_width and 0 <= min_y < img_height):
            raise ValueError(f"Invalid bounding box position: min_x={min_x}, min_y={min_y}")
        if not (min_x < max_x <= img_width and min_y < max_y <= img_height):
            raise ValueError(
                f"Invalid bounding box dimensions: max_x={max_x}, max_y={max_y}"
            )

        # Apply padding (in pixels) and ensure within image bounds
        x1 = max(0, int(min_x) - padding)
        y1 = max(0, int(min_y) - padding)
        x2 = min(img_width, int(max_x) + padding)
        y2 = min(img_height, int(max_y) + padding)

        # Crop the signature region
        cropped = image.crop((x1, y1, x2, y2))

        # Convert to PNG bytes
        img_byte_arr = io.BytesIO()
        cropped.save(img_byte_arr, format="PNG")
        png_bytes = img_byte_arr.getvalue()

    # Apply OpenCV post-processing if requested
    if opencv_upscale:
        if request_id is None:
            raise ValueError("request_id is required when opencv_upscale=True")
        png_bytes = _opencv_postprocess_image(png_bytes, request_id)

    # Apply OpenCV signature cropping if requested
    opencv_signatures: list[dict[str, Any]] = []
    if opencv_crop:
        if request_id is None:
            raise ValueError("request_id is required when opencv_crop=True")
        png_bytes, opencv_signatures = _opencv_crop_signature(png_bytes, request_id)

    # Encode to base64 string
    base64_string = base64.b64encode(png_bytes).decode("utf-8")

    return base64_string, opencv_signatures


def _convert_pdf_to_image_bytes(file_bytes: bytes, filename: str, dpi: int = 200) -> bytes:
    """
    Convert PDF first page to image bytes, or return original bytes if already an image.

    Args:
        file_bytes: Raw file bytes (PDF or image)
        filename: Original filename to determine file type
        dpi: DPI for PDF rendering (default: 200)

    Returns:
        PNG image bytes
    """
    file_ext = os.path.splitext(filename.lower())[1]

    if file_ext == ".pdf":
        # Extract first page of PDF as PNG image bytes
        pdf_document: Any = fitz.open(stream=file_bytes, filetype="pdf")
        if pdf_document.page_count == 0:
            raise ValueError("PDF has no pages")

        # Render first page to image at specified DPI
        page: Any = pdf_document[0]
        pix: Any = page.get_pixmap(dpi=dpi)
        png_bytes: bytes = pix.tobytes("png")
        return png_bytes

    # Already an image, return as-is
    return file_bytes


def _polygon_to_bbox(points: list[float]) -> tuple[float, float, float, float]:
    """Convert polygon [x1,y1,x2,y2,...] -> (min_x, min_y, max_x, max_y)."""
    xs = points[::2]
    ys = points[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def _save_crop_from_image(
    image_bytes: bytes, bbox_px: tuple[float, float, float, float], out_path: str, padding: int = 0
) -> bytes:
    """
    Crop region from image bytes (serverless-compatible, in-memory only).

    Args:
        image_bytes: Image file bytes
        bbox_px: Bounding box in pixels (min_x, min_y, max_x, max_y)
        out_path: Output path for local debugging
        padding: Padding in pixels

    Returns:
        PNG image bytes of the cropped region
    """
    # Load image from bytes (serverless pattern)
    im = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    min_x, min_y, max_x, max_y = bbox_px
    box = (
        max(int(min_x) - padding, 0),
        max(int(min_y) - padding, 0),
        min(int(max_x) + padding, im.width),
        min(int(max_y) + padding, im.height),
    )
    crop = im.crop(box)

    # Save crops to tmp/ folder if enabled
    save_crops = os.getenv("SAVE_CROPS", "false").lower() == "true"
    if save_crops:
        crop.save(out_path, "PNG")

    # Return cropped image as PNG bytes
    img_byte_arr = io.BytesIO()
    crop.save(img_byte_arr, format="PNG")
    return img_byte_arr.getvalue()


def _extract_signatures_with_doc_intelligence(
    image_bytes: bytes, debug_prefix: str = ""
) -> list[Any]:
    """
    Extract signature regions using Azure Document Intelligence.

    Args:
        image_bytes: Image file bytes (PNG, JPG, etc. - PDFs already converted)
        debug_prefix: Debug prefix for saved images

    Returns:
        List of extracted signature images as numpy arrays
    """
    if not AZURE_DI_ENDPOINT or not AZURE_DI_KEY:
        logger.warning("Azure Document Intelligence not configured, skipping")
        return []

    try:
        # Initialize Document Intelligence client
        client = DocumentIntelligenceClient(AZURE_DI_ENDPOINT, AzureKeyCredential(AZURE_DI_KEY))

        # Analyze document with Document Intelligence
        logger.debug(f"Analyzing document with Document Intelligence model '{AZURE_DI_MODEL_ID}'")
        # Wrap bytes in BytesIO for SDK compatibility
        image_stream = io.BytesIO(image_bytes)
        poller = client.begin_analyze_document(
            AZURE_DI_MODEL_ID, body=image_stream, content_type="application/octet-stream"
        )
        result: Any = poller.result()

        # Collect signature regions
        regions: list[tuple[str, int, list[float]]] = []

        # Strategy 1: Try to find Signature fields from custom model
        documents_attr: Any = getattr(result, "documents", None)
        if documents_attr:
            for doc in documents_attr:
                fields_attr: Any = getattr(doc, "fields", None)
                if fields_attr:
                    for fname, fobj in fields_attr.items():
                        # Match signature fields by type or name
                        value_type: str = str(getattr(fobj, "value_type", ""))
                        fname_str: str = str(fname)
                        if value_type.lower() == "signature" or "signature" in fname_str.lower():
                            bounding_regions_attr: Any = getattr(fobj, "bounding_regions", None)
                            if bounding_regions_attr:
                                for br in bounding_regions_attr:
                                    page_num: int = int(getattr(br, "page_number", 1))
                                    polygon: list[float] = list(getattr(br, "polygon", []))
                                    regions.append(("signature", page_num, polygon))

        # Strategy 2: Fallback to figures (Layout model)
        figures_attr: Any = getattr(result, "figures", None)
        if not regions and figures_attr:
            for idx, fig in enumerate(figures_attr):
                bounding_regions_attr_fig: Any = getattr(fig, "bounding_regions", [])
                for br in bounding_regions_attr_fig:
                    page_num_fig: int = int(getattr(br, "page_number", 1))
                    polygon_fig: list[float] = list(getattr(br, "polygon", []))
                    regions.append((f"figure_{idx + 1}", page_num_fig, polygon_fig))

        if not regions:
            logger.info("No signature/figure regions found by Document Intelligence")
            return []

        # Extract and crop signatures (coordinates are in pixels for images)
        signatures: list[Any] = []
        save_crops = os.getenv("SAVE_CROPS", "false").lower() == "true"
        timestamp = str(int(time.time() * 1000))

        for i, (name, page_no, poly) in enumerate(regions, start=1):
            min_x, min_y, max_x, max_y = _polygon_to_bbox(poly)

            # Crop from image bytes (in-memory)
            out_path = f"./tmp/{debug_prefix}_di_{name}_p{page_no}_{i}_{timestamp}.png"
            if save_crops:
                os.makedirs("./tmp", exist_ok=True)

            # Get cropped image bytes
            cropped_bytes = _save_crop_from_image(
                image_bytes,
                (min_x, min_y, max_x, max_y),
                out_path,
                padding=PADDING_PIXELS,
            )

            # Convert PNG bytes to OpenCV image (in-memory)
            nparr = np.frombuffer(cropped_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                signatures.append(img)
                logger.debug(f"Extracted signature: {out_path}")

        logger.info(
            f"Document Intelligence extracted {len(signatures)} signature(s) using {AZURE_DI_MODEL_ID} "
            f"from {len(regions)} region(s) detected"
        )
        return signatures

    except Exception as e:
        logger.warning(f"Document Intelligence extraction failed: {str(e)}, falling back to OpenCV")
        return []


def _extract_signatures(file_bytes: bytes, filename: str, debug_prefix: str = "") -> list[Any]:
    """
    Extract signature regions from an image/PDF using Document Intelligence (if configured)
    or traditional contour detection (fallback).

    Args:
        file_bytes: Raw file bytes (PDF or image)
        filename: Original filename (to detect file type)
        debug_prefix: Optional prefix for saved debug images (e.g., "valid_id", "specimen")

    Returns:
        List of extracted signature images as numpy arrays
    """
    # Try Azure Document Intelligence first if configured
    if AZURE_DI_ENDPOINT and AZURE_DI_KEY:
        logger.info(f"Using Azure Document Intelligence for signature extraction: {debug_prefix}")

        # Process with Document Intelligence using higher DPI (200) for better accuracy
        try:
            image_bytes_di = _convert_pdf_to_image_bytes(file_bytes, filename, dpi=PDF_RENDER_DPI)
            di_signatures = _extract_signatures_with_doc_intelligence(image_bytes_di, debug_prefix)
            if di_signatures:
                return di_signatures
            logger.info("Falling back to OpenCV contour detection")
        except Exception as e:
            logger.warning(
                f"Document Intelligence processing failed: {str(e)}, falling back to OpenCV"
            )

    # Fallback to traditional OpenCV contour detection
    # Convert PDF/image to bytes at lower DPI (150) for faster OpenCV processing
    try:
        image_bytes = _convert_pdf_to_image_bytes(file_bytes, filename, dpi=150)
        nparr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            logger.error("Failed to decode image bytes for OpenCV processing")
            return []
    except Exception as e:
        logger.error(f"Failed to convert file to image for OpenCV: {str(e)}")
        return []

    # Convert to grayscale
    gray: Any = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)  # type: ignore[assignment]

    # Apply Gaussian blur to reduce noise
    blurred: Any = cv2.GaussianBlur(gray, (5, 5), 0)  # type: ignore[arg-type]

    # Apply adaptive thresholding
    thresh: Any = cv2.adaptiveThreshold(  # type: ignore[assignment]
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11,
        2,  # type: ignore[arg-type]
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

    logger.info(
        f"OpenCV contour detection identified {len(signatures)} signature candidate(s), "
        f"returning top {len(top_signatures)} (debug_prefix: {debug_prefix})"
    )

    # Save extracted signatures for debugging (save crops to tmp/ if enabled)
    save_crops = os.getenv("SAVE_CROPS", "false").lower() == "true"
    if debug_prefix and save_crops:
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

    # Save normalized signature for debugging (save crops to tmp/ if enabled)
    save_crops = os.getenv("SAVE_CROPS", "false").lower() == "true"
    if debug_prefix and save_crops:
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
        (8, 8),  # block stride
        (8, 8),  # cell size
        9,  # number of bins
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


def _validate_env_variables(
    required_vars: dict[str, str | None], request_id: str
) -> func.HttpResponse | None:
    """
    Validate that required environment variables are set.

    Args:
        required_vars: Dictionary mapping variable names to their values
        request_id: Request ID for logging

    Returns:
        HttpResponse with error if validation fails, None if valid
    """
    missing_vars = [name for name, value in required_vars.items() if not value]

    if missing_vars:
        var_list = ", ".join(missing_vars)
        logger.error(f"[{request_id}] Configuration error: Missing environment variables: {var_list}")
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Configuration error",
                    "message": f"Server is not properly configured. Missing: {var_list}",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )

    return None


def _validate_padding_parameter(
    padding_str: str, request_id: str
) -> tuple[int, func.HttpResponse | None]:
    """
    Validate and parse padding parameter.

    Args:
        padding_str: String value of padding parameter (in pixels)
        request_id: Request ID for logging

    Returns:
        Tuple of (padding_value, error_response). If valid, error_response is None.
    """
    try:
        padding = int(padding_str)
    except ValueError:
        return 0, func.HttpResponse(
            json.dumps(
                {
                    "error": "Invalid parameters",
                    "message": "padding must be an integer",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )

    if not (0 <= padding <= 500):
        return 0, func.HttpResponse(
            json.dumps(
                {
                    "error": "Invalid parameters",
                    "message": "padding must be between 0 and 500 pixels",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )

    return padding, None


def _parse_json_body(
    req: func.HttpRequest, request_id: str
) -> tuple[dict[str, Any] | None, func.HttpResponse | None]:
    """
    Parse and validate JSON request body.

    Args:
        req: HTTP request object
        request_id: Request ID for logging

    Returns:
        Tuple of (body_dict, error_response). If valid, error_response is None.
    """
    try:
        body = req.get_json()
    except ValueError:
        return None, func.HttpResponse(
            json.dumps(
                {
                    "error": "Invalid request",
                    "message": "Request body must be valid JSON",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )

    if not body:
        return None, func.HttpResponse(
            json.dumps(
                {
                    "error": "Missing request body",
                    "message": "Request body is required",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )

    return body, None


def _validate_required_fields(
    body: dict[str, Any], required_fields: list[str], request_id: str
) -> func.HttpResponse | None:
    """
    Validate that required fields are present in request body.

    Args:
        body: Parsed JSON body dictionary
        required_fields: List of required field names
        request_id: Request ID for logging

    Returns:
        HttpResponse with error if validation fails, None if valid
    """
    missing_fields = [field for field in required_fields if not body.get(field)]

    if missing_fields:
        field_list = "', '".join(missing_fields)
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Missing required fields",
                    "message": f"The following required fields are missing: '{field_list}'",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )

    return None


def _decode_base64_content(
    base64_content: str, request_id: str
) -> tuple[bytes | None, func.HttpResponse | None]:
    """
    Decode base64-encoded content.

    Args:
        base64_content: Base64-encoded string
        request_id: Request ID for logging

    Returns:
        Tuple of (decoded_bytes, error_response). If valid, error_response is None.
    """
    try:
        decoded_bytes = base64.b64decode(base64_content)
        return decoded_bytes, None
    except Exception as e:
        logger.error(f"[{request_id}] Failed to decode base64 content: {str(e)}")
        return None, func.HttpResponse(
            json.dumps(
                {
                    "error": "Invalid content",
                    "message": "Failed to decode base64 content. Please ensure 'content' is a valid base64 string.",
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=400,
        )


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
                    json.dumps(
                        {
                            "error": "Missing required files",
                            "message": f"Please provide all required files: {', '.join(required_files)}",
                            "request_id": request_id,
                        }
                    ),
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
                    json.dumps(
                        {
                            "error": "Invalid file type",
                            "message": f"{name} must be one of: {', '.join(ALLOWED_FILE_TYPES)}",
                            "request_id": request_id,
                        }
                    ),
                    mimetype="application/json",
                    status_code=400,
                )

        logger.info(f"[{request_id}] Loading images from uploaded files")

        # Read raw file bytes
        valid_id_bytes = valid_id_file.read()
        specimen_bytes = specimen_file.read()
        selfie_bytes = selfie_file.read() if selfie_file else None

        # Extract signatures - _extract_signatures handles PDF conversion internally
        # (200 DPI for Azure DI, 150 DPI for OpenCV)
        extraction_start = time.time()
        logger.info(f"[{request_id}] Extracting signatures from images")

        valid_id_signatures = _extract_signatures(
            valid_id_bytes, valid_id_file.filename or "valid_id", f"{request_id}_valid_id"
        )
        specimen_signatures = _extract_signatures(
            specimen_bytes,
            specimen_file.filename or "specimen_signatures",
            f"{request_id}_specimen",
        )
        selfie_signatures = (
            _extract_signatures(
                selfie_bytes,
                (selfie_file.filename if selfie_file else None) or "selfie_with_id",
                f"{request_id}_selfie",
            )
            if selfie_bytes
            else []
        )

        extraction_time = time.time() - extraction_start

        logger.info(
            f"[{request_id}] Extracted signatures: valid_id={len(valid_id_signatures)}, "
            f"specimen={len(specimen_signatures)}, selfie={len(selfie_signatures)}"
        )

        if len(specimen_signatures) < 3:
            logger.warning(
                f"[{request_id}] Expected 3 specimen signatures, found {len(specimen_signatures)}"
            )
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Insufficient specimen signatures",
                        "message": f"Expected 3 specimen signatures, found only {len(specimen_signatures)}. "
                        "Please ensure the image clearly shows 3 specimen signatures.",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Normalize all signatures
        normalization_start = time.time()
        logger.info(f"[{request_id}] Normalizing signatures")

        normalized_specimen = [
            _normalize_signature(sig, f"{request_id}_specimen", i)
            for i, sig in enumerate(specimen_signatures[:3])
        ]
        normalized_valid_id = (
            [
                _normalize_signature(sig, f"{request_id}_valid_id", i)
                for i, sig in enumerate(valid_id_signatures)
            ]
            if valid_id_signatures
            else []
        )
        normalized_selfie = (
            [
                _normalize_signature(sig, f"{request_id}_selfie", i)
                for i, sig in enumerate(selfie_signatures)
            ]
            if selfie_signatures
            else []
        )

        normalization_time = time.time() - normalization_start

        # Extract features from all signatures (using OpenCV - no external API needed)
        feature_start = time.time()
        logger.info(f"[{request_id}] Extracting image features")

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
        specimen_avg_similarity = (
            sum(specimen_similarity_matrix[i][j] for i in range(3) for j in range(i + 1, 3)) / 3
        )

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
                "average_similarity": round(
                    sum(valid_id_similarities) / len(valid_id_similarities), 4
                )
                if valid_id_similarities
                else 0.0,
                "status": "MATCH"
                if valid_id_similarities
                and sum(valid_id_similarities) / len(valid_id_similarities) >= 0.80
                else "MISMATCH",
            }
            if valid_id_similarities
            else {"status": "NO_SIGNATURE_FOUND"},
            "specimen_vs_selfie": {
                "similarities": selfie_similarities,
                "average_similarity": round(sum(selfie_similarities) / len(selfie_similarities), 4)
                if selfie_similarities
                else 0.0,
                "status": "MATCH"
                if selfie_similarities
                and sum(selfie_similarities) / len(selfie_similarities) >= 0.80
                else "MISMATCH",
            }
            if selfie_similarities
            else {"status": "NO_SIGNATURE_FOUND"},
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
            json.dumps(
                {
                    "error": "Signature comparison failed",
                    "message": str(e),
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )


@app.route(route="gpt_crop", methods=["POST"])
@require_api_key
async def gpt_crop(req: func.HttpRequest) -> func.HttpResponse:
    """
    Extract and crop handwritten signature from an image using Azure OpenAI Vision API.
    Returns the cropped signature as a base64-encoded PNG string.

    Query Parameters:
        - model (optional): Azure OpenAI model name (default: from env AZURE_OPENAI_MODEL)
        - padding (optional): Additional padding around signature in pixels (default: 100)
        - opencv_upscale (optional): Enable OpenCV post-processing (grayscale, sharpen, upscale 2x) (default: false)
        - opencv_crop (optional): Enable OpenCV signature cropping using contour detection (default: false)
        - prompt (optional): Custom prompt for signature extraction (defaults to built-in SIGNATURE_EXTRACTION_PROMPT)

    Request Body:
        JSON with the following fields:
        - filename (required): Name of the image file
        - content (required): Base64-encoded image content

    Returns:
        JSON response with cropped signature in base64 format (first owner signature found)
        If opencv_upscale=true, the output will be grayscale, sharpened, and upscaled 2x
        If opencv_crop=true, applies contour detection to isolate the handwritten signature region
    """
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] Signature cropping request initiated")

    try:
        # Validate environment variables
        env_error = _validate_env_variables(
            {
                "AZURE_OPENAI_API_KEY": AZURE_OPENAI_API_KEY,
                "AZURE_OPENAI_ENDPOINT": AZURE_OPENAI_ENDPOINT,
            },
            request_id,
        )
        if env_error:
            return env_error

        # Get optional parameters
        model = req.params.get("model")
        padding_str = req.params.get("padding", "100")
        opencv_upscale_str = req.params.get("opencv_upscale", "false").lower()
        opencv_crop_str = req.params.get("opencv_crop", "false").lower()
        custom_prompt = req.params.get("prompt")

        # Validate and parse padding
        padding, padding_error = _validate_padding_parameter(padding_str, request_id)
        if padding_error:
            return padding_error

        opencv_upscale = opencv_upscale_str in ("true", "1", "yes")
        opencv_crop = opencv_crop_str in ("true", "1", "yes")

        # Parse and validate JSON body
        body, body_error = _parse_json_body(req, request_id)
        if body_error:
            return body_error

        # Validate required fields
        fields_error = _validate_required_fields(body, ["filename", "content"], request_id)
        if fields_error:
            return fields_error

        filename = body.get("filename")
        base64_content = body.get("content")

        # Decode base64 content
        image_bytes, decode_error = _decode_base64_content(base64_content, request_id)
        if decode_error:
            return decode_error

        logger.info(
            f"[{request_id}] Processing file: {filename} ({len(image_bytes)} bytes)"
        )

        # Extract signatures using Azure OpenAI Vision API
        extraction_start = time.time()
        extraction_result = await _extract_signature_with_openai(image_bytes, request_id, model, custom_prompt)
        extraction_time = time.time() - extraction_start

        signatures_found = extraction_result.get("signatures_found", 0)
        signatures = extraction_result.get("signatures", [])

        if signatures_found == 0:
            logger.warning(f"[{request_id}] No signatures found in image")
            total_time = time.time() - start_time
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "No signatures found",
                        "message": "No handwritten signatures were detected in the image",
                        "analysis_notes": extraction_result.get("analysis_notes", ""),
                        "request_id": request_id,
                        "performance": {
                            "extraction_ms": round(extraction_time * 1000, 2),
                            "total_ms": round(total_time * 1000, 2),
                        },
                    }
                ),
                mimetype="application/json",
                status_code=200,
            )

        # Filter signatures to only include owner signatures
        owner_signatures = [sig for sig in signatures if sig.get("is_owner_signature", False)]

        if not owner_signatures:
            logger.warning(f"[{request_id}] No owner signatures found (total signatures: {signatures_found})")
            total_time = time.time() - start_time
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "No owner signatures found",
                        "message": f"Found {signatures_found} signature(s), but none were identified as owner signatures. All detected signatures appear to be from witnesses, chairmen, or other third parties.",
                        "signatures_found": signatures_found,
                        "owner_signatures_found": 0,
                        "analysis_notes": extraction_result.get("analysis_notes", ""),
                        "request_id": request_id,
                        "performance": {
                            "extraction_ms": round(extraction_time * 1000, 2),
                            "total_ms": round(total_time * 1000, 2),
                        },
                    }
                ),
                mimetype="application/json",
                status_code=200,
            )

        logger.info(f"[{request_id}] Found {len(owner_signatures)} owner signature(s) out of {signatures_found} total")

        # Use the first owner signature
        target_signature = owner_signatures[0]
        logger.info(
            f"[{request_id}] Using first owner signature (ID: {target_signature.get('id')})"
        )

        # Crop signature from image
        crop_start = time.time()
        bounding_box = target_signature.get("bounding_box", {})
        try:
            cropped_base64, opencv_signatures = _crop_signature_from_gpt(
                image_bytes, bounding_box, padding, opencv_upscale, opencv_crop, request_id
            )
        except ValueError as e:
            logger.error(f"[{request_id}] Failed to crop signature: {str(e)}")
            total_time = time.time() - start_time
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Cropping failed",
                        "message": str(e),
                        "request_id": request_id,
                        "performance": {
                            "extraction_ms": round(extraction_time * 1000, 2),
                            "total_ms": round(total_time * 1000, 2),
                        },
                    }
                ),
                mimetype="application/json",
                status_code=500,
            )
        except FileNotFoundError as e:
            logger.error(f"[{request_id}] Model file not found: {str(e)}")
            total_time = time.time() - start_time
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Configuration error",
                        "message": str(e),
                        "request_id": request_id,
                        "performance": {
                            "extraction_ms": round(extraction_time * 1000, 2),
                            "total_ms": round(total_time * 1000, 2),
                        },
                    }
                ),
                mimetype="application/json",
                status_code=500,
            )

        crop_time = time.time() - crop_start
        total_time = time.time() - start_time

        # Build response
        result: dict[str, Any] = {
            "cropped_signature": cropped_base64,
            "signature_info": {
                "id": target_signature.get("id"),
                "location_description": target_signature.get("location_description"),
                "bounding_box": bounding_box,
                "confidence": target_signature.get("confidence"),
                "characteristics": target_signature.get("characteristics"),
                "is_owner_signature": target_signature.get("is_owner_signature"),
            },
            "signatures_found": signatures_found,
            "owner_signatures_found": len(owner_signatures),
            "model_used": model or AZURE_OPENAI_MODEL,
            "custom_prompt_used": custom_prompt is not None,
            "opencv_upscaling": opencv_upscale,
            "opencv_processing": opencv_crop,
            "request_id": request_id,
            "performance": {
                "extraction_ms": round(extraction_time * 1000, 2),
                "crop_ms": round(crop_time * 1000, 2),
                "total_ms": round(total_time * 1000, 2),
            },
        }

        # Add OpenCV signatures if available
        if opencv_signatures:
            result["opencv_signatures"] = opencv_signatures

        logger.info(
            f"[{request_id}] Signature cropping completed: "
            f"total_signatures={signatures_found}, "
            f"owner_signatures={len(owner_signatures)}, "
            f"used_id={target_signature.get('id')}, "
            f"confidence={target_signature.get('confidence')}, "
            f"total_time={total_time:.3f}s"
        )

        return func.HttpResponse(
            json.dumps(result), mimetype="application/json", status_code=200
        )

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] Signature cropping failed after {total_time:.3f}s: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Signature cropping failed",
                    "message": str(e),
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )


# GPT deduplication prompt for selecting cleanest signature
GPT_DEDUP_PROMPT = """
The attached image shows numbered signature crops on the left with corresponding handwritten signature images on the right. Identify which crop is the cleanest, it must fully capture the complete handwritten signature with no extra surrounding elements. Return only the number of the cleanest crop.

Return your response in the following JSON format:
{
  "selected_index": <number>,
  "reason": "<brief explanation of why this crop was selected>"
}
"""


async def _select_cleanest_signature_with_openai(
    image_bytes: bytes, request_id: str, model: str | None = None
) -> dict[str, Any]:
    """
    Select the cleanest signature from an image showing numbered signature crops
    using Azure OpenAI Vision API.

    Args:
        image_bytes: Image file bytes showing numbered signature options
        request_id: Request ID for logging
        model: Azure OpenAI model deployment name (defaults to AZURE_OPENAI_MODEL)

    Returns:
        Dictionary containing selection result with structure:
        {
            "selected_index": int,
            "reason": str
        }

    Raises:
        ValueError: If OpenAI is not configured or response parsing fails
        Exception: If API call fails
    """
    if model is None:
        model = AZURE_OPENAI_MODEL

    # Get OpenAI client (singleton pattern)
    client = _get_openai_client()

    # Encode image to base64
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    # Wrap synchronous OpenAI call in asyncio.to_thread for non-blocking execution
    def _call_openai() -> dict[str, Any]:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing signature images and selecting the cleanest, most complete signature crop. Always respond with valid JSON.",
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": GPT_DEDUP_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
            timeout=60,
        )

        # Extract and parse response
        content = response.choices[0].message.content

        # Handle None content
        if content is None:
            raise ValueError("No content returned from OpenAI API")

        # Try to extract JSON from response (in case it's wrapped in markdown)
        if "```json" in content:
            json_start = content.find("```json") + 7
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()
        elif "```" in content:
            json_start = content.find("```") + 3
            json_end = content.find("```", json_start)
            content = content[json_start:json_end].strip()

        result: dict[str, Any] = json.loads(content)
        return result

    logger.info(f"[{request_id}] Calling Azure OpenAI Vision API for signature deduplication")
    result = await asyncio.to_thread(_call_openai)
    logger.info(
        f"[{request_id}] Azure OpenAI selected signature index: {result.get('selected_index')}"
    )

    return result


def _combine_signatures_vertically(
    opencv_signatures: list[dict[str, Any]], request_id: str
) -> tuple[bytes, list[dict[str, Any]]]:
    """
    Combine multiple signature images vertically with index labels for GPT deduplication.
    Similar to the stacking logic in _opencv_crop_signature().

    Args:
        opencv_signatures: List of signature objects with 'content' field (base64-encoded PNG)
        request_id: Request ID for logging

    Returns:
        Tuple of:
        - Combined PNG image bytes with signatures stacked vertically
        - List of bounding box info for each signature in the combined image

    Raises:
        ValueError: If image decoding fails or no valid signatures provided
    """
    from PIL import ImageDraw, ImageFont

    if not opencv_signatures:
        raise ValueError("No signatures provided")

    # Decode all base64 images to PIL Images
    pil_images: list[Image.Image] = []
    for idx, sig in enumerate(opencv_signatures):
        base64_content = sig.get("content", "")
        if not base64_content:
            logger.warning(f"[{request_id}] Signature {idx} has no content, skipping")
            continue

        try:
            image_bytes = base64.b64decode(base64_content)
            pil_img = Image.open(io.BytesIO(image_bytes))
            # Convert to RGB if needed
            if pil_img.mode != "RGB":
                pil_img = pil_img.convert("RGB")
            pil_images.append(pil_img)
        except Exception as e:
            logger.warning(f"[{request_id}] Failed to decode signature {idx}: {str(e)}")
            continue

    if not pil_images:
        raise ValueError("No valid signature images could be decoded")

    logger.info(f"[{request_id}] Combining {len(pil_images)} signatures vertically")

    # Calculate canvas dimensions
    # Reserve space on the left for index numbers (120px margin for 48pt font)
    index_margin = 120
    max_img_width = max(img.width for img in pil_images)
    padding = 100
    total_height = sum(img.height for img in pil_images) + padding * (len(pil_images) - 1)
    canvas_width = index_margin + max_img_width

    logger.info(
        f"[{request_id}] Canvas size: {canvas_width}x{total_height} "
        f"({len(pil_images)} signatures with {padding}px padding, {index_margin}px index margin)"
    )

    # Create white canvas (RGB mode)
    combined_canvas = Image.new("RGB", (canvas_width, total_height), (255, 255, 255))
    draw = ImageDraw.Draw(combined_canvas)

    # Use Pillow's bundled font (Aileron Regular) - works in serverless environments
    font_size = 48
    font = ImageFont.load_default(size=font_size)
    logger.info(f"[{request_id}] Using Pillow bundled font at size {font_size}")

    # Track bounding boxes for each signature in the combined image
    bounding_boxes: list[dict[str, Any]] = []

    # Paste each signature right-aligned with index number on the left
    current_y = 0
    for idx, pil_img in enumerate(pil_images):
        # Right-align: place image at the rightmost position
        x_offset = canvas_width - pil_img.width
        combined_canvas.paste(pil_img, (x_offset, current_y))

        # Store bounding box for this signature (position in combined image)
        bounding_boxes.append({
            "index": idx,
            "x": x_offset,
            "y": current_y,
            "width": pil_img.width,
            "height": pil_img.height,
        })

        # Draw index number on the left side, vertically centered with the signature
        index_text = str(idx)
        # Get text bounding box for centering
        text_bbox = draw.textbbox((0, 0), index_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # Center the index number vertically with the signature image
        # and place it in the left margin area
        text_x = (index_margin - text_width) // 2
        text_y = current_y + (pil_img.height - text_height) // 2

        # Draw the index number in RED with stroke to simulate bold effect
        draw.text(
            (text_x, text_y),
            index_text,
            fill=(255, 0, 0),
            font=font,
            stroke_width=3,
            stroke_fill=(255, 0, 0),
        )

        logger.info(
            f"[{request_id}] Pasted signature {idx}/{len(pil_images) - 1}: "
            f"size={pil_img.width}x{pil_img.height}, position=({x_offset}, {current_y}), "
            f"index at ({text_x}, {text_y})"
        )

        current_y += pil_img.height + padding

    # Convert combined canvas to PNG bytes
    output_buffer = io.BytesIO()
    combined_canvas.save(output_buffer, format="PNG")
    combined_bytes = output_buffer.getvalue()

    logger.info(
        f"[{request_id}] Combined signature image: {canvas_width}x{total_height}, "
        f"{len(combined_bytes)} bytes"
    )

    return combined_bytes, bounding_boxes


@app.route(route="gpt_dedup", methods=["POST"])
@require_api_key
async def gpt_dedup(req: func.HttpRequest) -> func.HttpResponse:
    """
    Deduplicate signature crops by selecting the cleanest one using Azure OpenAI Vision API.
    Returns the cropped signature as a base64-encoded PNG string.

    This endpoint accepts an array of signature images, combines them vertically with index
    labels, and uses GPT to identify which signature is the cleanest (fully captures the
    complete handwritten signature with no extra surrounding elements).

    Query Parameters:
        - model (optional): Azure OpenAI model name (default: from env AZURE_OPENAI_MODEL)

    Request Body:
        JSON with the following fields:
        - opencv_signatures (required): Array of signature objects with structure:
            [{"content": "base64-encoded-png-image"}, ...]

    Returns:
        JSON response with:
        - cropped_signature: Base64-encoded PNG of the selected cleanest signature
        - selected_index: The index of the selected signature
        - reason: GPT's explanation for the selection
        - total_signatures: Total number of input signatures
        - performance: Timing metrics
    """
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] GPT signature deduplication request initiated")

    try:
        # Validate environment variables
        env_error = _validate_env_variables(
            {
                "AZURE_OPENAI_API_KEY": AZURE_OPENAI_API_KEY,
                "AZURE_OPENAI_ENDPOINT": AZURE_OPENAI_ENDPOINT,
            },
            request_id,
        )
        if env_error:
            return env_error

        # Get optional parameters
        model = req.params.get("model")

        # Parse and validate JSON body
        body, body_error = _parse_json_body(req, request_id)
        if body_error:
            return body_error

        # Validate required fields
        fields_error = _validate_required_fields(body, ["opencv_signatures"], request_id)
        if fields_error:
            return fields_error

        opencv_signatures: list[dict[str, Any]] = body.get("opencv_signatures", [])

        # Validate opencv_signatures is a non-empty list
        if not isinstance(opencv_signatures, list) or len(opencv_signatures) == 0:
            logger.warning(f"[{request_id}] Invalid opencv_signatures: must be a non-empty array")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid opencv_signatures",
                        "message": "opencv_signatures must be a non-empty array of signature objects",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Validate each signature has 'content' field
        for idx, sig in enumerate(opencv_signatures):
            if not isinstance(sig, dict) or not sig.get("content"):
                logger.warning(f"[{request_id}] Signature {idx} missing 'content' field")
                return func.HttpResponse(
                    json.dumps(
                        {
                            "error": "Invalid signature format",
                            "message": f"Signature at index {idx} must have a 'content' field with base64-encoded image",
                            "request_id": request_id,
                        }
                    ),
                    mimetype="application/json",
                    status_code=400,
                )

        logger.info(f"[{request_id}] Processing {len(opencv_signatures)} signature candidates")

        # If only one signature, return it directly without GPT call
        if len(opencv_signatures) == 1:
            logger.info(f"[{request_id}] Only one signature provided, returning directly")
            total_time = time.time() - start_time
            return func.HttpResponse(
                json.dumps(
                    {
                        "cropped_signature": opencv_signatures[0]["content"],
                        "selected_index": 0,
                        "reason": "Only one signature provided, no deduplication needed",
                        "total_signatures": 1,
                        "model_used": model or AZURE_OPENAI_MODEL,
                        "request_id": request_id,
                        "performance": {
                            "combine_ms": 0,
                            "selection_ms": 0,
                            "total_ms": round(total_time * 1000, 2),
                        },
                    }
                ),
                mimetype="application/json",
                status_code=200,
            )

        # Combine signatures vertically with index labels
        combine_start = time.time()
        try:
            combined_image_bytes, bounding_boxes = _combine_signatures_vertically(
                opencv_signatures, request_id
            )
        except ValueError as e:
            logger.error(f"[{request_id}] Failed to combine signatures: {str(e)}")
            total_time = time.time() - start_time
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Failed to combine signatures",
                        "message": str(e),
                        "request_id": request_id,
                        "performance": {
                            "total_ms": round(total_time * 1000, 2),
                        },
                    }
                ),
                mimetype="application/json",
                status_code=500,
            )
        combine_time = time.time() - combine_start

        # Call Azure OpenAI to select the cleanest signature
        selection_start = time.time()
        selection_result = await _select_cleanest_signature_with_openai(
            combined_image_bytes, request_id, model
        )
        selection_time = time.time() - selection_start

        selected_index = selection_result.get("selected_index")
        selection_reason = selection_result.get("reason", "")

        # Validate selected_index
        if selected_index is None:
            logger.error(f"[{request_id}] OpenAI did not return a selected_index")
            total_time = time.time() - start_time
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Selection failed",
                        "message": "OpenAI did not return a valid signature selection",
                        "request_id": request_id,
                        "performance": {
                            "combine_ms": round(combine_time * 1000, 2),
                            "selection_ms": round(selection_time * 1000, 2),
                            "total_ms": round(total_time * 1000, 2),
                        },
                    }
                ),
                mimetype="application/json",
                status_code=500,
            )

        # Validate selected_index is within range
        selected_index_int = int(selected_index)
        if selected_index_int < 0 or selected_index_int >= len(opencv_signatures):
            logger.error(
                f"[{request_id}] Selected index {selected_index_int} out of range. "
                f"Valid range: 0-{len(opencv_signatures) - 1}"
            )
            total_time = time.time() - start_time
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid selection",
                        "message": f"Selected index {selected_index_int} is out of range. "
                        f"Valid range: 0-{len(opencv_signatures) - 1}",
                        "request_id": request_id,
                        "performance": {
                            "combine_ms": round(combine_time * 1000, 2),
                            "selection_ms": round(selection_time * 1000, 2),
                            "total_ms": round(total_time * 1000, 2),
                        },
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        logger.info(
            f"[{request_id}] GPT selected signature index {selected_index_int}: {selection_reason}"
        )

        # Return the selected signature directly from the input
        cropped_signature = opencv_signatures[selected_index_int]["content"]
        total_time = time.time() - start_time

        # Build response
        result: dict[str, Any] = {
            "cropped_signature": cropped_signature,
            "selected_index": selected_index_int,
            "reason": selection_reason,
            "total_signatures": len(opencv_signatures),
            "model_used": model or AZURE_OPENAI_MODEL,
            "request_id": request_id,
            "performance": {
                "combine_ms": round(combine_time * 1000, 2),
                "selection_ms": round(selection_time * 1000, 2),
                "total_ms": round(total_time * 1000, 2),
            },
        }

        logger.info(
            f"[{request_id}] GPT deduplication completed: "
            f"selected_index={selected_index_int}, "
            f"total_candidates={len(opencv_signatures)}, "
            f"total_time={total_time:.3f}s"
        )

        return func.HttpResponse(
            json.dumps(result), mimetype="application/json", status_code=200
        )

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] GPT deduplication failed after {total_time:.3f}s: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "GPT deduplication failed",
                    "message": str(e),
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )


@app.route(route="adi_crop", methods=["POST"])
@require_api_key
async def adi_crop(req: func.HttpRequest) -> func.HttpResponse:
    """
    Extract and crop handwritten signature from an image using Azure Document Intelligence.
    Returns the cropped signature as a base64-encoded PNG string.

    Query Parameters:
        - model_id (optional): Azure Document Intelligence model ID (default: from env AZURE_DI_MODEL_ID)
        - padding (optional): Additional padding around signature in pixels (default: 4)
        - opencv_upscale (optional): Enable OpenCV post-processing (grayscale, sharpen, upscale 2x) (default: false)
        - opencv_crop (optional): Enable OpenCV signature cropping using contour detection (default: false)

    Request Body:
        JSON with the following fields:
        - content (required): Base64-encoded image content (PNG, JPG, etc.)

    Returns:
        JSON response with cropped signature in base64 format (first detected signature)
        If opencv_upscale=true, the output will be grayscale, sharpened, and upscaled 2x
        If opencv_crop=true, applies contour detection to isolate the handwritten signature region
    """
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] Azure DI signature cropping request initiated")

    try:
        # Validate environment variables
        env_error = _validate_env_variables(
            {
                "AZURE_DI_ENDPOINT": AZURE_DI_ENDPOINT,
                "AZURE_DI_KEY": AZURE_DI_KEY,
            },
            request_id,
        )
        if env_error:
            return env_error

        # Get optional parameters
        model_id = req.params.get("model_id")
        padding_str = req.params.get("padding", "4")
        opencv_upscale_str = req.params.get("opencv_upscale", "false").lower()
        opencv_crop_str = req.params.get("opencv_crop", "false").lower()

        # Validate and parse padding
        padding, padding_error = _validate_padding_parameter(padding_str, request_id)
        if padding_error:
            return padding_error

        opencv_upscale = opencv_upscale_str in ("true", "1", "yes")
        opencv_crop = opencv_crop_str in ("true", "1", "yes")

        # Parse and validate JSON body
        body, body_error = _parse_json_body(req, request_id)
        if body_error:
            return body_error

        # Validate required fields
        fields_error = _validate_required_fields(body, ["content"], request_id)
        if fields_error:
            return fields_error

        base64_content = body.get("content")

        # Decode base64 content
        image_bytes, decode_error = _decode_base64_content(base64_content, request_id)
        if decode_error:
            return decode_error

        logger.info(f"[{request_id}] Processing image ({len(image_bytes)} bytes)")

        # Extract signatures using Azure Document Intelligence
        extraction_start = time.time()
        extraction_result = await _extract_signature_with_doc_intelligence(
            image_bytes, request_id, model_id
        )
        extraction_time = time.time() - extraction_start

        signatures_found = extraction_result.get("signatures_found", 0)
        signatures = extraction_result.get("signatures", [])

        # If no signatures found and both opencv_upscale, opencv_crop are false, return early
        if signatures_found == 0 and not opencv_upscale and not opencv_crop:
            logger.warning(f"[{request_id}] No signatures found in image")
            total_time = time.time() - start_time
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "No signatures found",
                        "message": extraction_result.get(
                            "message", "No handwritten signatures were detected in the image"
                        ),
                        "request_id": request_id,
                        "performance": {
                            "extraction_ms": round(extraction_time * 1000, 2),
                            "total_ms": round(total_time * 1000, 2),
                        },
                    }
                ),
                mimetype="application/json",
                status_code=200,
            )

        logger.info(f"[{request_id}] Found {signatures_found} signature(s)")

        # Determine target signature and bounding box
        crop_start = time.time()
        target_signature: dict[str, Any] | None = None
        bounding_box: dict[str, float] | None = None

        if signatures:
            # Use the first detected signature
            target_signature = signatures[0]
            bounding_box = target_signature.get("bounding_box")
            logger.info(
                f"[{request_id}] Using first signature (ID: {target_signature.get('id')}, field: {target_signature.get('field_name')})"
            )
        else:
            # No signatures found, but opencv_upscale or opencv_crop is enabled
            # Process entire image with OpenCV
            logger.info(
                f"[{request_id}] No signatures detected, processing entire image with OpenCV "
                f"(upscale={opencv_upscale}, crop={opencv_crop})"
            )
        try:
            cropped_base64, opencv_signatures = _crop_signature_from_adi(
                image_bytes, bounding_box, padding, opencv_upscale, opencv_crop, request_id
            )
        except ValueError as e:
            logger.error(f"[{request_id}] Failed to crop signature: {str(e)}")
            total_time = time.time() - start_time
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Cropping failed",
                        "message": str(e),
                        "request_id": request_id,
                        "performance": {
                            "extraction_ms": round(extraction_time * 1000, 2),
                            "total_ms": round(total_time * 1000, 2),
                        },
                    }
                ),
                mimetype="application/json",
                status_code=500,
            )
        except FileNotFoundError as e:
            logger.error(f"[{request_id}] Model file not found: {str(e)}")
            total_time = time.time() - start_time
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Configuration error",
                        "message": str(e),
                        "request_id": request_id,
                        "performance": {
                            "extraction_ms": round(extraction_time * 1000, 2),
                            "total_ms": round(total_time * 1000, 2),
                        },
                    }
                ),
                mimetype="application/json",
                status_code=500,
            )

        crop_time = time.time() - crop_start
        total_time = time.time() - start_time

        # Build response
        result: dict[str, Any] = {
            "cropped_signature": cropped_base64,
            "signatures_found": signatures_found,
            "model_used": model_id or AZURE_DI_MODEL_ID,
            "opencv_upscaling": opencv_upscale,
            "opencv_processing": opencv_crop,
            "request_id": request_id,
            "performance": {
                "extraction_ms": round(extraction_time * 1000, 2),
                "crop_ms": round(crop_time * 1000, 2),
                "total_ms": round(total_time * 1000, 2),
            },
        }

        # Add OpenCV signatures if available
        if opencv_signatures:
            result["opencv_signatures"] = opencv_signatures

        # Add signature info only if a signature was detected
        if target_signature:
            result["signature_info"] = {
                "id": target_signature.get("id"),
                "field_name": target_signature.get("field_name"),
                "page_number": target_signature.get("page_number"),
                "bounding_box": bounding_box,
            }
            logger.info(
                f"[{request_id}] Azure DI signature cropping completed: "
                f"total_signatures={signatures_found}, "
                f"used_id={target_signature.get('id')}, "
                f"field={target_signature.get('field_name')}, "
                f"total_time={total_time:.3f}s"
            )
        else:
            result["signature_info"] = None
            result["message"] = "No signatures detected by Azure DI. OpenCV processing applied to entire image."
            logger.info(
                f"[{request_id}] Azure DI signature cropping completed (no signatures detected): "
                f"opencv_processing applied to entire image, "
                f"total_time={total_time:.3f}s"
            )

        return func.HttpResponse(
            json.dumps(result), mimetype="application/json", status_code=200
        )

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] Azure DI signature cropping failed after {total_time:.3f}s: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Signature cropping failed",
                    "message": str(e),
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )


@app.route(route="sig_compare", methods=["POST"])
@require_api_key
async def sig_compare(req: func.HttpRequest) -> func.HttpResponse:
    """
    Capture signature images and forward them to another endpoint for comparison.

    Accepts multipart/form-data with 2 required files:
    - valid_id: Image of valid ID (front)
    - specimen_signatures: Image of valid ID with specimen signatures

    Query Parameters:
    - forward_endpoint (required): Target endpoint URL to forward the files to

    Forwards files as base64-encoded strings in a POST request to the specified endpoint.
    """
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] Signature comparison forwarding request initiated")

    try:
        # Get forward endpoint from query parameters
        forward_endpoint = req.params.get("forward_endpoint")

        # Validate forward_endpoint URL format
        is_valid, error_message = _validate_url_parameter(forward_endpoint, "forward_endpoint")
        if not is_valid:
            logger.warning(f"[{request_id}] Invalid forward_endpoint: {error_message}")
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

        # Parse multipart form data
        files = req.files

        # Validate required files
        required_files = ["valid_id", "specimen_signatures"]
        for file_key in required_files:
            if file_key not in files:
                logger.warning(f"[{request_id}] Missing required file: {file_key}")
                return func.HttpResponse(
                    json.dumps(
                        {
                            "error": "Missing required files",
                            "message": f"Please provide all required files: {', '.join(required_files)}",
                            "request_id": request_id,
                        }
                    ),
                    mimetype="application/json",
                    status_code=400,
                )

        # Load and validate files
        valid_id_file = files["valid_id"]
        specimen_file = files["specimen_signatures"]

        # Validate file types
        files_to_validate = [
            (valid_id_file, "valid_id"),
            (specimen_file, "specimen_signatures"),
        ]

        for file_obj, name in files_to_validate:
            filename = file_obj.filename or ""
            file_ext = os.path.splitext(filename.lower())[1]
            if file_ext not in ALLOWED_FILE_TYPES:
                logger.warning(f"[{request_id}] Invalid file type for {name}: {file_ext}")
                return func.HttpResponse(
                    json.dumps(
                        {
                            "error": "Invalid file type",
                            "message": f"{name} must be one of: {', '.join(ALLOWED_FILE_TYPES)}",
                            "request_id": request_id,
                        }
                    ),
                    mimetype="application/json",
                    status_code=400,
                )

        logger.info(f"[{request_id}] Reading uploaded files")
        read_start = time.time()

        # Read raw file bytes
        valid_id_bytes = valid_id_file.read()
        specimen_bytes = specimen_file.read()

        # Get original filenames and extensions
        valid_id_filename = valid_id_file.filename or "valid_id"
        specimen_filename = specimen_file.filename or "specimen_signatures"
        valid_id_ext = os.path.splitext(valid_id_filename.lower())[1]
        specimen_ext = os.path.splitext(specimen_filename.lower())[1]

        # Convert PDF files to PNG format
        if valid_id_ext == ".pdf":
            logger.info(f"[{request_id}] Converting valid_id from PDF to PNG")
            valid_id_bytes = _convert_pdf_to_image_bytes(valid_id_bytes, valid_id_filename)
            valid_id_filename = os.path.splitext(valid_id_filename)[0] + ".png"
            logger.info(f"[{request_id}] valid_id converted to PNG ({len(valid_id_bytes)} bytes)")

        if specimen_ext == ".pdf":
            logger.info(f"[{request_id}] Converting specimen_signatures from PDF to PNG")
            specimen_bytes = _convert_pdf_to_image_bytes(specimen_bytes, specimen_filename)
            specimen_filename = os.path.splitext(specimen_filename)[0] + ".png"
            logger.info(f"[{request_id}] specimen_signatures converted to PNG ({len(specimen_bytes)} bytes)")

        # Encode files to base64
        valid_id_base64 = base64.b64encode(valid_id_bytes).decode("utf-8")
        specimen_base64 = base64.b64encode(specimen_bytes).decode("utf-8")

        read_time = time.time() - read_start

        # Prepare payload for forwarding
        forward_payload = {
            "valid_id": {
                "filename": valid_id_filename,
                "content": valid_id_base64,
                "size_bytes": len(valid_id_bytes),
            },
            "specimen_signatures": {
                "filename": specimen_filename,
                "content": specimen_base64,
                "size_bytes": len(specimen_bytes),
            },
            "request_id": request_id,
        }

        logger.info(
            f"[{request_id}] Forwarding files to {forward_endpoint} "
            f"(valid_id: {len(valid_id_bytes)} bytes, specimen: {len(specimen_bytes)} bytes)"
        )

        # Create background task to forward to target endpoint (fire-and-forget)
        async def _forward_in_background() -> None:
            """Forward payload to target endpoint without blocking the response."""
            try:
                timeout = aiohttp.ClientTimeout(total=120)  # 2 minutes timeout for external call
                async with (
                    aiohttp.ClientSession() as session,
                    session.post(
                        forward_endpoint,
                        json=forward_payload,
                        timeout=timeout,
                    ) as response,
                ):
                    response.raise_for_status()
                    logger.info(
                        f"[{request_id}] Forward request successful (status={response.status})"
                    )
            except Exception as e:
                logger.error(
                    f"[{request_id}] Background forward request failed: {str(e)}",
                    exc_info=True,
                )

        # Start background task without awaiting
        asyncio.create_task(_forward_in_background())

        total_time = time.time() - start_time

        result = {
            "status": "accepted",
            "request_id": request_id,
            "forward_endpoint": forward_endpoint,
            "files_forwarded": {
                "valid_id": {
                    "filename": valid_id_filename,
                    "size_bytes": len(valid_id_bytes),
                },
                "specimen_signatures": {
                    "filename": specimen_filename,
                    "size_bytes": len(specimen_bytes),
                },
            },
            "message": "Files accepted and forwarding initiated in background",
            "performance": {
                "read_ms": round(read_time * 1000, 2),
                "total_ms": round(total_time * 1000, 2),
            },
        }

        return func.HttpResponse(
            json.dumps(result),
            mimetype="application/json",
            status_code=202,  # Accepted - request accepted for processing
        )

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] Signature comparison forwarding failed after {total_time:.3f}s: "
            f"{type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Signature comparison forwarding failed",
                    "message": str(e),
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )


@app.route(route="id_masking", methods=["POST"])
@require_api_key
async def id_masking(req: func.HttpRequest) -> func.HttpResponse:
    """
    Mask faces and ID details from an image while preserving signatures.

    This endpoint performs two-stage masking:
    1. Face masking: Detects and masks all faces using Azure Face API
    2. ID detail masking: Masks all document fields (name, address, ID numbers, etc.)
       EXCEPT signature fields using Azure Document Intelligence

    Query Parameters:
        - model_id (optional): Azure Document Intelligence model ID (default: from env AZURE_DI_MODEL_ID)
        - padding (optional): Additional padding around masked regions in pixels (default: 4)
        - skip_face_masking (optional): Skip face detection/masking step (default: false)
        - skip_id_masking (optional): Skip ID details masking step (default: false)

    Request Body:
        JSON with the following fields:
        - filename (required): Name of the image file
        - content (required): Base64-encoded image content

    Returns:
        JSON response with:
        - masked_image: Base64-encoded masked image (PNG format)
        - faces_masked: Number of faces masked
        - fields_masked: Number of ID fields masked
        - signature_fields_preserved: List of signature field names preserved
        - performance: Timing metrics for each processing step
    """
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] ID masking request initiated")

    try:
        # Get optional parameters
        model_id = req.params.get("model_id")
        padding_str = req.params.get("padding", "4")
        skip_face_masking_str = req.params.get("skip_face_masking", "false").lower()
        skip_id_masking_str = req.params.get("skip_id_masking", "false").lower()

        # Validate and parse padding
        padding, padding_error = _validate_padding_parameter(padding_str, request_id)
        if padding_error:
            return padding_error

        skip_face_masking = skip_face_masking_str in ("true", "1", "yes")
        skip_id_masking = skip_id_masking_str in ("true", "1", "yes")

        # At least one masking operation must be enabled
        if skip_face_masking and skip_id_masking:
            logger.warning(f"[{request_id}] Both masking operations skipped")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid parameters",
                        "message": "At least one masking operation must be enabled. Both skip_face_masking and skip_id_masking cannot be true.",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Parse and validate JSON body
        body, body_error = _parse_json_body(req, request_id)
        if body_error:
            return body_error

        # Validate required fields
        fields_error = _validate_required_fields(body, ["filename", "content"], request_id)
        if fields_error:
            return fields_error

        filename = body.get("filename")
        base64_content = body.get("content")

        # Decode base64 content
        image_bytes, decode_error = _decode_base64_content(base64_content, request_id)
        if decode_error:
            return decode_error

        logger.info(
            f"[{request_id}] Processing file: {filename} ({len(image_bytes)} bytes), "
            f"face_masking={not skip_face_masking}, id_masking={not skip_id_masking}"
        )

        # Initialize result tracking
        current_image_bytes = image_bytes
        faces_masked = 0
        fields_masked = 0
        signature_fields_preserved: list[str] = []
        masked_fields: list[dict[str, Any]] = []
        face_time = 0.0
        id_time = 0.0

        # Step 1: Face masking using Azure Face API
        if not skip_face_masking:
            # Validate Face API configuration
            if not AZURE_FACE_API_KEY or not AZURE_FACE_ENDPOINT:
                logger.warning(f"[{request_id}] Azure Face API not configured, skipping face masking")
            else:
                face_start = time.time()

                # Detect faces
                face_result = await _detect_faces_with_azure_face_api(
                    current_image_bytes, request_id
                )

                if face_result.get("error"):
                    logger.warning(
                        f"[{request_id}] Face detection failed: {face_result['error']}, "
                        f"continuing with ID masking"
                    )
                else:
                    faces_masked = face_result.get("faces_found", 0)

                    if faces_masked > 0:
                        # Erase faces from image
                        current_image_bytes = _erase_faces_from_image(
                            current_image_bytes, face_result, request_id
                        )
                        logger.info(f"[{request_id}] Erased {faces_masked} face(s) from image")

                face_time = time.time() - face_start

        # Step 2: ID details masking using Azure Document Intelligence
        if not skip_id_masking:
            # Validate Document Intelligence configuration
            env_error = _validate_env_variables(
                {
                    "AZURE_DI_ENDPOINT": AZURE_DI_ENDPOINT,
                    "AZURE_DI_KEY": AZURE_DI_KEY,
                },
                request_id,
            )
            if env_error:
                # If DI is not configured but face masking was done, return partial result
                if faces_masked > 0:
                    logger.warning(
                        f"[{request_id}] Azure DI not configured, returning face-masked image only"
                    )
                else:
                    return env_error
            else:
                id_start = time.time()

                try:
                    # Mask ID details (preserving signatures)
                    mask_result = await _mask_id_details_with_doc_intelligence(
                        current_image_bytes, request_id, model_id, padding
                    )

                    fields_masked = mask_result.get("fields_masked", 0)
                    signature_fields_preserved = mask_result.get("signature_fields_preserved", [])
                    masked_fields = mask_result.get("masked_fields", [])
                    current_image_bytes = mask_result.get("masked_image_bytes", current_image_bytes)

                    logger.info(
                        f"[{request_id}] Masked {fields_masked} ID field(s), "
                        f"preserved {len(signature_fields_preserved)} signature field(s)"
                    )

                except Exception as e:
                    logger.error(
                        f"[{request_id}] ID masking failed: {type(e).__name__}: {str(e)}"
                    )
                    # If face masking was done, return partial result
                    if faces_masked > 0:
                        logger.warning(
                            f"[{request_id}] Returning face-masked image only due to ID masking error"
                        )
                    else:
                        raise

                id_time = time.time() - id_start

        # Encode final masked image to base64
        encode_start = time.time()
        masked_base64 = base64.b64encode(current_image_bytes).decode("utf-8")
        encode_time = time.time() - encode_start

        total_time = time.time() - start_time

        # Build response
        result: dict[str, Any] = {
            "masked_image": masked_base64,
            "faces_masked": faces_masked,
            "fields_masked": fields_masked,
            "signature_fields_preserved": signature_fields_preserved,
            "masked_fields": masked_fields,
            "model_used": model_id or AZURE_DI_MODEL_ID,
            "request_id": request_id,
            "performance": {
                "face_masking_ms": round(face_time * 1000, 2),
                "id_masking_ms": round(id_time * 1000, 2),
                "encode_ms": round(encode_time * 1000, 2),
                "total_ms": round(total_time * 1000, 2),
            },
        }

        logger.info(
            f"[{request_id}] ID masking completed: "
            f"faces_masked={faces_masked}, "
            f"fields_masked={fields_masked}, "
            f"signatures_preserved={len(signature_fields_preserved)}, "
            f"total_time={total_time:.3f}s"
        )

        return func.HttpResponse(
            json.dumps(result), mimetype="application/json", status_code=200
        )

    except Exception as e:
        total_time = time.time() - start_time
        logger.error(
            f"[{request_id}] ID masking failed after {total_time:.3f}s: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "ID masking failed",
                    "message": str(e),
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )
