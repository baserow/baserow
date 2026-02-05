import { useRuntimeConfig } from '#imports'

const FF_ENABLE_ALL = '*'

function getFeatureFlags(env) {
  return (env.FEATURE_FLAGS || '')
    .split(',')
    .map((flag) => flag.trim().toLowerCase())
}

function featureFlagIsEnabled(featureFlags, flag) {
  if (featureFlags.includes(FF_ENABLE_ALL)) {
    return true
  } else {
    return featureFlags.includes(flag.toLowerCase())
  }
}

export default defineNuxtPlugin(() => {
  const runtimeConfig = useRuntimeConfig()
  const featureFlagsValue = runtimeConfig.public.featureFlags
  const FEATURE_FLAGS = getFeatureFlags({
    ...runtimeConfig.public,
    FEATURE_FLAGS: featureFlagsValue,
  })

  return {
    provide: {
      featureFlagIsEnabled: (flag) => featureFlagIsEnabled(FEATURE_FLAGS, flag),
    },
  }
})
