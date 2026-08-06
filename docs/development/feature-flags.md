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

There are two sources of legacy configuration and both must be imported: AI provider
**environment variables** become instance-level providers, and each workspace's legacy
`generative_ai_models_settings` JSON becomes workspace-owned providers. Run the whole
sequence with the flag still disabled, because until a workspace's legacy JSON is
imported the new UI reports no workspace provider while that JSON is still what
resolves at runtime.

1. Keep `ai-providers` disabled and let the old workers drain, so nothing writes
   provider configuration through both paths at once.
2. Preview both scopes. The command writes nothing without `--apply`:

```bash
just b manage migrate_ai_provider_settings --scope instance
just b manage migrate_ai_provider_settings --scope workspace
```

3. Review the reported providers, then apply each atomically, instance first:

```bash
just b manage migrate_ai_provider_settings --scope instance --apply
just b manage migrate_ai_provider_settings --scope workspace --apply
```

4. Enable `ai-providers`.

The command never prints credentials and preserves provider types already configured
at the selected scope, so both imports are safe to run again — only missing
provider types are imported.

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
