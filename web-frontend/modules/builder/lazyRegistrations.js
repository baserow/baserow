import {
  GeneralBuilderSettingsType,
  DomainsBuilderSettingsType,
  IntegrationsBuilderSettingsType,
  ThemeBuilderSettingsType,
  UserSourcesBuilderSettingsType,
} from '@baserow/modules/builder/builderSettingTypes'
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
  LocalBaserowUpdateRowsWorkflowActionType,
  LogoutWorkflowActionType,
  RefreshDataSourceWorkflowActionType,
  DeleteRowWorkflowActionType,
  CoreCSVFileReaderWorkflowActionType,
  CoreHTTPRequestWorkflowActionType,
  CoreSMTPEmailWorkflowActionType,
  CoreStartWorkflowWorkflowActionType,
  AIAgentWorkflowActionType,
  LocalBaserowCreateRowsWorkflowActionType,
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

export default function registerBuilderDomain(nuxtApp) {
  const { $registry } = nuxtApp
  const context = { app: nuxtApp }

  $registry.register('builderSettings', new GeneralBuilderSettingsType(context))
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

  $registry.register('errorPage', new PublicSiteErrorPageType(context))

  $registry.register('element', new HeadingElementType(context))
  $registry.register('element', new TextElementType(context))
  $registry.register('element', new ImageElementType(context))
  $registry.register('element', new IFrameElementType(context))
  $registry.register('element', new LinkElementType(context))
  $registry.register('element', new ButtonElementType(context))
  $registry.register('element', new RatingElementType(context))
  $registry.register('element', new TableElementType(context))
  $registry.register('element', new SimpleContainerElementType(context))
  $registry.register('element', new ColumnElementType(context))
  $registry.register('element', new HeaderElementType(context))
  $registry.register('element', new FooterElementType(context))
  $registry.register('element', new FormContainerElementType(context))
  $registry.register('element', new InputTextElementType(context))
  $registry.register('element', new ChoiceElementType(context))
  $registry.register('element', new CheckboxElementType(context))
  $registry.register('element', new DateTimePickerElementType(context))
  $registry.register('element', new RecordSelectorElementType(context))
  $registry.register('element', new RepeatElementType(context))
  $registry.register('element', new RatingInputElementType(context))
  $registry.register('element', new MenuElementType(context))

  $registry.register('device', new DesktopDeviceType(context))
  $registry.register('device', new TabletDeviceType(context))
  $registry.register('device', new SmartphoneDeviceType(context))

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

  $registry.register('pathParamType', new TextPathParamType(context))
  $registry.register('pathParamType', new NumericPathParamType(context))

  $registry.register('queryParamType', new TextQueryParamType(context))
  $registry.register('queryParamType', new NumericQueryParamType(context))

  $registry.register('pageAction', new PublishPageActionType(context))
  $registry.register('pageAction', new PreviewPageActionType(context))

  $registry.register('builderDataProvider', new UserDataProviderType(context))
  $registry.register(
    'builderDataProvider',
    new CurrentRecordDataProviderType(context)
  )
  $registry.register(
    'builderDataProvider',
    new DataSourceDataProviderType(context)
  )
  $registry.register(
    'builderDataProvider',
    new DataSourceContextDataProviderType(context)
  )
  $registry.register(
    'builderDataProvider',
    new PageParameterDataProviderType(context)
  )
  $registry.register('builderDataProvider', new FormDataProviderType(context))
  $registry.register(
    'builderDataProvider',
    new PreviousActionDataProviderType(context)
  )

  $registry.register('themeConfigBlock', new ColorThemeConfigBlockType(context))
  $registry.register(
    'themeConfigBlock',
    new TypographyThemeConfigBlockType(context)
  )
  $registry.register(
    'themeConfigBlock',
    new ButtonThemeConfigBlockType(context)
  )
  $registry.register('themeConfigBlock', new LinkThemeConfigBlockType(context))
  $registry.register('themeConfigBlock', new ImageThemeConfigBlockType(context))
  $registry.register('themeConfigBlock', new PageThemeConfigBlockType(context))
  $registry.register('themeConfigBlock', new InputThemeConfigBlockType(context))
  $registry.register('themeConfigBlock', new TableThemeConfigBlockType(context))

  $registry.register(
    'workflowAction',
    new NotificationWorkflowActionType(context)
  )
  $registry.register('workflowAction', new OpenPageWorkflowActionType(context))
  $registry.register('workflowAction', new LogoutWorkflowActionType(context))
  $registry.register(
    'workflowAction',
    new RefreshDataSourceWorkflowActionType(context)
  )
  $registry.register(
    'workflowAction',
    new CoreHTTPRequestWorkflowActionType(context)
  )
  $registry.register(
    'workflowAction',
    new CoreSMTPEmailWorkflowActionType(context)
  )
  $registry.register(
    'workflowAction',
    new CoreCSVFileReaderWorkflowActionType(context)
  )
  $registry.register(
    'workflowAction',
    new CoreStartWorkflowWorkflowActionType(context)
  )
  $registry.register('workflowAction', new AIAgentWorkflowActionType(context))
  $registry.register('workflowAction', new CreateRowWorkflowActionType(context))
  $registry.register(
    'workflowAction',
    new LocalBaserowCreateRowsWorkflowActionType(context)
  )
  $registry.register('workflowAction', new UpdateRowWorkflowActionType(context))
  $registry.register(
    'workflowAction',
    new LocalBaserowUpdateRowsWorkflowActionType(context)
  )
  $registry.register('workflowAction', new DeleteRowWorkflowActionType(context))
  $registry.register(
    'workflowAction',
    new SlackWriteMessageWorkflowActionType(context)
  )

  $registry.register('collectionField', new BooleanCollectionFieldType(context))
  $registry.register('collectionField', new TextCollectionFieldType(context))
  $registry.register('collectionField', new LinkCollectionFieldType(context))
  $registry.register('collectionField', new TagsCollectionFieldType(context))
  $registry.register('collectionField', new ButtonCollectionFieldType(context))
  $registry.register('collectionField', new ImageCollectionFieldType(context))
  $registry.register('collectionField', new RatingCollectionFieldType(context))

  $registry.register('fontFamily', new InterFontFamilyType(context))
  $registry.register('fontFamily', new ArialFontFamilyType(context))
  $registry.register('fontFamily', new VerdanaFontFamilyType(context))
  $registry.register('fontFamily', new TahomaFontFamilyType(context))
  $registry.register('fontFamily', new TrebuchetMSFontFamilyType(context))
  $registry.register('fontFamily', new TimesNewRomanFontFamilyType(context))
  $registry.register('fontFamily', new GeorgiaFontFamilyType(context))
  $registry.register('fontFamily', new GaramondFontFamilyType(context))
  $registry.register('fontFamily', new CourierNewFontFamilyType(context))
  $registry.register('fontFamily', new BrushScriptMTFontFamilyType(context))

  $registry.register('guidedTour', new BuilderGuidedTourType(context))
}
