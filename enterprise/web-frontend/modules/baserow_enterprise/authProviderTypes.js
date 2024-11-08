import { AuthProviderType } from '@baserow/modules/core/authProviderTypes'

import SamlLoginAction from '@baserow_enterprise/components/admin/login/SamlLoginAction'
import AuthProviderItem from '@baserow_enterprise/components/admin/AuthProviderItem'
import SamlSettingsForm from '@baserow_enterprise/components/admin/forms/SamlSettingsForm'
import OAuth2SettingsForm from '@baserow_enterprise/components/admin/forms/OAuth2SettingsForm.vue'
import GitLabSettingsForm from '@baserow_enterprise/components/admin/forms/GitLabSettingsForm.vue'
import OpenIdConnectSettingsForm from '@baserow_enterprise/components/admin/forms/OpenIdConnectSettingsForm.vue'
import LoginButton from '@baserow_enterprise/components/admin/login/LoginButton.vue'

import PasswordAuthIcon from '@baserow/modules/core/assets/images/providers/Key.svg'
import SAMLIcon from '@baserow_enterprise/assets/images/providers/LockKey.svg'
import GoogleIcon from '@baserow_enterprise/assets/images/providers/Google.svg'
import FacebookIcon from '@baserow_enterprise/assets/images/providers/Facebook.svg'
import GitHubIcon from '@baserow_enterprise/assets/images/providers/GitHub.svg'
import GitLabIcon from '@baserow_enterprise/assets/images/providers/GitLab.svg'
import OpenIdIcon from '@baserow_enterprise/assets/images/providers/OpenID.svg'
import VerifiedProviderIcon from '@baserow_enterprise/assets/images/providers/VerifiedProviderIcon.svg'

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
    return AuthProviderItem
  }

  getAdminSettingsFormComponent() {
    return null
  }

  getOrder() {
    return 1
  }
}

export const SamlAuthProviderTypeMixin = (Base) =>
  class extends Base {
    static getType() {
      return 'saml'
    }

    getIcon() {
      return SAMLIcon
    }

    getVerifiedIcon() {
      return VerifiedProviderIcon
    }

    getName() {
      return 'SSO SAML provider'
    }

    getProviderName(provider) {
      return `SSO SAML: ${provider.domain}`
    }

    getLoginActionComponent() {
      return SamlLoginAction
    }

    getAdminListComponent() {
      return AuthProviderItem
    }

    getAdminSettingsFormComponent() {
      return SamlSettingsForm
    }

    getRelayStateUrl() {
      return this.app.store.getters['authProviderAdmin/getType'](this.getType())
        .relayStateUrl
    }
    getAcsUrl() {
      return this.app.store.getters['authProviderAdmin/getType'](this.getType())
        .acsUrl
    }

    populateLoginOptions(authProviderOption) {
      const loginOptions = super.populateLoginOptions(authProviderOption)
      return {
        redirectUrl: authProviderOption.redirect_url,
        domainRequired: authProviderOption.domain_required,
        ...loginOptions,
      }
    }

    populate(authProviderType) {
      const populated = super.populate(authProviderType)
      return {
        acsUrl: authProviderType.acs_url,
        relayStateUrl: authProviderType.relay_state_url,
        ...populated,
      }
    }
  }

export class SamlAuthProviderType extends SamlAuthProviderTypeMixin(
  AuthProviderType
) {
  getOrder() {
    return 50
  }
}

export const OAuth2AuthProviderTypeMixin = (Base) =>
  class extends Base {
    getLoginButtonComponent() {
      return LoginButton
    }

    getAdminListComponent() {
      return AuthProviderItem
    }

    getAdminSettingsFormComponent() {
      return OAuth2SettingsForm
    }
    getCallbackUrl(authProvider) {
      if (!authProvider.id) {
        const nextProviderId =
          this.app.store.getters['authProviderAdmin/getNextProviderId']
        return `${this.app.$config.PUBLIC_BACKEND_URL}/api/sso/oauth2/callback/${nextProviderId}/`
      }
      return `${this.app.$config.PUBLIC_BACKEND_URL}/api/sso/oauth2/callback/${authProvider.id}/`
    }

    populateLoginOptions(authProviderOption) {
      const loginOptions = super.populateLoginOptions(authProviderOption)
      return {
        ...loginOptions,
      }
    }

    populate(authProviderType) {
      const populated = super.populate(authProviderType)
      return {
        ...populated,
      }
    }
  }

export class GoogleAuthProviderType extends OAuth2AuthProviderTypeMixin(
  AuthProviderType
) {
  static getType() {
    return 'google'
  }

  getIcon() {
    return GoogleIcon
  }

  getName() {
    return 'Google'
  }

  getProviderName(provider) {
    return provider.name ? provider.name : `Google`
  }

  getOrder() {
    return 50
  }
}

export class FacebookAuthProviderType extends OAuth2AuthProviderTypeMixin(
  AuthProviderType
) {
  static getType() {
    return 'facebook'
  }

  getIcon() {
    return FacebookIcon
  }

  getName() {
    return 'Facebook'
  }

  getProviderName(provider) {
    return provider.name ? provider.name : this.getName()
  }

  getOrder() {
    return 50
  }
}

export class GitHubAuthProviderType extends OAuth2AuthProviderTypeMixin(
  AuthProviderType
) {
  static getType() {
    return 'github'
  }

  getIcon() {
    return GitHubIcon
  }

  getName() {
    return 'GitHub'
  }

  getProviderName(provider) {
    return provider.name ? provider.name : this.getName()
  }

  getOrder() {
    return 50
  }
}

export class GitLabAuthProviderType extends AuthProviderType {
  static getType() {
    return 'gitlab'
  }

  getIcon() {
    return GitLabIcon
  }

  getName() {
    return 'GitLab'
  }

  getProviderName(provider) {
    return provider.name ? provider.name : this.getName()
  }

  getLoginButtonComponent() {
    return LoginButton
  }

  getAdminListComponent() {
    return AuthProviderItem
  }

  getAdminSettingsFormComponent() {
    return GitLabSettingsForm
  }

  getOrder() {
    return 50
  }
}

export class OpenIdConnectAuthProviderType extends OAuth2AuthProviderTypeMixin(
  AuthProviderType
) {
  static getType() {
    return 'openid_connect'
  }

  getIcon() {
    return OpenIdIcon
  }

  getName() {
    return 'OpenID Connect'
  }

  getProviderName(provider) {
    return provider.name ? provider.name : this.getName()
  }

  getAdminSettingsFormComponent() {
    return OpenIdConnectSettingsForm
  }

  getOrder() {
    return 50
  }
}
