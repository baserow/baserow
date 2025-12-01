import path from 'path'

export const routes = [
  {
    name: 'automation-workflow',
    path: '/automation/:automationId/workflow/:workflowId',
    component: path.resolve(__dirname, 'pages/automationWorkflow.vue'),
    props(route) {
      const p = { ...route.params }
      p.automationId = parseInt(p.automationId)
      p.workflowId = parseInt(p.workflowId)
      return p
    },
  },
]
