# AI Agent Instructions for Document Extraction Dashboard

## Project Overview
Streamlit-based multi-service document extraction platform comparing Azure AI services (Document Intelligence, Content Understanding, OpenAI Vision, Mistral Document AI) for BIR tax document processing. Uses async parallel processing to benchmark multiple services simultaneously.

## Architecture Patterns

### Service Handler Pattern
All extraction services implement a unified interface in `handlers/`:
- `__init__(service_name)` - Initialize with service name for tracking
- `extract(uploaded_file) -> Dict[str, Any]` - Returns standardized extraction dict
- Must call `save_extraction_to_json()` from `utils.py` with fields dict
- Error responses must include `"error"` key in returned dict

**Key implementations:**
- `document_intelligence.py` - Uses `model_template` vs `model_neural` based on service_name
- `gpt_vision.py` - Converts PDFs to images via PyMuPDF, uses Pydantic `DocSchema` for structured output
- `mistral_document_ai.py` - Distinguishes `image_url` vs `document_url` based on MIME type
- `content_understanding.py` - Implements polling pattern for async Azure operations

### Async Parallel Processing (app.py)
```python
# Process multiple services in parallel for each file
async def process_file_with_services_async(file, selected_services):
    tasks = [extract_with_service_async(name, cls, file) for name, cls in selected_services]
    results = await asyncio.gather(*tasks, return_exceptions=True)
```
**Important:** Use `asyncio.run()` in Streamlit context, run blocking operations via `loop.run_in_executor()`.

### Results Persistence
`save_extraction_to_json()` in `utils.py`:
- Updates/appends to `outputs/extract_results.json`
- Filters by `file_name` + `service_name` for uniqueness
- Standardized fields: `name`, `value`, `confidence` (rounded to 3 decimals)
- Always include `processing_time` and `overall_confidence` parameters

## Environment Configuration

### Required `.env` Variables (see `.env.example`)
```bash
# Document Intelligence - Two models (template vs neural)
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=
AZURE_DOCUMENT_INTELLIGENCE_TEMPLATE_MODEL=
AZURE_DOCUMENT_INTELLIGENCE_NEURAL_MODEL=

# OpenAI - Two deployments (gpt-4.1 vs gpt-5)
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_DEPLOYMENT_GPT4-1=
AZURE_OPENAI_DEPLOYMENT_GPT5=

# Mistral - REST API with base64 encoding
AZURE_MISTRAL_DOCUMENT_AI_ENDPOINT=

# Content Understanding - Polling-based async
AZURE_CONTENT_UNDERSTANDING_ENDPOINT=
AZURE_CONTENT_UNDERSTANDING_ANALYZER_ID=
```

**Service selection logic:** Service name determines model variant (e.g., "ADI-Template" uses template model, "GPT-5-Vision" uses gpt-5 deployment).

## Dependency Management

Uses `uv` (modern Python package manager) + `pyproject.toml`:
```bash
uv sync                    # Install all dependencies
uv add package_name        # Add new dependency
uv run streamlit run app.py  # Run application
```

**Critical dependencies:**
- `streamlit==1.50.0` - Session state via `st.session_state`
- `azure-ai-documentintelligence>=1.0.2` - Uses `begin_analyze_document()` poller pattern
- `pymupdf>=1.26.5` - PDF to image conversion (fitz module)
- `pydantic>=2.10.6` - Structured extraction schemas for GPT Vision

## Streamlit Conventions

### Session State Management (`utils.py`)
```python
keep_state(value, "state_key")  # Persist across page navigations
```
Used for: `valid_files`, `selected_services`, checkbox states (`svc_template`, `svc_neural`, etc.)

### Page Structure
- `render_sidebar()` - MUST be called first on every page for navigation
- Tab pattern: "📤 Upload & Extract" | "🔍 Analyze Output"
- File validation: `is_valid_file_type()` checks `['pdf', 'png', 'jpg', 'jpeg']`
- Process button only shows when `valid_files AND selected_services`

### Custom CSS Loading
```python
with open('style.css') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
```
Loads Google Fonts (Gasoek One, Oswald) via `style.css`.

## Data Flow

1. **Upload** → Validate file types → Store in `st.session_state["valid_files"]`
2. **Service Selection** → Checkboxes create `[(service_name, ServiceClass)]` tuples
3. **Extraction** → `process_file_with_services_async()` runs services in parallel
4. **Save** → Each handler calls `save_extraction_to_json()` with standardized fields
5. **Analysis** → Tab 2 loads JSON, creates DataFrame sorted by `file_name` + `service_name`

**Output visualization:**
- Switchable "Values" vs "Confidence" view
- Processing time line chart using Plotly (`go.Scatter` with color palette)
- Table fields: `tin`, `taxpayerName`, `registeredDate`, `registeredAddress`, `tradeName`, `businessType`

## Common Tasks

### Adding a New Extraction Service
1. Create `handlers/new_service.py` implementing `extract(uploaded_file)`
2. Add to `handlers/__init__.py` imports and `__all__`
3. Add checkbox in `app.py` tab1 (follow pattern: `svc_newname = st.checkbox(...)`)
4. Append to `selected_services` list with tuple `("Display-Name", NewServiceClass)`
5. Extract fields, call `save_extraction_to_json()` with confidence scores

### Debugging Extraction Issues
- Check `outputs/extract_results.json` for saved results structure
- Errors must include `"error"` key to be caught by `failed_results` filter
- Use `st.spinner()` context for long operations (user feedback)
- `processing_time` calculated via `time.time() - start_time`

### Modifying BIR Document Schema
Update both:
1. Pydantic model `DocSchema` in `schemas/gpt_schema.py` (for OpenAI structured output)
2. JSON schema `properties` in `mistral_document_ai.py` (for Mistral Document AI)
3. Table columns in `app.py` tab2 DataFrame (`row = {...}` initialization)

## Development Workflow

```bash
# Setup
git clone https://github.com/robrita/azdemo.git
cd azdemo
uv sync

# Configure environment
cp .env.example .env
# Edit .env with Azure credentials

# Run locally
uv run streamlit run app.py

# Outputs stored in
outputs/extract_results.json  # All extraction results
inputs/test/new/             # Test documents
```

**Troubleshooting:**
- Missing credentials → Handlers return `{"error": "...not configured..."}` dict
- PDF conversion fails → Check PyMuPDF/fitz installation (`uv sync`)
- Async errors → Ensure `run_in_executor()` for blocking SDK calls
- Session state loss → Verify `keep_state()` calls for stateful data
