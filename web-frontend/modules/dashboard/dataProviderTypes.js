import { getValueAtPath } from '@baserow/modules/core/utils/object'
import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'

export class WidgetDataProviderType extends DataProviderType {
  static getType() {
    return 'widget_data'
  }

  get name() {
    return this.app.$i18n.t('dashboardDataProviderType.widgetData')
  }

  getWidgets({ storePrefix = '', owningWidgetId }) {
    return this.app.$store.getters[
      `${storePrefix}dashboardApplication/getWidgets`
    ].filter(
      (widget) =>
        this.app.$registry.get('dashboardWidget', widget.type).isFilterWidget &&
        (owningWidgetId === undefined || widget.id === owningWidgetId)
    )
  }

  getDataContent({ storePrefix = '' }) {
    return this.app.$store.getters[
      `${storePrefix}dashboardApplication/getWidgetValues`
    ]
  }

  getDataChunk(context, path) {
    return getValueAtPath(this.getDataContent(context), path)
  }

  getDataSourceDispatchContext(context) {
    return { ...(context.widgetValues ?? this.getDataContent(context)) }
  }

  /** Describe filter values using their registered type schemas. */
  getDataSchema(context) {
    return {
      type: 'object',
      properties: Object.fromEntries(
        this.getWidgets(context).map((widget) => [
          widget.id,
          this.app.$registry
            .get('dashboardWidget', widget.type)
            .getValueSchema(widget),
        ])
      ),
    }
  }

  getContextDataSchema(context) {
    return this.getDataSchema(context)
  }

  isValid(path) {
    return (
      path.length >= 1 &&
      path.length <= 2 &&
      /^[1-9][0-9]{0,18}$/.test(path[0]) &&
      (path.length === 1 || path[1] === '*' || /^[0-9]{1,9}$/.test(path[1]))
    )
  }
}

export class DashboardTableDataProviderType extends DataProviderType {
  static getType() {
    return 'table'
  }

  isValid(path) {
    return (
      path.length >= 3 &&
      /^[1-9][0-9]{0,18}$/.test(path[0]) &&
      (path[1] === '*' || /^[0-9]{1,9}$/.test(path[1])) &&
      (path[2] === 'id' || /^field_[1-9][0-9]{0,18}$/.test(path[2]))
    )
  }

  get name() {
    return this.app.$i18n.t('dataProviderType.dataSource')
  }

  getDataContent() {
    // Table values are resolved by the backend when loading filter options.
    return {}
  }

  getDataChunk(context, path) {
    return getValueAtPath(this.getDataContent(context), path)
  }

  getDataSchema({ storePrefix = '' }) {
    const getters = this.app.$store.getters
    const prefix = `${storePrefix}dashboardApplication/`
    const sourceIds = new Set(
      getters[prefix + 'getWidgets'].map((widget) => widget.data_source_id)
    )
    const properties = {}
    for (const sourceId of sourceIds) {
      const source = getters[prefix + 'getDataSourceById'](sourceId)
      if (source?.table_schema && !Object.hasOwn(properties, source.table_id)) {
        properties[source.table_id] = {
          ...source.table_schema,
          order: Object.keys(properties).length,
        }
      }
    }
    return { type: 'object', properties }
  }
}
