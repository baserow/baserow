import { RUN_STATUS } from '@baserow/modules/core/chatRuns/constants'

export function replyUndoGroup(message, store) {
  return message?.undo?.session_id ===
    store.getters['auth/getUntrustedClientSessionId']
    ? message?.undo?.group_id
    : null
}

/**
 * Whether the workspace has the assistant switched on, falling back to the
 * model that used to be configured for the whole instance.
 */
export const isAssistantConfigured = (app, workspace) =>
  workspace.ai_features?.kuma?.is_enabled ??
  !!app.$config.public.baserowEnterpriseAssistantLlmModel

/**
 * Whether the user can actually chat with the assistant in this workspace. Kept
 * in one place because the sidebar entry, the panel and the prompt on the
 * workspace homepage must agree on it.
 */
export const isAssistantAvailable = (app, workspace) =>
  app.$hasPermission('assistant.chat', workspace, workspace.id) &&
  isAssistantConfigured(app, workspace)

/**
 * Whether Stop was asked for a reply: in this tab, before the send is accepted
 * (`chat.cancelling`) or after, or in another tab. Kept in one place because the
 * panel, the navigation guard and the onboarding table must agree on it.
 *
 * @param {object|null} follower The follower of the reply's run, if any.
 * @param {object|null} chat The reply's chat, when Stop may come before its run.
 */
export const isStopping = (follower, chat = null) =>
  Boolean(
    chat?.cancelling ||
    follower?.stopRequested ||
    follower?.view.cancelRequested
  )

const RUN_ERROR_KEYS = {
  interrupted: 'assistant.runErrorInterrupted',
  not_started: 'assistant.runErrorNotStarted',
  timeout: 'assistant.runErrorTimeout',
  failed: 'assistant.runErrorFailed',
  persist_failed: 'assistant.runErrorPersistFailed',
  model_unavailable: 'assistant.runErrorModelUnavailable',
  access_lost: 'assistant.runErrorAccessLost',
}

/**
 * The locale key that explains how the run that wrote an AI message ended,
 * or null for a complete answer. An error code added later reads as a failure.
 */
export function runOutcomeKey({ run_status: status, error_code: errorCode }) {
  if (RUN_ERROR_KEYS[errorCode]) {
    return RUN_ERROR_KEYS[errorCode]
  }
  if (status === RUN_STATUS.CANCELLED) {
    return 'assistant.runStopped'
  }
  return status === RUN_STATUS.FAILED ? 'assistant.runErrorFailed' : null
}
