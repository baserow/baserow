import { DatabaseOnboardingStepType } from '@baserow/modules/database/databaseOnboardingStepTypes'
import AIDatabaseOnboardingForm from '@baserow_enterprise/components/onboarding/AIDatabaseOnboardingForm'
import { nextTick } from 'vue'
import { pageFinished } from '@baserow/modules/core/utils/routing.js'
import { DatabaseOnboardingType } from '@baserow/modules/database/onboardingTypes.js'
import { waitFor } from '@baserow/modules/core/utils/queue.js'

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
    return !!this.app.$config.public.baserowEnterpriseAssistantLLMModel
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

  getCompletedRoute(data, responses) {
    const workspace = responses[DatabaseOnboardingType.getType()].workspace
    const prompt = data[DatabaseOnboardingType.getType()].prompt
    nextTick(async () => {
      await pageFinished()
      await nextTick()
      await this.app.$bus.$emit('toggle-right-sidebar', true)
      await nextTick()
      await waitFor(() => !this.app.$store.getters['assistant/isLoadingChats'])
      await nextTick()
      const message = this.app.$i18n.t('aiDatabaseOnboardingStepType.prompt', {
        prompt,
      })
      await this.app.$store.dispatch('assistant/sendMessage', {
        message,
        workspace: workspace,
      })
    })
    // By default, this will redirect to the dashboard. We want to redirect there
    // because the AI-assistant must first create the database.
    return super.getCompletedRoute(data, responses)
  }
}
