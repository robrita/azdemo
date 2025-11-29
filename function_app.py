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
AISEARCH_TIMEOUT_SECONDS = int(os.getenv("AISEARCH_TIMEOUT_SECONDS", "60"))

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

# Signature extraction prompt for Azure OpenAI Vision API - No Center
SIGNATURE_EXTRACTION_PROMPT_NOCENTER = """
You are an expert computer vision assistant specializing in document analysis and signature detection. Your task is to identify and locate handwritten signatures within images.

## Task
Analyze the provided image and identify all handwritten signatures present. A signature is a person's name written in a distinctive, personalized handwriting style, typically used for authentication or authorization purposes.

## Instructions

1. **Carefully examine the entire image** for handwritten signatures
2. **Distinguish signatures from other handwritten text** - signatures typically have:
   - A more stylized, flowing, or cursive appearance
   - Personal flourishes or unique characteristics
   - Different ink color or pen pressure than printed text
   - Placement in typical signature locations (bottom of documents, signature lines, etc.)

3. **For each signature found**, provide:
   - **Location**: Describe where in the image the signature appears (e.g., "bottom right corner", "below the printed text", "on the signature line")
   - **Bounding box coordinates**: Estimated x, y, width, height as percentages of image dimensions
   - **Confidence level**: High, Medium, or Low
   - **Characteristics**: Brief description of the signature's appearance (e.g., "cursive script in blue ink", "printed signature in black")
   - **Legibility**: Whether the signature is legible enough to read the name
   - **Is owner signature**: Boolean indicating if this signature is by the owner/cardholder of the document
     - Set to `true` if the signature appears to be from the document owner, cardholder, Licensee, or primary subject
     - Set to `false` ONLY if there is clear evidence the signature is from an authorized representative, chairman, witness, guarantor, or other third party
     - Look for explicit labels ("Chairman", "Witness", "Authorized Signatory", "Guardian", etc.)
     - **Default to `true` when ownership is ambiguous or unclear**

4. **Exclude the following**:
   - Printed signatures or typed names
   - Initials alone (unless clearly part of a signature)
   - Random handwritten notes that are not signatures
   - Stamps or seal impressions (unless they contain a handwritten component)

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
        "x": <percentage>,
        "y": <percentage>,
        "width": <percentage>,
        "height": <percentage>
      },
      "confidence": "<High|Medium|Low>",
      "characteristics": "<description>",
      "legible": <true|false>,
      "estimated_name": "<name if legible, otherwise null>",
      "is_owner_signature": <true|false>
    }
  ],
  "analysis_notes": "<any additional observations or challenges>"
}
```

## Examples of What to Look For

**Typical Signature Characteristics:**
- Flowing, connected cursive writing
- Underlines or flourishes beneath the name
- Rapid, confident strokes
- May be partially illegible due to speed of writing
- Often appears on designated signature lines
- May include date nearby

**Common Locations:**
- Bottom of contracts or forms
- Next to "Signature:" or "Signed by:" labels
- On signature lines (indicated by "___________")
- In signature blocks with printed name underneath
- On checks, receipts, or official documents

**Owner vs Non-Owner Signatures:**
- **Owner signatures** typically appear on:
  - Primary signature line of ID cards or documents
  - "Cardholder signature" or "Owner signature" sections
  - Main applicant or account holder fields
  - Licensee signature fields (holder of a license)
  - Any signature without explicit third-party labels
- **Non-owner signatures** (set to `false` only with clear evidence) typically appear on:
  - Witness signature lines with "Witness" label
  - "Chairman", "Director", or "Authorized Officer" sections with explicit titles
  - Guardian, parent, or representative signature fields with clear labels
  - Co-signer or guarantor sections with "Guarantor" or "Co-signer" labels

## Edge Cases

- **Multiple signatures**: If there are multiple signatures (e.g., witness signatures, co-signers), identify each separately and determine which is the owner's signature
- **Digital signatures**: If you see a digital signature (typed name in script font), note it but mark it as "digital/printed" rather than handwritten
- **Unclear marks**: If you're uncertain whether a mark is a signature, note it with Low confidence
- **Partially visible signatures**: If a signature is cut off or partially obscured, describe what is visible
- **Ambiguous ownership**: If it's unclear whether a signature is from the owner or another party, **default to `true` (owner signature)** unless there is explicit evidence otherwise

## Analysis Approach

1. First, scan for common signature locations
2. Look for handwriting that differs from printed text
3. Identify flowing or stylized writing patterns
4. Check for signature lines or labels
5. Assess each potential signature against the characteristics listed above
6. **Determine signature ownership** by examining:
   - Labels or titles near the signature (e.g., "Owner", "Cardholder", "Witness", "Chairman")
   - Position on the document (primary vs secondary signature locations)
   - Document type and context
   - **When in doubt, default to owner signature (`true`)**
7. Provide clear, actionable results with confidence levels

Remember: Be thorough but conservative. It's better to report Low confidence than to misidentify non-signature elements as signatures.
"""


