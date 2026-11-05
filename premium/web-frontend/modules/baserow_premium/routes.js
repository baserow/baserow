import path from 'path'

export const routes = [
  {
    name: 'premium-root',
    path: '',
    file: path.resolve(__dirname, 'pages/root.vue'),
    children: [
      {
        name: 'admin-licenses',
        path: '/admin/licenses',
        file: path.resolve(__dirname, 'pages/admin/licenses.vue'),
      },
      {
        name: 'admin-license',
        path: '/admin/license/:id',
        file: path.resolve(__dirname, 'pages/admin/license.vue'),
      },
    ],
  },
  {
    name: 'database-public-kanban-view',
    path: '/public/kanban/:slug',
    file: '@baserow/modules/database/pages/publicView.vue',
  },
  {
    name: 'database-public-calendar-view',
    path: '/public/calendar/:slug',
    file: '@baserow/modules/database/pages/publicView.vue',
  },
  {
    name: 'database-public-timeline-view',
    path: '/public/timeline/:slug',
    file: '@baserow/modules/database/pages/publicView.vue',
  },
]

// Public premium views require the Database feature just like authenticated views.
for (const route of routes) {
  if (route.path.startsWith('/public/')) {
    route.meta = { ...route.meta, applicationBundle: 'database' }
  }
}
