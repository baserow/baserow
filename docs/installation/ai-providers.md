# AI provider management

Instance staff configure shared connections in **Admin → AI providers**. Workspace
administrators configure their own connections in **Settings → AI providers**.
Add models, choose their **Available for** features, and use **Test model** before
selecting them in a consumer. Kuma also needs a default under **AI features**; see
[AI assistant configuration](ai-assistant.md). AI Fields, formula suggestions, and
AI Agent actions keep their existing model selections.

## Configuration and compatibility

An active workspace model overrides an instance model with the same identifier;
other instance models remain inherited with their own complete connection. A disabled
workspace model suppresses that identifier. Disabling the workspace provider reveals
the inherited instance layer again. Each scope permits one provider of each type.

Legacy environment settings remain a fallback when no database provider configuration
exists for that provider type. Complete legacy workspace JSON settings remain usable
until that workspace provider is imported. Where database providers exist, their
enabled models and feature eligibility constrain that legacy workspace model list.
Incomplete workspace connections are not combined with credentials from another scope.
The administration page lists database providers, so an empty page does not prove that
no legacy configuration is in use.

AI integrations can still have their own settings. A complete connection with an
explicit model list is independent of database credentials and feature eligibility.
Without a `models` key it inherits the allowed list; `models: []` permits no models.
An incomplete connection can only narrow the inherited list, and its connection
fields are ignored. Complete connections do not borrow omitted optional endpoints or
organization settings. Check the
[override matrix](../testing/kuma-model-settings-test-plan.md#65-explicit-integration-overrides),
including installed extensions, before upgrading.

## Upgrading an existing installation

Imports are not required to start a new release, but an upgrade without imports
still needs compatibility verification. Verify the precedence of existing database
providers and legacy sources, including incomplete workspace settings.

1. Back up the database and deployment configuration securely. Rehearse the exact
   candidate and intended rollback image against an isolated representative copy,
   following the [rollout test plan](../testing/ai-provider-rollout-test-plan.md).
   Inventory every consumer, including published applications, and verify its
   intended provider account, endpoint, model, and disable rules.
2. Pause provider, integration, model-selection, and publication writes during the
   final reconciliation and deployment. Apply normal schema migrations. `core.0120`
   preserves existing model features and adds AI Agent eligibility once; imported
   models default to AI Fields and AI Agent. Kuma remains an explicit selection.
3. A rolling deployment is appropriate only when the exact previous and candidate
   versions have demonstrated equivalent behavior during overlap. If overlap cannot
   preserve behavior, use a planned coordinated cutover with old processes stopped
   before starting the candidate.
4. Drain every previous backend, worker, scheduler, and frontend process before
   changing provider configuration. Account for queued and in-flight AI work.
   Reload all active administrator/editor browsers before resuming writes. Before
   adding a provider type absent from older clients, require all affected users to
   reload; replacing frontend servers does not update already-loaded browser code.
5. Verify every consumer before ending the write pause. Retain usable legacy settings
   and the tested rollback image throughout the rollback window.

Start the inventory with `just b manage audit_ai_provider_settings`, optionally
adding `--workspace-id <id>` to inspect one workspace and its publications. It prints
read-only JSON metadata without credentials or provider requests. A successful
command means the inventory completed; it does not certify rollout readiness.

## Importing legacy settings

Run these commands in the deployment's backend environment. The examples use the
repository's `just` wrapper; container deployments can invoke the same Django
management command through their usual backend shell.

Preview environment settings as instance providers and workspace JSON as workspace
providers:

```bash
just b manage migrate_ai_provider_settings --scope instance
just b manage migrate_ai_provider_settings --scope workspace
```

Review every warning and reconcile differences under the write pause. Apply instance
settings first, then workspace settings, after incompatible previous processes have
drained and before consumer verification:

```bash
just b manage migrate_ai_provider_settings --scope instance --apply
just b manage migrate_ai_provider_settings --scope workspace --apply
```

Each scope is atomic and imports only missing providers without printing credentials.
Repeating an import is idempotent; it does **not** synchronize an existing provider
with later environment or workspace changes. Incomplete settings are skipped, and
conflicting database providers are preserved. Review the resulting behavior before
accepting either outcome. The two scopes are separate transactions.

Imports do not inspect integration overrides or publications. They also do not import
Kuma's legacy model selection or provider-native credentials; configure and test that
selection separately. Existing fallbacks remain supported while this work is pending.

## Published applications

Older publications can contain snapshots of inherited workspace settings. These are
indistinguishable from deliberate integration overrides because no provenance marker
was stored. Confirm the intended connection with each application's owner.

For an inherited source integration, an approved republish adopts live workspace
provider resolution. Republishing also deploys unrelated current draft changes:
preserve the intended live version in a protected backup and obtain the owner's
approval for the draft first. Check every Builder domain and live Automation workflow
separately. Keep publications with unapproved drafts unchanged.

Record deferred snapshots as compatibility overrides. They continue using their own
credentials and explicit model list; central credential rotation, disable rules, and
AI Agent eligibility do not govern them. Verify them independently and keep their
credentials usable until an approved cutover.

## Rollback

Use the **exact previously rehearsed application image and its verified
configuration** for rollback, or prepare a forward repair.
Retain the database schema and provider rows; do not reverse the compatibility
migrations as part of an application rollback.

Before rollback, pause relevant writes and verify that the previous image preserves
the intended behavior with the retained schema, credentials, and publications.
Database edits do not update legacy environment or workspace settings, and deleting
an imported workspace provider removes its matching legacy JSON. Reconcile key
rotations, database-only selections, and disable rules before restoring any previous
legacy path. Stop if equivalent behavior cannot be established. Drain replaced
processes, reload browsers, and verify all consumers before resuming writes.
