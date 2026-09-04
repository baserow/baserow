# Kuma model settings test plan

Manual tests for per-feature AI model settings and the workspace-level Kuma model
selection.

The feature lets an instance administrator pick which AI features a provider model
may serve (**Available for**), pick one default model per feature that needs one
(**AI features**), and lets a workspace admin inherit, override, or disable that
choice per workspace.

## Prerequisites

### Environment

- The `ai-providers` feature flag is enabled (`FEATURE_FLAGS=*` or an explicit list
  containing `ai-providers`) on backend, celery and web-frontend.
- An **Enterprise** license is active — Kuma is enterprise-only. AI fields need
  **Premium**.
- `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` **is set** together with the credentials
  its provider needs. This matters: the legacy fallback must exist, otherwise
  "unconfigured" and "disabled" look identical in the UI.
- At least one real API key so model tests and Kuma messages actually reach a
  provider. Two working model identifiers on the same provider make the
  "changed the model" tests decisive.

### Accounts and workspaces

Two accounts in the same workspace:

- **admin** — an instance staff user who is also an admin of the workspace. Used for
  every instance and workspace setting change.
- **builder** — a member of the same workspace without admin rights. Used for the
  permission and realtime tests.

Create a second workspace as well, so per-workspace isolation can be observed. Use
two browser profiles (or one normal and one private window) for the realtime tests.

### Where the UI lives

- **Instance**: Admin → **AI providers** (`/admin/ai-providers`), section **AI features**.
- **Workspace**: workspace context menu → **Settings** → **AI providers** tab,
  section **AI features**.
- **Kuma**: the **Kuma AI** item in the left sidebar of a workspace, which opens the
  assistant panel on the right.

UI strings quoted below come from `web-frontend/modules/core/locales/en.json`; if a
label was reworded since, treat the wording as indicative and the behaviour as
binding.

Only features that need one default model appear in the **AI features** section.
Today that is **Kuma** only — AI fields and AI Agent services used by Automation
nodes and Application Builder actions pick their models per consumer, so their
checkboxes control *eligibility*, not a default.

### Helper: what the backend actually resolves

Most expectations below are about which model Kuma ends up using, which the UI does
not show directly. Write this script once:

Set `WORKSPACE_IDS` to the workspaces you are testing. A development instance is
usually seeded with template workspaces, so listing "the first few workspaces" would
print scopes you never touch and omit the ones you do.

```bash
cat > /tmp/kuma_state.py <<'EOF'
import os

from baserow.core.ai_provider.handler import AIProviderHandler
from baserow.core.models import Workspace
from baserow_enterprise.assistant.model_profiles import resolve_assistant_model

ids = [int(value) for value in os.environ.get("WORKSPACE_IDS", "").split(",") if value]
scopes = [None] + list(Workspace.objects.filter(id__in=ids).order_by("id"))
for workspace in scopes:
    label = "instance" if workspace is None else f"workspace {workspace.id} {workspace.name}"
    for setting in AIProviderHandler.list_feature_settings(workspace):
        print(f"{label}: {setting['feature_type']} mode={setting['mode']} "
              f"state={setting['state']} model={setting['model']} "
              f"inherited_state={setting['inherited_state']}")
    try:
        profile = resolve_assistant_model(workspace=workspace)
        print(f"{label}: kuma -> source={profile.source} model={profile.model_string}")
    except Exception as error:
        print(f"{label}: kuma -> {type(error).__name__}: {error}")
EOF
```

Run it after every settings change:

```bash
WORKSPACE_IDS=1,2 just dc-dev exec -T backend -e WORKSPACE_IDS \
  /baserow/venv/bin/python /baserow/backend/src/baserow/manage.py shell < /tmp/kuma_state.py
```

Sample output on an untouched instance:

```
instance: kuma mode=legacy state=unconfigured model=None inherited_state=None
instance: kuma -> source=legacy model=<provider>:<env model>
```

`model=` on the feature line prints the bare model identifier; the `kuma ->` line
prints the fully qualified `<provider>:<identifier>` that reaches the provider.
`inherited_state` is only set at workspace scope: it reports how the *instance*
selection resolves **in that workspace**, so `invalid` means the instance picked a
model this workspace cannot reach.

