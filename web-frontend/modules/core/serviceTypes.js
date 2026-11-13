import { Registerable } from '@baserow/modules/core/registry'
import { ensureInteger } from '@baserow/modules/core/utils/validator'
import { getValueAtPath } from '@baserow/modules/core/utils/object'

// Tells a path a result doesn't hold apart from one holding `null`.
const NO_RESULT_VALUE = Symbol('noResultValue')

export const getCoreGroup = (app) => ({
  id: 'core',
  label: app.$i18n.t('groupedMenu.core'),
  icon: 'iconoir-package',
  iconColor: 'muted-green',
})

export const getFilesGroup = (app) => ({
  id: 'files',
  label: app.$i18n.t('groupedMenu.files'),
  icon: 'iconoir-page',
  iconColor: 'muted-yellow',
})

export const getHTTPGroup = (app) => ({
  id: 'http',
  label: app.$i18n.t('groupedMenu.http'),
  icon: 'iconoir-globe',
  iconColor: 'muted-cyan',
})

export const getWorkflowGroup = (app) => ({
  id: 'workflow',
  label: app.$i18n.t('groupedMenu.workflow'),
  icon: 'iconoir-git-fork',
  iconColor: 'muted-purple',
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

  /**
   * Extra terms a search for this service matches, besides its name and
   * description, e.g. "loop" for the iterator.
   * @returns {string[]}
   */
  get aliases() {
    return []
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
   * The name a service goes by until it is given one, worded from how it is
   * configured, like "Every day at 09:00".
   * @param {object|null} service The service to name.
   * @returns {string} The name, the type's name when nothing more fits.
   */
  getDefaultName(service) {
    return this.name
  }

  /**
   * Whether the service is valid.
   * @param service - The service object.
   * @returns {String} - The error message
   */
  getErrorMessage({ service, workspace = null, application = null }) {
    const deactivatedReason =
      workspace && this.isDeactivatedReason({ workspace })
    if (deactivatedReason) {
      return deactivatedReason
    }

    if (application && service?.integration_id) {
      const integration = this.app.$store.getters[
        'integration/getIntegrationById'
      ](application, service.integration_id)
      if (integration) {
        const integrationType = this.app.$registry.get(
          'integration',
          integration.type
        )
        const integrationError = integrationType.getErrorMessage(integration)
        if (integrationError) {
          return integrationError
        }
      }
    }

    return null
  }

  /**
   * Whether the service is valid.
   * Override `getErrorMessage` instead of this method so an invalid service also
   * provides a user-facing explanation.
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
   * The schema of the context data of the service, like the options of a
   * single select field. Null when the service has no context data.
   */
  getContextDataSchema(service) {
    return null
  }

  /**
   * Returns sample data for the given service.
   */
  getSampleData(service) {
    return service.sample_data || null
  }

  /**
   * Returns the value found at `path` in a result of the service, a dispatch
   * result or a sample of one. Mirrors the backend `get_result_value`: a list
   * service keeps its rows under `results`, so the first path part is the row
   * index and `prepareValuePath` maps the rest.
   *
   * @param {Object} service the service that produced the result.
   * @param {any} result the result to read from.
   * @param {Array<String>} path the path inside the result.
   * @returns the value, or `undefined` when the result holds nothing at that
   *  path. A path holding `null` returns `null`.
   */
  getResultValue(service, result, path) {
    let valuePath = path
    if (this.returnsList(service)) {
      result = result?.results
      if (path.length >= 2) {
        valuePath = [path[0], ...this.prepareValuePath(service, path.slice(1))]
      }
    } else {
      valuePath = this.prepareValuePath(service, path)
    }
    try {
      const value = getValueAtPath(result, valuePath, NO_RESULT_VALUE)
      return value === NO_RESULT_VALUE ? undefined : value
    } catch {
      // The result can be older than the schema, so the path may run through
      // a value that is no longer an object or a list.
      return undefined
    }
  }

  /**
   * Returns the value found at `path` in the service's sample data, i.e. the
   * result of its last test.
   *
   * @param {Object} service the service to read the sample data of.
   * @param {Array<String>} path the path inside the result.
   * @returns the value, or `undefined` when the service has no usable sample
   *  data or the sample holds nothing at that path.
   */
  getSampleValue(service, path) {
    const sample = this.getSampleData(service)
    if (!sample || sample._error !== undefined) {
      return undefined
    }
    return this.getResultValue(service, sample.data, path)
  }

  /**
   * The content type of the sample data returned by this service. Service
   * types returning 'html' get an extra HTML preview tab in the sample data
   * modal, rendering the value of `getSampleDataHtml`.
   */
  getSampleDataContentType(service) {
    return 'json'
  }

  /**
   * The HTML document to render in the sample data modal's HTML tab, for
   * service types whose sample data content type is 'html'.
   */
  getSampleDataHtml(service) {
    return null
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
   * Whether the given service returns a collection of records. By default it's
   * the same for all the services of this type.
   */
  returnsList(service) {
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

    /** Return optional metadata available alongside the source records. */
    getContextDataSchema(service) {
      return service.context_data_schema || null
    }

    /**
     * Whether this data source type is left out of the builder's data source
     * type picker, for types that can be dispatched as data but aren't offered
     * as builder data sources.
     */
    get hiddenInDataSourcePicker() {
      return false
    }

    /**
     * Whether the form of this data source type shows a Test button of its
     * own, using the `dataSourceTest` the data source form provides.
     */
    get hasOwnTestButton() {
      return false
    }

    /**
     * Whether a data source of this type can be tested from its form, to fill
     * the sample data its schema is built from.
     */
    get canBeTested() {
      return false
    }

    /**
     * The image a data source of this type is shown with when it has no
     * integration, whose image it would otherwise be shown with. Without one,
     * the type's icon is shown.
     */
    get image() {
      return null
    }

    /**
     * Why the last test of the data source found no data, when the test still
     * stored what it received: an error the test shows although it succeeded.
     */
    getTestError(service) {
      return null
    }

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
     * Convert record-name endpoint keys back to the value type used by this service.
     */
    parseRecordId(value) {
      return ensureInteger(value)
    }

    /**
     * Returns the JSON-schema type used by this service's record identifiers.
     */
    getRecordIdDataType(service) {
      return 'number'
    }

    /**
     * Some list services use record identifiers that can be displayed without
     * fetching the record name endpoint. Return null to fall back to the endpoint.
     */
    getRecordNameFromId(service, recordId) {
      return null
    }

    /**
     * In a service which returns a list, the fields a collection element, like
     * a table, starts with when this data source is chosen.
     */
    getDefaultCollectionFields(service) {
      return []
    }

    /**
     * The maximum number of records that can be returned by this service
     */
    getMaxResultLimit(service) {
      return null
    }

    /**
     * Whether this list data source supports frontend paging controls.
     */
    supportsPagination(service) {
      return this.returnsList(service)
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
