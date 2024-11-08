import { Registerable } from '@baserow/modules/core/registry'
import PasswordAuthIcon from '@baserow/modules/core/assets/images/providers/Key.svg'

/**
 * Base class for authorization provider types
 */
export class BaseAuthProviderType extends Registerable {
  /**
   * The icon for the provider
   */
  getIcon() {
    return null
  }

  /**
   * A human readable name of the application type.
   */
  getName() {
    return null
  }

  /**
   * A human readable name of the application type.
   */
  getProviderName(provider) {
    return null
  }

  /**
   * The component that will be rendered in the SSO admin section
   * where all the providers are listed.
   */
  getAdminListComponent() {
    return null
  }

  /**
   * The sidebar component will be rendered in the sidebar if the application is
   * in the selected workspace. All the applications of a workspace are listed in the
   * sidebar and this component should give the user the possibility to select
   * that application.
   */
  getAdminSettingsComponent() {
    return null
  }

  /**
   * The login link are shown in the login page above the username and
   * password form. This is the place where OAuth2 buttons can be added.
   */
  getLoginButtonComponent() {
    return null
  }

  /**
   * The login actions are shown in the login page below the username and
   * password form. This is the place where SAML or openID link/button can be
   * added.
   */
  getLoginActionComponent() {
    return null
  }

  populateLoginOptions(authProviderOption) {
    return {
      hasLoginButton: this.getLoginButtonComponent() !== null,
      hasLoginAction: this.getLoginActionComponent() !== null,
      ...authProviderOption,
    }
  }

  populate(authProviderType) {
    return {
      type: this.getType(),
      order: this.getOrder(),
      hasAdminSettings: this.getAdminListComponent() !== null,
      canCreateNewProviders: authProviderType.can_create_new,
      canDeleteExistingProviders: authProviderType.can_delete_existing,
      authProviders: authProviderType.auth_providers,
    }
  }

  getOrder() {
    throw new Error('The order of an application type must be set.')
  }
}

/**
 * The authorization provider type base class that can be extended when creating
 * a plugin for the frontend.
 */
export class AuthProviderType extends BaseAuthProviderType {
  constructor(...args) {
    super(...args)
    this.type = this.getType()
    this.icon = this.getIcon()

    if (this.type === null) {
      throw new Error('The type name of a provider type must be set.')
    }
    if (this.icon === null) {
      throw new Error('The icon of a provider type must be set.')
    }
    if (this.name === null) {
      throw new Error('The name of a provider type must be set.')
    }
  }

  /**
   * @return object
   */
  serialize() {
    return {
      type: this.type,
      iconClass: this.iconClass,
      name: this.getName(),
      routeName: this.routeName,
    }
  }
}

export class PasswordAuthProviderType extends AuthProviderType {
  static getType() {
    return 'password'
  }

  getIcon() {
    return PasswordAuthIcon
  }

  getName() {
    return this.app.i18n.t('authProviderTypes.password')
  }

  getProviderName(provider) {
    return this.getName()
  }

  getAdminListComponent() {
    return null
  }

  getAdminSettingsFormComponent() {
    return null
  }

  getOrder() {
    return 1
  }
}
