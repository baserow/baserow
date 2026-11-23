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

export class DashboardTableContextDataProviderType extends DataProviderType {
  static getType() {
    return 'table_context'
  }

  get name() {
    return this.app.$i18n.t('dashboardDataProviderType.tableContext')
  }

  isValid(path) {
    return path.length >= 2 && /^[1-9][0-9]{0,18}$/.test(path[0])
  }

  getDataSources({ storePrefix = '' }) {
    return this.app.$store.getters[
      `${storePrefix}dashboardApplication/getDataSources`
    ]
  }

  getDataContent(context) {
    const tables = {}
    for (const source of this.getDataSources(context)) {
      const tableId = source.context_table_id ?? source.table_id
      if (!tableId) continue
      tables[tableId] = {
        ...tables[tableId],
        ...source.context_data,
      }
    }
    return tables
  }

  /** Preserve empty option arrays when resolving wildcard properties. */
  getDataChunk(context, path) {
    const content = this.getDataContent(context)
    const wildcard = path.indexOf('*')
    if (wildcard !== -1) {
      const items = getValueAtPath(content, path.slice(0, wildcard))
      if (Array.isArray(items) && items.length === 0) return []
    }
    return getValueAtPath(content, path)
  }

  /** Group declared context fields by table, keeping one source per table. */
  getDataSchema(context) {
    const tables = new Set()
    const properties = {}
    for (const source of this.getDataSources(context)) {
      const schema = source.context_data_schema
      if (!schema || !source.table_id || tables.has(source.table_id)) continue
      tables.add(source.table_id)
      properties[source.table_id] = { ...schema, order: tables.size - 1 }
    }
    return { type: 'object', properties }
  }
}
