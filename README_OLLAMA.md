# Ollama-Compatible API

Aurora exposes an **Ollama-compatible REST API** so that Ollama-aware
clients — [Open WebUI](https://openwebui.com/), [Continue](https://continue.dev/),
and others — can connect directly to Aurora's RAG knowledge base without
any adapter code.

The compat layer is mounted at `/api` (not `/api/v1`) so that Ollama
client libraries resolve endpoints correctly out of the box.

---

## Quick Start

### 1. Start Aurora

```bash
cd packages/aurora-app
uv run uvicorn aurora_app.main:app --host 0.0.0.0 --port 8888
```

### 2. Configure Open WebUI

1. Open **Open WebUI** → **Admin Settings** → **Connections**.
2. Add a new Ollama connection:
   - **URL**: `http://localhost:8888`
   - Click the refresh icon — you should see the `aurora:latest` model.
3. Select the `aurora` model and start chatting.

### 3. Verify

```bash
# Check that the API is alive
curl http://localhost:8888/api/version
# → {"version":"0.9.3"}

# List available models
curl http://localhost:8888/api/tags
# → {"models":[{"name":"aurora:latest", ...}]}

# Send a chat message
curl -X POST http://localhost:8888/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "aurora",
    "messages": [{"role": "user", "content": "What is Aurora?"}],
    "stream": false
  }'
```

---

## Configuration

### TOML (`configs/aurora.toml`)

```toml
[ollama_compat]
enabled = true               # Global toggle
default_model = "aurora"     # Model name reported to clients
default_tag = "latest"       # Tag suffix (name:tag)
default_kb = "default"       # Fallback knowledge base

# Map Ollama model names → Aurora knowledge base names
[ollama_compat.model_mapping]
"aurora" = "default"
"aurora-code" = "code_kb"
"aurora-docs" = "docs_kb"
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_EMULATING_MODEL_NAME` | `aurora` | Override the model name |
| `OLLAMA_EMULATING_MODEL_TAG` | `latest` | Override the model tag |
| `OLLAMA_DEFAULT_KB` | `default` | Override the default KB |

Environment variables take precedence over TOML values.

---

## API Reference

All endpoints are mounted under `/api`.

### Model Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/version` | Returns simulated Ollama version |
| `GET` | `/api/tags` | Lists available models |
| `GET` | `/api/ps` | Lists running (loaded) models |
| `POST` | `/api/show` | Shows model details |

### Chat

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Chat with RAG routing |

```json
{
  "model": "aurora",
  "messages": [
    {"role": "system", "content": "You are helpful."},
    {"role": "user", "content": "What is Aurora?"}
  ],
  "stream": true,
  "options": {}
}
```

### Generate

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/generate` | Raw LLM generation (no RAG) |

```json
{
  "model": "aurora",
  "prompt": "Write a haiku about data.",
  "system": "You are a poet.",
  "stream": false
}
```

---

## Retrieval Modes

The `/api/chat` endpoint inspects the **last user message** for a mode
prefix that controls the RAG retrieval strategy:

| Prefix | Mode | Description |
|--------|------|-------------|
| `/local` | `local` | Entity-centric local retrieval |
| `/global` | `global` | Global graph traversal |
| `/hybrid` | `hybrid` | Combined local + global |
| `/naive` | `naive` | Simple vector search |
| `/mix` | `mix` | **(default)** All strategies combined |
| `/bypass` | `bypass` | Skip RAG, direct LLM |
| `/context` | `mix` | Alias for mix |
| `/localcontext` | `local` | Alias for local |

**Example**: `/global Summarize the architecture` triggers global graph
retrieval.

If no prefix is provided, the default mode is `mix`.

---

## Model → Knowledge Base Mapping

The `model_mapping` in configuration maps Ollama model names to Aurora
knowledge base names:

```
Ollama client selects "aurora-code"
    → config resolves to "code_kb"
    → RAG query runs against the "code_kb" knowledge base
```

Unmapped model names fall back to `default_kb`.

---

## Streaming

Both `/api/chat` and `/api/generate` support streaming via NDJSON
(Newline-Delimited JSON).  Each line is a self-contained JSON object:

```json
{"model":"aurora:latest","created_at":"...","message":{"role":"assistant","content":"Hello"},"done":false}
{"model":"aurora:latest","created_at":"...","message":{"role":"assistant","content":" world!"},"done":false}
{"model":"aurora:latest","created_at":"...","message":{"role":"assistant","content":""},"done":true,"total_duration":123456789,"prompt_eval_count":10,"eval_count":5}
```

The final line always has `"done": true`.

---

## Open WebUI Integration Notes

Open WebUI sometimes injects a `\n<chat_history>\nUSER:` marker into
the last message when forwarding multi-turn conversations.  The compat
layer detects this pattern and automatically switches to `bypass` mode
(direct LLM without RAG retrieval) to avoid polluting RAG context with
conversation history markup.

### Recommended Open WebUI Settings

- **System Prompt**: Set a system prompt in Open WebUI to guide the
  assistant's behavior.
- **Temperature**: Aurora respects the `options.temperature` field in
  chat requests.
- **Model Selection**: If you configured multiple model mappings, select
  the appropriate model in Open WebUI's model dropdown.

---

## Troubleshooting

### "No models found" in Open WebUI

1. Verify the Aurora server is running: `curl http://localhost:8888/api/tags`
2. Check the URL in Open WebUI settings — it should be the base URL
   (`http://localhost:8888`), **not** `http://localhost:8888/api`.
3. Ensure `[ollama_compat] enabled = true` in the config.

### Chat returns empty response

1. Verify a knowledge base exists and has ingested documents.
2. Check that an LLM and embedding model are configured (Models page).
3. Check server logs for `Ollama chat failed` errors.

### Streaming not working

1. Some reverse proxies (Nginx, Caddy) buffer responses by default.
   Add `X-Accel-Buffering: no` handling or disable buffering for `/api/`.
2. Verify `stream: true` is set in the request body.

### Model not found on `/api/show`

The model name must match a key in `[ollama_compat.model_mapping]` or
the `default_model` value.  Tag suffixes (e.g. `:latest`) are stripped
before matching.

---

## Architecture

```
aurora_serve/ollama_compat/
├── __init__.py      # Public exports
├── models.py        # Pydantic v2 request/response models (frozen)
├── config.py        # TOML + env-var configuration loader
├── mapper.py        # Mode parsing, KB mapping, message conversion
├── streaming.py     # NDJSON streaming helpers
└── routes.py        # FastAPI endpoints
```

The compat layer is a thin adapter over `KnowledgeV2Service`:
- **Chat** → `service.query(kb_name, query, mode, ...)`
- **Generate** → `service.llm_generate(prompt, system, ...)`
