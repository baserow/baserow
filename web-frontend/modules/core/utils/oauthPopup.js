/**
 * Signing in with another service in a popup: the page that starts the
 * sign-in opens the popup, the provider redirects the popup to a Baserow
 * callback page, and that page reports back. Used by the MCP servers of an
 * Agent and by the integrations that connect an account.
 */

/**
 * Open a sign-in popup. Call it straight from a click, before any request, or
 * the browser blocks it. Each gets its own name, so two sign-ins never share
 * one window.
 *
 * @param {string} prefix Names the window, e.g. `baserow-mcp-oauth`.
 * @returns {Window|null} The popup, null when the browser blocked it.
 */
export function openOAuthPopup(prefix) {
  const name = `${prefix}-${Math.random().toString(36).slice(2)}`
  return window.open('', name, 'popup,width=520,height=720')
}

/**
 * Resolve with the callback page's result for one sign-in. It's matched by
 * the sign-in's state, so another sign-in finishing doesn't end this one. The
 * popup closing isn't waited for: a provider page can cut it off from Baserow,
 * which then sees it as closed while the person is still signing in.
 *
 * @param {string} type The message type, also the channel name.
 * @param {string} state The state of the authorization URL.
 * @param {Object} options
 * @param {AbortSignal} options.signal Gives up on the sign-in.
 * @param {number} options.timeoutMs Gives up after this long.
 * @param {Function} options.cancelled Builds the error to reject with when
 *   the signal aborts.
 * @param {Function} options.timedOut Builds the error to reject with when
 *   the time is up.
 * @returns {Promise<Object>} The message the callback page sent.
 */
export function waitForOAuthResult(
  type,
  state,
  { signal = null, timeoutMs, cancelled, timedOut }
) {
  return new Promise((resolve, reject) => {
    const channel = new BroadcastChannel(type)
    const finish = (settle) => {
      channel.close()
      window.removeEventListener('message', onWindowMessage)
      signal?.removeEventListener('abort', onAbort)
      clearTimeout(timer)
      settle()
    }
    const onResult = (data) => {
      if (data?.type === type && data.state === state) {
        finish(() => resolve(data))
      }
    }
    const onWindowMessage = (event) => {
      if (event.origin === window.location.origin) onResult(event.data)
    }
    const onAbort = () => finish(() => reject(cancelled()))
    const timer = setTimeout(() => finish(() => reject(timedOut())), timeoutMs)
    channel.onmessage = (event) => onResult(event.data)
    window.addEventListener('message', onWindowMessage)
    signal?.addEventListener('abort', onAbort)
    if (signal?.aborted) onAbort()
  })
}

/**
 * From the callback page: tell the page waiting for this sign-in how it went.
 * The channel reaches it even when the provider cut the popup off from it;
 * the opener is told too where it's still there.
 *
 * @param {Object} message Must carry `type` and `state`.
 */
export function announceOAuthResult(message) {
  const channel = new BroadcastChannel(message.type)
  channel.postMessage(message)
  channel.close()
  if (window.opener) {
    window.opener.postMessage(message, window.location.origin)
  }
}
