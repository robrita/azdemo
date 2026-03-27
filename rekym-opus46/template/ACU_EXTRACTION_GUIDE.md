# ACU Document Extraction — Technical Reference

> **Purpose**: End-to-end documentation of the Azure Content Understanding (ACU)
> document extraction pipeline used in this application. Intended as a self-contained
> guide so the extraction capability can be ported to another application.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Azure Content Understanding (ACU) Concepts](#3-azure-content-understanding-acu-concepts)
4. [Analyzer Configuration](#4-analyzer-configuration)
5. [Prerequisites & Dependencies](#5-prerequisites--dependencies)
6. [Configuration Reference](#6-configuration-reference)
7. [Data Models](#7-data-models)
8. [End-to-End Flow](#8-end-to-end-flow)
9. [Core Components](#9-core-components)
    - [9.1 ContentExtractor Client](#91-contentextractor-client)
    - [9.2 TextExtractionService](#92-textextractionservice)
    - [9.3 Blob Storage Service (SAS URL)](#93-blob-storage-service-sas-url)
    - [9.4 Webhook Notifier](#94-webhook-notifier)
10. [Extraction Output Schema](#10-extraction-output-schema)
11. [Pagination Logic](#11-pagination-logic)
12. [API Endpoints](#12-api-endpoints)
13. [Cosmos DB Storage](#13-cosmos-db-storage)
14. [Error Handling & Retry](#14-error-handling--retry)
15. [Porting Checklist](#15-porting-checklist)
16. [Standalone Test Script](#16-standalone-test-script)

---

## 1. Overview

The extraction pipeline converts uploaded files (PDFs, images, Office documents)
into structured Markdown text, paginated page arrays, extracted field values, and
named entities using **Azure Content Understanding (ACU)**.

```
File Upload → Blob Storage → Pending Record (Cosmos DB)
           → [trigger] → Batch Processor → ACU SDK → Parsed Result → Cosmos DB
           → [optional] → Logic App Webhook Notification
```

ACU is a managed Azure AI service (part of Azure AI Services) that combines
OCR, layout analysis, and LLM-powered field extraction in a single API call.

---

## 2. Architecture

### Layers

```
Route Layer          →  POST /api/v1/extractions/process-pending
                         GET  /api/v1/extractions/{partnerId}
                         GET  /api/v1/extractions/{partnerId}/files/{fileMetadataId}

Service Layer        →  TextExtractionService
                         • Claims pending records
                         • Orchestrates parallel ACU calls
                         • Fires webhook notifications

Library Layer        →  ContentExtractor (ACU SDK wrapper)
                         BlobStorageService (SAS URL generation)
                         ExtractionWebhookNotifier (Logic App callbacks)

Repository Layer     →  UploadFileContentRepository (Cosmos DB CRUD)

Data Store           →  Azure Cosmos DB  (container: "upload-content")
                         Azure Blob Storage (container: "upload-files")
```

### Component Diagram

```
┌─────────────────┐     ┌──────────────────────────────┐
│  Logic App /     │────▶│  POST /process-pending       │
│  Timer Trigger   │     │  (extraction route)          │
└─────────────────┘     └────────────┬─────────────────┘
                                     │
                        ┌────────────▼─────────────────┐
                        │  TextExtractionService        │
                        │  .process_pending()           │
                        │                               │
                        │  1. Query pending records     │
                        │  2. Mark as "processing"      │
                        │  3. Generate SAS URLs         │
                        │  4. Call ACU (parallel)        │
                        │  5. Parse & store results     │
                        │  6. Notify webhook            │
                        └───┬──────────┬───────────┬───┘
                            │          │           │
                   ┌────────▼──┐ ┌─────▼────┐ ┌───▼───────────┐
                   │ Cosmos DB │ │ ACU SDK  │ │ Blob Storage  │
                   │ upload-   │ │ (Azure   │ │ (SAS URL gen) │
                   │ content   │ │  AI)     │ └───────────────┘
                   └───────────┘ └──────────┘
```

---

## 3. Azure Content Understanding (ACU) Concepts

| Concept         | Description |
|-----------------|-------------|
| **Endpoint**    | Regional Azure AI Services URL (e.g. `https://<resource>.services.ai.azure.com/`) |
| **Analyzer**    | A named configuration that defines how documents are processed — which OCR, layout, and field extraction features are enabled |
| **Base Analyzer** | `prebuilt-document` — the built-in document analysis model that ACU extends |
| **Field Schema** | JSON definition of custom fields the analyzer should extract using LLM generation |
| **Analysis Input** | A URL (SAS-signed blob URL) pointing to the document to analyze |
| **Analysis Result** | The structured output: markdown, fields, pages, entities |
| **Poller**       | ACU operations are long-running; the SDK returns a poller that resolves when complete |

### Authentication

- Uses **Microsoft Entra ID** (Azure AD) via `DefaultAzureCredential`
- No API keys — all authentication is identity-based
- The service principal / managed identity needs the **Cognitive Services User** role on the ACU resource

---

## 4. Analyzer Configuration

The analyzer is pre-provisioned in Azure and its definition is stored locally at
`backend/data/parser.json` for reference.

```json
{
  "analyzerId": "parser",
  "baseAnalyzerId": "prebuilt-document",
  "config": {
    "returnDetails": false,
    "enableOcr": true,
    "enableLayout": true,
    "enableFormula": true,
    "enableFigureDescription": false,
    "enableFigureAnalysis": false,
    "chartFormat": "chartjs",
    "tableFormat": "html",
    "enableSegment": false,
    "omitContent": false,
    "segmentPerPage": false,
    "annotationFormat": "markdown"
  },
  "models": {
    "completion": "gpt-4.1",
    "embedding": "text-embedding-3-large"
  },
  "fieldSchema": {
    "fields": {
      "entities": {
        "type": "array",
        "method": "generate",
        "description": "A deduplicated list of key named items as 'key=value' pairs. Keys: firstName, lastName, middleName, suffix, birthDate, address, city, province, country, zipCode, email, phone, tin, sss, companyName, tradeName, registrationNumber, amount, currency, date, referenceNumber, position, nationality."
      },
      "docType": {
        "type": "string",
        "method": "generate",
        "description": "The classification of the document (report, contract, policy, ID, certificate, etc.)"
      }
    }
  }
}
```

### Key Configuration Flags

| Flag | Value | Effect |
|------|-------|--------|
| `enableOcr` | `true` | Runs OCR on scanned/image documents |
| `enableLayout` | `true` | Detects tables, headings, paragraphs |
| `enableFormula` | `true` | Extracts mathematical formulas |
| `tableFormat` | `"html"` | Tables rendered as HTML in markdown output |
| `chartFormat` | `"chartjs"` | Chart data formatted as Chart.js JSON |
| `annotationFormat` | `"markdown"` | Output format for the extracted content |

### Custom Fields (LLM-Generated)

| Field | Type | Method | Purpose |
|-------|------|--------|---------|
| `entities` | `array<string>` | `generate` | Named entity pairs like `"firstName=John"`, `"tin=123-456-789"` |
| `docType` | `string` | `generate` | Document classification (e.g. "report", "contract", "ID") |

To add more custom fields, update the `fieldSchema.fields` in the analyzer configuration
via the ACU management API or Azure portal.

---

## 5. Prerequisites & Dependencies

### Azure Resources

| Resource | Purpose |
|----------|---------|
| **Azure AI Services** (Content Understanding) | Document extraction engine |
| **Azure Blob Storage** | Stores uploaded files; ACU reads via SAS URL |
| **Azure Cosmos DB** (NoSQL) | Stores extraction records and results |
| **Azure Logic App** *(optional)* | Triggers extraction processing; receives completion callbacks |

### Python Packages

```
azure-ai-contentunderstanding==1.0.1    # ACU SDK
azure-identity==1.25.1                  # Entra ID auth (DefaultAzureCredential)
azure-storage-blob==12.26.0             # Blob storage (upload + SAS generation)
azure-cosmos==4.14.6                    # Cosmos DB SDK
aiohttp==3.13.3                         # Async HTTP for webhook calls
pydantic==2.12.5                        # Data models
fastapi==0.129.2                        # Web framework (optional for porting)
```

### Identity / RBAC Requirements

| Principal | Role | Scope |
|-----------|------|-------|
| App identity (Managed Identity or developer) | **Cognitive Services User** | ACU resource |
| App identity | **Storage Blob Data Contributor** | Blob Storage account |
| App identity | *(Cosmos DB contributor or custom)* | Cosmos DB account |

---

## 6. Configuration Reference

All settings are loaded from environment variables via `pydantic-settings`.

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `ACU_ENDPOINT` | `""` | ACU base URL (e.g. `https://<resource>.services.ai.azure.com/`) |
| `ACU_ANALYZER_ID` | `""` | Analyzer name (e.g. `"parser"` or `"extractor"`) |
| `ACU_API_VERSION` | `"2025-11-01"` | ACU REST API version |
| `ACU_TIMEOUT_SECONDS` | `60` | Timeout for ACU HTTP requests |
| `EXTRACTION_BATCH_SIZE` | `20` | Max pending records per processing trigger |
| `BLOB_STORAGE_ACCOUNT_URL` | `""` | Blob account URL |
| `UPLOAD_BLOB_CONTAINER_NAME` | `"upload-files"` | Blob container for uploaded files |
| `LOGIC_APP_EXTRACTION_WEBHOOK_URL` | `""` | Webhook to ping after upload (triggers processing) |
| `LOGIC_APP_EXTRACTION_COMPLETE_WEBHOOK_URL` | `""` | Webhook to post after extraction batch completes |
| `COSMOS_ENDPOINT` | `""` | Cosmos DB account endpoint |
| `COSMOS_DATABASE` | `"myapp"` | Cosmos DB database name |
| `COSMOS_AUTH_MODE` | `"entra"` | `"entra"` (DefaultAzureCredential) or `"key"` |
| `INTERNAL_API_TOKEN` | `""` | Bearer token for internal API endpoints |

---

## 7. Data Models

### UploadFileContent (Cosmos DB document)

This is the central record that tracks each file through the extraction pipeline.

```python
class UploadFileContent(BaseModel):
    id: str                    # "uploadFileContent:{fileMetadataId}"
    upload_id: str             # Cosmos alias: "uploadId"
    partner_id: str            # Cosmos alias: "partnerId" — PARTITION KEY
    file_metadata_id: str      # Cosmos alias: "fileMetadataId"
    original_file_name: str    # Cosmos alias: "originalFileName"
    content_type: str          # Cosmos alias: "contentType" (MIME type)
    blob_name: str             # Cosmos alias: "blobName" (full blob path)
    status: str                # "pending" | "processing" | "completed" | "failed"
    operation_location: str    # Cosmos alias: "operationLocation" (ACU poller URL)
    markdown: str | None       # Full extracted markdown text
    pages: list[dict] | None   # Paginated content array
    page_count: int | None     # Cosmos alias: "pageCount"
    file_type: str | None      # Cosmos alias: "fileType" (detected: pdf, image, etc.)
    fields: dict | None        # Normalized extracted fields (excl. entities & docType)
    entities: list[str] | None # Extracted entity key=value pairs
    doc_type: str | None       # Cosmos alias: "docType" (document classification)
    analyzer_id: str | None    # Cosmos alias: "analyzerId" (which analyzer was used)
    extracted_at: datetime     # Cosmos alias: "extractedAt"
    error_message: str | None  # Cosmos alias: "errorMessage"
    correlation_id: str        # Cosmos alias: "correlationId"
    created_at: datetime       # Cosmos alias: "createdAt"
    updated_at: datetime       # Cosmos alias: "updatedAt"
```

### Cosmos DB Container

| Property | Value |
|----------|-------|
| Container name | `upload-content` |
| Partition key | `/partnerId` |
| Document ID format | `uploadFileContent:{fileMetadataId}` |

### ExtractionResult (internal dataclass — not persisted)

```python
@dataclass
class ExtractionResult:
    status: str                    # "completed" | "failed"
    markdown: str | None           # Full markdown text
    pages: list[dict]              # Paginated content
    page_count: int                # Number of pages
    file_type: str | None          # Detected file type
    fields: dict                   # Normalized fields (excl. entities, docType)
    entities: list[str]            # Entity key=value pairs
    doc_type: str | None           # Document classification
    analyzer_id: str | None        # Analyzer that produced the result
    api_version: str | None        # ACU API version
    error_message: str | None      # Error details (on failure)
```

---

## 8. End-to-End Flow

### Phase 1: File Upload (creates pending record)

```
1. User uploads file(s) via POST /api/v1/public-uploads/{uploadId}/files
2. PublicUploadService validates, scans for malware, stores in Blob Storage
3. For each accepted file, a pending UploadFileContent record is created in Cosmos DB:
     id = "uploadFileContent:{fileMetadataId}"
     status = "pending"
     blobName = "{partnerId}/{uploadId}/{storedFileName}"
4. After all files are stored, the extraction webhook is pinged (best-effort POST)
   to trigger extraction processing
```

### Phase 2: Extraction Processing (batch)

```
1. Logic App or timer calls POST /api/v1/extractions/process-pending
2. TextExtractionService.process_pending() runs:
   a. Query Cosmos for up to EXTRACTION_BATCH_SIZE records with
      status IN ('pending', 'failed', 'processing')
      ORDER BY createdAt ASC
   b. Mark all claimed records as status = "processing"
   c. For each record IN PARALLEL:
      i.   Generate a read-only SAS URL for the blob (30-min expiry)
      ii.  Call ACU SDK: client.begin_analyze(analyzer_id, inputs=[AnalysisInput(url=sas_url)])
      iii. Await poller.result() → AnalysisResult
      iv.  Parse result → ExtractionResult (markdown, pages, fields, entities, docType)
      v.   Update Cosmos record with results (status = "completed") or error (status = "failed")
   d. Collect unique partnerIds from the batch
   e. POST {"partnerIds": [...]} to the extraction-complete webhook (fire-and-forget)
3. Return summary: { processed, skipped, remaining, partnerIds, results }
```

### Phase 3: Query Results

```
GET /api/v1/extractions/{partnerId}                          → all records for a partner
GET /api/v1/extractions/{partnerId}?uploadId={uploadId}      → filter by upload
GET /api/v1/extractions/{partnerId}/files/{fileMetadataId}   → single file result
```

---

## 9. Core Components

### 9.1 ContentExtractor Client

**File**: `backend/src/lib/text_extraction.py`

The ACU SDK wrapper. This is the key component to port.

```python
from azure.ai.contentunderstanding.aio import ContentUnderstandingClient
from azure.ai.contentunderstanding.models import AnalysisInput, AnalysisResult
from azure.identity.aio import DefaultAzureCredential

class ContentExtractor:
    def __init__(self, settings):
        self._endpoint = settings.acu_endpoint.rstrip("/")
        self._analyzer_id = settings.acu_analyzer_id
        self._api_version = settings.acu_api_version
        self._credential = None
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._credential = DefaultAzureCredential()
            self._client = ContentUnderstandingClient(
                endpoint=self._endpoint,
                credential=self._credential,
                api_version=self._api_version,
            )
        return self._client

    async def extract(self, url, content_type, *, correlation_id="-"):
        client = self._get_client()
        poller = await client.begin_analyze(
            analyzer_id=self._analyzer_id,
            inputs=[AnalysisInput(url=url)],
        )
        result: AnalysisResult = await poller.result()
        return self._parse_result(result, content_type)

    async def close(self):
        if self._client: await self._client.close()
        if self._credential: await self._credential.close()
```

#### How `_parse_result` Works

1. Iterates over `result.contents` — each content item has optional `markdown`, `fields`, `end_page_number`
2. Concatenates all `markdown` parts with `\n\n` separator
3. Extracts `entities` field (type=array) → list of `"key=value"` strings
4. Extracts `docType` field → string classification
5. Normalizes remaining fields (extracts `.value`, converts dates to ISO strings)
6. Detects file type from MIME content type
7. Paginates markdown content (see [Section 11](#11-pagination-logic))

#### File Type Detection

```python
def detect_file_type(content_type: str) -> str:
    mapping = {
        "/pdf": "pdf",
        "image/": "image",
        ".document": "docx",       # wordprocessingml
        ".sheet": "xlsx",           # spreadsheetml
        ".presentation": "pptx",    # presentationml
        "/csv": "csv",
        "/json": "json",
        "audio/": "audio",
        "video/": "video",
        "text/": "text",
    }
    # Returns first match or "unknown"
```

### 9.2 TextExtractionService

**File**: `backend/src/services/text_extraction_service.py`

Orchestrates batch processing:

1. **Claim**: Queries up to `extraction_batch_size` processable records
2. **Lock**: Marks them all as `"processing"` before starting ACU calls
3. **Process**: Runs `_safe_extract_file()` for each record via `asyncio.gather()` (parallel)
4. **Notify**: Fire-and-forget webhook with affected partner IDs
5. **Count**: Returns remaining processable records

Each `_safe_extract_file` wrapper catches all exceptions so `gather()` never bubbles failures.

### 9.3 Blob Storage Service (SAS URL)

**File**: `backend/src/lib/blob_storage.py`

ACU needs a URL to read the document. This service generates a **User Delegation SAS** URL:

```python
async def generate_sas_url(self, blob_name: str, *, expiry_minutes: int = 30) -> str:
    # 1. Get user delegation key from blob service client
    user_delegation_key = await blob_service_client.get_user_delegation_key(
        key_start_time=now, key_expiry_time=now + 30min
    )
    # 2. Generate SAS token with read-only permission
    sas_token = generate_blob_sas(
        account_name=...,
        container_name=...,
        blob_name=blob_name,
        user_delegation_key=user_delegation_key,
        permission=BlobSasPermissions(read=True),
        expiry=expiry_time,
    )
    # 3. Return full URL: blob_url + "?" + sas_token
```

**Key points for porting:**
- Uses Entra ID (no storage account keys)
- SAS is short-lived (30 minutes)
- ACU must be able to reach the blob URL (network access)

### 9.4 Webhook Notifier

**File**: `backend/src/lib/extraction_webhook.py`

Two optional webhooks (empty URL = disabled):

| Webhook | Trigger | Payload |
|---------|---------|---------|
| `LOGIC_APP_EXTRACTION_WEBHOOK_URL` | After files uploaded | `POST` (no body) |
| `LOGIC_APP_EXTRACTION_COMPLETE_WEBHOOK_URL` | After extraction batch | `POST {"partnerIds": [...]}` |

Both are best-effort: failures are logged but never propagated.

---

## 10. Extraction Output Schema

### Full Extraction Response (API)

```json
{
  "id": "uploadFileContent:uploadFile:F6YXWJQG:abc123",
  "uploadId": "F6YXWJQG",
  "partnerId": "partner-123",
  "fileMetadataId": "uploadFile:F6YXWJQG:abc123",
  "originalFileName": "Tax_Certificate.pdf",
  "contentType": "application/pdf",
  "blobName": "partner-123/F6YXWJQG/f907b426-Tax_Certificate.pdf",
  "status": "completed",
  "markdown": "# Tax Certificate\n\nIssued to John Smith...\n\n<!-- PageBreak -->\n\nPage 2 content...",
  "pages": [
    { "page_number": 1, "content": "# Tax Certificate\n\nIssued to John Smith..." },
    { "page_number": 2, "content": "Page 2 content..." }
  ],
  "pageCount": 2,
  "fileType": "pdf",
  "fields": {
    "customField1": "extracted value"
  },
  "entities": [
    "firstName=John",
    "lastName=Smith",
    "tin=123-456-789",
    "companyName=Acme Corp"
  ],
  "docType": "certificate",
  "analyzerId": "parser",
  "extractedAt": "2026-03-14T10:30:00Z",
  "errorMessage": null,
  "createdAt": "2026-03-14T10:28:00Z",
  "updatedAt": "2026-03-14T10:30:00Z"
}
```

### Entities Format

Entities are `"key=value"` pairs extracted by the LLM. Common keys:

```
firstName, lastName, middleName, suffix, birthDate,
address, city, province, country, zipCode,
email, phone, tin, sss,
companyName, tradeName, registrationNumber,
amount, currency, date, referenceNumber,
position, nationality
```

---

## 11. Pagination Logic

**File**: `backend/src/lib/text_extraction.py` → `paginate_markdown_content()`

Markdown content is split into pages for downstream consumption:

### Strategy by File Type

| File Type | Strategy |
|-----------|----------|
| **PDF** | Split on `<!-- PageBreak -->` markers (inserted by ACU). Fall back to sentence-based chunking if no markers. |
| **XLSX** | Split on `# SheetName` headers (markdown H1s). Falls back to default pagination. |
| **All others** | Default pagination: PageBreak markers → sentence-based chunking |

### Default Pagination Algorithm

```
1. If content contains "<!-- PageBreak -->" markers:
   → Split on markers, each non-empty segment = one page

2. If content ≤ 15,000 chars:
   → Single page (or split on PageBreak if present)

3. Otherwise, sentence-based chunking:
   → Split on double-newlines
   → Accumulate sentences until chunk ≥ 10,000 chars
   → Emit page, reset accumulator
   → If final chunk < 10,000 chars, merge with previous page
```

### Page Object Structure

```json
{
  "page_number": 1,
  "content": "Markdown content for this page..."
}
```

---

## 12. API Endpoints

All extraction endpoints require `Authorization: Bearer {INTERNAL_API_TOKEN}`.

### Process Pending Extractions

```http
POST /api/v1/extractions/process-pending
Authorization: Bearer {token}
```

**Response** (`ProcessPendingResponse`):

```json
{
  "processed": 5,
  "skipped": 0,
  "remaining": 12,
  "partnerIds": ["partner-123", "partner-456"],
  "results": [
    {
      "fileMetadataId": "uploadFile:F6YXWJQG:abc123",
      "uploadId": "F6YXWJQG",
      "partnerId": "partner-123",
      "status": "completed",
      "pageCount": 3,
      "errorMessage": null
    }
  ]
}
```

### List Extractions by Partner

```http
GET /api/v1/extractions/{partnerId}
GET /api/v1/extractions/{partnerId}?uploadId={uploadId}
Authorization: Bearer {token}
```

**Response** (`ExtractionListResponse`):

```json
{
  "partnerId": "partner-123",
  "extractions": [ /* array of ExtractionFileResponse */ ]
}
```

### Get Single Extraction

```http
GET /api/v1/extractions/{partnerId}/files/{fileMetadataId}
Authorization: Bearer {token}
```

---

## 13. Cosmos DB Storage

### Container: `upload-content`

| Property | Value |
|----------|-------|
| Partition key | `/partnerId` |
| ID format | `uploadFileContent:{fileMetadataId}` |

### Example Document (Cosmos DB)

```json
{
  "id": "uploadFileContent:uploadFile:F6YXWJQG:abc123hex",
  "uploadId": "F6YXWJQG",
  "partnerId": "partner-123",
  "fileMetadataId": "uploadFile:F6YXWJQG:abc123hex",
  "originalFileName": "Tax_Certificate.pdf",
  "contentType": "application/pdf",
  "blobName": "partner-123/F6YXWJQG/f907b4-Tax_Certificate.pdf",
  "status": "completed",
  "operationLocation": null,
  "markdown": "# Tax Certificate\n\n...",
  "pages": [
    { "page_number": 1, "content": "..." }
  ],
  "pageCount": 2,
  "fileType": "pdf",
  "fields": {},
  "entities": ["firstName=John", "lastName=Smith"],
  "docType": "certificate",
  "analyzerId": "parser",
  "extractedAt": "2026-03-14T10:30:00+00:00",
  "errorMessage": null,
  "correlationId": "req-uuid-here",
  "createdAt": "2026-03-14T10:28:00+00:00",
  "updatedAt": "2026-03-14T10:30:00+00:00"
}
```

### Key Queries

```sql
-- Get processable records (batch claim)
SELECT TOP @limit * FROM c
WHERE c.status IN ('pending', 'failed', 'processing')
ORDER BY c.createdAt ASC

-- Count remaining
SELECT VALUE COUNT(1) FROM c
WHERE c.status IN ('pending', 'failed', 'processing')

-- Get by partner (partition-scoped)
SELECT * FROM c WHERE c.partnerId = @partnerId

-- Get completed by partner
SELECT * FROM c WHERE c.partnerId = @partnerId AND c.status = 'completed'

-- Get by upload (cross-partition)
SELECT * FROM c WHERE c.uploadId = @uploadId
```

---

## 14. Error Handling & Retry

### ACU Client Errors

| Error | Handling |
|-------|----------|
| `ClientAuthenticationError` | Record marked `"failed"`, message: `"authentication error"` |
| `AzureError` (generic) | Record marked `"failed"`, message: `"service error"` |
| Any unhandled exception | Caught by `_safe_extract_file`, record marked `"failed"` |

### Retry Strategy

- Failed records are **automatically retried** because `get_all_processable()` queries
  `status IN ('pending', 'failed', 'processing')`.
- Each call to `process_pending` re-claims failed records along with new pending ones.
- No exponential backoff — retry is driven by the external trigger cadence (Logic App timer).

### Batch Isolation

`asyncio.gather()` with individual `try/except` wrappers ensures one file failure
does not block other files in the same batch.

---

## 15. Porting Checklist

To export this extraction capability to another application:

### Minimum Viable Port

- [ ] **Install SDK**: `pip install azure-ai-contentunderstanding azure-identity azure-storage-blob`
- [ ] **Copy `ContentExtractor` class** from `backend/src/lib/text_extraction.py`
  - Includes: `ContentExtractor`, `ExtractionResult`, `detect_file_type`, `paginate_markdown_content`
  - Only dependency: `Settings` object with `acu_endpoint`, `acu_analyzer_id`, `acu_api_version`, `acu_timeout_seconds`
- [ ] **Configure ACU endpoint + analyzer** — provision an Azure AI Services resource and create an analyzer (use `parser.json` as template)
- [ ] **Provide document URL** — either a SAS URL or publicly accessible URL to the document
- [ ] **Handle `ExtractionResult`** — the output includes `markdown`, `pages`, `fields`, `entities`, `doc_type`

### Minimal Usage Example

```python
import asyncio
from dataclasses import dataclass

@dataclass
class MinimalSettings:
    acu_endpoint: str = "https://your-resource.services.ai.azure.com/"
    acu_analyzer_id: str = "parser"
    acu_api_version: str = "2025-11-01"
    acu_timeout_seconds: int = 60

async def extract_document(document_url: str):
    from text_extraction import ContentExtractor  # copy from backend/src/lib/

    settings = MinimalSettings()
    extractor = ContentExtractor(settings)
    try:
        result = await extractor.extract(
            url=document_url,
            content_type="application/pdf",
            correlation_id="test-001",
        )
        print(f"Status: {result.status}")
        print(f"Pages: {result.page_count}")
        print(f"Doc type: {result.doc_type}")
        print(f"Entities: {result.entities}")
        print(f"Markdown (first 500): {(result.markdown or '')[:500]}")
    finally:
        await extractor.close()

asyncio.run(extract_document("https://storage.blob.core.windows.net/...?sv=...&sig=..."))
```

### Full Port (with persistence & batch processing)

- [ ] Copy `ContentExtractor` + helpers (above)
- [ ] Copy `TextExtractionService` from `backend/src/services/text_extraction_service.py`
- [ ] Set up Cosmos DB container `upload-content` with partition key `/partnerId`
- [ ] Copy `UploadFileContentRepository` from `backend/src/repositories/upload_file_content.py`
- [ ] Copy `UploadFileContent` model from `backend/src/models/upload_file_content.py`
- [ ] Copy `BlobStorageService.generate_sas_url()` from `backend/src/lib/blob_storage.py`
- [ ] Copy `ExtractionWebhookNotifier` from `backend/src/lib/extraction_webhook.py` (optional)
- [ ] Wire up configuration env vars (see [Section 6](#6-configuration-reference))
- [ ] Create a trigger (timer, queue, HTTP) to call `process_pending()` periodically

---

## 16. Standalone Test Script

A ready-to-run test script exists at `backend/scripts/test_acu_api.py`. It:

1. Downloads a blob using `DefaultAzureCredential`
2. Submits binary content directly to ACU via `begin_analyze_binary()`
3. Prints the full parsed result

```bash
# Requires: az login (or managed identity)
python backend/scripts/test_acu_api.py
```

This script demonstrates the **simplest possible ACU integration** — no Cosmos DB,
no batch processing, just a direct SDK call with binary content.

> **Note**: The production flow uses `begin_analyze()` with a SAS URL (not binary upload).
> The test script uses `begin_analyze_binary()` for convenience.
