import AgentApplicationService from '@baserow/modules/agent/services/agentApplication'
import AgentTriggerService from '@baserow/modules/agent/services/agentTriggers'
import AgentActionService from '@baserow/modules/agent/services/agentActions'
import { AGENT_APPLICATION_TYPE } from '@baserow/modules/agent/constants'
import { ActionToolPresentationType } from '@baserow/modules/agent/toolPresentationTypes'
import {
  newTriggerValues,
  serviceTypeOf,
} from '@baserow/modules/agent/utils/triggers'
import { UserSubjectType } from '@baserow/modules/core/subjectTypes'

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
})

/**
 * @typedef {object} AgentSetup
 * @property {string} name
 * @property {string} instructions
 * @property {'chat'|'schedule'} start
 * @property {{kind: 'new', roleUid: string}|{kind: 'existing', id: number, name: string}|{kind: 'none'}} actsAs
 * @property {'read'|'ask'|'change'} permissions
 * @property {boolean} webSearch
 * @property {string[]} actionTypes Service type names of the actions to add.
 */

export const SETUP_SUGGESTIONS = Object.freeze([
  {
    icon: 'iconoir-globe',
    labelKey: 'agent.setupSuggestionInvest',
    nameKey: 'agent.setupSuggestionInvestName',
    instructionsKey: 'agent.setupSuggestionInvestInstructions',
  },
  {
    icon: 'iconoir-mail',
    labelKey: 'agent.setupSuggestionOutreach',
    nameKey: 'agent.setupSuggestionOutreachName',
    instructionsKey: 'agent.setupSuggestionOutreachInstructions',
  },
  {
    icon: 'iconoir-table',
    labelKey: 'agent.setupSuggestionTriage',
    nameKey: 'agent.setupSuggestionTriageName',
    instructionsKey: 'agent.setupSuggestionTriageInstructions',
  },
])

const PREFERRED_IDENTITY_ROLE = 'BUILDER'
const FALLBACK_IDENTITY_ROLE = 'MEMBER'

/**
 * @param {object} workspace The workspace, with its roles loaded in `_.roles`.
 * @returns {object[]} The active roles an identity can be given.
 */
export function identityRoles(workspace) {
  return (workspace._?.roles || []).filter(
    (role) =>
      role.isVisible &&
      !role.isDeactivated &&
      (!Array.isArray(role.allowedSubjectTypes) ||
        role.allowedSubjectTypes.includes(UserSubjectType.getType()))
  )
}

/**
 * @param {object} workspace The workspace the identity joins.
 * @returns {string} The role a new identity gets.
 */
export function newIdentityRoleUid(workspace) {
  return identityRoles(workspace).some(
    (role) => role.uid === PREFERRED_IDENTITY_ROLE
  )
    ? PREFERRED_IDENTITY_ROLE
    : FALLBACK_IDENTITY_ROLE
}

/**
 * @param {string} name The agent's name.
 * @param {object} workspace The workspace the agent is created in.
 * @param {boolean} canCreateIdentity Whether the user may create identities.
 * @returns {AgentSetup} The choices the wizard starts with.
 */
export function emptyAgentSetup(name, workspace, canCreateIdentity) {
  return {
    name,
    instructions: '',
    start: SETUP_START.CHAT,
    actsAs: canCreateIdentity
      ? { kind: SETUP_ACTS_AS.NEW, roleUid: newIdentityRoleUid(workspace) }
      : { kind: SETUP_ACTS_AS.NONE },
    permissions: SETUP_PERMISSIONS.ASK,
    webSearch: false,
    actionTypes: [],
  }
}

/**
 * @param {Array<{name: string, changes_data: boolean}>} availableTools The
 *   tools the agent can be given.
 * @param {'read'|'ask'|'change'} permissions The chosen preset.
 * @returns {{allowed_tools: string[], ask_first_tools: string[]}} The tools
 *   allowed and those that ask first.
 */
