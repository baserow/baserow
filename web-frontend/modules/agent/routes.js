import path from 'path'

export const routes = [
  {
    name: 'agent-mcp-oauth-callback',
    path: '/agent/mcp-oauth-callback',
    file: path.resolve(__dirname, 'pages/mcpOAuthCallback.vue'),
  },
  {
    name: 'agent-application',
    path: '/agent/:agentId',
    file: path.resolve(__dirname, 'pages/agent.vue'),
  },
]
