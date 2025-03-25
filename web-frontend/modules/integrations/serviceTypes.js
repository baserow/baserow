import { ServiceType } from '@baserow/modules/core/serviceTypes'
import { LocalBaserowIntegrationType } from '@baserow/modules/integrations/integrationTypes'
import LocalBaserowGetRowForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowGetRowForm'
import LocalBaserowListRowsForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowListRowsForm'
import LocalBaserowAggregateRowsForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowAggregateRowsForm'
import { uuid } from '@baserow/modules/core/utils/string'
import LocalBaserowAdhocHeader from '@baserow/modules/integrations/localBaserow/components/integrations/LocalBaserowAdhocHeader'
import { DistributionViewAggregationType } from '@baserow/modules/database/viewAggregationTypes'

export class LocalBaserowTableServiceType extends ServiceType {
  get integrationType() {
    return this.app.$registry.get(
      'integration',
      LocalBaserowIntegrationType.getType()
    )
  }

  /**
   * Responsible for determining if this service is in error. It will be if the
   * `table_id` is missing, or if one or more filters/sortings point to a field that
   * has been trashed.
   * @param service - The service object.
   * @returns {boolean} - If the service is valid.
   */
  isInError({ service }) {
    if (service === undefined) {
      return false
    }
    const filtersInError = service.filters.some((filter) => filter.trashed)
    const sortingsInError = service.sortings.some((sorting) => sorting.trashed)
    return Boolean(!service.table_id || filtersInError || sortingsInError)
  }

  getDataSchema(service) {
    return service.schema
  }

  getContextDataSchema(service) {
    return service.context_data_schema
  }

  getIdProperty(service, record) {
    return 'id'
  }

  /**
   * Responsible for returning the description of the service. This is used in
   * the UI to display a human-readable description of the service.
   *
   * @param service - The service object.
   * @param application - The application object.
   * @returns {string} - The description of the service.
   */
  getDescription(service, application) {
    const integration = this.app.store.getters[
      'integration/getIntegrationById'
    ](application, service.integration_id)

    const databases = integration?.context_data?.databases || []

    const tableSelected = databases
      .map((database) => database.tables)
      .flat()
      .find(({ id }) => id === service.table_id)

    let description = this.name
    if (service.table_id && tableSelected) {
      description += `- ${tableSelected.name}`
    }

    if (this.isInError({ service })) {
      description += ` - ${this.app.i18n.t('serviceType.misconfigured')}`
    }

    return description
  }
}

export class LocalBaserowGetRowServiceType extends LocalBaserowTableServiceType {
  static getType() {
    return 'local_baserow_get_row'
  }

  get name() {
    return this.app.i18n.t('serviceType.localBaserowGetRow')
  }

  get formComponent() {
    return LocalBaserowGetRowForm
  }

  /**
   * A hook called prior to an update to modify the filters and
   * sortings if the `table_id` changes from one ID to another.
   * The same behavior happens in the backend, this reset is to
   * make the filter/sort components reset properly.
   */
  beforeUpdate(newValues, oldValues) {
    if (
      oldValues.table_id !== null &&
      newValues.table_id !== oldValues.table_id
    ) {
      newValues.filters = []
      newValues.sortings = []
    }
    return newValues
  }

  getOrder() {
    return 10
  }
}

export class LocalBaserowListRowsServiceType extends LocalBaserowTableServiceType {
  static getType() {
    return 'local_baserow_list_rows'
  }

  get name() {
    return this.app.i18n.t('serviceType.localBaserowListRows')
  }

  get formComponent() {
    return LocalBaserowListRowsForm
  }

  /**
   * The Local Baserow adhoc filtering, sorting and searching component.
   */
  get adhocHeaderComponent() {
    return LocalBaserowAdhocHeader
  }

  get returnsList() {
    return true
  }

  get maxResultLimit() {
    return 100
  }

  /**
   * A hook called prior to an update to modify the filters and
   * sortings if the `table_id` changes from one ID to another.
   * The same behavior happens in the backend, this reset is to
   * make the filter/sort components reset properly.
   */
  beforeUpdate(newValues, oldValues) {
    if (
      oldValues.table_id !== null &&
      newValues.table_id !== oldValues.table_id
    ) {
      newValues.filters = []
      newValues.sortings = []
    }
    return newValues
  }

