from django.apps import AppConfig


class WhiteboardConfig(AppConfig):
    name = "baserow.contrib.whiteboard"

    def ready(self):
        from baserow.core.registries import (
            application_type_registry,
            object_scope_type_registry,
            operation_type_registry,
        )
        from baserow.ws.registries import page_registry

        from .application_types import WhiteboardApplicationType
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
        page_registry.register(WhiteboardPageType())

        from .ws import receivers  # noqa: F401
