from django.apps import AppConfig


class WhiteboardConfig(AppConfig):
    name = "baserow.contrib.whiteboard"

    def ready(self):
        from baserow.core.notifications.registries import notification_type_registry
        from baserow.core.registries import (
            application_type_registry,
            object_scope_type_registry,
            operation_type_registry,
            permission_manager_type_registry,
        )
        from baserow.ws.registries import page_registry

        from .application_types import WhiteboardApplicationType
        from .comments.notification_types import (
            WhiteboardCommentMentionNotificationType,
            WhiteboardCommentReplyNotificationType,
        )
        from .comments.operations import (
            CreateWhiteboardCommentOperationType,
            DeleteWhiteboardCommentOperationType,
            ListWhiteboardCommentsOperationType,
            ResolveWhiteboardCommentOperationType,
            UpdateWhiteboardCommentOperationType,
        )
        from .object_scopes import WhiteboardObjectScopeType
        from .operations import (
            ReadWhiteboardOperationType,
            UpdateWhiteboardContentOperationType,
        )
        from .ws.pages import WhiteboardPageType

        application_type_registry.register(WhiteboardApplicationType())
        object_scope_type_registry.register(WhiteboardObjectScopeType())
        operation_type_registry.register(ReadWhiteboardOperationType())
        operation_type_registry.register(UpdateWhiteboardContentOperationType())
        operation_type_registry.register(ListWhiteboardCommentsOperationType())
        operation_type_registry.register(CreateWhiteboardCommentOperationType())
        operation_type_registry.register(UpdateWhiteboardCommentOperationType())
        operation_type_registry.register(DeleteWhiteboardCommentOperationType())
        operation_type_registry.register(ResolveWhiteboardCommentOperationType())
        page_registry.register(WhiteboardPageType())

        notification_type_registry.register(WhiteboardCommentMentionNotificationType())
        notification_type_registry.register(WhiteboardCommentReplyNotificationType())

        from .permission_manager import AllowIfTemplatePermissionManagerType

        prev_manager = permission_manager_type_registry.get(
            AllowIfTemplatePermissionManagerType.type
        )
        permission_manager_type_registry.unregister(
            AllowIfTemplatePermissionManagerType.type
        )
        permission_manager_type_registry.register(
            AllowIfTemplatePermissionManagerType(prev_manager)
        )

        from .comments import notification_types  # noqa: F401
        from .ws import (
            comment_receivers,  # noqa: F401
            receivers,  # noqa: F401
        )
