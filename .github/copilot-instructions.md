# AI Agent Instructions for Document Extraction Dashboard

## Project Overview

**Document Extraction Dashboard** is a Streamlit-based multi-service document extraction platform that compares results from 6 different Azure AI services in parallel. The application extracts structured data from PDF and image documents using a unified handler pattern.

### Key Architecture Decisions

- **Multi-handler pattern**: Each extraction service (DocumentIntelligence, GPT Vision, Mistral, Content Understanding) is a separate handler class implementing `extract(uploaded_file)` returning `dict[str, Any]`
- **Async parallel processing**: Services run in parallel using `asyncio.gather()` to maximize throughput (see `process_file_with_services_async()`)
- **Session persistence**: Use `st.session_state` and `keep_state()` helper to maintain uploaded files and service selections across page navigation
- **Structured output**: All extractions normalize to JSON format in `outputs/extract_results.json` with standardized schema

## Critical Developer Workflows

### Package Management (uv + pyproject.toml)
```bash
make install          # Install dependencies (recommended workflow)
uv sync              # Manual install
uv add package_name  # Add new dependency
uv run pytest        # Run tests with project environment
```
**Why uv?** 10-100x faster than pip; reproducible lock files; follows PEP 518/621 standards.

### Local Development Loop
```bash
make check-and-run   # Lint + start app (GATE: stops if linting fails)
make lint            # Ruff linting only
make format          # Auto-fix + format
```

### Testing Strategy
- **Unit tests** (fast, no Azure calls): `make test-unit` - uses mocked handlers and `mock_env_vars` fixture
- **Integration tests** (requires `.env` with real credentials): `uv run pytest -m integration`
- **Coverage reports**: `make test-cov` generates HTML in `htmlcov/index.html`
- **Test markers**: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`

## Code Patterns & Conventions

### Handler Implementation Pattern
All service handlers follow this contract:

```python
from handlers.base import BaseHandler  # (or use as reference pattern)

class NewServiceHandler:
    def __init__(self, service_name: str = None):
        self.service_name = service_name
        self.endpoint = os.getenv("AZURE_SERVICE_ENDPOINT")
        self.key = os.getenv("AZURE_SERVICE_KEY")
        # Initialize client if credentials available
        
    def extract(self, uploaded_file) -> dict[str, Any]:
        """Extract returns dict with service, file_info, model_info, documents keys"""
        start_time = time.time()
        # Process file
        processing_time = time.time() - start_time
        return {"service": self.service_name, ...}
```

### Session State Management
Use `keep_state()` to persist data across Streamlit page navigations:
```python
keep_state(valid_files, "valid_files")      # Persist uploaded files
keep_state(selected_services, "selected_services")  # Persist service selections
```

### JSON Result Normalization
Use `save_extraction_to_json()` helper to append results (deduplicates by file_name + service_name):
```python
save_extraction_to_json(
    file_name="doc.pdf",
    service_name="GPT-4.1-Vision", 
    pages_count=1,
    fields={"field_name": {"content": "field_value", "confidence": 0.98}},
    processing_time=2.5
)
```

### Ruff Linting Rules
- **Line length**: 100 characters (enforced)
- **Target**: Python 3.11+
- **Format**: Double quotes for strings; per-file ignores in `pyproject.toml`
- **Pre-commit**: Always run `make format` before commits

## Environment Configuration

### Required for Development
Create `.env` file in project root (template in README). All Azure services are **optional**—unconfigured services show as unavailable in UI.

### Service Credentials (in `.env`)
```env
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://...
AZURE_DOCUMENT_INTELLIGENCE_TEMPLATE_MODEL=your-model-id
AZURE_OPENAI_DEPLOYMENT_GPT4-1=gpt-4-deployment-name
AZURE_MISTRAL_DOCUMENT_AI_ENDPOINT=https://...
AZURE_CONTENT_UNDERSTANDING_ANALYZER_ID=your-analyzer-id
```

### Test Fixtures for Mock Services
- `mock_env_vars`: Mocked credentials for unit tests (no API calls)
- `real_env_vars`: Loads `.env` for integration tests
- `mock_missing_env_vars`: Tests graceful degradation when services unavailable
- `sample_image_file` and `mock_pdf_file`: Sample documents for testing extraction handlers

## File Organization & Key Responsibilities

| Directory | Purpose |
|-----------|---------|
| `app.py` | Main Streamlit app entry point; renders file upload UI, service selection, extraction orchestration |
| `handlers/` | Service handlers: `document_intelligence.py`, `gpt_vision.py`, `mistral_document_ai.py`, `content_understanding.py` |
| `schemas/` | Pydantic models for structuring AI responses (`gpt_schema.py`, `mistral_schema.py`) |
| `pages/` | Additional Streamlit pages (e.g., `1_Pricing.py`) |
| `tests/` | Comprehensive pytest suite; `conftest.py` provides shared fixtures |
| `outputs/` | JSON extraction results accumulate here |

## Common Debugging Scenarios

**Service returns error**: Check `.env` credentials; verify endpoint format; confirm Azure resource exists and isn't rate-limited.

**Session state lost on page navigation**: Use `keep_state()` in page entry; see `app.py` for pattern.

**Test fails with missing test image**: Ensure sample images exist in `tests/data/`; tests skip gracefully if missing.

**Import path issues**: Handlers use `sys.path.append("..")` to access utils; Streamlit app requires `from handlers import ClassName`.

## Integration Points & Data Flow

1. **File Upload** → validated in `app.py` (allowed: pdf, png, jpg, jpeg)
2. **Service Selection** → checkbox selections stored in session state
3. **Async Extraction** → `process_file_with_services_async()` spawns handler tasks in parallel thread pool
4. **Result Aggregation** → each handler returns dict; results keyed by service name
5. **JSON Persistence** → `save_extraction_to_json()` appends to `outputs/extract_results.json`
6. **Analysis Tab** → loads JSON, renders dataframes and processing time trends via Plotly

## When Adding New Services

1. Create `handlers/new_service.py` following handler contract (init + extract method)
2. Add environment variable configuration in `.env` template
3. Update `conftest.py` with mock fixture if needed
4. Add handler import to `handlers/__init__.py`
5. Add UI checkbox in `app.py` for service selection
6. Add tests in `tests/test_handlers.py` for handler initialization and error cases

---

**Last updated**: October 2024 | **Coverage**: 100% | **Python**: 3.11+ | **Framework**: Streamlit 1.50.0
