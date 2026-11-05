import registerRealtimeMetadata from '@baserow/modules/database/realtimeMetadata'
import {
  DATABASE_VIEW_METADATA,
  registerViewMetadata,
} from '@baserow/modules/database/viewMetadata'

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
import {
  DatabaseSearchType,
  DatabaseTableSearchType,
  DatabaseFieldSearchType,
  DatabaseRowSearchType,
} from '@baserow/modules/database/searchTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'

/** Register lightweight application metadata for workspace lists and navigation. */
export default async function register(nuxtApp) {
  const { $registry } = nuxtApp
  const context = { app: nuxtApp }
  if (nuxtApp.$realtime) registerRealtimeMetadata(nuxtApp)
  registerViewMetadata(nuxtApp, DATABASE_VIEW_METADATA)
  $registry.register('application', new DatabaseApplicationType(context))
  $registry.register(
    'lastViewedItem',
    new DatabaseViewLastViewedItemType(context)
  )
  $registry.register('job', new DuplicateTableJobType(context))
  $registry.register('job', new SyncDataSyncTableJobType(context))
  $registry.register('job', new FileImportJobType(context))
  $registry.register('job', new DuplicateFieldJobType(context))
  $registry.register('job', new AirtableJobType(context))
  $registry.register('job', new ButtonFieldDispatchJobType(context))
  searchTypeRegistry.register(new DatabaseSearchType(context))
  searchTypeRegistry.register(new DatabaseTableSearchType(context))
  searchTypeRegistry.register(new DatabaseFieldSearchType(context))
  searchTypeRegistry.register(new DatabaseRowSearchType(context))
}
