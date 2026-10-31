from contextlib import contextmanager
from unittest.mock import Mock, patch

from django.db import connection
from django.urls import reverse

import pytest
from requests import exceptions as request_exceptions
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from advocate.exceptions import UnacceptableAddressException
from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.data_sources.service import DataSourceService
from baserow.contrib.integrations.core.constants import (
    HTTP_DATA_SOURCE_DEFAULT_RESULT_LIMIT,
    HTTP_DATA_SOURCE_MAX_RESULT_LIMIT,
    HTTP_DATA_SOURCE_TIMEOUT_DEFAULT,
    HTTP_METHOD,
)
from baserow.contrib.integrations.core.models import (
    CoreHTTPDataSourceService,
    CoreHTTPRequestService,
    CoreRouterService,
    HTTPHeader,
    HTTPQueryParam,
)
from baserow.contrib.integrations.core.service_types import (
    CoreHTTPDataSourceServiceType,
)
from baserow.core.registries import ImportExportConfig
from baserow.core.services.exceptions import (
    AddressNotAllowedDispatchException,
    RemoteBusyDispatchException,
    RemoteRefusedDispatchException,
    RuntimeDispatchException,
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
)
from baserow.core.services.registries import service_type_registry
from baserow.core.services.utils import sample_data_skeleton
from baserow.test_utils.pytest_conftest import FakeDispatchContext


# Answers the service's outbound call, so nothing here reaches the network.
@contextmanager
def mock_http_get(body=None, status_code=200, raise_exception=None, text=None):
    response = Mock()
    response.status_code = status_code
    response.headers = {"Content-Type": "application/json"}
    if text is not None:
        response.text = text
        response.json.side_effect = request_exceptions.JSONDecodeError(
            "mocked json error", "", 0
        )
    else:
        response.json.return_value = body

    with patch(
        "baserow.contrib.integrations.core.service_types.send_http_request"
    ) as mock_request:
        if raise_exception is not None:
            mock_request.side_effect = raise_exception
        else:
            mock_request.return_value = response
        yield mock_request


def create_http_get_service(data_fixture, **kwargs):
    kwargs.setdefault("url", "'https://example.notexist/items'")
    kwargs.setdefault("timeout", HTTP_DATA_SOURCE_TIMEOUT_DEFAULT)
    return data_fixture.create_service(CoreHTTPDataSourceService, **kwargs)


def test_http_data_source_type_is_registered():
    service_type = service_type_registry.get("http_get")

    assert isinstance(service_type, CoreHTTPDataSourceServiceType)
    assert service_type_registry.get_by_model(CoreHTTPDataSourceService) is (
        service_type
    )


@pytest.mark.django_db
def test_http_data_source_returns_list_per_service(data_fixture):
    service_type = service_type_registry.get("http_get")

    assert not service_type.returns_list(create_http_get_service(data_fixture))
    assert service_type.returns_list(
        create_http_get_service(data_fixture, returns_list=True)
    )


@pytest.mark.django_db
def test_http_data_source_always_sends_get_with_headers_and_params(data_fixture):
    service = create_http_get_service(data_fixture, http_method=HTTP_METHOD.POST)
    HTTPHeader.objects.create(service=service, key="Authorization", value="'Bearer x'")
    HTTPQueryParam.objects.create(service=service, key="page", value="'2'")

    with mock_http_get({"name": "Ada"}) as mock_request:
        result = service.get_type().dispatch(service, FakeDispatchContext())

    mock_request.assert_called_once()
    kwargs = mock_request.call_args.kwargs
    assert kwargs["method"] == HTTP_METHOD.GET
    assert kwargs["url"] == "https://example.notexist/items"
    assert kwargs["headers"]["Authorization"] == "Bearer x"
    assert kwargs["params"] == {"page": "2"}
    assert kwargs["operation_timeout"] == HTTP_DATA_SOURCE_TIMEOUT_DEFAULT
    assert "data" not in kwargs and "json" not in kwargs
    assert result.data == {"name": "Ada"}


