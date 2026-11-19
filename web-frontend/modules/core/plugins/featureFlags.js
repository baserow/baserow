import { useRuntimeConfig } from '#imports'

export const FF_DASHBOARD_FILTERS = 'dashboard-filters'
const FF_ENABLE_ALL = '*'
export const FF_IDENTITIES = 'identities'
export const FF_AGENT_BUILDER = 'agent-builder'
export const FF_RBAC_IMPROVEMENTS = 'rbac_improvements'
export const FF_APPLICATION_IN_ERROR = 'application_in_error'
export const FF_USER_TEMPLATES = 'user_templates'

function getFeatureFlags(env) {
  return (env.FEATURE_FLAGS || '')
    .split(',')
    .map((flag) => flag.trim().toLowerCase())
}

export function featureFlagIsEnabled(featureFlags, flag, store) {
  const name = flag.toLowerCase()
  if (featureFlags.includes(FF_ENABLE_ALL) || featureFlags.includes(name)) {
    return true
  }
  // Sign-out keeps the last user's additional data in the store.
  if (!store.getters['auth/isAuthenticated']) {
    return false
  }
  const userFlags = store.getters['auth/getAdditionalUserData'].feature_flags
  return Boolean(userFlags?.includes(name))
}

export default defineNuxtPlugin({
  name: 'feature-flags',
  dependsOn: ['create-store'],
  setup(nuxtApp) {
    const runtimeConfig = useRuntimeConfig()
    const featureFlagsValue = runtimeConfig.public.featureFlags
    const FEATURE_FLAGS = getFeatureFlags({
      ...runtimeConfig.public,
      FEATURE_FLAGS: featureFlagsValue,
    })

    return {
      provide: {
        featureFlagIsEnabled: (flag) =>
          featureFlagIsEnabled(FEATURE_FLAGS, flag, nuxtApp.$store),
      },
    }
  },
})
