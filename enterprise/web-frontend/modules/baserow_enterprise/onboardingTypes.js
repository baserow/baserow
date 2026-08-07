import { nextTick } from 'vue'
import { OnboardingType } from '@baserow/modules/core/onboardingTypes'
import { DatabaseOnboardingType } from '@baserow/modules/database/onboardingTypes'
import DatabaseAppLayoutPreview from '@baserow/modules/database/components/onboarding/DatabaseAppLayoutPreview'
import { pageFinished } from '@baserow/modules/core/utils/routing.js'
import { waitFor } from '@baserow/modules/core/utils/queue.js'
import AIPromptStep from '@baserow_enterprise/components/onboarding/AIPromptStep'
import AssistantOnboardingMessage from '@baserow_enterprise/components/assistant/AssistantOnboardingMessage.vue'
import { AIDatabaseOnboardingStepType } from '@baserow_enterprise/databaseOnboardingStepTypes'

export class AIPromptOnboardingType extends OnboardingType {
  static getType() {
    return 'ai_prompt'
  }

  getOrder() {
    return 5050
  }

  getFormComponent() {
    return AIPromptStep
  }

  getPreviewComponent() {
    return DatabaseAppLayoutPreview
  }

  condition(data) {
    const database = data[DatabaseOnboardingType.getType()]
    return database?.type === AIDatabaseOnboardingStepType.getType()
  }

  async complete(data, responses, callback) {
    const { $i18n: i18n } = this.app
    const workspace = responses[DatabaseOnboardingType.getType()].workspace
    const database = data[DatabaseOnboardingType.getType()]

    await this.app.$store.dispatch('workspace/select', workspace)

    const stepData = data[this.getType()]
    const message = [
      i18n.t('aiPromptOnboardingType.prompt', { prompt: stepData.prompt }),
      i18n.t('aiPromptOnboardingType.context', {
        industry: database.industry,
        team: database.team,
      }),
      i18n.t('aiPromptOnboardingType.language', {
        language: stepData.language,
      }),
    ].join(' ')

    callback(null, AssistantOnboardingMessage)
    await this.app.$store.dispatch('assistant/sendMessage', {
      message,
      workspace,
    })
    const chat = this.app.$store.getters['assistant/currentChat']
    await waitFor(() => {
      const currentChat = this.app.$store.getters['assistant/currentChat']
      return !currentChat?.running
    }, 50)
    const tableLocation = this.app.$store.getters[
      'assistant/uiLocationHistory'
    ].filter((location) => location.type === 'database-table')[0]
    if (!tableLocation) {
      throw new Error('The assistant did not create a table.')
    }
    return { tableLocation, chat }
  }

  getCompletedRoute(data, responses) {
    const response = responses[this.getType()]
    nextTick(async () => {
      await pageFinished(this.app)
      await nextTick()
      await this.app.$bus.$emit('toggle-right-sidebar', true)
      await this.app.$store.dispatch('assistant/selectChat', response.chat)
    })
    return {
      name: 'database-table',
      params: {
        databaseId: response.tableLocation.database_id,
        tableId: response.tableLocation.table_id,
      },
    }
  }
}
