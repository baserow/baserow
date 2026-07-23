import { defineNuxtPlugin } from '#app'
import { DatabaseViewsAdminType } from '@baserow/modules/database/adminTypes'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import { DatabaseViewLastViewedItemType } from '@baserow/modules/database/lastViewedItemTypes'
import {
  DuplicateTableJobType,
  SyncDataSyncTableJobType,
  FileImportJobType,
  DuplicateFieldJobType,
  AirtableJobType,
  ButtonFieldDispatchJobType,
} from '@baserow/modules/database/jobTypes'
import { APITokenSettingsType } from '@baserow/modules/database/settingsTypes'
import { DatabasePlugin } from '@baserow/modules/database/plugins'
import {
  CollaboratorAddedToRowNotificationType,
  FormSubmittedNotificationType,
  UserMentionInRichTextFieldNotificationType,
  WebhookDeactivatedNotificationType,
  WebhookPayloadTooLargedNotificationType,
} from '@baserow/modules/database/notificationTypes'
import { FieldsDataProviderType } from '@baserow/modules/database/dataProviderTypes'

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

import {
  DatabaseScratchTrackCampaignFieldsOnboardingType,
  DatabaseScratchTrackCustomFieldsOnboardingType,
  DatabaseScratchTrackProjectFieldsOnboardingType,
  DatabaseScratchTrackTaskFieldsOnboardingType,
  DatabaseScratchTrackTeamFieldsOnboardingType,
} from '@baserow/modules/database/databaseScratchTrackFieldsStepType'
import {
  DatabaseSearchType,
  DatabaseTableSearchType,
  DatabaseFieldSearchType,
  DatabaseRowSearchType,
} from '@baserow/modules/database/searchTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'

export default defineNuxtPlugin({
  name: 'database',
  dependsOn: ['core'],
  setup(nuxtApp) {
    const { $registry } = nuxtApp

    const context = { app: nuxtApp }

    $registry.registerNamespace('viewDecorator')
    $registry.registerNamespace('decoratorValueProvider')
    $registry.registerNamespace('twoWaySyncStrategy')
    $registry.registerNamespace('viewFilter')
    $registry.registerNamespace('viewOwnershipType')
    $registry.registerNamespace('fieldConstraint')
    $registry.registerNamespace('importer')
    $registry.registerNamespace('exporter')
    $registry.registerNamespace('dataSync')
    $registry.registerNamespace('webhookEvent')
    $registry.registerNamespace('formula_function')
    $registry.registerNamespace('formula_type')
    $registry.registerNamespace('preview')
    $registry.registerNamespace('viewAggregation')
    $registry.registerNamespace('formViewMode')
    $registry.registerNamespace('databaseDataProvider')
    $registry.registerNamespace('databaseWorkflowActionType')
    $registry.registerNamespace('rowModalSidebar')
    $registry.registerNamespace('onboardingTrackFields')
    $registry.registerNamespace('configureDataSync')
    $registry.registerNamespace('databaseOnboardingStep')
    $registry.registerNamespace('copyViewConfigurationOption')

    $registry.register('plugin', new DatabasePlugin(context))
    $registry.register('application', new DatabaseApplicationType(context))
    $registry.register(
      'lastViewedItem',
      new DatabaseViewLastViewedItemType(context)
    )
    $registry.register('admin', new DatabaseViewsAdminType(context))

    $registry.register('job', new DuplicateTableJobType(context))
    $registry.register('job', new SyncDataSyncTableJobType(context))
    $registry.register('job', new FileImportJobType(context))
    $registry.register('job', new DuplicateFieldJobType(context))
    $registry.register('job', new AirtableJobType(context))
    $registry.register('job', new ButtonFieldDispatchJobType(context))

    $registry.register('settings', new APITokenSettingsType(context))

    $registry.register(
      'databaseDataProvider',
      new FieldsDataProviderType(context)
    )

    // notifications
    $registry.register(
      'notification',
      new CollaboratorAddedToRowNotificationType(context)
    )
    $registry.register(
      'notification',
      new FormSubmittedNotificationType(context)
    )
    $registry.register(
      'notification',
      new UserMentionInRichTextFieldNotificationType(context)
    )
    $registry.register(
      'notification',
      new WebhookDeactivatedNotificationType(context)
    )
    $registry.register(
      'notification',
      new WebhookPayloadTooLargedNotificationType(context)
    )

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

    $registry.registerNamespace('fieldContextItem')

    searchTypeRegistry.register(new DatabaseSearchType(context))
    searchTypeRegistry.register(new DatabaseTableSearchType(context))
    searchTypeRegistry.register(new DatabaseFieldSearchType(context))
    searchTypeRegistry.register(new DatabaseRowSearchType(context))

    // Field, view, filter, formula types etc. load on database routes.
    $registry.registerDomainLoader('database', async () => {
      const { default: register } =
        await import('@baserow/modules/database/lazyRegistrations')
      register(nuxtApp)
    })
  },
})
