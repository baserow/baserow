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
