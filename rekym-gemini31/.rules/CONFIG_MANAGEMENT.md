# Configuration & Environment Variable Management

Best practices for managing application configuration in the Re-KYM Compliance Platform.

## Source of Truth

All backend configuration is centralized in `backend/src/config.py` via a **single** `Settings(BaseSettings)` class from `pydantic-settings`. The rest of the application imports `get_settings()` — no module may call `os.getenv()` or `os.environ` directly.

## Principles

### 1. Centralize — Single Config Object

All env vars are declared as typed fields in `Settings`. This provides:
- Type coercion and defaults in one place
- IDE autocompletion on `settings.<field>`
- No scattered `os.getenv()` calls to hunt down

### 2. Fail Fast — Startup Validation

The `Settings` class includes a `model_validator` that blocks unsafe configurations before the app starts:
- `COSMOS_KEY` is required when `COSMOS_AUTH_MODE=key`
- `AUTH_MODE=disabled` is rejected in production
- `APP_DEBUG=true` is rejected in production

If a required variable is missing or an invalid combination is detected, the app crashes immediately with a clear error message — not minutes later in a request handler.

### 3. Type Everything — No Stringly-Typed Config

Use `Literal`, `int`, `bool`, `SecretStr`, and `list` types. Never leave a config value as a bare `str` when a stricter type exists. Pydantic handles parsing from env var strings automatically.

### 4. Protect Secrets — `SecretStr`

Any field that holds a credential or connection string **must** use `SecretStr`. This prevents the value from appearing in logs, `repr()`, or error tracebacks:
- `cosmos_key: SecretStr`
- `scheduler_static_key: SecretStr`
- `application_insights_connection_string: SecretStr`

### 5. Provide Defaults for Non-Secrets

Dev-friendly defaults keep the "clone and run" experience smooth. Only require explicit values for secrets and environment-specific URLs.

### 6. Document Every Variable in `.env.example`

Every env var has:
- A section header (`# ---- Section (Required/Optional) ---`)
- A comment above each var explaining purpose and format
- Sensible placeholder values (never real credentials)

### 7. Keep Parity Across Files

When a config key is added, changed, or removed, update **all** of:
- `.env.example` — annotated template
- `.env` (local) — local working copy
- `local.settings.example.json` — Azure Functions template
- `local.settings.json` — Azure Functions local working copy
- `docker-compose.yaml` — if the key affects container behavior
- `README.md` — configuration table in docs
- `backend/src/config.py` — `Settings` class field

### 8. Never Commit Secrets

`.env` and `local.settings.json` are in `.gitignore`. Only `.env.example` and `local.settings.example.json` are committed. Secrets in production come from Azure Key Vault or App Configuration — never from env files.

### 9. Remove Deprecated Settings Promptly

Deprecated env vars create confusion. When a setting is superseded:
1. Remove the field from `Settings`
2. Remove from all env files (`.env.example`, `local.settings.example.json`, etc.)
3. Remove from code that reads it
4. Update tests

### 10. Scope Prefixes

Variables use implicit grouping by section. Script-only vars (like `AZURE_RESOURCE_GROUP`, `COSMOS_ACCOUNT`) that are not read by the Python app belong in a clearly labeled section at the bottom of `.env.example`.

### 11. Frontend Config is Separate

Frontend env vars use the `VITE_` prefix and live in `frontend/.env.example`. They are completely separate from backend config and accessed via `import.meta.env.VITE_*`.

## Anti-Patterns

| Don't | Do instead |
|-------|-----------|
| `os.getenv("MY_VAR")` scattered in code | Add field to `Settings`, import `get_settings()` |
| Boolean from string: `os.getenv("X") == "true"` | `my_flag: bool = Field(default=False)` — Pydantic parses it |
| Mutating config at runtime | Load once at startup via `@lru_cache`; treat as immutable |
| Duplicate env vars (`AUTH_DISABLED` + `AUTH_MODE=disabled`) | One canonical field per concept |
| Leaving commented-out deprecated vars in `.env.example` | Delete them; document migration in PR |
| Secret in `str` field | Use `SecretStr` |
