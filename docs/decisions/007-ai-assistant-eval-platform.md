# 007: AI assistant eval and observability platform

**Status:** accepted (2026-08-21). Tracing, the eval framework (65 cases in 5
datasets), and the runner are shipped (2026-08-24); the pytest harness is
retired. Judge evaluators are still in progress.

## The problem

The AI assistant has ~38 LLM evals that exist only as opt-in pytest tests
(`-m eval`) run on individual laptops. There is no shared place to run them,
compare models and providers, inspect traces, or track quality, cost, and
latency over time. We need one standard, team-wide way to evaluate the
assistant.

## Decision

Self-host [Arize Phoenix](https://arize.com/docs/phoenix) as the eval and
LLM-observability platform, plus a small **eval runner** service we own:

1. **Traces**: the assistant's pydantic-ai OTel spans are exported to Phoenix
   (OpenInference format) whenever `BASEROW_ASSISTANT_PHOENIX_URL` is set.
   See [AI assistant tracing](../development/ai-assistant-tracing.md).
2. **Evals as code**: eval cases live in the codebase as declarative dataset
   items with code evaluators, and are synced idempotently into Phoenix
   (stable case ids, append-only). The former pytest harness is retired;
   [AI assistant evals](../testing/ai-assistant-evals.md) is the runbook.
3. **Runner**: a dev-stack service that executes the real agent against a
   dataset (from a minimal run page, a management command, or CI later) and
   records results as Phoenix experiments — scores, cost, latency, traces.
4. **Judges as code**: LLM-as-judge evaluators are pydantic-ai agents
   versioned in the repo, optionally grounded on the assistant's knowledge
   base. Phoenix's UI-configured evaluators stay available for ad-hoc use but
   are not the standard.

## Why Phoenix?

A structural fact drove the choice: **no platform executes your Python agent
server-side**. "Run evals from a UI" therefore requires a self-owned runner on
every platform — which removes the main advantage of the heavier candidates
and makes footprint, licensing, and integration quality decisive.

| Candidate | Verdict |
|-----------|---------|
| **Phoenix** | 1 container, Postgres-backed; zero feature gates; free auth/RBAC/OAuth2; first-party pydantic-ai instrumentation; datasets/experiments/playground/cost tracking included. |
| Langfuse v4 | Full feature set, MIT, native remote-run webhook — but 6 required containers (ClickHouse, Redis, MinIO, …) with no lighter profile. |
| Opik | No authentication at all in self-hosted OSS, ~9 containers, no UI batch runs of a real agent. |
| LangSmith, Braintrust, W&B Weave | Self-hosting is enterprise-contract only. |
| promptfoo, MLflow, agenta, Laminar | Wrong shape (YAML evals, view-only UI, weak velocity, or gated alerts). |

## Key choices

- **Storage**: Postgres everywhere — locally a `phoenix` database in the dev
  stack's existing Postgres (created by the one-shot `ai-evals-db-init`
  service), a dedicated Postgres for the shared team instance. No storage
  drift between dev and team.
- **Compose profile**: Phoenix runs under `ai-evals`, separate from `ai`
  (assistant prerequisites), so using the assistant never requires Phoenix.
- **Off by default, additive to PostHog**: `BASEROW_ASSISTANT_PHOENIX_URL`
  empty disables the export entirely; PostHog LLM analytics stays the
  production path (dual export is a config-only change — see
  [AI assistant tracing](../development/ai-assistant-tracing.md)).
- **Auth**: team instances enable Phoenix auth; ingest authenticates with a
  system API key via `BASEROW_ASSISTANT_PHOENIX_API_KEY`.
- **Dependencies** are dev-group only (`openinference-instrumentation-pydantic-ai`,
  later `arize-phoenix-client`); the export degrades with a logged warning if
  they are missing, so production images are unaffected.

## Consequences and risks

- Phoenix is **ELv2** (source-available): free for internal self-hosting,
  forbids only reselling Phoenix itself as a service.
- The dev stack's Postgres 14 is exactly Phoenix's minimum version; if a
  future Phoenix raises the floor, Phoenix gets its own database container
  again.
- The Phoenix image, `openinference-instrumentation-pydantic-ai`, and
  `arize-phoenix-client` versions are **one upgrade unit**; pydantic-ai
  upgrades can silently degrade trace quality (the span rewriting is
  untyped), so re-verify a trace after upgrading either side.
- We own the runner: a small service to build and maintain, in exchange for
  running the real agent (not a prompt approximation) from a UI.
