import { getWorkspaceCookie } from '@baserow/modules/core/utils/workspace'

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

  // Prioritize workspaceId from route params if navigating to a workspace page.
  // This ensures SSR and client select the same workspace, avoiding hydration mismatch.
  let workspaceId = to.params.workspaceId
    ? parseInt(to.params.workspaceId, 10)
    : getWorkspaceCookie(nuxtApp)

  // If the workspaces haven't already been selected we will
  if (store.getters['auth/isAuthenticated']) {
    // If the workspaces haven't been loaded we will load them all.
    if (!store.getters['workspace/isLoaded']) {
      await store.dispatch('workspace/fetchAll')

      const workspaces = store.getters['workspace/getAll']
      const workspaceExists =
        workspaces.find((w) => w.id === workspaceId) !== undefined
      if (!workspaceExists) {
        workspaceId = null
      }

      // If no workspace was remembered, or the remembered workspace doesn't exist, we
      // automatically select the first one if it
      // exists.
      if (!workspaceExists && store.getters['workspace/getAll'].length > 0) {
        workspaceId = workspaces[0].id
      }

      // If there is a workspaceId cookie we will select that workspace.
      if (workspaceId) {
        try {
          await store.dispatch('workspace/selectById', workspaceId)
        } catch {}
      }
    }
    // If the applications haven't been loaded we will also load them all.
    if (!store.getters['application/isLoaded']) {
      await store.dispatch('application/fetchAll')
    }

    // If the user hasn't completed the onboarding, and the doesn't have any workspaces,
    // then redirect to the on-boarding page so that the user can create their first
    // one.
    const user = store.getters['auth/getUserObject']
    const workspaces = store.getters['workspace/getAll']
    if (!user.completed_onboarding && workspaces.length === 0) {
      return navigateTo({ name: 'onboarding' })
    }
  }
})

/*
Previous Nuxt 2 middleware:
export default async function WorkspacesAndApplications({
  store,
  req,
  app,
  redirect,
}) {
  // If nuxt generate, pass this middleware
  if (import.meta.server && !req) return

  // Get the selected workspace id
  let workspaceId = getWorkspaceCookie(app)

  // If the workspaces haven't already been selected we will
  if (store.getters['auth/isAuthenticated']) {
    // If the workspaces haven't been loaded we will load them all.
    if (!store.getters['workspace/isLoaded']) {
      await store.dispatch('workspace/fetchAll')

      const workspaces = store.getters['workspace/getAll']
      const workspaceExists =
        workspaces.find((w) => w.id === workspaceId) !== undefined
      if (!workspaceExists) {
        workspaceId = null
      }

      // If no workspace was remembered, or the remembered workspace doesn't exist, we
      // automatically select the first one if it
      // exists.
      if (!workspaceExists && store.getters['workspace/getAll'].length > 0) {
        workspaceId = workspaces[0].id
      }

      // If there is a workspaceId cookie we will select that workspace.
      if (workspaceId) {
        try {
          await store.dispatch('workspace/selectById', workspaceId)
        } catch {}
      }
    }
    // If the applications haven't been loaded we will also load them all.
    if (!store.getters['application/isLoaded']) {
      await store.dispatch('application/fetchAll')
    }

    // If the user hasn't completed the onboarding, and the doesn't have any workspaces,
    // then redirect to the on-boarding page so that the user can create their first
    // one.
    const user = store.getters['auth/getUserObject']
    const workspaces = store.getters['workspace/getAll']
    if (!user.completed_onboarding && workspaces.length === 0) {
      return redirect({ name: 'onboarding' })
    }
  }
}
*/