`source=legacy` means the env var is in use, `source=database` means the selected
model is, and `AssistantModelDisabledError` means Kuma is off with no fallback.

### Expected resolution

| Instance selection | Workspace selection | Kuma in that workspace |
|---|---|---|
| Use legacy environment model: `<env model>` | Use instance setting | legacy env model |
| Model A | Use instance setting | model A |
| Model A | Model B | model B |
| Model A | Disabled in this workspace | off, no fallback |
| Disabled | Use instance setting | off, no fallback |
| Disabled | Model B | model B |
| Model A, now unavailable (invalid) | Use instance setting | legacy env model |

"Off" means the Kuma sidebar item disappears and the API rejects messages. An
explicit **Disabled** never falls back to the env var; **unconfigured** and
**invalid** always do.

The last row is a workspace that was *already* inheriting when the instance selection
became unreachable. Newly switching to **Use instance setting** in that situation is
refused instead — see 4.5.

---

## 1. Instance provider and model setup

### 1.1 Add an instance provider

1. Sign in as **admin**, go to Admin → **AI providers**.
2. **Add provider** → pick a provider type, enter the API key.
3. In the model rows, enter a model identifier and note the new **Available for**
   checkboxes (**AI Agent**, **AI fields**, **Kuma**), all ticked by default.
4. Add a second model, untick **AI Agent** and **Kuma** on it, save.
5. Add a third model through the provider menu → **Add model**, and untick all three
   boxes.

Verify:
- The provider is created with all three models.
- The first two model rows show all three feature labels and **AI fields** only,
  respectively. Feature order is not semantically meaningful and can reflect how the
  row was created.
- A model with no boxes ticked saves, and its row shows
  `Not available to any listed feature`.

### 1.2 Test the models

1. Use the model row menu → **Test model** on the Kuma-eligible model.
2. Repeat on the AI-fields-only model.

Verify:
- Both show **Test passed** when the credentials are valid. This includes reasoning
  models such as `openai/gpt-oss-20b`, which spend tokens before emitting content:
  every probe uses the same `AI_PROVIDER_TEST_MAX_TOKENS` budget, so ticking or
  unticking **Kuma** must never change whether a working model passes.
- The Kuma-eligible model was probed for text *and* tool calling, the AI-fields-only
  model for text only. The UI does not show this, so check the response of
  `POST /api/ai-providers/models/test/` (its `feature_results` lists one entry per
  selected feature) or `AIProviderModel.last_test_capabilities`, which holds a `text`
  and a `tools` key for a Kuma-eligible model and only `text` otherwise.
- A model without tool support passes as an AI fields or AI Agent model, and shows
  **Some tests failed** when it is also marked for Kuma — hover the badge for the
  per-feature breakdown.
- With a bogus identifier the row shows **Test failed** and the tooltip lists a
  failure line per selected feature.

### 1.3 The new database-only provider types

This branch adds **Google Gemini** and **Groq** as provider types.

Verify:
- Both appear in the **Add provider** type list and accept an API key.
- Their models can be marked for Kuma, AI fields, and AI Agent services, tested, and
  selected like any other provider's.
- They are configurable through the admin/workspace AI providers UI only. The legacy
  endpoint is `PATCH` (a `PUT` returns `405`), and a `google` or `groq` key is
  rejected with `400 ERROR_REQUEST_BODY_VALIDATION`, *"Your request body had the
  following unknown attributes: google"*, while `openai`, `anthropic`, `mistral`,
  `ollama` and `openrouter` are still accepted there:

  ```bash
  curl -X PATCH "http://localhost:8000/api/workspaces/<id>/settings/generative-ai/" \
    -H "Authorization: JWT $JWT" -H "Content-Type: application/json" \
    -d '{"google":{"api_key":"x","models":["gemini-3.6-flash"]}}'
  ```
- An **AI integration** in the application builder or an automation *does* accept
  `google` and `groq` in its `ai_settings`.

### 1.4 Editing a model resets its test result

1. Edit the tested model, change the identifier or the **Available for** boxes, save.

Verify: the row falls back to **Not tested**. Changing the provider's API key
resets the test result of every model of that provider.