@pytest.mark.django_db
def test_http_data_source_missing_url(data_fixture):
    service = create_http_get_service(data_fixture, url="")

    with mock_http_get({}) as mock_request:
        with pytest.raises(ServiceImproperlyConfiguredDispatchException):
            service.get_type().dispatch(service, FakeDispatchContext())

    mock_request.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status_code,exception",
    [
        (400, RemoteRefusedDispatchException),
        (404, RemoteRefusedDispatchException),
        (301, RemoteRefusedDispatchException),
        (429, RemoteBusyDispatchException),
        (500, RemoteBusyDispatchException),
        (503, RemoteBusyDispatchException),
    ],
)
def test_http_data_source_non_2xx_raises(data_fixture, status_code, exception):
    service = create_http_get_service(data_fixture)

    with mock_http_get({"error": "nope"}, status_code=status_code):
        with pytest.raises(exception) as raised:
            service.get_type().dispatch(service, FakeDispatchContext())

    assert str(status_code) in str(raised.value)
    assert "example.notexist" not in str(raised.value)
    if status_code < 500 and status_code != 429:
        assert not isinstance(raised.value, RemoteBusyDispatchException)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "timeout_exception",
    [request_exceptions.ReadTimeout(), request_exceptions.ConnectTimeout()],
)
def test_http_data_source_timeout_raises(data_fixture, timeout_exception):
    service = create_http_get_service(data_fixture)

    with mock_http_get(raise_exception=timeout_exception):
        with pytest.raises(RuntimeDispatchException) as raised:
            service.get_type().dispatch(service, FakeDispatchContext())

    assert "timed out" in str(raised.value)


@pytest.mark.django_db
def test_http_data_source_non_json_body_raises(data_fixture):
    service = create_http_get_service(data_fixture)

    with mock_http_get(text="<html>hello</html>"):
        with pytest.raises(RemoteRefusedDispatchException) as raised:
            service.get_type().dispatch(service, FakeDispatchContext())

    assert "not valid JSON" in str(raised.value)


@pytest.mark.django_db
def test_http_data_source_removes_null_characters(data_fixture):
    service = create_http_get_service(data_fixture)

    with mock_http_get({"name": "A\x00da"}):
        result = service.get_type().dispatch(service, FakeDispatchContext())

    assert result.data == {"name": "Ada"}


@pytest.mark.django_db
def test_http_list_data_source_reads_root_list(data_fixture):
    service = create_http_get_service(data_fixture, returns_list=True)
    body = [{"id": 10, "name": "a"}, {"id": "b-2", "name": "b"}]

    with mock_http_get(body):
        result = service.get_type().dispatch(service, FakeDispatchContext())

    # Every record has an id, so they keep it and get no position.
    assert result.data == {"results": body, "has_next_page": False}


@pytest.mark.django_db
def test_http_list_data_source_reads_list_path(data_fixture):
    service = create_http_get_service(
        data_fixture, returns_list=True, list_path="data.items"
    )
    body = {"data": {"items": [{"name": "a"}, {"name": "b"}, "c"]}, "total": 3}

    with mock_http_get(body):
        result = service.get_type().dispatch(service, FakeDispatchContext())

    # Not every record has an id, so each gets its position. An item which
    # isn't an object becomes one.
    assert result.data == {
        "results": [
            {"name": "a", "_id": 0},
            {"name": "b", "_id": 1},
            {"value": "c", "_id": 2},
        ],
        "has_next_page": False,
    }


@pytest.mark.django_db
def test_http_list_data_source_list_path_with_index(data_fixture):
    service = create_http_get_service(
        data_fixture, returns_list=True, list_path="pages.1.rows"
    )
    body = {"pages": [{"rows": [{"id": 1}]}, {"rows": [{"id": 2}]}]}

    with mock_http_get(body):
        result = service.get_type().dispatch(service, FakeDispatchContext())

    assert result.data["results"] == [{"id": 2}]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "list_path,body,message",
    [
        ("", {"items": []}, "Expected a list as the response"),
        ("items", {"items": {"a": 1}}, 'Expected a list at "items"'),
        ("missing", {"items": []}, 'The path "missing" was not found'),
    ],
)
def test_http_list_data_source_expected_a_list(data_fixture, list_path, body, message):
    service = create_http_get_service(
        data_fixture, returns_list=True, list_path=list_path
    )

    with mock_http_get(body):
        with pytest.raises(ServiceImproperlyConfiguredDispatchException) as raised:
            service.get_type().dispatch(service, FakeDispatchContext())

    assert message in str(raised.value)


