/*const FF_ENABLE_ALL = '*'

/**
 * A comma separated list of feature flags used to enable in-progress or not ready
 * features for developers. See docs/development/feature-flags.md for more info
 * @param env The environment that should be used to get the flags from
 * @returns {string[]}
 *\/
function getFeatureFlags(env = process.env) {
  return (env.FEATURE_FLAGS || '')
    .split(',')
    .map((flag) => flag.trim().toLowerCase())
}

/**
 * Checks if a feature is enabled
 * @param featureFlags The list of feature flags
 * @param flag The flag that is being checked for
 * @returns {boolean|*}
 *\/
function featureFlagIsEnabled(featureFlags, flag) {
  if (featureFlags.includes(FF_ENABLE_ALL)) {
    return true
  } else {
    return featureFlags.includes(flag.toLowerCase())
  }
}

export default function ({ app }, inject) {
  const FEATURE_FLAGS = getFeatureFlags(app.$config)

  inject('featureFlagIsEnabled', (flag) =>
    featureFlagIsEnabled(FEATURE_FLAGS, flag)
  )
}
*/

import { useRuntimeConfig } from '#imports'

const FF_ENABLE_ALL = '*'

function getFeatureFlags(env = process.env) {
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