### 1.5 Feature eligibility is validated at the API

Verify:
- `POST /api/ai-providers/<provider_id>/models/` with
  `{"feature_types": ["not-a-feature"]}` returns
  `400 ERROR_AI_PROVIDER_MODEL_FEATURE_TYPE_DOES_NOT_EXIST`.
- Omitting `feature_types` entirely is the back-compat path for older API callers: the
  model is created with `["ai_fields", "ai_agent"]`, the two per-consumer features
  that used provider models before eligibility was introduced, **not** with every
  registered feature.
- `{"feature_types": []}` is accepted, and the resulting model is offered by no
  feature (see 6.1).

---

## 2. Instance-level Kuma selection

### 2.1 Default is the legacy fallback

Verify, before touching anything:
- The **AI features** section shows one row, **Kuma**, set to
  **Use legacy environment model: `<env model>`**, quoting the value of
  `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL`.
- The helper prints `mode=legacy state=unconfigured` and `source=legacy`.
- Kuma is visible in the sidebar of every workspace that inherits, and answers a
  message.

### 2.2 Select an instance model

1. In **AI features**, choose the Kuma-eligible model (labelled
   `<Provider> · <model identifier>`).
2. Reload, then run the helper.

Verify:
- The dropdown keeps the selection after a reload.
- The helper prints `mode=model state=configured` for the instance, and
  `mode=inherit state=inherited inherited_state=configured` for every workspace that
  inherits. Both print `source=database model=<provider>:<identifier>` — the
  resolution is shared, the mode and state are not.
- Kuma still answers a message in a workspace with no own selection.
- Only models with **Kuma** ticked, belonging to an active provider and enabled,
  are offered in the dropdown.

### 2.3 The database selection really overrides the env var

1. Add a model with a deliberately non-existent identifier (for example
   `openai/does-not-exist`), tick **Kuma**, and select it in **AI features**.
2. Send a message to Kuma.

Verify:
- The chat shows an error; the `POST /assistant/chat/<uuid>/messages/` response is
  `400` with `ERROR_ASSISTANT_CONFIGURED_MODEL_NOT_AVAILABLE` and the detail
  *"The Kuma model selected in AI provider settings could not be used. Test the
  selected model and verify its provider credentials before trying again."*
- It does **not** silently fall back to `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL`.
- After selecting a working model again, Kuma answers on the **next message**, with no
  wait: the readiness cache is keyed per model and provider revision, so a different
  model is a different key. The 30-second failure cache only delays retrying the *same*
  failing model, and a successful probe is cached for 5 minutes — which is why editing
  the provider (its `updated_on` is part of the key) is what re-probes a fixed model.

### 2.4 Change the instance model

1. Select model A, send a message, then select model B and send another.

Verify:
- The helper reports `model=<provider>:A` and then `model=<provider>:B`.
- The switch takes effect on the next message without restarting anything.

### 2.5 Disable Kuma instance-wide

1. Set **Kuma** to **Disabled**.

Verify:
- The **Kuma AI** sidebar item disappears in every workspace that *inherits* the
  instance setting, without a reload; an open Kuma panel closes on its own. A
  workspace with its own model selection keeps Kuma — that is tested in 3.4.
- `GET /api/settings/` returns `kuma.is_enabled: false`.
- The helper raises `AssistantModelDisabledError` for the instance and for every
  inheriting workspace — no legacy fallback.
- `POST /assistant/chat/<uuid>/messages/` returns `400`
  `ERROR_ASSISTANT_MODEL_DISABLED`, detail *"Kuma is disabled in AI provider
  settings. Enable Kuma before trying again."* Note the assistant endpoints are
  mounted at the root, not under `/api/`, and the request needs a `ClientSessionId`
  header plus a `ui_context` — without them you get a body-validation error instead
  of the error you are testing for:

  ```bash
  curl -X POST "http://localhost:8000/assistant/chat/$(uuidgen)/messages/" \
    -H "Authorization: JWT $JWT" -H "Content-Type: application/json" \
    -H "ClientSessionId: manual-test" \
    -d '{"content":"hi","ui_context":{
          "workspace":{"id":<id>,"name":"<name>"},
          "user":{"id":<id>,"first_name":"<name>","email":"<email>"}}}'
  ```

