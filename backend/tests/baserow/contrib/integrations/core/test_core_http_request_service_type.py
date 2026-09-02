import json
from contextlib import contextmanager
from unittest.mock import MagicMock, Mock, patch

import pytest
from requests import exceptions as request_exceptions

from baserow.contrib.integrations.core.models import BODY_TYPE, HTTP_METHOD
from baserow.contrib.integrations.core.service_types import CoreHTTPRequestServiceType
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.test_utils.helpers import AnyInt, AnyStr
from baserow.test_utils.pytest_conftest import FakeDispatchContext


# Custom context manager
@contextmanager
def mock_advocate_request(
    body=None, headers=None, status_code=200, raise_exception=None
):
    if headers is None:
        headers = {}

    # Create a mock response
    mock_response = Mock()
    if body is not None:
        if isinstance(body, str):
            mock_response.text = body
            mock_response.json.side_effect = request_exceptions.JSONDecodeError(
                "mocked json error", "", 0
            )
            headers = headers or {"Content-Type": "text/plain"}
        else:
            mock_response.text = str(body)
            mock_response.json.return_value = body
            headers = headers or {"Content-Type": "application/json"}

    mock_response.headers = headers
    mock_response.status_code = status_code
    # The service streams the body in so it can stop an endpoint that
    # sends more than this installation accepts.
    mock_response.iter_content.return_value = iter(
        [str(mock_response.text or "").encode()]
    )

    # Use the patch context manager to mock `advocate.request`
    with patch("advocate.request", return_value=mock_response) as mock_request:

        def side_effect(*args, **kwargs):
            if raise_exception is not None:
                raise raise_exception
            return mock_response

        mock_request.side_effect = side_effect
        yield mock_request


@pytest.mark.django_db
def test_core_http_request_basic(
    data_fixture,
):
    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'", timeout=15, http_method=HTTP_METHOD.POST
    )
    service_type = service.get_type()

    dispatch_context = FakeDispatchContext()

    # Use the patch context manager to mock `advocate.request`
    with mock_advocate_request(
        {"raw_body": "body"}, status_code=204, headers={"test": "header"}
    ) as mock_request:
        dispatch_data = service_type.dispatch(service, dispatch_context)

        mock_request.assert_called_once_with(
            **{
                "headers": {"user-agent": AnyStr()},
                "method": HTTP_METHOD.POST,
                "params": {},
                "timeout": 15,
                "stream": True,
                "url": "http://example.notexist/",
            }
        )

    assert dispatch_data.data == {
        "body": {
            "raw_body": "body",
        },
        "raw_body": '{"raw_body": "body"}',
        "headers": {"test": "header"},
        "status_code": 204,
    }


@pytest.mark.django_db
def test_core_http_request_request_error(
    data_fixture,
):
    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'", timeout=15, http_method=HTTP_METHOD.POST
    )
    service_type = service.get_type()

    dispatch_context = FakeDispatchContext()

    # Use the patch context manager to mock `advocate.request`
    from requests.exceptions import InvalidHeader

    with pytest.raises(UnexpectedDispatchException):
        with mock_advocate_request(raise_exception=InvalidHeader()):
            service_type.dispatch(service, dispatch_context)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "timeout_exception",
    [
        request_exceptions.ReadTimeout(),
        request_exceptions.ConnectTimeout(),
        request_exceptions.Timeout(),
    ],
)
def test_core_http_request_timeout_returns_504(data_fixture, timeout_exception):
    """
    When the request times out, instead of failing we return a 504
    status code so that the caller can decide the next step to take.
    """

    service = data_fixture.create_core_http_request_service(
        url="'http://foo.localhost/'", timeout=1, http_method=HTTP_METHOD.POST
    )
    service_type = service.get_type()

    dispatch_context = FakeDispatchContext()

    with mock_advocate_request(raise_exception=timeout_exception):
        dispatch_data = service_type.dispatch(service, dispatch_context)

    assert dispatch_data.data == {
        "raw_body": "",
        "body": "",
        "headers": {},
        "status_code": 504,
    }


