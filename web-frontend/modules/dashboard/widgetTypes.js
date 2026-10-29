import isEqual from 'lodash/isEqual'
import { refreshWidgetSources } from '@baserow/modules/dashboard/utils/widgetFilters'
import TextFilterWidgetSvg from '@baserow/modules/dashboard/assets/images/widgets/text_filter_widget.svg?url'
import TextFilterWidget from '@baserow/modules/dashboard/components/widget/TextFilterWidget'
import TextFilterWidgetSettings from '@baserow/modules/dashboard/components/widget/TextFilterWidgetSettings'
import { Registerable } from '@baserow/modules/core/registry'
import SummaryWidgetSvg from '@baserow/modules/dashboard/assets/images/widgets/summary_widget.svg?url'
import SummaryWidget from '@baserow/modules/dashboard/components/widget/SummaryWidget'
import SummaryWidgetSettings from '@baserow/modules/dashboard/components/widget/SummaryWidgetSettings'

export class WidgetType extends Registerable {
  constructor(...args) {
    super(...args)
    this.type = this.getType()

    if (this.type === null) {
      throw new Error('The type name of a widget type must be set.')
    }

    if (this.name === null) {
      throw new Error('The name of a widget type must be set.')
    }
  }

  get name() {
    return null
  }

  get createWidgetImage() {
    return null
  }

  get component() {
    return null
  }

  get settingsComponent() {
    return null
  }

  /**
   * When the same widget can be created with different
   * options resulting in different name, image, and
   * settings.
   */
  get variations() {
    return [
      {
        name: this.name,
        createWidgetImage: this.createWidgetImage,
        type: this,
        params: {},
        dropdownIcon: '',
      },
    ]
  }

  getOrder() {
    return 0
  }

  isLoading(widget, data) {
    return false
  }

  isMisconfigured(widget, data) {
    return false
  }

  get showHeaderBorder() {
    return true
  }

  isAvailable() {
    return true
  }

  getDeactivatedModal() {
    return null
  }

  get isDisplayWidget() {
    return false
  }

  get isFilterWidget() {
    return false
  }

  /** Widget lifecycle hooks receive the local Vuex context and widget registry. */
  afterCreate(widget, context) {}

  afterUpdate(widget, context, previousWidget) {}

  afterDelete(widget, context) {}

  /** Called after the server accepts a configuration update. */
  afterSave(widget, context, values) {}

  valueChanged(widget, context, value) {}

  getTargetWidgetIds(widget) {
    return []
  }
}

export class DataSourceWidgetType extends WidgetType {
  get isDisplayWidget() {
    return true
  }

  getDataSourceId(widget) {
    return widget.data_source_id
  }
  afterCreate(widget, context) {
    if (
      context.state.dataSources.some(
        (source) => source.id === widget.data_source_id
      )
    ) {
      context.dispatch('refreshDataSources', [widget.data_source_id])
    }
  }

  /** Refresh dependencies when a display widget changes its source. */
  afterUpdate(widget, context, previousWidget) {
    if (widget.data_source_id !== previousWidget.data_source_id) {
      context.dispatch(
        'refreshDataSources',
        [previousWidget.data_source_id, widget.data_source_id].filter(Boolean)
      )
    }
  }

  getDataSourceData(widget, data) {
    return data?.[widget.data_source_id]
  }

  isLoading(widget, data) {
    const dataSourceData = this.getDataSourceData(widget, data)
    return !dataSourceData || Object.keys(dataSourceData).length === 0
  }

  isMisconfigured(widget, data) {
    return Boolean(this.getDataSourceData(widget, data)?._error)
  }
}

export class SummaryWidgetType extends DataSourceWidgetType {
  static getType() {
    return 'summary'
  }

  get name() {
    const { $i18n: i18n } = this.app
    return i18n.t('summaryWidget.name')
  }

  get createWidgetImage() {
    return SummaryWidgetSvg
  }

  get component() {
    return SummaryWidget
  }

  get settingsComponent() {
    return SummaryWidgetSettings
  }

  get showHeaderBorder() {
    return false
  }
}

export class FilterWidgetType extends WidgetType {
  get isFilterWidget() {
    return true
  }

  getDefaultValue(widget) {
    return null
  }

  getValueSchema(widget) {
    throw new Error('Filter types must define their value schema.')
  }
  afterCreate(widget, context) {
    if (!Object.hasOwn(context.state.widgetValues, widget.id)) {
      this.valueChanged(widget, context, this.getDefaultValue(widget))
    }
  }

  /** Defaults reset viewer values; editing links refreshes both old and new targets. */
  afterUpdate(widget, context, previousWidget) {
    if (
      !isEqual(
        this.getDefaultValue(widget),
        this.getDefaultValue(previousWidget)
      )
    ) {
      this.valueChanged(widget, context, this.getDefaultValue(widget))
    }
    if (
      !isEqual(widget.target_filters, previousWidget.target_filters) ||
      !isEqual(widget.target_widget_ids, previousWidget.target_widget_ids)
    ) {
      refreshWidgetSources(previousWidget, context)
      refreshWidgetSources(widget, context)
    }
  }

  afterDelete(widget, context) {
    refreshWidgetSources(widget, context)
    context.commit('DELETE_WIDGET_VALUE', widget.id)
  }

  /** Refresh persisted groups after the server accepts the configuration. */
  afterSave(widget, context, values) {
    if (Object.hasOwn(values, 'target_filters'))
      refreshWidgetSources(widget, context)
  }

  valueChanged(widget, context, value) {
    if (context.state.widgetValues[widget.id] === value) return
    context.commit('SET_WIDGET_VALUE', { widgetId: widget.id, value })
    refreshWidgetSources(widget, context)
  }

  getTargetWidgetIds(widget) {
    return widget.target_filters
      ? widget.target_filters.map((link) => link.target_widget_id)
      : widget.target_widget_ids || []
  }
}

export class TextFilterWidgetType extends FilterWidgetType {
  getDefaultValue(widget) {
    return widget.default_value ?? ''
  }

  getValueSchema(widget) {
    return { type: 'string', title: widget.title }
  }
  static getType() {
    return 'text_filter'
  }

  get name() {
    return this.app.$i18n.t('textFilterWidget.name')
  }

  get createWidgetImage() {
    return TextFilterWidgetSvg
  }

  get component() {
    return TextFilterWidget
  }

  get settingsComponent() {
    return TextFilterWidgetSettings
  }
}
