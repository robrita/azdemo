# Dependency Management

## Rules

1. **Always** use exact versions with `==` in `pyproject.toml` (e.g., `azure-cosmos==4.14.6`)
2. **Never** use `>=` or other version ranges — pin exact versions for reproducibility
3. **Always** check the latest library version before installation
4. Maintain alphabetical order within each section
5. Separate production deps from dev deps (use `[project.optional-dependencies] dev = [...]`)

## Version Checking

```bash
pip index versions <package-name>
uv pip search <package-name>
```

## Package Manager

This project uses `uv` for fast dependency resolution:

```bash
uv sync                      # Sync all dependencies
pip install -e ".[dev]"      # Install with dev dependencies
```

## Example

```toml
[project]
dependencies = [
    "aiohttp==3.13.3",
    "azure-cosmos==4.14.6",
    "fastapi==0.129.2",
    "pydantic==2.12.5",
    "pydantic-settings==2.13.1",
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
