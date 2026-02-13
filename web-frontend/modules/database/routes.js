import path from 'path'

// Note that routes can't start with `/api/`, `/ws/` or `/media/` because they are
// reserved for the backend. In some cases, for example with the Heroku or Clouron
// deployment, the Baserow installation will share a single domain and port and then
// those URLS are forwarded to the backend or media files server. The rest is
// // forwarded to the web-frontend.
export const routes = [
  {
    name: 'database-table',
    path: '/database/:databaseId/table/:tableId/:viewId?',
    file: path.resolve(__dirname, 'pages/table.vue'),
    children: [
      {
        path: 'row/:rowId',
        name: 'database-table-row',
        file: path.resolve(
          __dirname,
          '../core/components/RouterViewPlaceholder.vue'
        ),
      },
      {
        path: 'webhooks',
        name: 'database-table-open-webhooks',
        file: path.resolve(__dirname, 'pages/table/webhooks.vue'),
      },
      {
        path: 'configure-data-sync/:selectedPage?',
        name: 'database-table-open-configure-data-sync',
        file: path.resolve(__dirname, 'pages/table/configureDataSync.vue'),
      },
    ],
  },
  // TODO MIG Is this necessary?
  {
    name: 'database-root',
    path: '',
    file: path.resolve(__dirname, 'pages/root.vue'),
    children: [],
  },
  // These redirect exist because the original api docs path was `/api/docs`, but
  // they have been renamed.
  {
    name: 'database-api-docs-redirect',
    path: '/api/docs',
    redirect: '/api-docs',
  },
  {
    name: 'database-api-docs-details-redirect',
    path: '/api/docs/database/:databaseId',
    redirect: '/api-docs/database/:databaseId',
  },
  {
    name: 'database-api-docs',
    path: '/api-docs',
    alias: '/api/docs',
    file: path.resolve(__dirname, 'pages/APIDocs.vue'),
  },
  {
    name: 'database-api-docs-detail',
    path: '/api-docs/database/:databaseId',
    file: path.resolve(__dirname, 'pages/APIDocsDatabase.vue'),
  },
  {
    name: 'database-table-form',
    path: '/form/:slug',
    file: path.resolve(__dirname, 'pages/form.vue'),
  },
  {
    name: 'database-public-grid-view',
    path: '/public/grid/:slug',
    file: path.resolve(__dirname, 'pages/publicView.vue'),
  },
  {
    name: 'database-public-gallery-view',
    path: '/public/gallery/:slug',
    file: path.resolve(__dirname, 'pages/publicView.vue'),
  },
  {
    name: 'database-public-view-auth',
    path: '/public/auth/:slug',
    file: path.resolve(__dirname, 'pages/publicViewLogin.vue'),
    meta: { layout: 'login' },
  },
]