export function toolsForPermissions(availableTools, permissions) {
  const allowed =
    permissions === SETUP_PERMISSIONS.READ
      ? availableTools.filter((tool) => !tool.changes_data)
      : availableTools
  return {
    allowed_tools: allowed.map((tool) => tool.name),
    ask_first_tools:
      permissions === SETUP_PERMISSIONS.ASK
        ? allowed.filter((tool) => tool.changes_data).map((tool) => tool.name)
        : [],
  }
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
 * @param {object} context The store, client, registry and translate function.
 * @param {object} workspace The workspace the identity is created in.
 * @param {AgentSetup} setup The wizard's choices.
 * @returns {Promise<{type: string, id: number}|null>} The identity to run as,
 *   or null when none was chosen or it could not be created.
 */
async function resolveIdentity({ store }, workspace, setup) {
  const { actsAs } = setup
  if (actsAs.kind === SETUP_ACTS_AS.EXISTING) {
    return { type: UserSubjectType.getType(), id: actsAs.id }
  }
  if (actsAs.kind !== SETUP_ACTS_AS.NEW) return null
  const identity = await store.dispatch('identity/create', {
    workspaceId: workspace.id,
    values: { name: setup.name, role_uid: actsAs.roleUid },
  })
  return { type: UserSubjectType.getType(), id: identity.id }
}

/**
 * @param {object|null} configuration The new agent's configuration, null when
 *   it couldn't be read.
 * @param {{type: string, id: number}|null} runAs The identity to run as.
 * @param {AgentSetup} setup The wizard's choices.
 * @param {string[]} notApplied Collects what can't be applied.
 * @param {Function} t The translate function.
 * @returns {object} The configuration values to save.
 */
function configurationValues(configuration, runAs, setup, notApplied, t) {
  const values = {}
  if (setup.instructions.trim()) values.instructions = setup.instructions
  if (runAs) {
    values.run_as = runAs
    if (configuration) {
      Object.assign(
        values,
        toolsForPermissions(configuration.available_tools, setup.permissions)
      )
    } else {
      notApplied.push(t('agent.setupPermissions'))
    }
  }
  if (setup.webSearch) {
    if (configuration?.web_search_available) values.web_search_enabled = true
    else notApplied.push(t('agent.webSearch'))
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

/**
 * Creates the agent, then applies each choice through the endpoints its
 * Configuration uses. Only the agent itself must be created; any other step
 * that fails is reported and the rest still runs.
 *
 * @param {{store: object, client: object, registry: object, t: Function}} context
 * @param {object} workspace The workspace the agent is created in.
 * @param {AgentSetup} setup The wizard's choices.
 * @returns {Promise<{application: object, notApplied: string[]}>} The created
 *   agent and the translated labels of what wasn't applied.
 */
export async function applyAgentSetup(context, workspace, setup) {
  const { store, client, registry, t } = context
  const application = await store.dispatch('application/create', {
    type: AGENT_APPLICATION_TYPE,
    workspace,
    values: { name: setup.name },
  })
  const notApplied = []
  const agentService = AgentApplicationService(client)

  const configuration = await readConfiguration(agentService, application.id)

  let runAs = null
  try {
    runAs = await resolveIdentity(context, workspace, setup)
  } catch {
    notApplied.push(t('agent.setupActsAs'))
  }

  const values = configurationValues(configuration, runAs, setup, notApplied, t)
  if (Object.keys(values).length) {
    try {
      const { data } = await agentService.updateConfiguration(
        application.id,
        values
      )
      if (values.web_search_enabled && data.web_search_blocked_by_tools) {
        notApplied.push(t('agent.webSearch'))
      }
    } catch {
      notApplied.push(t('agent.setupConfiguration'))
    }
  }

  if (setup.start === SETUP_START.SCHEDULE) {
    try {
      await AgentTriggerService(client).create(
        application.id,
        newTriggerValues(registry, t, SCHEDULE_TRIGGER_TYPE)
      )
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

  return { application, notApplied }
}
