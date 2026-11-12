import { API_ERROR_CODE } from '@baserow/modules/agent/constants'

/** Raised when signing in with an MCP server's provider didn't connect it. */
export class MCPSignInError extends Error {
  constructor(reason) {
    super(reason || 'Sign-in not completed')
    this.reason = reason
  }
}

/** Raised when the editor gave up on a sign-in, e.g. by closing the modal. */
export class MCPSignInCancelled extends Error {}

const MESSAGES = {
  [API_ERROR_CODE.MCP_SERVER_REFUSED_CREDENTIAL]: [
    'agent.connectedAppRefusedTitle',
    'agent.connectedAppRefused',
  ],
  [API_ERROR_CODE.MCP_SERVER_UNREACHABLE]: [
    'agent.connectedAppUnreachableTitle',
    'agent.connectedAppUnreachable',
  ],
  [API_ERROR_CODE.MCP_SERVER_NOT_CONNECTED]: [
    'agent.connectedAppNotConnectedTitle',
    'agent.connectedAppNotConnectedMessage',
  ],
  [API_ERROR_CODE.MCP_OAUTH_STATE_INVALID]: [
    'agent.connectedAppSignInFailedTitle',
    'agent.connectedAppStateInvalid',
  ],
  [API_ERROR_CODE.MCP_SERVER_DOES_NOT_USE_OAUTH]: [
    'agent.connectedAppSignInFailedTitle',
    'agent.connectedAppDoesNotUseOAuth',
  ],
}

/**
 * The title and message to show for a failed MCP server request or sign-in.
 * Marks an API error as handled.
 *
 * @param {Function} t The translate function.
 * @param {Error} error What failed.
 * @returns {{title: string, message: string}}
 * @throws The error, when it isn't an API error or a sign-in error.
 */
export function mcpErrorMessage(t, error) {
  if (error instanceof MCPSignInError) {
    return {
      title: t('agent.connectedAppSignInFailedTitle'),
      message: error.reason || t('agent.connectedAppSignInFailed'),
    }
  }
  if (!error.handler) throw error
  error.handler.handled()
  const code = error.handler.code
  if (code === API_ERROR_CODE.MCP_OAUTH_FAILED) {
    // The detail says what the provider or server did, e.g. no OAuth support.
    return {
      title: t('agent.connectedAppSignInFailedTitle'),
      message: error.handler.detail || t('agent.connectedAppSignInFailed'),
    }
  }
  if (MESSAGES[code]) {
    const [title, message] = MESSAGES[code]
    return { title: t(title), message: t(message) }
  }
  return error.handler.getMessage()
}
