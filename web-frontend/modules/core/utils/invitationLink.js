import { getToken, setToken } from '@baserow/modules/core/utils/auth'

export const INVITATION_LINK_AUTHORIZATION_HEADER =
  'Baserow-Invitation-Link-Authorization'
export const INVITATION_LINK_PASSWORD_REQUIRED =
  'ERROR_WORKSPACE_INVITATION_LINK_PASSWORD_REQUIRED'

const cookieKey = (slug) => `invitation_link_${slug}`

/**
 * Remembers the token handed out for the password of an invitation link, in a
 * cookie keyed by the slug, so that it survives the signup or login detour
 * before the visitor comes back to the link.
 */
export const setInvitationLinkToken = (appOrContext, slug, token) =>
  setToken(appOrContext, token, cookieKey(slug))

export const getInvitationLinkToken = async (appOrContext, slug) =>
  (await getToken(appOrContext, cookieKey(slug))) || null

export const invitationLinkHeaders = (token) =>
  token ? { [INVITATION_LINK_AUTHORIZATION_HEADER]: `JWT ${token}` } : {}

export const isInvitationLinkPasswordRequired = (error) => {
  const response = error?.response || error?.handler?.response
  return response?.data?.error === INVITATION_LINK_PASSWORD_REQUIRED
}
