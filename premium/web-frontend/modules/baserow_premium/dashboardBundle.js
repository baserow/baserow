import {
  ChartWidgetType,
  PieChartWidgetType,
} from '@baserow_premium/dashboard/widgetTypes'

/** Register this feature only when its application is used. */
export default async function register(nuxtApp) {
  const { $registry } = nuxtApp
  const context = { app: nuxtApp }
  $registry.register('dashboardWidget', new ChartWidgetType(context))
  $registry.register('dashboardWidget', new PieChartWidgetType(context))
}

export { default as PremiumDashboardShareOptions } from '@baserow_premium/components/dashboard/PremiumDashboardShareOptions'
