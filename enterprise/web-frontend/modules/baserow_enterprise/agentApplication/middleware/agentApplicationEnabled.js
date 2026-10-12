import { FF_AGENT_BUILDER } from '@baserow_enterprise/agentApplication/constants'

export function requireAgentApplicationEnabled(app) {
  if (!app.$featureFlagIsEnabled(FF_AGENT_BUILDER)) {
    throw createError({ statusCode: 404, message: 'Agent not found.' })
  }
}

export default defineNuxtRouteMiddleware(() =>
  requireAgentApplicationEnabled(useNuxtApp())
)
