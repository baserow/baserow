from unittest.mock import MagicMock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.utils import override_settings

import pytest
import responses
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework.fields import (
    BooleanField,
    CharField,
    ChoiceField,
    DateField,
    DateTimeField,
    DecimalField,
    EmailField,
    FloatField,
    IntegerField,
    ListField,
    SerializerMethodField,
    UUIDField,
)
from rest_framework.serializers import ListSerializer, Serializer

from baserow.contrib.database.api.fields.serializers import FileFieldRequestSerializer
from baserow.contrib.integrations.local_baserow.utils import (
    guess_cast_function_from_response_serializer_field,
    guess_json_type_from_response_serializer_field,
    prepare_files_for_db,
)
from baserow.core.formula.validator import (
    ensure_array,
    ensure_boolean,
    ensure_date,
    ensure_datetime,
    ensure_integer,
    ensure_string,
)
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.user_files.handler import UserFileHandler
from baserow.test_utils.helpers import AnyInt, AnyStr


def test_guess_type_for_response_serialize_field_permutations():
    TYPE_NULL = {"type": None}
    TYPE_OBJECT = {"type": "object", "properties": {}}
    TYPE_STRING = {"type": "string"}
    TYPE_NUMBER = {"type": "number"}
    TYPE_BOOLEAN = {"type": "boolean"}
    TYPE_DATE = {"type": "string", "format": "date"}
    TYPE_DATE_TIME = {"type": "string", "format": "date-time"}
    TYPE_ARRAY_CHILD_OBJECT = {
        "type": "array",
        "items": TYPE_OBJECT,
    }
    TYPE_OBJECT_FROM_METHOD_SERIALIZER = {
        "type": "object",
        "properties": {
            "answer": {"title": "answer", "type": "number"},
            "url": {"title": "url", "type": "string"},
        },
    }

    class FakeSerializer(Serializer):
        """Dummy serializer for testing method serializers that use OpenAPI types."""

        answer = SerializerMethodField()
        url = SerializerMethodField()

        @extend_schema_field(OpenApiTypes.NUMBER)
        def get_answer(self, instance):
            return 42

        @extend_schema_field(OpenApiTypes.URI)
        def get_url(self, instance):
            return "https://baserow.io"

    assert guess_json_type_from_response_serializer_field(UUIDField()) == TYPE_STRING
    assert guess_json_type_from_response_serializer_field(CharField()) == TYPE_STRING
    assert (
        guess_json_type_from_response_serializer_field(
            DecimalField(decimal_places=2, max_digits=4)
        )
        == TYPE_STRING
    )
    assert guess_json_type_from_response_serializer_field(FloatField()) == TYPE_STRING
    assert (
        guess_json_type_from_response_serializer_field(ChoiceField(choices=("a", "b")))
        == TYPE_STRING
    )
    assert guess_json_type_from_response_serializer_field(IntegerField()) == TYPE_NUMBER
    assert (
        guess_json_type_from_response_serializer_field(BooleanField()) == TYPE_BOOLEAN
    )
    assert guess_json_type_from_response_serializer_field(DateField()) == TYPE_DATE
    assert (
        guess_json_type_from_response_serializer_field(DateTimeField())
        == TYPE_DATE_TIME
    )
    assert (
        guess_json_type_from_response_serializer_field(
            ListSerializer(child=Serializer())
        )
        == TYPE_ARRAY_CHILD_OBJECT
    )
    assert guess_json_type_from_response_serializer_field(Serializer()) == TYPE_OBJECT
    assert (
        guess_json_type_from_response_serializer_field("unknown")  # type: ignore
        == TYPE_NULL
    )
    assert (
        guess_json_type_from_response_serializer_field((FakeSerializer()))
    ) == TYPE_OBJECT_FROM_METHOD_SERIALIZER


