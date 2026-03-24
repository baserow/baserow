# PRD: AI Provider Management Refactor

## Context

Baserow's current AI configuration is fragmented across three disconnected systems:
1. **Generative AI module** (`core/generative_ai/`): env vars for instance config, JSONField on Workspace for workspace config, used by AI Field and AI Agent Service
2. **AI Assistant** (`enterprise/assistant/`): completely separate — single env var `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` with `udspy.LM`, doesn't use the generative_ai module at all
3. **Builder AI Integration** (`contrib/integrations/ai/`): yet another JSONField override layer on top of workspace settings

This makes it impossible to centrally manage which AI providers/models are available, where, and for which features. Adding a new AI feature means wiring up yet another ad-hoc configuration path.

**Goal**: Replace all three with a unified, hierarchical, DB-backed AI provider management system with a feature registry that controls which models are available for which AI capabilities.

---

## Data Model

### Core Tables (new)

```
AIProviderConfig
├── id (BigAutoField)
├── provider_type (CharField) — registry key: "openai", "anthropic", "mistral", "ollama", "openrouter"
├── name (CharField) — human-readable label, e.g. "OpenAI Premium", "Ollama Local"
├── api_key (CharField, blank=True) — api keys.
├── extra_settings (JSONField) — provider-specific: organization, base_url, host, etc.
├── scope_content_type (FK → ContentType) — polymorphic scope: NULL=instance, Workspace, Application
├── scope_object_id (PositiveIntegerField, nullable)
├── created_by (FK → User, nullable)
├── created_on / updated_on
└── is_active (BooleanField, default=True)

AIProviderModel
├── id (BigAutoField)
├── provider_config (FK → AIProviderConfig, on_delete=CASCADE)
├── model_identifier (CharField) — e.g. "gpt-4o", "claude-3-opus-20240229"
├── display_name (CharField, blank=True) — optional human-friendly name
├── is_enabled (BooleanField, default=True)
├── last_test_at (DateTimeField, nullable) — when the last test call was made
├── last_test_status (CharField, nullable) — "success" | "failure" | null (never tested)
└── last_test_error (TextField, blank=True) — error message if last test failed

AIProviderModelFeature (M2M through table)
├── id (BigAutoField)
├── provider_model (FK → AIProviderModel, on_delete=CASCADE)
└── feature_type (CharField) — registry key: "ai_field", "ai_assistant", "ai_prompt_node"

AIProviderOverride (toggle inherited providers at any child scope)
├── id (BigAutoField)
├── provider_config (FK → AIProviderConfig, on_delete=CASCADE) — the inherited provider being overridden
├── scope_content_type (FK → ContentType) — the scope doing the overriding (Workspace, Application)
├── scope_object_id (PositiveIntegerField)
├── is_enabled (BooleanField, default=True)
└── unique_together: (provider_config, scope_content_type, scope_object_id)

AIFeatureDefaultModel (per-scope default model for features that need one)
├── id (BigAutoField)
├── feature_type (CharField) — registry key: "ai_assistant", etc.
├── provider_model (FK → AIProviderModel, on_delete=CASCADE)
├── scope_content_type (FK → ContentType, nullable) — same scope pattern as AIProviderConfig
├── scope_object_id (PositiveIntegerField, nullable)
└── unique_together: (feature_type, scope_content_type, scope_object_id)
```

The `AIFeatureDefaultModel` allows features like the AI Assistant to have a configured "default model" at each scope level. Resolution: application default → workspace default → instance default. Features like AI Field don't need this — they let users pick per-field.

### Scope Hierarchy

```
Instance (scope_content_type=NULL, scope_object_id=NULL)
  └── Workspace (scope_content_type=Workspace CT, scope_object_id=workspace.id)
       └── Application (scope_content_type=Application CT, scope_object_id=application.id)
```

- **Instance-level**: Managed by staff/admin. Available in all workspaces (unless overridden).
- **Workspace-level**: Managed by workspace admins. Full CRUD. Only visible in that workspace.
- **Application-level**: Managed by application editors. Full CRUD. Only visible in that application.

