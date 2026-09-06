import { isSecureURL } from '@baserow/modules/core/utils/string'
import { getCookieName } from '@baserow/modules/core/utils/cookie'
import { useCookie } from '#app'

// NOTE: this has been deliberately left as `group`. A future task will rename it.
const cookieWorkspaceName = 'baserow_group_id'

export const setWorkspaceCookie = (workspaceId, appOrContext) => {
  return appOrContext.runWithContext(() => {
    const { $config } = appOrContext
    const secure = isSecureURL($config.public.publicWebFrontendUrl)
    const cookie = useCookie(getCookieName($config, cookieWorkspaceName), {
      path: '/',
      maxAge: 60 * 60 * 24 * 7,
      sameSite: $config.public.baserowFrontendSameSiteCookie,
      secure,
    })
    cookie.value = workspaceId
  })
}

export const unsetWorkspaceCookie = (appOrContext) => {
  return appOrContext.runWithContext(() => {
    const { $config } = appOrContext
    const cookie = useCookie(getCookieName($config, cookieWorkspaceName))
    cookie.value = null
  })
}

export const getWorkspaceCookie = (appOrContext) => {
  return appOrContext.runWithContext(() => {
    const { $config } = appOrContext
    return useCookie(getCookieName($config, cookieWorkspaceName)).value
  })
}

/**
 * Fetches the workspaces and applications of the authenticated user if that hasn't
 * happened yet, and selects the provided workspace, or the first one if it doesn't
 * exist. Shared by the `workspacesAndApplications` middleware and the pages that
 * fetch them without blocking the navigation, so that the remembered workspace is
 * selected regardless of which page loaded them first.
 */
export const fetchWorkspacesAndApplications = async (nuxtApp, workspaceId) => {
  const store = nuxtApp.$store

  if (!store.getters['workspace/isLoaded']) {
    await store.dispatch('workspace/fetchAll')

    const workspaces = store.getters['workspace/getAll']
    const workspaceExists =
      workspaces.find((w) => w.id === workspaceId) !== undefined
    if (!workspaceExists) {
      workspaceId = workspaces.length > 0 ? workspaces[0].id : null
    }

    if (workspaceId) {
      try {
        await store.dispatch('workspace/selectById', workspaceId)
      } catch {}
    }
  }

  if (!store.getters['application/isLoaded']) {
    await store.dispatch('application/fetchAll')
  }
}
