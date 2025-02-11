import { WidgetType } from '@baserow/modules/dashboard/widgetTypes'
import ChartWidget from '@baserow_enterprise/dashboard/components/widget/ChartWidget'
import ChartWidgetSettings from '@baserow_enterprise/dashboard/components/widget/ChartWidgetSettings'
import ChartWidgetSvg from '@baserow_enterprise/assets/images/dashboard/widgets/chart_widget.svg'
import EnterpriseFeatures from '@baserow_enterprise/features'
import EnterpriseModal from '@baserow_enterprise/components/EnterpriseModal'

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
    return this.app.$hasFeature(EnterpriseFeatures.CHART_WIDGET, workspaceId)
  }

  getDeactivatedModal() {
    return EnterpriseModal
  }
}
