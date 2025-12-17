import { UserSourceType } from '@baserow/modules/core/userSourceTypes'
import { LocalBaserowIntegrationType } from '@baserow/modules/integrations/localBaserow/integrationTypes'
import LocalBaserowUserSourceForm from '@baserow_enterprise/integrations/localBaserow/components/userSources/LocalBaserowUserSourceForm'
import localBaserowIntegration from '@baserow/modules/integrations/localBaserow/assets/images/localBaserowIntegration.svg'
import moment from '@baserow/modules/core/moment'

import {
  FormulaFieldType,
  SingleSelectFieldType,
  TextFieldType,
  LongTextFieldType,
  EmailFieldType,
  NumberFieldType,
  UUIDFieldType,
} from '@baserow/modules/database/fieldTypes'

export class LocalBaserowUserSourceType extends UserSourceType {
  static getType() {
    return 'local_baserow'
  }

  get integrationType() {
    return this.app.$registry.get(
      'integration',
      LocalBaserowIntegrationType.getType()
    )
  }

  get name() {
    return this.app.i18n.t('userSourceType.localBaserow')
  }

  get image() {
    return localBaserowIntegration
  }

  /**
   * Returns the allowed field type list for the email field.
   * It's defined here so that it can be changed by a plugin.
   */
  get allowedEmailFieldTypes() {
    return [
      TextFieldType.getType(),
      LongTextFieldType.getType(),
      EmailFieldType.getType(),
    ]
  }

  /**
   * Returns the allowed field type list for the name field.
   * It's defined here so that it can be changed by a plugin.
   */
  get allowedNameFieldTypes() {
    return [
      TextFieldType.getType(),
      LongTextFieldType.getType(),
      EmailFieldType.getType(),
      NumberFieldType.getType(),
      UUIDFieldType.getType(),
    ]
  }

  genUid(userSource) {
    return `${userSource.id}_${userSource.table_id || 0}_${
      userSource.email_field_id || 0
    }_${userSource.role_field_id || 0}`
  }

  /**
   * The Local Baserow user source will only work on tables which are not data-synced.
   * @param {Array} tables - The array of tables to filter.
   * @returns {Array} - The supported tables.
   */
  supportedTables(tables) {
    return tables.filter((table) => !table.is_data_sync)
  }

  /**
   * Returns the allowed field type list for the role field.
   * It's defined here so that it can be changed by a plugin.
   *
   * Please ensure this list is kept in sync with its backend counterpart:
   * `user_source_types.py::LocalBaserowUserSourceType::field_types_allowed_as_role`
   */
  get allowedRoleFieldTypes() {
    return [
      TextFieldType.getType(),
      SingleSelectFieldType.getType(),
      FormulaFieldType.getType(),
    ]
  }

  getSummary(userSource) {
    const application = this.app.store.getters['application/get'](
      userSource.application_id
    )
    const integration = this.app.store.getters[
      'integration/getIntegrationById'
    ](application, userSource.integration_id)

    if (!integration) {
      return this.app.i18n.t('localBaserowUserSourceType.notConfigured')
    }

    const databases = integration.context_data?.databases

    const tableSelected = databases
      .map((database) => database.tables)
      .flat()
      .find(({ id }) => id === userSource.table_id)

    if (!tableSelected) {
      return `${integration.name} - ${this.app.i18n.t(
        'localBaserowUserSourceType.notConfigured'
      )}`
    }

    const summaryParts = [integration.name, tableSelected.name]
    if (!userSource.email_field_id || !userSource.name_field_id) {
      summaryParts.push(
        this.app.i18n.t('localBaserowUserSourceType.notConfigured')
      )
    } else if (userSource.user_count_updated_at !== null) {
      summaryParts.push(
        this.app.i18n.t('userSourceType.userCountSummary', {
          count: userSource.user_count,
          lastUpdated: moment.utc(userSource.user_count_updated_at).fromNow(),
        })
      )
    }
    return summaryParts.join(' - ')
  }

  get formComponent() {
    return LocalBaserowUserSourceForm
  }

  getLoginOptions(userSource) {
    if (!userSource.email_field_id || !userSource.name_field_id) {
      return {}
    }

    return userSource.auth_providers.reduce((acc, authProvider) => {
      if (!acc[authProvider.type]) {
        acc[authProvider.type] = []
      }

      const loginOptions = this.app.$registry
        .get('appAuthProvider', authProvider.type)
        .getLoginOptions(authProvider)

      if (loginOptions) {
        acc[authProvider.type].push(loginOptions)
      }

      return acc
    }, {})
  }

  getOrder() {
    return 10
  }
}
