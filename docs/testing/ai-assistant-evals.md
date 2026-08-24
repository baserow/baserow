# AI Assistant Evals

The assistant eval suite runs the real agent against a live LLM and scores the
outcome. Evals are defined in the codebase, synced automatically into
[Phoenix](../development/ai-assistant-tracing.md) as datasets, and every run is
recorded there as an experiment with per-case scores, cost, latency, and a full
trace. Why this platform: [ADR 007](../decisions/007-ai-assistant-eval-platform.md).

## Running evals from the UI

1. In `.env.docker-dev`: `COMPOSE_PROFILES=optional,ai,ai-evals`, plus a
   provider API key (e.g. `GROQ_API_KEY`) — see
   [AI assistant tracing](../development/ai-assistant-tracing.md) for the
   Phoenix side.
2. `just dc-dev up -d` — the `assistant-eval-runner` service migrates its own
   `baserow_evals` database, syncs the datasets into Phoenix, and serves
   `http://localhost:8090`.
3. Pick a whole dataset or individual cases, a model from the dropdown (only
   models whose provider key is configured are listed; the free-text field
   accepts any pydantic-ai model string), a repeat count, and Run.
4. The run row links to the experiment in Phoenix when done.

## Running evals from the CLI

The CLI uses your host env (`.env.local`): the database it points at and
`BASEROW_ASSISTANT_PHOENIX_URL` for Phoenix.

> **Warning:** CLI runs create real scenario data (users, workspaces, apps) in
> whatever database `DATABASE_NAME` points at, with no teardown. The runner
> service uses its own disposable `baserow_evals` database, so prefer it for
> bulk runs, or point `DATABASE_NAME` at a disposable database first.

```bash
# Sync the datasets defined in code into Phoenix (idempotent)
just b eval-sync

# Run a whole dataset
just b eval-run --dataset kuma-core

# Run selected cases (must all belong to the same dataset)
just b eval-run --case database/creates-simple-table --case database/creates-view-kanban

# Compare models / measure flakiness
just b eval-run --dataset kuma-builder --model groq:openai/gpt-oss-20b --runs 3 --name builder-20b
```

`--runs N` repeats every case N times in one experiment — the score spread
across repetitions is the flake signal. Compare experiments (models, prompt
changes, repeat runs) side by side in the Phoenix dataset view. Every
experiment is auto-stamped with its model, git branch and commit, and prompt
hashes, so branch/model comparisons are filterable in Phoenix.

## The datasets

| Dataset | Cases | Covers |
|---------|-------|--------|
| `kuma-core` | 3 | creating/listing databases and automations |
| `kuma-database` | 21 | tables, fields, views, filters, rows |
| `kuma-builder` | 16 | pages, elements, data sources, themes, user sources |
| `kuma-automation` | 7 | workflows, triggers, nodes |
| `kuma-docs` | 18 | the `search_user_docs` RAG tool |

`kuma-docs` needs the knowledge base: the `embeddings` service (`ai` profile)
plus a synced KB. When unavailable, those cases are recorded as skipped, not
failed.

## Writing a new eval

Cases live in
`enterprise/backend/src/baserow_enterprise/assistant/evals/datasets/` and are
picked up automatically (registration on import, synced at runner startup or
via `just b eval-sync`). A case is three parts — a scenario (the Baserow state
the agent starts from), a prompt, and checks:

```python
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.evals.harness import tool_called
from baserow_enterprise.assistant.evals.registry import register_case, register_scenario
from baserow_enterprise.assistant.evals.scenarios import build_database_ui_context
from baserow_enterprise.assistant.evals.types import (
    CheckResult,
    EvalCase,
    EvalRunOutput,
    EvalScenario,
)


@register_scenario("database-my-scenario")
def _my_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(workspace=workspace, name="Sales")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_database_ui_context(user, workspace, database),
        refs={"database": database},
    )


def _my_checks(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    return [
        CheckResult("called list_tables", tool_called(output, "list_tables") >= 1),
        CheckResult(
            "answer mentions Sales",
            "sales" in output.answer.lower(),
            hint=output.answer[:200],
        ),
    ]


register_case(
    EvalCase(
        id="database/my-new-case",          # append-only, never rename
        dataset="kuma-database",
        prompt="Which tables are in the Sales database?",
        scenario="database-my-scenario",
        checks=_my_checks,
        max_iters=10,
    )
)
```

