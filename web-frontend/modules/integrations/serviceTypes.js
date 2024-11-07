import { ServiceType } from '@baserow/modules/core/serviceTypes'
import { LocalBaserowIntegrationType } from '@baserow/modules/integrations/integrationTypes'
import LocalBaserowGetRowForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowGetRowForm'
import LocalBaserowListRowsForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowListRowsForm'
import LocalBaserowAggregateRowsForm from '@baserow/modules/integrations/localBaserow/components/services/LocalBaserowAggregateRowsForm'
import { uuid } from '@baserow/modules/core/utils/string'
import LocalBaserowAdhocHeader from '@baserow/modules/integrations/localBaserow/components/integrations/LocalBaserowAdhocHeader'

export class LocalBaserowTableServiceType extends ServiceType {
  get integrationType() {
    return this.app.$registry.get(
      'integration',
      LocalBaserowIntegrationType.getType()
    )
  }

  /**
   * Responsible for returning if the Local Baserow service type is valid. By
   * default, this is just if a `table_id` has been set. Subclasses must extend
   * this with their own requirements.
   *
   * @param service - The service object.
   * @returns {boolean} - If the service is valid.
   */
  isValid(service) {
    return super.isValid(service) && Boolean(service.table_id)
  }

  getDataSchema(service) {
    return service.schema
  }

  getContextDataSchema(service) {
    return service.context_data_schema
  }

  /**
   * In a Local Baserow service which returns a list, this method is used to
   * return the name of the given record.
   */
  getRecordName(service, record) {
    return ''
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

    const databases = integration.context_data?.databases

    const tableSelected = databases
      .map((database) => database.tables)
      .flat()
      .find(({ id }) => id === service.table_id)

    if (service.table_id && tableSelected) {
      return `${this.name} - ${tableSelected.name}`
    }

    return this.name
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

  isValid(service) {
    return super.isValid(service) && Boolean(service.table_id)
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

  isValid(service) {
    return (
      super.isValid(service) &&
      Boolean(service.field_id) &&
      Boolean(service.aggregation_type)
    )
  }

  getDescription(service, application) {
    const integration = this.app.store.getters[
      'integration/getIntegrationById'
    ](application, service.integration_id)

    const databases = integration.context_data?.databases

    const tableSelected = databases
      .map((database) => database.tables)
      .flat()
      .find(({ id }) => id === service.table_id)

    if (service.table_id && tableSelected) {
      const defaultTableDescription = `${this.name} - ${tableSelected.name}`
      if (service.field_id) {
        const fieldSelected = tableSelected.fields.find(
          ({ id }) => id === service.field_id
        )
        return `${defaultTableDescription} - ${fieldSelected.name}`
      }

      return defaultTableDescription
    }

    return this.name
  }

  getOrder() {
    return 30
  }
}
