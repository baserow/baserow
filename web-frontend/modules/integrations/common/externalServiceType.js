import {
  ServiceType,
  WorkflowActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'
import ExternalServiceForm from '@baserow/modules/integrations/common/components/services/ExternalServiceForm'

/**
 * A workflow action that calls a third party with an integration's
 * credentials. Subclasses name the integration type, the form fields and the
 * translation keys; the shared form renders the fields and this class checks
 * the required ones, so each new action is declarative.
 */
export class ExternalServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  /**
   * The integration type class whose integrations this action uses.
   */
  static get integrationTypeClass() {
    throw new Error('Must be set on the type.')
  }

  /**
   * The key under `serviceType` in the integrations locale, without suffix;
   * `<key>` is the name and `<key>Description` the description.
   */
  static get i18nKey() {
    throw new Error('Must be set on the type.')
  }

  /**
   * The fields the form shows, in order. Each is
   * `{ name, type: 'formula' | 'integer', required, label, placeholder, help }`
   * with the texts as translation keys under `externalServiceForm`.
   */
  get formFields() {
    return []
  }

  get name() {
    return this.app.$i18n.t(`serviceType.${this.constructor.i18nKey}`)
  }

  get description() {
    return this.app.$i18n.t(
      `serviceType.${this.constructor.i18nKey}Description`
    )
  }

  get integrationType() {
    return this.app.$registry.get(
      'integration',
      this.constructor.integrationTypeClass.getType()
    )
  }

  getErrorMessage({ service }) {
    if (service === undefined) {
      return null
    }
    if (!service.integration_id) {
      return this.app.$i18n.t('externalServiceForm.missingIntegration', {
        integration: this.integrationType.name,
      })
    }
    for (const field of this.formFields) {
      if (!field.required) {
        continue
      }
      const value = service[field.name]
      const empty =
        field.type === 'formula'
          ? !value?.formula?.length
          : value === null || value === undefined || value === ''
      if (empty) {
        return this.app.$i18n.t('externalServiceForm.missingField', {
          field: this.app.$i18n.t(field.label),
        })
      }
    }
    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return ExternalServiceForm
  }
}

export const formulaField = (name, label, options = {}) => ({
  name,
  type: 'formula',
  required: options.required === true,
  label: `externalServiceForm.${label}`,
  placeholder: options.placeholder
    ? `externalServiceForm.${options.placeholder}`
    : null,
  help: options.help ? `externalServiceForm.${options.help}` : null,
})

export const integerField = (name, label, options = {}) => ({
  name,
  type: 'integer',
  required: false,
  label: `externalServiceForm.${label}`,
  help: options.help ? `externalServiceForm.${options.help}` : null,
  min: 1,
  max: options.max ?? 250,
})
