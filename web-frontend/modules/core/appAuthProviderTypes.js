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
   * Return an error message potentially extracted from query params.
   * @param {*} userSource
   * @param {*} authProvider
   * @param {*} route
   * @returns
   */
  handleError(userSource, authProvider, route) {
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