### 2.6 Back to the fallback

1. Set **Kuma** back to **Use legacy environment model: `<env model>`**.

Verify: the sidebar item returns without a reload, `kuma.is_enabled` is `true`
again, and the helper prints `source=legacy`.

---

## 3. Workspace-level Kuma selection

Precondition: the instance selection is a working model A.

### 3.1 A workspace inherits by default

1. As **admin**, open the workspace **Settings → AI providers**.

Verify:
- The **AI features** row is set to **Use instance setting — `<Provider> · A`**.
- The helper prints `mode=inherit state=inherited inherited_state=configured` and
  `source=database model=…A`.
- The inherit option reflects the instance state as resolved *in this workspace*:

  | instance situation | `inherited_state` | inherit option reads | selectable |
  |---|---|---|---|
  | model A, reachable here | `configured` | **— `<Provider> · A`** | yes |
  | no instance row | `unconfigured` | **— legacy environment model: `<env model>`** | yes |
  | no instance row, env var unset | `unconfigured` | **— legacy environment model: empty** | no |
  | instance row **Disabled** | `disabled` | **— Disabled** | yes |
  | model A, unreachable here | `invalid` | **— selected model unavailable in this workspace** | no |

  The last row is what 4.5 sets up. The option must never advertise the legacy
  environment model when the instance is in fact pointing at a database model.
- There is no legacy option at workspace scope; the three entries are the inherit
  option, **Disabled in this workspace**, and the eligible models.

### 3.2 Override with a different model

1. Add a workspace-owned provider with its own key and a Kuma-eligible model B, or
   pick an inherited instance model.
2. Select it in the workspace **AI features** row.

Verify:
- Model options are suffixed **· Instance** or **· Workspace** so their origin is
  visible.
- The helper prints `mode=model state=overridden` and `source=database model=…B`
  for this workspace only; other workspaces still resolve A.
- Kuma answers in this workspace.

### 3.3 Disable Kuma in one workspace

1. Set the workspace row to **Disabled in this workspace**.

Verify:
- The **Kuma AI** sidebar item disappears in *this* workspace only, without a
  reload, and
  an open panel closes.
- Kuma is still available in the other workspace.
- The helper raises `AssistantModelDisabledError` for this workspace and still
  resolves normally for the instance and the other workspace.

### 3.4 An instance disable wins over inheritance

1. Restore the workspace to **Use instance setting**, then set the instance row to
   **Disabled**.

Verify: the workspace is off too, and its dropdown still reads **Use instance
setting**. Selecting a model in the workspace while the instance is disabled turns
Kuma back on for that workspace only.

### 3.5 Back to inheriting

1. Set the workspace row back to **Use instance setting**.

Verify: the helper shows `mode=inherit` again and the workspace follows the
instance selection; the workspace row is deleted rather than pinned to a copy —
changing the instance model immediately changes this workspace too.

---

## 4. Guardrails around a model in use

With Kuma pointing at model A (at any scope), as the scope's admin. A provider's
**More actions** menu offers *Add model / Test all models / Edit / Disable / Delete*;
a model's offers *Test model / Edit / Disable / Delete*.

### 4.1 Deleting the selected model or its provider

Verify: the delete is rejected (`ERROR_AI_PROVIDER_MODEL_IN_USE`) with the toast
*"The AI provider change could not be completed. / Choose another model for the AI
feature before changing this provider or model."* The provider and its models
survive the confirm dialog.

### 4.2 Removing the Kuma checkbox from the selected model

Verify: same rejection, under the title *"The AI provider model could not be
saved."*; the modal stays open and the row keeps **Available for: AI Agent, AI fields,
Kuma**. Removing only the **AI Agent** or **AI fields** checkbox is allowed, because
neither is a default-model feature.

### 4.3 Disabling the selected model or its provider

Verify: the model's **Disable** action and the provider's **Disable** both return
`400 ERROR_AI_PROVIDER_MODEL_IN_USE` and raise the same *"The AI provider change could
not be completed."* toast as 4.1.

