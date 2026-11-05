import { TriggerDataProviderType } from '@baserow/modules/agent/dataProviderTypes'
import { agentToolPresentationTypes } from '@baserow/modules/agent/toolPresentationTypes'
import { AgentChatRunType } from '@baserow/modules/agent/chatRunTypes'
import {
  ConnectedAppsAgentConfigurationSectionType,
  InstructionsAgentConfigurationSectionType,
  WhenItRunsAgentConfigurationSectionType,
  SettingsAgentConfigurationSectionType,
  WorkspaceAccessAgentConfigurationSectionType,
} from '@baserow/modules/agent/configurationSectionTypes'

/** Register this feature only when its application is used. */
export default async function register(nuxtApp) {
  const { $registry } = nuxtApp
  const context = { app: nuxtApp }
  for (const ToolPresentation of agentToolPresentationTypes) {
    $registry.register('toolPresentation', new ToolPresentation(context))
  }
  nuxtApp.$registry.registerNamespace('agentConfigurationSection')
  $registry.registerNamespace('agentDataProvider')
  $registry.register('agentDataProvider', new TriggerDataProviderType(context))
  $registry.register('agentConfigurationSection', new WhenItRunsAgentConfigurationSectionType(context))
  $registry.register('agentConfigurationSection', new ConnectedAppsAgentConfigurationSectionType(context))
  nuxtApp.$registry.register(
    'agentConfigurationSection',
    new InstructionsAgentConfigurationSectionType(context)
  )
  nuxtApp.$registry.register(
    'agentConfigurationSection',
    new WorkspaceAccessAgentConfigurationSectionType(context)
  )
  nuxtApp.$registry.register(
    'agentConfigurationSection',
    new SettingsAgentConfigurationSectionType(context)
  )
  nuxtApp.$registry.register('chatRunType', new AgentChatRunType(context))
}
