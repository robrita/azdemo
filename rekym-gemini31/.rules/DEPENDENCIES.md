# Dependency Management

## Rules

1. **ALWAYS** use exact versions with `==` in `pyproject.toml` (e.g., `azure-cosmos==4.14.6`)
2. **NEVER** use `>=` or other version ranges — pin exact versions for reproducibility
3. **ALWAYS** check the latest library version with tools before installation — do not rely on past knowledge
4. Maintain alphabetical order within each section
5. Separate production deps from dev deps (use `[project.optional-dependencies] dev = [...]`)

## Version Checking Workflow

Before adding or updating any dependency:

```bash
# Use pip index to check latest version
pip index versions <package-name>

# Or use uv (faster alternative)
uv pip search <package-name>
```

## Package Manager

This project uses `uv` for fast dependency resolution:

```bash
# Sync all dependencies (creates/updates .venv)
uv sync

# Install with dev dependencies
pip install -e ".[dev]"
```

## Example

```toml
# pyproject.toml
[project]
dependencies = [
    "aiohttp==3.13.3",
    "azure-cosmos==4.14.6",
    "fastapi==0.129.2",
    "google-auth==2.48.0",
    "pydantic==2.12.5",
    "pydantic-settings==2.13.1",
    "python-multipart==0.0.22",
    "uvicorn[standard]==0.41.0",
]

[project.optional-dependencies]
dev = [
    "pytest==9.0.2",
    "pytest-asyncio==1.3.0",
    "pytest-cov==7.0.0",
    "httpx==0.28.1",
    "ruff==0.15.2",
    "mypy==1.19.1",
]
```
