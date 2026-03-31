/**
 * Redirects from the dashboard to the appropriate workspace page if the user
 * has workspaces. This must run as middleware (not in <script setup>) to avoid
 * chained navigateTo during Suspense, which breaks in Nuxt 3.21+.
 */
export default defineNuxtRouteMiddleware(async (to) => {
  const nuxtApp = useNuxtApp()
  const store = nuxtApp.$store

  const selectedWorkspace = store.getters['workspace/getSelected']
  const allWorkspaces = store.getters['workspace/getAll']

  if (selectedWorkspace?.id) {
    return navigateTo(
      {
        name: 'workspace',
        params: { workspaceId: selectedWorkspace.id },
        query: to.query,
      },
      { replace: true }
    )
  } else if (allWorkspaces?.length > 0) {
    return navigateTo(
      {
        name: 'workspace',
        params: { workspaceId: allWorkspaces[0].id },
        query: to.query,
      },
      { replace: true }
    )
  }
})
