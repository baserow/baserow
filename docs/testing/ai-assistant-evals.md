# AI Assistant Evals

The assistant eval suite runs the real agent against a live LLM to verify
end-to-end behaviour: tool selection, schema compatibility, row creation, etc.

All eval tests live under
`enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/` and are
marked with `@pytest.mark.eval` so they are **skipped by default** in CI and
local test runs.

## Prerequisites

1. A running PostgreSQL database (see [running-tests.md](../development/running-tests.md)).
2. An API key for the LLM provider you want to test against.
3. **For `test_eval_search_user_docs` only:** an embeddings server and a
   synced knowledge base (see [Search docs evals](#search-docs-evals) below).

## Quick start

```bash
# Set your API key (Groq example — works with any pydantic-ai provider)
export GROQ_API_KEY=gsk_...

# Suppress noisy framework-level log messages (Celery task registration, etc.)
export BASEROW_BACKEND_LOG_LEVEL=WARNING

# Run all evals with the default model (groq:openai/gpt-oss-120b)
just b test ../enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/ \
  -m eval -v

# Run a single eval file
just b test ../enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/test_eval_core_builders.py \
  -m eval -v
```

> **Tip:** Do **not** pass `-s`. Without it, pytest captures `print_message_history` output and shows it only in the failure report — passing tests stay silent. Use `-s` only when you want to watch the agent's tool calls in real time for a single test.


## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `EVAL_LLM_MODEL` | `groq:openai/gpt-oss-120b` | Model string in pydantic-ai format (`provider:model`). Accepts a comma-separated list to parametrize every eval across multiple models. |
| `EVAL_RETRIES` | `0` | Retry each failing eval test up to N times. If a test passes on retry it's a flake (LLM non-determinism); if it fails all N retries it's a consistent bug. |
| `GROQ_API_KEY` | — | Required when using a Groq model. |
| `OPENAI_API_KEY` | — | Required when using an OpenAI model. |
| `ANTHROPIC_API_KEY` | — | Required when using an Anthropic model. |

### API keys from a file

The eval conftest reads API keys from the same `TEST_ENV_FILE` that
`baserow/config/settings/test.py` already parses, and exposes them via
`os.environ` so that LLM provider SDKs can find them:

```bash
TEST_ENV_FILE=.env.testing-local just b test \
  ../enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/ -m eval -v -s
```

Variables already present in `os.environ` take precedence.

### Running against multiple models

```bash
GROQ_API_KEY=... OPENAI_API_KEY=... EVAL_LLM_MODEL="groq:openai/gpt-oss-120b,openai:gpt-4o" \
just b test ../enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/ \
  -m eval -v -s
```

Each test will run once per model, with the model name shown in the test ID.

## Test files

File names follow the pattern `test_eval_{module}_{feature}.py`, where module
maps to the tool directory (`core`, `database`, `automation`, `navigation`,
`search_user_docs`). Browse
`enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/` for the
full list. Each file defines its prompts as module-level `PROMPT_*` constants
at the top, making it easy to scan which scenarios are covered without reading
the test bodies.

## Writing a new eval

1. Create a new `test_eval_<area>.py` file in the `evals/` directory.
2. Define prompts as `PROMPT_*` constants at the top, so it's easier to have an overview of the existing evals.
3. Mark each test with `@pytest.mark.eval` and
   `@pytest.mark.django_db(transaction=True)`.
4. Use the helpers from `eval_utils.py`:

```python
import pytest
from .eval_utils import (
    EvalChecklist,
    build_database_ui_context,
    count_tool_errors,
    create_eval_assistant,
    print_message_history,
)

PROMPT_DOES_SOMETHING = "Do something useful in database {database_name}"

@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_does_something(data_fixture, eval_model):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace, name="Test")

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=15, model=eval_model
    )
    ui_context = build_database_ui_context(user, workspace, database)
    deps.tool_helpers.request_context["ui_context"] = ui_context

    result = agent.run_sync(
        user_prompt=PROMPT_DOES_SOMETHING.format(database_name=database.name),
        deps=deps,
        model=model,
        usage_limits=usage_limits,
        toolsets=[toolset],
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    with EvalChecklist("does something") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        # Add domain-specific checks here
        checks.check("created the thing", some_condition, hint="details if failed")
```

### Key helpers

| Helper | Purpose |
|--------|---------|
| `create_eval_assistant(user, workspace, max_iters, model)` | Returns `(agent, deps, tracker, model, usage_limits, toolset)` configured like production. |
| `build_database_ui_context(user, workspace, database, table)` | Builds the UI context JSON the agent receives. |
| `count_tool_errors(result)` | Returns `(error_count, hint)` — count of tool validation errors (pydantic retries) and a formatted hint string. Use with `EvalChecklist`: `checks.check("no tool errors", err_count == 0, hint=err_hint)`. |
| `EvalChecklist(name)` | Context manager for soft assertions: collects checks, prints a score table (`4/6 (66%)`), and only hard-fails at the end. Use for tests with multiple independent checks. |
| `print_message_history(result)` | Prints the full agent conversation to stdout. |
| `format_message_history(result)` | Returns the conversation as a list of dicts for programmatic assertions. |

## Search docs evals

`test_eval_search_user_docs.py` tests the `search_user_docs` tool end-to-end:
the agent receives a real user question, decides to call the tool, the tool
performs a vector search against the knowledge base, and a sub-agent produces
an answer with source URLs. The test verifies that:

1. The agent called `search_user_docs`.
2. The answer mentions expected concepts (e.g. "date_diff" for a date
   formula question).
3. Returned source URLs match expected documentation pages (non-fatal
   warning if not — URLs can change).

### Additional prerequisites

These tests are **automatically skipped** when the knowledge base is not
available. To enable them:

1. **Embeddings server** — start the embeddings service and set:
   ```bash
   # Running tests outside Docker (local dev):
   export BASEROW_EMBEDDINGS_API_URL=http://localhost:7999
   # Running tests inside Docker:
   export BASEROW_EMBEDDINGS_API_URL=http://embeddings
   ```

2. **pgvector extension** — the PostgreSQL instance must have the `vector`
   extension installed. If you use the dev Docker setup this is already
   included.

3. **Sync the knowledge base** — the test suite handles this automatically
   (see [Knowledge base caching](#knowledge-base-caching) below), but you
   can also trigger a manual sync:
   ```bash
   # From the backend directory, with the Django env active:
   python -m baserow sync_knowledge_base
   ```
   This reads `website_export.csv` (user docs) and `docs/` (dev docs),
   creates `KnowledgeBaseDocument` / `KnowledgeBaseChunk` rows, and
   generates embeddings via the embeddings server.

### Knowledge base caching

Syncing the knowledge base is slow (it generates embeddings for every
documentation chunk). To avoid repeating this on every test run, the eval
suite uses two mechanisms together:

1. **Session-scoped fixture** — the `synced_knowledge_base` fixture in
   `conftest.py` runs once per pytest session. It checks whether the KB is
   already populated (`handler.can_search()`) and only calls
   `sync_knowledge_base()` when it isn't.

2. **`--reuse-db`** — pytest-django's `--reuse-db` flag keeps the test
   database between sessions instead of recreating it. Combined with the
   fixture above, the expensive sync only happens on the very first run.
   Subsequent runs detect that the data is already there and skip the sync
   entirely.

3. **No `transaction=True`** — search docs tests use
   `@pytest.mark.django_db` (savepoint rollback) rather than
   `@pytest.mark.django_db(transaction=True)` (full table truncation). This
   is important: `transaction=True` would wipe the knowledge base tables
   after each test, defeating the caching.

**Typical workflow:**

| Run | What happens | Time |
|-----|--------------|------|
| First ever | DB created, KB synced, tests run | Several minutes |
| Subsequent | DB reused, KB already populated, tests run | Seconds |

To force a fresh sync (e.g. after schema changes or new documentation):

```bash
# Drop and recreate the test DB, then re-sync
just b test ../enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/test_eval_search_user_docs.py \
  -m eval -v -s --create-db
```

### Running search docs evals

```bash
# Only search docs evals
just b test ../enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/test_eval_search_user_docs.py \
  -m eval -v -s

# A single test case by parametrize ID
just b test ../enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/test_eval_search_user_docs.py \
  -m eval -v -s -k "vlookup-to-link-row"
```

If the embeddings server is not running or the knowledge base has not been
synced, all search docs tests will be skipped with a clear message.

## Troubleshooting

### `FAILED — No API key`

Make sure the correct `*_API_KEY` env var is set for your provider/

### Flaky results

LLM evals are inherently non-deterministic. If a test fails intermittently:

- Use `EVAL_RETRIES` to automatically distinguish flakes from consistent bugs:
  ```bash
  EVAL_RETRIES=3 just b test \
    ../enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/test_eval_database_tables.py \
    -m eval -v -s
  ```
  A test that passes on retry is a flake; one that fails all 3 retries is a real problem.
- Check the printed message history (`-s` flag) to see what the agent did.
- If a prompt is ambiguous, tighten the wording in the `PROMPT_*` constant.
- Consider lowering the temperature in the model profile for the eval model.
