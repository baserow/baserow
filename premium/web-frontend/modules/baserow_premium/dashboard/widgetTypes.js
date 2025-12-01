import { WidgetType } from '@baserow/modules/dashboard/widgetTypes'
import ChartWidget from '@baserow_premium/dashboard/components/widget/ChartWidget'
import PieChartWidget from '@baserow_premium/dashboard/components/widget/PieChartWidget'
import ChartWidgetSettings from '@baserow_premium/dashboard/components/widget/ChartWidgetSettings'
import ChartBarWidgetSvg from '@baserow_premium/assets/images/dashboard/widgets/chart_widget_bar.svg'
import ChartLineWidgetSvg from '@baserow_premium/assets/images/dashboard/widgets/chart_widget_line.svg'
import ChartPieWidgetSvg from '@baserow_premium/assets/images/dashboard/widgets/chart_widget_pie.svg'
import ChartDonutWidgetSvg from '@baserow_premium/assets/images/dashboard/widgets/chart_widget_donut.svg'
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
    return ChartBarWidgetSvg
  }

  get component() {
    return ChartWidget
  }

  get settingsComponent() {
    return ChartWidgetSettings
  }

  get variations() {
    return [
      {
        name: this.app.i18n.t('chartWidget.bar'),
        createWidgetImage: ChartBarWidgetSvg,
        type: this,
        params: {
          default_series_chart_type: 'BAR',
        },
        dropdownIcon: 'baserow-icon-bar-chart',
      },
      {
        name: this.app.i18n.t('chartWidget.line'),
        createWidgetImage: ChartLineWidgetSvg,
        type: this,
        params: {
          default_series_chart_type: 'LINE',
        },
        dropdownIcon: 'baserow-icon-line-chart',
      },
    ]
  }

  async dataSourceUpdated(widget, data) {
    // If widget series configuration is missing for any existing
    // series we will create a series configuration reflecting the
    // proper defaults.
    const dataSourceSeriesIds = data.aggregation_series.map(
      (series) => series.id
    )
    const widgetConfSeriesIds = widget.series_config.map(
      (conf) => conf.series_id
    )
    const missingConfIds = dataSourceSeriesIds.filter(
      (element) => !widgetConfSeriesIds.includes(element)
    )
    if (missingConfIds.length > 0) {
      const values = JSON.parse(JSON.stringify(widget))
      const originalValues = JSON.parse(JSON.stringify(widget))
      const seriesConfig = {
        series_id: missingConfIds[0],
        series_chart_type: widget.default_series_chart_type,
      }
      values.series_config.push(seriesConfig)
      await this.app.store.dispatch(`dashboardApplication/updateWidget`, {
        widgetId: widget.id,
        values,
        originalValues,
      })
    }
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

export class PieChartWidgetType extends WidgetType {
  static getType() {
    return 'pie_chart'
  }

  get name() {
    return this.app.i18n.t('pieChartWidget.name')
  }

  get createWidgetImage() {
    return ChartPieWidgetSvg
  }

  get component() {
    return PieChartWidget
  }

  get settingsComponent() {
    return ChartWidgetSettings
  }

  get variations() {
    return [
      {
        name: this.app.i18n.t('pieChartWidget.pie'),
        createWidgetImage: ChartPieWidgetSvg,
        type: this,
        params: {
          default_series_chart_type: 'PIE',
        },
        dropdownIcon: 'baserow-icon-pie-chart',
      },
      {
        name: this.app.i18n.t('pieChartWidget.doughnut'),
        createWidgetImage: ChartDonutWidgetSvg,
        type: this,
        params: {
          default_series_chart_type: 'DOUGHNUT',
        },
        dropdownIcon: 'baserow-icon-donut-chart',
      },
    ]
  }

  async dataSourceUpdated(widget, data) {
    // If widget series configuration is missing for any existing
    // series we will create a series configuration reflecting the
    // proper defaults.
    const dataSourceSeriesIds = data.aggregation_series.map(
      (series) => series.id
    )
    const widgetConfSeriesIds = widget.series_config.map(
      (conf) => conf.series_id
    )
    const missingConfIds = dataSourceSeriesIds.filter(
      (element) => !widgetConfSeriesIds.includes(element)
    )
    if (missingConfIds.length > 0) {
      const values = JSON.parse(JSON.stringify(widget))
      const originalValues = JSON.parse(JSON.stringify(widget))
      const seriesConfig = {
        series_id: missingConfIds[0],
        series_chart_type: widget.default_series_chart_type,
      }
      values.series_config.push(seriesConfig)
      await this.app.store.dispatch(`dashboardApplication/updateWidget`, {
        widgetId: widget.id,
        values,
        originalValues,
      })
    }
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
