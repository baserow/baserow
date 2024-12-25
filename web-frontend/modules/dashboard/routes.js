import path from 'path'

export const routes = [
  {
    name: 'dashboard-application',
    path: '/dashboard/:dashboardId',
    component: path.resolve(__dirname, 'pages/dashboard.vue'),
    props(route) {
      const p = { ...route.params }
      p.dashboardId = parseInt(p.dashboardId)
      return p
    },
  },
]
