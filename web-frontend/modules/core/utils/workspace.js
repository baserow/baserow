import { isSecureURL } from '@baserow/modules/core/utils/string'
import { getCookie, setCookie, deleteCookie } from 'h3'
import { useCookie } from '#app'

// NOTE: this has been deliberately left as `group`. A future task will rename it.
const cookieWorkspaceName = 'baserow_group_id'

export const setWorkspaceCookie = (workspaceId, { $config }) => {
  if (process.SERVER_BUILD) return
  const secure = isSecureURL($config.PUBLIC_WEB_FRONTEND_URL)
  /*$cookies.set(cookieWorkspaceName, workspaceId, {
    path: '/',
    maxAge: 60 * 60 * 24 * 7,
    sameSite: $config.BASEROW_FRONTEND_SAME_SITE_COOKIE,
    secure,
  })*/
  const cookie = useCookie(cookieWorkspaceName, {
    path: '/',
    maxAge: 60 * 60 * 24 * 7,
    sameSite: $config.config.baserowFrontendSameSiteCookie,
    secure,
  })
  cookie.value = workspaceId
}

export const unsetWorkspaceCookie = () => {
  if (process.SERVER_BUILD) return
  const cookie = useCookie(cookieWorkspaceName)
  cookie.value = null
  //deleteCookie(cookieWorkspaceName)
  //$cookies.remove(cookieWorkspaceName)
}

export const getWorkspaceCookie = () => {
  if (process.SERVER_BUILD) return
  return useCookie(cookieWorkspaceName).value
  //return getCookie(cookieWorkspaceName)
  //return $cookies.get(cookieWorkspaceName)
}
