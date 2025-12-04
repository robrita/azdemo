# Azure Functions App - Signature Comparison

Azure Function App providing REST API access for signature verification using computer vision and AI embeddings.

## Features

- **Signature Comparison**: Automated signature verification using OpenCV and OpenAI CLIP embeddings
- **Signature Extraction & Enhancement**:
  - **Azure OpenAI Vision API** (GPT-4.1): Natural language-based signature detection with owner/non-owner classification
  - **Azure Document Intelligence**: AI-powered layout analysis with precise polygon bounding boxes
  - **OpenCV Post-Processing**: Optional 2x upscaling (LapSRN), grayscale conversion, and sharpening
- **ID Masking**: Privacy protection for identity documents
  - **Face Masking**: Azure Face API for detecting and masking faces
  - **ID Detail Masking**: Azure Document Intelligence to mask personal information while preserving signatures
- **Parallel Execution**: Batch operations execute concurrently using async/await
- **Multi-Format Support**: Handles PNG, JPG, JPEG, and PDF files
- **API Key Authentication**: Secure endpoints with X-API-Key header (query param fallback)
- **Structured Logging**: Request ID tracking and performance metrics
- **Serverless Compatible**: All operations in-memory, no file system writes required

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
    "average_similarity": 0.87,
    "status": "MATCH"
  },
  "specimen_vs_selfie": {
    "similarities": [0.85, 0.84, 0.83],
    "average_similarity": 0.84,
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

**Signature Extraction Methods**:
The function supports two signature extraction methods:

1. **Azure Document Intelligence (Optional)** - AI-powered signature detection:

   - Uses custom neural models or prebuilt-layout model to detect signature regions
   - More accurate for complex documents and various signature styles
   - Requires Azure Document Intelligence endpoint and key (configured via environment variables)
   - Automatically falls back to OpenCV if not configured or if extraction fails

2. **OpenCV Contour Detection (Default)** - Traditional computer vision:
   - Uses adaptive thresholding and contour analysis
   - No external dependencies or API calls required
   - Works well for clean signatures with good contrast

**Important Notes**:

1. Signatures are automatically extracted using Document Intelligence (if configured) or OpenCV contour detection
2. All signatures are normalized to 300x150 pixels for consistent comparison
3. Features are extracted using HOG (Histogram of Oriented Gradients) and histogram analysis - **no external API calls required**
4. Cosine similarity is used to calculate confidence scores (0.0 to 1.0)
5. At least 3 specimen signatures must be detected from the specimen_signatures image
6. Feature extraction and comparison are done locally using OpenCV - no cloud API dependencies

#### `POST /api/gpt_crop`

Extract and crop handwritten signature from an image using Azure OpenAI Vision API (GPT-4.1).

**Use Case**: Automatically detect and extract signature regions from documents, ID cards, or contracts. Returns the cropped signature as a base64-encoded PNG for further processing or storage.

**Headers**:

- `X-API-Key`: API key for authentication (required)

**Query Parameters** (all optional):

- `model`: Azure OpenAI model deployment name (default: from `AZURE_OPENAI_MODEL` env var, typically `gpt-4.1`)
- `padding`: Additional padding around signature in percent (0-50, default: 5.0)
- `opencv_process`: Enable OpenCV post-processing (`true` or `false`, default: `false`)
  - When enabled, applies grayscale conversion, sharpening (unsharp masking), and 2x upscaling using LapSRN
  - Output image will be grayscale, clearer (not blurred), and 2x larger
  - Useful for improving low-quality or blurry signature images

**Request Body** (application/json):

```json
{
  "filename": "valid_id1.png",
  "content": "iVBORw0KGgoAAAANS...base64_encoded_image_data..."
}
```

- `filename` (required): Name of the image file
- `content` (required): Base64-encoded image content (PNG, JPG, JPEG formats supported)

**Response** (Success - 200):

```json
{
  "cropped_signature": "iVBORw0KGgoAAAANSUhEUgAA...base64_encoded_png_data...",
  "signature_info": {
    "id": 1,
    "location_description": "bottom right corner, on signature line",
    "bounding_box": {
      "x": 65.5,
      "y": 78.2,
      "width": 25.3,
      "height": 8.5
    },
    "confidence": "High",
    "characteristics": "cursive script in blue ink with underline flourish",
    "is_owner_signature": true
  },
  "signatures_found": 2,
  "owner_signatures_found": 1,
  "model_used": "gpt-4.1",
  "opencv_processing": false,
  "request_id": "abc12345",
  "performance": {
    "extraction_ms": 2150.45,
    "crop_ms": 12.34,
    "total_ms": 2162.79
  }
}
```

**Response** (No Signatures Found - 404):

```json
{
  "error": "No signatures found",
  "message": "No handwritten signatures were detected in the image",
  "analysis_notes": "Document appears to be a printed form with no handwritten elements",
  "request_id": "abc12345",
  "performance": {
    "extraction_ms": 2100.12,
    "total_ms": 2100.12
  }
}
```

**Response** (No Owner Signatures Found - 404):

```json
{
  "error": "No owner signatures found",
  "message": "Found 2 signature(s), but none were identified as owner signatures. All detected signatures appear to be from witnesses, chairmen, or other third parties.",
  "signatures_found": 2,
  "owner_signatures_found": 0,
  "analysis_notes": "Detected signatures from 'Witness' and 'Chairman' fields",
  "request_id": "abc12345",
  "performance": {
    "extraction_ms": 2150.34,
    "total_ms": 2150.34
  }
}
```

#### `POST /api/gpt_dedup`

Deduplicate signature crops by selecting the cleanest one using Azure OpenAI Vision API.

**Use Case**: When multiple signature candidates are detected (e.g., from OpenCV contour detection), use GPT to intelligently select the cleanest crop that fully captures the complete handwritten signature with no extra surrounding elements. Returns the selected signature as a base64-encoded PNG.

**Headers**:

- `X-API-Key`: API key for authentication (required)

**Query Parameters** (all optional):

- `model`: Azure OpenAI model deployment name (default: from `AZURE_OPENAI_MODEL` env var, typically `gpt-4.1`)

**Request Body** (application/json):

```json
{
  "opencv_signatures": [
    {
      "content": "iVBORw0KGgoAAAANS...base64_encoded_signature_1..."
    },
    {
      "content": "iVBORw0KGgoAAAANS...base64_encoded_signature_2..."
    }
  ]
}
```

- `opencv_signatures` (required): Array of signature objects, each with:
  - `content` (required): Base64-encoded PNG image of a signature candidate

**How It Works**:

1. The endpoint combines all provided signature images vertically with index labels (similar to OpenCV contour detection output)
2. Sends the combined image to Azure OpenAI Vision API for analysis
3. GPT selects the index of the cleanest signature
4. Returns the original signature image from the selected index

**Response** (Success - 200):

```json
{
  "cropped_signature": "iVBORw0KGgoAAAANSUhEUgAA...base64_encoded_png_data...",
  "selected_index": 0,
  "reason": "Crop 0 fully captures the complete handwritten signature with clean edges and no surrounding elements",
  "total_signatures": 2,
  "model_used": "gpt-4.1",
  "request_id": "abc12345",
  "performance": {
    "combine_ms": 45.23,
    "selection_ms": 1850.45,
    "total_ms": 1895.68
  }
}
```

**Response** (Single Signature - 200):

When only one signature is provided, it's returned directly without GPT analysis:

```json
{
  "cropped_signature": "iVBORw0KGgoAAAANSUhEUgAA...base64_encoded_png_data...",
  "selected_index": 0,
  "reason": "Only one signature provided, no deduplication needed",
  "total_signatures": 1,
  "model_used": "gpt-4.1",
  "request_id": "abc12345",
  "performance": {
    "combine_ms": 0,
    "selection_ms": 0,
    "total_ms": 12.34
  }
}
```

**Response** (Invalid opencv_signatures - 400):

```json
{
  "error": "Invalid opencv_signatures",
  "message": "opencv_signatures must be a non-empty array of signature objects",
  "request_id": "abc12345"
}
```

#### `POST /api/adi_crop`

Extract and crop handwritten signature from an image using Azure Document Intelligence.

**Use Case**: Automatically detect and extract signature regions from documents using AI-powered layout analysis. Returns the cropped signature as a base64-encoded PNG. More accurate than contour detection for complex documents with busy backgrounds.

**Headers**:

- `X-API-Key`: API key for authentication (required)

**Query Parameters** (all optional):

- `model_id`: Azure Document Intelligence model ID (default: from `AZURE_DI_MODEL_ID` env var, typically `prebuilt-layout`)
- `padding`: Additional padding around signature in percent (0-50, default: 5.0)
- `opencv_process`: Enable OpenCV post-processing (`true` or `false`, default: `false`)
  - When enabled, applies 2x upscaling using LapSRN, grayscale conversion, and sharpening (unsharp masking)
  - Output image will be 2x larger, grayscale, and clearer (not blurred)
  - Useful for improving low-quality or small signature images

**Request Body** (application/json):

```json
{
  "content": "iVBORw0KGgoAAAANS...base64_encoded_image_data..."
}
```

- `content` (required): Base64-encoded image content (PNG, JPG, JPEG formats supported)

**Response** (Success - 200):

```json
{
  "cropped_signature": "iVBORw0KGgoAAAANSUhEUgAA...base64_encoded_png_data...",
  "signature_info": {
    "id": 1,
    "field_name": "signature_field",
    "page_number": 1,
    "bounding_box": {
      "min_x": 150.5,
      "min_y": 320.2,
      "max_x": 380.8,
      "max_y": 380.7,
      "width": 230.3,
      "height": 60.5
    }
  },
  "signatures_found": 1,
  "model_used": "prebuilt-layout",
  "opencv_processing": false,
  "request_id": "abc12345",
  "performance": {
    "extraction_ms": 850.45,
    "crop_ms": 8.34,
    "total_ms": 858.79
  }
}
```

**Response** (No Signatures Found - 404):

```json
{
  "error": "No signatures found",
  "message": "No signature regions detected by Document Intelligence",
  "request_id": "abc12345",
  "performance": {
    "extraction_ms": 800.12,
    "total_ms": 800.12
  }
}
```

**Notes**:

- Requires Azure Document Intelligence (Form Recognizer) resource configured
- Uses polygon-based bounding boxes (more accurate than OpenAI Vision percentages)
- Supports both custom trained models and prebuilt layout model
- Custom models with explicit "Signature" fields provide best accuracy
- Fallback to "figures" detection from layout model if no signature fields found

**Response** (Specific Signature Not Found - 404):

```json
{
  "error": "Signature not found",
  "message": "Signature ID 3 not found in owner signatures. Only 2 owner signature(s) were detected.",
  "signatures_found": 3,
  "owner_signatures_found": 2,
  "available_owner_ids": [1, 2],
  "request_id": "abc12345",
  "performance": {
    "extraction_ms": 2200.34,
    "total_ms": 2200.34
  }
}
```

**Signature Detection Logic**:

- Azure OpenAI Vision API analyzes the image to detect handwritten signatures
- Returns bounding box coordinates as percentages of image dimensions
- Distinguishes between owner signatures and third-party signatures (witness, chairman, etc.)
- By default, extracts the first owner signature (typically the primary signer)
- Use `signature_id` parameter to extract a specific signature if multiple are found

#### `POST /api/sig_compare`

Forward signature images to another endpoint for comparison processing. This endpoint acts as a proxy, capturing multipart form data files, encoding them as base64, and forwarding them to a target API endpoint **asynchronously** (fire-and-forget pattern).

**Use Case**: Integration with external signature comparison services or custom processing pipelines that expect base64-encoded image data. Returns immediately without waiting for the target endpoint to respond.

**Headers**:

- `X-API-Key`: API key for authentication (required)

**Query Parameters**:

- `forward_endpoint` (required): Target endpoint URL to forward the files to (must be a valid HTTP/HTTPS URL)

**Request Body** (multipart/form-data):

- `valid_id`: Image file of valid ID (front) - PNG, JPG, JPEG, or PDF (required)
- `specimen_signatures`: Image file with specimen signatures - PNG, JPG, JPEG, or PDF (required)

**Response** (Accepted - 202):

```json
{
  "status": "accepted",
  "request_id": "abc12345",
  "forward_endpoint": "https://your-target-endpoint.com/api/compare",
  "files_forwarded": {
    "valid_id": {
      "filename": "valid_id1.png",
      "size_bytes": 125430
    },
    "specimen_signatures": {
      "filename": "specimen1.png",
      "size_bytes": 98765
    }
  },
  "message": "Files accepted and forwarding initiated in background",
  "performance": {
    "read_ms": 12.34,
    "total_ms": 25.67
  }
}
```

**Forwarded Payload Format**:

The endpoint sends a JSON POST request to the `forward_endpoint` with the following structure:

```json
{
  "valid_id": {
    "filename": "valid_id1.png",
    "content": "iVBORw0KGgoAAAANSUhEUgAA...base64_encoded_content...",
    "size_bytes": 125430
  },
  "specimen_signatures": {
    "filename": "specimen1.png",
    "content": "iVBORw0KGgoAAAANSUhEUgAA...base64_encoded_content...",
    "size_bytes": 98765
  },
  "request_id": "abc12345"
}
```

**Error Responses**:

- **400 Bad Request**: Missing required files, invalid file types, or missing `forward_endpoint` parameter
- **500 Internal Server Error**: Server-side processing error

**Important Notes**:

1. **Asynchronous Processing**: Returns immediately (HTTP 202 Accepted) without waiting for the target endpoint's response
2. **Fire-and-Forget Pattern**: The forward request runs in the background - success/failure is logged but not returned to the client
3. Both `valid_id` and `specimen_signatures` files are required
4. Files are converted to base64 strings before forwarding
5. Forward request timeout is 120 seconds (2 minutes) for the background task
6. All file validation (type, size) happens before accepting the request
7. Uses `aiohttp` for async HTTP requests to the target endpoint
8. Use the `request_id` to correlate requests with server logs for debugging

#### `POST /api/id_masking`

Mask faces and ID details from an image while preserving signatures.

**Use Case**: Privacy protection for identity documents. This endpoint performs two-stage masking:

1. **Face Masking**: Detects and masks all faces using Azure Face API (with expanded padding to cover hair/forehead)
2. **ID Detail Masking**: Masks all document fields (name, address, ID numbers, dates, etc.) EXCEPT signature fields using Azure Document Intelligence

The result is an image with faces and personal information hidden, but signatures preserved for verification purposes.

**Headers**:

- `X-API-Key`: API key for authentication (required)

**Query Parameters**:

- `model_id` (optional): Azure Document Intelligence model ID (default: from env `AZURE_DI_MODEL_ID`)
- `padding` (optional): Additional padding around masked regions in pixels (default: 4, range: 0-50)
- `skip_face_masking` (optional): Skip face detection/masking step (default: false)
- `skip_id_masking` (optional): Skip ID details masking step (default: false)

**Request Body** (application/json):

```json
{
  "filename": "valid_id.png",
  "content": "base64_encoded_image_string"
}
```

**Parameters**:

- `filename` (string, required): Name of the image file
- `content` (string, required): Base64-encoded image content (PNG, JPG, JPEG)

**Response** (Success - 200):

```json
{
  "masked_image": "base64_encoded_masked_image",
  "faces_masked": 1,
  "fields_masked": 8,
  "signature_fields_preserved": ["signature1", "CustomerSignature"],
  "signature_images": {
    "signature1": "base64_encoded_cropped_signature_1",
    "CustomerSignature": "base64_encoded_cropped_signature_2"
  },
  "masked_fields": [
    {
      "index": 1,
      "field_name": "full_name",
      "page_number": 1,
      "bbox": { "min_x": 100, "min_y": 50, "max_x": 400, "max_y": 80 }
    },
    {
      "index": 2,
      "field_name": "address",
      "page_number": 1,
      "bbox": { "min_x": 100, "min_y": 90, "max_x": 500, "max_y": 130 }
    }
  ],
  "model_used": "valid_id2",
  "request_id": "abc12345",
  "performance": {
    "face_masking_ms": 450.23,
    "id_masking_ms": 1200.45,
    "encode_ms": 15.67,
    "signature_crop_ms": 25.34,
    "total_ms": 1691.69
  }
}
```

**Error Responses**:

- **400 Bad Request**: Invalid parameters, missing required fields, or both masking operations skipped
- **401 Unauthorized**: Missing API key
- **403 Forbidden**: Invalid API key
- **500 Internal Server Error**: Processing failed

**Processing Pipeline**:

1. **Input Validation**: Validate parameters and decode base64 image
2. **Face Detection**: Call Azure Face API to detect face locations
3. **Face Masking**: Draw white rectangles over detected faces (with 20% width/height padding, 40% top padding for hair)
4. **Document Analysis**: Call Azure Document Intelligence to detect document fields
5. **Field Filtering**: Identify signature fields vs non-signature fields
6. **ID Masking**: Draw white rectangles over non-signature fields (preserving signatures)
7. **Signature Cropping**: Extract each signature field as individual cropped images
8. **Output Encoding**: Encode final masked image and signature images to base64 PNG

**Partial Results**:

- If Face API is not configured but DI is configured → Only ID details are masked
- If Face API succeeds but DI fails → Returns face-masked image only
- If both fail → Returns appropriate error

**Important Notes**:

1. **Signature Preservation**: Any field containing "signature" in its name is preserved (not masked)
2. **Signature Images**: Each preserved signature is cropped and returned in `signature_images` dictionary, keyed by the actual field name from Azure Document Intelligence (e.g., `signature1`, `CustomerSignature`)
3. **Face Padding**: Faces are masked with expanded rectangles to cover hair, forehead, and ears
4. **Serverless Compatible**: All processing is in-memory (no file system writes)
5. **Async Operations**: Uses `aiohttp` for Face API and `asyncio.to_thread` for Document Intelligence
6. **Custom Models**: Use a custom-trained Document Intelligence model for best field detection accuracy

**Example cURL Request**:

```bash
# Full masking (faces + ID details)
curl -X POST "http://localhost:7071/api/id_masking" \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "driver_license.png",
    "content": "iVBORw0KGgoAAAANS..."
  }'

# Face masking only
curl -X POST "http://localhost:7071/api/id_masking?skip_id_masking=true" \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "selfie.png",
    "content": "iVBORw0KGgoAAAANS..."
  }'

# ID details masking only (no face masking)
curl -X POST "http://localhost:7071/api/id_masking?skip_face_masking=true&model_id=valid_id2" \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "id_card.png",
    "content": "iVBORw0KGgoAAAANS..."
  }'
```

**Configuration Requirements**:

- **Azure Face API**: Set `AZURE_FACE_API_KEY` and `AZURE_FACE_ENDPOINT` environment variables
- **Azure Document Intelligence**: Set `AZURE_DI_ENDPOINT`, `AZURE_DI_KEY`, and optionally `AZURE_DI_MODEL_ID`
- For best results, use a custom-trained Document Intelligence model with explicit field definitions

**Configuration Requirements**:

- Requires Azure OpenAI with vision-capable model (e.g., GPT-4.1, GPT-4o)
- Set `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, and `AZURE_OPENAI_API_VERSION` environment variables
- See Configuration section below for details

**Important Notes**:

1. Uses Azure OpenAI Vision API for signature detection (cloud-based, requires API key)
2. Returns cropped signature as base64-encoded PNG string
3. All processing is serverless-compatible (in-memory only, no file system writes)
4. **Only processes owner signatures** - filters out witness, chairman, and other third-party signatures
5. Supports multiple owner signatures - specify `signature_id` to choose which one to extract
6. Automatically identifies owner vs non-owner signatures based on labels and document context
7. Padding parameter adds extra space around the detected signature (useful for downstream processing)

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
FACE_API_TIMEOUT_SECONDS=60            # Default: 60

# Azure Face API (Required for /id_masking face detection)
# Used to detect and mask faces in ID documents
AZURE_FACE_API_KEY=your-face-api-key
AZURE_FACE_ENDPOINT=https://your-face-instance.cognitiveservices.azure.com/

# Azure Document Intelligence (Optional)
# If provided, signature extraction will use AI-powered detection
# If not provided, falls back to traditional OpenCV contour detection
AZURE_DI_ENDPOINT=https://your-di-instance.cognitiveservices.azure.com/
AZURE_DI_KEY=your-document-intelligence-key
AZURE_DI_MODEL_ID=prebuilt-layout      # Default: prebuilt-layout (or use custom model ID)

# Azure OpenAI (Required for /crop_signature endpoint)
# Vision-capable model required (e.g., GPT-4.1, GPT-4o)
AZURE_OPENAI_API_KEY=your-openai-api-key
AZURE_OPENAI_ENDPOINT=https://your-openai-instance.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-12-01-preview  # Default: 2024-12-01-preview
AZURE_OPENAI_MODEL=gpt-4.1                   # Default: gpt-4.1 (must support vision)

# OpenCV Post-Processing (Required for opencv_process=true in /gpt_crop)
LAPSRN_MODEL_PATH=notebook/LapSRN_x2.pb      # Default: notebook/LapSRN_x2.pb
                                              # Download from: https://github.com/opencv/opencv_contrib/tree/master/modules/dnn_superres
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

# Crop signature from image (Azure OpenAI Vision-based extraction)
curl -X POST "http://localhost:7071/api/gpt_crop?padding=5" \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"filename": "valid_id.jpg", "content": "iVBORw0KGgoAAAANS..."}'

# Crop signature with OpenCV post-processing (grayscale, sharpen, upscale 2x)
curl -X POST "http://localhost:7071/api/gpt_crop?opencv_process=true&padding=10" \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"filename": "valid_id.jpg", "content": "iVBORw0KGgoAAAANS..."}'

# Crop signature using Azure Document Intelligence
curl -X POST "http://localhost:7071/api/adi_crop?padding=5" \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"content": "iVBORw0KGgoAAAANS..."}'

# Azure DI with custom model and OpenCV post-processing
curl -X POST "http://localhost:7071/api/adi_crop?model_id=valid_id2&opencv_process=true&padding=10" \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"content": "iVBORw0KGgoAAAANS..."}'
```

**Note**: For signature comparison testing, you'll need to prepare test images:

- Create a `testdata/` directory
- Add sample images: `valid_id.jpg`, `specimen_signatures.jpg`, `selfie_with_id.jpg`
- Supported formats: PNG, JPG, JPEG, PDF

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
