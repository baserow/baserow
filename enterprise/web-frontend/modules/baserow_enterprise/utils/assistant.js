import { RUN_STATUS } from '@baserow/modules/core/chatRuns/constants'

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

const RUN_ERROR_KEYS = {
  interrupted: 'assistant.runErrorInterrupted',
  not_started: 'assistant.runErrorNotStarted',
  timeout: 'assistant.runErrorTimeout',
  failed: 'assistant.runErrorFailed',
  persist_failed: 'assistant.runErrorPersistFailed',
  model_unavailable: 'assistant.runErrorModelUnavailable',
}

/**
 * The locale key that explains how the run that wrote an AI message failed,
 * or null when it didn't. An error code added later reads as a failure.
 */
export function runOutcomeKey({ run_status: status, error_code: errorCode }) {
  if (RUN_ERROR_KEYS[errorCode]) {
    return RUN_ERROR_KEYS[errorCode]
  }
  return status === RUN_STATUS.FAILED ? 'assistant.runErrorFailed' : null
}
