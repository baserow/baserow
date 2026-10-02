import {
  ChartWidgetType,
  PieChartWidgetType,
} from '@baserow_premium/dashboard/widgetTypes'
import { SingleSelectFormattingType } from '@baserow_premium/dashboard/chartFieldFormatting'

export default function registerPremiumDashboardDomain(nuxtApp) {
  const { $registry } = nuxtApp
  const context = { app: nuxtApp }

  $registry.register('dashboardWidget', new ChartWidgetType(context))
  $registry.register('dashboardWidget', new PieChartWidgetType(context))
  $registry.register(
    'chartFieldFormatting',
    new SingleSelectFormattingType(context)
  )
}
