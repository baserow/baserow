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
