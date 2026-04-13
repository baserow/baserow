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

        application_type_registry.register(WhiteboardApplicationType())

        from .object_scopes import WhiteboardObjectScopeType

        object_scope_type_registry.register(WhiteboardObjectScopeType())

        from .operations import (
            ReadWhiteboardOperationType,
            UpdateWhiteboardContentOperationType,
        )

        operation_type_registry.register(ReadWhiteboardOperationType())
        operation_type_registry.register(UpdateWhiteboardContentOperationType())

        from .ws.pages import WhiteboardPageType

        page_registry.register(WhiteboardPageType())
