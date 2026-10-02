import { SummaryWidgetType } from '@baserow/modules/dashboard/widgetTypes'

export default function registerDashboardDomain(nuxtApp) {
  const { $registry } = nuxtApp
  const context = { app: nuxtApp }

  $registry.register('dashboardWidget', new SummaryWidgetType(context))
}
