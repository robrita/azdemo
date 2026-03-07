# Completion Checklist

Before calling the template update complete, verify all of the following:

- Docs and starter assets are both updated.
- Root local development works from the repository root.
- Azure Functions hosting is still wired through `function_app.py`.
- Container hosting still runs the same FastAPI app.
- Cosmos DB remains the default primary store.
- Config parity is preserved.
- Health probes remain explicit.
- Frontend light and dark mode both remain usable.
- Quality gate commands still reflect the project layout.