At each level, inherited providers from parent levels are **read-only** (can only be toggled on/off at workspace level via `AIProviderOverride`). API keys for parent-level providers are **never exposed** to lower levels.

---

## Feature Registry

New registry in `baserow.core.generative_ai.feature_registry`:

```python
class AIFeatureType(Instance):
    """Base class for AI features that can use AI providers."""
    # type: str — unique key, e.g. "ai_field"
    # name: str — human-readable, e.g. "AI Field"
    # description: str
    # icon: str — for frontend

class AIFeatureTypeRegistry(Registry):
    name = "ai_feature"
```

Registered features (initially):
| Key | Name | Module | License |
|-----|------|--------|---------|
| `ai_field` | AI Field | `baserow_premium` | Premium |
| `ai_assistant` | AI Assistant | `baserow_enterprise` | Enterprise |
| `ai_prompt_node` | AI Prompt Node | `contrib.automation` | Core |

Each feature registers itself in its module's `apps.py` `ready()` — same pattern as field types, auth providers, etc.

---

## API Endpoints

Single base path with scope as a query/path parameter. Permissions are validated based on the scope:

```
/api/ai-providers/?scope=instance                          → staff only
/api/ai-providers/?scope=workspace&scope_id={workspace_id}  → workspace admin
/api/ai-providers/?scope=application&scope_id={app_id}      → application editor
```

