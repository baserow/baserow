import { OAUTH_ERROR_CODE } from '@baserow/modules/integrations/oauthAccount/constants'

const MESSAGES = {
  [OAUTH_ERROR_CODE.NOT_CONFIGURED]: 'oauthAccountErrors.notConfigured',
  [OAUTH_ERROR_CODE.STATE_INVALID]: 'oauthAccountErrors.stateInvalid',
  [OAUTH_ERROR_CODE.SIGN_IN_CANCELLED]: 'oauthAccountErrors.cancelled',
  [OAUTH_ERROR_CODE.ADMIN_CONSENT_REQUIRED]:
    'oauthAccountErrors.adminConsentRequired',
  [OAUTH_ERROR_CODE.TENANT_NOT_ALLOWED]: 'oauthAccountErrors.tenantNotAllowed',
  [OAUTH_ERROR_CODE.CLIENT_REJECTED]: 'oauthAccountErrors.clientRejected',
  [OAUTH_ERROR_CODE.ACCOUNT_MISMATCH]: 'oauthAccountErrors.accountMismatch',
  [OAUTH_ERROR_CODE.SERVICE_TYPE_NOT_ALLOWED]:
    'oauthAccountErrors.serviceTypeNotAllowed',
  [OAUTH_ERROR_CODE.POPUP_BLOCKED]: 'oauthAccountErrors.popupBlocked',
}

/**
 * What to tell the person when a sign-in failed.
 *
 * @param {Function} t The translate function.
 * @param {string|null} code The API error code, null when none came back.
 * @param {string} provider The provider's name, e.g. `Microsoft`.
 * @returns {string}
 */
export function oauthErrorMessage(t, code, provider) {
  return t(MESSAGES[code] || 'oauthAccountErrors.failed', { provider })
}
