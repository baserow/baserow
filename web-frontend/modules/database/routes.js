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
    component: path.resolve(__dirname, 'pages/table.vue'),
    props(route) {
      // @TODO figure out why the route param is empty on the server side.
      const p = { ...route.params }
      p.databaseId = parseInt(p.databaseId)
      p.tableId = parseInt(p.tableId)
      p.viewId = p.viewId ? parseInt(p.viewId) : null
      return p
    },
    children: [
      {
        path: 'row/:rowId',
        name: 'database-table-row',
      },
      {
        path: 'webhooks',
        name: 'database-table-open-webhooks',
        component: path.resolve(__dirname, 'pages/table/webhooks.vue'),
      },
      {
        path: 'configure-data-sync/:selectedPage?',
        name: 'database-table-open-configure-data-sync',
        component: path.resolve(__dirname, 'pages/table/configureDataSync.vue'),
      },
    ],
  },
  // These redirect exist because the original api docs path was `/api/docs`, but
  // they have been renamed.
  {
    path: '/api/docs',
    redirect: '/api-docs',
  },
  {
    path: '/api/docs/database/:databaseId',
    redirect: '/api-docs/database/:databaseId',
  },
  {
    name: 'database-api-docs',
    path: '/api-docs',
    alias: '/api/docs',
    component: path.resolve(__dirname, 'pages/APIDocs.vue'),
  },
  {
    name: 'database-api-docs-detail',
    path: '/api-docs/database/:databaseId',
    component: path.resolve(__dirname, 'pages/APIDocsDatabase.vue'),
  },
  {
    name: 'database-table-form',
    path: '/form/:slug',
    component: path.resolve(__dirname, 'pages/form.vue'),
  },
  {
    name: 'database-public-grid-view',
    path: '/public/grid/:slug',
    component: path.resolve(__dirname, 'pages/publicView.vue'),
  },
  {
    name: 'database-public-gallery-view',
    path: '/public/gallery/:slug',
    component: path.resolve(__dirname, 'pages/publicView.vue'),
  },
  {
    name: 'database-public-view-auth',
    path: '/public/auth/:slug',
    component: path.resolve(__dirname, 'pages/publicViewLogin.vue'),
  },
]
