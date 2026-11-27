import { useRuntimeConfig } from '#imports'

const FF_ENABLE_ALL = '*'
export const FF_IDENTITIES = 'identities'
export const FF_AGENT_BUILDER = 'agent-builder'
export const FF_USER_TEMPLATES = 'user_templates'

function getFeatureFlags(env) {
  const flags = (env.FEATURE_FLAGS || '')
    .split(',')
    .map((flag) => flag.trim().toLowerCase())
  // Agents run as identities, so turning the agent builder on turns both on.
  return flags.includes(FF_AGENT_BUILDER) ? [...flags, FF_IDENTITIES] : flags
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
