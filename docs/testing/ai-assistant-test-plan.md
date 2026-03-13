# PR Test Plan: Port AI Assistant to pydantic-ai

## Context

This PR replaces `udspy` with `pydantic-ai` as the agent framework for the
Baserow AI assistant. It touches the entire assistant stack: deps, agents,
tools, telemetry, history, streaming, and tests. The PR also adds an LLM eval
suite.

---

## How to test

### 1. Automated tests (unit)

Run the existing unit test suite (uses `TestModel`/`FunctionModel`, no LLM
needed):

```bash
just b test ../enterprise/backend/tests/baserow_enterprise_tests/assistant/ \
  -v --ignore=enterprise/backend/tests/baserow_enterprise_tests/assistant/evals
```

All tests must pass. These cover: assistant orchestrator, all tool modules,
telemetry event emission, history compaction, and streaming.

### 2. Automated tests (evals, optional)

Run the eval suite against a live LLM. Requires an API key:

```bash
export GROQ_API_KEY=gsk_...
just b test ../enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/ \
  -m eval -v -s
```

See [ai-assistant-evals.md](ai-assistant-evals.md) for configuration details
(multi-model, env file, etc).

### 3. Manual: Tool smoke tests

Open the assistant in the UI and verify each tool works end-to-end. Suggested
prompts:

| Tool | Prompt |
|------|--------|
| `navigate` | "Go to the Customers table" |
| `list_builders` | "What applications do I have?" |
| `create_builders` | "Create a new application called Test App" |
| `list_tables` | "What tables are in my database?" |
| `get_tables_schema` | "Show me the schema of the Customers table" |
| `list_rows` | "Show me the first rows of the Customers table" |
| `list_views` | "What views does the Customers table have?" |
| `create_tables` | "Create a table called Projects with columns: Name (text), Status (single select: Active/Done), Due date (date)" |
| `create_fields` | "Add an email field to the Customers table" |
| `create_views` | "Create a kanban view grouped by Status on the Projects table" |
| `create_view_filters` | "Add a filter on the Projects grid view to only show Active rows" |
| `generate_formula` | "Add a formula field that concatenates first name and last name" |
| `update_fields` | "Rename the email field to Contact Email in the Customers table" |
| `delete_fields` | "Delete the Contact Email field from the Customers table" |
| `load_row_tools` | "Add a row to the Projects table: Name=Launch, Status=Active" (this implicitly triggers load_row_tools first) |
| `update_rows_in_table_X` | "Change the Status of the Launch row in Projects to Done" |
| `delete_rows_in_table_X` | "Delete the Launch row from the Projects table" |
| `switch_mode` | "Switch to automation mode" |
| `list_workflows` | "What automations do I have?" |
| `create_workflows` | "Create an automation that sends a notification when a row is created in Projects" |
| `list_nodes` | "What nodes are in my first workflow?" |
| `add_nodes` | "Add a Slack notification action after the trigger in my workflow" |
| `update_nodes` | "Rename the trigger node to New Project Trigger" |
| `delete_nodes` | "Delete the Slack notification node from my workflow" |
| `search_user_docs` | "How do I create a lookup field?" |

### 4. Manual: Feedback

- Send a message, then click the thumbs-up/thumbs-down on the response
- Verify the feedback is recorded (no errors in the console/network tab)
- Refresh the page, the previously selected thumb up/down button must be highlighted

### 5. Manual: Conversation memory (history)

Test that the agent retains multi-turn context:

1. Send: "My name is Mario"
2. Agent responds acknowledging
3. Send: "What's my name?"
4. Agent should respond "Mario" (proves history serialization/deserialization
   via `message_history` field works)

Also test a longer conversation (3+ turns) to verify the compaction doesn't
lose essential context.

### 6. Manual: Telemetry / PostHog traces

Requires PostHog configured (`POSTHOG_API_KEY`, `POSTHOG_HOST` etc.):

1. Send a few messages exercising different tools
2. Go to PostHog > LLM Analytics > Traces
3. Verify:
   - Each conversation turn appears as a `$ai_trace`
   - Tool calls appear as `$ai_span` children
   - LLM generations appear as `$ai_generation` with model name, token counts,
     latency
   - Input/output content is captured (not empty)

### 7. Manual: Knowledge base (search_user_docs)

Requires an embeddings server and synced KB. Verify:

- Ask a Baserow how-to question (e.g. "How do I set up SSO?") -> agent should
  call `search_user_docs` and cite sources
- Ask a creative task (e.g. "Create a table for tracking expenses") -> agent
  should NOT call search_user_docs, should just act
- Ask a question about the agent's own tools (e.g. "What tools do you have?")
  -> agent should NOT search docs, should answer from its own knowledge

### 8. Manual: Do vs. Describe

Verify the agent acts rather than describes:

- "Create a table called Invoices" -> should actually create it (call
  `create_tables`), not describe how to do it
- "How would I create a table?" -> should describe the manual UI steps (no
  tools available for this meta-question) or search docs
- After creating something, the agent should navigate to it to show the result

### 9. Manual: Cancellation

1. Send a long-running request (e.g. "Create a table with 10 fields")
2. Click cancel mid-execution
3. Verify the stream stops cleanly without error toasts

### 10. Manual: Error handling

- Misconfigure the LLM API key and try to chat -> should show a clear error,
  not a stack trace
- Send a prompt referencing a non-existent table/database -> agent should
  handle gracefully