@pytest.mark.django_db
def test_http_list_data_source_slices_with_range(data_fixture):
    service = create_http_get_service(data_fixture, returns_list=True)
    body = [{"name": str(index)} for index in range(5)]
    dispatch_context = FakeDispatchContext()
    dispatch_context.range = lambda service: (1, 2)

    with mock_http_get(body):
        result = service.get_type().dispatch(service, dispatch_context)

    assert result.data == {
        "results": [{"name": "1", "_id": 1}, {"name": "2", "_id": 2}],
        "has_next_page": True,
    }

    dispatch_context.range = lambda service: (3, 2)
    with mock_http_get(body):
        result = service.get_type().dispatch(service, dispatch_context)

    assert result.data["has_next_page"] is False
    assert [record["_id"] for record in result.data["results"]] == [3, 4]


@pytest.mark.django_db
def test_http_list_data_source_default_and_max_count(data_fixture):
    service = create_http_get_service(data_fixture, returns_list=True)
    body = [{"name": str(index)} for index in range(150)]
    dispatch_context = FakeDispatchContext()

    dispatch_context.range = lambda service: (0, None)
    with mock_http_get(body):
        result = service.get_type().dispatch(service, dispatch_context)
    assert len(result.data["results"]) == HTTP_DATA_SOURCE_DEFAULT_RESULT_LIMIT

    dispatch_context.range = lambda service: (0, 1000)
    with mock_http_get(body):
        result = service.get_type().dispatch(service, dispatch_context)
    assert len(result.data["results"]) == HTTP_DATA_SOURCE_MAX_RESULT_LIMIT
    assert result.data["has_next_page"] is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    "body,only_record_id,expected",
    [
        ([{"id": "a"}, {"id": "b"}], "b", [{"id": "b"}]),
        ([{"id": 1}, {"id": 2}], "2", [{"id": 2}]),
        ([{"name": "x"}, {"name": "y"}], 1, [{"name": "y", "_id": 1}]),
        ([{"name": "x"}], "5", []),
        # A null `id` is no id: the record is found by its position.
        ([{"id": None}, {"id": None}], "1", [{"id": None, "_id": 1}]),
        # Records with and without an `id` are all found by their position,
        # which never matches another record's `id`.
        (
            [{"id": 1, "name": "a"}, {"name": "b"}],
            "1",
            [{"name": "b", "_id": 1}],
        ),
        (
            [{"id": 1, "name": "a"}, {"name": "b"}],
            "0",
            [{"id": 1, "name": "a", "_id": 0}],
        ),
    ],
)
def test_http_list_data_source_only_record_id(
    data_fixture, body, only_record_id, expected
):
    service = create_http_get_service(data_fixture, returns_list=True)
    dispatch_context = FakeDispatchContext(only_record_id=only_record_id)

    with mock_http_get(body):
        result = service.get_type().dispatch(service, dispatch_context)

    assert result.data["results"] == expected


def test_http_list_data_source_prepare_record_ids():
    service_type = service_type_registry.get("http_get")

    assert service_type.prepare_record_ids([1, "abc", "", None, "2"]) == [
        1,
        "abc",
        "2",
    ]


def used(*path):
    """A property a page uses, as the service type extracts it."""

    return CoreHTTPDataSourceServiceType().extract_properties(None, list(path))[0]


@pytest.mark.django_db
def test_http_list_data_source_sanitize_keeps_position(data_fixture):
    service = create_http_get_service(data_fixture, returns_list=True)
    result = {
        "results": [{"name": "a", "secret": "s", "_id": 0}],
        "has_next_page": False,
    }

    assert service.get_type().sanitize_result(service, result, [used("name")]) == {
        "results": [{"name": "a", "_id": 0}],
        "has_next_page": False,
    }


@pytest.mark.django_db
def test_http_data_source_sanitize_keeps_only_the_used_paths(data_fixture):
    service = create_http_get_service(data_fixture)
    service_type = service.get_type()
    body = {
        "user": {"name": "Ada", "ssn": "123", "tags": [{"a": 1, "b": 2}, {"a": 3}]},
        "items": [{"name": "x", "secret": 1}, {"name": "y", "secret": 2}],
        "a.b": {"c": 1, "d": 2},
    }

    assert service_type.sanitize_result(service, body, [used("user", "name")]) == {
        "user": {"name": "Ada"}
    }
    assert service_type.sanitize_result(
        service, body, [used("user", "tags", "*", "a"), used("items", "1", "name")]
    ) == {
        "user": {"tags": [{"a": 1}, {"a": 3}]},
        "items": [None, {"name": "y"}],
    }
    # A key of a list's items reads it in every item, the way a repeat over the
    # list does.
    assert service_type.sanitize_result(service, body, [used("items", "name")]) == {
        "items": [{"name": "x"}, {"name": "y"}]
    }
    assert service_type.sanitize_result(service, body, [used("a.b", "c")]) == {
        "a.b": {"c": 1}
    }
    # An element's own property names are a single key, whole.
    assert service_type.sanitize_result(service, body, ["user"]) == {
        "user": body["user"]
    }
    assert service_type.sanitize_result(service, body, [used()]) == body
    assert service_type.sanitize_result(service, body, []) == {}


