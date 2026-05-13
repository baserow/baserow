import { DataSourceLocalBaserowTableServiceType } from '@baserow/modules/integrations/localBaserow/serviceTypes'
import LocalBaserowGroupedAggregateRowsForm from '@baserow_premium/integrations/localBaserow/components/services/LocalBaserowGroupedAggregateRowsForm'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { GroupedAggregateRowsDataSourcePaidFeature } from '@baserow_premium/paidFeatures'

export const BUILDER_GROUPED_AGGREGATE_ROWS_FEATURE =
  'builder_grouped_aggregate_rows'

export class LocalBaserowGroupedAggregateRowsServiceType extends DataSourceLocalBaserowTableServiceType {
  static getType() {
    return 'local_baserow_grouped_aggregate_rows'
  }

  get name() {
    return this.app.$i18n.t('serviceType.localBaserowGroupedAggregateRows')
  }

  get description() {
    return this.app.$i18n.t(
      'serviceType.localBaserowGroupedAggregateRowsDescription'
    )
  }

  get formComponent() {
    return LocalBaserowGroupedAggregateRowsForm
  }

  get icon() {
    return 'iconoir-stats-report'
  }

  get returnsList() {
    return true
  }

  isDeactivatedReason({ workspace }) {
    if (!workspace) {
      return null
    }
    if (
      !this.app.$hasFeature(
        BUILDER_GROUPED_AGGREGATE_ROWS_FEATURE,
        workspace.id
      )
    ) {
      return this.app.$i18n.t('enterprise.deactivated')
    }
    return super.isDeactivatedReason({ workspace })
  }

  getDeactivatedClickModal({ workspace }) {
    if (
      workspace &&
      !this.app.$hasFeature(
        BUILDER_GROUPED_AGGREGATE_ROWS_FEATURE,
        workspace.id
      )
    ) {
      return [
        PaidFeaturesModal,
        {
          'initial-selected-type':
            GroupedAggregateRowsDataSourcePaidFeature.getType(),
        },
      ]
    }
    return null
  }

  get supportsPagination() {
    return false
  }

  getIdProperty(service, record) {
    return 'id'
  }

  parseRecordId(value) {
    return value
  }

  getRecordIdDataType(service) {
    return 'string'
  }

  getRecordNameFromId(service, recordId) {
    return recordId
  }

  getSchemaPropertyDisplayName(service, propertyName) {
    const property = this.getSchemaProperty(service, propertyName)
    return (
      property?.metadata?.source_field?.display_name ||
      super.getSchemaPropertyDisplayName(service, propertyName)
    )
  }

  getResultPropertyName(service, propertyName) {
    const property = this.getSchemaProperty(service, propertyName)
    if (property?.metadata?.aggregation) {
      return property.metadata.display_name || property?.title || propertyName
    }
    return property?.title || propertyName
  }

  getRecordName(service, record) {
    const fallbackName =
      record.id !== undefined && record.id !== null ? `${record.id}` : ''
    const schema = this.getDataSchema(service)
    const properties = schema?.items?.properties
    if (!properties) {
      return fallbackName
    }

    const groupBy = service.aggregation_group_bys?.[0]
    if (!groupBy) {
      return fallbackName
    }

    const nameProperty =
      groupBy.field_id === null
        ? Object.entries(properties).find(
            ([property, { metadata }]) => property !== 'id' && metadata?.primary
          )?.[0]
        : `field_${groupBy.field_id}`

    const field = properties[nameProperty]?.metadata
    const fieldType = field?.type
      ? this.app.$registry.get('field', field.type)
      : null
    const value = record[nameProperty]
    if (!fieldType || value === undefined || value === null) {
      return fallbackName
    }
    return fieldType.toHumanReadableString(field, value)
  }

  getErrorMessage({ service, workspace = null }) {
    const deactivatedReason =
      workspace && this.isDeactivatedReason({ workspace })
    if (deactivatedReason) {
      return deactivatedReason
    }

    if (service !== undefined) {
      if (!service.table_id) {
        return this.app.$i18n.t('serviceType.errorNoTableSelected')
      }
      if (
        !service.aggregation_series ||
        service.aggregation_series.length === 0
      ) {
        return this.app.$i18n.t('serviceType.errorNoAggregationSeriesDefined')
      }
      const incompleteSeries = service.aggregation_series.some(
        (item) => !item.field_id || !item.aggregation_type
      )
      if (incompleteSeries) {
        return this.app.$i18n.t('serviceType.errorIncompleteAggregationSeries')
      }
      const filtersInError = service.filters?.some((filter) => filter.trashed)
      if (filtersInError) {
        return this.app.$i18n.t('serviceType.errorFilterInError')
      }
    }
    return super.getErrorMessage({ service, workspace })
  }

  beforeUpdate(newValues, oldValues) {
    if (
      oldValues.table_id !== null &&
      newValues.table_id !== oldValues.table_id
    ) {
      newValues.filters = []
      newValues.aggregation_series = []
      newValues.aggregation_group_bys = []
      newValues.aggregation_sorts = []
    }
    return newValues
  }

  getOrder() {
    return 40
  }
}
