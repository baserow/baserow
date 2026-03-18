# Baserow AI-Assistant: Quick DevOps Setup

This guide shows how to enable the AI-assistant in Baserow, configure the required
environment variables, and (optionally) turn on knowledge-base lookups via an embeddings
server.

## 1) Core concepts

- The assistant is built on [**pydantic-ai**](https://ai.pydantic.dev/) — a
  Python agent framework that supports multiple LLM providers out of the box.
- You **must** set `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` with the provider and model
  of your choosing.
- The assistant has been mostly tested with the `gpt-oss-120b` family. Other models can
  work as well.

## 2) Minimal enablement

Set the model you want, restart Baserow, and let migrations run.

**Important:** When running Baserow with Docker Compose or multiple services, `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` must be set in **all services** (both backend and frontend) for the assistant to work properly.

```dotenv
# Required
BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL=openai:gpt-5.2
OPENAI_API_KEY=your_api_key

# Optional - adjust LLM temperature (default: 0.3)
BASEROW_ENTERPRISE_ASSISTANT_LLM_TEMPERATURE=0.3
```

**About temperature:**
- Controls randomness in the main assistant's LLM responses.
- **Default: 0.3** (focused, consistent responses)
- Higher values (depending on the model) = more creative/varied responses.
- Lower values (e.g., 0-0.1) = more analytical responses. Note that even with temperature of 0.0, the results will not be fully deterministic.

## 3) Provider presets

Choose **one** provider block and set its variables. pydantic-ai uses the standard
environment variables for each provider (e.g. `OPENAI_API_KEY`, `GROQ_API_KEY`).

### OpenAI / OpenAI-compatible

```dotenv
BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL=openai:gpt-5.2
OPENAI_API_KEY=your_api_key
# Optional: point to an alternative OpenAI-compatible endpoint
OPENAI_BASE_URL=https://eu.api.openai.com/v1
# or
OPENAI_BASE_URL=https://<your-resource-name>.openai.azure.com
```

### Anthropic

```dotenv
BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL=anthropic:claude-sonnet-4-20250514
ANTHROPIC_API_KEY=your_api_key
```

### AWS Bedrock

pydantic-ai supports two authentication methods for Bedrock. Use whichever matches your setup.

**Option A — Standard AWS credentials (boto3)**

```dotenv
BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL=bedrock:openai.gpt-oss-120b-1:0
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=eu-central-1
```

Any boto3-compatible credential method works: env vars, IAM roles, instance profiles, `~/.aws/credentials`, etc.

**Option B — Bedrock bearer token**

```dotenv
BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL=bedrock:openai.gpt-oss-120b-1:0
AWS_BEARER_TOKEN_BEDROCK=your_bearer_token
AWS_DEFAULT_REGION=eu-central-1
```

### Groq

```dotenv
BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL=groq:openai/gpt-oss-120b
GROQ_API_KEY=your_api_key
```

### Ollama

```dotenv
BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL=ollama:gpt-oss:120b
# Point to your Ollama instance (defaults to http://localhost:11434/v1)
OLLAMA_BASE_URL=http://localhost:11434/v1
```

pydantic-ai auto-detects the provider from the model prefix and routes requests
accordingly.

## 4) Knowledge-base lookup

If your deployment method doesn't auto-provision embeddings, run the Baserow embeddings
service and point Baserow at it.

**For developers using Docker Compose:** See [embeddings-server.md](../development/embeddings-server.md) for setup instructions.

### Run the embeddings container

```bash
docker run -d --name baserow-embeddings -p 80:80 baserow/embeddings:latest
```

### Point Baserow to it

```dotenv
BASEROW_EMBEDDINGS_API_URL=http://your-embedder-service
# e.g., http://localhost if you mapped -p 80:80 locally
# Then restart Baserow and allow migrations to run.
```

After restart and migrations, knowledge-base lookup will be available.

## 5) Troubleshooting

### The assistant doesn't appear or doesn't work

If the assistant is not visible in the sidebar or doesn't work, verify that:

1. `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` is set correctly in **both** the backend and frontend services
2. The required API key for your chosen provider is set (e.g., `OPENAI_API_KEY`, `GROQ_API_KEY`, etc.)

### Verifying environment variables in development

To check if the variables are set correctly in development, from the host run:

```bash
# Check backend
just dcd run --rm backend bash -c env | grep LLM_MODEL
just dcd run --rm backend bash -c env | grep API_KEY

# Check frontend
just dcd run --rm web-frontend bash -c env | grep LLM_MODEL
```

Both commands must return the same value for `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL`. If either is missing or they differ, update your environment configuration and restart the services.

## 6) Supported models

OpenAI, Anthropic, AWS Bedrock, Groq, Gemini/Vertex AI and any OpenAI-compatible
endpoint (Azure, DeepSeek, Fireworks, LiteLLM, Perplexity, Together AI, etc.).

## 7) Framework change: UDSPy to pydantic-ai

The assistant previously used [UDSPy](https://github.com/baserow/udspy/) as its agent
framework. It now uses [pydantic-ai](https://ai.pydantic.dev/). Most environment
variables are unchanged or bridged for backward compatibility.

### What stays the same

| Variable | Notes |
|----------|-------|
| `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` | Works exactly as before. Both `provider/model` and `provider:model` formats are accepted. |
| `BASEROW_ENTERPRISE_ASSISTANT_LLM_TEMPERATURE` | Still supported. Overrides the orchestrator temperature when set. |
| `OPENAI_API_KEY` | Unchanged. |
| `GROQ_API_KEY` | Unchanged. |
| `AWS_BEARER_TOKEN_BEDROCK` | Still works — pydantic-ai supports Bedrock bearer token auth natively. |

### Bridged for backward compatibility (no action needed)

| Old variable | Equivalent | Notes |
|--------------|------------|-------|
| `UDSPY_LM_MODEL` | `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` | If set and the new var is absent, the old value is used automatically. |
| `UDSPY_LM_API_KEY` | `OPENAI_API_KEY` / `GROQ_API_KEY` / etc. | Propagated to all provider key variables as a fallback. |
| `UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL` | `OPENAI_BASE_URL` | Still works; bridged automatically. |
| `AWS_REGION_NAME` | `AWS_DEFAULT_REGION` | Still works; bridged automatically. |

### New variables

| Variable | Notes |
|----------|-------|
| `OPENAI_BASE_URL` | Preferred replacement for `UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL`. |
| `AWS_DEFAULT_REGION` | Preferred replacement for `AWS_REGION_NAME`. |
| `OLLAMA_BASE_URL` | Replaces `UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL` for Ollama. Defaults to `http://localhost:11434/v1`. |
| `ANTHROPIC_API_KEY` | New provider — Anthropic models are now supported. |
