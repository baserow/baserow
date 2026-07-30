import { Registerable } from '@baserow/modules/core/registry'

export const getCoreGroup = (app) => ({
  id: 'core',
  label: app.$i18n.t('groupedMenu.core'),
  icon: 'iconoir-package',
  iconColor: 'var(--palette-green-700)',
})

export const getFilesGroup = (app) => ({
  id: 'files',
  label: app.$i18n.t('groupedMenu.files'),
  icon: 'iconoir-page',
  iconColor: 'var(--palette-yellow-700)',
})

export const getHTTPGroup = (app) => ({
  id: 'http',
  label: app.$i18n.t('groupedMenu.http'),
  icon: 'iconoir-globe',
  iconColor: 'var(--palette-cyan-700)',
})

export const getWorkflowGroup = (app) => ({
  id: 'workflow',
  label: app.$i18n.t('groupedMenu.workflow'),
  icon: 'iconoir-git-fork',
  iconColor: 'var(--palette-purple-700)',
})

export class ServiceType extends Registerable {
  get name() {
    throw new Error('Must be set on the type.')
  }

  /**
   * The integration type necessary to access this service.
   */
  get integrationType() {
    return null
  }

  get group() {
    const integrationType = this.integrationType
    if (!integrationType) {
      return getCoreGroup(this.app)
    }

    return {
      id: `integration-${integrationType.getType()}`,
      label: integrationType.name,
      image: integrationType.image,
      icon: integrationType.iconClass,
      iconColor: integrationType.iconColor,
    }
  }

  /**
   * The form component to edit this service.
   */
  get formComponent() {
    return null
  }

  get icon() {
    return 'iconoir-question-mark'
  }

  get iconColor() {
    return this.group.iconColor
  }

  /**
   * Allow to hook into default values for this service type.
   * @param {object} service the service being edited.
   * @param {object} values the current default values for the service form.
   * @returns an object containing values updated with the default values.
   */
  getDefaultValues(service, values) {
    return values
  }

  /**
   * Whether the service is valid.
   * @param service - The service object.
   * @returns {String} - The error message
   */
  getErrorMessage({ service }) {
    return null
  }

  /**
   * Whether the service is valid.
   * @param service - The service object.
   * @returns {boolean} - If the service is valid.
   */
  isInError(params) {
    return Boolean(this.getErrorMessage(params))
  }

  /**
   * Should return a JSON schema of the data returned by this service.
   */
  getDataSchema(applicationContext, service) {
    throw new Error('Must be set on the type.')
  }

  /**
   * Returns sample data for the given service.
   */
  getSampleData(service) {
    return service.sample_data || null
  }

  /**
   * A hook called prior to an update to modify the new values
   * before they get persisted in the API.
   */
  beforeUpdate(newValues, oldValues) {
    return newValues
  }

  /**
   * Returns a description of the given service
   */
  getDescription(service, application) {
    return this.name
  }

  /**
   * Allow to customize way data are accessed from service
   */
  prepareValuePath(service, path) {
    return path
  }

  /**
   * Whether the service returns a collection of records.
   */
  get returnsList() {
    return false
  }

  isDeactivatedReason({ workspace }) {
    return null
  }

  isDeactivated({ workspace }) {
    return !!this.isDeactivatedReason({ workspace })
  }

  getDeactivatedClickModal({ workspace }) {
    return null
  }

  getOrder() {
    return 0
  }
}

export const DataSourceServiceTypeMixin = (Base) =>
  class extends Base {
    isDataSource = true

    /**
     * In a service which returns a list, this method is used to
     * return the name of the given record.
     */
    getRecordName(service, record) {
      throw new Error('Must be set on the type.')
    }

    /**
     * In a service which returns a list, this method is used to
     * return the id of the given record.
     */
    getIdProperty(service, record) {
      throw new Error('Must be set on the type.')
    }

    /**
     * The maximum number of records that can be returned by this service
     */
    getMaxResultLimit(service) {
      return null
    }

    /**
     * This method can be used to process service data
     * in the frontend when displaying raw data
     * is not enough.
     */
    getResult(service, data) {
      return null
    }
  }

export const WorkflowActionServiceTypeMixin = (Base) =>
  class extends Base {
    isWorkflowAction = true
  }

export const TriggerServiceTypeMixin = (Base) =>
  class extends Base {
    isTrigger = true

    canBeImmediatelyDispatched(service) {
      return false
    }
  }
