import json
from unittest.mock import MagicMock, patch
from uuid import UUID

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.api.exceptions import RequestBodyValidationException
from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.elements.exceptions import ElementTypeDeactivated
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.formula_importer import import_formula
from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.test_utils.helpers import AnyInt, AnyStr
from baserow_enterprise.builder.elements.element_types import (
    AuthFormElementType,
    FileInputElementType,
    GraphElementSeriesSerializer,
    GraphElementType,
)
from baserow_enterprise.builder.elements.models import FileInputElement


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
        AuthFormElementType, user_source=user_source_1
    )

    id_mapping = {"user_sources": {user_source_1.id: user_source_2.id}}
    serialized = element_type.export_serialized(exported_element)

    imported_element = element_type.import_serialized(page, serialized, id_mapping)

    assert imported_element.user_source.id == user_source_2.id


@pytest.mark.django_db
def test_builder_application_import_with_auth_form_referencing_trashed_user_source(
    data_fixture,
):
    from baserow.contrib.builder.application_types import BuilderApplicationType
    from baserow.core.registries import ImportExportConfig
    from baserow.core.trash.handler import TrashHandler

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)
    data_fixture.create_builder_element(
        AuthFormElementType, page=page, user_source=user_source
    )

    # Trash the user source; the auth form keeps its dangling reference.
    TrashHandler.trash(user, workspace, builder, user_source)

    config = ImportExportConfig(include_permission_data=True)
    serialized = BuilderApplicationType().export_serialized(builder, config)
    serialized = json.loads(json.dumps(serialized))

    imported = BuilderApplicationType().import_serialized(
        workspace, serialized, config, {}
    )

    imported_page = imported.visible_pages.get(name=page.name)
    imported_element = imported_page.element_set.get().specific
    assert imported_element.user_source_id is None


@pytest.mark.django_db
def test_graph_element_import_export_formula_data_sources(
    data_fixture, enable_enterprise
):
    page = data_fixture.create_builder_page()
    data_source_1 = data_fixture.create_builder_local_baserow_get_row_data_source()
    data_source_2 = data_fixture.create_builder_local_baserow_get_row_data_source()
    element_type = GraphElementType()

    exported_element = data_fixture.create_builder_element(
        GraphElementType,
        page=page,
        labels=f"get('data_source.{data_source_1.id}.field_1')",
        series=[
            {
                "uid": "61b8a893-d454-47e4-9924-8d8da62a8bd9",
                "label": f"get('data_source.{data_source_1.id}.field_2')",
                "values": f"get('data_source.{data_source_1.id}.field_3')",
                "color": "#2e90fa",
                "chart_type": "BAR",
            }
        ],
    )

    id_mapping = {"builder_data_sources": {data_source_1.id: data_source_2.id}}
    updated_models = element_type.import_formulas(
        exported_element, id_mapping, import_formula
    )

    assert updated_models == {exported_element}

    assert (
        exported_element.labels["formula"]
        == f"get('data_source.{data_source_2.id}.field_1')"
    )
    assert (
        exported_element.series[0]["label"]["formula"]
        == f"get('data_source.{data_source_2.id}.field_2')"
    )
    assert (
        exported_element.series[0]["values"]["formula"]
        == f"get('data_source.{data_source_2.id}.field_3')"
    )
    assert exported_element.series[0]["color"] == "#2e90fa"
    assert exported_element.series[0]["chart_type"] == "BAR"
    assert exported_element.series[0]["uid"] == "61b8a893-d454-47e4-9924-8d8da62a8bd9"


