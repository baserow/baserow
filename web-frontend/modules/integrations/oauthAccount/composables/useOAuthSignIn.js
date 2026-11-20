import { useNuxtApp } from '#app'
import { useStore } from 'vuex'
import OAuthAccountService from '@baserow/modules/integrations/oauthAccount/services/oauthAccount'
import {
  OAUTH_ERROR_CODE,
  OAUTH_SIGN_IN_TIMEOUT_MS,
  oauthMessageType,
} from '@baserow/modules/integrations/oauthAccount/constants'
import {
  openOAuthPopup,
  waitForOAuthResult,
} from '@baserow/modules/core/utils/oauthPopup'

/** Raised when a sign-in didn't connect an account. */
export class OAuthSignInError extends Error {
  /**
   * @param {string|null} code The API error code, when there's one.
   * @param {string|null} detail Its detail: for an admin consent error, the
   *   URL where an admin approves Baserow.
   */
  constructor(code = null, detail = null) {
    super(code || 'Sign-in not completed')
    this.code = code
    this.detail = detail
  }
}

/**
 * Open the sign-in popup. Call it straight from a click, before any request,
 * or the browser blocks it.
 *
 * @param {string} integrationType The integration type.
 * @returns {Window|null}
 */
export function openOAuthSignInPopup(integrationType) {
  return openOAuthPopup(oauthMessageType(integrationType))
}

/**
 * Signing in, in a popup, for an integration that connects an account, and
 * keeping the integration store up to date with what the sign-in created or
 * connected again.
 *
 * @param {string} integrationType The integration type, e.g. `microsoft`.
 */
export function useOAuthSignIn(integrationType) {
  const { $client } = useNuxtApp()
  const store = useStore()
  const findIntegration = (application, id) =>
    store.getters['integration/getIntegrationById'](application, id)
  const service = OAuthAccountService($client, integrationType)

  /**
   * @param {Object} options
   * @param {Window} options.popup From `openOAuthSignInPopup`.
   * @param {Object} options.application The integration's application.
   * @param {Object} options.integration Connects this integration again;
   *   without it, the sign-in creates one.
   * @param {string[]} options.serviceTypes What the account is connected for.
   * @param {string} options.name The name of the integration to create.
   * @param {AbortSignal} options.signal Gives up on the sign-in.
   * @returns {Promise<{created: boolean, integration: Object}>}
   * @throws {OAuthSignInError} When no account got connected.
   * @throws The API error when the sign-in couldn't start.
   */
  async function signIn({
    popup,
    application,
    integration = null,
    serviceTypes = [],
    name = '',
    signal = null,
  }) {
    if (!popup) {
      // Checked before starting, so no sign-in is left waiting for nothing.
      throw new OAuthSignInError(OAUTH_ERROR_CODE.POPUP_BLOCKED)
    }
    let authorizationUrl
    try {
      const target = integration
        ? { integrationId: integration.id }
        : { applicationId: application.id }
      const { data } = await service.start(target, serviceTypes, name)
      authorizationUrl = data.authorization_url
    } catch (error) {
      popup.close()
      throw error
    }
    popup.location.href = authorizationUrl
    const state = new URL(authorizationUrl).searchParams.get('state')
    let result
    try {
      result = await waitForOAuthResult(
        oauthMessageType(integrationType),
        state,
        {
          signal,
          timeoutMs: OAUTH_SIGN_IN_TIMEOUT_MS,
          // Giving up isn't a failure to report.
          cancelled: () =>
            new OAuthSignInError(OAUTH_ERROR_CODE.SIGN_IN_CANCELLED),
          timedOut: () => new OAuthSignInError(),
        }
      )
    } finally {
      // Some browsers keep the popup open after the callback page closes it.
      popup.close()
    }
    if (result.error || !result.integration) {
      throw new OAuthSignInError(result.error?.code, result.error?.detail)
    }
    await keep(result.integration, result.created, application)
    return { created: result.created, integration: result.integration }
  }

  /**
   * Store an integration a sign-in created or connected again. The backend
   * leaves the tab that started the sign-in out of the real-time event, so
   * it's stored here, once.
   */
  async function keep(data, created, application) {
    const existing = findIntegration(application, data.id)
    if (existing) {
      await store.dispatch('integration/forceUpdate', {
        application,
        integration: existing,
        values: data,
      })
    } else if (created) {
      await store.dispatch('integration/forceCreate', {
        application,
        integration: data,
      })
    }
  }

  /** Forget the tokens of an integration. */
  async function disconnect(application, integration) {
    const { data } = await service.disconnect(integration.id)
    await store.dispatch('integration/forceUpdate', {
      application,
      integration,
      values: data,
    })
    return data
  }

  return { signIn, disconnect, getConfig: () => service.getConfig() }
}
