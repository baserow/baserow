import en from '@baserow/modules/builder/locales/en.json'
import fr from '@baserow/modules/builder/locales/fr.json'
import nl from '@baserow/modules/builder/locales/nl.json'
import de from '@baserow/modules/builder/locales/de.json'
import es from '@baserow/modules/builder/locales/es.json'
import it from '@baserow/modules/builder/locales/it.json'
import pl from '@baserow/modules/builder/locales/pl.json'
import ko from '@baserow/modules/builder/locales/ko.json'
import {
  GeneralBuilderSettingsType,
  DomainsBuilderSettingsType,
  IntegrationsBuilderSettingsType,
  ThemeBuilderSettingsType,
  UserSourcesBuilderSettingsType,
} from '@baserow/modules/builder/builderSettingTypes'

import pageStore from '@baserow/modules/builder/store/page'
import elementStore from '@baserow/modules/builder/store/element'
import domainStore from '@baserow/modules/builder/store/domain'
import publicBuilderStore from '@baserow/modules/builder/store/publicBuilder'
import dataSourceStore from '@baserow/modules/builder/store/dataSource'
import pageParameterStore from '@baserow/modules/builder/store/pageParameter'
import dataSourceContentStore from '@baserow/modules/builder/store/dataSourceContent'
import elementContentStore from '@baserow/modules/builder/store/elementContent'
import themeStore from '@baserow/modules/builder/store/theme'
import builderWorkflowActionStore from '@baserow/modules/builder/store/builderWorkflowAction'
import formDataStore from '@baserow/modules/builder/store/formData'
import builderToast from '@baserow/modules/builder/store/builderToast'
import { registerRealtimeEvents } from '@baserow/modules/builder/realtime'
import {
  HeadingElementType,
  ImageElementType,
  TextElementType,
  LinkElementType,
  InputTextElementType,
  ColumnElementType,
  ButtonElementType,
  TableElementType,
  FormContainerElementType,
  ChoiceElementType,
  CheckboxElementType,
  DateTimePickerElementType,
  IFrameElementType,
  RepeatElementType,
  RecordSelectorElementType,
  HeaderElementType,
  FooterElementType,
  RatingElementType,
  RatingInputElementType,
  MenuElementType,
  SimpleContainerElementType,
} from '@baserow/modules/builder/elementTypes'
import {
  DesktopDeviceType,
  SmartphoneDeviceType,
  TabletDeviceType,
} from '@baserow/modules/builder/deviceTypes'
import {
  DuplicatePageJobType,
  PublishBuilderJobType,
} from '@baserow/modules/builder/jobTypes'
import { BuilderApplicationType } from '@baserow/modules/builder/applicationTypes'
import { PublicSiteErrorPageType } from '@baserow/modules/builder/errorPageTypes'
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
  TextPathParamType,
  NumericPathParamType,
} from '@baserow/modules/builder/pathParamTypes'

import {
  PreviewPageActionType,
  PublishPageActionType,
} from '@baserow/modules/builder/pageActionTypes'

import {
  PageParameterDataProviderType,
  DataSourceDataProviderType,
  CurrentRecordDataProviderType,
  FormDataProviderType,
  PreviousActionDataProviderType,
  UserDataProviderType,
  DataSourceContextDataProviderType,
} from '@baserow/modules/builder/dataProviderTypes'

import {
  ColorThemeConfigBlockType,
  TypographyThemeConfigBlockType,
  ButtonThemeConfigBlockType,
  LinkThemeConfigBlockType,
  ImageThemeConfigBlockType,
  PageThemeConfigBlockType,
  InputThemeConfigBlockType,
  TableThemeConfigBlockType,
} from '@baserow/modules/builder/themeConfigBlockTypes'
import {
  CreateRowWorkflowActionType,
  NotificationWorkflowActionType,
  OpenPageWorkflowActionType,
  UpdateRowWorkflowActionType,
  LogoutWorkflowActionType,
  RefreshDataSourceWorkflowActionType,
  DeleteRowWorkflowActionType,
  CoreHTTPRequestWorkflowActionType,
  CoreSMTPEmailWorkflowActionType,
  AIAgentWorkflowActionType,
  SlackWriteMessageWorkflowActionType,
} from '@baserow/modules/builder/workflowActionTypes'

