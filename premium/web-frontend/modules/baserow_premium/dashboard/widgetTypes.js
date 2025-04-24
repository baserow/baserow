import { WidgetType } from '@baserow/modules/dashboard/widgetTypes'
import ChartWidget from '@baserow_premium/dashboard/components/widget/ChartWidget'
import ChartWidgetSettings from '@baserow_premium/dashboard/components/widget/ChartWidgetSettings'
import ChartWidgetSvg from '@baserow_premium/assets/images/dashboard/widgets/chart_widget.svg'
import PremiumFeatures from '@baserow_premium/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { ChartPaidFeature } from '@baserow_premium/paidFeatures'

export class ChartWidgetType extends WidgetType {
  static getType() {
    return 'chart'
  }

  get name() {
    return this.app.i18n.t('chartWidget.name')
  }

  get createWidgetImage() {
    return ChartWidgetSvg
  }

  get component() {
    return ChartWidget
  }

  get settingsComponent() {
    return ChartWidgetSettings
  }

  isLoading(widget, data) {
    const dataSourceId = widget.data_source_id
    if (data[dataSourceId] && Object.keys(data[dataSourceId]).length !== 0) {
      return false
    }
    return true
  }

  isAvailable(workspaceId) {
    return this.app.$hasFeature(PremiumFeatures.PREMIUM, workspaceId)
  }

  getDeactivatedModal() {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': ChartPaidFeature.getType() },
    ]
  }
}