@pytest.mark.django_db
def test_core_http_request_basic_body_raw(
    data_fixture,
):
    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'",
        body_content="'test'",
        body_type=BODY_TYPE.RAW,
    )
    service_type = service.get_type()

    dispatch_context = FakeDispatchContext()

    # Use the patch context manager to mock `advocate.request`
    with mock_advocate_request({"foo": "bar"}) as mock_request:
        service_type.dispatch(service, dispatch_context)

        mock_request.assert_called_once_with(
            **{
                "headers": {"user-agent": AnyStr()},
                "data": "test",
                "method": HTTP_METHOD.GET,
                "params": {},
                "timeout": 30,
                "stream": True,
                "url": "http://example.notexist/",
            }
        )


@pytest.mark.django_db
def test_core_http_request_basic_body_json(
    data_fixture,
):
    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'",
        body_content="""'{"test": "2"}'""",
        body_type=BODY_TYPE.JSON,
    )
    service_type = service.get_type()

    dispatch_context = FakeDispatchContext()

    # Use the patch context manager to mock `advocate.request`
    with mock_advocate_request({"foo": "bar"}) as mock_request:
        service_type.dispatch(service, dispatch_context)

        mock_request.assert_called_once_with(
            **{
                "headers": {"user-agent": AnyStr()},
                "json": {"test": "2"},
                "method": HTTP_METHOD.GET,
                "params": {},
                "timeout": 30,
                "stream": True,
                "url": "http://example.notexist/",
            }
        )


@pytest.mark.django_db
def test_core_http_request_body_json_invalid_static_body(data_fixture):
    """
    A static body that isn't valid JSON should fail with the plain error
    message, without the extra hint.
    """

    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'",
        # `{"value1": }` is missing a value, so it's invalid JSON.
        body_content="""'{"value1": }'""",
        body_type=BODY_TYPE.JSON,
    )
    service_type = service.get_type()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        service_type.dispatch(service, FakeDispatchContext())

    assert str(exc.value) == "The body is not a valid JSON"


@pytest.mark.django_db
def test_core_http_request_body_json_invalid_with_data_provider_hint(data_fixture):
    """
    When the body interpolates a formula value without `to_json(...)` and
    the result isn't valid JSON, the error should hint at wrapping the value.
    """

    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'",
        # The value isn't wrapped in quotes/`to_json`, so a string value
        # produces invalid JSON, e.g. `{"value1": hello}`.
        body_content="""concat('{"value1": ', get('page_parameter.id'), '}')""",
        body_type=BODY_TYPE.JSON,
    )
    service_type = service.get_type()
    dispatch_context = FakeDispatchContext(context={"page_parameter": {"id": "hello"}})

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        service_type.dispatch(service, dispatch_context)

    assert "The body is not a valid JSON" in str(exc.value)
    assert "to_json(" in str(exc.value)


@pytest.mark.django_db
def test_core_http_request_body_json_invalid_with_formula_function_hint(data_fixture):
    """
    The hint should also be shown for formula functions as well (e.g. `now()`).
    """

    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'",
        # `now()` produces an unquoted value, e.g. `{"id":  2026-06-22 03:52:07.130000+00:00}`.
        body_content="""concat('{"id": ', now(), '}')""",
        body_type=BODY_TYPE.JSON,
    )
    service_type = service.get_type()

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        service_type.dispatch(service, FakeDispatchContext())

    assert "The body is not a valid JSON" in str(exc.value)
    assert "wrap it with to_json()" in str(exc.value)


@pytest.mark.django_db
def test_core_http_request_body_json_with_to_json_escapes_data_source(data_fixture):
    """
    Wrapping a data source value with `to_json(...)` produces a valid JSON body
    even when the value contains characters that would otherwise break it.
    """

    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'",
        body_content=(
            """concat('{"value1": ', to_json(get('page_parameter.id')), '}')"""
        ),
        body_type=BODY_TYPE.JSON,
    )
    service_type = service.get_type()
    dispatch_context = FakeDispatchContext(
        context={"page_parameter": {"id": 'foo "bar"'}}
    )

    with mock_advocate_request({"foo": "bar"}) as mock_request:
        service_type.dispatch(service, dispatch_context)

        mock_request.assert_called_once_with(
            **{
                "headers": {"user-agent": AnyStr()},
                "json": {"value1": 'foo "bar"'},
                "method": HTTP_METHOD.GET,
                "params": {},
                "timeout": 30,
                "stream": True,
                "url": "http://example.notexist/",
            }
        )


