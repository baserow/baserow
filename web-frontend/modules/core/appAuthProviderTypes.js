import { BaseAuthProviderType } from '@baserow/modules/core/authProviderTypes'

export class AppAuthProviderType extends BaseAuthProviderType {
  get name() {
    return this.getName()
  }

  getLoginOptions(authProvider) {
    return null
  }

  isConfigured() {
    return true
  }

  get component() {
    return null
  }

  /**
   * The form to edit this user source.
   */
  get formComponent() {
    return this.getAdminSettingsFormComponent()
  }

  getAuthProviderCallbackQueryParamName(userSource) {
    return null
  }

  getAuthProviderCallbackErrorQueryParamName(userSource) {
    return null
  }

  formatAuthProviderCallbackError(errorCode) {
    return null
  }

  getAuthProviderCallbackQueryParamNames(url) {
    return []
  }

  /**
   * Parses this provider's callback parameters for a specific user source.
   *
   * A callback is accepted only when it contains exactly one non-empty token or
   * one non-empty error. Duplicate values and callbacks containing both are
   * rejected. The returned parameter names let callers remove only the values
   * consumed by this provider from the URL.
   *
   * @param {Object} userSource The user source targeted by the callback.
   * @param {URL} url The callback URL to parse without modifying it.
   * @returns {{sourceId: number, token: string|null, error: Object|null,
   * queryParamNames: string[]}|null} The parsed callback, or null when the URL
   * does not contain a valid callback for this provider and user source.
   */
  getAuthProviderCallback(userSource, url) {
    const tokenParamName =
      this.getAuthProviderCallbackQueryParamName(userSource)
    const errorParamName =
      this.getAuthProviderCallbackErrorQueryParamName(userSource)
    const tokenValues = tokenParamName
      ? url.searchParams.getAll(tokenParamName)
      : []
    const errorValues = errorParamName
      ? url.searchParams.getAll(errorParamName)
      : []
    if (
      tokenValues.length > 1 ||
      errorValues.length > 1 ||
      (tokenValues.length === 1 && errorValues.length === 1)
    ) {
      return null
    }
    if (tokenValues.length === 1 && tokenValues[0].length > 0) {
      return {
        sourceId: userSource.id,
        token: tokenValues[0],
        error: null,
        queryParamNames: [tokenParamName],
      }
    }
    if (errorValues.length !== 1 || errorValues[0].length === 0) {
      return null
    }
    const error = this.formatAuthProviderCallbackError(errorValues[0])
    if (!error) {
      return null
    }
    return {
      sourceId: userSource.id,
      token: null,
      error,
      queryParamNames: [errorParamName],
    }
  }

  /**
   * Returns whether the provider is enabled or not.
   * @param {Number} workspaceId The workspace id.
   * @returns {Boolean} True if the provider is disabled, false otherwise.
   */
  isDeactivated(workspaceId) {
    return false
  }
}