### 4.4 A workspace turning off an inherited provider it resolves through

1. In a workspace inheriting an instance Kuma selection, toggle the inherited
   provider off in the workspace AI providers list.

Verify: rejected with the same error. It succeeds once that workspace no longer
resolves Kuma **through that provider** — so setting Kuma to **Disabled in this
workspace**, or selecting a model from a *different* provider. Picking another model
of the same inherited provider does not unblock it.

### 4.5 Inheriting an unavailable instance selection

1. In a workspace inheriting instance model A, set its row to **Disabled in this
   workspace** (so 4.4 no longer blocks the provider), then disable the inherited
   provider in the workspace AI providers list.
2. Reopen the **AI features** dropdown.

Verify:
- The inherit option now reads **Use instance setting — selected model unavailable in
  this workspace** and is **disabled**, so the rejection cannot be reached by clicking.
  It must not read *"legacy environment model: …"* — the instance is still pointing at
  model A, this workspace just cannot reach it.
- The helper prints `inherited_state=invalid` for this workspace while the instance
  scope still prints `state=configured`.
- The API still refuses the transition, which is what the disabled option reflects:

  ```bash
  curl -X PUT "http://localhost:8000/api/ai-providers/features/kuma/?workspace_id=<id>" \
    -H "Authorization: JWT $JWT" -H "Content-Type: application/json" \
    -d '{"mode":"inherit"}'
  # 400 ERROR_AI_PROVIDER_FEATURE_MODEL_NOT_AVAILABLE
  ```

- Re-enabling the inherited provider makes the option selectable again, and choosing
  it deletes the workspace row (see 3.5).

Note the asymmetry, which is deliberate: a workspace *already* inheriting an
unresolvable instance selection keeps working on the legacy environment model (see
section 5), but no one may newly opt into that state.

### 4.6 Cross-scope: a workspace selection blocks the instance admin

1. With the instance Kuma row **Disabled** and one workspace pointing at instance
   model A, sign in as the instance admin and try to delete model A, and to untick its
   **Kuma** box.

Verify:
- Both are rejected with `ERROR_AI_PROVIDER_MODEL_IN_USE`, even though no *instance*
  feature selects the model — `_feature_types_using_model` deliberately looks across
  every scope.
- The error names the model but not the workspace holding it, so the instance admin
  cannot tell which workspace to change. Confirm this is still the behaviour before
  filing it as a bug.

### 4.7 Instance provider is read-only in a workspace

Verify: an inherited provider is listed with the badges **Shared across workspaces**
and **Inherited**, its **More actions** menu offers only **Disable**, and a separate
**Add workspace configuration** button lets the workspace own its own provider of
that type instead. Editing or deleting it through the API returns
`ERROR_AI_PROVIDER_IS_READ_ONLY`.

---

## 5. Invalid selection falls back (forced state)

The guardrails above make an invalid selection unreachable through the UI, so force
it directly:

```bash
just dc-dev exec -T backend /baserow/venv/bin/python \
  /baserow/backend/src/baserow/manage.py shell <<'EOF'
from baserow.core.ai_provider.models import AIProviderConfig
AIProviderConfig.objects.filter(workspace__isnull=True).update(is_active=False)
EOF
```

Reload the admin page and verify:
- The **AI features** dropdown shows the disabled entry **"Selected model
  unavailable — using legacy environment model: `<env model>`"**.
- The helper prints `state=invalid` and `source=legacy` — Kuma keeps working on the
  env-var model, it does not go off.
- Kuma is still visible in the sidebar (because the fallback exists). With
  `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` unset it would disappear instead.

Re-enable the provider (`update(is_active=True)`) and confirm the selection becomes
`configured` again.

The workspace scope has its own `invalid` branch, reached without the shell: have a
workspace select an instance model, then disable that provider instance-wide. Verify
its **AI features** dropdown shows the same disabled
**"Selected model unavailable — using legacy environment model: `<env model>`"** entry,
and that Kuma there also falls back rather than switching off.

---

## 6. Per-consumer features are separate

### 6.1 Eligibility is per feature

1. Create an AI field in a table of the workspace.

