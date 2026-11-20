import { markRaw } from 'vue'
import { Registerable } from '@baserow/modules/core/registry'
import AgentInstructionsSection from '@baserow/modules/agent/components/configuration/AgentInstructionsSection'
import AgentSettingsSection from '@baserow/modules/agent/components/configuration/AgentSettingsSection'
import AgentWorkspaceAccessSection from '@baserow/modules/agent/components/configuration/AgentWorkspaceAccessSection'
import AgentConnectedAppsSection from '@baserow/modules/agent/components/configuration/AgentConnectedAppsSection'
import AgentWhenItRunsSection from '@baserow/modules/agent/components/configuration/AgentWhenItRunsSection'
import AgentActionsSection from '@baserow/modules/agent/components/configuration/AgentActionsSection'
import { getRunAsStatus } from '@baserow/modules/agent/utils/runAs'
import {
  CONFIGURATION_ERROR,
  RUN_AS_STATUS,
} from '@baserow/modules/agent/constants'

const ActionsSection = markRaw(AgentActionsSection)
const InstructionsSection = markRaw(AgentInstructionsSection)
const SettingsSection = markRaw(AgentSettingsSection)
const WorkspaceAccessSection = markRaw(AgentWorkspaceAccessSection)
const ConnectedAppsSection = markRaw(AgentConnectedAppsSection)
const WhenItRunsSection = markRaw(AgentWhenItRunsSection)

/**
 * A section in the Agent configuration sidebar. Plugins can register additional
 * sections in `agentConfigurationSection`. Its component receives the current
 * configuration, name, validation errors, availability and editing permissions,
 * and emits `change`, `flush`, `update:name` and `rename` to save changes.
 *
 * Components can expose `focusField(field)` to focus a field selected from the
 * configuration warning. The fields map identifies which section owns a field
 * and provides its label and optional unavailable error message. Section errors
 * also receive the configuration for optional settings that don't block replies,
 * and the sidebar's context: the Agent, its workspace and its triggers.
 */
export class AgentConfigurationSectionType extends Registerable {
  get name() {
    return null
  }

  get description() {
    return null
  }

  get icon() {
    return null
  }

  get component() {
    return null
  }

  get fields() {
    return {}
  }

  /**
   * Runs once in the sidebar's setup, so a section can load and watch what its
   * error message needs while it is closed.
   *
   * @param {object} context The reactive `agent`, `workspace` and `triggers`,
   *   the latter as `useAgentTriggers` returns them.
   */
  setup(context) {}

  getFieldErrorMessage(field, error) {
    if (!error) return ''
    return this.$t(
      error === CONFIGURATION_ERROR.UNAVAILABLE &&
        this.fields[field]?.unavailableMessage
        ? this.fields[field].unavailableMessage
        : 'error.requiredField'
    )
  }

  /**
   * @param {object} errors The configuration's errors by field.
   * @param {object} configuration The Agent's configuration.
   * @param {object} context What `setup` received.
   * @returns {string} Why the section needs attention, or an empty string.
   */
  getErrorMessage(errors, configuration, context) {
    return Object.entries(this.fields)
      .filter(([field]) => errors[field])
      .map(([field, { label }]) =>
        this.$t('agent.fieldError', {
          field: this.$t(label),
          error: this.getFieldErrorMessage(field, errors[field]),
        })
      )
      .join(' ')
  }
}

export class InstructionsAgentConfigurationSectionType extends AgentConfigurationSectionType {
  static getType() {
    return 'instructions'
  }

  get name() {
    return this.$t('agent.instructions')
  }

  get description() {
    return this.$t('agent.instructionsDescription')
  }

  get icon() {
    return 'iconoir-page-edit'
  }

  get component() {
    return InstructionsSection
  }

  get fields() {
    return { instructions: { label: 'agent.instructions' } }
  }

  getOrder() {
    return 10
  }
}

export class WhenItRunsAgentConfigurationSectionType extends AgentConfigurationSectionType {
  static getType() {
    return 'when_it_runs'
  }

  get name() {
    return this.$t('agent.whenItRuns')
  }

  get description() {
    return this.$t('agent.whenItRunsDescription')
  }

  get icon() {
    return 'iconoir-play'
  }

  get component() {
    return WhenItRunsSection
  }

  getOrder() {
    return 20
  }
}

export class WorkspaceAccessAgentConfigurationSectionType extends AgentConfigurationSectionType {
  static getType() {
    return 'workspace_access'
  }

  get name() {
    return this.$t('agent.workspaceAccess')
  }

  get description() {
    return this.$t('agent.workspaceAccessDescription')
  }

  get icon() {
    return 'baserow-icon-agent'
  }

  get component() {
    return WorkspaceAccessSection
  }

  getErrorMessage(errors, configuration) {
    const runAs = configuration?.run_as
    const status = getRunAsStatus(runAs)
    if (status === RUN_AS_STATUS.TRASHED)
      return this.$t('agent.runAsTrashed', { name: runAs.name })
    return status === RUN_AS_STATUS.MISSING ? this.$t('agent.runAsMissing') : ''
  }

  getOrder() {
    return 30
  }
}

export class ConnectedAppsAgentConfigurationSectionType extends AgentConfigurationSectionType {
  static getType() {
    return 'connected_apps'
  }

  get name() {
    return this.$t('agent.connectedApps')
  }

  get description() {
    return this.$t('agent.connectedAppsDescription')
  }

  get icon() {
    return 'iconoir-network-right'
  }

  get component() {
    return ConnectedAppsSection
  }

  getOrder() {
    return 40
  }
}

export class SettingsAgentConfigurationSectionType extends AgentConfigurationSectionType {
  static getType() {
    return 'settings'
  }

  get name() {
    return this.$t('agent.agentSettings')
  }

  get description() {
    return this.$t('agent.agentSettingsDescription')
  }

  get icon() {
    return 'iconoir-settings'
  }

  get component() {
    return SettingsSection
  }

  get fields() {
    return {
      provider_type: {
        label: 'agent.provider',
        unavailableMessage: 'agent.providerUnavailable',
      },
      model_identifier: {
        label: 'agent.model',
        unavailableMessage: 'agent.modelUnavailable',
      },
    }
  }

  getOrder() {
    return 90
  }
}

export class ActionsAgentConfigurationSectionType extends AgentConfigurationSectionType {
  static getType() {
    return 'actions'
  }

  get name() {
    return this.$t('agent.actions')
  }

  get description() {
    return this.$t('agent.actionsDescription')
  }

  get icon() {
    return 'iconoir-flash'
  }

  get component() {
    return ActionsSection
  }

  getOrder() {
    return 35
  }
}
