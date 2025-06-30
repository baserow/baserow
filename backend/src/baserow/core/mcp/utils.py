import re
from typing import Dict, Optional
from urllib.parse import urlencode

from django.contrib.auth.models import AbstractUser
from django.urls import reverse

from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.openapi import AutoSchema
from drf_spectacular.plumbing import (
    ComponentRegistry,
    OpenApiGeneratorExtension,
    build_root_object,
    force_instance,
)
from rest_framework import viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.test import APIClient, APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken


class FullyInlineAutoSchema(AutoSchema):
    def _map_serializer_field(self, field, direction, bypass_extensions=False):
        from drf_spectacular.plumbing import is_list_serializer, is_serializer

        if is_list_serializer(field):
            return self._unwrap_list_serializer(field, direction)

        if is_serializer(field):
            return self._map_serializer(field, direction)

        return super()._map_serializer_field(field, direction, bypass_extensions)

    def _unwrap_list_serializer(self, serializer, direction):
        from drf_spectacular.plumbing import is_list_serializer, is_serializer

        if not is_list_serializer(serializer):
            return None

        child = serializer.child
        if is_serializer(child):
            item_schema = self._map_serializer(child, direction)
            return {"type": "array", "items": item_schema}

        return super()._unwrap_list_serializer(serializer, direction)

    def resolve_serializer(self, serializer, direction):
        """
        Overrides the normal behavior to avoid ever returning $ref.
        This forces all serializers (including those via extensions) to be fully
        inlined.
        """

        serializer = force_instance(serializer)
        extension = OpenApiSerializerExtension.get_match(serializer)

        schema_dict = (
            extension.map_serializer(self, direction)
            if extension
            else self._map_serializer(serializer, direction)
        )

        # Return a dummy object that provides `.ref` as the inlined schema dict
        return type("ResolvedInline", (), {"ref": schema_dict})()


def serializer_to_openapi_inline(
    serializer_class: Serializer, method: str = "GET", direction: str = "request"
) -> Dict:
    """
    This helper method converts the provided serializer class into an inline OpenAPI
    schema dict. It uses the `drf-spectacular` library that we're already using to
    automatically generate the full API docs.

    It's also compatible with OpenAPI serializer extensions like
    `CustomFieldRegistryMappingSerializer`.

    :param serializer_class: The serializer class that must be converted to the OpenAI
        dict.
    :param method: `drf-spectacular` automatically extracts information from a view.
        It therefore also extracts the method, and it must be provided here.
    :param direction: `request` or `response` serializer.
    :return: The OpenAPI spec of the serializer as dict.
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
        version="1.0.0",
    )

    serializer_instance = force_instance(serializer_class)

    extension = OpenApiGeneratorExtension.get_match(serializer_instance)
    if extension:
        return extension.map_serializer(schema, direction)
    else:
        return schema._map_serializer(serializer_instance, direction)


class NameRoute:
    """
    Helper class to construct an match a route with parameters. Can be used like:

    ```
    route = NameRoute("/page/{id}/test")
    route.match("/page/1/test") == {"id": 1}
    route.match("other-page") == None
    ```
    """

    def __init__(self, pattern: str):
        self.pattern = pattern
        self.regex, self.param_names = self._compile_pattern(pattern)

    def _compile_pattern(self, pattern: str):
        param_names = []
        regex_pattern = ""

        pos = 0
        for match in re.finditer(r"{(\w+)}", pattern):
            start, end = match.span()
            param_name = match.group(1)
            param_names.append(param_name)

            regex_pattern += re.escape(pattern[pos:start])
            regex_pattern += r"(?P<%s>[^/]+)" % param_name
            pos = end

        regex_pattern += re.escape(pattern[pos:])
        regex = re.compile(f"^{regex_pattern}$")
        return regex, param_names

    def match(self, path: str) -> Optional[Dict[str, str]]:
        match = self.regex.match(path)
        if match:
            return match.groupdict()
        return None


def internal_api_request(
    route_name: str,
    method: str = "GET",
    path_params: Optional[dict] = None,
    data: Optional[dict] = None,
    user: Optional[AbstractUser] = None,
    query_params: Optional[dict] = None,
) -> Response:
    """
    Simulate an internal API request in Django.

    :param route_name: Name of the URL pattern (named route).
    :param method: HTTP method (e.g., 'GET', 'POST').
    :param path_params: Dictionary of path parameters.
    :param data: Dictory used as payload in the body.
    :param user: User object or None if anonymous. Automatically adds the `JWT`
        authorization header if provided.
    :param query_params: Dictionary of query parameters.
    :return: Response from the view function.
    """

    client = APIClient()

    if user:
        jwt_token = str(AccessToken.for_user(user))
        client.credentials(HTTP_AUTHORIZATION=f"JWT {jwt_token}")

    base_url = reverse(route_name, kwargs=path_params or {})
    if query_params:
        query_string = urlencode(query_params)
        url_path = f"{base_url}?{query_string}"
    else:
        url_path = base_url

    headers = {"Content-Type": "application/json"}

    method_func = getattr(client, method.lower(), None)
    if not method_func:
        raise ValueError(f"Unsupported HTTP method: {method}")

    response = method_func(url_path, data=data, format="json", **headers)
    return response
