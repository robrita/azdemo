# GPT-5 / Reasoning Model Integration Specification

> Portable reference for integrating Azure OpenAI reasoning models (gpt-5\*, o1, o3, o4-mini) alongside standard models (gpt-4o) in a FastAPI + Python application. Covers the API behavior differences, configuration, model-adaptive kwargs, debug logging, and porting checklist.

---

## Table of Contents

1. [Overview](#overview)
2. [Problem Statement](#problem-statement)
3. [Reasoning Model API Differences](#reasoning-model-api-differences)
4. [Dependencies](#dependencies)
5. [Configuration](#configuration)
   - [Settings Class](#settings-class)
   - [Environment Variables](#environment-variables)
   - [Config Parity Files](#config-parity-files)
6. [Service Implementation](#service-implementation)
   - [Model Detection](#model-detection)
   - [Adaptive Kwargs Pattern](#adaptive-kwargs-pattern)
   - [Client Initialization](#client-initialization)
   - [API Call Pattern](#api-call-pattern)
7. [Debug Logging](#debug-logging)
8. [Common Pitfalls](#common-pitfalls)
9. [Environment Variable Reference](#environment-variable-reference)
10. [Key Source Files](#key-source-files)
11. [Porting Checklist](#porting-checklist)

---

## Overview

Azure OpenAI reasoning models (gpt-5\*, o1, o3, o4-mini) use a fundamentally different completion strategy than standard models (gpt-4o, gpt-4-turbo). They allocate a portion of `max_completion_tokens` to internal "thinking" before producing visible output, and they reject parameters that standard models accept (e.g., `temperature`). This spec documents a **model-adaptive pattern** that lets a single service class work seamlessly with both model families, controlled entirely by configuration.

| Standard Models | Reasoning Models |
|-----------------|-----------------|
| `temperature` accepted (0–2) | `temperature` **rejected** (only default 1) |
| No reasoning tokens | Thinking tokens consume part of `max_completion_tokens` |
| No `reasoning_effort` param | `reasoning_effort` controls think budget (`low`, `medium`, `high`) |
| Output starts immediately | Output deferred until reasoning completes |
| `finish_reason=stop` on success | `finish_reason=length` if thinking exhausts token budget |

---

## Problem Statement

When switching from `gpt-4o` to `gpt-5.1` (or any o-series model), three issues surface:

### 1. Empty output — `finish_reason=length` with `content_length=0`

Reasoning models use `max_completion_tokens` for **both** internal thinking and visible output. A hard cap of 4096 tokens may be entirely consumed by reasoning, leaving zero tokens for the JSON response. The API returns HTTP 200 with an empty message.

**Symptom:** Score shows 0/100, summary is empty, no pillar scores.

### 2. `temperature` rejected

Reasoning models only accept the default temperature (1). Passing any other value causes:

```
openai.BadRequestError: 400 - "Unsupported value: 'temperature' does not support
0.3 with this model. Only the default (1) value is supported."
```

### 3. `reasoning` vs `reasoning_effort` parameter name

The OpenAI Python SDK (v1.x / v2.x) uses `reasoning_effort` as a **flat top-level parameter**, not a nested `reasoning.effort` dict. Using the wrong shape causes:

```
TypeError: AsyncCompletions.create() got an unexpected keyword argument 'reasoning'
```

---

## Reasoning Model API Differences

| Parameter | Standard Models | Reasoning Models | Notes |
|-----------|----------------|-----------------|-------|
| `temperature` | 0–2 (default 1) | **Only 1** (any other value → 400 error) | Must be omitted for reasoning models |
| `max_completion_tokens` | Caps output tokens only | Caps thinking + output combined | Omit to let model use full budget, or set high (16k+) |
| `reasoning_effort` | Not supported (ignored) | `low` / `medium` / `high` | Controls how much thinking the model does |
| `top_p` | Supported | **Not supported** | Must be omitted |
| `presence_penalty` | Supported | **Not supported** | Must be omitted |
| `frequency_penalty` | Supported | **Not supported** | Must be omitted |
| `logprobs` | Supported | **Not supported** | Must be omitted |
| `response_format` | Supported | Supported | JSON mode works on both |
| `system` role in messages | Supported | Supported (gpt-5); some o-series use `developer` role | Check model docs |

---

## Dependencies

```toml
# pyproject.toml
dependencies = [
    "azure-identity==1.25.1",
    "openai==1.82.0",          # or >=1.60.0 for reasoning_effort support
    "pydantic-settings==2.13.1",
]
```

> **SDK version matters.** The `reasoning_effort` parameter was added in `openai>=1.60.0`. Earlier versions will raise `TypeError`.

---

## Configuration

### Settings Class

```python
# src/config.py
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Azure OpenAI
    azure_openai_endpoint: str = Field(
        default="",
        description="Azure OpenAI endpoint URL",
    )
    azure_openai_deployment: str = Field(
        default="gpt-4o",
        description="Azure OpenAI model deployment name",
    )
    azure_openai_api_version: str = Field(
        default="2024-12-01-preview",
        description="Azure OpenAI API version",
    )
    azure_openai_timeout: int = Field(
        default=120,
        description="Azure OpenAI request timeout in seconds",
    )
    azure_openai_reasoning_effort: str = Field(
        default="medium",
        description="Reasoning effort for gpt-5/o-series models (low, medium, high)",
    )
```

### Environment Variables

```bash
# .env / .env.example
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-5.1          # or gpt-4o for standard
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_TIMEOUT=120
AZURE_OPENAI_REASONING_EFFORT=medium     # low | medium | high
```

### Config Parity Files

Every config key must appear in all of these (adapt to your project):

| File | Format |
|------|--------|
| `.env.example` | `KEY=default_value` |
| `.env` | `KEY=actual_value` |
| `local.settings.example.json` | `"KEY": "default_value"` |
| `local.settings.json` | `"KEY": "actual_value"` |
| `docker-compose.yaml` | `KEY=${KEY:-default_value}` |

Example docker-compose entry:

```yaml
environment:
  - AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT:-}
  - AZURE_OPENAI_DEPLOYMENT=${AZURE_OPENAI_DEPLOYMENT:-gpt-4o}
  - AZURE_OPENAI_API_VERSION=${AZURE_OPENAI_API_VERSION:-2024-12-01-preview}
  - AZURE_OPENAI_TIMEOUT=${AZURE_OPENAI_TIMEOUT:-120}
  - AZURE_OPENAI_REASONING_EFFORT=${AZURE_OPENAI_REASONING_EFFORT:-medium}
```

---

## Service Implementation

### Model Detection

Detect reasoning models by deployment name prefix. This covers all known families:

```python
def _is_reasoning_model(self) -> bool:
    """Check if the deployment is a reasoning model (gpt-5*, o-series)."""
    name = self._settings.azure_openai_deployment.lower()
    return name.startswith(("gpt-5", "o1", "o3", "o4"))
```

> **Why deployment name?** Azure OpenAI uses deployment names that mirror model names. If your deployment names differ from model names, adjust the prefix list or add a separate `AZURE_OPENAI_MODEL_FAMILY` config.

### Adaptive Kwargs Pattern

A single method returns the correct kwargs based on model type. This is the **core pattern** — it ensures incompatible parameters are never sent:

```python
from typing import Any

def _model_kwargs(self, temperature: float = 0.3) -> dict[str, Any]:
    """Return model-specific kwargs (reasoning models don't support temperature)."""
    if self._is_reasoning_model():
        return {"reasoning_effort": self._settings.azure_openai_reasoning_effort}
    return {"temperature": temperature}
```

**Key design decisions:**

1. **No `max_completion_tokens`** — omitting it lets the model use its full default budget. Reasoning models with a hard cap risk exhausting all tokens on thinking.
2. **`temperature` omitted for reasoning models** — they reject any value other than the default (1).
3. **`reasoning_effort` only for reasoning models** — standard models ignore it but sending it is unnecessary.

### Client Initialization

Uses Entra ID (DefaultAzureCredential) for token-based auth:

```python
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncAzureOpenAI

def _get_client(self) -> AsyncAzureOpenAI:
    if self._client is None:
        credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )
        self._client = AsyncAzureOpenAI(
            azure_endpoint=self._settings.azure_openai_endpoint,
            azure_ad_token_provider=token_provider,
            api_version=self._settings.azure_openai_api_version,
            timeout=self._settings.azure_openai_timeout,
        )
    return self._client
```

### API Call Pattern

Spread the adaptive kwargs into the `create()` call:

```python
response = await client.chat.completions.create(
    model=self._settings.azure_openai_deployment,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ],
    response_format={"type": "json_object"},
    **self._model_kwargs(temperature=0),      # <- adaptive
)
```

For calls where you want a different temperature for standard models:

```python
response = await client.chat.completions.create(
    model=self._settings.azure_openai_deployment,
    messages=cast(list[ChatCompletionMessageParam], messages),
    response_format={"type": "json_object"},
    **self._model_kwargs(temperature=0.3),    # <- creative calls
)
```

---

## Debug Logging

Add logging around the API call to diagnose empty-output issues:

```python
import logging
logger = logging.getLogger(__name__)

# Before the call
logger.info(
    "evaluate: %d questions, %d answers, pillars=%s",
    len(questions), len(answers), selected_pillars,
)

# After the call
choice = response.choices[0]
logger.info(
    "evaluate: finish_reason=%s, content_length=%s, refusal=%s",
    choice.finish_reason,
    len(choice.message.content) if choice.message.content else 0,
    getattr(choice.message, "refusal", None),
)

raw = choice.message.content or "{}"
logger.debug("evaluate: raw response=%.2000s", raw)

data = json.loads(raw)
logger.info(
    "evaluate: parsed keys=%s, overall_score=%s, pillar_scores count=%d",
    list(data.keys()),
    data.get("overall_score"),
    len(data.get("pillar_scores", [])),
)
```

### Diagnostic Log Interpretation

| Log Pattern | Diagnosis | Fix |
|-------------|-----------|-----|
| `finish_reason=length, content_length=0` | Thinking consumed all tokens | Remove `max_completion_tokens` or increase to 16k+ |
| `finish_reason=length, content_length>0` | Output truncated mid-JSON | Increase `max_completion_tokens`; simplify prompt |
| `finish_reason=stop, content_length=2` (`{}`) | Model returned empty JSON | Prompt issue; check system/user message clarity |
| `refusal=<message>` | Content policy refusal | Review prompt for policy triggers |
| `finish_reason=stop, parsed keys=[]` | Valid but empty response | Check JSON parsing; model may need stronger instructions |
| `finish_reason=stop, parsed keys=[...]` with data | Success | No action needed |

---

## Common Pitfalls

### 1. Hardcoded `max_completion_tokens=4096`

**Don't do this with reasoning models.** The model will burn all 4096 tokens on thinking and return empty output. Either omit the parameter entirely (let the model use its full budget) or set it to 16384+.

### 2. Sending `temperature` to reasoning models

```python
# BAD — will fail with gpt-5*
response = await client.chat.completions.create(
    model="gpt-5.1",
    temperature=0.3,       # 400 error
    ...
)

# GOOD — use adaptive kwargs
response = await client.chat.completions.create(
    model="gpt-5.1",
    **self._model_kwargs(temperature=0.3),  # reasoning_effort sent instead
    ...
)
```

### 3. Wrong `reasoning_effort` parameter shape

```python
# BAD — nested dict (matches docs but not SDK)
{"reasoning": {"effort": "medium"}}
# TypeError: got an unexpected keyword argument 'reasoning'

# GOOD — flat top-level param (openai SDK >=1.60.0)
{"reasoning_effort": "medium"}
```

### 4. Forgetting `top_p`, `presence_penalty`, `frequency_penalty`

These are also rejected by reasoning models. If your existing code sets them, add them to the adaptive kwargs exclusion.

### 5. `system` vs `developer` role

Some o-series models (o1, o1-mini) required `developer` instead of `system` for the system message role. The gpt-5 family supports `system` normally. Check Azure OpenAI docs for your specific model.

---

## Environment Variable Reference

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | — | Yes | Azure OpenAI resource endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` | Yes | Deployment name (determines model family) |
| `AZURE_OPENAI_API_VERSION` | `2024-12-01-preview` | No | Azure OpenAI API version |
| `AZURE_OPENAI_TIMEOUT` | `120` | No | Request timeout in seconds |
| `AZURE_OPENAI_REASONING_EFFORT` | `medium` | No | Reasoning effort: `low`, `medium`, `high` (only affects reasoning models) |

---

## Key Source Files

| File | Purpose |
|------|---------|
| `backend/src/config.py` | `Settings` model with all Azure OpenAI config fields |
| `backend/src/services/openai_service.py` | `OpenAIService` with `_is_reasoning_model()`, `_model_kwargs()`, API calls |
| `.env.example` | Template environment variables |
| `docker-compose.yaml` | Container environment passthrough |
| `local.settings.example.json` | Azure Functions local settings template |
| `backend/tests/unit/test_evaluate.py` | Unit tests for the evaluate flow with mocked OpenAI responses |

---

## Porting Checklist

When replicating this pattern in another project:

- [ ] **Install SDK** — `openai>=1.60.0` for `reasoning_effort` support
- [ ] **Add config fields** — `azure_openai_reasoning_effort` in your Settings class
- [ ] **Add env vars** — `AZURE_OPENAI_REASONING_EFFORT` in all config parity files
- [ ] **Implement `_is_reasoning_model()`** — check deployment name prefixes
- [ ] **Implement `_model_kwargs()`** — return `reasoning_effort` OR `temperature`, never both
- [ ] **Remove `max_completion_tokens`** from API calls (or make configurable with high default)
- [ ] **Remove `temperature`, `top_p`, `presence_penalty`, `frequency_penalty`** from direct API call kwargs — route them through `_model_kwargs()`
- [ ] **Add debug logging** — log `finish_reason`, `content_length`, `refusal` after every API call
- [ ] **Handle empty responses** — when `finish_reason=length` and content is empty, log a clear warning
- [ ] **Test both paths** — unit tests with mocked responses for valid JSON, empty JSON, truncated JSON, and None content
- [ ] **Verify `system` role** — some o-series models require `developer` role instead
- [ ] **Update timeout** — reasoning models think longer; ensure `AZURE_OPENAI_TIMEOUT` is adequate (120s+)
