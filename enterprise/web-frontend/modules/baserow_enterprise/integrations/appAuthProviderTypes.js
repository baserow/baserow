import { AppAuthProviderType } from '@baserow/modules/core/appAuthProviderTypes'
import { SamlAuthProviderTypeMixin } from '@baserow_enterprise/authProviderTypes'

import LocalBaserowUserSourceForm from '@baserow_enterprise/integrations/localBaserow/components/appAuthProviders/LocalBaserowPasswordAppAuthProviderForm'
import LocalBaserowAuthPassword from '@baserow_enterprise/integrations/localBaserow/components/appAuthProviders/LocalBaserowAuthPassword'
import CommonSamlSettingForm from '@baserow_enterprise/integrations/common/components/CommonSamlSettingForm'
import SamlAuthLink from '@baserow_enterprise/integrations/common/components/SamlAuthLink'
import { PasswordFieldType } from '@baserow/modules/database/fieldTypes'

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
    return route.query[queryParamName]
  }

  handleError(userSource, authProvider, route) {
    const queryParamName = `saml_error__${userSource.id}`
    const errorCode = route.query[queryParamName]
    if (errorCode) {
      return { message: this.app.i18n.t(`loginError.${errorCode}`), code: 500 }
    }
  }

  getOrder() {
    return 20
  }
}