  getDefaultCollectionFields(service) {
    return Object.keys(service.schema.items.properties)
      .filter(
        (field) =>
          field !== 'id' &&
          service.schema.items.properties[field].original_type !== 'formula' // every formula has different properties
      )
      .map((field) => {
        const type = service.schema.items.properties[field].type
        const originalType =
          service.schema.items.properties[field].original_type
        let outputType = 'text'
        let valueFormula = `get('current_record.${field}')`
        if (originalType === 'boolean') {
          outputType = 'boolean'
        } else if (originalType === 'url') {
          return {
            link_name: valueFormula,
            name: service.schema.items.properties[field].title,
            id: uuid(), // Temporary id
            navigate_to_page_id: null,
            navigate_to_url: valueFormula,
            navigation_type: 'custom',
            page_parameters: [],
            target: 'blank',
            type: 'link',
          }
        } else if (originalType === 'file') {
          return {
            id: uuid(),
            name: service.schema.items.properties[field].title,
            type: 'image',
            src: `get('current_record.${field}.*.url')`,
            alt: `get('current_record.${field}.*.visible_name')`,
          }
        } else if (
          originalType === 'last_modified_by' ||
          originalType === 'created_by'
        ) {
          valueFormula = `get('current_record.${field}.name')`
        } else if (originalType === 'single_select') {
          valueFormula = `get('current_record.${field}.value')`
        }
        if (originalType === 'multiple_collaborators') {
          valueFormula = `get('current_record.${field}.*.name')`
        } else if (type === 'array') {
          valueFormula = `get('current_record.${field}.*.value')`
        }
        return {
          name: service.schema.items.properties[field].title,
          type: outputType,
          value: valueFormula,
          id: uuid(), // Temporary id
        }
      })
  }

  getRecordName(service, record) {
    // We skip row_id and order properties here, so we keep only first key
    // that should be the primary field
    // [{ field_1234: 'The name of the record', id: 0, __idx__: 0 }]
    // NOTE: This is assuming that the first field is the primary field.
    const field = Object.keys(record).find((key) => key.startsWith('field_'))
    return record[field]
  }

  getOrder() {
    return 20
  }
}

export class LocalBaserowAggregateRowsServiceType extends LocalBaserowTableServiceType {
  static getType() {
    return 'local_baserow_aggregate_rows'
  }

  get name() {
    return this.app.i18n.t('serviceType.localBaserowAggregateRows')
  }

  get formComponent() {
    return LocalBaserowAggregateRowsForm
  }

  /**
   * Local Baserow aggregate rows does not currently support the distribution
   * aggregation type, this will be resolved in a future release.
   */
  get unsupportedAggregationTypes() {
    return [DistributionViewAggregationType.getType()]
  }

  getResult(service, data) {
    if (data && data.result !== undefined && service !== undefined) {
      const field = service.context_data.field
      const fieldType = this.app.$registry.get('field', field.type)
      const aggregationType = this.app.$registry.get(
        'viewAggregation',
        service.aggregation_type
      )
      const formattedResult = aggregationType.formatValue(data.result, {
        field,
        fieldType,
      })
      return formattedResult
    }
    return null
  }

  isInError({ service }) {
    if (service === undefined) {
      return false
    }
    const filtersInError = service.filters.some((filter) => filter.trashed)
    return Boolean(
      !service.table_id ||
        !service.field_id ||
        !service.aggregation_type ||
        filtersInError
    )
  }

  getDescription(service, application) {
    const integration = this.app.store.getters[
      'integration/getIntegrationById'
    ](application, service.integration_id)

    const databases = integration?.context_data?.databases || []

    const tableSelected = databases
      .map((database) => database.tables)
      .flat()
      .find(({ id }) => id === service.table_id)

    if (service.table_id && tableSelected) {
      const defaultTableDescription = `${this.name} - ${tableSelected.name}`
      if (service.field_id) {
        if (service.context_data.field) {
          const fieldName = service.context_data.field.name
          return `${defaultTableDescription} - ${fieldName}`
        } else {
          return `${defaultTableDescription} - ${this.app.i18n.t(
            'serviceType.trashedField'
          )}`
        }
      }

      return defaultTableDescription
    }

    return this.name
  }

  getOrder() {
    return 30
  }
}
