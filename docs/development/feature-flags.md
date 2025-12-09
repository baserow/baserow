# Feature flags

Baserow uses basic feature flags currently to allow unfinished features to be merged
and/or released.

## Available Feature Flags

Add/remove features flags to the list below:

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
    someComponentMethod()
    {
        if (this.$featureFlagIsEnabled(FF_FEATURE1)){
            // do the feature
        }
    }
}
```