### Provider CRUD
- `GET /api/ai-providers/?scope=...&scope_id=...` — list providers at this scope + inherited from parent scopes (parent providers marked `read_only: true`, API keys redacted for inherited)
- `POST /api/ai-providers/?scope=...&scope_id=...` — create provider at this scope
- `PATCH /api/ai-providers/{id}/?scope=...&scope_id=...` — update provider. If the provider belongs to the caller's scope: full update. If it belongs to a parent scope (e.g. instance provider patched at workspace level): only `is_enabled` is writable (creates/updates `AIProviderOverride` under the hood). All other fields are rejected.
- `DELETE /api/ai-providers/{id}/` — delete provider (only if owned by caller's scope)
- `POST /api/ai-providers/models/{model_id}/test/` — test a specific model (sends a minimal prompt using the parent provider's API key, updates `last_test_at/status/error` on `AIProviderModel`)

### Available models (for consumers like AI Field, AI Agent, etc.)
- `GET /api/ai-providers/models/?feature={feature_type}&scope=...&scope_id=...` — returns the resolved list of models available for a given feature at a given scope. This is what the AI Field dropdown, AI Agent model selector, etc. call.

### Feature default model (for features like AI Assistant that need a default)
- `GET /api/ai-providers/feature-defaults/?scope=...&scope_id=...` — get default model for each feature at this scope
- `PATCH /api/ai-providers/feature-defaults/?scope=...&scope_id=...` — set default model for a feature (body: `{feature_type: "ai_assistant", provider_model_id: 123}`)

---

## Resolution Logic

When a feature needs to know "which models can I use?":

```python
def get_available_models_for_feature(feature_type: str, scope_type: str, scope_id: int) -> list[AIProviderModel]:
    """
    Returns all enabled models for a given feature, resolving the hierarchy:
    1. Collect instance-level providers (active + model enabled + feature assigned)
    2. Apply overrides at each scope level (remove providers disabled via AIProviderOverride)
    3. Add workspace-level providers (active + model enabled + feature assigned)
    4. If scope is application: apply application-level overrides, add application-level providers
    5. Return merged list
    """
```

When a feature needs to **execute** an AI call, it looks up the `AIProviderConfig` for the selected model, gets the API key + settings, and delegates to the existing `GenerativeAIModelType.prompt()`.

## Data Migration

### 1. Env vars → Instance-level `AIProviderConfig`

On startup (management command or `AppConfig.ready()`):
1. Read all `BASEROW_*_API_KEY`, `BASEROW_*_MODELS`, etc. env vars
2. Read `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` env var (e.g. `openai/gpt-4o`)
3. For each configured provider, check if a matching instance-level `AIProviderConfig` already exists (match on `provider_type` + instance scope)
4. If not, create `AIProviderConfig` + `AIProviderModel` records with all features enabled (preserving current behavior)
5. For the assistant model env var: parse `provider/model`, find or create the matching model, set as `AIFeatureDefaultModel` for `ai_assistant` at instance scope
6. Log deprecation warnings for all env vars found
7. Env vars serve as seed-only — once in DB, admin UI is the source of truth

**Env vars to migrate:**
- `BASEROW_OPENAI_API_KEY`, `BASEROW_OPENAI_MODELS`, `BASEROW_OPENAI_ORGANIZATION`, `BASEROW_OPENAI_BASE_URL`
- `BASEROW_ANTHROPIC_API_KEY`, `BASEROW_ANTHROPIC_MODELS`
- `BASEROW_MISTRAL_API_KEY`, `BASEROW_MISTRAL_MODELS`
- `BASEROW_OLLAMA_HOST`, `BASEROW_OLLAMA_MODELS`
- `BASEROW_OPENROUTER_API_KEY`, `BASEROW_OPENROUTER_MODELS`, `BASEROW_OPENROUTER_ORGANIZATION`
- `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL`, `BASEROW_ENTERPRISE_ASSISTANT_LLM_TEMPERATURE`

### 2. Workspace JSONField → Workspace-level `AIProviderConfig`

Django data migration over `Workspace.generative_ai_models_settings`:

```python
# For each workspace with non-empty generative_ai_models_settings:
#   settings = {"openai": {"api_key": "sk-...", "models": ["gpt-4o", "gpt-4o-mini"], "organization": "org-..."}, ...}
#   For each provider_type, settings_dict in settings.items():
#     1. Create AIProviderConfig(provider_type=provider_type, name=f"{ProviderName}", api_key=..., scope=workspace, extra_settings={org, base_url, host})
#     2. For each model_id in settings_dict["models"]:
#        Create AIProviderModel(provider_config=config, model_identifier=model_id)
#        Create AIProviderModelFeature for all features (preserve current "everything enabled" behavior)
```

### 3. AIIntegration → Application-level `AIProviderConfig`

Django data migration over `AIIntegration.ai_settings`:

```python
# For each AIIntegration with non-empty ai_settings:
#   application = integration.application
#   For each provider_type, settings_dict in ai_settings.items():
#     Same pattern as workspace migration but scope=application
#     Only create if settings_dict actually overrides (has api_key or models)
```

### 4. AIField + AIAgentService → FK to `AIProviderModel`

Add a nullable FK `ai_provider_model = ForeignKey(AIProviderModel, null=True, on_delete=SET_NULL)` to both `AIField` and `AIAgentService`.

Django data migration:

```python
# For each AIField with ai_generative_ai_type and ai_generative_ai_model set:
#   1. Find the AIProviderModel that matches (provider_config.provider_type == ai_generative_ai_type,
#      model_identifier == ai_generative_ai_model) within the field's workspace scope
#      (resolve hierarchy: check workspace providers first, then instance)
#   2. Set ai_provider_model = matched_model
#
# Same for AIAgentService, resolving within the service's integration's application scope
```

Keep the old `ai_generative_ai_type` and `ai_generative_ai_model` CharFields as deprecated (read-only) for one release cycle as fallback. New code reads from `ai_provider_model` FK; if null, falls back to old string fields during transition.

### 5. Deprecation schedule

**Immediately deprecated (still functional during transition):**
- `Workspace.generative_ai_models_settings` JSONField
- `AIIntegration` model + `ai_settings` JSONField
- `AIField.ai_generative_ai_type` / `ai_generative_ai_model` CharFields
- `AIAgentService.ai_generative_ai_type` / `ai_generative_ai_model` CharFields
- All `BASEROW_*_API_KEY`, `BASEROW_*_MODELS` env vars
- `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` env var
- Old workspace settings API endpoints (`/api/workspaces/{id}/generative-ai-models-settings/`)

**Removed in next major version:**
- All of the above
- Old `GenerativeAIModelType.get_workspace_setting()`, `get_enabled_models()`, `get_api_key()` methods
- `backend/src/baserow/api/generative_ai/serializers.py` old settings serializers

---

## UI Design

### Instance Admin Settings Page (`/admin/ai-providers`)

Similar to the Auth Providers page. Each provider is a collapsible card with a model sub-table:

#### Provider List (read view)

```
┌─────────────────────────────────────────────────────────────────┐
│ AI Providers                                    [Add provider]   │
│                                                 ┌─────────────┐ │
│                                                 │ OpenAI      │ │
│                                                 │ Anthropic   │ │
│                                                 │ Mistral     │ │
│                                                 │ Ollama      │ │
│                                                 │ OpenRouter  │ │
│                                                 └─────────────┘ │
│                                                                  │
│ ▼ OpenAI Premium                               [Edit] [Delete]  │
│   OpenAI · 2 models                                              │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ MODEL          FEATURES                 USAGE      STATUS   │ │
│ │ ───────────── ──────────────────────── ────────── ──────── │ │
│ │ gpt-4o        AI Field · AI Assistant  Used (4)   ✅ 2h ago │ │
│ │               AI Prompt Node                      [Test]   │ │
│ │ ───────────── ──────────────────────── ────────── ──────── │ │
│ │ gpt-4o-mini   AI Field · AI Prompt    Used (1)   ❌ 1d ago │ │
│ │               Node                                [Test]   │ │
│ │                                        "model not found"   │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ ▼ Anthropic                                    [Edit] [Delete]  │
│   Anthropic · 1 model                                            │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ MODEL          FEATURES                 USAGE      STATUS   │ │
│ │ ───────────── ──────────────────────── ────────── ──────── │ │
│ │ claude-sonnet  AI Assistant             Used (1)   ⚪ —     │ │
│ │ -4-20250514                                        [Test]   │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ ▶ Ollama Local (collapsed)                     [Edit] [Delete]  │
│   Ollama · 1 model                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Provider card** (header row):
- Collapse/expand toggle (▼/▶)
- Provider name + provider type label + model count
- [Edit] and [Delete] buttons

**Model sub-table** (expanded, per provider):
- **Model**: identifier (e.g. `gpt-4o`)
- **Features**: badges/tags showing which features this model is enabled for
- **Usage**: "Used (N)" with total reference count, or "—" if unused
- **Status**: test result icon + relative time
  - ✅ passed (2h ago)
  - ❌ failed + error message (1d ago)
  - ⚪ never tested
- **[Test]** button: click → spinner → updates status inline

#### Edit Form (modal or inline, triggered by [Edit] on provider)

```
┌──────────────────────────────────────────────────────────────┐
│ Edit: OpenAI Premium                                    [✕]  │
├──────────────────────────────────────────────────────────────┤
│ Provider type:  OpenAI (read-only)                           │
│ Name:           [OpenAI Premium          ]                   │
│ API key:        [••••••••••••sk-abc      ]                   │
│ Organization:   [org-xxxxx               ]                   │
│ Base URL:       [                        ] (optional)        │
├──────────────────────────────────────────────────────────────┤
│ Models                                                       │
│ ┌──────────────────────────────────────────────────────────┐ │
│ │  Model ID         AI Field  Assistant  Prompt Node   ⊘   │ │
│ │  ──────────────── ──────── ────────── ──────────── ───── │ │
│ │  [gpt-4o        ] [☑]      [☑]        [☑]          [🗑]  │ │
│ │  [gpt-4o-mini   ] [☑]      [☐]        [☑]          [🗑]  │ │
│ │                                                          │ │
│ │  [+ Add model]                                           │ │
│ └──────────────────────────────────────────────────────────┘ │
│                                                              │
│                              [Cancel]  [Save]                │
└──────────────────────────────────────────────────────────────┘
```

The models inline table (Django TabularInline style):
- One row per model with editable model identifier
- One checkbox column per registered feature type (columns are dynamic — driven by the feature registry)
- Delete (🗑) button per row
- [+ Add model] button at bottom to add a new row
- Feature checkbox columns are driven by the frontend feature registry (mirroring the backend one) — no API call needed, no hardcoded feature list

### Feature Defaults Section

Shown below the provider list on both Instance and Workspace pages. Only features with `requires_default_model = True` appear here.

#### Instance level

```
┌─────────────────────────────────────────────────────────────────┐
│ Feature Defaults                                                 │
│                                                                  │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ FEATURE          DEFAULT MODEL                     STATUS   │ │
│ │ ──────────────── ───────────────────────────────── ──────── │ │
│ │ AI Assistant     [OpenAI Premium / gpt-4o      ▼]  ✅ 2h ago│ │
│ │                                                              │ │
│ │ (future features with requires_default_model appear here)    │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ The dropdown lists all models that have the corresponding        │
│ feature enabled. Grouped by provider name:                       │
│                                                                  │
│   ┌──────────────────────────────┐                               │
│   │ OpenAI Premium               │                               │
│   │   gpt-4o               ✅    │                               │
│   │   gpt-4o-mini          ❌    │                               │
│   │ Anthropic                    │                               │
│   │   claude-sonnet-4  ⚪    │                               │
│   └──────────────────────────────┘                               │
│                                                                  │
│ Each option shows the model's last test status icon so admins    │
│ can pick a model they know works.                                │
└─────────────────────────────────────────────────────────────────┘
```

#### Workspace level

```
┌─────────────────────────────────────────────────────────────────┐
│ Feature Defaults                                                 │
│                                                                  │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ FEATURE          DEFAULT MODEL                     SOURCE   │ │
│ │ ──────────────── ───────────────────────────────── ──────── │ │
│ │ AI Assistant     [OpenAI Premium / gpt-4o      ▼]  Instance │ │
│ │                  Inherited from instance.                    │ │
│ │                  Select a different model to override.       │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ After overriding:                                                │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ FEATURE          DEFAULT MODEL                     SOURCE   │ │
│ │ ──────────────── ───────────────────────────────── ──────── │ │
│ │ AI Assistant     [My Ollama / llama3            ▼]  Work-   │ │
│ │                  Overrides instance default.     space      │ │
│ │                  [Reset to instance default]                 │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ The dropdown includes models from both instance providers        │
│ (non-disabled) and workspace providers. The "Source" column      │
│ shows whether the current value is inherited or overridden.      │
│ [Reset to instance default] removes the workspace override.      │
└─────────────────────────────────────────────────────────────────┘
```

Key behaviors:
- Dropdown is grouped by provider name, each model shows its test status icon
- Only models with the corresponding feature enabled appear in the dropdown
- At workspace level, shows "Inherited from instance" when no workspace override exists
- Changing the dropdown at workspace level creates a workspace-scoped `AIFeatureDefaultModel`
- [Reset to instance default] button deletes the workspace override, reverting to inherited
- Application level follows the same pattern (inherits from workspace, can override)

### Workspace Settings Page

Same layout with two sections — inherited (read-only) and workspace-owned (editable):

```
┌─────────────────────────────────────────────────────────────────┐
│ AI Providers                                    [Add provider]   │
│                                                                  │
│ ── Instance providers (managed by admin) ──────────────────────  │
│                                                                  │
│ ▼ OpenAI Premium                                      [toggle]  │
│   OpenAI · 2 models · Configured by admin                        │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ MODEL          FEATURES                 USAGE      STATUS   │ │
│ │ ───────────── ──────────────────────── ────────── ──────── │ │
│ │ gpt-4o        AI Field · AI Assistant  Used (4)   ✅ 2h ago │ │
│ │               AI Prompt Node                      [Test]   │ │
│ │ ───────────── ──────────────────────── ────────── ──────── │ │
│ │ gpt-4o-mini   AI Field · AI Prompt    —           ✅ 2h ago │ │
│ │               Node                                [Test]   │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
│ ── Workspace providers ────────────────────────────────────────  │
│                                                                  │
│ ▼ My Custom Ollama                             [Edit] [Delete]  │
│   Ollama · 1 model                                               │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ MODEL          FEATURES                 USAGE      STATUS   │ │
│ │ ───────────── ──────────────────────── ────────── ──────── │ │
│ │ llama3         AI Field                —           ⚪ —     │ │
│ │                                                    [Test]   │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

Key differences from instance page:
- Instance providers show "Configured by admin" — no API key visible, no [Edit]
- Instance providers have a toggle switch instead (enable/disable for this workspace)
- Disabled instance providers are hidden from the list (fully hidden per spec)
- Workspace providers have full [Edit] [Delete] controls
- [Add provider] creates workspace-scoped providers only
- [Test] works on all models regardless of scope (uses the provider's own credentials server-side)

### Application Settings

Same two-section pattern — inherited (instance + workspace) providers are read-only, application-scoped providers are fully editable. Feature Defaults section if applicable.

---

## Migration Plan

### Phase 1: Core Infrastructure
1. Create new DB models (`AIProviderConfig`, `AIProviderModel`, `AIProviderModelFeature`, `AIProviderOverride`, `AIFeatureDefaultModel`)
2. Add nullable FK `ai_provider_model` to `AIField` and `AIAgentService`
3. Implement the `AIFeatureTypeRegistry` in core
4. Create the handler (`AIProviderHandler`) with CRUD + resolution logic + usage tracking
5. Create API endpoints + serializers
6. Audit log action types
7. Add feature flag

### Phase 2: Data Migration
1. Env var seeding logic (instance-level providers, management command)
2. Django data migration: `Workspace.generative_ai_models_settings` → workspace-level `AIProviderConfig` + `AIProviderModel`
3. Django data migration: `AIIntegration.ai_settings` → application-level `AIProviderConfig` + `AIProviderModel`
4. Django data migration: `AIField.ai_generative_ai_type/model` → `AIField.ai_provider_model` FK
5. Django data migration: `AIAgentService.ai_generative_ai_type/model` → `AIAgentService.ai_provider_model` FK
6. Django data migration: `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` → `AIFeatureDefaultModel`

### Phase 3: Feature Registration + Consumer Migration
1. Register `ai_field`, `ai_assistant`, `ai_prompt_node` features
2. Refactor AI Field to read from `ai_provider_model` FK (fallback to old string fields during transition)
3. Refactor AI Agent Service to read from `ai_provider_model` FK
4. Refactor AI Assistant to resolve via `AIFeatureDefaultModel` instead of env var
5. Refactor Builder AI Integration to use application-level scope

### Phase 4: Frontend
1. Instance admin page (new page in admin section)
2. Workspace AI settings page (replace existing `GenerativeAIWorkspaceSettings.vue`)
3. Application-level AI settings (new, for automation initially)
4. Update model selectors in AI Field, AI Agent, AI Assistant to use new API
5. Remove feature flag

### Phase 5: Deprecation & Cleanup
1. Deprecation warnings for all env vars
2. Remove `Workspace.generative_ai_models_settings` JSONField
3. Remove `AIIntegration` model and integration type
4. Remove env var reading from `GenerativeAIModelType` subclasses
5. Remove old API endpoints

---

## Key Files to Modify

### New files
- `backend/src/baserow/core/ai_providers/models.py`
- `backend/src/baserow/core/ai_providers/handler.py`
- `backend/src/baserow/core/ai_providers/registries.py` (AIFeatureTypeRegistry)
- `backend/src/baserow/core/ai_providers/exceptions.py`
- `backend/src/baserow/core/ai_providers/operations.py`
- `backend/src/baserow/api/ai_providers/views.py`
- `backend/src/baserow/api/ai_providers/serializers.py`
- `backend/src/baserow/api/ai_providers/urls.py`
- `web-frontend/modules/core/pages/admin/aiProviders.vue`
- `web-frontend/modules/core/components/ai/AIProviderItem.vue`
- `web-frontend/modules/core/components/ai/AIProviderForm.vue`
- `web-frontend/modules/core/services/aiProviderAdmin.js`
- `web-frontend/modules/core/store/aiProvider.js`

### Modified files
- `backend/src/baserow/core/apps.py` — register AI feature types
- `premium/backend/src/baserow_premium/apps.py` — register `ai_field` feature
- `enterprise/backend/src/baserow_enterprise/apps.py` — register `ai_assistant` feature
- `backend/src/baserow/contrib/automation/apps.py` — register `ai_prompt_node` feature
- `premium/backend/src/baserow_premium/fields/models.py` — add `ai_provider_model` FK (nullable), deprecate string fields
- `premium/backend/src/baserow_premium/fields/field_types.py` — use new resolution API + FK
- `backend/src/baserow/contrib/integrations/ai/models.py` — add `ai_provider_model` FK to `AIAgentService` (nullable)
- `backend/src/baserow/contrib/integrations/ai/service_types.py` — use new resolution API + FK
- `enterprise/backend/src/baserow_enterprise/assistant/assistant.py` — use new resolution API via `AIFeatureDefaultModel`
- `web-frontend/modules/core/components/ai/SelectAIModelForm.vue` — fetch from new API
- `web-frontend/modules/core/components/workspace/GenerativeAIWorkspaceSettings.vue` — rewrite

### Eventually removed
- `backend/src/baserow/core/generative_ai/registries.py` — `get_enabled_models()`, `get_workspace_setting()` methods become obsolete
- `backend/src/baserow/contrib/integrations/ai/models.py` — `AIIntegration` model
- `backend/src/baserow/api/generative_ai/serializers.py` — old settings serializers
- `Workspace.generative_ai_models_settings` field

---

## Verification

1. **Unit tests**: CRUD for all 3 scope levels, resolution logic with overrides, feature filtering, env var seeding
2. **API tests**: All endpoints with permission checks (staff-only for instance, admin-only for workspace, editor for application)
3. **Integration tests**: AI Field generates values using a model configured via the new system; AI Agent Service dispatches using resolved model; test call endpoint works
4. **Frontend manual testing**: Create/edit/delete providers at all levels, toggle instance providers at workspace level, verify model dropdowns show correct filtered models per feature
5. **Migration test**: Set env vars, start app, verify DB seeded correctly, verify existing workspace settings still work during transition

---

## Audit Logging (could be a separate PR)

All provider config mutations (create, update, delete, toggle override, set feature default) must be tracked in the audit log following the existing `ActionType` pattern. Actions:
- `CreateAIProviderActionType`
- `UpdateAIProviderActionType`
- `DeleteAIProviderActionType`
- `ToggleAIProviderActionType` (when PATCH on a parent-scoped provider only changes `is_enabled`)
- `SetAIFeatureDefaultModelActionType`

---

## Open Questions / Nice to have / Future Work

- **Encryption**: API keys should be encrypted at rest. Django has packages like `django-encrypted-model-fields` or we can use Fernet or it could remain plain text if simpler. Need to decide on approach.
- **Rate limiting**: Per-provider rate limits / usage tracking — out of scope for now but the model supports it later.
- **Model auto-discovery**: Some providers (OpenAI, Ollama) support listing available models via API. Could auto-populate the model list.
- **Detailed usage breakdown**: Expand from simple "Used (N)" to a drilldown showing exactly where each model is used (which AI fields, which automations, which assistant chats). Make this the central place for admins to understand AI usage across the instance.
- **Token counters & cost tracking**: Track token usage (input/output) per model, per provider, per workspace. Show cumulative usage in the UI, set budget limits, alert on thresholds. Requires intercepting all AI calls to log token counts from provider responses.
