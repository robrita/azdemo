
# Code Quality Standards (Ruff)

## Formatting Rules

- **Line length**: 100 chars (enforced in `pyproject.toml`)
- **Quotes**: Double quotes only
- **Target**: Python 3.11+
- **Pre-commit**: Run `make format` before every commit

## Per-File Ignores

- `__init__.py`: Ignores `F401` (unused imports are acceptable for package exports)
- `schemas/gpt_schema.py`: Ignores `N815` (camelCase allowed to match JSON field names)

## Development Commands

```bash
make lint       # Check code style (non-destructive)
make format     # Auto-fix + format (idempotent, safe to run repeatedly)
```

## Best Practices

1. Always run `make format` before committing
2. Fix lint errors before running the app (enforced by `make check-and-run`)
3. Keep code idiomatic to Python 3.11+ (use type hints, modern syntax)
4. Maintain consistency with existing codebase patterns

---

# Documentation notes

- Do not create a new markdown file for summary documentation on new features.
- Write the concise documentation by updating the README.md file instead.

---

# Streamlit Development Guidelines

## Chart Width Configuration

### General Streamlit Charts
For most Streamlit chart components, use `width="stretch"` instead of the deprecated `use_container_width=True`.

**Correct:**
```python
st.line_chart(data, width="stretch")
st.bar_chart(data, width="stretch")
```

**Incorrect (deprecated):**
```python
st.line_chart(data, use_container_width=True)
st.bar_chart(data, use_container_width=True)
```

### Plotly Charts (st.plotly_chart)
For `st.plotly_chart()` specifically, use the `config` parameter to specify Plotly configuration options instead of width parameters.

**Correct:**
```python
st.plotly_chart(fig, config={"responsive": True})
```

**Incorrect:**
```python
st.plotly_chart(fig, width="stretch")  # Deprecated
st.plotly_chart(fig, use_container_width=True)  # Deprecated
```

### Why This Matters
- `use_container_width=True` is deprecated across Streamlit components
- `width="stretch"` is the modern approach for general charts
- `st.plotly_chart()` uses Plotly's native configuration system via the `config` parameter
- Following these guidelines avoids deprecation warnings and ensures future compatibility
