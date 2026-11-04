import { AgentApplicationType } from '@baserow/modules/agent/applicationTypes'
import { AgentChatRunType } from '@baserow/modules/agent/chatRunTypes'
import { AgentLastViewedItemType } from '@baserow/modules/agent/lastViewedItemTypes'
import { AgentApplicationSearchType } from '@baserow/modules/agent/searchTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'
import {
  InstructionsAgentConfigurationSectionType,
  SettingsAgentConfigurationSectionType,
  WorkspaceAccessAgentConfigurationSectionType,
} from '@baserow/modules/agent/configurationSectionTypes'

/** Register this entry before rendering or hydrating its routes. */
export default async function register(nuxtApp) {
  const context = { app: nuxtApp }
  nuxtApp.$registry.registerNamespace('agentConfigurationSection')
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
  nuxtApp.$registry.register('application', new AgentApplicationType(context))
  nuxtApp.$registry.register('chatRunType', new AgentChatRunType(context))
  nuxtApp.$registry.register(
    'lastViewedItem',
    new AgentLastViewedItemType(context)
  )
  searchTypeRegistry.register(new AgentApplicationSearchType(context))
}