# Signature extraction prompt for Azure OpenAI Vision API - Center
SIGNATURE_EXTRACTION_PROMPT_CENTER = """
You are an expert computer vision assistant specializing in document analysis and signature detection. Your task is to identify and locate handwritten signatures within images.

## Task
Analyze the provided image and identify all handwritten signatures present. A signature is a person's name written in a distinctive, personalized handwriting style, typically used for authentication or authorization purposes.

## Instructions

1. **Carefully examine the entire image** for handwritten signatures
2. **Distinguish signatures from other handwritten text** - signatures typically have:
   - A more stylized, flowing, or cursive appearance
   - Personal flourishes or unique characteristics
   - Different ink color or pen pressure than printed text
   - Placement in typical signature locations (bottom of documents, signature lines, etc.)

3. **For each signature found**, provide:
   - **Location**: Describe where in the image the signature appears (e.g., "bottom right corner", "below the printed text", "on the signature line")
   - **Bounding box coordinates**: Estimated x, y, width, height as percentages of image dimensions
     - **IMPORTANT**: Ensure the bounding box is **centered on the signature** with **balanced padding on all sides**
     - Include approximately **10-15% padding** around the actual signature strokes (not too tight, not too loose)
     - The signature should be **visually centered** within the bounding box
     - Adjust the bounding box to maintain symmetry - equal space on left/right and top/bottom where possible
   - **Confidence level**: High, Medium, or Low
   - **Characteristics**: Brief description of the signature's appearance (e.g., "cursive script in blue ink", "printed signature in black")
   - **Legibility**: Whether the signature is legible enough to read the name
   - **Is owner signature**: Boolean indicating if this signature is by the owner/cardholder of the document
     - Set to `true` if the signature appears to be from the document owner, cardholder, Licensee, or primary subject
     - Set to `false` ONLY if there is clear evidence the signature is from an authorized representative, chairman, witness, guarantor, or other third party
     - Look for explicit labels ("Chairman", "Witness", "Authorized Signatory", "Guardian", etc.)
     - **Default to `true` when ownership is ambiguous or unclear**

4. **Exclude the following**:
   - Printed signatures or typed names
   - Initials alone (unless clearly part of a signature)
   - Random handwritten notes that are not signatures
   - Stamps or seal impressions (unless they contain a handwritten component)

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
        "x": <percentage>,
        "y": <percentage>,
        "width": <percentage>,
        "height": <percentage>
      },
      "confidence": "<High|Medium|Low>",
      "characteristics": "<description>",
      "legible": <true|false>,
      "estimated_name": "<name if legible, otherwise null>",
      "is_owner_signature": <true|false>
    }
  ],
  "analysis_notes": "<any additional observations or challenges>"
}
```

## Analysis Approach

1. First, scan for common signature locations
2. Look for handwriting that differs from printed text
3. Identify flowing or stylized writing patterns
4. Check for signature lines or labels
5. Assess each potential signature against the characteristics listed above
6. **Determine signature ownership** by examining:
   - Labels or titles near the signature (e.g., "Owner", "Cardholder", "Witness", "Chairman")
   - Position on the document (primary vs secondary signature locations)
   - Document type and context
   - **When in doubt, default to owner signature (`true`)**
7. **Calculate precise bounding boxes**:
   - Identify the exact extent of the signature strokes (leftmost, rightmost, topmost, bottommost points)
   - Add equal padding on all sides (approximately 10-15% of the signature dimensions)
   - Ensure the signature is centered horizontally and vertically within the bounding box
   - Verify the bounding box doesn't include unnecessary whitespace or adjacent elements
8. Provide clear, actionable results with confidence levels

Remember: Be thorough but conservative. It's better to report Low confidence than to misidentify non-signature elements as signatures.

**Bounding Box Quality Checklist:**
- ✓ Signature is centered within the box (not pushed to one edge)
- ✓ Equal padding on left and right sides
- ✓ Equal padding on top and bottom sides
- ✓ Box captures the complete signature including all flourishes
- ✓ Minimal excess whitespace beyond the padding
- ✓ No adjacent text or elements included unless part of the signature
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
    image_bytes: bytes, request_id: str, model: str | None = None, prompt_center: bool = False
) -> dict[str, Any]:
    """
    Extract handwritten signatures from an image using Azure OpenAI Vision API.
    Uses asyncio.to_thread to wrap the synchronous OpenAI SDK call.

    Args:
        image_bytes: Image file bytes (PNG, JPG, etc.)
        request_id: Request ID for logging
        model: Azure OpenAI model deployment name (defaults to AZURE_OPENAI_MODEL)
        prompt_center: If True, uses SIGNATURE_EXTRACTION_PROMPT_CENTER (centered bounding boxes with balanced padding).
                      If False, uses SIGNATURE_EXTRACTION_PROMPT_NOCENTER (default)

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

    # Choose prompt based on prompt_center parameter
    selected_prompt = SIGNATURE_EXTRACTION_PROMPT_CENTER if prompt_center else SIGNATURE_EXTRACTION_PROMPT_NOCENTER

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
) -> bytes:
    """
    Crop the signature region from an image using OpenCV contour detection.
    Uses adaptive thresholding, morphological operations, and contour filtering
    to isolate the handwritten signature.

    Implementation follows crop_signatures_opencv() from signature_extraction_opencv.ipynb:
    - Extracts individual signature regions with padding
    - Sorts by area and keeps top 3 candidates
    - Returns largest signature by area

    All processing is done in-memory (serverless-compatible).

    Args:
        image_bytes: PNG image bytes
        request_id: Request ID for logging

    Returns:
        Cropped PNG image bytes containing the largest signature region

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

            signature_img = image[y1:y2, x1:x2]
            signatures.append({
                "image": signature_img,
                "bbox": (x1, y1, x2, y2),
                "area": area,
                "aspect_ratio": aspect_ratio,
            })

    # If no valid contours found, return original image
    if not signatures:
        logger.warning(f"[{request_id}] No signature contours found, returning original image")
        return image_bytes

    logger.info(f"[{request_id}] Detected {len(signatures)} signature candidate(s)")

    # Sort by area (largest first) and keep top 3
    signatures.sort(key=lambda s: s["area"], reverse=True)
    top_signatures = signatures[:3]

    logger.info(
        f"[{request_id}] Keeping top {len(top_signatures)} signature(s) by area"
    )

    # If there are 2 or more signatures, combine them vertically
    if len(signatures) >= 2:
        logger.info(f"[{request_id}] Multiple signatures detected, combining vertically with 50px padding")

        # Convert OpenCV images to PIL for easier combining
        pil_images = []
        for sig in signatures:
            # Convert BGR to RGB for PIL
            rgb_img = cv2.cvtColor(sig["image"], cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_img)
            pil_images.append(pil_img)

        # Calculate canvas dimensions
        max_width = max(img.width for img in pil_images)
        padding = 100
        total_height = sum(img.height for img in pil_images) + padding * (len(pil_images) - 1)

        logger.info(
            f"[{request_id}] Canvas size: {max_width}x{total_height} "
            f"({len(pil_images)} signatures with {padding}px padding)"
        )

        # Create white canvas (RGB mode)
        combined_canvas = Image.new("RGB", (max_width, total_height), (255, 255, 255))

        # Paste each signature centered horizontally
        current_y = 0
        for idx, pil_img in enumerate(pil_images):
            # Center horizontally
            x_offset = (max_width - pil_img.width) // 2
            combined_canvas.paste(pil_img, (x_offset, current_y))
            current_y += pil_img.height + padding

            logger.info(
                f"[{request_id}] Pasted signature {idx + 1}/{len(pil_images)}: "
                f"size={pil_img.width}x{pil_img.height}, position=({x_offset}, {current_y - pil_img.height - padding})"
            )

        # Convert back to OpenCV format
        cropped_img = cv2.cvtColor(np.array(combined_canvas), cv2.COLOR_RGB2BGR)

        logger.info(
            f"[{request_id}] Combined signature: output_size={cropped_img.shape[1]}x{cropped_img.shape[0]}"
        )
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

    # Encode cropped signature to PNG bytes
    success, encoded = cv2.imencode(".png", cropped_img)
    if not success:
        raise ValueError("Failed to encode cropped signature to PNG")

    return encoded.tobytes()


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

        # Strategy 2: Fallback to figures (Layout model)
        figures_attr: Any = getattr(result, "figures", None)
        if not regions and figures_attr:
            for idx, fig in enumerate(figures_attr):
                regions_attr_fig: Any = getattr(fig, "bounding_regions", None)
                if regions_attr_fig:
                    for region in regions_attr_fig:
                        page_number_fig: int = int(getattr(region, "page_number", 1))
                        polygon_raw_fig: Any = getattr(region, "polygon", [])
                        polygon_fig: list[float] = (
                            list(polygon_raw_fig) if polygon_raw_fig else []
                        )
                        if polygon_fig:
                            regions.append(
                                (f"figure_{idx+1}", page_number_fig, polygon_fig)
                            )

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
) -> str:
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
        Base64-encoded PNG image string of the cropped signature

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
    if opencv_crop:
        if request_id is None:
            raise ValueError("request_id is required when opencv_crop=True")
        png_bytes = _opencv_crop_signature(png_bytes, request_id)

    # Encode to base64 string
    base64_string = base64.b64encode(png_bytes).decode("utf-8")

    return base64_string


def _crop_signature_from_adi(
    image_bytes: bytes,
    bbox: dict[str, float] | None,
    padding: int = 4,
    opencv_upscale: bool = False,
    opencv_crop: bool = False,
    request_id: str | None = None,
) -> str:
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
        Base64-encoded PNG image string of the cropped signature

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
    if opencv_crop:
        if request_id is None:
            raise ValueError("request_id is required when opencv_crop=True")
        png_bytes = _opencv_crop_signature(png_bytes, request_id)

    # Encode to base64 string
    base64_string = base64.b64encode(png_bytes).decode("utf-8")

    return base64_string


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
        - prompt_center (optional): Use centered bounding box prompt with balanced padding (default: false)

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
        prompt_center_str = req.params.get("prompt_center", "false").lower()

        # Validate and parse padding
        padding, padding_error = _validate_padding_parameter(padding_str, request_id)
        if padding_error:
            return padding_error

        opencv_upscale = opencv_upscale_str in ("true", "1", "yes")
        opencv_crop = opencv_crop_str in ("true", "1", "yes")
        prompt_center = prompt_center_str in ("true", "1", "yes")

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
        extraction_result = await _extract_signature_with_openai(image_bytes, request_id, model, prompt_center)
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
            cropped_base64 = _crop_signature_from_gpt(
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
        result = {
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
            "prompt_centered": prompt_center,
            "opencv_upscaling": opencv_upscale,
            "opencv_processing": opencv_crop,
            "request_id": request_id,
            "performance": {
                "extraction_ms": round(extraction_time * 1000, 2),
                "crop_ms": round(crop_time * 1000, 2),
                "total_ms": round(total_time * 1000, 2),
            },
        }

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
            cropped_base64 = _crop_signature_from_adi(
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


@app.route(route="sig_dedup", methods=["POST"])
@require_api_key
async def sig_dedup(req: func.HttpRequest) -> func.HttpResponse:
    """
    Deduplicate handwritten signature images by combining and cropping.

    Query Parameters:
        - opencv_crop (optional): Enable OpenCV signature cropping using contour detection (default: false)

    Accepts JSON body with up to three base64-encoded signature images:
    - signature1: First signature image (base64)
    - signature2: Second signature image (base64)
    - signature3: Third signature image (base64)

    If only one signature is provided, returns that signature immediately.
    If multiple signatures are provided, combines them vertically and optionally crops to a single signature region.

    Returns the deduplicated signature as a base64-encoded PNG image.
    """
    request_id = _generate_request_id()
    start_time = time.time()
    logger.info(f"[{request_id}] Signature deduplication request initiated")

    try:
        # Get optional parameters
        opencv_crop_str = req.params.get("opencv_crop", "false").lower()
        opencv_crop = opencv_crop_str in ("true", "1", "yes")

        # Parse and validate JSON body
        body, body_error = _parse_json_body(req, request_id)
        if body_error:
            return body_error

        # Extract signature parameters
        signature1_base64 = body.get("signature1", "")
        signature2_base64 = body.get("signature2", "")
        signature3_base64 = body.get("signature3", "")

        # Collect non-empty signatures
        signatures = []
        if signature1_base64:
            signatures.append(("signature1", signature1_base64))
        if signature2_base64:
            signatures.append(("signature2", signature2_base64))
        if signature3_base64:
            signatures.append(("signature3", signature3_base64))

        # Check if all signatures are empty
        if not signatures:
            logger.warning(f"[{request_id}] All signature parameters are empty")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Missing signatures",
                        "message": "At least one signature image must be provided (signature1, signature2, or signature3)",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # If only one signature provided, return it immediately
        if len(signatures) == 1:
            sig_name, sig_base64 = signatures[0]
            logger.info(f"[{request_id}] Only {sig_name} provided, returning immediately")
            total_time = time.time() - start_time
            return func.HttpResponse(
                json.dumps(
                    {
                        "signature_base64": sig_base64,
                        "request_id": request_id,
                        "message": f"Single signature returned ({sig_name} only)",
                        "performance": {
                            "total_ms": round(total_time * 1000, 2),
                        },
                    }
                ),
                mimetype="application/json",
                status_code=200,
            )

        # Multiple signatures provided - decode them
        logger.info(f"[{request_id}] {len(signatures)} signatures provided, proceeding with deduplication")

        decode_start = time.time()
        decoded_images = []

        for sig_name, sig_base64 in signatures:
            sig_bytes, decode_error = _decode_base64_content(sig_base64, request_id)
            if decode_error:
                return decode_error
            decoded_images.append((sig_name, sig_bytes))

        decode_time = time.time() - decode_start

        # Open images using PIL for better handling of different widths
        combine_start = time.time()
        images = []
        try:
            for sig_name, sig_bytes in decoded_images:
                image = Image.open(io.BytesIO(sig_bytes))  # type: ignore[arg-type]
                image = image.convert("RGB")  # Convert to RGB (white background)
                images.append((sig_name, image))
                logger.info(f"[{request_id}] {sig_name}: {image.width}x{image.height}")
        except Exception as e:
            logger.error(f"[{request_id}] Failed to open signature images: {str(e)}")
            return func.HttpResponse(
                json.dumps(
                    {
                        "error": "Invalid image",
                        "message": f"Failed to decode signature images. Please provide valid image formats (PNG, JPEG): {str(e)}",
                        "request_id": request_id,
                    }
                ),
                mimetype="application/json",
                status_code=400,
            )

        # Calculate canvas size: width = max of all widths; height = sum of all heights + padding between images
        padding = 100
        out_width = max(img.width for _, img in images)
        out_height = sum(img.height for _, img in images) + padding * (len(images) - 1)

        logger.info(
            f"[{request_id}] Combining {len(images)} signatures: "
            f"canvas={out_width}x{out_height} (with {padding}px padding between images)"
        )

        # Create a white canvas (RGB mode)
        combined_image = Image.new("RGB", (out_width, out_height), (255, 255, 255))

        # Paste images centered horizontally, stacked vertically with padding
        y_offset = 0
        for sig_name, image in images:
            x_offset = (out_width - image.width) // 2
            combined_image.paste(image, (x_offset, y_offset))
            logger.info(f"[{request_id}] Pasted {sig_name} at position ({x_offset}, {y_offset})")
            y_offset += image.height + padding

        logger.info(
            f"[{request_id}] Combined image size: {combined_image.width}x{combined_image.height}"
        )

        # Convert combined image to PNG bytes
        combined_buffer = io.BytesIO()
        combined_image.save(combined_buffer, format="PNG")
        combined_bytes = combined_buffer.getvalue()
        combine_time = time.time() - combine_start

        # Conditionally apply OpenCV signature cropping
        crop_time = 0.0
        if opencv_crop:
            crop_start = time.time()
            logger.info(f"[{request_id}] Applying OpenCV signature cropping to combined image")
            try:
                cropped_bytes = _opencv_crop_signature(combined_bytes, request_id)
            except ValueError as e:
                logger.error(f"[{request_id}] Signature cropping failed: {str(e)}")
                return func.HttpResponse(
                    json.dumps(
                        {
                            "error": "Signature extraction failed",
                            "message": f"Failed to extract signature from combined image: {str(e)}",
                            "request_id": request_id,
                        }
                    ),
                    mimetype="application/json",
                    status_code=500,
                )
            crop_time = time.time() - crop_start
        else:
            logger.info(f"[{request_id}] Skipping OpenCV cropping (opencv_crop=false)")
            cropped_bytes = combined_bytes

        # Encode result to base64
        encode_start = time.time()
        result_base64 = base64.b64encode(cropped_bytes).decode("utf-8")
        encode_time = time.time() - encode_start

        total_time = time.time() - start_time

        logger.info(
            f"[{request_id}] Signature deduplication completed successfully in {total_time:.3f}s"
        )

        return func.HttpResponse(
            json.dumps(
                {
                    "signature_base64": result_base64,
                    "request_id": request_id,
                    "opencv_processing": opencv_crop,
                    "message": "Signatures deduplicated successfully",
                    "performance": {
                        "decode_ms": round(decode_time * 1000, 2),
                        "combine_ms": round(combine_time * 1000, 2),
                        "crop_ms": round(crop_time * 1000, 2),
                        "encode_ms": round(encode_time * 1000, 2),
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
            f"[{request_id}] Signature deduplication failed after {total_time:.3f}s: "
            f"{type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return func.HttpResponse(
            json.dumps(
                {
                    "error": "Signature deduplication failed",
                    "message": str(e),
                    "request_id": request_id,
                }
            ),
            mimetype="application/json",
            status_code=500,
        )
