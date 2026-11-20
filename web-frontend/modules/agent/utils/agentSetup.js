import AgentApplicationService from '@baserow/modules/agent/services/agentApplication'
import AgentTriggerService from '@baserow/modules/agent/services/agentTriggers'
import AgentActionService from '@baserow/modules/agent/services/agentActions'
import { AGENT_APPLICATION_TYPE } from '@baserow/modules/agent/constants'
import { ActionToolPresentationType } from '@baserow/modules/agent/toolPresentationTypes'
import { usableAgentTools } from '@baserow/modules/agent/agentTools'
import {
  newTriggerValues,
  serviceTypeOf,
} from '@baserow/modules/agent/utils/triggers'
import { UserSubjectType } from '@baserow/modules/core/subjectTypes'
import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'
import { getEnabledModelsForAIProviderFeature } from '@baserow/modules/core/aiProviderModelFeatureTypes'

export const SCHEDULE_TRIGGER_TYPE = 'periodic'
export const SETUP_START = Object.freeze({ CHAT: 'chat', SCHEDULE: 'schedule' })
export const SETUP_ACTS_AS = Object.freeze({
  NEW: 'new',
  EXISTING: 'existing',
  NONE: 'none',
})
export const SETUP_PERMISSIONS = Object.freeze({
  READ: 'read',
  ASK: 'ask',
  CHANGE: 'change',
  CUSTOM: 'custom',
})
const AI_AGENT_FEATURE = 'ai_agent'
// The agent's new identity takes its name, and identity names are shorter.
export const IDENTITY_NAME_MAX_LENGTH = 150

/**
 * @typedef {object} AgentSetup
 * @property {string} name
 * @property {string} instructions
 * @property {'chat'|'schedule'} start
 * @property {object|null} schedule What differs from the default schedule,
 *   used while it starts on a schedule.
 * @property {{kind: 'new'}|{kind: 'existing', id: number, name: string, roleUid: string}|{kind: 'none'}} actsAs
 * @property {'read'|'ask'|'change'|'custom'} permissions
 * @property {{allowed_tools: string[], ask_first_tools: string[]}|null} customTools
 *   The tools picked one by one, used while the permissions are custom.
 * @property {string|null} providerType
 * @property {string|null} modelIdentifier
 * @property {'off'|'low'|'medium'|'high'|null} reasoningEffort Null is the
 *   model's default.
 * @property {boolean} webSearch
 * @property {string[]} actionTypes Service type names of the actions to add.
 */

export const SETUP_SUGGESTIONS = Object.freeze([
  {
    icon: 'iconoir-globe',
    labelKey: 'agent.setupSuggestionInvest',
    nameKey: 'agent.setupSuggestionInvestName',
    instructionsKey: 'agent.setupSuggestionInvestInstructions',
    setup: {
      start: SETUP_START.SCHEDULE,
      schedule: null,
      permissions: SETUP_PERMISSIONS.ASK,
      webSearch: true,
      actionTypes: [],
    },
  },
  {
    icon: 'iconoir-mail',
    labelKey: 'agent.setupSuggestionOutreach',
    nameKey: 'agent.setupSuggestionOutreachName',
    instructionsKey: 'agent.setupSuggestionOutreachInstructions',
    setup: {
      start: SETUP_START.CHAT,
      schedule: null,
      permissions: SETUP_PERMISSIONS.READ,
      webSearch: true,
      actionTypes: ['smtp_email'],
    },
  },
  {
    icon: 'iconoir-table',
    labelKey: 'agent.setupSuggestionTriage',
    nameKey: 'agent.setupSuggestionTriageName',
    instructionsKey: 'agent.setupSuggestionTriageInstructions',
    setup: {
      start: SETUP_START.CHAT,
      schedule: null,
      permissions: SETUP_PERMISSIONS.ASK,
      webSearch: false,
      actionTypes: [],
    },
  },
  {
    icon: 'iconoir-calendar',
    labelKey: 'agent.setupSuggestionSummary',
    nameKey: 'agent.setupSuggestionSummaryName',
    instructionsKey: 'agent.setupSuggestionSummaryInstructions',
    setup: {
      start: SETUP_START.SCHEDULE,
      schedule: { interval: 'WEEK', day_of_week: 0 },
      permissions: SETUP_PERMISSIONS.READ,
      webSearch: false,
      actionTypes: [],
    },
  },
])

/**
 * Choose the new identity's workspace role from the requested workspace tools.
 * A write that requires approval still needs an identity that can perform it.
 * Workspaces without role-based access control offer Member instead.
 */
export function newIdentityRole(workspace, setup, availableTools) {
  const changesData =
    setup.permissions === SETUP_PERMISSIONS.CUSTOM
      ? availableTools.some(
          (tool) =>
            tool.changes_data &&
            setup.customTools.allowed_tools.includes(tool.name)
        )
      : setup.permissions !== SETUP_PERMISSIONS.READ
  const roles = (workspace._?.roles || []).filter(
    (role) =>
      role.isVisible &&
      !role.isDeactivated &&
      (!Array.isArray(role.allowedSubjectTypes) ||
        role.allowedSubjectTypes.includes(UserSubjectType.getType()))
  )
  return (
    roles.find((role) => role.uid === (changesData ? 'BUILDER' : 'VIEWER')) ??
    roles.find((role) => role.uid === 'MEMBER')
  )
}

