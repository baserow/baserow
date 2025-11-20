# Baserow AI-Assistant: Quick DevOps Setup

This guide shows how to enable the AI-assistant in Baserow, configure the required
environment variables, and (optionally) turn on knowledge-base lookups via an embeddings
server.

## 1) Core concepts

- The assistant runs via **UDSPy** — see https://github.com/baserow/udspy/
- UDSPy speaks to **any OpenAI-compatible API**.
- You **must** set `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` with the provider and model
  of your choosing.
- The assistant has been mostly tested with the `gpt-oss-120b` family. Other models can
  work as well.

## 2) Minimal enablement

Set the model you want, restart Baserow, and let migrations run.

```dotenv
# Required
BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL=openai/gpt-4o
OPENAI_API_KEY=your_api_key

# Optional - adjust LLM temperature (default: 0)
BASEROW_ENTERPRISE_ASSISTANT_LLM_TEMPERATURE=0
```

**About temperature:**
- Controls randomness in LLM responses (0.0 to 2.0)
- **Default: 0** (deterministic, consistent responses - recommended for production)
- Higher values (e.g., 0.7-1.0) = more creative/varied responses
- Lower values (e.g., 0-0.3) = more focused/consistent responses

## 3) Provider presets

Choose **one** provider block and set its variables.

### OpenAI / OpenAI-compatible

```dotenv
BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL=openai/gpt-4o
OPENAI_API_KEY=your_api_key
# Optional alternative endpoints (OpenAI EU or Azure OpenAI, etc.)
UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL=https://eu.api.openai.com/v1
# or
UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL=https://<your-resource-name>.openai.azure.com
# or any OpenAI compatible endpoint
```

### AWS Bedrock

```dotenv
BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL=bedrock/openai.gpt-oss-120b-1:0
AWS_BEARER_TOKEN_BEDROCK=your_bedrock_token
AWS_REGION_NAME=eu-central-1
```

### Groq

```dotenv
BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL=groq/openai/gpt-oss-120b
GROQ_API_KEY=your_api_key
```

### Ollama

```dotenv
BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL=ollama/gpt-oss:120b
OLLAMA_API_KEY=your_api_key
# Optionally and alternative endpoint
UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL=http://localhost:11434/v1
```

Under the hood, UDSPy auto-detects provider from the model prefix and builds an
OpenAI-compatible client accordingly.

## 4) Knowledge-base lookup

If your deployment method doesn’t auto-provision embeddings, run the Baserow embeddings
service and point Baserow at it.

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
