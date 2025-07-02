import { Registerable } from '@baserow/modules/core/registry'
import SummaryWidgetSvg from '@baserow/modules/dashboard/assets/images/widgets/summary_widget.svg'
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

  isAvailable() {
    return true
  }

  getDeactivatedModal() {
    return null
  }
}

export class SummaryWidgetType extends WidgetType {
  static getType() {
    return 'summary'
  }

  get name() {
    return this.app.i18n.t('summaryWidget.name')
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

  isLoading(widget, data) {
    const dataSourceId = widget.data_source_id
    if (data[dataSourceId] && Object.keys(data[dataSourceId]).length !== 0) {
      return false
    }
    return true
  }
}
