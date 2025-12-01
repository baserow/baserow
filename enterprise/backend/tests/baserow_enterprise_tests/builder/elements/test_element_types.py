import json
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK

from baserow.api.exceptions import RequestBodyValidationException
from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.test_utils.helpers import AnyInt, AnyStr
from baserow_enterprise.builder.elements.element_types import (
    AuthFormElementType,
    FileInputElementType,
)
from baserow_enterprise.builder.elements.models import AuthFormElement, FileInputElement


@pytest.mark.django_db
def test_auth_form_element_import_export_data_source(data_fixture):
    page = data_fixture.create_builder_page()
    user_source_1 = data_fixture.create_user_source_with_first_type(
        application=page.builder
    )
    user_source_2 = data_fixture.create_user_source_with_first_type(
        application=page.builder
    )
    element_type = AuthFormElementType()

    exported_element = data_fixture.create_builder_element(
        AuthFormElement, user_source=user_source_1
    )

    id_mapping = {"user_sources": {user_source_1.id: user_source_2.id}}
    serialized = element_type.export_serialized(exported_element)

    imported_element = element_type.import_serialized(page, serialized, id_mapping)

    assert imported_element.user_source.id == user_source_2.id


@pytest.mark.django_db
def test_create_auth_form_with_user_source(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    user_source_1 = data_fixture.create_user_source_with_first_type(
        application=page.builder
    )

    ElementService().create_element(
        user,
        element_type_registry.get("auth_form"),
        page=page,
        user_source_id=user_source_1.id,
    )


@pytest.mark.django_db
def test_create_auth_form_with_user_source_another_app(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    user_source_other_app = data_fixture.create_user_source_with_first_type(user=user)

    with pytest.raises(RequestBodyValidationException):
        ElementService().create_element(
            user,
            element_type_registry.get("auth_form"),
            page=page,
            user_source_id=user_source_other_app.id,
        )


@pytest.mark.django_db
def test_file_input_element_is_valid(fake):
    element = MagicMock()
    element.multiple = False
    element.allowed_filetypes = []
    element.max_filesize = 100

    fake_request = MagicMock()
    fake_request.data = {}

    fake_file = SimpleUploadedFile(
        name="avatar.png", content=fake.image(), content_type="image/png"
    )
    fake_request.FILES = {
        "3c913094-c69a-4fd3-b19d-c35322f7d5c5": fake_file,
    }

    dispatch_context = BuilderDispatchContext(fake_request, None)

    value = {
        "__file__": True,
        "name": "image_1.png",
        "content_type": "image/png",
        "size": "1963",
        "file": "3c913094-c69a-4fd3-b19d-c35322f7d5c5",
    }

    validated = FileInputElementType().is_valid(element, value, dispatch_context)

    assert validated == {
        "__file__": True,
        "name": "image_1.png",
        "content_type": "image/png",
        "size": "1963",
        "file": fake_file,
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "allowed,should_raise",
    [
        (["video/*"], TypeError),
        (["image/*"], None),
        (["audio/*"], TypeError),
        (["png"], None),
        ([".png"], None),
        ([".jpg"], TypeError),
        ([".jpg", "png"], None),
    ],
)
def test_file_input_element_is_valid_invalid_filetype(fake, allowed, should_raise):
    element = MagicMock()
    element.multiple = False
    element.allowed_filetypes = allowed
    element.max_filesize = 100

    fake_request = MagicMock()
    fake_request.data = {}

    fake_file = SimpleUploadedFile(
        name="avatar.png", content=fake.image(), content_type="image/png"
    )
    fake_request.FILES = {
        "3c913094-c69a-4fd3-b19d-c35322f7d5c5": fake_file,
    }

    dispatch_context = BuilderDispatchContext(fake_request, None)

    value = {
        "__file__": True,
        "name": "image_1.png",
        "content_type": "video/avi",  # Should not use that
        "size": "1963",
        "file": "3c913094-c69a-4fd3-b19d-c35322f7d5c5",
    }

    if should_raise:
        with pytest.raises(should_raise):
            FileInputElementType().is_valid(element, value, dispatch_context)
    else:
        assert FileInputElementType().is_valid(element, value, dispatch_context) == {
            "__file__": True,
            "name": "image_1.png",
            "content_type": "image/png",
            "size": "1963",
            "file": fake_file,
        }


@pytest.mark.django_db
def test_file_input_element_is_valid_invalid_size(fake):
    element = MagicMock()
    element.multiple = False
    element.allowed_filetypes = []
    element.max_filesize = 1

    fake_request = MagicMock()
    fake_request.data = {}

    fake_file = MagicMock()
    fake_file.name = "avatar.png"
    fake_file.size = 1024 * 1024 * 2  # 2MB
    fake_file.content_type = "image/png"

    fake_request.FILES = {
        "3c913094-c69a-4fd3-b19d-c35322f7d5c5": fake_file,
    }

    dispatch_context = BuilderDispatchContext(fake_request, None)

    value = {
        "__file__": True,
        "name": "image_1.png",
        "content_type": "image/png",
        "size": "1963",
        "file": "3c913094-c69a-4fd3-b19d-c35322f7d5c5",
    }

    with pytest.raises(ValueError):
        FileInputElementType().is_valid(element, value, dispatch_context)


@pytest.mark.django_db
def test_dispatch_local_baserow_update_row_workflow_action_with_file(
    api_client, data_fixture, fake
):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("File", "file"),
        ],
        rows=[[[]]],
    )
    model = table.get_model()
    first_row = model.objects.all()[0]
    file_field = table.field_set.get(name="File")
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    button_element = data_fixture.create_builder_button_element(page=page)
    file_input_element = data_fixture.create_builder_element(
        FileInputElement, user, page=page, multiple=True
    )

    workflow_action = data_fixture.create_local_baserow_update_row_workflow_action(
        page=page,
        element=button_element,
        event=EventTypes.CLICK,
        user=user,
    )
    service = workflow_action.service.specific
    service.table = table
    service.row_id = f"'{first_row.id}'"
    service.field_mappings.create(
        field=file_field, value=f"get('form_data.{file_input_element.id}')"
    )
    service.save()

    url = reverse(
        "api:builder:workflow_action:dispatch",
        kwargs={"workflow_action_id": workflow_action.id},
    )

    with patch(
        "baserow.contrib.builder.handler.get_builder_used_property_names"
    ) as used_properties_mock:
        used_properties_mock.return_value = {
            "all": {workflow_action.service.id: ["id", file_field.db_column]},
            "external": {workflow_action.service.id: ["id", file_field.db_column]},
        }

        image = fake.image()

        payload = {
            "metadata": json.dumps(
                {
                    "form_data": {
                        str(file_input_element.id): [
                            {
                                "__file__": True,
                                "name": "image_1.png",
                                "content_type": "image/png",
                                "size": "1963",
                                "file": "3c913094-c69a-4fd3-b19d-c35322f7d5c5",
                            },
                        ]
                    }
                }
            ),
            "3c913094-c69a-4fd3-b19d-c35322f7d5c5": SimpleUploadedFile(
                name="avatar.png", content=image, content_type="image/png"
            ),
        }
        response = api_client.post(
            url,
            payload,
            format="multipart",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json[file_field.name] == [
        {
            "image_height": 256,
            "image_width": 256,
            "is_image": True,
            "mime_type": "image/png",
            "name": AnyStr(),
            "size": AnyInt(),
            "uploaded_at": AnyStr(),
            "thumbnails": {
                "tiny": {
                    "height": 21,
                    "url": AnyStr(),
                    "width": 21,
                },
            },
            "url": AnyStr(),
            "visible_name": "image_1.png",
        },
    ]
