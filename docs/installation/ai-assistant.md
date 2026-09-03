# Baserow AI-Assistant: Quick DevOps Setup

This guide shows how to enable the AI-assistant in Baserow, configure the required
environment variables, and (optionally) turn on knowledge-base lookups via an embeddings
server.

## 1) Core concepts

- The assistant is built on [**pydantic-ai**](https://ai.pydantic.dev/) — a
  Python agent framework that supports multiple LLM providers out of the box.
- With database-backed AI providers enabled, an instance administrator configures
  providers and chooses one Kuma model under **Admin > AI providers > AI features**.
  A workspace can inherit that choice, select another model available to Kuma, or
  disable Kuma in its workspace AI provider settings.
- `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` remains the legacy fallback while the
  `ai-providers` feature is disabled, or while its Kuma selection is unconfigured
  or invalid. An explicit instance or workspace disable remains authoritative.
- The assistant has been mostly tested with the `gpt-oss-120b` family. Other models can
  work as well.

## 2) Minimal enablement

For a fresh database-backed setup, enable `ai-providers`, then add a provider and
its models in the admin UI. On each model, choose whether it is available to Kuma,
AI Fields, or both, then select the Kuma model in the **AI features** section.
Availability permits a feature to choose a model; it does not force AI Fields to
use Kuma's model. Use **Test model** to check every selected feature. AI Fields
check for a text response, while Kuma also checks tool calling.

For every existing installation, deploy this release with `ai-providers` still
disabled and wait for the previous web and worker processes to drain. If the
installation uses the `*` catch-all flag, first roll out an explicit list of the
other flags to every process on the currently installed release. Wait for all
wildcard-configured processes to drain before deploying the new image; do not combine
these changes in one rolling update. If configuration cannot be rolled out
separately, stop the old processes before starting the new release with the explicit
flag list. Pause changes to instance and workspace AI settings through the import and
feature switch.
The database-backed Google and Groq providers are configured through the admin UI,
not new provider environment variables. Add either provider after the old frontend
processes have drained; older
bundles cannot render these provider types. Also require active users to reload
Baserow, or close and reopen their tabs, before either provider can appear in API
or realtime payloads: draining the frontend processes does not replace JavaScript
already loaded by a browser. Keep the settings-write pause in place until that
client cutover is complete.
Preview both scopes before applying them, then enable the feature:

```bash
baserow migrate_ai_provider_settings --scope instance
baserow migrate_ai_provider_settings --scope workspace
baserow migrate_ai_provider_settings --scope instance --apply
baserow migrate_ai_provider_settings --scope workspace --apply
```

Review every warning before enabling the feature. Repair or explicitly accept
incomplete legacy settings and differences from an existing database provider. The
importer keeps an existing database provider in a conflict, while an incomplete
workspace override can inherit the instance provider after the switch. Keep the
settings-write pause in place while you redeploy or restart every web, backend, and
worker process with `ai-providers` enabled. Wait for every feature-disabled process
to drain before ending the pause; otherwise different process generations can resolve
different settings, or a workspace can change its legacy JSON after the command reads
it.

After the switch, republish each Application Builder site or Automation workflow that
uses an AI integration without its own provider override. Older publications contain
a snapshot of the inherited legacy workspace settings, while a new publication uses
the live database-backed workspace provider. Integrations with an explicit provider
override remain self-contained and do not need to be republished for this reason.

This command imports Baserow's legacy AI provider configuration; it does not
import `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` or the provider-native credentials
used by Kuma. The assistant therefore stays on its legacy fallback until an
administrator configures the same provider connection in the database, marks and
tests a model for Kuma, and explicitly selects it. A database selection is
authoritative, so verify its credentials and endpoint before switching.
To roll back that selection, choose **Use legacy environment model**, which
also displays the configured model, in the instance AI feature settings. The choice
is disabled when neither `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` nor the deprecated
`UDSPY_LM_MODEL` fallback provides a model **to the web-frontend process**, which is
where that option is rendered: setting the variable on the backend alone leaves the
option disabled while the backend fallback still resolves. Choosing **Disabled**
deliberately keeps Kuma off.

When using the legacy fallback with Docker Compose or multiple services, set
`BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` in both backend and frontend services.

```dotenv
# Required only for the legacy fallback
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

## 3) Legacy fallback provider presets

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

### Google (Gemini)

```dotenv
BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL=google:gemini-3.6-flash
GOOGLE_API_KEY=your_api_key
```

Create the key in [Google AI Studio](https://aistudio.google.com/apikey). For Vertex AI,
use the `google-cloud` prefix instead: `GOOGLE_API_KEY` is then treated as a Vertex AI
Express Mode key, while project-based access uses Application Default Credentials.

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

Use one of these configurations:

1. Select a usable Kuma model under **AI providers > AI features** and make sure
   its model test passes; or
2. Leave the Kuma selection unconfigured and set the legacy
   `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` in both backend and frontend services,
   with its provider credentials available to the backend.

An explicit Kuma disable does not use the legacy fallback.

### Verifying legacy environment variables in development

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
| `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` | Continues as the fallback while the database selection is unconfigured or invalid, but not when it is explicitly disabled. Both `provider/model` and `provider:model` formats are accepted. |
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
