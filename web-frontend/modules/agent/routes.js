import path from 'path'

export const routes = [
  {
    name: 'agent-application',
    path: '/agent/:agentId',
    file: path.resolve(__dirname, 'pages/agent.vue'),
  },
]
