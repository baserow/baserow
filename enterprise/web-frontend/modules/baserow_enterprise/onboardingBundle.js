import { AIPromptOnboardingType } from '@baserow_enterprise/onboardingTypes'
import { AIDatabaseOnboardingStepType } from '@baserow_enterprise/databaseOnboardingStepTypes'

/** Initialize onboarding independently of application editors, once per Nuxt app. */
export default async function register(app) {
  const { $registry } = app
  const context = { app }
  $registry.register('onboarding', new AIPromptOnboardingType(context))
  $registry.register(
    'databaseOnboardingStep',
    new AIDatabaseOnboardingStepType(context)
  )
}
export { default as AIDatabaseOnboardingForm } from '@baserow_enterprise/components/onboarding/AIDatabaseOnboardingForm'
export { default as AIPromptStep } from '@baserow_enterprise/components/onboarding/AIPromptStep'
export { default as AssistantOnboardingMessage } from '@baserow_enterprise/components/assistant/AssistantOnboardingMessage.vue'
