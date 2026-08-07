import { DatabaseOnboardingStepType } from '@baserow/modules/database/databaseOnboardingStepTypes'
import AIDatabaseOnboardingForm from '@baserow_enterprise/components/onboarding/AIDatabaseOnboardingForm'

/**
 * AI-assisted database onboarding step type. Only visible when an LLM model is
 * configured in the enterprise settings. Asks a few questions about the user, after
 * which the AIPromptOnboardingType step asks for the actual prompt.
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
    // Right after switching tabs the ref still points at the component of the
    // previously selected type, which has no `isValid`. The next render, once the
    // ref has caught up, gets the real answer.
    return refs.stepComponent?.isValid?.() === true
  }
}
