import {
  fetchWorkspacesAndApplications,
  getWorkspaceCookie,
} from '@baserow/modules/core/utils/workspace'

/**
 * This middleware will make sure that all the workspaces and applications belonging to
 * the user are fetched and added to the store.
 */
export default defineNuxtRouteMiddleware(async (to) => {
  const nuxtApp = useNuxtApp()
  const store = nuxtApp.$store
  const event = import.meta.server ? useRequestEvent() : null

  // If nuxt generate, pass this middleware
  if (import.meta.server && !event) return

  let workspaceId = getWorkspaceCookie(nuxtApp)

  // Prefer route param over cookie to avoid double selectById calls on SSR.
  // Pages can opt out or change param by doing:
  // `definePageMeta({ useRouteWorkspaceParam: 'none' }).
  const workspaceIdParam = to.meta.useRouteWorkspaceParam ?? 'workspaceId'
  if (to.params[workspaceIdParam]) {
    const routeWorkspaceId = parseInt(to.params[workspaceIdParam], 10)
    if (!isNaN(routeWorkspaceId)) {
      workspaceId = routeWorkspaceId
    }
  }

  if (store.getters['auth/isAuthenticated']) {
    await fetchWorkspacesAndApplications(nuxtApp, workspaceId)

    // If the user hasn't completed the onboarding, and the doesn't have any workspaces,
    // then redirect to the on-boarding page so that the user can create their first
    // one.
    const user = store.getters['auth/getUserObject']
    const workspaces = store.getters['workspace/getAll']
    if (!user.completed_onboarding && workspaces.length === 0) {
      return nuxtApp.runWithContext(() => navigateTo({ name: 'onboarding' }))
    }
  }
})
