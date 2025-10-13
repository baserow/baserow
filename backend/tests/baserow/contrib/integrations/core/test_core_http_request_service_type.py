import json
from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest
from requests import exceptions as request_exceptions

from baserow.contrib.integrations.core.models import BODY_TYPE, HTTP_METHOD
from baserow.contrib.integrations.core.service_types import CoreHTTPRequestServiceType
from baserow.core.services.exceptions import UnexpectedDispatchException
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
    assert CoreHTTPRequestServiceType().extract_properties(
        ["headers", "content_type"]
    ) == ["headers"]

    assert CoreHTTPRequestServiceType().extract_properties([]) == []


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
                "url": "http://example.notexist/",
            }
        )

    assert dispatch_data.data == {
        "body": "Hello world!",
        "raw_body": "Hello world!",
        "headers": headers,
        "status_code": 204,
    }