@pytest.mark.django_db
@pytest.mark.parametrize("control_char", ["\n", "\t", "\r"])
def test_core_http_request_basic_body_json_with_control_characters(
    data_fixture, control_char
):
    """
    Raw control characters (e.g. newlines, tabs) inside JSON string values
    should be accepted. The body can be the resolved output of a formula, so
    such characters are legitimate content and shouldn't fail the request.
    """

    value = f"line1{control_char}line2"
    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'",
        # A *raw* control character inside the JSON string (not an escaped
        # `\n` sequence), which `json.loads` rejects unless `strict=False`.
        body_content="'" + f'{{"test": "{value}"}}' + "'",
        body_type=BODY_TYPE.JSON,
    )
    service_type = service.get_type()

    dispatch_context = FakeDispatchContext()

    # Use the patch context manager to mock `advocate.request`
    with mock_advocate_request({"foo": "bar"}) as mock_request:
        service_type.dispatch(service, dispatch_context)

        mock_request.assert_called_once_with(
            **{
                "headers": {"user-agent": AnyStr()},
                "json": {"test": value},
                "method": HTTP_METHOD.GET,
                "params": {},
                "timeout": 30,
                "stream": True,
                "url": "http://example.notexist/",
            }
        )


@pytest.mark.django_db
def test_core_http_request_with_formulas(
    data_fixture,
):
    service = data_fixture.create_core_http_request_service(
        url="concat('http://example.notexist/', get('page_parameter.id'))",
        body_content="""concat('{"test":"', get('page_parameter.id'), '"}')""",
        body_type=BODY_TYPE.JSON,
    )
    service_type = service.get_type()

    formula_context = {"page_parameter": {"id": 2}}
    dispatch_context = FakeDispatchContext(context=formula_context)

    # Use the patch context manager to mock `advocate.request`
    with mock_advocate_request({"foo": "bar"}) as mock_request:
        service_type.dispatch(service, dispatch_context)

        mock_request.assert_called_once_with(
            **{
                "headers": {"user-agent": AnyStr()},
                "json": {"test": "2"},
                "method": HTTP_METHOD.GET,
                "params": {},
                "timeout": 30,
                "stream": True,
                "url": "http://example.notexist/2",
            }
        )


@pytest.mark.django_db
def test_core_http_request_with_headers(
    data_fixture,
):
    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'",
    )
    service_type = service.get_type()

    service.headers.create(
        key="test", value="""concat('test__', get('page_parameter.id'))"""
    )
    service.headers.create(key="test2", value="""'value'""")

    formula_context = {"page_parameter": {"id": 2}}
    dispatch_context = FakeDispatchContext(context=formula_context)

    # Use the patch context manager to mock `advocate.request`
    with mock_advocate_request({"foo": "bar"}) as mock_request:
        service_type.dispatch(service, dispatch_context)

        mock_request.assert_called_once_with(
            **{
                "headers": {
                    "test": "test__2",
                    "test2": "value",
                    "user-agent": AnyStr(),
                },
                "method": HTTP_METHOD.GET,
                "params": {},
                "timeout": 30,
                "stream": True,
                "url": "http://example.notexist/",
            }
        )


@pytest.mark.django_db
def test_core_http_request_with_query_params(
    data_fixture,
):
    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'",
    )
    service_type = service.get_type()

    service.query_params.create(
        key="test", value="concat('test__', get('page_parameter.id'))"
    )
    service.query_params.create(key="test2", value="'value'")

    formula_context = {"page_parameter": {"id": 2}}
    dispatch_context = FakeDispatchContext(context=formula_context)

    # Use the patch context manager to mock `advocate.request`
    with mock_advocate_request({"foo": "bar"}) as mock_request:
        service_type.dispatch(service, dispatch_context)

        mock_request.assert_called_once_with(
            **{
                "headers": {"user-agent": AnyStr()},
                "method": HTTP_METHOD.GET,
                "params": {"test": "test__2", "test2": "value"},
                "timeout": 30,
                "stream": True,
                "url": "http://example.notexist/",
            }
        )


