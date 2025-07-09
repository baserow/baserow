import time
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.test import override_settings

import pytest
from freezegun import freeze_time
from rest_framework import serializers, status
from rest_framework.exceptions import APIException
from rest_framework.serializers import CharField
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from rest_framework.test import APIRequestFactory

from baserow.api.exceptions import QueryParameterValidationException
from baserow.api.registries import RegisteredException, api_exception_registry
from baserow.api.utils import (
    get_serializer_class,
    map_exceptions,
    validate_data,
    validate_data_custom_fields,
)
from baserow.contrib.database.api.views.utils import parse_limit_linked_items_params
from baserow.core.models import Workspace
from baserow.core.registry import (
    CustomFieldsInstanceMixin,
    Instance,
    ModelInstanceMixin,
    Registry,
)
from baserow.throttling import (
    BASEROW_CONCURRENCY_THROTTLE_REQUEST_ID,
    ConcurrentUserRequestsThrottle,
)


class TemporaryException(Exception):
    pass


class TemporaryException2(Exception):
    pass


class TemporarySubClassException(TemporaryException):
    pass


class TemporarySerializer(serializers.Serializer):
    field_1 = serializers.CharField()
    field_2 = serializers.ChoiceField(choices=("choice_1", "choice_2"))


class TemporaryListSerializer(serializers.ListSerializer):
    def __init__(self, *args, **kwargs):
        kwargs["child"] = TemporarySerializer()
        super().__init__(*args, **kwargs)


class TemporarySerializerWithList(serializers.Serializer):
    field_3 = serializers.IntegerField()
    field_4 = serializers.ListField(child=serializers.IntegerField())


class TemporaryInstance(CustomFieldsInstanceMixin, ModelInstanceMixin, Instance):
    pass


class TemporaryInstanceType1(TemporaryInstance):
    type = "temporary_1"
    model_class = Workspace


class TemporaryInstanceType2(TemporaryInstance):
    type = "temporary_2"
    model_class = Workspace
    serializer_field_names = ["name"]
    serializer_field_overrides = {"name": serializers.IntegerField()}


class TemporaryTypeRegistry(Registry):
    name = "temporary"


class TemporaryQueryParamSerializer(serializers.Serializer):
    field_5 = serializers.IntegerField(required=True)
    field_6 = serializers.CharField(max_length=20, required=False)


def test_map_exceptions_context_manager():
    with pytest.raises(APIException) as api_exception_1:
        with map_exceptions({TemporaryException: "ERROR_TEMPORARY"}):
            raise TemporaryException

    assert api_exception_1.value.detail["error"] == "ERROR_TEMPORARY"
    assert api_exception_1.value.detail["detail"] == ""
    assert api_exception_1.value.status_code == status.HTTP_400_BAD_REQUEST

    error_tuple = (
        "ERROR_TEMPORARY_2",
        HTTP_404_NOT_FOUND,
        "Another message {e.message}",
    )
    with pytest.raises(APIException) as api_exception_2:
        with map_exceptions({TemporaryException: error_tuple}):
            e = TemporaryException()
            e.message = "test"
            raise e

    assert api_exception_2.value.detail["error"] == "ERROR_TEMPORARY_2"
    assert api_exception_2.value.detail["detail"] == "Another message test"
    assert api_exception_2.value.status_code == status.HTTP_404_NOT_FOUND

    with pytest.raises(TemporaryException2):
        with map_exceptions({TemporaryException: "ERROR_TEMPORARY_3"}):
            raise TemporaryException2

    with map_exceptions({TemporaryException: "ERROR_TEMPORARY_4"}):
        pass

    # Can map to a callable which returns an error code
    with pytest.raises(APIException) as api_exception_3:
        with map_exceptions(
            {
                TemporaryException: lambda ex: "CONDITIONAL_ERROR"
                if "test" in str(ex)
                else None
            }
        ):
            raise TemporaryException("test")

    assert api_exception_3.value.detail["error"] == "CONDITIONAL_ERROR"

    # If the callable returns None the exception is rethrown
    with pytest.raises(TemporaryException):
        with map_exceptions(
            {
                TemporaryException: lambda ex: "CONDITIONAL_ERROR"
                if "test" in str(ex)
                else None
            }
        ):
            raise TemporaryException("not matching lambda")

    # Can map to a callable condition which can return a error tuple
    with pytest.raises(APIException) as api_exception_5:
        with map_exceptions(
            {
                TemporaryException: lambda ex: error_tuple
                if "test" in ex.message
                else None
            }
        ):
            exception = TemporaryException()
            exception.message = "test"
            raise exception

    assert api_exception_5.value.detail["error"] == "ERROR_TEMPORARY_2"
    assert api_exception_5.value.detail["detail"] == "Another message test"
    assert api_exception_5.value.status_code == status.HTTP_404_NOT_FOUND

    # Can map to a sub type of an exception and it will be chosen
    with pytest.raises(APIException) as api_exception_3:
        with map_exceptions(
            {
                TemporarySubClassException: "SUB_TYPE_ERROR",
                TemporaryException: "BASE_TYPE_ERROR",
            }
        ):
            raise TemporarySubClassException

    assert api_exception_3.value.detail["error"] == "SUB_TYPE_ERROR"

    # Can map to a base type of an exception and it will be chosen
    with pytest.raises(APIException) as api_exception_3:
        with map_exceptions(
            {
                TemporarySubClassException: "SUB_TYPE_ERROR",
                TemporaryException: "BASE_TYPE_ERROR",
            }
        ):
            raise TemporaryException

    assert api_exception_3.value.detail["error"] == "BASE_TYPE_ERROR"


