import { isSecureURL } from '@baserow/modules/core/utils/string'
import { getCookiesInstance } from '@baserow/modules/core/utils/cookies'

// NOTE: this has been deliberately left as `group`. A future task will rename it.
const cookieWorkspaceName = 'baserow_group_id'

export const setWorkspaceCookie = (workspaceId, { $config }) => {
  if (process.SERVER_BUILD) return

  const cookiesInstance = getCookiesInstance()

  const secure = isSecureURL($config.PUBLIC_WEB_FRONTEND_URL)

  cookiesInstance.set(cookieWorkspaceName, workspaceId, {
    path: '/',
    maxAge: 60 * 60 * 24 * 7,
    sameSite: $config.BASEROW_FRONTEND_SAME_SITE_COOKIE,
    secure,
  })
}

export const unsetWorkspaceCookie = () => {
  if (process.SERVER_BUILD) return
  getCookiesInstance().remove(cookieWorkspaceName)
}

export const getWorkspaceCookie = () => {
  if (process.SERVER_BUILD) return
  return getCookiesInstance().get(cookieWorkspaceName)
}
