import { MoreOnboardingType } from '@baserow/modules/core/onboardingTypes'

/** Initialize onboarding independently of application editors, once per Nuxt app. */
export default async function register(app) {
  const { $registry } = app
  const context = { app }
  $registry.register('onboarding', new MoreOnboardingType(context))
}
export { default as MoreStep } from '@baserow/modules/core/components/onboarding/MoreStep'
export { default as UserPreview } from '@baserow/modules/core/components/onboarding/UserPreview'