Verify:
- Models with **AI fields** unticked are not offered in the field's model dropdown.
- Models with **AI Agent** unticked are not offered in an Automation AI Agent node's
  or Application Builder AI Agent action's model dropdown.
- Models with only **AI fields** ticked are not offered in the Kuma **AI features**
  dropdown.
- A model with no feature ticked appears nowhere.

The same filter can be checked directly on the payload the frontend reads:

```bash
curl -s http://localhost:8000/api/workspaces/ -H "Authorization: JWT <token>" \
  | python3 -c "import json,sys; [print(w['id'], json.dumps(w['ai_features'])) for w in json.load(sys.stdin)]"
```

`ai_features.ai_fields.models` must exclude every Kuma-only model,
`ai_features.ai_agent.models` must exclude every model without AI Agent eligibility,
and a model with no feature ticked must be absent from all feature lists. The legacy
`generative_ai_models_enabled` field still lists **all** of them, including the
no-feature model — which is exactly why the frontend must read `ai_features` while the
flag is on, and why section 10's legacy path still offers those models.

`ai_features.kuma` carries `is_enabled` plus a `state`. That `state` is not the
helper's: `unconfigured` and `invalid` are both reported here as `legacy`, because
what the client needs to know is that Kuma is running on the environment model.

### 6.2 The Kuma switch does not touch AI fields

1. Disable Kuma at instance or workspace level.

Verify: the AI field type is still available, the model dropdown is unchanged, and
generating values still works.

### 6.3 Removing AI fields eligibility from a model in use by a field

1. Untick **AI fields** on a model that an existing AI field uses.

Verify:
- The change is allowed — no default-model feature blocks it.
- Generation is refused: `POST /api/database/fields/<id>/generate-ai-field-values/`
  returns `400 ERROR_MODEL_DOES_NOT_BELONG_TO_TYPE`, *"The selected AI model is
  disabled or no longer available."*
- The field form does **not** announce the loss. Both **AI Type** and **AI Model** fall
  back to the empty `Make a choice` placeholder, because the stored value is no longer
  among the options. That is today's behaviour, not a defect to file — but it means a
  tester must not expect an explicit "model unavailable" message here.

---

## 7. Realtime propagation

Two sessions: **admin** in browser A on the admin page, **builder** in browser B
with the shared workspace open.

### 7.1 Instance change

1. In A, set the instance Kuma row to **Disabled**, then back to a model.

Verify in B, without reloading:
- The Kuma sidebar item disappears and reappears.
- An open Kuma panel closes when it disappears.
- B never receives provider state. Check the `ai_provider_updated` websocket frames in
  B: a non-admin member gets only `generative_ai_models_enabled_by_workspace` and
  `ai_features_by_workspace`, plus the instance-wide `instance_ai_features`. The keys
  carrying provider rows are scoped:

  | key | recipients |
  |---|---|
  | `instance_ai_features` | every user |
  | `generative_ai_models_enabled_by_workspace`, `ai_features_by_workspace` | every member of the workspace |
  | `ai_providers_by_workspace`, `ai_provider_feature_settings_by_workspace` | workspace admins |
  | `instance_ai_providers`, `instance_ai_provider_feature_settings` | staff |

### 7.2 Workspace change

1. In A, disable Kuma for the shared workspace in its settings.

Verify: B loses the Kuma item for that workspace without a reload, and a session
on a different workspace is unaffected.

### 7.3 Admin lists stay in sync

Verify: a second staff session with the admin page open sees the provider list,
model rows and the **AI features** selection update live.

---

## 8. Permissions

The error codes below are the ones an **Enterprise** instance returns, where the RBAC
role permission manager denies first. Without RBAC the basic manager answers instead
and you get `ERROR_USER_INVALID_GROUP_PERMISSIONS` — so run these with the licence
this plan assumes, or the codes will not match.

### 8.1 Instance settings need staff

Verify: **builder** has no **AI providers** admin entry, `/admin/ai-providers` is not
reachable (the route carries an `aiProvidersFeatureFlag` middleware and a `staff`
middleware), and `GET /api/ai-providers/features/` returns
`401 PERMISSION_DENIED`. Note that a workspace admin who is not instance staff is
refused here too.

### 8.2 Workspace settings need workspace admin

