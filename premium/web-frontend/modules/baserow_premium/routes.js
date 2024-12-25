import path from 'path'

export const routes = [
  {
    name: 'admin-licenses',
    path: '/admin/licenses',
    component: path.resolve(__dirname, 'pages/admin/licenses.vue'),
  },
  {
    name: 'admin-license',
    path: '/admin/license/:id',
    component: path.resolve(__dirname, 'pages/admin/license.vue'),
  },
  {
    name: 'database-public-kanban-view',
    path: '/public/kanban/:slug',
    component: '@baserow/modules/database/pages/publicView.vue',
  },
  {
    name: 'database-public-calendar-view',
    path: '/public/calendar/:slug',
    component: '@baserow/modules/database/pages/publicView.vue',
  },
  {
    name: 'database-public-timeline-view',
    path: '/public/timeline/:slug',
    component: '@baserow/modules/database/pages/publicView.vue',
  },
]
