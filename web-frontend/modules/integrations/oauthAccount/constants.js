/**
 * The message an integration type's sign-in callback page sends, also its
 * channel's name, e.g. `baserow-microsoft-oauth`.
 *
 * @param {string} integrationType The integration type.
 * @returns {string}
 */
export function oauthMessageType(integrationType) {
  return `baserow-${integrationType}-oauth`
}

/**
 * Whether a value can be an integration type name. The callback page reads it
 * from its URL, so it's checked before it's put in an API path.
 *
 * @param {string} value
 * @returns {boolean}
 */
export function isIntegrationTypeName(value) {
  return typeof value === 'string' && /^[a-z0-9_]+$/.test(value)
}

// As long as the backend keeps a started sign-in.
export const OAUTH_SIGN_IN_TIMEOUT_MS = 600000

export const OAUTH_ERROR_CODE = {
  NOT_CONFIGURED: 'ERROR_OAUTH_NOT_CONFIGURED',
  STATE_INVALID: 'ERROR_OAUTH_STATE_INVALID',
  FAILED: 'ERROR_OAUTH_FAILED',
  SIGN_IN_CANCELLED: 'ERROR_OAUTH_SIGN_IN_CANCELLED',
  ADMIN_CONSENT_REQUIRED: 'ERROR_OAUTH_ADMIN_CONSENT_REQUIRED',
  TENANT_NOT_ALLOWED: 'ERROR_OAUTH_TENANT_NOT_ALLOWED',
  CLIENT_REJECTED: 'ERROR_OAUTH_CLIENT_REJECTED',
  ACCOUNT_MISMATCH: 'ERROR_OAUTH_ACCOUNT_MISMATCH',
  SERVICE_TYPE_NOT_ALLOWED: 'ERROR_OAUTH_SERVICE_TYPE_NOT_ALLOWED',
  // Not an API error: the browser didn't open the sign-in window.
  POPUP_BLOCKED: 'POPUP_BLOCKED',
}
