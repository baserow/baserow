from rest_framework import viewsets
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.plumbing import (
    build_root_object,
    ComponentRegistry,
    force_instance,
    is_serializer,
    is_list_serializer,
)


class FullyInlineAutoSchema(AutoSchema):
    def _map_serializer_field(self, field, direction, bypass_extensions=False):
        from drf_spectacular.plumbing import is_serializer, is_list_serializer

        if is_list_serializer(field):
            return self._unwrap_list_serializer(field, direction)

        if is_serializer(field):
            return self._map_serializer(field, direction)

        return super()._map_serializer_field(field, direction, bypass_extensions)

    def _unwrap_list_serializer(self, serializer, direction):
        """
        Override list serializer unwrapping to inline the child serializer,
        avoiding any $ref in deeply nested lists.
        """
        from drf_spectacular.plumbing import is_list_serializer, is_serializer

        if not is_list_serializer(serializer):
            return None

        child = serializer.child
        if is_serializer(child):
            item_schema = self._map_serializer(child, direction)
            return {
                "type": "array",
                "items": item_schema
            }

        # fallback
        return super()._unwrap_list_serializer(serializer, direction)


def serializer_to_openapi_inline(serializer_class, method="GET", direction="response"):
    """
    Generate an inline OpenAPI schema dict from a DRF serializer using drf-spectacular (v0.27.2),
    without $ref or component registration.
    """
    class DummyViewSet(viewsets.ViewSet):
        def get_serializer(self, *args, **kwargs):
            return serializer_class(*args, **kwargs)

    factory = APIRequestFactory()
    request = factory.generic(method.upper(), "/dummy/")
    wrapped_request = Request(request)

    dummy_view = DummyViewSet()
    dummy_view.request = wrapped_request
    dummy_view.format_kwarg = None

    schema = FullyInlineAutoSchema()
    schema.view = dummy_view
    schema.method = method.upper()
    schema.path = "/dummy/"
    schema.registry = ComponentRegistry()

    build_root_object(
        paths={"/dummy/": {schema.method.lower(): schema}},
        components={},
        webhooks={},
        version="1.0.0"
    )

    serializer_instance = serializer_class()
    return schema._map_serializer(serializer_instance, direction)
