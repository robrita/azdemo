# Configuration Management

## Source of truth

All backend configuration must be declared in `backend/src/config.py` using one `Settings(BaseSettings)` class.

## Rules

1. Never call `os.getenv()` directly in application code.
2. Use typed fields with `Literal`, `bool`, `int`, `list[str]`, and `SecretStr` where appropriate.
3. Fail fast on invalid production configuration.
4. Use root `.env` for local backend and Docker configuration.
5. Keep parity across:
   - `.env.example`
   - `.env`
   - `local.settings.example.json`
   - `local.settings.json` when used
   - `docker-compose.yaml`
   - `backend/src/config.py`
   - template docs
6. Keep frontend env vars separate in `frontend/.env.example` and `frontend/.env.local`.

## Required secret handling

- Use `SecretStr` for secrets.
- Do not log secret values.
- Do not commit real credentials.