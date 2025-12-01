from django.apps import AppConfig


class BuilderConfig(AppConfig):
    name = "baserow.contrib.builder"

    def ready(self):
        from baserow.core.registries import (
            application_type_registry,
            object_scope_type_registry,
            operation_type_registry,
        )
        from baserow.core.trash.registries import trash_item_type_registry
        from baserow.core.usage.registries import workspace_storage_usage_item_registry

        from .application_types import BuilderApplicationType

        application_type_registry.register(BuilderApplicationType())

        from baserow.contrib.builder.data_sources.object_scopes import (
            BuilderDataSourceObjectScopeType,
        )
        from baserow.contrib.builder.domains.object_scopes import (
            BuilderDomainObjectScopeType,
        )
        from baserow.contrib.builder.elements.object_scopes import (
            BuilderElementObjectScopeType,
        )
        from baserow.contrib.builder.object_scopes import BuilderObjectScopeType
        from baserow.contrib.builder.pages.object_scopes import (
            BuilderPageObjectScopeType,
        )
        from baserow.contrib.builder.workflow_actions.object_scopes import (
            BuilderWorkflowActionScopeType,
        )

        object_scope_type_registry.register(BuilderObjectScopeType())
        object_scope_type_registry.register(BuilderPageObjectScopeType())
        object_scope_type_registry.register(BuilderElementObjectScopeType())
        object_scope_type_registry.register(BuilderDomainObjectScopeType())
        object_scope_type_registry.register(BuilderDataSourceObjectScopeType())
        object_scope_type_registry.register(BuilderWorkflowActionScopeType())

        from baserow.contrib.builder.operations import (
            ListDomainsBuilderOperationType,
            ListPagesBuilderOperationType,
            OrderDomainsBuilderOperationType,
            OrderPagesBuilderOperationType,
        )

        operation_type_registry.register(ListPagesBuilderOperationType())
        operation_type_registry.register(OrderPagesBuilderOperationType())
        operation_type_registry.register(ListDomainsBuilderOperationType())
        operation_type_registry.register(OrderDomainsBuilderOperationType())

        from baserow.contrib.builder.elements.usage_types import (
            ImageElementWorkspaceStorageUsageItem,
        )

        workspace_storage_usage_item_registry.register(
            ImageElementWorkspaceStorageUsageItem()
        )

        from baserow.contrib.builder.pages.operations import (
            CreatePageOperationType,
            DeletePageOperationType,
            DuplicatePageOperationType,
            ReadPageOperationType,
            UpdatePageOperationType,
        )

        operation_type_registry.register(CreatePageOperationType())
        operation_type_registry.register(DeletePageOperationType())
        operation_type_registry.register(UpdatePageOperationType())
        operation_type_registry.register(ReadPageOperationType())
        operation_type_registry.register(DuplicatePageOperationType())

        from baserow.contrib.builder.domains.operations import (
            CreateDomainOperationType,
            DeleteDomainOperationType,
            PublishDomainOperationType,
            ReadDomainOperationType,
            RestoreDomainOperationType,
            UpdateDomainOperationType,
        )

        operation_type_registry.register(CreateDomainOperationType())
        operation_type_registry.register(DeleteDomainOperationType())
        operation_type_registry.register(ReadDomainOperationType())
        operation_type_registry.register(UpdateDomainOperationType())
        operation_type_registry.register(PublishDomainOperationType())
        operation_type_registry.register(RestoreDomainOperationType())

        from baserow.contrib.builder.data_sources.operations import (
            CreateDataSourceOperationType,
            DeleteDataSourceOperationType,
            DispatchDataSourceOperationType,
            ListDataSourcesPageOperationType,
            OrderDataSourcesPageOperationType,
            ReadDataSourceOperationType,
            UpdateDataSourceOperationType,
        )

        operation_type_registry.register(CreateDataSourceOperationType())
        operation_type_registry.register(ListDataSourcesPageOperationType())
        operation_type_registry.register(ReadDataSourceOperationType())
        operation_type_registry.register(UpdateDataSourceOperationType())
        operation_type_registry.register(DeleteDataSourceOperationType())
        operation_type_registry.register(OrderDataSourcesPageOperationType())
        operation_type_registry.register(DispatchDataSourceOperationType())

        from baserow.contrib.builder.domains.job_types import PublishDomainJobType
        from baserow.contrib.builder.pages.job_types import DuplicatePageJobType
        from baserow.core.jobs.registries import job_type_registry

        job_type_registry.register(DuplicatePageJobType())
        job_type_registry.register(PublishDomainJobType())

        from baserow.contrib.builder.elements.operations import (
            CreateElementOperationType,
            DeleteElementOperationType,
            ListElementsPageOperationType,
            OrderElementsPageOperationType,
            ReadElementOperationType,
            UpdateElementOperationType,
        )

        operation_type_registry.register(ListElementsPageOperationType())
        operation_type_registry.register(OrderElementsPageOperationType())
        operation_type_registry.register(CreateElementOperationType())
        operation_type_registry.register(ReadElementOperationType())
        operation_type_registry.register(UpdateElementOperationType())
        operation_type_registry.register(DeleteElementOperationType())

        from baserow.contrib.builder.workflow_actions.operations import (
            CreateBuilderWorkflowActionOperationType,
            DeleteBuilderWorkflowActionOperationType,
            DispatchBuilderWorkflowActionOperationType,
            ListBuilderWorkflowActionsPageOperationType,
            OrderBuilderWorkflowActionOperationType,
            ReadBuilderWorkflowActionOperationType,
            UpdateBuilderWorkflowActionOperationType,
        )

        operation_type_registry.register(ListBuilderWorkflowActionsPageOperationType())
        operation_type_registry.register(CreateBuilderWorkflowActionOperationType())
        operation_type_registry.register(DeleteBuilderWorkflowActionOperationType())
        operation_type_registry.register(UpdateBuilderWorkflowActionOperationType())
        operation_type_registry.register(ReadBuilderWorkflowActionOperationType())
        operation_type_registry.register(OrderBuilderWorkflowActionOperationType())
        operation_type_registry.register(DispatchBuilderWorkflowActionOperationType())

        from baserow.core.registries import permission_manager_type_registry

        from .domains.permission_manager import AllowPublicBuilderManagerType
        from .elements.permission_manager import ElementVisibilityPermissionManager
        from .permission_manager import AllowIfTemplatePermissionManagerType

        permission_manager_type_registry.register(AllowPublicBuilderManagerType())
        permission_manager_type_registry.register(ElementVisibilityPermissionManager())

        prev_manager = permission_manager_type_registry.get(
            AllowIfTemplatePermissionManagerType.type
        )
        permission_manager_type_registry.unregister(
            AllowIfTemplatePermissionManagerType.type
        )
        permission_manager_type_registry.register(
            AllowIfTemplatePermissionManagerType(prev_manager)
        )

        from .elements.element_types import (
            ButtonElementType,
            CheckboxElementType,
            ChoiceElementType,
            ColumnElementType,
            DateTimePickerElementType,
            FooterElementType,
            FormContainerElementType,
            HeaderElementType,
            HeadingElementType,
            IFrameElementType,
            ImageElementType,
            InputTextElementType,
            LinkElementType,
            MenuElementType,
            RatingElementType,
            RatingInputElementType,
            RecordSelectorElementType,
            RepeatElementType,
            SimpleContainerElementType,
            TableElementType,
            TextElementType,
        )
        from .elements.registries import element_type_registry

        element_type_registry.register(HeadingElementType())
        element_type_registry.register(TextElementType())
        element_type_registry.register(RatingElementType())
        element_type_registry.register(RatingInputElementType())
        element_type_registry.register(LinkElementType())
        element_type_registry.register(ImageElementType())
        element_type_registry.register(InputTextElementType())
        element_type_registry.register(ColumnElementType())
        element_type_registry.register(ButtonElementType())
        element_type_registry.register(TableElementType())
        element_type_registry.register(RepeatElementType())
        element_type_registry.register(RecordSelectorElementType())
        element_type_registry.register(FormContainerElementType())
        element_type_registry.register(ChoiceElementType())
        element_type_registry.register(CheckboxElementType())
        element_type_registry.register(IFrameElementType())
        element_type_registry.register(DateTimePickerElementType())
        element_type_registry.register(HeaderElementType())
        element_type_registry.register(FooterElementType())
        element_type_registry.register(MenuElementType())
        element_type_registry.register(SimpleContainerElementType())

        from .domains.domain_types import CustomDomainType, SubDomainType
        from .domains.registries import domain_type_registry

        domain_type_registry.register(CustomDomainType())
        domain_type_registry.register(SubDomainType())

        from .domains.trash_types import DomainTrashableItemType

        trash_item_type_registry.register(DomainTrashableItemType())

        from baserow.contrib.builder.data_providers.registries import (
            builder_data_provider_type_registry,
        )

        from .data_providers.data_provider_types import (
            CurrentRecordDataProviderType,
            DataSourceContextDataProviderType,
            DataSourceDataProviderType,
            FormDataProviderType,
            PageParameterDataProviderType,
            PreviousActionProviderType,
            UserDataProviderType,
        )

        builder_data_provider_type_registry.register(DataSourceDataProviderType())
        builder_data_provider_type_registry.register(
            DataSourceContextDataProviderType()
        )
        builder_data_provider_type_registry.register(PageParameterDataProviderType())
        builder_data_provider_type_registry.register(CurrentRecordDataProviderType())
        builder_data_provider_type_registry.register(FormDataProviderType())
        builder_data_provider_type_registry.register(PreviousActionProviderType())
        builder_data_provider_type_registry.register(UserDataProviderType())

        from baserow.contrib.builder.theme.operations import UpdateThemeOperationType

        operation_type_registry.register(UpdateThemeOperationType())

        from .theme.registries import theme_config_block_registry
        from .theme.theme_config_block_types import (
            ButtonThemeConfigBlockType,
            ColorThemeConfigBlockType,
            ImageThemeConfigBlockType,
            InputThemeConfigBlockType,
            LinkThemeConfigBlockType,
            PageThemeConfigBlockType,
            TableThemeConfigBlockType,
            TypographyThemeConfigBlockType,
        )

        theme_config_block_registry.register(ColorThemeConfigBlockType())
        theme_config_block_registry.register(TypographyThemeConfigBlockType())
        theme_config_block_registry.register(ButtonThemeConfigBlockType())
        theme_config_block_registry.register(ImageThemeConfigBlockType())
        theme_config_block_registry.register(PageThemeConfigBlockType())
        theme_config_block_registry.register(InputThemeConfigBlockType())
        theme_config_block_registry.register(TableThemeConfigBlockType())
        theme_config_block_registry.register(LinkThemeConfigBlockType())

        from .workflow_actions.registries import builder_workflow_action_type_registry
        from .workflow_actions.workflow_action_types import (
            AIAgentWorkflowActionType,
            CoreHttpRequestActionType,
            CoreSMTPEmailActionType,
            CreateRowWorkflowActionType,
            DeleteRowWorkflowActionType,
            LogoutWorkflowActionType,
            NotificationWorkflowActionType,
            OpenPageWorkflowActionType,
            RefreshDataSourceWorkflowActionType,
            SlackWriteMessageWorkflowActionType,
            UpdateRowWorkflowActionType,
        )

        builder_workflow_action_type_registry.register(NotificationWorkflowActionType())
        builder_workflow_action_type_registry.register(OpenPageWorkflowActionType())
        builder_workflow_action_type_registry.register(CreateRowWorkflowActionType())
        builder_workflow_action_type_registry.register(UpdateRowWorkflowActionType())
        builder_workflow_action_type_registry.register(DeleteRowWorkflowActionType())
        builder_workflow_action_type_registry.register(LogoutWorkflowActionType())
        builder_workflow_action_type_registry.register(
            RefreshDataSourceWorkflowActionType()
        )
        builder_workflow_action_type_registry.register(CoreHttpRequestActionType())
        builder_workflow_action_type_registry.register(CoreSMTPEmailActionType())
        builder_workflow_action_type_registry.register(AIAgentWorkflowActionType())
        builder_workflow_action_type_registry.register(
            SlackWriteMessageWorkflowActionType()
        )

        from .elements.collection_field_types import (
            BooleanCollectionFieldType,
            ButtonCollectionFieldType,
            ImageCollectionFieldType,
            LinkCollectionFieldType,
            RatingCollectionFieldType,
            TagsCollectionFieldType,
            TextCollectionFieldType,
        )
        from .elements.registries import collection_field_type_registry

        collection_field_type_registry.register(BooleanCollectionFieldType())
        collection_field_type_registry.register(RatingCollectionFieldType())
        collection_field_type_registry.register(TextCollectionFieldType())
        collection_field_type_registry.register(LinkCollectionFieldType())
        collection_field_type_registry.register(TagsCollectionFieldType())
        collection_field_type_registry.register(ButtonCollectionFieldType())
        collection_field_type_registry.register(ImageCollectionFieldType())

        from .domains.receivers import connect_to_domain_pre_delete_signal

        connect_to_domain_pre_delete_signal()

        from .data_sources.receivers import connect_to_data_source_pre_delete_signal

        connect_to_data_source_pre_delete_signal()

        from baserow.contrib.builder.workflow_actions.receivers import (
            connect_to_builder_workflow_action_pre_delete_signal,
        )

        connect_to_builder_workflow_action_pre_delete_signal()

        # The signals must always be imported last because they use the registries
        # which need to be filled first.
        import baserow.contrib.builder.signals  # noqa: F403, F401
        import baserow.contrib.builder.ws.signals  # noqa: F403, F401
        from baserow.core.search.registries import workspace_search_registry

        from .search_types import BuilderSearchType

        workspace_search_registry.register(BuilderSearchType())