@pytest.mark.django_db
def test_core_http_request_with_form_data(
    data_fixture,
):
    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'", body_type=BODY_TYPE.FORM
    )
    service_type = service.get_type()

    service.form_data.create(
        key="test", value="""concat('test__', get('page_parameter.id'))"""
    )
    service.form_data.create(key="test2", value="""'value'""")

    formula_context = {"page_parameter": {"id": 2}}
    dispatch_context = FakeDispatchContext(context=formula_context)

    # Use the patch context manager to mock `advocate.request`
    with mock_advocate_request({"foo": "bar"}) as mock_request:
        service_type.dispatch(service, dispatch_context)

        mock_request.assert_called_once_with(
            **{
                "headers": {"user-agent": AnyStr()},
                "method": HTTP_METHOD.GET,
                "data": {"test": "test__2", "test2": "value"},
                "params": {},
                "timeout": 30,
                "stream": True,
                "url": "http://example.notexist/",
            }
        )


@pytest.mark.django_db
def test_core_http_request_create(data_fixture):
    service = ServiceHandler().create_service(
        CoreHTTPRequestServiceType(),
        url="'http://example.com'",
        headers=[{"key": "key", "value": "'value'"}],
        query_params=[{"key": "key", "value": "'value'"}],
        form_data=[{"key": "key", "value": "'value'"}],
    )

    assert service.url["formula"] == "'http://example.com'"
    assert service.headers.count() == 1
    assert service.headers.first().key == "key"
    assert service.query_params.count() == 1
    assert service.query_params.first().key == "key"
    assert service.form_data.count() == 1
    assert service.form_data.first().key == "key"


@pytest.mark.django_db
def test_core_http_request_update(data_fixture):
    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'"
    )
    service_type = service.get_type()

    ServiceHandler().update_service(
        service_type,
        service,
        url="'http://another.url'",
        headers=[{"key": "key", "value": "'value'"}],
        query_params=[{"key": "key", "value": "'value'"}],
        form_data=[{"key": "key", "value": "'value'"}],
    )

    service.refresh_from_db()

    assert service.url["formula"] == "'http://another.url'"
    assert service.headers.count() == 1
    assert service.headers.first().key == "key"
    assert service.query_params.count() == 1
    assert service.query_params.first().key == "key"
    assert service.form_data.count() == 1
    assert service.form_data.first().key == "key"


@pytest.mark.django_db
def test_core_http_request_formula_generator():
    service = ServiceHandler().create_service(
        CoreHTTPRequestServiceType(),
        url="'http://example.com'",
        body_content="'body'",
        headers=[{"key": "key", "value": "'value1'"}],
        query_params=[{"key": "key", "value": "'value2'"}],
        form_data=[{"key": "key", "value": "'value3'"}],
    )
    service_type = service.get_type()

    formulas = list(service_type.formula_generator(service))
    assert formulas == [
        {"mode": "simple", "version": "0.1", "formula": "'body'"},
        {"mode": "simple", "version": "0.1", "formula": "'http://example.com'"},
        {"mode": "simple", "version": "0.1", "formula": "'value3'"},
        {"mode": "simple", "version": "0.1", "formula": "'value1'"},
        {"mode": "simple", "version": "0.1", "formula": "'value2'"},
    ]


@pytest.mark.django_db
def test_core_http_request_extract_properties(data_fixture):
    mock_service = MagicMock()

    assert CoreHTTPRequestServiceType().extract_properties(
        mock_service, ["headers", "content_type"]
    ) == ["headers"]

    assert CoreHTTPRequestServiceType().extract_properties(mock_service, []) == []