def test_map_exceptions_from_registry():
    class TestException(Exception):
        ...

    test_error = (
        "TEST_ERROR",
        HTTP_400_BAD_REQUEST,
        "Test error description.",
    )

    test_registered_ex = RegisteredException(
        exception_class=TestException, exception_error=test_error
    )

    api_exception_registry.register(test_registered_ex)

    with pytest.raises(APIException) as api_exception:
        with map_exceptions({}):
            raise TestException

    assert api_exception.value.detail["error"] == "TEST_ERROR"
    assert api_exception.value.detail["detail"] == "Test error description."
    assert api_exception.value.status_code == status.HTTP_400_BAD_REQUEST


def test_validate_data():
    with pytest.raises(APIException) as api_exception_1:
        validate_data(TemporarySerializer, {"field_1": "test"})

    assert api_exception_1.value.detail["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert api_exception_1.value.detail["detail"]["field_2"][0]["error"] == (
        "This field is required."
    )
    assert api_exception_1.value.detail["detail"]["field_2"][0]["code"] == "required"
    assert api_exception_1.value.status_code == status.HTTP_400_BAD_REQUEST

    with pytest.raises(APIException) as api_exception_2:
        validate_data(TemporarySerializer, {"field_1": "test", "field_2": "wrong"})

    assert api_exception_2.value.detail["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert api_exception_2.value.detail["detail"]["field_2"][0]["error"] == (
        '"wrong" is not a valid choice.'
    )
    assert api_exception_2.value.detail["detail"]["field_2"][0]["code"] == (
        "invalid_choice"
    )
    assert api_exception_2.value.status_code == status.HTTP_400_BAD_REQUEST

    validated_data = validate_data(
        TemporarySerializer, {"field_1": "test", "field_2": "choice_1"}
    )
    assert validated_data["field_1"] == "test"
    assert validated_data["field_2"] == "choice_1"
    assert len(validated_data.items()) == 2

    with pytest.raises(APIException) as api_exception_1:
        validate_data(
            TemporarySerializerWithList, {"field_3": "aaa", "field_4": ["a", "b"]}
        )

    assert api_exception_1.value.status_code == status.HTTP_400_BAD_REQUEST
    assert api_exception_1.value.detail["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert api_exception_1.value.detail["detail"]["field_3"][0]["error"] == (
        "A valid integer is required."
    )
    assert api_exception_1.value.detail["detail"]["field_3"][0]["code"] == "invalid"

    assert len(api_exception_1.value.detail["detail"]["field_4"]) == 2
    assert api_exception_1.value.detail["detail"]["field_4"][0][0]["error"] == (
        "A valid integer is required."
    )
    assert api_exception_1.value.detail["detail"]["field_4"][0][0]["code"] == (
        "invalid"
    )
    assert api_exception_1.value.detail["detail"]["field_4"][1][0]["error"] == (
        "A valid integer is required."
    )
    assert api_exception_1.value.detail["detail"]["field_4"][1][0]["code"] == (
        "invalid"
    )

    with pytest.raises(APIException) as api_exception_3:
        validate_data(TemporaryListSerializer, [{"something": "nothing"}])

    assert api_exception_3.value.status_code == status.HTTP_400_BAD_REQUEST
    assert api_exception_3.value.detail["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert len(api_exception_3.value.detail["detail"]) == 1
    assert api_exception_3.value.detail["detail"][0]["field_1"][0]["code"] == "required"
    assert api_exception_3.value.detail["detail"][0]["field_2"][0]["code"] == "required"

    with pytest.raises(QueryParameterValidationException) as api_exception_4:
        validate_data(
            TemporaryQueryParamSerializer,
            {"field_5": "wrong_type"},
            exception_to_raise=QueryParameterValidationException,
        )
    assert api_exception_4.value.status_code == status.HTTP_400_BAD_REQUEST
    assert api_exception_4.value.detail["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
    assert api_exception_4.value.detail["detail"]["field_5"][0]["code"] == "invalid"
    assert api_exception_4.value.detail["detail"]["field_5"][0]["error"] == (
        "A valid integer is required."
    )

    with pytest.raises(QueryParameterValidationException) as api_exception_5:
        validate_data(
            TemporaryQueryParamSerializer,
            {},
            exception_to_raise=QueryParameterValidationException,
        )
    assert api_exception_5.value.status_code == status.HTTP_400_BAD_REQUEST
    assert api_exception_5.value.detail["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
    assert api_exception_5.value.detail["detail"]["field_5"][0]["code"] == "required"
    assert api_exception_5.value.detail["detail"]["field_5"][0]["error"] == (
        "This field is required."
    )

    with pytest.raises(QueryParameterValidationException) as api_exception_6:
        validate_data(
            TemporaryQueryParamSerializer,
            {"field_5": 5, "field_6": "string_is_way_too_long"},
            exception_to_raise=QueryParameterValidationException,
        )
    assert api_exception_6.value.status_code == status.HTTP_400_BAD_REQUEST
    assert api_exception_6.value.detail["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
    assert api_exception_6.value.detail["detail"]["field_6"][0]["code"] == "max_length"
    assert api_exception_6.value.detail["detail"]["field_6"][0]["error"] == (
        "Ensure this field has no more than 20 characters."
    )

    with pytest.raises(QueryParameterValidationException) as api_exception_7:
        validate_data(
            TemporaryQueryParamSerializer,
            {"field_5": "wrong_type", "field_6": "string_is_way_too_long"},
            exception_to_raise=QueryParameterValidationException,
        )
    assert api_exception_7.value.status_code == status.HTTP_400_BAD_REQUEST
    assert api_exception_7.value.detail["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"
    assert api_exception_7.value.detail["detail"]["field_6"][0]["code"] == "max_length"
    assert api_exception_7.value.detail["detail"]["field_6"][0]["error"] == (
        "Ensure this field has no more than 20 characters."
    )
    assert api_exception_7.value.detail["detail"]["field_5"][0]["code"] == "invalid"
    assert api_exception_7.value.detail["detail"]["field_5"][0]["error"] == (
        "A valid integer is required."
    )


def test_validate_data_custom_fields():
    registry = TemporaryTypeRegistry()
    registry.register(TemporaryInstanceType1())
    registry.register(TemporaryInstanceType2())

    with pytest.raises(APIException) as api_exception:
        validate_data_custom_fields("NOT_EXISTING", registry, {})

    assert api_exception.value.detail["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert api_exception.value.detail["detail"]["type"][0]["error"] == (
        '"NOT_EXISTING" is not a valid choice.'
    )
    assert api_exception.value.detail["detail"]["type"][0]["code"] == "invalid_choice"
    assert api_exception.value.status_code == status.HTTP_400_BAD_REQUEST

    with pytest.raises(APIException) as api_exception_2:
        validate_data_custom_fields("temporary_2", registry, {})

    assert api_exception_2.value.detail["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert api_exception_2.value.detail["detail"]["name"][0]["error"] == (
        "This field is required."
    )
    assert api_exception_2.value.detail["detail"]["name"][0]["code"] == "required"
    assert api_exception_2.value.status_code == status.HTTP_400_BAD_REQUEST

    with pytest.raises(APIException) as api_exception_3:
        validate_data_custom_fields("temporary_2", registry, {"name": "test1"})

    assert api_exception_3.value.detail["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert api_exception_3.value.detail["detail"]["name"][0]["error"] == (
        "A valid integer is required."
    )
    assert api_exception_3.value.detail["detail"]["name"][0]["code"] == "invalid"
    assert api_exception_3.value.status_code == status.HTTP_400_BAD_REQUEST

    data = validate_data_custom_fields("temporary_2", registry, {"name": 123})
    assert data["name"] == 123


@pytest.mark.django_db
def test_get_serializer_class(data_fixture):
    workspace = data_fixture.create_workspace(name="Workspace 1")

    workspace_serializer = get_serializer_class(Workspace, ["name"])(workspace)
    assert workspace_serializer.data == {"name": "Workspace 1"}
    assert workspace_serializer.__class__.__name__ == "WorkspaceSerializer"

    workspace_serializer_2 = get_serializer_class(
        Workspace, ["id", "name"], {"id": CharField()}
    )(workspace)
    assert workspace_serializer_2.data == {
        "id": str(workspace.id),
        "name": "Workspace 1",
    }


@override_settings(DEBUG=False)
def test_api_error_if_url_trailing_slash_is_missing(api_client):
    invalid_url = "/api/invalid-url"
    # with DEBUG=False always return a JSON response for an invalid url
    for content_type in ["application/json", "application/xml", "text/html", "", "*/*"]:
        for method in ["get", "post", "patch", "delete"]:
            response = getattr(api_client, method)(
                invalid_url, HTTP_ACCEPT=content_type
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
            response_json = response.json()
            assert response_json["detail"] == f"URL {invalid_url} not found."
            assert response_json["error"] == "URL_NOT_FOUND"

    # get nicer 404 error if the url is valid (even if method is not)
    url = "/api/user/dashboard"
    for method in ["get", "post", "patch", "delete"]:
        response = getattr(api_client, method)(url, HTTP_ACCEPT="application/json")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        response_json = response.json()
        assert response_json["detail"] == (
            "A valid URL must end with a trailing slash. "
            f"Please, redirect requests to {url}/"
        )
        assert response_json["error"] == "URL_TRAILING_SLASH_MISSING"


@override_settings(DEBUG=True)
def test_api_give_informative_404_page_in_debug_for_invalid_urls(api_client):
    invalid_url = "/api/invalid-url"

    # check that the django 404 html informative page is returned if DEBUG=True
    # and the ACCEPT header does not accept json
    for content_type in ["application/xml", "text/html"]:
        for method in ["get", "post", "patch", "delete"]:
            response = getattr(api_client, method)(
                invalid_url, HTTP_ACCEPT=content_type
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert response.headers.get("content-type") == "text/html; charset=utf-8"


def create_dummy_request(user, path="/api/user/dashboard"):
    class DummyRequest:
        def __init__(self, path, user):
            self.path = path
            self.user = user

    request = APIRequestFactory().get(path)
    request.user = user
    request._request = DummyRequest(path, user)
    return request


@override_settings(BASEROW_CONCURRENT_USER_REQUESTS_THROTTLE_TIMEOUT=30)
@pytest.mark.django_db
def test_concurrent_user_requests_throttle_non_staff_authenticated_users(data_fixture):
    user = data_fixture.create_user()
    ConcurrentUserRequestsThrottle.timer = lambda s: time.time()
    ConcurrentUserRequestsThrottle.rate = 1

    with freeze_time("2023-03-30 00:00:00"):
        throttle = ConcurrentUserRequestsThrottle()
        assert throttle.allow_request(create_dummy_request(user), None)

    with freeze_time("2023-03-30 00:00:01"):
        throttle = ConcurrentUserRequestsThrottle()
        assert not throttle.allow_request(create_dummy_request(user), None)
        assert throttle.wait() == 29

    # once the timeout is over, the user should be able to make a new request
    request = create_dummy_request(user)
    with freeze_time("2023-03-30 00:00:31"):
        throttle = ConcurrentUserRequestsThrottle()
        throttle.timer = lambda: time.time()
        assert throttle.allow_request(request, None)

    # once the request has beed processed and the callback called,
    # another request can be made
    ConcurrentUserRequestsThrottle.on_request_processed(request._request)
    with freeze_time("2023-03-30 00:00:40"):
        throttle = ConcurrentUserRequestsThrottle()
        throttle.timer = lambda: time.time()
        assert throttle.allow_request(request, None)


@pytest.mark.django_db
def test_concurrent_user_requests_does_not_throttle_staff_users(data_fixture):
    user = data_fixture.create_user(is_staff=True)
    ConcurrentUserRequestsThrottle.timer = lambda s: time.time()
    ConcurrentUserRequestsThrottle.rate = 1

    with freeze_time("2023-03-30 00:00:00"):
        throttle = ConcurrentUserRequestsThrottle()
        assert throttle.allow_request(create_dummy_request(user), None)

    with freeze_time("2023-03-30 00:00:01"):
        throttle = ConcurrentUserRequestsThrottle()
        assert throttle.allow_request(create_dummy_request(user), None)

    with freeze_time("2023-03-30 00:00:02"):
        throttle = ConcurrentUserRequestsThrottle()
        assert throttle.allow_request(create_dummy_request(user), None)


@override_settings(
    MIDDLEWARE=[
        *settings.MIDDLEWARE,
        "baserow.middleware.ConcurrentUserRequestsMiddleware",
    ],
)
@patch("baserow.throttling.ConcurrentUserRequestsThrottle.on_request_processed")
@pytest.mark.django_db
def test_throttle_set_baserow_concurrency_throttle_request_id_and_middleware_can_get_it(
    mock_on_request_processed, data_fixture, api_client
):
    # Looking at
    # https://github.com/encode/django-rest-framework/blob/3.14.0/rest_framework/views.py#L110
    # it seems like the throttle_classes are set when the class is created so
    # @override_settings does not work as expected. We need to set the
    # throttle_classes on the class itself to be able to override the settings.
    from baserow.api.user.views import DashboardView

    ConcurrentUserRequestsThrottle.rate = 1
    DashboardView.throttle_classes = [ConcurrentUserRequestsThrottle]

    _, token = data_fixture.create_user_and_token()

    api_client.get("/api/user/dashboard/", HTTP_AUTHORIZATION=f"JWT {token}")

    assert mock_on_request_processed.call_count == 1
    request = mock_on_request_processed.call_args[0][0]
    assert getattr(request, BASEROW_CONCURRENCY_THROTTLE_REQUEST_ID, None) is not None


@pytest.mark.django_db
def test_can_set_per_user_profile_custom_limt(data_fixture):
    user = data_fixture.create_user(concurrency_limit=-1)
    assert user.profile.concurrency_limit == -1
    ConcurrentUserRequestsThrottle.timer = lambda s: time.time()
    ConcurrentUserRequestsThrottle.rate = 1

    with freeze_time("2023-03-30 00:00:00"):
        throttle = ConcurrentUserRequestsThrottle()
        assert throttle.allow_request(create_dummy_request(user), None)

    with freeze_time("2023-03-30 00:00:01"):
        throttle = ConcurrentUserRequestsThrottle()
        assert throttle.allow_request(create_dummy_request(user), None)

    with freeze_time("2023-03-30 00:00:02"):
        throttle = ConcurrentUserRequestsThrottle()
        assert throttle.allow_request(create_dummy_request(user), None)


@pytest.mark.django_db
def test_can_set_throttle_per_user_profile_custom_limit(data_fixture):
    user = data_fixture.create_user(concurrency_limit=1)
    ConcurrentUserRequestsThrottle.timer = lambda s: time.time()
    ConcurrentUserRequestsThrottle.rate = 20

    with freeze_time("2023-03-30 00:00:00"):
        throttle = ConcurrentUserRequestsThrottle()
        assert throttle.allow_request(create_dummy_request(user), None)

    with freeze_time("2023-03-30 00:00:01"):
        throttle = ConcurrentUserRequestsThrottle()
        assert not throttle.allow_request(create_dummy_request(user), None)

    with freeze_time("2023-03-30 00:00:02"):
        throttle = ConcurrentUserRequestsThrottle()
        assert not throttle.allow_request(create_dummy_request(user), None)


@pytest.mark.django_db
def test_anon_user_works(data_fixture):
    user = AnonymousUser()
    ConcurrentUserRequestsThrottle.timer = lambda s: time.time()
    ConcurrentUserRequestsThrottle.rate = 20

    with freeze_time("2023-03-30 00:00:00"):
        throttle = ConcurrentUserRequestsThrottle()
        assert throttle.allow_request(create_dummy_request(user), None)

    with freeze_time("2023-03-30 00:00:01"):
        throttle = ConcurrentUserRequestsThrottle()
        assert throttle.allow_request(create_dummy_request(user), None)

    with freeze_time("2023-03-30 00:00:02"):
        throttle = ConcurrentUserRequestsThrottle()
        assert throttle.allow_request(create_dummy_request(user), None)


@pytest.mark.django_db
def test_parse_limit_linked_items_params(data_fixture):
    # Test with no params
    request = APIRequestFactory().get("/api/database/rows/")
    assert parse_limit_linked_items_params(request) is None

    # Test with empty params
    request = APIRequestFactory().get("/api/database/rows/?limit_linked_items=")
    assert parse_limit_linked_items_params(request) is None

    # Test with invalid params
    request = APIRequestFactory().get(f"/api/database/rows/?limit_linked_items=hello!")
    assert parse_limit_linked_items_params(request) is None

    # Test with negative params
    request = APIRequestFactory().get(f"/api/database/rows/?limit_linked_items=-1")
    assert parse_limit_linked_items_params(request) is None

    # Test with zero as params
    request = APIRequestFactory().get(f"/api/database/rows/?limit_linked_items=0")
    assert parse_limit_linked_items_params(request) is None

    # Test with valid params
    request = APIRequestFactory().get(f"/api/database/rows/?limit_linked_items=3")
    assert parse_limit_linked_items_params(request) == 3
