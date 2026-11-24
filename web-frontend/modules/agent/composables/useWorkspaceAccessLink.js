import { inject, provide } from 'vue'
import { useI18n } from 'vue-i18n'
import { WORKSPACE_ACCESS_SECTION } from '@baserow/modules/agent/constants'

/**
 * Lets a service form whose table choices come from the Agent's workspace
 * identity send people to set one up, when it has none to choose from.
 */
export function provideWorkspaceAccessLink() {
  const { t } = useI18n()
  const openSection = inject('openAgentConfigurationSection', null)
  provide(
    'formChoicesErrorAction',
    openSection && {
      get label() {
        return t('agent.setUpWorkspaceAccess')
      },
      onClick: () => openSection(WORKSPACE_ACCESS_SECTION),
    }
  )
}
