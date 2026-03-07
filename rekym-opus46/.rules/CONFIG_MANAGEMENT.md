# Configuration & Environment Variable Management

## Source of Truth

All backend configuration is centralized in `backend/src/config.py` via a **single** `Settings(BaseSettings)` class. The rest of the application imports `get_settings()` — no module may call `os.getenv()` directly.

## Principles

### 1. Centralize — Single Config Object

All env vars are declared as typed fields in `Settings`. This provides:
- Type coercion and defaults in one place
- IDE autocompletion on `settings.<field>`
- No scattered `os.getenv()` calls

### 2. Fail Fast — Startup Validation

The `Settings` class includes a `model_validator` that blocks unsafe configurations:
- `COSMOS_KEY` is required when `COSMOS_AUTH_MODE=key`
- `AUTH_MODE=disabled` is rejected in production
- `APP_DEBUG=true` is rejected in production

### 3. Type Everything

Use `Literal`, `int`, `bool`, `SecretStr`, and `list` types. Never leave a config value as a bare `str` when a stricter type exists.

### 4. Protect Secrets — `SecretStr`

Any field holding credentials must use `SecretStr`:
- `cosmos_key: SecretStr`

### 5. Provide Defaults for Non-Secrets

Dev-friendly defaults keep the "clone and run" experience smooth.

### 6. Document Every Variable in `.env.example`

Every env var has a section header, a comment, and a placeholder value.

### 7. Keep Parity Across Files

When a config key changes, update **all** of:
- `.env.example`
- `.env` (local)
- `local.settings.example.json`
- `local.settings.json` (local)
- `docker-compose.yaml` (if relevant)
- `backend/src/config.py` — `Settings` class

### 8. Never Commit Secrets

`.env` and `local.settings.json` are in `.gitignore`. Secrets in production come from Azure Key Vault.

### 9. Frontend Config is Separate

Frontend env vars use the `VITE_` prefix and live in `frontend/.env.example`. Accessed via `import.meta.env.VITE_*`.

## Anti-Patterns

| Don't | Do Instead |
|-------|-----------|
| `os.getenv("MY_VAR")` | Add field to `Settings`, import `get_settings()` |
| Boolean from string: `os.getenv("X") == "true"` | `my_flag: bool = Field(default=False)` |
| Mutating config at runtime | Load once via `@lru_cache`; treat as immutable |
| Secret in `str` field | Use `SecretStr` |
