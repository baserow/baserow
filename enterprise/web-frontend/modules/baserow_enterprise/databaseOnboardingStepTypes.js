import { DatabaseOnboardingStepType } from '@baserow/modules/database/databaseOnboardingStepTypes'
import AIDatabaseOnboardingForm from '@baserow_enterprise/components/onboarding/AIDatabaseOnboardingForm'

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
    return this.app.$config.public.baserowEnterpriseAssistantLLMModel !== null
  }

  isValid(data, vuelidate, refs) {
    return true
  }
}
