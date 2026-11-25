import { ERROR_CHAT_RUN_IN_PROGRESS } from '@baserow/modules/core/chatRuns/constants'

export const AGENT_APPLICATION_TYPE = 'agent'

/** The built-in tool a triggered run calls to ask a person a question. */
export const ASK_PERSON_TOOL = 'ask_person'
export const ASK_PERSON_ANSWER_MAX_LENGTH = 10000
export const AGENT_SUGGESTED_MESSAGES_MAX = 4
export const AGENT_SUGGESTED_MESSAGE_MAX_LENGTH = 200

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
  SUGGESTED_MESSAGES: 'suggested_messages',
  PROVIDER_TYPE: 'provider_type',
  MODEL_IDENTIFIER: 'model_identifier',
  REASONING_EFFORT: 'reasoning_effort',
  APPLIED_REASONING_EFFORT: 'applied_reasoning_effort',
  RUN_AS: 'run_as',
  ALLOWED_TOOLS: 'allowed_tools',
  ASK_FIRST_TOOLS: 'ask_first_tools',
  PENDING_TOOLS: 'pending_tools',
  PENDING_ASK_FIRST_TOOLS: 'pending_ask_first_tools',
  AVAILABLE_TOOLS: 'available_tools',
  WEB_SEARCH_ENABLED: 'web_search_enabled',
  WEB_SEARCH_AVAILABLE: 'web_search_available',
  WEB_SEARCH_BLOCKED_BY_TOOLS: 'web_search_blocked_by_tools',
  WEB_FETCH_ENABLED: 'web_fetch_enabled',
  AVAILABLE_TRIGGER_TYPES: 'available_trigger_types',
  AVAILABLE_ACTION_TYPES: 'available_action_types',
  MAX_ACTIONS: 'max_actions',
  MAX_QUEUED_TRIGGER_RUNS: 'max_queued_trigger_runs',
  MAX_PARALLEL_TRIGGER_RUNS: 'max_parallel_trigger_runs',
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
  },
  {
    value: 'wait',
    label: 'agent.triggerOnOverlapWait',
    hint: 'agent.triggerOnOverlapWaitHint',
    unlimitedHint: 'agent.triggerOnOverlapWaitUnlimitedHint',
  },
  {
    value: 'parallel',
    label: 'agent.triggerOnOverlapParallel',
    hint: 'agent.triggerOnOverlapParallelHint',
    unlimitedHint: 'agent.triggerOnOverlapParallelUnlimitedHint',
    queueUnlimitedHint: 'agent.triggerOnOverlapParallelQueueUnlimitedHint',
    cap: 'parallel',
  },
])

export const TRIGGER_SKIP_REASON_TEXT = Object.freeze({
  rate_limited: 'agent.triggerSkippedRateLimited',
  agent_rate_limited: 'agent.triggerSkippedAgentRateLimited',
  previous_running: 'agent.triggerSkippedPreviousRunning',
  queue_full: 'agent.triggerSkippedQueueFull',
  no_access: 'agent.triggerSkippedNoAccess',
  event_too_large: 'agent.triggerSkippedEventTooLarge',
})

// Mirrors the backend's AGENT_TRIGGER_MAX_BATCH_SIZE.
export const TRIGGER_MAX_BATCH_SIZE = 100

// Mirrors the backend's AGENT_TRIGGER_NAME_MAX_LENGTH.
export const TRIGGER_NAME_MAX_LENGTH = 75

export const CONFIGURATION_SAVE_RESULT = Object.freeze({
  REJECTED_IDENTITY: 'rejected_identity',
})

export const MESSAGE_ROLE = Object.freeze({
  USER: 'user',
  ASSISTANT: 'assistant',
  TRIGGER: 'trigger',
  VISITOR: 'visitor',
})

// Error responses handled by the Agent API client, including shared API errors.
export const API_ERROR_CODE = Object.freeze({
  AGENT_NOT_READY: 'ERROR_AGENT_NOT_READY',
  REQUEST_BODY_VALIDATION: 'ERROR_REQUEST_BODY_VALIDATION',
  CHAT_RUN_IN_PROGRESS: ERROR_CHAT_RUN_IN_PROGRESS,
  AGENT_BUSY: 'ERROR_AGENT_BUSY',
  AGENT_MESSAGE_CONFLICT: 'ERROR_AGENT_MESSAGE_CONFLICT',
  AGENT_CONVERSATION_DOES_NOT_EXIST: 'ERROR_AGENT_CONVERSATION_DOES_NOT_EXIST',
  AGENT_CHANNEL_DOES_NOT_EXIST: 'ERROR_AGENT_CHANNEL_DOES_NOT_EXIST',
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
  AGENT_TRIGGER_DOES_NOT_EXIST: 'ERROR_AGENT_TRIGGER_DOES_NOT_EXIST',
  TRIGGER_SERVICE_MISCONFIGURED: 'ERROR_TRIGGER_SERVICE_MISCONFIGURED',
  AGENT_TRIGGER_NO_ACCESS: 'ERROR_AGENT_TRIGGER_NO_ACCESS',
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
  CHANNEL_OFF: 'channel_off',
  PROVIDER_AUTH_FAILED: 'provider_auth_failed',
  PROVIDER_RATE_LIMITED: 'provider_rate_limited',
  PROVIDER_UNAVAILABLE: 'provider_unavailable',
})

export const RUN_AS_STATUS = Object.freeze({
  UNSET: 'unset',
  ACTIVE: 'active',
  TRASHED: 'trashed',
  MISSING: 'missing',
})

export const CONFIGURATION_SECTION_GROUP = Object.freeze({
  ESSENTIALS: 'essentials',
  START: 'start',
  CAPABILITIES: 'capabilities',
})

/** The groups of the configuration sidebar, in the order they are shown. */
export const CONFIGURATION_SECTION_GROUPS = Object.freeze([
  {
    type: CONFIGURATION_SECTION_GROUP.ESSENTIALS,
    name: 'agent.groupEssentials',
    optional: false,
  },
  {
    type: CONFIGURATION_SECTION_GROUP.START,
    name: 'agent.groupStart',
    optional: true,
  },
  {
    type: CONFIGURATION_SECTION_GROUP.CAPABILITIES,
    name: 'agent.groupCapabilities',
    optional: true,
  },
])

/** The configuration section where the Agent's workspace identity is set. */
export const WORKSPACE_ACCESS_SECTION = 'workspace_access'
