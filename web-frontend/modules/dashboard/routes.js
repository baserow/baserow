import path from 'path'

export const routes = [
  {
    name: 'dashboard-application',
    path: '/dashboard/:dashboardId',
    file: path.resolve(__dirname, 'pages/dashboard.vue'),
  },
  {
    name: 'dashboard-public',
    path: '/public/dashboard/:slug',
    file: path.resolve(__dirname, 'pages/publicDashboard.vue'),
  },
  {
    name: 'dashboard-public-auth',
    path: '/public/dashboard/:slug/auth',
    file: path.resolve(__dirname, 'pages/publicDashboardAuth.vue'),
    meta: { layout: 'login' },
  },
]
