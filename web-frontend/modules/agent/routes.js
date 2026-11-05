import path from 'path'

export const routes = [
  {
    name: 'agent-application',
    path: '/agent/:agentId',
    file: path.resolve(__dirname, 'pages/agent.vue'),
  },
]

// Each route initializes its application before selecting data or rendering UI.
for (const route of routes) {
  route.meta = { ...route.meta, applicationBundle: 'agent' }
}
