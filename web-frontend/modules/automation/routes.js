import path from 'path'

export const routes = [
  {
    name: 'automation-application',
    path: '/automation/:automationId',
    component: path.resolve(__dirname, 'pages/automation.vue'),
    props(route) {
      const p = { ...route.params }
      p.automationId = parseInt(p.automationId)
      return p
    },
  },
]