@pytest.mark.django_db
def test_core_http_request_export_import():
    service = ServiceHandler().create_service(
        CoreHTTPRequestServiceType(),
        url="'http://example.com'",
        body_content="'body'",
        headers=[{"key": "key", "value": "'value1'"}],
        query_params=[{"key": "key", "value": "'value2'"}],
        form_data=[{"key": "key", "value": "'value3'"}],
    )

    service_type = service.get_type()

    serialized = json.loads(json.dumps(service_type.export_serialized(service)))

    assert serialized == {
        "id": AnyInt(),
        "integration_id": None,
        "type": "http_request",
        "http_method": "GET",
        "url": {"formula": "'http://example.com'", "version": "0.1", "mode": "simple"},
        "headers": [
            {
                "key": "key",
                "value": {"formula": "'value1'", "version": "0.1", "mode": "simple"},
            }
        ],
        "query_params": [
            {
                "key": "key",
                "value": {"formula": "'value2'", "version": "0.1", "mode": "simple"},
            }
        ],
        "form_data": [
            {
                "key": "key",
                "value": {"formula": "'value3'", "version": "0.1", "mode": "simple"},
            }
        ],
        "body_type": "none",
        "body_content": {"formula": "'body'", "version": "0.1", "mode": "simple"},
        "timeout": 30,
        "sample_data": None,
    }

    new_service = service_type.import_serialized(None, serialized, {}, lambda x, d: x)

    assert new_service.url["formula"] == "'http://example.com'"
    assert new_service.headers.count() == 1
    assert new_service.query_params.count() == 1
    assert new_service.form_data.count() == 1


@pytest.mark.django_db
def test_core_http_request_generate_schema():
    service = ServiceHandler().create_service(
        CoreHTTPRequestServiceType(),
        url="'http://example.com'",
        body_content="'body'",
        headers=[{"key": "key", "value": "'value1'"}],
        query_params=[{"key": "key", "value": "'value2'"}],
        form_data=[{"key": "key", "value": "'value3'"}],
    )

    service_type = service.get_type()
    schema_name = service_type.get_schema_name(service)

    assert service_type.generate_schema(service, []) == {
        "title": schema_name,
        "type": "object",
        "properties": {},
    }

    assert service_type.generate_schema(service, ["raw_body"]) == {
        "title": schema_name,
        "type": "object",
        "properties": {"raw_body": {"type": "string", "title": "Raw body"}},
    }

    assert service_type.generate_schema(
        service, ["raw_body", "headers", "status_code"]
    ) == {
        "title": schema_name,
        "type": "object",
        "properties": {
            "raw_body": {"type": "string", "title": "Raw body"},
            "headers": {
                "properties": {
                    "Content-Length": {
                        "description": "The length of the response body in octets (8-bit bytes)",
                        "type": "number",
                    },
                    "Content-Type": {
                        "description": "The MIME type of the response body",
                        "type": "string",
                    },
                    "ETag": {
                        "description": "An identifier for a specific version of a resource",
                        "type": "string",
                    },
                },
                "type": "object",
                "title": "Headers",
            },
            "status_code": {"title": "Status code", "type": "number"},
        },
    }
    assert service_type.generate_schema(
        service, ["raw_body", "headers", "status_code"]
    ) == service_type.generate_schema(service, None)


def get_raw_sample_data():
    sample_data = {
        "fighters": {
            "Ryu": {
                "power": "Hadogen",
                "country": "Japan",
            },
            "Guile": {"power": "Sonic boom", "country": "United States"},
            "Blanka": {"power": "Electric thunder", "country": "Brazil"},
        }
    }
    return json.dumps(sample_data)


