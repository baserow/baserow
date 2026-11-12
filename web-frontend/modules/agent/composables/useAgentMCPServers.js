import { computed, ref } from 'vue'
import { useNuxtApp } from '#app'
import { useStore } from 'vuex'
import MCPServerService from '@baserow/modules/agent/services/mcpServer'
import {
  MCP_OAUTH_MESSAGE_TYPE,
  MCP_SERVER_INTEGRATION_TYPE,
} from '@baserow/modules/agent/constants'
import {
  MCPSignInCancelled,
  MCPSignInError,
} from '@baserow/modules/agent/utils/mcp'

export { MCPSignInCancelled, MCPSignInError }

// As long as the backend keeps a started sign-in.
const SIGN_IN_TIMEOUT_MS = 600000

/**
 * Open a sign-in popup. Call it straight from a click, before any request, or
 * the browser blocks it. Each gets its own name, so two sign-ins never share
 * one window.
 */
export function openSignInPopup() {
  const name = `baserow-mcp-oauth-${Math.random().toString(36).slice(2)}`
  return window.open('', name, 'popup,width=520,height=720')
}

/**
 * Resolve with the callback page's result for this sign-in. It's matched by
 * the sign-in's state, so another sign-in finishing doesn't end this one. The
 * popup closing isn't waited for: a provider page can cut it off from Baserow,
 * which then sees it as closed while the editor is still signing in.
 *
 * @param {string} state The state of the authorization URL.
 * @param {AbortSignal} signal Gives up on the sign-in.
 */
function waitForSignIn(state, signal) {
  return new Promise((resolve, reject) => {
    const channel = new BroadcastChannel(MCP_OAUTH_MESSAGE_TYPE)
    const finish = (settle) => {
      channel.close()
      window.removeEventListener('message', onWindowMessage)
      signal?.removeEventListener('abort', onAbort)
      clearTimeout(timer)
      settle()
    }
    const onResult = (data) => {
      if (data?.type === MCP_OAUTH_MESSAGE_TYPE && data.state === state) {
        finish(() => resolve(data))
      }
    }
    const onWindowMessage = (event) => {
      if (event.origin === window.location.origin) onResult(event.data)
    }
    const onAbort = () => finish(() => reject(new MCPSignInCancelled()))
    const timer = setTimeout(
      () => finish(() => reject(new MCPSignInError(null))),
      SIGN_IN_TIMEOUT_MS
    )
    channel.onmessage = (event) => onResult(event.data)
    window.addEventListener('message', onWindowMessage)
    signal?.addEventListener('abort', onAbort)
    if (signal?.aborted) onAbort()
  })
}

/**
 * The MCP servers an Agent may call tools of. Each is an integration of the
 * Agent, kept in the integration store like those of other applications, so
 * other editors' changes arrive in real time. Its tools are listed by the
 * server and turned on by an editor.
 *
 * @param {Ref<Object>} agent The Agent.
 * @param {Function} onChange Called after a server is stored or removed: which
 *   tools a reply offers may have changed.
 */
export function useAgentMCPServers(agent, onChange = () => {}) {
  const { $client } = useNuxtApp()
  const store = useStore()
  const mcp = MCPServerService($client)

  const servers = computed(() =>
    store.getters['integration/getIntegrations'](agent.value).filter(
      (integration) => integration.type === MCP_SERVER_INTEGRATION_TYPE
    )
  )
  const loading = ref(false)
  const loadError = ref(false)

  const find = (id) =>
    store.getters['integration/getIntegrationById'](agent.value, id)

  async function load() {
    loading.value = true
    loadError.value = false
    try {
      await store.dispatch('integration/fetch', { application: agent.value })
    } catch {
      loadError.value = true
    } finally {
      loading.value = false
    }
  }

  /** Store a server an MCP endpoint answered with. */
  async function apply(data) {
    const integration = find(data.id)
    if (integration) {
      await store.dispatch('integration/forceUpdate', {
        application: agent.value,
        integration,
        values: data,
      })
    }
    onChange()
    return find(data.id) ?? data
  }

  async function create(values) {
    const integration = await store.dispatch('integration/create', {
      application: agent.value,
      integrationType: MCP_SERVER_INTEGRATION_TYPE,
      values,
    })
    onChange()
    return find(integration.id)
  }

  async function update(server, values) {
    await store.dispatch('integration/update', {
      application: agent.value,
      integrationId: server.id,
      values,
    })
    onChange()
    return find(server.id)
  }

  async function remove(server) {
    await store.dispatch('integration/delete', {
      application: agent.value,
      integrationId: server.id,
    })
    onChange()
  }

  /**
   * Sign in with the server's provider in the given popup, then list the
   * server's tools.
   *
   * @param {Object} server The server.
   * @param {Window} popup From `openSignInPopup`.
   * @param {AbortSignal} signal Gives up on the sign-in.
   * @param {Function} onStarted Called once the popup shows the provider.
   * @throws {MCPSignInError} When no account got connected.
   * @throws {MCPSignInCancelled} When the signal aborted.
   */
  async function connect(server, popup, signal, onStarted = () => {}) {
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
    onStarted()
    const state = new URL(authorizationUrl).searchParams.get('state')
    let result
    try {
      result = await waitForSignIn(state, signal)
    } finally {
      // Some browsers keep the popup open after the callback page closes it.
      popup.close()
    }
    if (result.error || !result.integration) {
      throw new MCPSignInError(result.error)
    }
    await apply(result.integration)
    return await refreshTools(find(server.id) ?? result.integration)
  }

  async function disconnect(server) {
    const { data } = await mcp.disconnectOAuth(server.id)
    return await apply(data)
  }

  async function refreshTools(server) {
    const { data } = await mcp.refreshTools(server.id)
    return await apply(data)
  }

  async function updateTools(server, tools) {
    const { data } = await mcp.updateTools(server.id, tools)
    return await apply(data)
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
