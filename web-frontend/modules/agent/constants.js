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
  ASK_FIRST_TOOLS: 'ask_first_tools',
  AVAILABLE_TOOLS: 'available_tools',
  WEB_SEARCH_ENABLED: 'web_search_enabled',
  WEB_SEARCH_AVAILABLE: 'web_search_available',
  WEB_SEARCH_BLOCKED_BY_TOOLS: 'web_search_blocked_by_tools',
  AVAILABLE_TRIGGER_TYPES: 'available_trigger_types',
  MAX_QUEUED_TRIGGER_RUNS: 'max_queued_trigger_runs',
})

// Null keeps the model's default reasoning.
export const REASONING_EFFORTS = Object.freeze([
  { value: 'off', label: 'agent.reasoningEffortOff' },
  { value: 'low', label: 'agent.reasoningEffortLow' },
  { value: 'medium', label: 'agent.reasoningEffortMedium' },
  { value: 'high', label: 'agent.reasoningEffortHigh' },
])

export const TRIGGER_OVERLAP_OPTIONS = Object.freeze([
  {
    value: 'skip',
    label: 'agent.triggerOnOverlapSkip',
    hint: 'agent.triggerOnOverlapSkipHint',
    recommended: true,
  },
  {
    value: 'wait',
    label: 'agent.triggerOnOverlapWait',
    hint: 'agent.triggerOnOverlapWaitHint',
    unlimitedHint: 'agent.triggerOnOverlapWaitUnlimitedHint',
  },
])

export const TRIGGER_SKIP_REASON_TEXT = Object.freeze({
  rate_limited: 'agent.triggerSkippedRateLimited',
  agent_rate_limited: 'agent.triggerSkippedAgentRateLimited',
  previous_running: 'agent.triggerSkippedPreviousRunning',
  queue_full: 'agent.triggerSkippedQueueFull',
})

// Mirrors the backend's AGENT_TRIGGER_NAME_MAX_LENGTH.
export const TRIGGER_NAME_MAX_LENGTH = 75

export const CONFIGURATION_SAVE_RESULT = Object.freeze({
  REJECTED_IDENTITY: 'rejected_identity',
})

export const MESSAGE_ROLE = Object.freeze({
  USER: 'user',
  ASSISTANT: 'assistant',
  TRIGGER: 'trigger',
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
  MCP_SERVER_DOES_NOT_USE_OAUTH: 'ERROR_MCP_SERVER_DOES_NOT_USE_OAUTH',
  AGENT_CONVERSATION_WAITING_FOR_APPROVAL:
    'ERROR_AGENT_CONVERSATION_WAITING_FOR_APPROVAL',
  AGENT_TOOL_APPROVAL_NOT_PENDING: 'ERROR_AGENT_TOOL_APPROVAL_NOT_PENDING',
  AGENT_CONVERSATION_READ_ONLY: 'ERROR_AGENT_CONVERSATION_READ_ONLY',
  AGENT_TRIGGER_DOES_NOT_EXIST: 'ERROR_AGENT_TRIGGER_DOES_NOT_EXIST',
  TRIGGER_SERVICE_MISCONFIGURED: 'ERROR_TRIGGER_SERVICE_MISCONFIGURED',
})

export const MCP_SERVER_INTEGRATION_TYPE = 'mcp_server'

export const MCP_AUTH_TYPE = Object.freeze({
  NONE: 'none',
  HEADER: 'header',
  OAUTH: 'oauth',
})

// The channel and message type the OAuth callback page reports on. Unlike
// `window.opener`, the channel still works when the provider's page cut the
// popup off from Baserow, as a `Cross-Origin-Opener-Policy` header does.
export const MCP_OAUTH_MESSAGE_TYPE = 'baserow-mcp-oauth'

export const AGENT_REPLY_ERROR_CODE = Object.freeze({
  NOT_READY: 'not_ready',
  NOT_ALLOWED: 'not_allowed',
  RUN_LIMIT_REACHED: 'chat_run_limit_reached',
  TRIGGER_MESSAGE_FAILED: 'trigger_message_failed',
  TRIGGER_OFF: 'trigger_off',
})

export const RUN_AS_STATUS = Object.freeze({
  UNSET: 'unset',
  ACTIVE: 'active',
  TRASHED: 'trashed',
  MISSING: 'missing',
})
