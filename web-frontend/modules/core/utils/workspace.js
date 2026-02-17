import { isSecureURL } from '@baserow/modules/core/utils/string'
import { useCookie } from '#app'

// NOTE: this has been deliberately left as `group`. A future task will rename it.
const cookieWorkspaceName = 'baserow_group_id'

export const setWorkspaceCookie = (workspaceId, { $config }) => {
  const secure = isSecureURL($config.public.publicWebFrontendUrl)
  const cookie = useCookie(cookieWorkspaceName, {
    path: '/',
    maxAge: 60 * 60 * 24 * 7,
    sameSite: $config.public.baserowFrontendSameSiteCookie,
    secure,
  })
  cookie.value = workspaceId
}

export const unsetWorkspaceCookie = () => {
  const cookie = useCookie(cookieWorkspaceName)
  cookie.value = null
}

export const getWorkspaceCookie = () => {
  return useCookie(cookieWorkspaceName).value
}
