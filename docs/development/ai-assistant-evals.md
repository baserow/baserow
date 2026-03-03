# AI Assistant Evals

The assistant eval suite runs the real agent against a live LLM to verify
end-to-end behaviour: tool selection, schema compatibility, row creation, etc.

All eval tests live under
`enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/` and are
marked with `@pytest.mark.eval` so they are **skipped by default** in CI and
local test runs.

## Prerequisites

1. A running PostgreSQL database (see [running-tests.md](running-tests.md)).
2. An API key for the LLM provider you want to test against.
3. **For `test_eval_search_user_docs` only:** an embeddings server and a
   synced knowledge base (see [Search docs evals](#search-docs-evals) below).

## Quick start

```bash
# Set your API key (Groq example — works with any pydantic-ai provider)
export GROQ_API_KEY=gsk_...

# Run all evals with the default model (groq:openai/gpt-oss-120b)
just b test enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/ \
  -m eval -v -s

# Run a single eval file
just b test enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/test_eval_core_builders.py \
  -m eval -v -s
```

> **Tip:** Always pass `-s` so you can see the agent's tool calls and message
> history printed to stdout.

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `EVAL_LLM_MODEL` | `groq:openai/gpt-oss-120b` | Model string in pydantic-ai format (`provider:model`). |
| `EVAL_LLM_MODELS` | *(unset)* | Comma-separated list of models. When set, every eval is parametrized and runs once per model. |
| `GROQ_API_KEY` | — | Required when using a Groq model. |
| `OPENAI_API_KEY` | — | Required when using an OpenAI model. |
| `ANTHROPIC_API_KEY` | — | Required when using an Anthropic model. |

### API keys from a file

The eval conftest loads API keys from two optional locations (first match wins):

1. The file pointed to by `TEST_ENV_FILE` (same resolution as
   `baserow/config/settings/test.py`).
2. `.vscode/env` at the repo root — handy for local development.

Variables already present in `os.environ` are never overwritten.

### Running against multiple models

```bash
export EVAL_LLM_MODELS="groq:openai/gpt-oss-120b,openai:gpt-4o"
just b test enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/ \
  -m eval -v -s
```

Each test will run once per model, with the model name shown in the test ID.

## Test files

File names follow the pattern `test_eval_{module}_{feature}.py`, where module
maps to the tool directory (`core`, `database`, `automation`, `navigation`,
`search_user_docs`).

| File | Module | What it covers |
|------|--------|----------------|
| `test_eval_navigation.py` | navigation | Navigate to tables and workspaces |
| `test_eval_core_builders.py` | core | List/create databases, create automations |
| `test_eval_database_tables.py` | database | Create tables, fields, views, view filters; parametrized across view/filter types |
| `test_eval_database_rows.py` | database | Create rows with all managed field types (text, number, boolean, date, select, link_row, …) |
| `test_eval_database_sample_rows.py` | database | Automatic sample-row generation when creating tables |
| `test_eval_automation_workflows.py` | automation | Create workflows with triggers, actions, routers, and field-value mappings |
| `test_eval_search_user_docs.py` | search_user_docs | Documentation Q&A: source retrieval and answer quality (requires KB) |
| `test_eval_tool_structured_output.py` | *(cross-cutting)* | Schema compatibility: every registered tool produces valid structured output |

Each file defines its prompts as module-level `PROMPT_*` constants at the top,
making it easy to scan which scenarios are covered without reading the test
bodies.

## Writing a new eval

1. Create a new `test_eval_<area>.py` file in the `evals/` directory.
2. Define prompts as `PROMPT_*` constants at the top.
3. Mark each test with `@pytest.mark.eval` and
   `@pytest.mark.django_db(transaction=True)`.
4. Use the helpers from `eval_utils.py`:

```python
import pytest
from .eval_utils import (
    assert_no_tool_errors,
    build_database_ui_context,
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
    assert_no_tool_errors(tracker, result)

    # Add domain-specific assertions here
```

### Key helpers

| Helper | Purpose |
|--------|---------|
| `create_eval_assistant(user, workspace, max_iters, model)` | Returns `(agent, deps, tracker, model, usage_limits, toolset)` configured like production. |
| `build_database_ui_context(user, workspace, database, table)` | Builds the UI context JSON the agent receives. |
| `assert_no_tool_errors(tracker, result)` | Fails if any tool raised an exception or the LLM sent invalid arguments. |
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
   export BASEROW_EMBEDDINGS_API_URL=http://localhost:8090
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
just b test enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/test_eval_search_user_docs.py \
  -m eval -v -s --create-db
```

### Running search docs evals

```bash
# Only search docs evals
just b test enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/test_eval_search_user_docs.py \
  -m eval -v -s

# A single test case by parametrize ID
just b test enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/test_eval_search_user_docs.py \
  -m eval -v -s -k "vlookup-to-link-row"
```

If the embeddings server is not running or the knowledge base has not been
synced, all search docs tests will be skipped with a clear message.

## Troubleshooting

### `FAILED — No API key`

Make sure the correct `*_API_KEY` env var is set for your provider, or
create a `.vscode/env` file at the repo root:

```dotenv
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-...
```

### Flaky results

LLM evals are inherently non-deterministic. If a test fails intermittently:

- Re-run it a couple of times — a single failure doesn't necessarily indicate a
  bug.
- Check the printed message history (`-s` flag) to see what the agent did.
- If a prompt is ambiguous, tighten the wording in the `PROMPT_*` constant.
- Consider lowering the temperature in the model profile for the eval model.
