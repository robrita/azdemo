# Document Processing Dashboard - AI Agent Instructions

## Project Overview
A Streamlit-based document extraction platform that processes BIR (Bureau of Internal Revenue) tax documents using multiple Azure AI services in parallel. Built with modern Python tooling (uv + pyproject.toml) and follows a pluggable service handler architecture.

## Architecture & Key Patterns

### Service Handler Pattern
All extraction services follow a standardized interface in `handlers/`:
- Each handler class implements `__init__(service_name)` and `extract(uploaded_file) -> Dict[str, Any]`
- Handlers read environment variables for Azure endpoints/keys (see `.env.example`)
- All handlers must call `save_extraction_to_json()` from `utils.py` to persist results to `outputs/extract_results.json`
- Error handling returns dict with `"error"` key - never raise exceptions to user
- Processing time tracking is mandatory (use `time.time()` start/end pattern)

**Active handlers:**
- `DocumentIntelligence`: Azure Document Intelligence with template/neural models (selected by service name)
- `MistralDocumentAI`: Mistral Document AI using base64-encoded documents with JSON schema extraction
- `ContentUnderstanding`, `GPT5ForVision`, `GPT41ForVision`: Placeholder/mock implementations

### Async Parallel Processing
Document extraction runs services concurrently (see `pages/1_Document_Extraction.py`):
```python
async def process_file_with_services_async(file, selected_services):
    # Creates asyncio tasks for all services
    # Uses ThreadPoolExecutor for blocking I/O operations
    # Returns consolidated results with processing summary
```
This pattern enables 3-5x speedup when processing multiple services on same file.

### Standardized Data Format
All extraction results follow this schema (`outputs/extract_results.json`):
```json
{
  "results": [{
    "file_name": "document.pdf",
    "service_name": "ADI-Template",
    "pages_count": 3,
    "document_confidence": 0.952,
    "processing_time": 2.134,
    "fields": [
      {"name": "tin", "value": "123-456-789-000", "confidence": 0.98},
      {"name": "tradeName", "value": "Acme Corp", "confidence": 0.95}
    ]
  }]
}
```

### BIR Document Fields
Target extraction fields (Philippines tax documents):
- `tin`: TIN format XXX-XXX-XXX-XXXXX or variations
- `tradeName`: Registered business name
- `registeredDate`: Format MM/DD/YYYY
- `registeredAddress`: Complete address string
- `businessType`: Industry classification/line of business
- `language`, `summary`: Context fields (Mistral only)

## Development Workflow

### Running the App
```bash
# Development (auto-reloads on file changes)
uv run streamlit run app.py

# Production
uv run streamlit run app.py --server.port 8080 --server.address 0.0.0.0
```

### Adding Dependencies
```bash
uv add package_name              # Production dependency
uv add --dev package_name        # Dev-only dependency
uv sync                          # Install all dependencies
```

### Environment Setup
1. Copy `.env.example` to `.env`
2. Required variables for DocumentIntelligence and MistralDocumentAI
3. Environment vars loaded via `load_dotenv()` in `app.py`

### Adding New Services
1. Create handler in `handlers/` following the pattern:
   - Inherit naming from existing handlers (no base class)
   - Implement `__init__(service_name)` and `extract(uploaded_file)`
   - Use `utils.save_extraction_to_json()` to persist results
   - Return structured dict matching existing services
2. Import in `pages/1_Document_Extraction.py`
3. Add checkbox in `tab1` section (col1 or col2)
4. Add to `selected_services` list with tuple `("Display-Name", HandlerClass)`

### File Organization
```
handlers/          # Service implementations (each is self-contained)
pages/             # Streamlit pages (1_Document_Extraction.py is main app)
inputs/            # Test documents (new/, old/, test/ subdirectories)
outputs/           # JSON results (extract_results.json, extract_results_old.json)
app.py             # Homepage with navigation
utils.py           # Shared utilities (sidebar, state, JSON saving)
style.css          # Theme-aware CSS (dark mode default)
```

## Critical Implementation Details

### Streamlit State Management
Use `utils.keep_state(state_object, state_name)` to persist data across page navigation:
- `valid_files`: Uploaded files list
- `selected_services`: Chosen extraction services
- Checkbox states: `svc_template`, `svc_neural`, `svc_mistral`, etc.

### CSS Theming
`style.css` uses CSS variables for theme support:
- Dark mode default with auto-detection via `prefers-color-scheme`
- Theme variables: `--text-primary`, `--background-card`, `--border-color`
- Special handling for sidebar gradient and button styles (not theme-aware)

### Mistral JSON Schema Pattern
When working with Mistral Document AI, use inline JSON schema in the request payload:
```python
"document_annotation_format": {
    "type": "json_schema",
    "json_schema": {
        "name": "bir_document_extraction",
        "schema": {"properties": {...}}
    }
}
```
Base64 encode documents with proper MIME type detection for PDF/images.

### Error Handling Philosophy
- Never display stack traces directly to users
- Return structured error dicts with `"error"` key
- Use `st.warning()` for recoverable issues, `st.error()` for failures
- Processing continues for other files/services even if one fails

## Common Modifications

### Changing Target Fields
1. Update JSON schema in `MistralDocumentAI.extract()` (lines 83-120)
2. Modify table columns in analysis tab (lines 265-275 in `1_Document_Extraction.py`)
3. Ensure `save_extraction_to_json()` handles new field structure

### Adjusting Timeouts
- Mistral API: 120s for PDF, 60s for images (line 140 in `mistral_document_ai.py`)
- Document Intelligence: Uses Azure SDK poller (no explicit timeout)

### Output Formats
Results stored in `outputs/extract_results.json` by default. To use different file:
```python
save_extraction_to_json(..., results_file_path="outputs/custom_results.json")
```

## Testing Strategy
- Place test files in `inputs/test/new/` or `inputs/test/old/`
- Use "Analyze Output" tab to compare service performance
- Processing time trends graph shows performance across services
- Confidence scores available in both Values and Confidence views