@pytest.mark.parametrize(
    "serializer,expected",
    [
        (CharField(), ensure_string),
        (UUIDField(), ensure_string),
        (EmailField(), ensure_string),
        (IntegerField(), ensure_integer),
        (DecimalField(decimal_places=2, max_digits=4), ensure_string),
        (BooleanField(), ensure_boolean),
        (DateField(), ensure_date),
        (DateTimeField(), ensure_datetime),
        (ListSerializer(child=Serializer()), ensure_array),
        (ListField(child=IntegerField()), ensure_array),
        (ListField(), ensure_array),
        ("unknown", None),
        (None, None),
    ],
)
def test_guess_cast_function_from_response_serialize_field(serializer, expected):
    assert (
        guess_cast_function_from_response_serializer_field(serializer, None) == expected
    )


@pytest.mark.django_db
def test_guess_cast_function_for_filefieldserializer(data_fixture, fake):
    user = data_fixture.create_user()
    service = MagicMock()
    service.integration = MagicMock()
    service.integration.authorized_user = user
    prepare = guess_cast_function_from_response_serializer_field(
        FileFieldRequestSerializer(), service
    )

    value = {
        "__file__": True,
        "name": "superfile",
        "file": SimpleUploadedFile(
            name="avatar.png", content=fake.image(), content_type="image/png"
        ),
    }

    assert prepare(value) == [
        {
            "image_height": 256,
            "image_width": 256,
            "is_image": True,
            "mime_type": "image/png",
            "name": AnyStr(),
            "size": AnyInt(),
            "uploaded_at": AnyStr(),
        },
    ]


@pytest.mark.parametrize(
    "value,result",
    [
        (None, []),
        ("", []),
        ({}, [{}]),
        ({"prop": 1}, [{"prop": 1}]),
        ([{}], [{}]),
        ([{"prop": 1}], [{"prop": 1}]),
    ],
)
@pytest.mark.django_db
def test_prepare_file_for_db(data_fixture, value, result):
    user = data_fixture.create_user()

    assert prepare_files_for_db(value, user) == result


@pytest.mark.django_db
def test_prepare_file_for_db_with_file(data_fixture, fake):
    user = data_fixture.create_user()

    image = fake.image()

    value = {
        "__file__": True,
        "name": "superfile",
        "file": SimpleUploadedFile(
            name="avatar.png", content=image, content_type="image/png"
        ),
    }

    assert prepare_files_for_db(value, user) == [
        {
            "image_height": 256,
            "image_width": 256,
            "is_image": True,
            "mime_type": "image/png",
            "name": AnyStr(),
            "size": AnyInt(),
            "uploaded_at": AnyStr(),
        },
    ]

    value = [
        {
            "__file__": True,
            "name": "superfile1",
            "file": SimpleUploadedFile(
                name="avatar.png", content=image, content_type="image/png"
            ),
        },
        {
            "__file__": True,
            "name": "superfile2",
            "file": SimpleUploadedFile(
                name="avatar.png", content=image, content_type="image/png"
            ),
        },
    ]

    assert prepare_files_for_db(value, user) == [
        {
            "image_height": 256,
            "image_width": 256,
            "is_image": True,
            "mime_type": "image/png",
            "name": AnyStr(),
            "size": AnyInt(),
            "uploaded_at": AnyStr(),
        },
        {
            "image_height": 256,
            "image_width": 256,
            "is_image": True,
            "mime_type": "image/png",
            "name": AnyStr(),
            "size": AnyInt(),
            "uploaded_at": AnyStr(),
        },
    ]


@pytest.mark.django_db
@responses.activate
def test_prepare_file_for_db_with_url(data_fixture, fake):
    user = data_fixture.create_user()

    url = "https://picsum.photos/200/300"
    value = {
        "__file__": True,
        "name": "filename",
        "url": url,
    }

    responses.add(
        responses.GET,
        url,
        status=200,
        body=fake.image((200, 300)),
    )

    assert prepare_files_for_db(value, user) == [
        {
            "image_height": 300,
            "image_width": 200,
            "is_image": True,
            "mime_type": "image/png",
            "name": AnyStr(),
            "size": AnyInt(),
            "uploaded_at": AnyStr(),
        },
    ]

    assert prepare_files_for_db([value, value], user) == [
        {
            "image_height": 300,
            "image_width": 200,
            "is_image": True,
            "mime_type": "image/png",
            "name": AnyStr(),
            "size": AnyInt(),
            "uploaded_at": AnyStr(),
        },
        {
            "image_height": 300,
            "image_width": 200,
            "is_image": True,
            "mime_type": "image/png",
            "name": AnyStr(),
            "size": AnyInt(),
            "uploaded_at": AnyStr(),
        },
    ]


