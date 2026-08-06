import { markRaw } from 'vue'
import { Registerable } from '@baserow/modules/core/registry'
import AgentGeneralSettingsFormComponent from '@baserow/modules/core/components/settings/agents/AgentGeneralSettingsForm'
import AgentMcpServerSettingsComponent from '@baserow/modules/core/components/settings/agents/AgentMcpServerSettings'

const AgentGeneralSettingsForm = markRaw(AgentGeneralSettingsFormComponent)
const AgentMcpServerSettings = markRaw(AgentMcpServerSettingsComponent)

export class AgentSettingsType extends Registerable {
  get name() {
    return null
  }

  get icon() {
    return null
  }

  get component() {
    return null
  }

  get componentPadding() {
    return true
  }

  get showInCreate() {
    return true
  }

  isActive(workspace) {
    return true
  }

  getInitialValues(agent, context) {
    return {}
  }

  getSubmitValues(values) {
    return {}
  }
}

export class GeneralAgentSettingsType extends AgentSettingsType {
  static getType() {
    return 'general'
  }

  get name() {
    return this.app.$i18n.t('agents.general')
  }

  get icon() {
    return 'iconoir-settings'
  }

  get component() {
    return AgentGeneralSettingsForm
  }

  getOrder() {
    return 1
  }

  getInitialValues(agent, { defaultRole }) {
    return {
      name: agent?.name || '',
      role_uid: agent?.role_uid || defaultRole,
    }
  }

  getSubmitValues({ name, role_uid: roleUid }) {
    return { name, role_uid: roleUid }
  }
}

export class McpServerAgentSettingsType extends AgentSettingsType {
  static getType() {
    return 'mcp_server'
  }

  get name() {
    return this.app.$i18n.t('mcpEndpointSettings.title')
  }

  get icon() {
    return 'iconoir-magic-wand'
  }

  get component() {
    return AgentMcpServerSettings
  }

  get showInCreate() {
    return false
  }

  getOrder() {
    return 20
  }
}
