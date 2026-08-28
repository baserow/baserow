# Feature flags

Baserow uses basic feature flags currently to allow unfinished features to be merged
and/or released.

## Available Feature Flags

Add/remove features flags to the list below:

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

1. Before deploying the release, keep `ai-providers` disabled. If the installation
   uses `FEATURE_FLAGS=*`, first make a separate configuration-only rollout of the
   currently installed release with an explicit list of the other required flags;
   there is no negative override for one flag. Wait for every wildcard-configured
   web and worker process to drain before deploying the new image. Do not combine
   this configuration change with a rolling image update: old processes would still
   enable `ai-providers`. If the platform cannot roll out configuration separately,
   stop the old processes before starting the new release with the explicit list.
2. Deploy the release and let the old web and worker processes drain. Pause changes
   to instance and workspace AI provider settings until the import is complete and
   the flag has been enabled; otherwise a workspace can change its legacy JSON after
   the command has read it.
   The new Google and Groq provider types have no environment variables and are
   configured in the admin UI only. Older frontend bundles do not have those
   provider types in their registry and cannot safely render a workspace payload
   containing them, so add either provider only after every old frontend process
   has drained. Draining frontend processes does not replace JavaScript already
   loaded in a browser tab: before adding either provider, require active users to
   reload Baserow (or close and reopen it) onto the new frontend assets. Keep the
   settings-write pause in place until that client cutover is complete.
3. Preview both scopes. The command writes nothing without `--apply`:

```bash
just b manage migrate_ai_provider_settings --scope instance
just b manage migrate_ai_provider_settings --scope workspace
```

4. Review every warning. Repair or explicitly accept each incomplete legacy setting
   and each difference from an existing database provider before proceeding. The
   importer preserves the database provider in a conflict, and an incomplete
   workspace override can inherit the instance provider after the flag is enabled.
   Then apply each scope atomically, instance first:

```bash
just b manage migrate_ai_provider_settings --scope instance --apply
just b manage migrate_ai_provider_settings --scope workspace --apply
```

5. Redeploy or restart every web, backend, and worker process with `ai-providers`
   enabled, then wait for every feature-disabled process to drain before ending
   the settings-write pause. This prevents one generation from resolving legacy
   settings while another resolves the imported database settings. Wildcard
   installations can now restore `FEATURE_FLAGS=*`.

The command never prints credentials and preserves provider types already configured
at the selected scope, so both imports are safe to run again — only missing
provider types are imported.

The command does not import Kuma's legacy model or provider-native credentials.
Kuma continues to use that legacy configuration when its database selection is
unconfigured or invalid. An explicit instance or workspace disable remains
authoritative and does not fall back. An administrator can clear an instance
database selection with **Use legacy environment model**, which displays the
configured model, before or after the feature gate is retired.

When retiring `ai-providers`, make the database-backed paths unconditional in both
the backend and frontend; a missing flag must not route clients back to legacy-only
payloads. Remove only the feature gates in that release and retain the legacy provider
and Kuma resolution fallbacks: self-hosted installations can skip the manual import
sequence, and some legacy Kuma providers cannot yet be represented by database-backed
providers. Retiring those fallbacks requires a separate migration which covers every
supported provider and credential source.

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
