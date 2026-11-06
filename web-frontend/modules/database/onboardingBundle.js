import {
  DatabaseOnboardingType,
  DatabaseScratchTrackOnboardingType,
  DatabaseImportOnboardingType,
  DatabaseScratchTrackFieldsOnboardingType,
} from '@baserow/modules/database/onboardingTypes'
import {
  ScratchDatabaseOnboardingStepType,
  ImportDatabaseOnboardingStepType,
  AirtableDatabaseOnboardingStepType,
  TemplateDatabaseOnboardingStepType,
} from '@baserow/modules/database/databaseOnboardingStepTypes'

/** Initialize onboarding independently of application editors, once per Nuxt app. */
export default async function register(app) {
  const { $registry } = app
  const context = { app }
  $registry.register('onboarding', new DatabaseOnboardingType(context))
  $registry.register(
    'onboarding',
    new DatabaseScratchTrackOnboardingType(context)
  )
  $registry.register(
    'onboarding',
    new DatabaseScratchTrackFieldsOnboardingType(context)
  )
  $registry.register('onboarding', new DatabaseImportOnboardingType(context))
  $registry.registerNamespace('databaseOnboardingStep')
  $registry.register(
    'databaseOnboardingStep',
    new ScratchDatabaseOnboardingStepType(context)
  )
  $registry.register(
    'databaseOnboardingStep',
    new ImportDatabaseOnboardingStepType(context)
  )
  $registry.register(
    'databaseOnboardingStep',
    new AirtableDatabaseOnboardingStepType(context)
  )
  $registry.register(
    'databaseOnboardingStep',
    new TemplateDatabaseOnboardingStepType(context)
  )
}
export { default as DatabaseStep } from '@baserow/modules/database/components/onboarding/DatabaseStep'
export { default as DatabaseScratchTrackStep } from '@baserow/modules/database/components/onboarding/DatabaseScratchTrackStep'
export { default as DatabaseAppLayoutPreview } from '@baserow/modules/database/components/onboarding/DatabaseAppLayoutPreview'
export { default as AirtableImportForm } from '@baserow/modules/database/components/airtable/AirtableImportForm'
export { default as TemplateImportForm } from '@baserow/modules/database/components/onboarding/TemplateImportForm'
export { default as TemplateOnboardingCancelModal } from '@baserow/modules/database/components/onboarding/TemplateOnboardingCancelModal'
export { default as DatabaseTemplatePreview } from '@baserow/modules/database/components/onboarding/DatabaseTemplatePreview'
