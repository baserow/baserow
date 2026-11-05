import path from 'path'

export const routes = [
  {
    name: 'automation-workflow',
    path: '/automation/:automationId/workflow/:workflowId',
    file: path.resolve(__dirname, 'pages/automationWorkflow.vue'),
    props: (route) => ({
      automationId: parseInt(route.params.automationId),
      workflowId: parseInt(route.params.workflowId),
    }),
  },
]

// Each route initializes its application before selecting data or rendering UI.
for (const route of routes) {
  route.meta = { ...route.meta, applicationBundle: 'automation' }
}