@pytest.mark.django_db
def test_http_data_source_sanitize_non_object_body(data_fixture):
    service = create_http_get_service(data_fixture)
    service_type = service.get_type()

    assert service_type.sanitize_result(
        service, [{"a": 1, "b": 2}, {"secret": 2}], [used("0", "a")]
    ) == [{"a": 1}, None]
    assert service_type.sanitize_result(
        service, [{"a": 1, "b": 2}, {"a": 3}], [used("*", "a")]
    ) == [{"a": 1}, {"a": 3}]
    assert service_type.sanitize_result(service, [1, 2], []) == [None, None]
    assert service_type.sanitize_result(service, "text", [used()]) == "text"
    assert service_type.sanitize_result(service, "text", [used("x")]) is None
    assert service_type.sanitize_result(service, "text", []) is None
    assert service_type.sanitize_result(service, None, [used("x")]) is None


def create_public_page(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    builder_to = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(builder=builder, published_to=builder_to)
    return data_fixture.create_builder_page(builder=builder_to)


def public_dispatch(api_client, page, body):
    url = reverse(
        "api:builder:domains:public_dispatch_all", kwargs={"page_id": page.id}
    )
    with mock_http_get(body):
        response = api_client.post(url, {}, format="json")
    assert response.status_code == HTTP_200_OK, response.json()
    return response.json()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path,body,expected",
    [
        # Only the used value of an object, not the object.
        (
            ".user.name",
            {"user": {"name": "Ada", "ssn": "123"}, "internal": {"note": "x"}},
            {"user": {"name": "Ada"}},
        ),
        # Every item of a list with `[All]`, with only the used value.
        (
            ".*.name",
            [{"name": "a", "secret": 1}, {"name": "b", "secret": 2}],
            [{"name": "a"}, {"name": "b"}],
        ),
        (
            ".data.*.name",
            {"data": [{"name": "a", "secret": 1}], "token": "x"},
            {"data": [{"name": "a"}]},
        ),
        # The whole body when the page uses the whole body.
        ("", 42, 42),
    ],
)
def test_public_dispatch_http_data_source_only_sends_the_used_values(
    api_client, data_fixture, path, body, expected
):
    page = create_public_page(data_fixture)
    data_source = data_fixture.create_builder_data_source(
        page=page, service=create_http_get_service(data_fixture)
    )
    data_fixture.create_builder_heading_element(
        page=page, value=f"get('data_source.{data_source.id}{path}')"
    )

    assert public_dispatch(api_client, page, body) == {str(data_source.id): expected}


@pytest.mark.django_db
def test_public_dispatch_http_list_data_source_only_sends_the_used_values(
    api_client, data_fixture
):
    page = create_public_page(data_fixture)
    data_source = data_fixture.create_builder_data_source(
        page=page,
        service=create_http_get_service(
            data_fixture, returns_list=True, list_path="data"
        ),
    )
    data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source,
        fields=[
            {
                "name": "Owner",
                "type": "text",
                "config": {"value": "get('current_record.owner.name')"},
            },
        ],
    )
    body = {
        "data": [
            {"owner": {"name": "Ada", "email": "ada@x"}, "secret": 1},
            {"owner": {"name": "Bob", "email": "bob@x"}, "secret": 2},
        ],
        "token": "x",
    }

    assert public_dispatch(api_client, page, body) == {
        str(data_source.id): {
            "results": [
                {"owner": {"name": "Ada"}, "_id": 0},
                {"owner": {"name": "Bob"}, "_id": 1},
            ],
            "has_next_page": False,
        }
    }


