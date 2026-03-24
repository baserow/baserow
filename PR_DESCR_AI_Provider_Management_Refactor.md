# AI Provider Management Refactor

## Summary

Replaces Baserow's fragmented AI configuration (env vars, workspace JSONField, Builder AIIntegration JSONField, assistant env var) with a unified, hierarchical, DB-backed AI provider management system.

- New admin page at `/admin/ai-providers` (behind `ai-providers` feature flag)
- Unified API at `/api/ai-providers/` with scope query params (instance/workspace/application)
- Per-model test endpoint, feature assignments, override mechanism
- Data migration from all legacy config sources
- Bridge layer for backward compatibility

## Problem

Baserow's AI configuration was fragmented across three disconnected systems:

1. **Generative AI module** — env vars (`BASEROW_OPENAI_API_KEY`, etc.) for instance config + `Workspace.generative_ai_models_settings` JSONField for workspace overrides. Used by AI Field and AI Agent Service.
2. **AI Assistant** — completely separate single env var `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` with pydantic-ai. Doesn't use the generative_ai module at all.
3. **Builder AI Integration** — yet another `AIIntegration.ai_settings` JSONField override layer on top of workspace settings.

This made it impossible to centrally manage which AI providers/models are available, for which features, and at which scope.

---

## Architecture

### Data Model

Five new tables in `baserow.core.ai_provider`:

```
AIProviderConfig              — A configured provider (OpenAI, Anthropic, etc.)
├── provider_type             — "openai", "anthropic", "ollama", etc.
├── name                      — human label ("OpenAI Production")
├── api_key                   — stored server-side, never returned via API
├── extra_settings            — JSONField (organization, base_url, host)
├── scope (GFK)               — NULL=instance, Workspace CT, Application CT
└── models ──→ AIProviderModel
                ├── model_identifier    — "gpt-4o", "claude-sonnet-4-20250514"
                ├── order               — user-defined sort order
                ├── last_test_*         — test status/error/timestamp
                └── features ──→ AIProviderModelFeature
                                 └── feature_type — "ai_field", "ai_assistant", "ai_agent_node"

AIProviderOverride            — Toggle inherited provider on/off at child scope
AIFeatureDefaultModel         — Per-scope default model for features that need one
```

### Scope Hierarchy

```
Instance (scope GFK = NULL)
  └── Workspace (scope GFK → Workspace)
       └── Application (scope GFK → Application)
```

- **Instance-level**: Managed by staff admins. Inherited by all workspaces.
- **Workspace-level**: Managed by workspace admins. Full CRUD. Only visible in that workspace.
- **Application-level**: For Builder AI integrations. Only visible in that application.

At each level, inherited providers from parent scopes are read-only (can only be toggled on/off via `AIProviderOverride`). API keys for parent-level providers are never exposed to lower levels.

### Resolution Logic

When a feature needs to know "which models can I use?":

1. Collect instance-level providers (active + model enabled + feature assigned)
2. Apply overrides at workspace level (remove providers disabled via AIProviderOverride)
3. Add workspace-level providers
4. If scope is application: apply application-level overrides, add application-level providers
5. Return merged list

### Bridge Layer (Backward Compatibility)

`GenerativeAIModelType.get_workspace_setting()` was modified to check AIProviderConfig records first, then fall back to the legacy JSONField and env vars. This means all existing consumers (AI Field, AI Agent Service, etc.) continue working without changes — they call the same `prompt()` / `get_api_key()` / `get_enabled_models()` methods, which now resolve from the new DB-backed system.

Resolution order: `settings_override` → AIProvider (workspace scope) → AIProvider (instance scope) → workspace JSONField (legacy) → env vars (legacy).

### Feature Registry

A new `aiFeature` registry on both backend and frontend:

| Key | Frontend Label | Module |
|-----|---------------|--------|
| `ai_field` | Database - AI field | Premium |
| `ai_assistant` | Kuma AI assistant | Enterprise |
| `ai_agent_node` | Automation - AI agent node | Core |

Each model can be assigned to specific features via checkboxes. Features that need a default model (like the AI Assistant) use `AIFeatureDefaultModel` with the same scope hierarchy.

### Consumer Migration

- **AIField**: new nullable FK `ai_provider_model` added. Data migration backfills from old `ai_generative_ai_type` + `ai_generative_ai_model` string fields by matching against AIProviderModel records.
- **AIAgentService**: same pattern — nullable FK + backfill.
- **AI Assistant**: `get_model_string()` now checks `AIFeatureDefaultModel` for "ai_assistant" at instance scope before falling back to the env var.

### API Security