Verify: a non-admin member has no **Settings** entry in the workspace context menu, and
`PUT /api/ai-providers/features/kuma/?workspace_id=<id>` returns
`401 PERMISSION_DENIED`. An admin of workspace X aiming at workspace Y is refused
earlier still, with `400 ERROR_USER_NOT_IN_GROUP` — a different code, because they are
not a member at all rather than a member without rights.

### 8.3 Scope confusion

Verify, all `400 ERROR_AI_PROVIDER_FEATURE_MODE_NOT_ALLOWED`:
- `PUT /api/ai-providers/features/kuma/?workspace_id=<id>` with `{"mode": "legacy"}`
  (legacy is instance-only);
- the instance scope with `{"mode": "inherit"}` (inherit is workspace-only).

And `400 ERROR_REQUEST_BODY_VALIDATION`:
- `{"mode": "disabled", "model_id": 1}` — *"A model can only be provided in model
  mode."*;
- `{"mode": "model"}` with no `model_id` — *"A model is required when selecting model
  mode."*

### 8.4 Secrets never leave the backend

Verify:
- `GET /api/ai-providers/` (staff) and `GET /api/ai-providers/?workspace_id=<id>`
  (workspace admin) never contain `api_key`, for any provider.
- A workspace admin reading an **inherited** provider gets `extra_settings: {}` — the
  instance's organization, base URL or Ollama host are not disclosed to workspaces.
- Neither appears in any `ai_provider_updated` websocket frame (7.1).

---

## 9. Instance settings payload and onboarding

### 9.1 Settings endpoint

Verify: `GET /api/settings/` contains `kuma.is_enabled`, `true` while a model is
selected or the legacy fallback exists, `false` when the instance row is
**Disabled**.

### 9.2 Onboarding step visibility

1. Sign up a new user while Kuma is enabled, and walk to the database step.
2. Repeat with the instance row **Disabled**.

To reuse an account instead of signing up twice, clear its onboarding flag and reload:

```bash
just dc-dev exec -T backend /baserow/venv/bin/python \
  /baserow/backend/src/baserow/manage.py shell <<'EOF'
from baserow.core.models import UserProfile
UserProfile.objects.filter(user__email="<email>").update(completed_onboarding=False)
EOF
```

Verify: the AI-assisted database onboarding step is offered in the first case and
hidden in the second. The step reads `settings.kuma.is_enabled`, so it follows the
instance row and not the workspace one.

### 9.3 Onboarding suggestions

Verify: with Kuma disabled at the instance,
`POST /assistant/onboarding/prompt-suggestions/` returns
`ERROR_ASSISTANT_MODEL_DISABLED`; with a broken selected model it returns
`ERROR_ASSISTANT_CONFIGURED_MODEL_NOT_AVAILABLE`. Onboarding resolves the
**instance** scope, so a workspace-level disable must not affect it.

---

## 10. Feature flag off (legacy behaviour)

Restart the stack with `ai-providers` removed from `FEATURE_FLAGS` (all services)
and verify nothing from this feature leaks into the old path:

- The admin **AI providers** page and `/api/ai-providers/...` are unavailable.
- The workspace settings tab is the old **Generative AI** form again, and it lists
  only providers that support legacy workspace settings — **Google Gemini** and
  **Groq** must not appear there.
- Kuma is visible exactly when `BASEROW_ENTERPRISE_ASSISTANT_LLM_MODEL` is set, and
  uses it; stored feature settings are ignored (the helper prints `source=legacy`).
- AI fields offer the env-var and legacy workspace models, unfiltered by
  `feature_types`.
- Automation AI Agent nodes and Application Builder AI Agent actions likewise use
  the legacy integration/workspace/environment model lists without feature filtering.

---

## Known limitations

- `update_feature_setting` revalidates the selection without holding a lock, so two
  administrators saving at the same instant can race. This is accepted, not a defect to
  file — do not chase it as a flake.
- `ERROR_AI_PROVIDER_MODEL_IN_USE` names the model but never the scope holding it
  (4.6).
- Removing a model's **AI fields** eligibility silently empties the AI field form's
  dropdowns rather than explaining itself (6.3).
