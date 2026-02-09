import path from 'path'

// Note that routes can't start with `/api/`, `/ws/` or `/media/` because they are
// reserved for the backend. In some cases, for example with the Heroku or Cloudron
// deployment, the Baserow installation will share a single domain and port and then
// those URLS are forwarded to the backend or media files server. The rest is
// forwarded to the web-frontend.
export const routes = [
  {
    name: 'index',
    path: '',
    file: path.resolve(__dirname, 'pages/index.vue'),
  },
  {
    name: 'debug',
    path: '/debug',
    file: path.resolve(__dirname, 'pages/debug.vue'),
  },
  {
    name: 'login-pages',
    path: '',
    file: path.resolve(__dirname, 'pages/loginPages.vue'),
    children: [
      {
        name: 'login',
        path: '/login',
        file: path.resolve(__dirname, 'pages/login.vue'),
      },
      {
        name: 'signup',
        path: '/signup',
        file: path.resolve(__dirname, 'pages/signup.vue'),
      },
      {
        name: 'forgot-password',
        path: '/forgot-password',
        file: path.resolve(__dirname, 'pages/forgotPassword.vue'),
      },
      {
        name: 'reset-password',
        path: '/reset-password/:token',
        file: path.resolve(__dirname, 'pages/resetPassword.vue'),
        meta: { preventPageViewTracking: true },
      },
      {
        name: 'change-email',
        path: '/change-email/:token',
        file: path.resolve(__dirname, 'pages/changeEmail.vue'),
        meta: { preventPageViewTracking: true },
      },
      {
        name: 'verify-email-address',
        path: '/verify-email-address/:token',
        file: path.resolve(__dirname, 'pages/verifyEmailAddress.vue'),
      },
      {
        // It's not exactly a login page but it was inheriting from login layout
        name: 'style-guide',
        path: '/style-guide',
        file: path.resolve(__dirname, 'pages/styleGuide.vue'),
      },
    ],
  },
  {
    name: 'root',
    path: '',
    file: path.resolve(__dirname, 'pages/root.vue'),
    children: [
      {
        name: 'dashboard',
        path: '/dashboard',
        file: path.resolve(__dirname, 'pages/dashboard.vue'),
      },
      {
        name: 'workspace',
        path: '/workspace/:workspaceId',
        file: path.resolve(__dirname, 'pages/workspace.vue'),
      },
      {
        name: 'admin-settings',
        path: '/admin/settings',
        file: path.resolve(__dirname, 'pages/admin/settings.vue'),
      },
      {
        name: 'admin-health',
        path: '/admin/health',
        file: path.resolve(__dirname, 'pages/admin/health.vue'),
      },
      {
        name: 'admin-dashboard',
        path: '/admin/dashboard',
        file: path.resolve(__dirname, 'pages/admin/dashboard.vue'),
      },
      {
        name: 'admin-users',
        path: '/admin/users',
        file: path.resolve(__dirname, 'pages/admin/users.vue'),
      },
      {
        name: 'admin-workspaces',
        path: '/admin/workspaces',
        file: path.resolve(__dirname, 'pages/admin/workspaces.vue'),
      },
      {
        name: 'settings',
        path: '/workspace/:workspaceId/settings',
        file: path.resolve(__dirname, 'pages/settings.vue'),
        children: [
          {
            name: 'settings-members',
            path: 'members',
            file: path.resolve(__dirname, 'pages/settings/members.vue'),
          },
          {
            name: 'settings-invites',
            path: 'invites',
            file: path.resolve(__dirname, 'pages/settings/invites.vue'),
          },
        ],
      },
    ],
  },

  {
    name: 'workspace-invitation',
    path: '/workspace-invitation/:token',
    file: path.resolve(__dirname, 'pages/workspaceInvitation.vue'),
    meta: { preventPageViewTracking: true },
  },

  {
    name: 'template',
    path: '/template/:slug',
    file: path.resolve(__dirname, 'pages/template.vue'),
  },
  {
    name: 'health-check',
    path: '/_health/:trailing()?',
    file: path.resolve(__dirname, 'pages/_health.vue'),
  },
  {
    name: 'notification-redirect',
    path: '/notification/:workspaceId/:notificationId',
    file: path.resolve(__dirname, 'pages/notificationRedirect.vue'),
  },
  {
    name: 'onboarding',
    path: '/onboarding',
    file: path.resolve(__dirname, 'pages/onboarding.vue'),
  },
]

// if (import.meta.env.MODE  !== 'production') {
//   routes.push({
//     name: 'storybook',
//     path: '/storybook',
//     file: path.resolve(__dirname, 'pages/storybook.vue'),
//   })
// }
