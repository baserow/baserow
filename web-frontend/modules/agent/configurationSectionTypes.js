import { markRaw } from 'vue'
import { Registerable } from '@baserow/modules/core/registry'
import { lazyComponent } from '@baserow/modules/core/utils/lazyComponent'

const AgentInstructionsSection = lazyComponent(
  () =>
    import('@baserow/modules/agent/components/configuration/AgentInstructionsSection')
)
const AgentSettingsSection = lazyComponent(
  () =>
    import('@baserow/modules/agent/components/configuration/AgentSettingsSection')
)

const InstructionsSection = markRaw(AgentInstructionsSection)
const SettingsSection = markRaw(AgentSettingsSection)

/**
 * A section in the Agent configuration sidebar. Plugins can register additional
 * sections in `agentConfigurationSection`. Its component receives the current
 * configuration, name, validation errors, availability and editing permissions,
 * and emits `change`, `flush`, `update:name` and `rename` to save changes.
 *
 * Components can expose `focusField(field)` to focus a field selected from the
 * configuration warning. The fields map identifies which section owns a field
 * and provides its label and optional unavailable error message.
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

  getFieldErrorMessage(field, error) {
    if (!error) return ''
    return this.$t(
      error === 'unavailable' && this.fields[field]?.unavailableMessage
        ? this.fields[field].unavailableMessage
        : 'error.requiredField'
    )
  }

  getErrorMessage(errors) {
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
    return 20
  }
}
