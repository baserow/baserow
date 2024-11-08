import { BaseAuthProviderType } from '@baserow/modules/core/authProviderTypes'

export class AppAuthProviderType extends BaseAuthProviderType {
  get name() {
    return this.getName()
  }

  /**
   * The form to edit this user source.
   */
  get formComponent() {
    return this.getAdminSettingsFormComponent()
  }
}
