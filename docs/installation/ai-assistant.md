# Baserow AI-Assistant: Quick DevOps Setup

This guide shows how to configure the AI assistant's provider and model in Baserow
and optionally enable knowledge-base lookups through an embeddings server.

## 1) Core concepts

- The assistant is built on [**pydantic-ai**](https://ai.pydantic.dev/) — a
  Python agent framework that supports multiple LLM providers out of the box.
- An instance administrator configures providers and chooses one Kuma model under
  **Admin tools → AI providers → AI features**. A workspace admin can inherit that
  choice, select another model available to Kuma, or disable Kuma in the workspace's
  **Settings → AI providers**.
- `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` and its `UDSPY_LM_MODEL` alias are
  **deprecated**. They remain compatibility fallbacks while the Kuma selection is
  unconfigured or invalid. An explicit instance or workspace disable remains
  authoritative.
- The assistant has been mostly tested with the `gpt-oss-120b` family. Other models can
  work as well.

## 2) Minimal enablement

For a fresh setup, add a provider and its models under **Admin tools → AI providers**
or a workspace's **Settings → AI providers**; see
[where to configure them](https://baserow.io/docs/installation%2Fai-providers#where-to-configure-them).
On each model, choose whether it is available to Kuma, AI Fields, AI Agent actions, or
any combination of them, then select the Kuma model in the **AI features** section.
Availability permits a feature to choose a model; it does not force AI Fields or AI
Agent actions to use Kuma's model. Use **Test model** to check every selected feature. AI Fields and AI Agent
actions check for a text response, while Kuma also checks tool calling.

Changing a model that is already in use is confirmed, not applied silently. Disabling
or deleting a model, unchecking one of its features, or renaming its identifier first
reports how many AI Fields and AI Agent actions use it, and applies the change once
confirmed: those consumers store the provider type and the model identifier rather
than a reference to the model, so they keep the old selection and stop working until
they are repointed. Counts are per provider type and identifier, so an instance model
and a workspace model sharing an identifier report the same consumers. The Kuma
selection is a real reference instead, so disabling or deleting the model, or
unchecking Kuma, is refused while it is selected as the Kuma model: repoint that
selection first, in the **AI features** section of the scope that holds it. Renaming
is allowed and the Kuma selection follows the model to its new identifier. A consumer left on a model that is disabled or
gone keeps showing its saved provider and model, marked unavailable, so it can be
found and repointed.

For an existing installation, see
[Upgrading to Baserow 2.4](https://baserow.io/docs/installation%2Fai-providers#upgrading-to-baserow-24).
The upgrade imports legacy provider settings automatically. Applications published
before the upgrade keep the settings copied into them at publish time, and explicit
integration overrides keep their own credentials; both need separate review before
they can use centrally managed credentials. Republishing a site or workflow also
deploys its current draft changes.

The import does not cover the deprecated Kuma model selector or the provider-native
credentials used by Kuma. The assistant therefore stays on its legacy fallback until
an administrator configures the same provider connection in the database, marks and
tests a model for Kuma, and explicitly selects it. A database selection is
authoritative, so verify its credentials and endpoint before switching.
To roll back that selection, choose **Use environment model (deprecated)**, which
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
# Deprecated; choose the Kuma model under Admin tools → AI providers → AI features.
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

These presets retain compatibility for existing environment-based setups. Their
`BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` selector is **deprecated**; use provider
administration and an explicit Kuma selection when the connection is representable
there. Vertex AI, and Bedrock through the server's IAM role or instance profile, do
not have an equivalent database provider configuration, so those paths must keep
their verified environment fallback. Do not remove a working fallback before a
replacement is available and tested.

Choose **one** provider block for a fallback that is still needed. pydantic-ai's
native credential and connection variables, such as `OPENAI_API_KEY`, `GROQ_API_KEY`,
AWS credentials, and `OPENAI_BASE_URL`, remain supported; they are separate from the
deprecated Baserow model selector.

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

Bedrock with an IAM access key or a Bedrock API key can be added in
[AI providers](https://baserow.io/docs/installation%2Fai-providers#amazon-bedrock)
instead. Keep this fallback only for credentials that come from the server itself.

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
docker run -d --name baserow-embeddings -p 80:80 baserow/embeddings:1.1.1
```

To embed large volumes faster, for example for semantic search on big tables, run the
GPU image on a host with an NVIDIA GPU and the NVIDIA Container Toolkit instead, and set
`BASEROW_EMBEDDINGS_TEXTS_PER_REQUEST=64` in Baserow:

```bash
docker run -d --name baserow-embeddings --gpus all -p 80:80 baserow/embeddings:1.1.1-gpu
```

See the [embeddings README](https://github.com/baserow/baserow/blob/develop/embeddings/README.md)
for the requirements and how to run several containers on one GPU.

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

1. Select a usable Kuma model under **Admin tools → AI providers → AI features** and
   make sure its model test passes; or
2. For an existing compatibility setup, leave the Kuma selection unconfigured and
   set the deprecated
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

### Environment compatibility

| Variable | Notes |
|----------|-------|
| `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` | **Deprecated.** Kuma uses this model until you make a model available to Kuma and select it under **Admin tools → AI providers → AI features**. It is also used when that selection becomes unavailable, but not when Kuma is set to **Disabled** there. Both `provider/model` and `provider:model` formats are accepted. |
| `BASEROW_ENTERPRISE_ASSISTANT_LLM_TEMPERATURE` | Still supported. Overrides the orchestrator temperature when set. |
| `OPENAI_API_KEY` | Unchanged. |
| `GROQ_API_KEY` | Unchanged. |
| `AWS_BEARER_TOKEN_BEDROCK` | Still works — pydantic-ai supports Bedrock bearer token auth natively. |

### Bridged for backward compatibility

| Old variable | Equivalent | Notes |
|--------------|------------|-------|
| `UDSPY_LM_MODEL` | Kuma model under **Admin tools → AI providers → AI features** | **Deprecated.** Used only when `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` is not set. Selecting a Kuma model in **AI features** replaces it; renaming it to `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` does not. |
| `UDSPY_LM_API_KEY` | **API key** of the provider in **Admin tools → AI providers** | **Deprecated.** Only read while Kuma uses its environment model. If you still need that, use the provider's own variable instead, such as `OPENAI_API_KEY` or `GROQ_API_KEY`. |
| `UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL` | **Base URL** (OpenAI) or **Host** (Ollama) of the provider in **Admin tools → AI providers** | **Deprecated.** Only read while Kuma uses its environment model. If you still need that, use `OPENAI_BASE_URL` or `OLLAMA_BASE_URL` instead. |
| `AWS_REGION_NAME` | `AWS_DEFAULT_REGION` | Still works; bridged automatically. |

### New variables

| Variable | Notes |
|----------|-------|
| `OPENAI_BASE_URL` | Preferred replacement for `UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL`. |
| `AWS_DEFAULT_REGION` | Preferred replacement for `AWS_REGION_NAME`. |
| `OLLAMA_BASE_URL` | Replaces `UDSPY_LM_OPENAI_COMPATIBLE_BASE_URL` for Ollama. Defaults to `http://localhost:11434/v1`. |
| `ANTHROPIC_API_KEY` | New provider — Anthropic models are now supported. |

## 8) Background runs

Kuma answers every message in a background task, so its reply keeps going when
the browser is closed. The reply streams through Redis Streams, and a reloaded
page picks it up without repeating the prompt or its tools.

Redis keeps each run's live output, up to 8 MiB or 10,000 events, until an hour
after its last output. Without that output, the browser waits for the saved
answer. Postgres saves the answer only when the run ends, so if both the worker
and Redis are lost the partial answer is lost; tool changes already made remain,
and the run is not retried.

For adapter and protocol details, see
[Background chat runs](../development/background-chat-runs.md).

Background runs use the existing worker infrastructure:

- **Worker.** The tasks run on the `chat_run` queue, which the existing export
  worker (`celery-exportworker`) consumes, so no new service is needed. A custom
  worker command must include `chat_run` in its `-Q` list, or Kuma messages wait
  and fail after an hour. For how worker settings affect Kuma, see
  `BASEROW_AMOUNT_OF_WORKERS` and `BASEROW_RUN_MINIMAL` in the
  [Celery configuration](https://baserow.io/docs/installation%2Fconfiguration#celery-configuration).
  The worker calls Kuma's model, so with the deprecated environment model it
  also needs `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` and the provider's
  credentials.
- **Sharing.** Kuma shares the export worker with exports, imports, webhooks and
  notification emails. When they delay each other, isolate Kuma without code
  changes: start the export worker with `-X chat_run` and add a container that
  runs `celery-exportworker -Q chat_run`.
- **Deploys.** A deploy interrupts runs that take longer than the worker's stop
  grace. The compose files and the Helm chart give the export worker 120
  seconds. The all-in-one image stops it after 10 seconds, so a deploy there
  interrupts the runs in flight. An interrupted run ends with an error, and the
  message can be sent again.
- **Health.** The health check warns when a run has waited more than 5 minutes
  for a worker, or when a run lost its worker and wasn't cleaned up (check that
  `celery-beat` runs).

### First rollout from HTTP execution

Existing HTTP replies finish in the process that accepted them. They are never
converted to runs or sent to a worker again. Existing chats, messages, predictions
and model history keep their format; this change has no schema migration or
backfill. The next accepted message starts the chat's first background run.

Use a brief admission pause for Kuma messages during this first cutover:

1. At the ingress, temporarily reject **new POST requests** to
   `/assistant/chat/<uuid>/messages/` with HTTP 503 and `Retry-After`. Apply this
   before forwarding or reading the streaming response, so rejected prompts are
   neither saved nor executed. Keep existing connections, history GETs, Stop
   DELETEs and the rest of Baserow available. Do not automatically retry POSTs:
   a lost response does not prove that the original prompt was rejected.
2. Leave the old HTTP backends alive until every accepted Kuma response finishes.
   Measure active requests at the proxy/backend; `AssistantChat.status` does not
   track these replies, and absence of a `ChatRun` does not mean a chat is idle.
   Verify that the final messages and history are saved before proceeding. A
   Gunicorn, proxy or pod shutdown timeout is not a drain confirmation. If a
   reply takes longer, keep waiting or postpone the cutover; do not kill it to
   meet a rollout deadline.
3. While admission remains paused, upgrade **all Celery workers**, including
   export/chat-run consumers and workers running sweep/prune tasks, then the beat
   process. Wait for old consumers to exit and their reserved tasks to finish.
   An old worker knows the shared `execute_chat_run` task but not Kuma's
   `assistant` run type, so it can claim and fail a new Kuma run. Confirm the new
   workers load `AssistantChatRunType`, consume `chat_run`, and have the selected
   model's credentials. Check `/api/_health/celery-queue/?queue=chat_run` returns
   200; queue health alone does not verify the adapter or model configuration.
4. Upgrade every HTTP backend and switch traffic while admission stays paused.
   Only then remove the ingress rule. New POSTs now create runs; an old browser
   tab can keep using the original content/UI-context request and cumulative JSON
   response. Stop still accepts the original DELETE URL.
5. Deploy the frontend last. New frontend assets require the new backends; do not
   send them to an old backend pool. Verify a new prompt completes, refreshing
   follows that same run, and the next prompt in an existing chat retains its
   earlier context without repeating tools.

Old and new writers must not answer the same chat concurrently: the old HTTP
path has no shared admission lock and can overwrite a background run's history.
The pause and complete drain avoid adding a second execution path, a backfill or
a rollout flag to the application. After the cutover, requests always use runs.

If continuous admission is required, first ship a separate preparation release
that makes old HTTP sends participate in shared admission tracking. Do not skip
the drain and rely on a normal mixed-version rolling restart.

Before reopening admission, rollback consists of restoring the old HTTP pool
while keeping the pause in place until it is ready. Once runs have been accepted,
pause new sends again and drain their queue and active executions on the new
workers before reverting any backend or worker. Keep the schema and saved chat
data; do not reverse the shared engine migration, recreate runs, or replay prompts.
Keep the new workers/backends if runs cannot be drained safely and fix forward.
Already loaded new browser assets also need the new API; a full rollback needs a
controlled client reload. Prefer reverting the frontend alone while keeping the
new backend's compatible POST response.