@pytest.mark.django_db
@responses.activate
def test_prepare_file_for_db_with_unreachable_url(data_fixture):
    user = data_fixture.create_user()

    url = "https://somenthing.doesnt.exist.com"
    value = {
        "__file__": True,
        "name": "filename",
        "url": url,
    }

    responses.add(responses.GET, url, status=404)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        prepare_files_for_db(value, user)


@pytest.mark.django_db
@override_settings(BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB=1)
def test_prepare_file_for_db_with_toolarge_url(data_fixture, fake):
    user = data_fixture.create_user()
    image = fake.image(size=(1000, 1000))

    value = {
        "__file__": True,
        "name": "superfile",
        "file": SimpleUploadedFile(
            name="avatar.png", content=image, content_type="image/png"
        ),
    }

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        prepare_files_for_db(value, user)


@pytest.mark.django_db
def test_prepare_file_for_db_with_existing_file(data_fixture):
    user = data_fixture.create_user()
    user_file = data_fixture.create_user_file(
        original_name=f"a.txt",
    )

    value = {
        "__file__": True,
        "name": "filename",
        "url": UserFileHandler().get_user_file_url(user_file),
    }

    assert prepare_files_for_db(value, user) == [
        {
            "image_height": None,
            "image_width": None,
            "is_image": False,
            "mime_type": "text/plain",
            "name": AnyStr(),
            "size": AnyInt(),
            "uploaded_at": AnyStr(),
        },
    ]

    assert prepare_files_for_db([value, value], user) == [
        {
            "image_height": None,
            "image_width": None,
            "is_image": False,
            "mime_type": "text/plain",
            "name": AnyStr(),
            "size": AnyInt(),
            "uploaded_at": AnyStr(),
        },
        {
            "image_height": None,
            "image_width": None,
            "is_image": False,
            "mime_type": "text/plain",
            "name": AnyStr(),
            "size": AnyInt(),
            "uploaded_at": AnyStr(),
        },
    ]


@pytest.mark.django_db
@responses.activate
def test_prepare_file_for_db_with_mix(data_fixture, fake):
    picsum_url = "https://picsum.photos/300/200"
    responses.add(
        responses.GET,
        picsum_url,
        status=200,
        body=fake.image((300, 200)),
    )

    user = data_fixture.create_user()
    user_file = data_fixture.create_user_file(
        original_name=f"a.txt",
    )
    image = fake.image()

    value = [
        {
            "__file__": True,
            "name": "filename",
            "url": UserFileHandler().get_user_file_url(user_file),
        },
        {
            "__file__": True,
            "name": "filename",
            "url": picsum_url,
        },
        {
            "__file__": True,
            "name": "superfile",
            "file": SimpleUploadedFile(
                name="avatar.png", content=image, content_type="image/png"
            ),
        },
    ]

    assert prepare_files_for_db(value, user) == [
        {
            "image_height": None,
            "image_width": None,
            "is_image": False,
            "mime_type": "text/plain",
            "name": AnyStr(),
            "size": AnyInt(),
            "uploaded_at": AnyStr(),
        },
        {
            "image_height": 200,
            "image_width": 300,
            "is_image": True,
            "mime_type": "image/png",
            "name": AnyStr(),
            "size": AnyInt(),
            "uploaded_at": AnyStr(),
        },
        {
            "image_height": 256,
            "image_width": 256,
            "is_image": True,
            "mime_type": "image/png",
            "name": AnyStr(),
            "size": AnyInt(),
            "uploaded_at": AnyStr(),
        },
    ]