@pytest.mark.django_db
def test_core_http_request_generate_schema_with_sample_data():
    api_response = get_raw_sample_data()
    service = ServiceHandler().create_service(
        CoreHTTPRequestServiceType(),
        url="'http://example.com'",
        headers=[{"key": "key", "value": "'value1'"}],
        query_params=[{"key": "key", "value": "'value2'"}],
        form_data=[{"key": "key", "value": "'value3'"}],
    )

    service.sample_data = {"data": {"body": json.loads(api_response)}}
    service.save()

    service_type = service.get_type()

    assert service_type.generate_schema(service)["properties"]["body"]["properties"][
        "fighters"
    ] == {
        "properties": {
            "Blanka": {
                "properties": {
                    "country": {"type": "string"},
                    "power": {"type": "string"},
                },
                "required": ["country", "power"],
                "type": "object",
            },
            "Guile": {
                "properties": {
                    "country": {"type": "string"},
                    "power": {"type": "string"},
                },
                "required": ["country", "power"],
                "type": "object",
            },
            "Ryu": {
                "properties": {
                    "country": {"type": "string"},
                    "power": {"type": "string"},
                },
                "required": ["country", "power"],
                "type": "object",
            },
        },
        "required": ["Blanka", "Guile", "Ryu"],
        "type": "object",
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "content_type",
    [
        "application/json",
        "text/html",
        "text/html; charset=UTF-8",
        "",
    ],
)
def test_core_http_request_dispatch_data_with_json(data_fixture, content_type):
    """
    If the response contains valid JSON, prefer to return the JSON instead of
    assuming it is a string.
    """

    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'", timeout=15, http_method=HTTP_METHOD.POST
    )

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    headers = {}
    if content_type is not None:
        headers["Content-Type"] = content_type

    # Use the patch context manager to mock `advocate.request`
    with mock_advocate_request(
        {"fighters": {"Ryu": {"power": "Hadogen"}}},
        status_code=204,
        headers=headers,
    ) as mock_request:
        dispatch_data = service_type.dispatch(service, dispatch_context)

        mock_request.assert_called_once_with(
            **{
                "headers": {"user-agent": AnyStr()},
                "method": HTTP_METHOD.POST,
                "params": {},
                "timeout": 15,
                "stream": True,
                "url": "http://example.notexist/",
            }
        )

    assert dispatch_data.data == {
        "body": {"fighters": {"Ryu": {"power": "Hadogen"}}},
        "raw_body": '{"fighters": {"Ryu": {"power": "Hadogen"}}}',
        "headers": headers,
        "status_code": 204,
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "content_type",
    [
        "text/html",
        "text/html; charset=UTF-8",
        "",
    ],
)
def test_core_http_request_dispatch_data_with_text(data_fixture, content_type):
    """
    If the response isn't valid JSON, ensure we return the raw response
    string instead.
    """

    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'", timeout=15, http_method=HTTP_METHOD.POST
    )
    service.sample_data = {"raw_body": "Hello world!"}
    service.save()

    service_type = service.get_type()
    dispatch_context = FakeDispatchContext()

    headers = {}
    if content_type is not None:
        headers["Content-Type"] = content_type

    # Use the patch context manager to mock `advocate.request`
    with mock_advocate_request(
        "Hello world!",
        status_code=204,
        headers=headers,
    ) as mock_request:
        dispatch_data = service_type.dispatch(service, dispatch_context)

        mock_request.assert_called_once_with(
            **{
                "headers": {"user-agent": AnyStr()},
                "method": HTTP_METHOD.POST,
                "params": {},
                "timeout": 15,
                "stream": True,
                "url": "http://example.notexist/",
            }
        )

    assert dispatch_data.data == {
        "body": "Hello world!",
        "raw_body": "Hello world!",
        "headers": headers,
        "status_code": 204,
    }


@pytest.mark.django_db
def test_a_response_bigger_than_the_ceiling_is_refused(data_fixture, settings):
    """
    The body is read in chunks so an endpoint cannot decide how much memory
    this worker spends. Buffering it whole and measuring afterwards is too
    late: a very large answer, or a small compressed one that unpacks into a
    large one, is already held by then.
    """

    settings.INTEGRATIONS_HTTP_MAX_RESPONSE_BYTES = 1024
    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'", timeout=15, http_method=HTTP_METHOD.GET
    )
    service_type = service.get_type()

    mock_response = Mock()
    mock_response.headers = {}
    mock_response.status_code = 200
    # More than the ceiling, handed over in chunks the way a real one arrives.
    mock_response.iter_content.return_value = iter([b"x" * 512] * 10)

    with patch("advocate.request", return_value=mock_response):
        with pytest.raises(ServiceImproperlyConfiguredDispatchException) as raised:
            service_type.dispatch(service, FakeDispatchContext())

    assert "larger than the 1024 bytes" in str(raised.value)
    # Hung up on rather than left running.
    mock_response.close.assert_called_once()


@pytest.mark.django_db
def test_a_response_within_the_ceiling_is_read_whole(data_fixture, settings):
    settings.INTEGRATIONS_HTTP_MAX_RESPONSE_BYTES = 1024
    service = data_fixture.create_core_http_request_service(
        url="'http://example.notexist/'", timeout=15, http_method=HTTP_METHOD.GET
    )
    service_type = service.get_type()

    with mock_advocate_request({"title": "small"}) as mock_request:
        dispatch_data = service_type.dispatch(service, FakeDispatchContext())

    assert mock_request.call_count == 1
    assert dispatch_data.data["body"] == {"title": "small"}
