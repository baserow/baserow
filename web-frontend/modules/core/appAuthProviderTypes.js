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

  getAuthToken(userSource, authProvider, route) {
    return null
  }

  handleError(userSource, authProvider, route) {
    return null
  }
}
