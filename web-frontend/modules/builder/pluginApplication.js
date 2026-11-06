import {
  GeneralBuilderSettingsType,
  BreakpointsBuilderSettingsType,
  DomainsBuilderSettingsType,
  IntegrationsBuilderSettingsType,
  ThemeBuilderSettingsType,
  UserSourcesBuilderSettingsType,
} from '@baserow/modules/builder/builderSettingTypes'

import {
  DataSourcesPageHeaderItemType,
  ElementsPageHeaderItemType,
  SettingsPageHeaderItemType,
} from '@baserow/modules/builder/pageHeaderItemTypes'
import {
  EventsPageSidePanelType,
  GeneralPageSidePanelType,
  StylePageSidePanelType,
  VisibilityPageSidePanelType,
} from '@baserow/modules/builder/pageSidePanelTypes'
import {
  CustomDomainType,
  SubDomainType,
} from '@baserow/modules/builder/domainTypes'
import {
  PagePageSettingsType,
  PageVisibilitySettingsType,
} from '@baserow/modules/builder/pageSettingsTypes'
import {
  PreviewPageActionType,
  PublishPageActionType,
} from '@baserow/modules/builder/pageActionTypes'
import { BuilderGuidedTourType } from '@baserow/modules/builder/guidedTourTypes'

/** Register this entry before rendering or hydrating its routes. */
export default async function register(nuxtApp) {
  const { $store, $registry } = nuxtApp
  const context = { app: nuxtApp }

  $registry.register('builderSettings', new GeneralBuilderSettingsType(context))
  $registry.register(
    'builderSettings',
    new BreakpointsBuilderSettingsType(context)
  )
  $registry.register(
    'builderSettings',
    new IntegrationsBuilderSettingsType(context)
  )
  $registry.register('builderSettings', new ThemeBuilderSettingsType(context))
  $registry.register('builderSettings', new DomainsBuilderSettingsType(context))
  $registry.register(
    'builderSettings',
    new UserSourcesBuilderSettingsType(context)
  )
  $registry.register('pageHeaderItem', new ElementsPageHeaderItemType(context))
  $registry.register(
    'pageHeaderItem',
    new DataSourcesPageHeaderItemType(context)
  )
  $registry.register('pageHeaderItem', new SettingsPageHeaderItemType(context))
  $registry.register('pageSidePanel', new GeneralPageSidePanelType(context))
  $registry.register('pageSidePanel', new StylePageSidePanelType(context))
  $registry.register('pageSidePanel', new VisibilityPageSidePanelType(context))
  $registry.register('pageSidePanel', new EventsPageSidePanelType(context))
  $registry.register('domain', new CustomDomainType(context))
  $registry.register('domain', new SubDomainType(context))
  $registry.register('pageSettings', new PagePageSettingsType(context))
  $registry.register('pageSettings', new PageVisibilitySettingsType(context))
  $registry.register('pageAction', new PublishPageActionType(context))
  $registry.register('pageAction', new PreviewPageActionType(context))
  $registry.register('guidedTour', new BuilderGuidedTourType(context))
}
