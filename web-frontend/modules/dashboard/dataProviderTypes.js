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

  getDataChunk(context, [id]) {
    return this.getDataContent(context)[id]
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
    return path.length === 1 && /^[1-9][0-9]*$/.test(path[0])
  }
}