/**
 * @param {string} name The agent's name.
 * @param {object} workspace The workspace the agent is created in.
 * @param {boolean} canCreateIdentity Whether the user may create identities.
 * @returns {AgentSetup} The choices the wizard starts with.
 */
export function emptyAgentSetup(name, workspace, canCreateIdentity) {
  const [providerType = null, models = []] =
    Object.entries(setupEnabledModels(workspace)).find(
      ([, identifiers]) => identifiers.length > 0
    ) ?? []
  return {
    name,
    instructions: '',
    start: SETUP_START.CHAT,
    schedule: null,
    actsAs: canCreateIdentity
      ? { kind: SETUP_ACTS_AS.NEW }
      : { kind: SETUP_ACTS_AS.NONE },
    permissions: SETUP_PERMISSIONS.ASK,
    customTools: null,
    providerType,
    modelIdentifier: models[0] ?? null,
    reasoningEffort: null,
    webSearch: false,
    actionTypes: [],
  }
}

/**
 * @param {object} suggestion One of `SETUP_SUGGESTIONS`.
 * @param {Function} t The translate function.
 * @param {string[]} offeredActionTypes The action types the wizard offers.
 * @param {string[]} takenNames The names already used in the workspace.
 * @returns {object} The choices the suggestion fills in: its name, its
 *   instructions and the setup they describe.
 */
export function suggestionSetup(suggestion, t, offeredActionTypes, takenNames) {
  return {
    name: getNextAvailableNameInSequence(t(suggestion.nameKey), takenNames),
    instructions: t(suggestion.instructionsKey),
    ...suggestion.setup,
    actionTypes: suggestion.setup.actionTypes.filter((type) =>
      offeredActionTypes.includes(type)
    ),
  }
}

/**
 * @param {object} registry The app registry.
 * @param {object|null} schedule What differs from the default schedule.
 * @returns {object} The service values of the schedule's trigger.
 */
export function scheduleValues(registry, schedule) {
  return {
    ...registry
      .get('service', SCHEDULE_TRIGGER_TYPE)
      .getDefaultValues(null, {}),
    ...schedule,
  }
}

/**
 * @param {object} workspace The workspace the agent is created in.
 * @returns {Object<string, string[]>} The models an agent can use, by provider.
 */
export function setupEnabledModels(workspace) {
  return getEnabledModelsForAIProviderFeature(workspace, AI_AGENT_FEATURE)
}

/**
 * @param {Array<{name: string, changes_data: boolean}>} availableTools The
 *   tools the agent can be given.
 * @param {'read'|'ask'|'change'} permissions The chosen preset.
 * @returns {{allowed_tools: string[], ask_first_tools: string[]}} The tools
 *   allowed and those that ask first.
 */
export function toolsForPermissions(availableTools, permissions) {
  const usableTools = usableAgentTools(availableTools)
  const allowed =
    permissions === SETUP_PERMISSIONS.READ
      ? usableTools.filter((tool) => !tool.changes_data)
      : usableTools
  return {
    allowed_tools: allowed.map((tool) => tool.name),
    ask_first_tools:
      permissions === SETUP_PERMISSIONS.ASK
        ? allowed.filter((tool) => tool.changes_data).map((tool) => tool.name)
        : [],
  }
}

/**
 * @param {AgentSetup} setup The wizard's choices.
 * @param {Array<{name: string, changes_data: boolean}>} availableTools The
 *   tools the agent can be given.
 * @returns {{allowed_tools: string[], ask_first_tools: string[]}} The tools the
 *   choices allow and those that ask first.
 */
export function setupTools(setup, availableTools) {
  return setup.permissions === SETUP_PERMISSIONS.CUSTOM
    ? setup.customTools
    : toolsForPermissions(availableTools, setup.permissions)
}

/**
 * @param {object} registry The app registry.
 * @param {object} workspace The workspace the agent is created in.
 * @returns {object[]} The service types of the actions the wizard offers.
 */
export function setupActionTypes(registry, workspace) {
  return registry
    .getOrderedList('toolPresentation')
    .filter(
      (presentation) => presentation instanceof ActionToolPresentationType
    )
    .map((presentation) => serviceTypeOf(registry, presentation.getType()))
    .filter(
      (serviceType) => serviceType && !serviceType.isDeactivated({ workspace })
    )
}

/**
 * Creates the identity the wizard offered, so a retry reuses it.
 *
 * @param {{store: object}} context The store.
 * @param {object} workspace The workspace the identity is created in.
 * @param {AgentSetup} setup The wizard's choices.
 * @param {string|undefined} roleUid The workspace role shown for the identity.
 * @returns {Promise<AgentSetup>} The choices, acting as the created identity
 *   when a new one was chosen.
 */