- API keys are **never returned** from the API. Responses include `has_api_key: true/false` instead.
- In the edit form, API key shows as masked dots with a "Replace" pencil icon. Clicking it enables an empty input with eye toggle.
- Backend validates API key is required for all providers except Ollama.

---

## Frontend

### Admin Page (`/admin/ai-providers`)

Behind the `ai-providers` feature flag (`FEATURE_FLAGS=ai-providers` or `FEATURE_FLAGS=*`).

**Provider list**: Collapsible cards, expanded by default. Each card shows:
- Header: provider name, type badge, model count, edit/delete icons with tooltips
- Model rows (grid layout): model name, feature badges (translated names from registry), test status, Test button

**Create/Edit modal** (shared component `AIProviderFormModal`):
- Provider type dropdown (read-only after create)
- Name (required)
- API key: required for non-Ollama. On edit, shows masked + "Replace" pencil. On replace, eye toggle + cancel.
- Provider-specific fields: Organization, Base URL (placeholder: `https://api.openai.com/v1`), Host (placeholder: `http://localhost:11434`)
- Models section: cards with input, X to remove, FEATURES section (checkboxes on rows, "all / none" links), status footer with test result + Test link
- **Two save buttons**: "Save" (keeps modal open, enables testing) and "Save & close"
- Dirty detection: editing a model name disables its Test link and resets status to "Never tested" until saved

**Delete modal**: Confirmation with warning text. Shows model count and warns that features using the models will stop working.

**Reactivity**: Testing a model inside the modal updates both the modal's local state AND the store (via `aiProvider/testModel` action), so the list behind the modal stays in sync.

### Vuex Store (`aiProvider`)

- `fetchAll({ scope, scopeId })` — loads providers for a scope
- `create/update/delete` — CRUD with store mutations
- `toggleOverride` — optimistic update with rollback
- `testModel` — calls API, updates model in the matching provider item, returns result

### Workspace Settings Page

The existing `GenerativeAIWorkspaceSettings.vue` continues to work via the bridge layer. A future commit will rewrite it to show two sections: inherited (instance) providers with toggle switches, and workspace-owned providers with full CRUD — reusing the same `AIProviderItem` and `AIProviderFormModal` components.

---

## Data Migration (`0115_populate_ai_providers`)

Six migration steps, all idempotent:

1. **Env vars → instance-level providers**: Reads `BASEROW_OPENAI_API_KEY`, `BASEROW_OPENAI_MODELS`, etc. for all 5 provider types. Creates `AIProviderConfig` + `AIProviderModel` records with all features enabled.
2. **Workspace JSONField → workspace-level providers**: Iterates workspaces with non-empty `generative_ai_models_settings`. Creates per-workspace providers.
3. **AIIntegration.ai_settings → application-level providers**: Iterates Builder AI integrations with non-empty settings. Creates per-application providers.
4. **AIField FK backfill**: Matches `ai_generative_ai_type` + `ai_generative_ai_model` string fields to `AIProviderModel` records (workspace scope → instance scope fallback). Sets `ai_provider_model` FK.
5. **AIAgentService FK backfill**: Same pattern for Builder AI agent services (application → workspace → instance fallback).
6. **Assistant default model**: Parses `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` env var (supports `openai/gpt-4o`, `groq:openai/gpt-oss-120b`, `gpt-4o` formats). Creates `AIFeatureDefaultModel` at instance scope.

---

## Test Coverage (45 tests)

### Handler tests (14 tests)
`backend/tests/baserow/core/ai_provider/test_ai_provider_handler.py`
- `test_create_instance_provider` — creates provider at instance scope with models and features
- `test_create_workspace_provider` — creates provider at workspace scope
- `test_get_provider` / `test_get_provider_not_found` — retrieval and 404
- `test_get_provider_model_not_found` — model retrieval 404
- `test_update_provider` — name/api_key update
- `test_update_provider_with_models_data` — model sync preserves existing, adds new, updates features
- `test_delete_provider` — deletion cascades
- `test_list_providers_at_scope` — lists only providers at exact scope
- `test_list_effective_providers` — merges inherited + own providers
- `test_toggle_provider_override` — enable/disable inherited providers at child scope
- `test_get_available_models_for_feature` — feature-filtered model resolution across scopes
- `test_available_models_excludes_disabled_provider` — override disabling hides models
- `test_feature_default_model` — default model resolution with inheritance and override

