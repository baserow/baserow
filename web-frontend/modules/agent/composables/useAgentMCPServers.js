import { computed, ref } from 'vue'
import { useNuxtApp } from '#app'
import IntegrationService from '@baserow/modules/core/services/integration'
import MCPServerService from '@baserow/modules/agent/services/mcpServer'
import { MCP_SERVER_INTEGRATION_TYPE } from '@baserow/modules/agent/constants'

/**
 * The MCP servers an Agent may call tools of. Each is an integration of the
 * Agent; its tools are listed by the server and turned on by an editor.
 */
export function useAgentMCPServers(agent) {
  const { $client } = useNuxtApp()
  const integrations = IntegrationService($client)
  const mcp = MCPServerService($client)

  const servers = ref([])
  const loading = ref(false)
  const loadError = ref(false)
  let request = 0

  const isServer = (integration) =>
    integration.type === MCP_SERVER_INTEGRATION_TYPE

  function replace(server) {
    const index = servers.value.findIndex(({ id }) => id === server.id)
    if (index === -1) servers.value = [...servers.value, server]
    else servers.value = servers.value.with(index, server)
    return server
  }

  async function load() {
    const current = ++request
    loading.value = true
    loadError.value = false
    try {
      const { data } = await integrations.fetchAll(agent.value.id)
      if (current === request) servers.value = data.filter(isServer)
    } catch {
      if (current === request) loadError.value = true
    } finally {
      if (current === request) loading.value = false
    }
  }

  async function create(values) {
    const { data } = await integrations.create(
      agent.value.id,
      MCP_SERVER_INTEGRATION_TYPE,
      values
    )
    return replace(data)
  }

  async function update(server, values) {
    const { data } = await integrations.update(server.id, values)
    return replace(data)
  }

  async function remove(server) {
    await integrations.delete(server.id)
    servers.value = servers.value.filter(({ id }) => id !== server.id)
  }

  async function refreshTools(server) {
    const { data } = await mcp.refreshTools(server.id)
    return replace(data)
  }

  async function updateTools(server, tools) {
    const { data } = await mcp.updateTools(server.id, tools)
    return replace(data)
  }

  const needsReview = computed(() =>
    servers.value.some((server) =>
      server.tools.some((tool) => tool.changed_since_review)
    )
  )

  return {
    servers,
    loading,
    loadError,
    needsReview,
    load,
    create,
    update,
    remove,
    refreshTools,
    updateTools,
  }
}
