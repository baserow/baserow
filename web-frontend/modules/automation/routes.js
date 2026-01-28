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
