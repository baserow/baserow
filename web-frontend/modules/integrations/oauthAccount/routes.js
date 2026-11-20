import path from 'path'

export const routes = [
  {
    name: 'integrations-oauth-callback',
    path: '/integrations/:integrationType/oauth-callback',
    file: path.resolve(__dirname, 'pages/oauthCallback.vue'),
  },
]
