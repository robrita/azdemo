# AI Agent Instructions for Document Extraction Dashboard

## 📊 Project Overview

**Document Extraction Dashboard** is a Streamlit-based multi-service document extraction platform that processes PDF and image documents through 4+ parallel Azure AI services. The application normalizes outputs to a unified JSON format for comparative analysis.

### Architecture Highlights

- **Multi-handler pattern** (`handlers/`): Each service implements `extract(uploaded_file) -> dict[str, Any]` (no BaseHandler base class; implementations are independent)
- **Async parallel processing** (`app.py`): `extract_with_service_async()` + `asyncio.gather()` runs extraction concurrently in thread pool
- **Session persistence** (`utils.py`): `keep_state()` maintains uploaded files and service selections across Streamlit page navigation
- **Unified output** (`utils.py`): `save_extraction_to_json()` appends normalized results (deduplicates file_name + service_name) to `outputs/extract_results.json`
- **No base handler**: Handlers are concrete implementations; reference `document_intelligence.py` as the canonical pattern

## ⚡ Critical Developer Workflows

### Setup & Dependencies (uv + pyproject.toml)
```bash
make install          # Install all deps (recommended first step)
uv add package_name   # Add new dependency
uv sync --frozen      # Reproducible lockfile install
uv run pytest         # Run tests with project environment
```
**Why uv?** 10-100x faster than pip; deterministic resolution; PEP 518/621 compliant.

### Development Loop (Makefile)
```bash
make check-and-run    # 🔴 MAIN WORKFLOW: Lint→Pass?→Start app (blocks if lint fails)
make lint             # Check code (Ruff)
make format           # Auto-fix + format (idempotent)
make test-unit        # Run unit tests (mocked, no Azure calls)
```

### Testing Strategy
- **Unit tests**: `make test-unit` — fast, isolated, uses `@pytest.mark.unit`
- **Integration tests**: `uv run pytest -m integration` — requires `.env` credentials
- **Coverage**: `make test-cov` → HTML report in `htmlcov/index.html`
- **Fixtures** (`tests/conftest.py`): `sample_image_file`, `mock_pdf_file`, `mock_invalid_file`, `mock_empty_file`

## 🎯 Code Patterns & Conventions

### Handler Contract (Concrete Pattern)
All handlers in `handlers/` follow this structure:

```python
class ServiceName:
    def __init__(self, service_name: str = None):
        self.service_name = service_name
        self.endpoint = os.environ.get("AZURE_SERVICE_ENDPOINT")
        self.key = os.environ.get("AZURE_SERVICE_KEY")
        # Lazy init client only if credentials available
        
    def extract(self, uploaded_file) -> dict[str, Any]:
        """Returns {'service': name, 'error'?: msg, ...extraction data}"""
        start_time = time.time()
        # Process file; catch exceptions as dicts with 'error' key
        processing_time = time.time() - start_time
        return {...}
```
See `handlers/document_intelligence.py` for canonical example.

### Session State Persistence (Streamlit)
```python
from utils import keep_state
keep_state(valid_files, "valid_files")      # Persist across page changes
keep_state(selected_services, "selected_services")
```

### JSON Normalization
```python
from utils import save_extraction_to_json
save_extraction_to_json(
    file_name="doc.pdf",
    service_name="GPT-4.1-Vision", 
    pages_count=1,
    fields={"field_name": {"content": "text", "confidence": 0.98}},
    processing_time=2.5
)  # Auto-deduplicates (file_name, service_name) pairs
```

### Code Quality (Ruff)
- **Line length**: 100 chars (enforced in `pyproject.toml`)
- **Quotes**: Double quotes only
- **Target**: Python 3.11+
- **Per-file ignores**: `__init__.py` ignores `F401`; `schemas/gpt_schema.py` ignores `N815` (camelCase matches JSON)
- **Pre-commit**: `make format` before every commit

## 🔧 Environment & Services

### .env Template
```env
# Azure Document Intelligence
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://...
AZURE_DOCUMENT_INTELLIGENCE_KEY=...
AZURE_DOCUMENT_INTELLIGENCE_TEMPLATE_MODEL=...
AZURE_DOCUMENT_INTELLIGENCE_NEURAL_MODEL=...

# Azure OpenAI (GPT-4.1 & GPT-5)
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT_GPT4-1=gpt-4.1
AZURE_OPENAI_DEPLOYMENT_GPT5=gpt-5

# Azure Mistral Document AI
AZURE_MISTRAL_DOCUMENT_AI_ENDPOINT=https://...
AZURE_MISTRAL_DOCUMENT_AI_KEY=...

# Azure Content Understanding
AZURE_CONTENT_UNDERSTANDING_ENDPOINT=https://...
AZURE_CONTENT_UNDERSTANDING_SUBSCRIPTION_KEY=...
AZURE_CONTENT_UNDERSTANDING_ANALYZER_ID=...
```
**All services are optional**—UI shows unavailable services if credentials missing.

## 📁 Key File Responsibilities

| File | Role |
|------|------|
| `app.py` | Entry point; orchestrates file upload, service selection, async extraction, result aggregation |
| `utils.py` | Shared helpers: `keep_state()`, `render_sidebar()`, `save_extraction_to_json()` |
| `handlers/{service}.py` | Concrete service implementations; each has `__init__()` + `extract()` |
| `schemas/gpt_schema.py`, `mistral_schema.py` | Pydantic models for response parsing (define expected JSON structure) |
| `pages/pg1_Schema_Builder.py`, `pg2_Pricing.py` | Additional Streamlit pages |
| `tests/conftest.py` | pytest fixtures; defines `sample_image_file`, `mock_pdf_file`, etc. |

## 🔄 Data Flow & Integration Points

1. **Upload** → `app.py` validates file type (pdf, png, jpg, jpeg only)
2. **Selection** → User picks services via checkboxes → stored in `st.session_state`
3. **Async Extraction** → `extract_with_service_async()` runs each service in thread pool concurrently
4. **Error Handling** → Each service catches exceptions and returns `{'error': str}` key instead of crashing
5. **Aggregation** → Results keyed by service name; merged into one response dict
6. **Persistence** → `save_extraction_to_json()` appends to `outputs/extract_results.json` (deduplicates)
7. **Analysis** → Analysis tab loads JSON, renders Pandas DataFrames + Plotly trends

## 🆕 Adding a New Service

1. Create `handlers/new_service.py` with class implementing `__init__(service_name)` + `extract(uploaded_file) -> dict[str, Any]`
2. Add env vars in `.env` template (README + code comments)
3. Import in `handlers/__init__.py` + `app.py`
4. Add checkbox in `app.py` UI for service selection
5. Create mock fixture in `tests/conftest.py` if needed
6. Add handler unit tests to `tests/test_handlers.py` (use `@pytest.mark.unit`)

## 🐛 Debugging Checklist

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Service returns `{'error': '...'}` | Missing/wrong `.env` credential | Verify endpoint format + key; check Azure resource isn't rate-limited |
| Session state lost on page nav | `keep_state()` not called early | Add `keep_state(var, "state_key")` at page entry (see `app.py`) |
| Test imports fail | `sys.path.append("..")` in handlers | Ensure handlers import from `utils` correctly; run from project root |
| Linting blocks `make check-and-run` | Code style violation | Run `make format` to auto-fix |

---

**Last updated**: October 2025 | **Coverage**: 100% | **Python**: 3.11+ | **Framework**: Streamlit 1.50.0 | **Package Manager**: uv
