import { AppAuthProviderType } from '@baserow/modules/core/appAuthProviderTypes'
import {
  SamlAuthProviderTypeMixin,
  OAuth2AuthProviderTypeMixin,
} from '@baserow_enterprise/authProviderTypes'

import LocalBaserowUserSourceForm from '@baserow_enterprise/integrations/localBaserow/components/appAuthProviders/LocalBaserowPasswordAppAuthProviderForm'
import LocalBaserowAuthPassword from '@baserow_enterprise/integrations/localBaserow/components/appAuthProviders/LocalBaserowAuthPassword'
import CommonSamlSettingForm from '@baserow_enterprise/integrations/common/components/CommonSamlSettingForm'
import CommonOIDCSettingForm from '@baserow_enterprise/integrations/common/components/CommonOIDCSettingForm'
import SamlAuthLink from '@baserow_enterprise/integrations/common/components/SamlAuthLink'
import OIDCAuthLink from '@baserow_enterprise/integrations/common/components/OIDCAuthLink'
import OpenIdIcon from '@baserow_enterprise/assets/images/providers/OpenID.svg'
import { PasswordFieldType } from '@baserow/modules/database/fieldTypes'
import EnterpriseFeatures from '@baserow_enterprise/features'

export class LocalBaserowPasswordAppAuthProviderType extends AppAuthProviderType {
  static getType() {
    return 'local_baserow_password'
  }

  get name() {
    return this.app.i18n.t('appAuthProviderType.localBaserowPassword')
  }

  get component() {
    return LocalBaserowAuthPassword
  }

  get formComponent() {
    return LocalBaserowUserSourceForm
  }

  /**
   * Returns the allowed field type list for the password field.
   * It's defined here so that it can be changed by a plugin.
   */
  get allowedPasswordFieldTypes() {
    return [PasswordFieldType.getType()]
  }

  getLoginOptions(authProvider) {
    if (authProvider.password_field_id) {
      return {}
    }
    return null
  }

  /**
   * We can create only one password provider.
   */
  canCreateNew(appAuthProviders) {
    return (
      !appAuthProviders[this.getType()] ||
      appAuthProviders[this.getType()].length === 0
    )
  }

  getOrder() {
    return 10
  }
}

export class SamlAppAuthProviderType extends SamlAuthProviderTypeMixin(
  AppAuthProviderType
) {
  get name() {
    return this.app.i18n.t('appAuthProviderType.commonSaml')
  }

  get component() {
    return SamlAuthLink
  }

  get formComponent() {
    return CommonSamlSettingForm
  }

  handleServerError(vueComponentInstance, error) {
    if (error.handler.code !== 'ERROR_REQUEST_BODY_VALIDATION') return false

    if (error.handler.detail?.auth_providers?.length > 0) {
      const flatProviders = Object.entries(vueComponentInstance.authProviders)
        .map(([, providers]) => providers)
        .flat()
        // Sort per ID to make sure we have the same order
        // as the backend
        .sort((a, b) => a.id - b.id)

      for (const [
        index,
        authError,
      ] of error.handler.detail.auth_providers.entries()) {
        if (
          Object.keys(authError).length > 0 &&
          flatProviders[index].id === vueComponentInstance.authProvider.id
        ) {
          vueComponentInstance.serverErrors = {
            ...vueComponentInstance.serverErrors,
            ...authError,
          }
          return true
        }
      }
    }

    return false
  }

  getAuthToken(userSource, authProvider, route) {
    // token can be in the query string (SSO) or in the cookies (previous session)
    // We use the user source id in order to prevent conflicts when using multiple
    // auth forms on the same page.
    const queryParamName = `user_source_saml_token__${userSource.id}`
    const found = route.query[queryParamName]
    if (found) {
      const currentUrl = new URL(window.location.href)
      currentUrl.searchParams.delete(queryParamName)
      window.history.replaceState({}, document.title, currentUrl.toString())
    }
    return found
  }

  handleError(userSource, authProvider, route) {
    const queryParamName = `saml_error__${userSource.id}`
    const errorCode = route.query[queryParamName]
    if (errorCode) {
      return { message: this.app.i18n.t(`loginError.${errorCode}`), code: 500 }
    }
  }

  getRelayStateUrls(userSource) {
    const application = this.app.store.getters['application/get'](
      userSource.application_id
    )
    const applicationType = this.app.$registry.get(
      'application',
      application.type
    )
    return applicationType.getFrontendUrls()
  }

  getAcsUrl(userSource) {
    return `${this.app.$config.PUBLIC_BACKEND_URL}/api/user-source/sso/saml/acs/`
  }

  getOrder() {
    return 20
  }

  /**
   * `SamlAppAuthProviderType` requires the `BUILDER_SSO` feature to be enabled.
   * @param {Number} workspaceId The workspace id.
   * @returns {Boolean} True if the provider is disabled, false otherwise.
   */
  isDeactivated(workspaceId) {
    return !this.app.$hasFeature(EnterpriseFeatures.BUILDER_SSO, workspaceId)
  }
}

export class OpenIdConnectAppAuthProviderType extends OAuth2AuthProviderTypeMixin(
  AppAuthProviderType
) {
  static getType() {
    return 'openid_connect'
  }

  getIcon() {
    return OpenIdIcon
  }

  getName() {
    return this.app.i18n.t('appAuthProviderType.openIdConnect')
  }

  getProviderName(provider) {
    if (provider.name) {
      return provider.name
    } else {
      return this.app.i18n.t(
        'authProviderTypes.ssoOIDCProviderNameUnconfigured'
      )
    }
  }

  get component() {
    return OIDCAuthLink
  }

  get formComponent() {
    return CommonOIDCSettingForm
  }

  getAuthToken(userSource, authProvider, route, router) {
    // token can be in the query string (SSO) or in the cookies (previous session)
    // We use the user source id in order to prevent conflicts when using multiple
    // auth forms on the same page.
    const queryParamName = `user_source_oidc_token__${userSource.id}`
    const found = route.query[queryParamName]
    if (found) {
      const currentUrl = new URL(window.location.href)
      currentUrl.searchParams.delete(queryParamName)
      window.history.replaceState({}, document.title, currentUrl.toString())
    }
    return found
  }

  handleServerError(vueComponentInstance, error) {
    if (error.handler.code !== 'ERROR_REQUEST_BODY_VALIDATION') return false

    if (error.handler.detail?.auth_providers?.length > 0) {
      const flatProviders = Object.entries(vueComponentInstance.authProviders)
        .map(([, providers]) => providers)
        .flat()
        // Sort per ID to make sure we have the same order
        // as the backend
        .sort((a, b) => a.id - b.id)

      for (const [
        index,
        authError,
      ] of error.handler.detail.auth_providers.entries()) {
        if (
          Object.keys(authError).length > 0 &&
          flatProviders[index].id === vueComponentInstance.authProvider.id
        ) {
          vueComponentInstance.serverErrors = {
            ...vueComponentInstance.serverErrors,
            ...authError,
          }
          return true
        }
      }
    }

    return false
  }

  getOrder() {
    return 50
  }

  /**
   * `OpenIdConnectAppAuthProviderType` requires the `BUILDER_SSO` feature to be enabled.
   * @param {Number} workspaceId The workspace id.
   * @returns {Boolean} True if the provider is disabled, false otherwise.
   */
  isDeactivated(workspaceId) {
    return !this.app.$hasFeature(EnterpriseFeatures.BUILDER_SSO, workspaceId)
  }
}
