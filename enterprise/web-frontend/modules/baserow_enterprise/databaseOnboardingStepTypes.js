import { DatabaseOnboardingStepType } from '@baserow/modules/database/databaseOnboardingStepTypes'
import AIDatabaseOnboardingForm from '@baserow_enterprise/components/onboarding/AIDatabaseOnboardingForm'
import { FF_AI_PROVIDERS } from '@baserow/modules/core/plugins/featureFlags'

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
    const legacyConfigured =
      !!this.app.$config.public.baserowEnterpriseAssistantLlmModel
    if (!this.app.$featureFlagIsEnabled(FF_AI_PROVIDERS)) {
      return legacyConfigured
    }
    return (
      this.app.$store.getters['settings/get'].kuma?.is_enabled ??
      legacyConfigured
    )
  }

  isValid(data, vuelidate, refs) {
    // Right after switching tabs the ref still points at the component of the
    // previously selected type, which has no `isValid`. The next render, once the
    // ref has caught up, gets the real answer.
    return refs.stepComponent?.isValid?.() === true
  }
}