export async function createSetupIdentity(
  { store },
  workspace,
  setup,
  roleUid
) {
  if (setup.actsAs.kind !== SETUP_ACTS_AS.NEW) return setup
  const identity = await store.dispatch('identity/create', {
    workspaceId: workspace.id,
    values: { name: setup.name, role_uid: roleUid },
  })
  return {
    ...setup,
    actsAs: {
      kind: SETUP_ACTS_AS.EXISTING,
      id: identity.id,
      name: identity.name,
      roleUid,
    },
  }
}

function runAsOf({ actsAs }) {
  return actsAs.kind === SETUP_ACTS_AS.EXISTING
    ? { type: UserSubjectType.getType(), id: actsAs.id }
    : null
}

/**
 * @param {object|null} configuration The new agent's configuration, null when
 *   it couldn't be read.
 * @param {{type: string, id: number}|null} runAs The identity to run as.
 * @param {AgentSetup} setup The wizard's choices.
 * @param {string[]} notApplied Collects what can't be applied.
 * @param {Function} t The translate function.
 * @returns {object} The configuration values to save, without web search.
 */
function configurationValues(configuration, runAs, setup, notApplied, t) {
  const values = {}
  if (setup.instructions.trim()) values.instructions = setup.instructions
  if (setup.providerType && setup.modelIdentifier) {
    values.provider_type = setup.providerType
    values.model_identifier = setup.modelIdentifier
  }
  if (setup.reasoningEffort) values.reasoning_effort = setup.reasoningEffort
  if (runAs) {
    values.run_as = runAs
    if (configuration || setup.permissions === SETUP_PERMISSIONS.CUSTOM) {
      Object.assign(
        values,
        setupTools(setup, configuration?.available_tools ?? [])
      )
    } else {
      notApplied.push(t('agent.setupPermissions'))
    }
  }
  return values
}

async function readConfiguration(agentService, agentId) {
  try {
    const { data } = await agentService.getConfiguration(agentId)
    return data
  } catch {
    return null
  }
}

function webSearchWarningOf(setup, saved, t) {
  if (!setup.webSearch || !saved || saved.web_search_available) return null
  return saved.web_search_blocked_by_tools
    ? t('agent.webSearchBlockedByTools')
    : t('agent.setupWebSearchUnsupported')
}

/**
 * @param {object} agentService The agent application service.
 * @param {number} agentId The id of the new agent.
 * @returns {Promise<boolean>} Whether web search was turned on.
 */
async function enableWebSearch(agentService, agentId) {
  try {
    await agentService.updateConfiguration(agentId, {
      web_search_enabled: true,
    })
    return true
  } catch {
    return false
  }
}

/**
 * Creates the agent, then applies each choice through the endpoints its
 * Configuration uses. Only the agent itself must be created; any other step
 * that fails is reported and the rest still runs. A new identity is created
 * beforehand with `createSetupIdentity`.
 *
 * @param {{store: object, client: object, registry: object, t: Function}} context
 * @param {object} workspace The workspace the agent is created in.
 * @param {AgentSetup} setup The wizard's choices.
 * @returns {Promise<{application: object, notApplied: string[],
 *   webSearchWarning: string|null}>} The created agent, the translated labels of
 *   what wasn't applied and why the chosen model can't search, if it can't.
 */
export async function applyAgentSetup(context, workspace, setup) {
  const { store, client, registry, t } = context
  const runAs = runAsOf(setup)
  const application = await store.dispatch('application/create', {
    type: AGENT_APPLICATION_TYPE,
    workspace,
    values: { name: setup.name },
  })
  const notApplied = []
  const agentService = AgentApplicationService(client)

  const configuration = await readConfiguration(agentService, application.id)

  const values = configurationValues(configuration, runAs, setup, notApplied, t)
  let saved = configuration
  if (Object.keys(values).length) {
    try {
      saved = (await agentService.updateConfiguration(application.id, values))
        .data
    } catch {
      saved = null
      notApplied.push(t('agent.setupConfiguration'))
    }
  }

  const webSearchWarning = webSearchWarningOf(setup, saved, t)
  if (setup.webSearch && !webSearchWarning) {
    if (!saved || !(await enableWebSearch(agentService, application.id))) {
      notApplied.push(t('agent.webSearch'))
    }
  }

  if (setup.start === SETUP_START.SCHEDULE) {
    try {
      await AgentTriggerService(client).create(application.id, {
        ...newTriggerValues(registry, t, SCHEDULE_TRIGGER_TYPE),
        service: scheduleValues(registry, setup.schedule),
      })
    } catch {
      notApplied.push(t('agent.setupStartSchedule'))
    }
  }

  for (const type of setup.actionTypes) {
    const name = serviceTypeOf(registry, type)?.name ?? type
    const available = configuration?.available_action_types ?? [type]
    if (!available.includes(type)) {
      notApplied.push(name)
      continue
    }
    try {
      await AgentActionService(client).create(application.id, { type })
    } catch {
      notApplied.push(name)
    }
  }

  return { application, notApplied, webSearchWarning }
}
