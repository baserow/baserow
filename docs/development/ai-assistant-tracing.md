# AI assistant tracing with Phoenix

[Arize Phoenix](https://arize.com/docs/phoenix) is the self-hosted platform we
use to inspect the AI assistant's LLM traces: every chat turn appears as a span
tree (agent run → LLM generations → tool calls) with inputs/outputs, token
counts, latency, and cost. It is also the foundation of the assistant eval
platform (datasets, experiments, prompt playground) being built on top of it —
see [ADR 007](../decisions/007-ai-assistant-eval-platform.md) for why Phoenix
and where this is going.

## Local development

The dev stack ships Phoenix behind the `ai-evals` compose profile (the `ai`
profile covers only what the assistant itself needs) — see the optional
services section of
[running the dev environment with Docker](./running-the-dev-env-with-docker.md).
In short, in `.env.docker-dev`:

```bash
COMPOSE_PROFILES=optional,ai,ai-evals
BASEROW_ASSISTANT_PHOENIX_URL=http://phoenix:6006
```

Start the stack, chat with the assistant, and open the Phoenix UI on
`http://localhost:6060` (no login locally). Unset the URL to stop exporting;
the assistant is unaffected either way. Phoenix stores its data in a `phoenix`
database inside the dev stack's Postgres, created automatically on first
start — the same storage backend the team instance uses.

| Variable | Purpose |
|----------|---------|
| `BASEROW_ASSISTANT_PHOENIX_URL` | Phoenix base URL. Empty (default) disables the export entirely. |
| `BASEROW_ASSISTANT_PHOENIX_API_KEY` | Only needed for auth-enabled instances (see below). Sent as `Authorization: Bearer` on trace ingest. |

Phoenix export runs **alongside** PostHog LLM analytics, not instead of it:
when both are configured the same spans feed both. Production keeps exporting
to PostHog; pointing it additionally at the team Phoenix instance is a
config-only change.

## Reading a trace

In the Phoenix UI, open the `default` project and click a trace. Each chat
turn is one trace: an `invoke_agent main_agent` root span, `chat <model>`
spans (one per LLM call, with the full prompt/response, token counts, and
cost), and `execute_tool <name>` spans (tool arguments and results). A
separate short `invoke_agent title_agent` trace generates the chat title.

What to look for when something is off:

- **Errored spans**: filter on `status_code == 'ERROR'` — a red tool span
  shows the exception the model received; a red LLM span is a provider
  failure. See
  [Phoenix trace filtering](https://arize.com/docs/phoenix/tracing/how-to-query-spans).
- **Retry loops**: many consecutive `chat` spans without an intervening tool
  result usually mean the model keeps producing invalid tool calls — read the
  last tool span's output for the validation message it was shown.
- **Wrong tool choice / missing context**: the first `chat` span's input
  contains the full system prompt, injected UI context, and tool manifest —
  check what the model actually saw before blaming the model.
- **Cost and latency**: sort traces by total tokens or duration; per-model
  prices are configurable in Phoenix settings
  ([cost tracking](https://arize.com/docs/phoenix/tracing/features-tracing/cost-tracking)).

## Experimenting with prompts and models

Every LLM span can be replayed: open it in a trace and click the playground
button — the exact system prompt, messages, and invocation parameters load
into the
[prompt playground](https://arize.com/docs/phoenix/prompt-engineering/overview-prompts),
where you edit the prompt, switch provider/model, re-run, and **Compare**
variants side by side with output, latency, token, and cost differences.

- **Provider keys** are environment variables on the `phoenix` container; the
  dev compose forwards `GROQ_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`,
  and `GEMINI_API_KEY` from `.env.docker-dev`. Other or OpenAI-compatible
  providers: Settings → AI Providers → New Provider.
- **Gotcha**: replay infers the provider from the span's model string. The
  assistant's Groq models are named `openai/...`, which routes to the OpenAI
  provider and fails with `model_not_found` — pick the model under **Groq**
  in the model selector before running.
- **Test over a dataset** runs the prompt (per model) over a Phoenix dataset
  and saves the results as an experiment on that dataset. The
  add-to-dataset button on any span turns real traffic into dataset examples,
  so regression cases can be collected straight from traces.

The playground exercises a **single prompt**, not the full agent-plus-tools
loop. To run the real eval suite across models, use the eval runner's page on
`http://localhost:8090` or `just b eval-run --model ...` — see
[AI assistant evals](../testing/ai-assistant-evals.md).

## Deploying the shared team instance

One shared Phoenix collects traces and eval results for the whole team. It is
the same container as the dev one, plus Postgres persistence and
authentication. Run it on any Docker host:

```yaml
services:
  phoenix:
    image: arizephoenix/phoenix:version-20.3.0
    environment:
      - PHOENIX_SQL_DATABASE_URL=postgresql://phoenix:${PHOENIX_DB_PASSWORD}@phoenix-db:5432/phoenix
      - PHOENIX_ENABLE_AUTH=true
      - PHOENIX_SECRET=${PHOENIX_SECRET}
      - PHOENIX_DEFAULT_ADMIN_INITIAL_PASSWORD=${PHOENIX_ADMIN_PASSWORD}
    ports:
      - "127.0.0.1:6060:6006"
    depends_on:
      - phoenix-db
    restart: unless-stopped

  phoenix-db:
    image: postgres:16
    environment:
      - POSTGRES_USER=phoenix
      - POSTGRES_PASSWORD=${PHOENIX_DB_PASSWORD}
      - POSTGRES_DB=phoenix
    volumes:
      - phoenix_db_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  phoenix_db_data:
```

Set `PHOENIX_SECRET` (a long random string, signs the JWTs),
`PHOENIX_DB_PASSWORD`, and `PHOENIX_ADMIN_PASSWORD` in the host's `.env`.
Postgres 14+ is required. Put your reverse proxy with TLS in front of port
6060 — the compose file deliberately binds to loopback only.

### First login and API keys

1. Log in as `admin@localhost` with the password from
   `PHOENIX_ADMIN_PASSWORD` (only read on first startup).
2. Invite team members from the settings page (admin/member/viewer roles;
   OAuth2/OIDC providers can be configured via env instead of local accounts).
3. Create a **system API key** (Settings → API keys, admin-only). This is the
   key backends use to send traces.

### Pointing an environment at it

On any Baserow deployment (a dev stack, a staging environment) set:

```bash
BASEROW_ASSISTANT_PHOENIX_URL=https://phoenix.your-domain.example
BASEROW_ASSISTANT_PHOENIX_API_KEY=<system API key>
```

Send an assistant chat message and the trace appears in the Phoenix UI within
a few seconds.

## Operational notes

- **Version pinning**: the image tag is pinned (`version-20.3.0`) and must be
  upgraded together with the `openinference-instrumentation-pydantic-ai` and
  (once the eval tooling lands) `arize-phoenix-client` Python packages — treat
  them as one upgrade unit and re-verify a trace after upgrading.
- **Privacy**: traces contain full chat content and tool arguments. Keep the
  instance on the internal network/VPN and treat access like access to
  production logs. Production traffic does not export here — this receives
  only what deployments explicitly configured with the env vars send.
- **Disk**: traces accumulate in Postgres and are kept forever by default;
  set a retention policy in Settings → Data Retention on the team instance.
- **License**: Phoenix is ELv2 — free for internal self-hosting; it only
  forbids reselling Phoenix itself as a hosted service.
