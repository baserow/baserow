import { BaseAuthProviderType } from '@baserow/modules/core/authProviderTypes'

export class AppAuthProviderType extends BaseAuthProviderType {
  get name() {
    return this.getName()
  }

  getLoginOptions(authProvider) {
    return null
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

  /**
   * Return an auth token potentially extracted from the route query params.
   * @param {*} userSource
   * @param {*} authProvider
   * @param {*} route
   * @returns
   */
  getAuthToken(userSource, authProvider, route) {
    return null
  }

  /**
   * After an SSO login fails, the provider redirects back to the app with an error
   * code in a query parameter. This returns a translated, user-facing message for
   * that error (to be shown near the auth form) and clears the parameter from the
   * URL, or `null` when there is no error for the given user source.
   * @param {Object} userSource The user source the auth form is bound to.
   * @param {Object} route The current route, whose query is inspected.
   * @returns {string|null}
   */
  getLoginError(userSource, route) {
    return null
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
