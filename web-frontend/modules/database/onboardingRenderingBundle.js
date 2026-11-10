import { loadApplicationBundle } from '@baserow/modules/core/utils/applicationBundles'
import {
  DatabaseScratchTrackCampaignFieldsOnboardingType,
  DatabaseScratchTrackCustomFieldsOnboardingType,
  DatabaseScratchTrackProjectFieldsOnboardingType,
  DatabaseScratchTrackTaskFieldsOnboardingType,
  DatabaseScratchTrackTeamFieldsOnboardingType,
} from '@baserow/modules/database/databaseScratchTrackFieldsStepType'

/** Initialize onboarding independently of application editors, once per Nuxt app. */
export default async function register(app) {
  const { $registry } = app
  const context = { app }
  await loadApplicationBundle(app, 'database')
  $registry.registerNamespace('onboardingTrackFields')
  $registry.register(
    'onboardingTrackFields',
    new DatabaseScratchTrackProjectFieldsOnboardingType(context)
  )
  $registry.register(
    'onboardingTrackFields',
    new DatabaseScratchTrackTeamFieldsOnboardingType(context)
  )
  $registry.register(
    'onboardingTrackFields',
    new DatabaseScratchTrackTaskFieldsOnboardingType(context)
  )
  $registry.register(
    'onboardingTrackFields',
    new DatabaseScratchTrackCampaignFieldsOnboardingType(context)
  )
  $registry.register(
    'onboardingTrackFields',
    new DatabaseScratchTrackCustomFieldsOnboardingType(context)
  )
}
export { default as DatabaseImportStep } from '@baserow/modules/database/components/onboarding/DatabaseImportStep'
export { default as DatabaseScratchTrackFieldsStep } from '@baserow/modules/database/components/onboarding/DatabaseScratchTrackFieldsStep'
export { default as DatabaseTablePreview } from '@baserow/modules/database/components/onboarding/DatabaseTablePreview'