@pytest.mark.django_db
def test_http_data_source_generate_schema(data_fixture):
    service = create_http_get_service(data_fixture)
    service_type = service.get_type()

    assert service_type.generate_schema(service) is None

    service.sample_data = {"_error": "boom"}
    assert service_type.generate_schema(service) is None

    service.sample_data = {"data": {"name": "Ada", "age": 36, "tags": ["a"]}}
    schema = service_type.generate_schema(service)
    assert schema == {
        "title": f"HTTPDataSource{service.id}Schema",
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["age", "name", "tags"],
    }

    assert set(
        service_type.generate_schema(service, allowed_fields=["name"])["properties"]
    ) == {"name"}
    assert set(
        service_type.generate_schema(
            service, allowed_fields=[used("tags", "0"), used("name")]
        )["properties"]
    ) == {"name", "tags"}
    assert (
        len(
            service_type.generate_schema(service, allowed_fields=[used()])["properties"]
        )
        == 3
    )


@pytest.mark.django_db
def test_http_list_data_source_generate_schema(data_fixture):
    service = create_http_get_service(data_fixture, returns_list=True)
    service_type = service.get_type()

    assert service_type.generate_schema(service) is None

    service.sample_data = {"data": {"results": [], "has_next_page": False}}
    assert service_type.generate_schema(service) is None

    service.sample_data = {
        "data": {
            "results": [{"name": "a", "_id": 0}, {"name": "b", "extra": 1, "_id": 1}],
            "has_next_page": False,
        }
    }
    schema = service_type.generate_schema(service)
    assert schema["title"] == f"HTTPDataSource{service.id}Schema"
    assert schema["type"] == "array"
    assert set(schema["items"]["properties"]) == {"name", "extra", "_id"}


