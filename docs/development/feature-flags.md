# Feature flags

Baserow uses basic feature flags currently to allow unfinished features to be merged
and/or released.

## Available Feature Flags

Add/remove features flags to the list below:

- `agents` — workspace Agent management and Agent creation.
- `ai-providers` — AI provider management for the instance admin area and for
  workspace settings.
- `button-field`: enables the button field type
  ([#1722](https://github.com/baserow/baserow/issues/1722)).

### Preparing the `ai-providers` feature

Migration `core.0120` runs in both flag states. It adds AI Agent eligibility to
existing models, preserves their other features, and defaults omitted feature
selections to AI Fields and AI Agent. Keeping the flag disabled requires no provider
imports or republishing.

Review [integration override compatibility](../testing/kuma-model-settings-test-plan.md#65-explicit-integration-overrides)
before upgrading: these rules apply in both flag states, including to existing
publications.

To enable database-backed providers on an existing installation:

1. Pause AI settings changes and deploy with the flag disabled. Drain old web and
   worker processes. With `FEATURE_FLAGS=*`, first roll out an explicit list of the
   other flags and drain wildcard processes before deploying; alternatively, stop
   the old processes first.
2. Preview both imports: environment settings become instance providers, and legacy
   workspace JSON becomes workspace providers. Review warnings and reconcile conflicts.

   ```bash
   just b manage migrate_ai_provider_settings --scope instance
   just b manage migrate_ai_provider_settings --scope workspace
   ```

3. Apply instance settings first, then workspace settings:

   ```bash
   just b manage migrate_ai_provider_settings --scope instance --apply
   just b manage migrate_ai_provider_settings --scope workspace --apply
   ```

   Each scope is atomic and imports only missing providers, without printing
   credentials. Repeating an import does not synchronize changes to existing providers.
4. Restart all web, backend, and worker processes with `ai-providers` enabled and
   drain the previous processes. Reload administrator/editor tabs before resuming
   settings changes, and all browser tabs before adding new provider types such as
   Google or Groq.
5. Republish sites and workflows containing inherited legacy AI settings snapshots
   to adopt live database credentials and eligibility. Review pending draft changes
   first: republishing makes them live too. Explicit complete integration overrides
   remain independent.

For installations already using the flag, pause settings changes, upgrade with old
processes stopped, and reload administrator/editor tabs before resuming. Keep the
flag enabled unless usable legacy settings have been verified.

For rollback, retain the schema and verify legacy settings before disabling the
flag. Database changes are not copied back; deleting an imported workspace provider
also removes its legacy JSON. Verify published sites and workflows too.

Kuma's legacy model and provider-native credentials are not imported; see
[AI assistant configuration](../installation/ai-assistant.md#2-minimal-enablement).
Use the [transition test plan](../testing/kuma-model-settings-test-plan.md#11-transition-from-legacy-settings-to-database-providers)
to rehearse adoption and rollback.

## Enabling feature flags

To enable specific feature flags set the environment variable
`FEATURE_FLAGS=feature1,feature2,feature3`. Using `just` this would look like:

```bash
FEATURE_FLAGS=feature1,feature2,feature3 just dc-dev up -d
```

You could also add the variable to your `.env.docker-dev` file (for Docker development)
or `.env.local` file (for local development).

## Enabling all feature flags

Use the `*` feature flag to enable every single feature flag without having to specify
each one.

```bash
FEATURE_FLAGS=* just dc-dev up -d
```

## Naming convention

Feature flags should be:

1. Alphanumeric with dashes.
2. Not start or end with spaces (flags from the env variable will be trimmed for ease of
   use).
3. Unique per feature.

## Creating a feature flag

### In the Backend

```python
# Add variable with feature flag to baserow.core.feature_flag in format
# FF_<FEATURE_NAME> = "feature_name"
# i.e.
FF_FEATURE1 = "feature1"

# In your feature file import flag you need and feature flag function
from baserow.core.feature_flag import FF_FEATURE1, feature_flag_is_enabled

# Use to check if feature is enabled
if feature_flag_is_enabled(FF_FEATURE1):
    # do the feature

# or if you want to raise exception if the feature is not enabled
feature_flag_is_enabled(FF_FEATURE1, raise_if_disabled=True)
```

### In the Web-frontend

```javascript
// add feature flag variable in @core/plugins/featureFlags.js in format
// FF_<FEATURE_NAME> = "feature_name"
// i.e.
export const FF_FEATURE1 = "feature1";

methods: {
    someComponentMethod();
    {
        if (this.$featureFlagIsEnabled(FF_FEATURE1)) {
            // do the feature
        }
    }
}
```
