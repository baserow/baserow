import {
  DuplicatePageJobType,
  PublishBuilderJobType,
} from '@baserow/modules/builder/jobTypes'
import { BuilderPageLastViewedItemType } from '@baserow/modules/builder/lastViewedItemTypes'
import { BuilderSearchType } from '@baserow/modules/builder/searchTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'

/** Workspace metadata does not require the Builder editor. */
export default async function register(nuxtApp) {
  const { $registry } = nuxtApp
  const context = { app: nuxtApp }
  $registry.register(
    'lastViewedItem',
    new BuilderPageLastViewedItemType(context)
  )
  $registry.register('job', new DuplicatePageJobType(context))
  $registry.register('job', new PublishBuilderJobType(context))
  searchTypeRegistry.register(new BuilderSearchType(context))
}