@pytest.mark.django_db
def test_http_data_source_default_timeout_on_create(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    data_source = DataSourceService().create_data_source(
        user, page=page, service_type=service_type_registry.get("http_get")
    )

    assert data_source.service.specific.timeout == HTTP_DATA_SOURCE_TIMEOUT_DEFAULT


@pytest.mark.django_db
def test_http_data_source_switch_to_list_keeps_the_service(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    data_source = DataSourceService().create_data_source(
        user,
        page=page,
        service_type=service_type_registry.get("http_get"),
        url={"formula": "'https://example.notexist'"},
        headers=[{"key": "x-key", "value": "'1'"}],
        timeout=20,
    )
    service_type = data_source.service.get_type()
    service_id = data_source.service_id

    updated = DataSourceService().update_data_source(
        user,
        data_source,
        service_type=service_type,
        returns_list=True,
        list_path="items",
    )

    service = updated.data_source.service.specific
    assert service.id == service_id
    assert service.get_type().type == "http_get"
    assert service.returns_list is True
    assert service.url["formula"] == "'https://example.notexist'"
    assert service.timeout == 20
    assert service.list_path == "items"
    assert [(h.key, h.value["formula"]) for h in service.headers.all()] == [
        ("x-key", "'1'")
    ]


def test_sample_data_skeleton():
    assert sample_data_skeleton(
        {
            "name": "Ada",
            "age": 36,
            "score": 1.5,
            "active": True,
            "nothing": None,
            "tags": ["a", "b"],
            "items": [
                {"id": 1, "label": "x"},
                {"id": 2, "extra": {"deep": "y"}},
            ],
            "empty": [],
        }
    ) == {
        "name": "",
        "age": 0,
        "score": 0,
        "active": False,
        "nothing": None,
        "tags": [""],
        "items": [{"id": 0, "label": "", "extra": {"deep": ""}}],
        "empty": [],
    }
    assert sample_data_skeleton([[{"a": 1}], [{"b": "x"}]]) == [[{"a": 0, "b": ""}]]
    assert sample_data_skeleton([None, {"a": 1}]) == [{"a": 0}]


@pytest.mark.django_db
def test_http_data_source_export_skeleton_vs_publish(data_fixture):
    service = create_http_get_service(data_fixture)
    HTTPHeader.objects.create(service=service, key="Authorization", value="'Bearer x'")
    service.sample_data = {
        "data": {"name": "Ada", "items": [{"id": 3}]},
        "status": 200,
        "output_uid": "",
    }
    service.save()
    service_type = service.get_type()

    external = service_type.export_serialized(
        service, import_export_config=ImportExportConfig(include_permission_data=False)
    )
    assert external["sample_data"] == {
        "data": {"name": "", "items": [{"id": 0}]},
        "status": 200,
        "output_uid": "",
    }
    assert external["headers"] == [{"key": "Authorization", "value": None}]

    published = service_type.export_serialized(
        service,
        import_export_config=ImportExportConfig(
            include_permission_data=True, exclude_sensitive_data=False
        ),
    )
    assert published["sample_data"] == service.sample_data
    assert published["headers"][0]["value"]["formula"] == "'Bearer x'"

    # A stored failure is no shape at all.
    service.sample_data = {"_error": "boom"}
    service.save()
    assert (
        service_type.export_serialized(
            service,
            import_export_config=ImportExportConfig(include_permission_data=False),
        )["sample_data"]
        is None
    )


@pytest.mark.django_db(transaction=True)
def test_public_dispatch_sends_http_requests_outside_a_transaction(
    api_client, data_fixture
):
    # A transactional test: anything else runs the test in a transaction.
    page = create_public_page(data_fixture)
    data_sources = [
        data_fixture.create_builder_data_source(
            page=page, service=create_http_get_service(data_fixture, timeout=7)
        )
        for _ in range(2)
    ]
    for data_source in data_sources:
        data_fixture.create_builder_heading_element(
            page=page, value=f"get('data_source.{data_source.id}.name')"
        )

    response = Mock()
    response.status_code = 200
    response.headers = {"Content-Type": "application/json"}
    response.json.return_value = {"name": "Ada"}
    sends = []

    def send(**kwargs):
        sends.append((connection.in_atomic_block, kwargs["deadline"] - 1000))
        return response

    url = reverse(
        "api:builder:domains:public_dispatch_all", kwargs={"page_id": page.id}
    )
    with (
        patch(
            "baserow.contrib.integrations.core.service_types.send_http_request",
            side_effect=send,
        ),
        patch("time.monotonic", return_value=1000),
    ):
        result = api_client.post(url, {}, format="json")

    assert result.status_code == HTTP_200_OK, result.json()
    assert result.json() == {
        str(data_source.id): {"name": "Ada"} for data_source in data_sources
    }
    # Each waits for at most its own timeout, holding no transaction open.
    assert sends == [(False, 7), (False, 7)]


@pytest.mark.django_db
def test_only_sensitive_sample_data_is_emptied_on_export(data_fixture):
    # The sample data of an automation's nodes is what simulates them, which
    # its templates rely on.
    action = data_fixture.create_service(
        CoreHTTPRequestService,
        url="'https://example.notexist'",
        sample_data={"data": {"body": {"id": 13}, "status_code": 200}},
    )
    router = data_fixture.create_service(
        CoreRouterService,
        sample_data={"data": {"edge": {"label": "Urgent"}}, "output_uid": "abc"},
    )
    config = ImportExportConfig(include_permission_data=False)

    for service in [action, router]:
        exported = service.get_type().export_serialized(
            service, import_export_config=config
        )
        assert exported["sample_data"] == service.sample_data


@pytest.mark.django_db
def test_http_data_source_import_keeps_skeleton_schema(data_fixture):
    service = create_http_get_service(data_fixture, returns_list=True)
    service.sample_data = {
        "data": {
            "results": [{"id": 1, "name": "a"}, {"id": 2, "city": "b"}],
            "has_next_page": False,
        }
    }
    service.save()
    service_type = service.get_type()

    serialized = service_type.export_serialized(
        service, import_export_config=ImportExportConfig(include_permission_data=False)
    )
    imported = service_type.import_serialized(
        None, serialized, {}, import_export_config=None
    )

    schema = service_type.generate_schema(imported)
    assert set(schema["items"]["properties"]) == {"id", "name", "city"}


@pytest.mark.django_db
def test_simulate_dispatch_http_get_data_source(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source = DataSourceService().create_data_source(
        user,
        page=page,
        service_type=service_type_registry.get("http_get"),
        url={"formula": "'https://example.notexist/me'"},
    )

    url = reverse(
        "api:builder:data_source:simulate-dispatch",
        kwargs={"data_source_id": data_source.id},
    )

    with mock_http_get({"name": "Ada", "age": 36}) as mock_request:
        response = api_client.post(
            url, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
        )

    assert response.status_code == HTTP_200_OK
    assert mock_request.call_args.kwargs["method"] == HTTP_METHOD.GET
    response_json = response.json()
    assert response_json["type"] == "http_get"
    assert response_json["sample_data"]["data"] == {"name": "Ada", "age": 36}
    assert set(response_json["schema"]["properties"]) == {"name", "age"}

    # A failed test keeps the last good sample.
    with mock_http_get({"error": "nope"}, status_code=404):
        response = api_client.post(
            url, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
        )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SERVICE_IMPROPERLY_CONFIGURED"
    assert "404" in response.json()["detail"]
    service = DataSourceHandler().get_data_source(data_source.id).service.specific
    assert service.sample_data["data"] == {"name": "Ada", "age": 36}


@pytest.mark.django_db
def test_simulate_dispatch_http_list_data_source_keeps_response(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source = DataSourceService().create_data_source(
        user,
        page=page,
        service_type=service_type_registry.get("http_get"),
        url={"formula": "'https://example.notexist/items'"},
        returns_list=True,
        list_path="data.items",
    )
    body = {
        "data": {
            "items": [{"id": index, "tags": ["a", "b", "c", "d"]} for index in range(5)]
        },
        "total": 5,
    }

    url = reverse(
        "api:builder:data_source:simulate-dispatch",
        kwargs={"data_source_id": data_source.id},
    )
    with mock_http_get(body):
        response = api_client.post(
            url, {}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
        )

    assert response.status_code == HTTP_200_OK, response.json()
    sample = response.json()["sample_data"]["data"]
    assert [record["id"] for record in sample["results"]] == [0, 1, 2, 3, 4]
    # The response keeps the first items of each of its lists, to choose
    # another list in it.
    assert sample["response"] == {
        "data": {
            "items": [{"id": index, "tags": ["a", "b", "c"]} for index in range(3)]
        },
        "total": 5,
    }
    assert set(response.json()["schema"]["items"]["properties"]) == {"id", "tags"}

    # An export without the sensitive data only keeps the shape of it.
    service = DataSourceHandler().get_data_source(data_source.id).service.specific
    skeleton = service.get_type().sample_data_skeleton(service.sample_data)
    assert skeleton["data"]["response"] == {
        "data": {"items": [{"id": 0, "tags": [""]}]},
        "total": 0,
    }

    # Only a test keeps the response.
    with mock_http_get(body):
        result = service.get_type().dispatch(service, FakeDispatchContext())
    assert "response" not in result.data


@pytest.mark.django_db
def test_switching_http_data_source_to_a_list_keeps_the_tested_response(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source = DataSourceService().create_data_source(
        user,
        page=page,
        service_type=service_type_registry.get("http_get"),
        url={"formula": "'https://example.notexist/items'"},
    )
    body = {"data": {"items": [{"name": f"item {i}"} for i in range(4)]}}
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    item_url = reverse(
        "api:builder:data_source:item", kwargs={"data_source_id": data_source.id}
    )

    with mock_http_get(body):
        api_client.post(
            reverse(
                "api:builder:data_source:simulate-dispatch",
                kwargs={"data_source_id": data_source.id},
            ),
            {},
            format="json",
            **headers,
        )

    # The list reads its records from the response the single record was tested
    # with, without a request.
    with mock_http_get(body) as mock_request:
        response = api_client.patch(
            item_url,
            {"returns_list": True, "list_path": "data.items"},
            format="json",
            **headers,
        )
    mock_request.assert_not_called()

    assert response.status_code == HTTP_200_OK, response.json()
    sample = response.json()["sample_data"]
    assert sample["status"] == 200
    assert sample["data"]["results"] == [
        {"name": f"item {i}", "_id": i} for i in range(4)
    ]
    assert sample["data"]["has_next_page"] is False
    assert sample["data"]["response"] == {"data": {"items": body["data"]["items"][:3]}}
    assert set(response.json()["schema"]["items"]["properties"]) == {"name", "_id"}

    # The single record gets the response the list kept.
    response = api_client.patch(
        item_url, {"returns_list": False}, format="json", **headers
    )
    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["sample_data"]["data"] == {
        "data": {"items": body["data"]["items"][:3]}
    }
    assert set(response.json()["schema"]["properties"]) == {"data"}

    # A list path which isn't in the response needs a test.
    response = api_client.patch(
        item_url,
        {"returns_list": True, "list_path": "nope"},
        format="json",
        **headers,
    )
    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["sample_data"] is None
    assert response.json()["schema"] is None


@pytest.mark.django_db
def test_changing_http_list_path_reads_the_tested_response_again(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source = DataSourceService().create_data_source(
        user,
        page=page,
        service_type=service_type_registry.get("http_get"),
        url={"formula": "'https://example.notexist/items'"},
        returns_list=True,
        list_path="results",
    )
    body = {"results": [{"id": 1, "jobs": [{"id": 3, "value": "Architect"}]}]}
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    item_url = reverse(
        "api:builder:data_source:item", kwargs={"data_source_id": data_source.id}
    )

    with mock_http_get(body):
        api_client.post(
            reverse(
                "api:builder:data_source:simulate-dispatch",
                kwargs={"data_source_id": data_source.id},
            ),
            {},
            format="json",
            **headers,
        )

    with mock_http_get(body) as mock_request:
        response = api_client.patch(
            item_url, {"list_path": "results.0.jobs"}, format="json", **headers
        )
    mock_request.assert_not_called()

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["sample_data"]["data"]["results"] == [
        {"id": 3, "value": "Architect"}
    ]
    assert set(response.json()["schema"]["items"]["properties"]) == {"id", "value"}

    # Other changes keep the sample data.
    response = api_client.patch(item_url, {"timeout": 5}, format="json", **headers)
    assert response.json()["sample_data"]["data"]["results"] == [
        {"id": 3, "value": "Architect"}
    ]

    # A list path which isn't in the response needs a test.
    response = api_client.patch(
        item_url, {"list_path": "nope"}, format="json", **headers
    )
    assert response.json()["sample_data"] is None
    assert response.json()["schema"] is None

    # So does a sample data kept before the response was.
    service = DataSourceHandler().get_data_source(data_source.id).service.specific
    service.list_path = "results"
    service.sample_data = {"data": {"results": body["results"]}, "status": 200}
    service.save()
    response = api_client.patch(
        item_url, {"list_path": "results.0.jobs"}, format="json", **headers
    )
    assert response.json()["sample_data"] is None


@pytest.mark.django_db
def test_update_http_data_source_returns_list_through_api_keeps_values(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)
    data_source = DataSourceService().create_data_source(
        user,
        page=page,
        service_type=service_type_registry.get("http_get"),
        url={"formula": "'https://example.notexist'"},
    )
    url = reverse(
        "api:builder:data_source:item", kwargs={"data_source_id": data_source.id}
    )

    # The toggle sends the values of the form along with the shape.
    response = api_client.patch(
        url,
        {
            "returns_list": True,
            "url": {"formula": "'https://example.notexist'"},
            "headers": [{"key": "x-key", "value": {"formula": "'1'"}}],
            "query_params": [],
            "timeout": 12,
            "list_path": "data.items",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert response_json["type"] == "http_get"
    assert response_json["returns_list"] is True
    assert response_json["list_path"] == "data.items"
    assert response_json["timeout"] == 12
    assert response_json["url"]["formula"] == "'https://example.notexist'"
    assert [header["key"] for header in response_json["headers"]] == ["x-key"]

    response = api_client.patch(
        url,
        {
            "returns_list": False,
            "url": {"formula": "'https://example.notexist'"},
            "headers": [],
            "query_params": [],
            "timeout": 12,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["returns_list"] is False
    assert response.json()["headers"] == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "failure,exception",
    [
        (UnacceptableAddressException(), AddressNotAllowedDispatchException),
        (ConnectionError(), RuntimeDispatchException),
        (
            request_exceptions.ConnectionError(
                "HTTPSConnectionPool(host='example.notexist'): Max retries "
                "exceeded with url: /items?api_key=secret"
            ),
            RuntimeDispatchException,
        ),
        (
            ValueError("https://example.notexist/items?api_key=secret"),
            UnexpectedDispatchException,
        ),
    ],
)
def test_http_data_source_errors_name_no_address(data_fixture, failure, exception):
    # A data source's error reaches the visitors of a published page.
    service = create_http_get_service(
        data_fixture, url="'https://example.notexist/items?api_key=secret'"
    )

    with mock_http_get(raise_exception=failure):
        with pytest.raises(exception) as raised:
            service.get_type().dispatch(service, FakeDispatchContext())

    assert "example.notexist" not in str(raised.value)
    assert "secret" not in str(raised.value)