### API tests (14 tests)
`backend/tests/baserow/api/ai_provider/test_ai_provider_views.py`
- `test_list_instance_providers_unauthenticated` — 401 without token
- `test_list_instance_providers_non_staff` — 403 for non-staff
- `test_list_instance_providers_staff` — returns providers with models/features
- `test_create_instance_provider` — creates with API key validation, returns has_api_key flag
- `test_create_instance_provider_non_staff` — 403 for non-staff
- `test_get_single_provider` / `test_get_nonexistent_provider` — retrieval
- `test_update_provider` — PATCH update
- `test_delete_provider` — DELETE with 204
- `test_list_workspace_effective_providers` — merged list with API key redaction
- `test_toggle_override` — workspace override for inherited provider
- `test_available_models` — feature-filtered model list
- `test_feature_defaults_crud` — GET/PATCH feature default model
- `test_missing_scope_param` — 400 without required scope

### Data migration tests (17 tests)
`backend/tests/baserow/core/ai_provider/test_ai_provider_data_migration.py`

**Env vars → instance providers:**
- `test_env_var_migration_creates_openai_provider` — API key, models, organization
- `test_env_var_migration_creates_ollama_provider` — host-based (no API key)
- `test_env_var_migration_skips_unconfigured_providers` — no env vars = no providers
- `test_env_var_migration_is_idempotent` — running twice creates only one

**Workspace JSONField → workspace providers:**
- `test_workspace_settings_migration` — multi-provider workspace settings
- `test_workspace_settings_migration_is_idempotent` — running twice creates only one
- `test_workspace_settings_migration_skips_empty` — empty settings = no providers
- `test_workspace_settings_migration_multiple_workspaces` — each workspace gets its own

**AIIntegration (Builder) → application providers:**
- `test_ai_integration_migration` — Builder ai_settings to application-level provider
- `test_ai_integration_migration_skips_empty` — empty settings = no providers

**AIField FK backfill:**
- `test_ai_field_fk_backfill` — matches type+model to workspace provider
- `test_ai_field_fk_backfill_skips_already_set` — doesn't overwrite existing FK
- `test_ai_field_fk_backfill_falls_back_to_instance` — uses instance provider when no workspace match

**AIAgentService FK backfill:**
- `test_ai_agent_service_fk_backfill` — matches type+model to workspace provider

**Assistant default model:**
- `test_assistant_default_model_from_env_var` — `openai/gpt-4o` format
- `test_assistant_default_model_groq_format` — `groq:openai/gpt-oss-120b` format
- `test_assistant_default_model_skips_when_no_env_var` — no env var = no default

## Files Changed

### New backend files
- `backend/src/baserow/core/ai_provider/` — models, handler, registries, operations, object_scopes, actions, exceptions, constants
- `backend/src/baserow/api/ai_provider/` — views, serializers, urls, errors
- `backend/src/baserow/core/migrations/0114_ai_provider.py` — schema (5 tables)
- `backend/src/baserow/core/migrations/0115_populate_ai_providers.py` — data migration
- `premium/backend/src/baserow_premium/ai_field_feature_type.py`
- `enterprise/backend/src/baserow_enterprise/ai_assistant_feature_type.py`
- Consumer migrations: `premium/.../0032_aifield_ai_provider_model.py`, `integrations/.../0028_aiagentservice_ai_provider_model.py`

### New frontend files
- `web-frontend/modules/core/pages/admin/aiProviders.vue`
- `web-frontend/modules/core/components/ai/AIProviderItem.vue`
- `web-frontend/modules/core/components/ai/AIProviderFormModal.vue`
- `web-frontend/modules/core/components/ai/AIProviderDeleteModal.vue`
- `web-frontend/modules/core/store/aiProvider.js`
- `web-frontend/modules/core/services/aiProvider.js`
- `web-frontend/modules/core/aiFeatureTypes.js`
- `web-frontend/modules/core/assets/scss/components/ai_provider_admin.scss`

### Modified files
- `backend/src/baserow/core/generative_ai/registries.py` — bridge layer
- `backend/src/baserow/core/apps.py` — register operations, scopes, actions
- `backend/src/baserow/api/urls.py` — add ai-providers URL
- `premium/.../fields/models.py` + `field_types.py` — ai_provider_model FK
- `backend/.../integrations/ai/models.py` — ai_provider_model FK on AIAgentService
- `enterprise/.../assistant/model_profiles.py` — resolve from AIFeatureDefaultModel
- `web-frontend/modules/core/plugin.js` — register store, admin type, feature types
- `web-frontend/modules/core/plugins/featureFlags.js` — FF_AI_PROVIDERS
- `web-frontend/modules/core/adminTypes.js` — AIProvidersAdminType
- `web-frontend/modules/core/locales/en.json` — translations