import {
  BooleanCollectionFieldType,
  TextCollectionFieldType,
  LinkCollectionFieldType,
  ButtonCollectionFieldType,
  TagsCollectionFieldType,
  ImageCollectionFieldType,
  RatingCollectionFieldType,
} from '@baserow/modules/builder/collectionFieldTypes'

import {
  InterFontFamilyType,
  ArialFontFamilyType,
  VerdanaFontFamilyType,
  TahomaFontFamilyType,
  TrebuchetMSFontFamilyType,
  TimesNewRomanFontFamilyType,
  GeorgiaFontFamilyType,
  GaramondFontFamilyType,
  CourierNewFontFamilyType,
  BrushScriptMTFontFamilyType,
} from '@baserow/modules/builder/fontFamilyTypes'
import {
  TextQueryParamType,
  NumericQueryParamType,
} from '@baserow/modules/builder/queryParamTypes'
import { BuilderGuidedTourType } from '@baserow/modules/builder/guidedTourTypes'
import { BuilderSearchType } from '@baserow/modules/builder/searchTypes'
import { searchTypeRegistry } from '@baserow/modules/core/search/types/registry'

export default (context) => {
  const { store, app, isDev } = context

  // Allow locale file hot reloading in dev
  if (isDev && app.i18n) {
    const { i18n } = app
    i18n.mergeLocaleMessage('en', en)
    i18n.mergeLocaleMessage('fr', fr)
    i18n.mergeLocaleMessage('nl', nl)
    i18n.mergeLocaleMessage('de', de)
    i18n.mergeLocaleMessage('es', es)
    i18n.mergeLocaleMessage('it', it)
    i18n.mergeLocaleMessage('pl', pl)
    i18n.mergeLocaleMessage('ko', ko)
  }

  registerRealtimeEvents(app.$realtime)

  app.$clientErrorMap.setError(
    'ERROR_PAGE_NAME_NOT_UNIQUE',
    app.i18n.t('pageErrors.errorNameNotUnique'),
    app.i18n.t('pageErrors.errorNameNotUniqueDescription')
  )

  store.registerModule('page', pageStore)
  store.registerModule('element', elementStore)
  store.registerModule('domain', domainStore)
  store.registerModule('publicBuilder', publicBuilderStore)
  store.registerModule('dataSource', dataSourceStore)
  store.registerModule('pageParameter', pageParameterStore)
  store.registerModule('dataSourceContent', dataSourceContentStore)
  store.registerModule('elementContent', elementContentStore)
  store.registerModule('theme', themeStore)
  store.registerModule('builderWorkflowAction', builderWorkflowActionStore)
  store.registerModule('formData', formDataStore)
  store.registerModule('builderToast', builderToast)

  app.$registry.registerNamespace('builderSettings')
  app.$registry.registerNamespace('element')
  app.$registry.registerNamespace('device')
  app.$registry.registerNamespace('pageHeaderItem')
  app.$registry.registerNamespace('domain')
  app.$registry.registerNamespace('pageSettings')
  app.$registry.registerNamespace('pathParamType')
  app.$registry.registerNamespace('builderDataProvider')
  app.$registry.registerNamespace('themeConfigBlock')
  app.$registry.registerNamespace('fontFamily')
  app.$registry.registerNamespace('builderPageDecorator')

  app.$registry.register('application', new BuilderApplicationType(context))
  app.$registry.register('job', new DuplicatePageJobType(context))
  app.$registry.register('job', new PublishBuilderJobType(context))

  app.$registry.register(
    'builderSettings',
    new GeneralBuilderSettingsType(context)
  )
  app.$registry.register(
    'builderSettings',
    new IntegrationsBuilderSettingsType(context)
  )
  app.$registry.register(
    'builderSettings',
    new ThemeBuilderSettingsType(context)
  )
  app.$registry.register(
    'builderSettings',
    new DomainsBuilderSettingsType(context)
  )

  app.$registry.register(
    'builderSettings',
    new UserSourcesBuilderSettingsType(context)
  )

  app.$registry.register('errorPage', new PublicSiteErrorPageType(context))

  app.$registry.register('element', new HeadingElementType(context))
  app.$registry.register('element', new TextElementType(context))
  app.$registry.register('element', new ImageElementType(context))
  app.$registry.register('element', new IFrameElementType(context))
  app.$registry.register('element', new LinkElementType(context))
  app.$registry.register('element', new ButtonElementType(context))
  app.$registry.register('element', new RatingElementType(context))
  app.$registry.register('element', new TableElementType(context))
  app.$registry.register('element', new SimpleContainerElementType(context))
  app.$registry.register('element', new ColumnElementType(context))
  app.$registry.register('element', new HeaderElementType(context))
  app.$registry.register('element', new FooterElementType(context))
  app.$registry.register('element', new FormContainerElementType(context))
  app.$registry.register('element', new InputTextElementType(context))
  app.$registry.register('element', new ChoiceElementType(context))
  app.$registry.register('element', new CheckboxElementType(context))
  app.$registry.register('element', new DateTimePickerElementType(context))
  app.$registry.register('element', new RecordSelectorElementType(context))
  app.$registry.register('element', new RepeatElementType(context))
  app.$registry.register('element', new RatingInputElementType(context))
  app.$registry.register('element', new MenuElementType(context))

  app.$registry.register('device', new DesktopDeviceType(context))
  app.$registry.register('device', new TabletDeviceType(context))
  app.$registry.register('device', new SmartphoneDeviceType(context))

  app.$registry.register(
    'pageHeaderItem',
    new ElementsPageHeaderItemType(context)
  )
  app.$registry.register(
    'pageHeaderItem',
    new DataSourcesPageHeaderItemType(context)
  )
  app.$registry.register(
    'pageHeaderItem',
    new SettingsPageHeaderItemType(context)
  )
  app.$registry.register('pageSidePanel', new GeneralPageSidePanelType(context))
  app.$registry.register('pageSidePanel', new StylePageSidePanelType(context))
  app.$registry.register(
    'pageSidePanel',
    new VisibilityPageSidePanelType(context)
  )
  app.$registry.register('pageSidePanel', new EventsPageSidePanelType(context))

  app.$registry.register('domain', new CustomDomainType(context))
  app.$registry.register('domain', new SubDomainType(context))

  app.$registry.register('pageSettings', new PagePageSettingsType(context))
  app.$registry.register(
    'pageSettings',
    new PageVisibilitySettingsType(context)
  )

  app.$registry.register('pathParamType', new TextPathParamType(context))
  app.$registry.register('pathParamType', new NumericPathParamType(context))

  app.$registry.register('queryParamType', new TextQueryParamType(context))
  app.$registry.register('queryParamType', new NumericQueryParamType(context))

  app.$registry.register('pageAction', new PublishPageActionType(context))
  app.$registry.register('pageAction', new PreviewPageActionType(context))

  app.$registry.register(
    'builderDataProvider',
    new UserDataProviderType(context)
  )
  app.$registry.register(
    'builderDataProvider',
    new CurrentRecordDataProviderType(context)
  )
  app.$registry.register(
    'builderDataProvider',
    new DataSourceDataProviderType(context)
  )
  app.$registry.register(
    'builderDataProvider',
    new DataSourceContextDataProviderType(context)
  )
  app.$registry.register(
    'builderDataProvider',
    new PageParameterDataProviderType(context)
  )
  app.$registry.register(
    'builderDataProvider',
    new FormDataProviderType(context)
  )
  app.$registry.register(
    'builderDataProvider',
    new PreviousActionDataProviderType(context)
  )
  app.$registry.register(
    'themeConfigBlock',
    new ColorThemeConfigBlockType(context)
  )
  app.$registry.register(
    'themeConfigBlock',
    new TypographyThemeConfigBlockType(context)
  )
  app.$registry.register(
    'themeConfigBlock',
    new ButtonThemeConfigBlockType(context)
  )
  app.$registry.register(
    'themeConfigBlock',
    new LinkThemeConfigBlockType(context)
  )
  app.$registry.register(
    'themeConfigBlock',
    new ImageThemeConfigBlockType(context)
  )
  app.$registry.register(
    'themeConfigBlock',
    new PageThemeConfigBlockType(context)
  )
  app.$registry.register(
    'themeConfigBlock',
    new InputThemeConfigBlockType(context)
  )
  app.$registry.register(
    'themeConfigBlock',
    new TableThemeConfigBlockType(context)
  )

  app.$registry.register(
    'workflowAction',
    new NotificationWorkflowActionType(context)
  )
  app.$registry.register(
    'workflowAction',
    new OpenPageWorkflowActionType(context)
  )
  app.$registry.register(
    'workflowAction',
    new LogoutWorkflowActionType(context)
  )
  app.$registry.register(
    'workflowAction',
    new RefreshDataSourceWorkflowActionType(context)
  )
  app.$registry.register(
    'workflowAction',
    new CoreHTTPRequestWorkflowActionType(context)
  )
  app.$registry.register(
    'workflowAction',
    new CoreSMTPEmailWorkflowActionType(context)
  )
  app.$registry.register(
    'workflowAction',
    new AIAgentWorkflowActionType(context)
  )
  app.$registry.register(
    'workflowAction',
    new CreateRowWorkflowActionType(context)
  )
  app.$registry.register(
    'workflowAction',
    new UpdateRowWorkflowActionType(context)
  )
  app.$registry.register(
    'workflowAction',
    new DeleteRowWorkflowActionType(context)
  )
  app.$registry.register(
    'workflowAction',
    new SlackWriteMessageWorkflowActionType(context)
  )

  app.$registry.register(
    'collectionField',
    new BooleanCollectionFieldType(context)
  )
  app.$registry.register(
    'collectionField',
    new TextCollectionFieldType(context)
  )
  app.$registry.register(
    'collectionField',
    new LinkCollectionFieldType(context)
  )
  app.$registry.register(
    'collectionField',
    new TagsCollectionFieldType(context)
  )
  app.$registry.register(
    'collectionField',
    new ButtonCollectionFieldType(context)
  )
  app.$registry.register(
    'collectionField',
    new ImageCollectionFieldType(context)
  )
  app.$registry.register(
    'collectionField',
    new RatingCollectionFieldType(context)
  )

  app.$registry.register('fontFamily', new InterFontFamilyType(context))
  app.$registry.register('fontFamily', new ArialFontFamilyType(context))
  app.$registry.register('fontFamily', new VerdanaFontFamilyType(context))
  app.$registry.register('fontFamily', new TahomaFontFamilyType(context))
  app.$registry.register('fontFamily', new TrebuchetMSFontFamilyType(context))
  app.$registry.register('fontFamily', new TimesNewRomanFontFamilyType(context))
  app.$registry.register('fontFamily', new GeorgiaFontFamilyType(context))
  app.$registry.register('fontFamily', new GaramondFontFamilyType(context))
  app.$registry.register('fontFamily', new CourierNewFontFamilyType(context))
  app.$registry.register('fontFamily', new BrushScriptMTFontFamilyType(context))

  app.$registry.register('guidedTour', new BuilderGuidedTourType(context))

  searchTypeRegistry.register(new BuilderSearchType())
}
