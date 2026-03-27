# AI Field Architecture

## Overview

The AI field lets users generate cell values by sending prompts to LLM
providers. The architecture splits into two layers:

- **Core layer** (`baserow.core.generative_ai`) — provider abstraction,
  prompt execution, file handling contract. Provider-agnostic.
- **Premium layer** (`baserow_premium.fields`) — AI field type, handler
  (orchestration), output types, job scheduling.

## Core: GenerativeAIModelType

Each LLM provider (OpenAI, Anthropic, Mistral, Ollama, OpenRouter) is a
`GenerativeAIModelType` subclass registered in
`generative_ai_model_type_registry`. A model type is responsible for:

- **Configuration** — reading API keys and enabled models from workspace
  settings or instance-level env vars (`get_workspace_setting`,
  `get_enabled_models`).
- **Prompting** — `prompt()` is the single entry point for all AI calls.
  It accepts a text prompt, optional multi-modal content, an output type
  (plain text, choice list, or Pydantic model for structured output), and
  returns the result. Internally it builds a pydantic-ai Agent and runs it.
- **File handling** — providers that support file input
  (`supports_files = True`) override `prepare_files()` and `delete_file()`.
  See [File handling](#file-handling) below.

OpenAI-compatible providers (OpenAI, Ollama, OpenRouter) share a common base
(`BaseOpenAIGenerativeAIModelType`) for credential handling and model
instantiation.

### Adding a new provider

Subclass `GenerativeAIModelType`, implement `get_ai_model()` (returns a
pydantic-ai Model), `get_enabled_models()`, `is_enabled()`, and
`get_settings_serializer()`. Register it in the plugin's `ready()` hook.
Override `_prepare_model_settings()` if the provider has quirks (e.g.
Anthropic caps temperature at 1.0). If the provider supports file input,
set `supports_files = True` and override `prepare_files()` and
`delete_file()`.

No frontend changes are needed — the UI reads the available providers and
models from the workspace settings populated by the backend's
`get_enabled_models_per_type()` API and renders them dynamically.

## Premium: AIFieldHandler

`AIFieldHandler` is the single entry point for AI field operations:

- `generate_formula_with_ai()` — generates a Baserow formula from a
  natural-language description (used by the formula AI modal).
- `generate_value_with_ai(ai_field, row)` — generates a single cell value.
  This is the core method that orchestrates the full flow:
  1. Validates the model configuration.
  2. Resolves the prompt formula against the row context.
  3. Collects files from the row's file field (if configured).
  4. Calls `model_type.prepare_files()` then `model_type.prompt()`.
  5. Cleans up uploaded files via `model_type.cleanup_files()`.
  6. Resolves the output (choice matching if applicable).

### Output types

The `AIFieldOutputType` registry defines how AI responses map to cell
values. Current types:

- `TextAIFieldOutputType` — free-form text stored as long text.
- `ChoiceAIFieldOutputType` — the prompt is constrained to a set of select
  options; the model's response is fuzzy-matched to the closest option.

## File handling

File support follows a prepare/cleanup lifecycle using the `AIFile`
dataclass:

1. `AIFieldHandler._collect_ai_files()` builds `AIFile` instances from the
   row's file field. Each `AIFile` has metadata (`name`, `size`,
   `mime_type`) and a lazy `read_content()` method.
2. `model_type.prepare_files(ai_files, workspace)` decides which files to
   accept. It reads content only for accepted files, sets `ai_file.content`
   (the pydantic-ai content part), and optionally `ai_file.provider_file_id`
   if the file was uploaded to the provider. Returns only processed files.
3. After the prompt call, `model_type.cleanup_files(prepared, workspace)`
   deletes any provider-uploaded files.

Currently only OpenAI supports files. It embeds images as binary content
and uploads documents to the OpenAI Files API.

## Job scheduling

Bulk generation (entire table, filtered view, or specific rows) runs as an
async job (`GenerateAIValuesJobType`). The job uses `AIValueGenerator`
which processes rows in a thread pool, calling
`AIFieldHandler.generate_value_with_ai()` per row.

When auto-update is enabled, changes to fields referenced in the prompt
create `AIFieldScheduledUpdate` records and schedule a per-field singleton
Celery task. The task runs synchronously (holding a lock), then checks if
new updates arrived while it was running — if so, it reschedules itself.
