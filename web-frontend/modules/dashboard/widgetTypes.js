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
}

export class DataSourceWidgetType extends WidgetType {
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
