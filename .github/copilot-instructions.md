# Document Extraction Dashboard - AI Agent Guide

## Architecture Overview

**Streamlit Multi-Page App**: Main entry point is `app.py` (Document Extraction page) with additional pages in `pages/` directory (Schema Builder, Pricing). The app uses async parallel processing to extract document data via multiple Azure AI services simultaneously.

**Handler Pattern**: All extraction services (`handlers/*.py`) implement a **concrete pattern** (no base class). Each handler must:
- Provide `__init__(service_name: str = None)` with lazy Azure client initialization
- Implement `extract(uploaded_file) -> dict[str, Any]` that returns `{'service': name, 'error'?: msg, ...}` on failure
- Track `processing_time` using `time.time()` for performance metrics
- Reference: `handlers/document_intelligence.py` is the canonical implementation

**Async Parallel Execution**: `app.py` uses `asyncio.run(process_file_with_services_async())` to process files with all selected services concurrently via `concurrent.futures.ThreadPoolExecutor`, dramatically reducing total extraction time.

**Pydantic Schemas**: Vision-based services (GPT, Mistral) use Pydantic models in `schemas/` to enforce structured JSON extraction. These schemas allow camelCase field names (`schemas/gpt_schema.py` ignores `N815` lint rule to match JSON output format).

## Development Workflow

**Package Manager**: Use `uv` (modern, fast alternative to pip) - NOT pip directly:
- `uv sync` - Install/sync dependencies from `pyproject.toml`
- `uv run streamlit run app.py` - Run the app
- `uv add package_name` - Add new dependency
- `uv run ruff check --fix . && uv run ruff format .` - Lint + format

**Makefile Commands** (requires `make` on Windows via chocolatey or WSL):
- `make check-and-run` - **Primary workflow**: Lint, then start app (stops if linting fails)
- `make test-unit` - Run fast unit tests only (no Azure API calls)
- `make test-cov` - Generate HTML coverage report in `htmlcov/`
- `make format` - Auto-fix + format (idempotent, run before every commit)

**Code Quality**: Ruff enforces 100-char lines, Python 3.11+ syntax, double quotes. Always run `make format` before committing. Test coverage target is 100%.

## Testing Strategy

**Test Markers** (defined in `pytest.ini`):
- `@pytest.mark.unit` - Fast, mocked tests (use fixtures from `conftest.py`)
- `@pytest.mark.integration` - Real Azure API calls (requires `.env` credentials)
- `@pytest.mark.slow` - Long-running tests

**Running Tests**:
- `make test-unit` - Default for development (fast, no external deps)
- `uv run pytest -m integration` - Integration tests (needs valid `.env`)
- `uv run pytest -k "test_name"` - Run specific test

**Fixtures** (`tests/conftest.py`): Use provided fixtures like `mock_pdf_file`, `sample_image_file`, `mock_env_vars` (unit), `real_env_vars` (integration) instead of creating test data inline.

## Adding New Services

Follow this exact sequence (see `.github/instructions/adding-services.instructions.md`):
1. Create `handlers/new_service.py` with `__init__` + `extract()` methods
2. Add env vars to README `.env` section with comments
3. Import in `handlers/__init__.py` and `app.py`
4. Add UI checkbox in `app.py` main tab
5. Write unit tests in `tests/test_handlers.py` with `@pytest.mark.unit` marker
6. Run `make test-unit` and `make format`

## Key Patterns

**Session State Persistence** (Streamlit multi-page):
```python
from utils import keep_state
keep_state(valid_files, "valid_files")  # Survives page navigation
```

**Saving Extraction Results**:
```python
from utils import save_extraction_to_json
save_extraction_to_json(file_name, service_name, pages_count, fields, 
                       overall_confidence=0.95, processing_time=2.5)
# Auto-deduplicates by (file_name, service_name) pairs
```

**Error Handling in Handlers**: Always catch exceptions and return dict with `'error'` key instead of raising - this allows the app to show partial results from other services.

## Environment Variables

All Azure credentials loaded from `.env` (use `.env.example` template from README). Services with missing credentials are marked unavailable in UI but don't crash the app due to lazy client initialization.

## Critical Files

- `app.py` - Main entry point, async extraction orchestration
- `handlers/document_intelligence.py` - Reference handler implementation
- `utils.py` - `keep_state()`, `save_extraction_to_json()` utilities
- `tests/conftest.py` - All test fixtures and mock data
- `pyproject.toml` - Dependencies, Ruff config, coverage settings
- `.github/instructions/*.instructions.md` - Detailed patterns (handler contract, testing, adding services)

## Common Pitfalls

- **Don't use `pip`** - always use `uv` for consistency with lock file
- **Don't call handlers synchronously** - use the async executor pattern from `app.py`
- **Don't hardcode Azure credentials** - use env vars with lazy initialization
- **Don't skip `make format`** - Ruff formatting is enforced, not negotiable
- **Don't create base classes for handlers** - use concrete pattern (independent implementations)
- **Don't use camelCase in Python** except Pydantic schema fields matching JSON output (explicitly allowed in config)
