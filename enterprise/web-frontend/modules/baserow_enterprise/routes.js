import path from 'path'

// Routes that should be children of 'root' (inherit layout and middlewares)
export const rootChildRoutes = [
  {
    name: 'admin-auth-providers',
    path: '/admin/auth-providers',
    file: path.resolve(__dirname, 'pages/admin/authProviders.vue'),
  },
  {
    name: 'admin-audit-log',
    path: '/admin/audit-log',
    file: path.resolve(__dirname, 'pages/auditLog.vue'),
  },
  {
    name: 'admin-data-scanner',
    path: '/admin/data-scanner',
    redirect: '/admin/data-scanner/scans',
    file: path.resolve(__dirname, 'pages/admin/dataScanner.vue'),
    children: [
      {
        name: 'admin-data-scanner-scans',
        path: 'scans',
        file: path.resolve(__dirname, 'pages/admin/dataScanner/scans.vue'),
      },
      {
        name: 'admin-data-scanner-results',
        path: 'results',
        file: path.resolve(__dirname, 'pages/admin/dataScanner/results.vue'),
      },
    ],
  },
  {
    name: 'workspace-audit-log',
    path: '/workspace/:workspaceId/audit-log',
    file: path.resolve(__dirname, 'pages/auditLog.vue'),
  },
]

// Login pages (children of login-pages route, inherit login layout)
export const routes = [
  {
    name: 'login-saml',
    path: '/login/saml',
    file: path.resolve(__dirname, 'pages/login/loginWithSAML.vue'),
  },
  {
    name: 'login-error',
    path: '/login/error',
    file: path.resolve(__dirname, 'pages/login/loginError.vue'),
  },
]