Rules that keep results comparable over time:

- **Case ids are append-only.** They are the stable key in Phoenix; renaming
  one breaks its history. Add new ids, never repurpose old ones.
- Scenario object names must match what the prompt references.
- Checks run right after the agent, with the scenario objects alive — DB
  assertions through `scenario.refs` are the norm. The harness automatically
  prepends a `tool_errors_within_budget` check (`EvalCase.max_tool_errors`,
  default 0).
- Pre-run state a check needs later (a snapshot before the agent acts) goes in
  `scenario.pre_state`.
- A case's score is `passed_checks / total_checks`; it passes only when every
  check passes.

## Contributing cases from the Phoenix UI

You don't need a PR to add a case: from the dataset editor, or from a trace
span's "Add Example to Dataset", add an example directly in Phoenix. `just b
eval-sync` preserves it — it no longer wipes examples that aren't in the
codebase, only code-owned ones (identified by a `case_id` in their metadata)
are replaced wholesale.

To promote a UI-added example to code:

```bash
just b eval-export --dataset kuma-docs
```

This prints a ready-to-paste `_register_docs_case(...)` snippet per UI-added
`kuma-docs` example (question from the example, keywords/source patterns from
its metadata if the UI author set them, else `TODO` placeholders to fill in).
Paste it into `datasets/docs.py`, pick a real id and keywords, then `just b
eval-sync` — the UI copy is dropped automatically because its prompt now
matches the code case (matched by exact prompt text, so no duplicate).
Non-`kuma-docs` datasets have no registration helper to generate from, so
`eval-export` prints a commented JSON block instead; write the scenario and
checks by hand.

A UI-added example is still part of the dataset, so it runs alongside code
cases — but with no code case to resolve, the runner records it as `skipped`
rather than crashing or scoring it.

## Models and providers

The dropdown/default list is `EVAL_MODELS` in
`enterprise/backend/src/baserow_enterprise/assistant/evals/models.py` — extend
it there. Any pydantic-ai `provider:model` string works via `--model` or the
free-text field, given the matching `*_API_KEY` env var. The model applies to
the whole agent, sub-agents included.

## Prompts

Kuma's load-bearing prompts (the main system prompt and each sub-agent's
instructions — see `SYNCED_PROMPTS` in
`enterprise/backend/src/baserow_enterprise/assistant/evals/prompt_sync.py`)
are synced to Phoenix's Prompts tab as versioned prompts on every eval-sync.
To experiment with a prompt change: edit the constant in code (the runner
hot-reloads), run an experiment, and compare — the experiment's `prompts`
metadata records the content hash of every synced prompt, so you can see
exactly which prompt version produced which scores.

## Reading results

Every experiment run links to its trace (agent → LLM calls → tool calls, with
token counts and cost). What to look for when a case fails:
[reading a trace](../development/ai-assistant-tracing.md#reading-a-trace).
Failed checks appear in the experiment's `checklist` evaluator explanation
with their hints.

`kuma-docs` runs get a third score, `answer_quality`, from an LLM judge (the
judge prompt lives in `evals/judge.py`) that grades the answer's correctness,
helpfulness, and groundedness against the sources the assistant cited. The
judge model is `BASEROW_EVAL_JUDGE_MODEL`, defaulting to
`groq:openai/gpt-oss-120b`, and is stamped into every experiment's metadata.
A judge failure (LLM error, missing case, ...) records no `answer_quality`
score rather than a 0, so it doesn't skew aggregates.
