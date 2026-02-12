import { DatabaseOnboardingStepType } from '@baserow/modules/database/databaseOnboardingStepTypes'
import AIDatabaseOnboardingForm from '@baserow_enterprise/components/onboarding/AIDatabaseOnboardingForm'
import { nextTick } from 'vue'
import { pageFinished } from '@baserow/modules/core/utils/routing.js'
import { DatabaseOnboardingType } from '@baserow/modules/database/onboardingTypes.js'
import { waitFor } from '@baserow/modules/core/utils/queue.js'
import AssistantOnboardingMessage from '@baserow_enterprise/components/assistant/AssistantOnboardingMessage.vue'

/**
 * AI-assisted database onboarding step type. Only visible when an LLM model is
 * configured in the enterprise settings.
 */
export class AIDatabaseOnboardingStepType extends DatabaseOnboardingStepType {
  static getType() {
    return 'ai'
  }

  getOrder() {
    return 10
  }

  getLabel() {
    return this.app.$i18n.t('databaseStep.ai')
  }

  getComponent() {
    return AIDatabaseOnboardingForm
  }

  hasNameInput() {
    return false
  }

  isVisible() {
    // Only show if the AI-assistant is configured because it will use the
    // AI-assistant to create the database.
    return !!this.app.$config.public.baserowEnterpriseAssistantLlmModel
  }

  isValid(data, vuelidate, refs) {
    const component = refs.stepComponent
    return (
      !!component &&
      !!component.v$ &&
      !component.v$.$invalid &&
      component.v$.$dirty
    )
  }

  async completeAfterWorkspace(workspace, stepData, callback) {
    await this.app.$store.dispatch('workspace/select', workspace)
    const message = this.app.$i18n.t('aiDatabaseOnboardingStepType.prompt', {
      prompt: stepData.prompt,
    })
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
    const response = responses[DatabaseOnboardingType.getType()]
    nextTick(async () => {
      await pageFinished()
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
