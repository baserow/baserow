export const AGENT_APPLICATION_TYPE = 'agent'

export const AGENT_READINESS = Object.freeze({
  INCOMPLETE: 'incomplete',
  UNAVAILABLE: 'unavailable',
  READY: 'ready',
})

export const CONFIGURATION_ERROR = Object.freeze({
  REQUIRED: 'required',
  UNAVAILABLE: 'unavailable',
})

export const CONFIGURATION_FIELD = Object.freeze({
  INSTRUCTIONS: 'instructions',
  PROVIDER_TYPE: 'provider_type',
  MODEL_IDENTIFIER: 'model_identifier',
  REASONING_EFFORT: 'reasoning_effort',
  APPLIED_REASONING_EFFORT: 'applied_reasoning_effort',
  RUN_AS: 'run_as',
  ALLOWED_TOOLS: 'allowed_tools',
  AVAILABLE_TOOLS: 'available_tools',
  WEB_SEARCH_ENABLED: 'web_search_enabled',
  WEB_SEARCH_AVAILABLE: 'web_search_available',
  WEB_SEARCH_BLOCKED_BY_TOOLS: 'web_search_blocked_by_tools',
})

// Null keeps the model's default reasoning.
export const REASONING_EFFORTS = Object.freeze([
  { value: 'off', label: 'agent.reasoningEffortOff' },
  { value: 'low', label: 'agent.reasoningEffortLow' },
  { value: 'medium', label: 'agent.reasoningEffortMedium' },
  { value: 'high', label: 'agent.reasoningEffortHigh' },
])

export const CONFIGURATION_SAVE_RESULT = Object.freeze({
  REJECTED_IDENTITY: 'rejected_identity',
})

export const MESSAGE_ROLE = Object.freeze({
  USER: 'user',
  ASSISTANT: 'assistant',
  SYSTEM: 'system',
})

// Error responses handled by the Agent API client, including shared API errors.
export const API_ERROR_CODE = Object.freeze({
  AGENT_NOT_READY: 'ERROR_AGENT_NOT_READY',
  REQUEST_BODY_VALIDATION: 'ERROR_REQUEST_BODY_VALIDATION',
  CHAT_RUN_IN_PROGRESS: 'ERROR_CHAT_RUN_IN_PROGRESS',
  AGENT_BUSY: 'ERROR_AGENT_BUSY',
  AGENT_MESSAGE_CONFLICT: 'ERROR_AGENT_MESSAGE_CONFLICT',
  AGENT_CONVERSATION_DOES_NOT_EXIST: 'ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST',
  AGENT_RUN_AS_SUBJECT_DOES_NOT_EXIST:
    'ERROR_AGENT_RUN_AS_SUBJECT_DOES_NOT_EXIST',
  MCP_SERVER_UNREACHABLE: 'ERROR_MCP_SERVER_UNREACHABLE',
  MCP_SERVER_REFUSED_CREDENTIAL: 'ERROR_MCP_SERVER_REFUSED_CREDENTIAL',
  MCP_SERVER_NOT_CONNECTED: 'ERROR_MCP_SERVER_NOT_CONNECTED',
  MCP_OAUTH_FAILED: 'ERROR_MCP_OAUTH_FAILED',
  MCP_OAUTH_STATE_INVALID: 'ERROR_MCP_OAUTH_STATE_INVALID',
})

export const MCP_SERVER_INTEGRATION_TYPE = 'mcp_server'

export const MCP_AUTH_TYPE = Object.freeze({
  NONE: 'none',
  HEADER: 'header',
  OAUTH: 'oauth',
})

// The message the OAuth callback page sends to the window that opened it.
export const MCP_OAUTH_MESSAGE_TYPE = 'baserow-mcp-oauth'

export const AGENT_REPLY_ERROR_CODE = Object.freeze({
  NOT_READY: 'not_ready',
  NOT_ALLOWED: 'not_allowed',
})

export const RUN_AS_STATUS = Object.freeze({
  UNSET: 'unset',
  ACTIVE: 'active',
  TRASHED: 'trashed',
  MISSING: 'missing',
})
