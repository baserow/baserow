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
5. The page's **Help** tab renders this guide and the
   [tracing guide](../development/ai-assistant-tracing.md) inline.

> **Warning:** the runner hot-reloads on any mounted `.py` change (including
> a lint/format pass), which kills queued and running experiments — don't
> edit backend Python while a run is in flight.

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
| `kuma-docs` | 64 | docs Q&A via `search_user_docs`, incl. cannot-do guardrail cases |

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

UI-added examples are **runnable**: they appear on the runner page under
"Added in the Phoenix UI" in their dataset's tab (reload the page after
adding one), and they run with the rest of the dataset too. The example's
`input` needs a `{"prompt": "..."}` (or `"question"`) and everything else is
optional metadata:

### Docs questions

Add the example to `kuma-docs`. It runs against the standard docs scenario
with the standard checks (`search_user_docs` called, at least one source),
and the LLM judge scores `answer_quality`. Optional fields:

- `output` → `{"reference_answer": "..."}` — the ideal answer the judge
  grades against.
- metadata `expected_keywords` — list of strings; adds an
  "answer mentions one of" check and informs the judge.

### Tool use cases

Add the example to the matching dataset (`kuma-database`, `kuma-builder`,
`kuma-automation`, `kuma-core`) and declare what to exercise in its metadata:

- `scenario` — name of a registered starting state (the
  `register_scenario("...")` ids in `evals/datasets/*.py` and
  `evals/scenarios.py`). Defaults to `empty-workspace`, a bare workspace —
  enough for "create a table called X"-style prompts. Pick a richer scenario
  when the prompt references existing objects; its object names must match
  what the prompt mentions.
- `expected_tools` — list of tool names; each adds a "called `<tool>`" check.
- `answer_contains` — list of strings; each adds a case-insensitive
  "answer contains" check.
- `mode` (agent mode, defaults to the dataset's usual one), `max_iters`,
  `max_tool_errors` — same meaning as on a code case.

Checks that assert on **database state** (rows really created, field types
correct) can't be expressed in metadata — promote the example to code for
those. The tool-error budget check always runs, and the full trace is linked
from every run, so even a check-less example is useful for experimenting.

To promote a UI-added example to code:

```bash
just b eval-export --dataset kuma-docs
```

This prints a ready-to-paste `_register_docs_case(...)` snippet per UI-added
`kuma-docs` example (question from the example, keywords/source patterns from
its metadata if the UI author set them, else `TODO` placeholders to fill in;
a `reference_answer` kwarg is included too if the example's `output` carries
one). Paste it into `datasets/docs.py`, pick a real id and keywords, then
`just b eval-sync` — the UI copy is dropped automatically because its prompt
now matches the code case (matched by exact prompt text, so no duplicate).
Non-`kuma-docs` datasets have no registration helper to generate from, so
`eval-export` prints a commented JSON block instead; write the scenario and
checks by hand.

### Reference answers for docs cases

A `kuma-docs` case can carry an ideal "reference answer" that the LLM judge
grades Kuma's answer against (see below). Add one in code with
`_register_docs_case(..., reference_answer="...")`, or curate it directly on
a synced example in the Phoenix UI by editing its `output` field to
`{"reference_answer": "..."}` — that's a normal, versioned edit to the
example, so it survives `just b eval-sync`: a code case with no
`reference_answer` never overwrites a live one, it only adopts it, and a
code-set `reference_answer` always wins over whatever is live.

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
are synced to Phoenix's **Prompts** tab as versioned prompts on every
eval-sync. Every experiment's `prompts` metadata records the content hash of
each prompt as it ran, so prompt-version comparisons are filterable in
Phoenix.

To experiment with a prompt change **without touching code**:

1. Edit the prompt in Phoenix's Prompts tab and save — that's a new version
   (Phoenix prompts are append-only, nothing is lost).
2. In the runner page's **Prompt overrides** section, tick that prompt —
   checked prompts run with their latest Phoenix version instead of the code
   constant. CLI equivalent: `--override-prompt <name>` (repeatable). The
   list sorts the active tab's likely-relevant prompts first, but any prompt
   can be overridden — one the selected cases never exercise is just a no-op.
3. Run and compare: the experiment is stamped with the effective prompt
   hashes plus a `prompt_overrides` list naming what was overridden.
4. To promote a winning prompt, paste its text into the code constant — the
   next eval-sync records it as the new latest version.

Editing the constant in code directly still works too (the runner
hot-reloads .py changes).

## Reading results

Every experiment run links to its trace (agent → LLM calls → tool calls, with
token counts and cost). Failed checks appear in the experiment's `checklist`
evaluator explanation with their hints. How to compare against the committed
baseline, classify outcomes (improvement / regression / gap / flake), and
diagnose failures through traces:
[evaluating results](./ai-assistant-eval-analysis.md).

`kuma-docs` runs get a third score, `answer_quality`, from an LLM judge (the
judge prompt lives in `evals/judge.py`) that grades the answer's correctness,
helpfulness, and groundedness against the sources the assistant cited. When
the case (or its synced example) carries a `reference_answer`, the judge is
also given it and told to weigh factual agreement with it heavily — it's the
ideal answer, not the only acceptable phrasing, so wording differences alone
don't cost points. The judge model is `BASEROW_EVAL_JUDGE_MODEL`, defaulting
to `groq:openai/gpt-oss-120b`, and is stamped into every experiment's
metadata. A judge failure (LLM error, missing case, ...) records no
`answer_quality` score rather than a 0, so it doesn't skew aggregates.