@pytest.mark.django_db
def test_graph_element_update_preserves_series_uid(
    api_client, enterprise_data_fixture, enable_enterprise
):
    user, token = enterprise_data_fixture.create_user_and_token()
    page = enterprise_data_fixture.create_builder_page(user=user)
    graph = enterprise_data_fixture.create_builder_element(
        GraphElementType,
        page=page,
    )
    series_uid = "61b8a893-d454-47e4-9924-8d8da62a8bd9"

    url = reverse("api:builder:element:item", kwargs={"element_id": graph.id})
    response = api_client.patch(
        url,
        {
            "series": [
                {
                    "uid": series_uid,
                    "label": "'Count'",
                    "values": "to_array('1,2')",
                    "color": "primary",
                    "chart_type": "BAR",
                }
            ]
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    graph.refresh_from_db()
    assert graph.series[0]["uid"] == series_uid


@pytest.mark.django_db
def test_graph_element_update_generates_missing_series_uid(
    api_client, enterprise_data_fixture, enable_enterprise
):
    """Ensure older clients can omit a series UID without causing a server error."""

    user, token = enterprise_data_fixture.create_user_and_token()
    page = enterprise_data_fixture.create_builder_page(user=user)
    graph = enterprise_data_fixture.create_builder_element(GraphElementType, page=page)

    url = reverse("api:builder:element:item", kwargs={"element_id": graph.id})
    response = api_client.patch(
        url,
        {"series": [{"label": "'Count'", "values": "to_array('1,2')"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    graph.refresh_from_db()
    assert graph.series[0]["uid"] == response.json()["series"][0]["uid"]
    assert UUID(graph.series[0]["uid"])


@pytest.mark.django_db
def test_graph_element_create_requires_license(enterprise_data_fixture):
    user = enterprise_data_fixture.create_user()
    page = enterprise_data_fixture.create_builder_page(user=user)
    element_type = element_type_registry.get("graph")

    enterprise_data_fixture.delete_all_licenses()

    assert element_type.is_deactivated(page.builder.workspace)
    with pytest.raises(ElementTypeDeactivated):
        ElementService().create_element(user, element_type, page)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "series",
    [
        [{"uid": "61b8a893-d454-47e4-9924-8d8da62a8bd9"}],
        [
            {
                "uid": "61b8a893-d454-47e4-9924-8d8da62a8bd9",
                "label": "'Count'",
            }
        ],
        [
            {
                "uid": "61b8a893-d454-47e4-9924-8d8da62a8bd9",
                "values": "to_array('1,2')",
            }
        ],
    ],
)
def test_graph_element_update_rejects_incomplete_series(
    api_client, enterprise_data_fixture, enable_enterprise, series
):
    """Ensure every graph series contains both required formula fields."""

    user, token = enterprise_data_fixture.create_user_and_token()
    page = enterprise_data_fixture.create_builder_page(user=user)
    graph = enterprise_data_fixture.create_builder_element(
        GraphElementType,
        page=page,
    )

    url = reverse("api:builder:element:item", kwargs={"element_id": graph.id})
    response = api_client.patch(
        url,
        {"series": series},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


def test_graph_element_series_reports_required_formula_fields():
    serializer = GraphElementSeriesSerializer(
        data={"uid": "61b8a893-d454-47e4-9924-8d8da62a8bd9"}, partial=True
    )

    assert not serializer.is_valid()
    assert serializer.errors == {
        "label": ["This field is required."],
        "values": ["This field is required."],
    }


@pytest.mark.django_db
def test_public_elements_exclude_unlicensed_graph_element(
    api_client, enterprise_data_fixture, enable_enterprise
):
    """Ensure a graph saved before a downgrade isn't exposed publicly afterward."""

    user = enterprise_data_fixture.create_user()
    source_builder = enterprise_data_fixture.create_builder_application(user=user)
    published_builder = enterprise_data_fixture.create_builder_application(
        user=user, workspace=None
    )
    page = enterprise_data_fixture.create_builder_page(builder=published_builder)
    heading = enterprise_data_fixture.create_builder_heading_element(page=page)
    graph = enterprise_data_fixture.create_builder_element(GraphElementType, page=page)
    enterprise_data_fixture.create_builder_custom_domain(
        domain_name="test.getbaserow.io",
        builder=source_builder,
        published_to=published_builder,
    )

    enterprise_data_fixture.delete_all_licenses()

    url = reverse("api:builder:domains:list_elements", kwargs={"page_id": page.id})
    response = api_client.get(url, format="json")

    assert response.status_code == HTTP_200_OK
    assert [element["id"] for element in response.json()] == [heading.id]
    assert graph.id not in {element["id"] for element in response.json()}


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

    dispatch_context = BuilderDispatchContext(
        fake_request,
        MagicMock(
            builder=MagicMock(get_workspace=MagicMock(return_value=MagicMock(id=-1)))
        ),
    )

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
        (["image/png"], None),
        (["IMAGE/PNG"], None),
        (["image/jpeg"], TypeError),
        (["video/avi"], TypeError),
        (["application/pdf", "image/png"], None),
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

    dispatch_context = BuilderDispatchContext(
        fake_request,
        MagicMock(
            builder=MagicMock(get_workspace=MagicMock(return_value=MagicMock(id=-1)))
        ),
    )

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


@pytest.mark.parametrize(
    "allowed,content_type,expected",
    [
        (["text/*"], "text/csv", True),
        (["text/*"], "text/plain", True),
        (["TEXT/*"], "TEXT/CSV", True),
        (["text/*"], "application/pdf", False),
        (["text/*"], "textual/csv", False),
        (["application/*"], "application/pdf", True),
        (["application/*"], "image/png", False),
        (["image/*"], "image/jpeg", True),
        (["audio/*"], "audio/mpeg", True),
        (["video/*"], "video/mp4", True),
        (["*/*"], "text/csv", False),
        (["text/c*"], "text/csv", False),
        (["image/jpg"], "image/jpeg", True),
        (["image/jpeg"], "image/jpg", True),
        (["IMAGE/JPG"], "IMAGE/JPEG", True),
        (["image/jpg"], "image/png", False),
        (["image/jpeg"], "image/png", False),
        (["jpg"], "image/jpg", True),
        ([".jpg"], "image/jpeg", True),
        (["jpg"], "image/jpeg", True),
        (["jpeg"], "image/jpeg", True),
        (["jpeg"], "image/jpg", True),
        ([".jpeg"], "image/jpeg", True),
        ([".jpeg"], "image/jpg", True),
        (["jpeg"], "image/png", False),
        ([".jpeg"], "image/png", False),
        (["text/csv"], "text/csv", True),
        (["text/csv"], "text/plain", False),
        ([], "text/csv", True),
        (["image/jpg", "text/*"], "text/csv", True),
    ],
)
def test_file_input_element_allowed_content_type(allowed, content_type, expected):
    element = FileInputElement(allowed_filetypes=allowed)
    assert (
        FileInputElementType().is_allowed_content_type(element, content_type)
        is expected
    )


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

    dispatch_context = BuilderDispatchContext(
        fake_request,
        MagicMock(
            builder=MagicMock(get_workspace=MagicMock(return_value=MagicMock(id=-1)))
        ),
    )

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
@pytest.mark.parametrize(
    "allowed_filetypes,filename,content_type,image_format",
    [
        ([], "image_1.png", "image/png", "png"),
        (["image/png"], "image_1.png", "image/png", "png"),
        (["image/jpg"], "image_1.JPG", "image/jpeg", "jpeg"),
        (["image/jpeg"], "image_1.JPG", "image/jpg", "jpeg"),
        (["text/*"], "data.csv", "text/csv", None),
    ],
)
def test_dispatch_local_baserow_update_row_workflow_action_with_file(
    api_client,
    data_fixture,
    enable_enterprise,
    fake,
    allowed_filetypes,
    filename,
    content_type,
    image_format,
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
        FileInputElementType,
        user,
        page=page,
        multiple=True,
        allowed_filetypes=allowed_filetypes,
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

        content = (
            fake.image(image_format=image_format) if image_format else b"name\nAlice\n"
        )

        payload = {
            "metadata": json.dumps(
                {
                    "form_data": {
                        str(file_input_element.id): [
                            {
                                "__file__": True,
                                "name": filename,
                                "content_type": content_type,
                                "size": "1963",
                                "file": "3c913094-c69a-4fd3-b19d-c35322f7d5c5",
                            },
                        ]
                    }
                }
            ),
            "3c913094-c69a-4fd3-b19d-c35322f7d5c5": SimpleUploadedFile(
                name=filename, content=content, content_type=content_type
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
            "image_height": 256 if image_format else None,
            "image_width": 256 if image_format else None,
            "is_image": bool(image_format),
            "mime_type": f"image/{image_format}" if image_format else "text/csv",
            "name": AnyStr(),
            "size": AnyInt(),
            "uploaded_at": AnyStr(),
            "thumbnails": {
                "tiny": {
                    "height": 21,
                    "url": AnyStr(),
                    "width": 21,
                },
            }
            if image_format
            else None,
            "url": AnyStr(),
            "visible_name": filename,
        },
    ]


@pytest.mark.django_db
def test_auth_form_element_get_event_names(data_fixture):
    page = data_fixture.create_builder_page()
    auth_form = data_fixture.create_builder_element(AuthFormElementType, page=page)

    assert AuthFormElementType().get_event_names(auth_form) == [
        EventTypes.AFTER_LOGIN.value
    ]
