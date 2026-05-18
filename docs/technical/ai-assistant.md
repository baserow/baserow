# AI assistant

Kuma, the enterprise AI assistant, is a server-side pydantic-ai agent whose
mutating tools call Baserow `ActionType`s. For setup, provider env vars, and
troubleshooting, see [AI assistant setup](../installation/ai-assistant.md).

> **Enterprise feature.** Code lives under
> `enterprise/backend/src/baserow_enterprise/assistant/` and
> `enterprise/web-frontend/modules/baserow_enterprise/components/assistant/`.

## Core Design

The key choice: assistant tools are wrappers around Baserow actions.

That gives us:

- **Permissions in the normal place.** `ActionType.do(...)` reaches handlers
  that call `CoreHandler.check_permissions(...)`.
- **Audit and future undo.** Assistant mutations write normal action rows and
  share an `action_group_id` per turn.
- **No REST round trip inside the backend.** Tools work with handlers, ORM
  objects, and action types directly.

Read [Action system](action-system.md) before changing mutating tools.

## Agent Runtime

`assistant/agents.py` defines:

- `main_agent`: handles user messages.
- `title_agent`: creates a chat title from the first message.

The system prompt lives in `assistant/prompts.py`. Dynamic instructions inject
request context such as UI state, mode, license tier, original task, and the
tool manifest.

Conversation state is stored in:

- `AssistantChat`: chat metadata, status, workspace/user scope, and compacted
  pydantic-ai message history.
- `AssistantChatMessage`: visible human/AI messages, artifacts, and
  `action_group_id`.
- `AssistantChatPrediction`: feedback/eval link between prompt and response.

Long chats are compacted before the next turn so large tool outputs do not
consume the whole model context.

## Tools

Tools live under `assistant/tools/`, grouped by mode. Read-only tools may use
handlers or ORM queries. Mutating tools must call an existing or new
`ActionType.do(...)`; calling handlers directly skips audit and undo grouping.

Adding a tool:

1. Subclass `AssistantToolType`.
2. Implement `can_use(user, workspace)` for license/permission visibility.
3. Implement the function. Use an action for mutations.
4. Register in `apps.py`.
5. Add backend unit tests.
6. Add or update eval scenarios when prompt/tool semantics change.

Keep tool schemas small. Too many available tools makes model choice worse.

## Modes

`AgentMode` controls which tools are available:

- `database`
- `application`
- `automation`
- `explain` (read-only)

`ModeAwareToolset` filters tools for the current turn. `switch_mode` lets the
agent move when the user's request changes domain.

## Streaming and Cancellation

The chat endpoint returns **Server-Sent Events**, not websocket messages.
`AssistantChatView.post` streams events from `Assistant.astream_messages(...)`
while the model runs.

Important event types:

- `AiStartedMessage`
- `AiReasoningChunk`
- `AiMessageChunk`
- `AiThinkingMessage`
- `ChatTitleMessage`
- `AiErrorMessage`
- `AiCancelledMessage`

Cancellation is cache-polled: the API sets a Redis key, the running assistant
checks it, and tool helpers raise cancellation into running work.

## Permissions

There are two gates:

1. Tool visibility: `AssistantToolType.can_use(user, workspace)`.
2. Operation enforcement: the action/handler permission check.

The assistant inherits the user's scope. There is no separate list of tables or
resources the assistant can touch.

## Knowledge Base

RAG is optional and enabled by `BASEROW_EMBEDDINGS_API_URL`. Documents are split
into chunks, embedded, stored with pgvector, and queried by the
`search_user_docs` tool. If embeddings are not configured, the tool is hidden.

See [Embeddings server](../development/embeddings-server.md).

## Provider Abstraction

Model and provider selection are environment-driven through pydantic-ai. The
assistant wraps the selected model with:

- `RetryingModel`: retries transient provider errors and turns streaming errors
  into recoverable events.
- `InlineRefsToolset`: inlines JSON Schema refs for models that do not handle
  `$ref` well.

Provider env vars belong in the setup guide, not here.

## Frontend

The enterprise frontend assistant components handle the panel, message list,
input, sources, feedback, and chat history. The store action opens the SSE
stream and applies each event to state. Routing and layout are otherwise
ordinary Vue/Nuxt.

## Tests and Evals

- Unit tests:
  `enterprise/backend/tests/baserow_enterprise_tests/assistant/`.
- Evals:
  `enterprise/backend/tests/baserow_enterprise_tests/assistant/evals/`.

Evals hit real LLM providers and are not part of normal CI. Run them deliberately
after changing prompts, tools, provider routing, or mode selection.

## Direction

Tools are increasingly shared between the in-app assistant and external MCP
clients. New tools should avoid assistant-specific runtime state unless needed.
See [MCP server](../development/mcp-server.md).

## Related

- [AI assistant setup](../installation/ai-assistant.md).
- [AI assistant evals](../testing/ai-assistant-evals.md).
- [AI assistant test plan](../testing/ai-assistant-test-plan.md).
- [Action system](action-system.md).
- [MCP server](../development/mcp-server.md).
