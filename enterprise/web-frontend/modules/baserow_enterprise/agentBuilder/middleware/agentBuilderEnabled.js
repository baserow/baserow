import { FF_AGENT_BUILDER } from '@baserow_enterprise/agentBuilder/constants'

export function requireAgentBuilderEnabled(app) {
  if (!app.$featureFlagIsEnabled(FF_AGENT_BUILDER)) {
    throw createError({ statusCode: 404, message: 'Agent Builder not found.' })
  }
}

export default defineNuxtRouteMiddleware(() =>
  requireAgentBuilderEnabled(useNuxtApp())
)
