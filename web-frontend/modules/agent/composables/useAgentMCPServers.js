import { ref } from 'vue'
import { useNuxtApp } from '#app'
import IntegrationService from '@baserow/modules/core/services/integration'
import MCPServerService from '@baserow/modules/agent/services/mcpServer'
import {
  MCP_OAUTH_MESSAGE_TYPE,
  MCP_SERVER_INTEGRATION_TYPE,
} from '@baserow/modules/agent/constants'

// How often to check whether the sign-in popup was closed.
const POPUP_POLL_MS = 500
// A provider page can cut the popup off from Baserow, which then reports it as
// closed while the editor is still signing in. The server is checked this
// often, for this long, before giving up.
const STATUS_POLL_MS = 2000
const STATUS_POLL_LIMIT_MS = 120000

/** Raised when signing in with an MCP server's provider didn't connect it. */
export class MCPSignInError extends Error {
  constructor(reason) {
    super(reason || 'Sign-in not completed')
    this.reason = reason
  }
}

/**
 * Open the sign-in popup. Call it straight from a click, before any request,
 * or the browser blocks it.
 */
export function openSignInPopup() {
  return window.open('', 'baserow-mcp-oauth', 'popup,width=520,height=720')
}

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

  async function reloadServer(server) {
    const { data } = await integrations.fetchAll(agent.value.id)
    const fresh = data.find(({ id }) => id === server.id)
    return fresh ? replace(fresh) : null
  }

  /**
   * Resolve with the callback page's message, or null once the popup closes
   * without one. A provider page can cut the popup off from its opener, so the
   * message is only a shortcut: the stored server is checked either way.
   */
  function waitForSignIn(popup) {
    return new Promise((resolve) => {
      const finish = (result) => {
        window.removeEventListener('message', onMessage)
        clearInterval(timer)
        resolve(result)
      }
      const onMessage = (event) => {
        if (
          event.origin === window.location.origin &&
          event.data?.type === MCP_OAUTH_MESSAGE_TYPE
        ) {
          finish(event.data)
        }
      }
      const timer = setInterval(() => {
        if (!popup || popup.closed) finish(null)
      }, POPUP_POLL_MS)
      window.addEventListener('message', onMessage)
    })
  }

  /**
   * Sign in with the server's provider in the given popup, then list the
   * server's tools.
   *
   * @throws {MCPSignInError} When no account got connected.
   */
  async function connect(server, popup) {
    let authorizationUrl
    try {
      const { data } = await mcp.startOAuth(server.id)
      authorizationUrl = data.authorization_url
    } catch (error) {
      popup?.close()
      throw error
    }
    if (!popup) throw new MCPSignInError(null)
    popup.location.href = authorizationUrl
    const message = await waitForSignIn(popup)
    // Some browsers keep the popup open after the callback page closes itself.
    popup.close()
    let updated = await reloadServer(server)
    if (!message) {
      const deadline = Date.now() + STATUS_POLL_LIMIT_MS
      while (!updated?.oauth_connected && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, STATUS_POLL_MS))
        updated = await reloadServer(server)
      }
    }
    if (!updated?.oauth_connected) throw new MCPSignInError(message?.error)
    return await refreshTools(updated)
  }

  async function disconnect(server) {
    const { data } = await mcp.disconnectOAuth(server.id)
    return replace(data)
  }

  async function refreshTools(server) {
    const { data } = await mcp.refreshTools(server.id)
    return replace(data)
  }

  async function updateTools(server, tools) {
    const { data } = await mcp.updateTools(server.id, tools)
    return replace(data)
  }

  return {
    servers,
    loading,
    loadError,
    load,
    create,
    update,
    remove,
    refreshTools,
    updateTools,
    connect,
    disconnect,
  }
}
