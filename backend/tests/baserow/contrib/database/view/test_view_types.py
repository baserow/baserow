import secrets
from io import BytesIO
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage

import pytest
import zipstream

from baserow.contrib.database.fields.field_filters import (
    FILTER_TYPE_AND,
    FILTER_TYPE_OR,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import GalleryViewFieldOptions
from baserow.contrib.database.views.registries import (
    view_aggregation_type_registry,
    view_type_registry,
)
from baserow.contrib.database.views.view_ownership_types import (
    CollaborativeViewOwnershipType,
)
from baserow.core.models import WorkspaceUser
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.storage import ExportZipFile
from baserow.core.user_files.handler import UserFileHandler
from baserow.test_utils.helpers import ReplayValues, is_dict_subset


@pytest.mark.django_db
def test_import_export_grid_view(data_fixture):
    grid_view = data_fixture.create_grid_view(
        name="Test",
        order=1,
        filter_type="AND",
        filters_disabled=False,
        row_identifier_type="count",
    )
    field = data_fixture.create_text_field(table=grid_view.table)
    imported_field = data_fixture.create_text_field(table=grid_view.table)
    field_option = data_fixture.create_grid_view_field_option(
        grid_view=grid_view,
        field=field,
        aggregation_type="whatever",
        aggregation_raw_type="empty",
    )
    view_filter = data_fixture.create_view_filter(
        view=grid_view, field=field, value="test", type="equal"
    )
    view_sort = data_fixture.create_view_sort(view=grid_view, field=field, order="ASC")

    view_decoration = data_fixture.create_view_decoration(
        view=grid_view,
        value_provider_conf={"config": 12},
    )

    id_mapping = {"database_fields": {field.id: imported_field.id}}

    grid_view_type = view_type_registry.get("grid")
    serialized = grid_view_type.export_serialized(
        grid_view, ImportExportConfig(include_permission_data=False), None, None, None
    )
    imported_grid_view = grid_view_type.import_serialized(
        grid_view.table,
        serialized,
        ImportExportConfig(include_permission_data=False),
        id_mapping,
        None,
        None,
    )

    assert grid_view.id != imported_grid_view.id
    assert grid_view.name == imported_grid_view.name
    assert grid_view.order == imported_grid_view.order
    assert grid_view.filter_type == imported_grid_view.filter_type
    assert grid_view.filters_disabled == imported_grid_view.filters_disabled
    assert grid_view.row_identifier_type == imported_grid_view.row_identifier_type
    assert imported_grid_view.viewfilter_set.all().count() == 1
    assert imported_grid_view.viewsort_set.all().count() == 1

    imported_view_filter = imported_grid_view.viewfilter_set.all().first()
    assert view_filter.id != imported_view_filter.id
    assert imported_field.id == imported_view_filter.field_id
    assert view_filter.value == imported_view_filter.value
    assert view_filter.type == imported_view_filter.type

    imported_view_sort = imported_grid_view.viewsort_set.all().first()
    assert view_sort.id != imported_view_sort.id
    assert imported_field.id == imported_view_sort.field_id
    assert view_sort.order == imported_view_sort.order

    imported_view_decoration = imported_grid_view.viewdecoration_set.all().first()
    assert view_decoration.id != imported_view_decoration.id
    assert view_decoration.type == imported_view_decoration.type
    assert (
        view_decoration.value_provider_type
        == imported_view_decoration.value_provider_type
    )
    assert (
        imported_view_decoration.value_provider_conf
        == imported_view_decoration.value_provider_conf
    )
    assert view_decoration.order == imported_view_decoration.order

    imported_field_options = imported_grid_view.get_field_options()
    imported_field_option = imported_field_options[0]
    assert field_option.id != imported_field_option.id
    assert imported_field.id == imported_field_option.field_id
    assert field_option.width == imported_field_option.width
    assert field_option.hidden == imported_field_option.hidden
    assert field_option.order == imported_field_option.order
    assert field_option.aggregation_type == imported_field_option.aggregation_type
    assert (
        field_option.aggregation_raw_type == imported_field_option.aggregation_raw_type
    )


@pytest.mark.django_db
def test_grid_view_field_type_change(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field1 = data_fixture.create_text_field(table=table)
    field2 = data_fixture.create_text_field(table=table)
    grid_view = data_fixture.create_grid_view(table=table, create_options=False)

    field_option1 = data_fixture.create_grid_view_field_option(
        grid_view=grid_view,
        field=field1,
        aggregation_type="whatever",
        aggregation_raw_type="empty_count",
    )

    field_option2 = data_fixture.create_grid_view_field_option(
        grid_view=grid_view,
        field=field2,
        aggregation_type="",
        aggregation_raw_type="",
    )

    field_handler = FieldHandler()

    options = grid_view.get_field_options()
    assert options[0].aggregation_raw_type == "empty_count"

    # Force field incompatibility for the test
    empty_count = view_aggregation_type_registry.get("empty_count")
    empty_count.field_is_compatible = lambda _: False

    field_handler.update_field(
        user=user,
        field=field1,
        new_type_name="boolean",
    )

    # We also test a field with field option but without aggregation_raw_type
    field_handler.update_field(
        user=user,
        field=field2,
        new_type_name="boolean",
    )

    empty_count.field_is_compatible = lambda _: True

    options = grid_view.get_field_options()
    assert options[0].aggregation_raw_type == ""


@pytest.mark.django_db
def test_import_export_gallery_view(data_fixture, tmpdir):
    user = data_fixture.create_user()

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    table = data_fixture.create_database_table(user=user)
    file_field = data_fixture.create_file_field(table=table)
    gallery_view = data_fixture.create_gallery_view(
        table=table, card_cover_image_field=file_field
    )
    text_field = data_fixture.create_text_field(table=table)
    field_option = data_fixture.create_gallery_view_field_option(
        gallery_view, text_field, order=1
    )

    files_buffer = BytesIO()
    gallery_view_type = view_type_registry.get("gallery")

    with ZipFile(files_buffer, "a", ZIP_DEFLATED, False) as files_zip:
        serialized = gallery_view_type.export_serialized(
            gallery_view,
            ImportExportConfig(include_permission_data=False),
            None,
            files_zip=files_zip,
            storage=storage,
        )

    assert serialized["id"] == gallery_view.id
    assert serialized["type"] == "gallery"
    assert serialized["name"] == gallery_view.name
    assert serialized["order"] == 0
    assert serialized["card_cover_image_field_id"] == file_field.id
    assert len(serialized["field_options"]) == 2
    assert serialized["field_options"][0]["id"] == field_option.id
    assert serialized["field_options"][0]["field_id"] == field_option.field_id
    assert serialized["field_options"][0]["hidden"] is True
    assert serialized["field_options"][0]["order"] == 1

    imported_single_select_field = data_fixture.create_text_field(table=table)
    imported_file_field = data_fixture.create_file_field(table=table)
    id_mapping = {
        "database_fields": {
            text_field.id: imported_single_select_field.id,
            file_field.id: imported_file_field.id,
        }
    }

    with ZipFile(files_buffer, "a", ZIP_DEFLATED, False) as files_zip:
        imported_gallery_view = gallery_view_type.import_serialized(
            gallery_view.table,
            serialized,
            ImportExportConfig(include_permission_data=False),
            id_mapping,
            files_zip,
            storage,
        )

    assert gallery_view.id != imported_gallery_view.id
    assert gallery_view.name == imported_gallery_view.name
    assert gallery_view.order == imported_gallery_view.order
    assert imported_gallery_view.card_cover_image_field.id == imported_file_field.id
    imported_field_options = imported_gallery_view.get_field_options()
    assert len(imported_field_options) == 2
    imported_field_option = imported_field_options[0]
    assert field_option.id != imported_field_option.id
    assert field_option.hidden == imported_field_option.hidden
    assert field_option.order == imported_field_option.order


@pytest.mark.django_db
def test_newly_created_gallery_view(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, primary=True)
    data_fixture.create_text_field(table=table)
    data_fixture.create_text_field(table=table)
    data_fixture.create_text_field(table=table)

    handler = ViewHandler()
    handler.create_view(user, table=table, type_name="gallery")

    all_field_options = (
        GalleryViewFieldOptions.objects.all()
        .order_by("field_id")
        .values_list("hidden", flat=True)
    )
    assert list(all_field_options) == [False, False, False, True]


@pytest.mark.django_db
def test_convert_card_cover_image_field_to_another(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    file_field = data_fixture.create_file_field(table=table)
    gallery_view = data_fixture.create_gallery_view(
        table=table, card_cover_image_field=file_field
    )
    FieldHandler().update_field(user=user, field=file_field, new_type_name="text")
    gallery_view.refresh_from_db()
    assert gallery_view.card_cover_image_field_id is None


@pytest.mark.django_db
def test_convert_card_cover_image_field_deleted(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    file_field = data_fixture.create_file_field(table=table)
    gallery_view = data_fixture.create_gallery_view(
        table=table, card_cover_image_field=file_field
    )
    FieldHandler().delete_field(user=user, field=file_field)
    gallery_view.refresh_from_db()
    assert gallery_view.card_cover_image_field_id is None


@pytest.mark.django_db
def test_convert_to_incompatible_field_in_form_view(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    form_view = data_fixture.create_form_view(table=table)
    options = data_fixture.create_form_view_field_option(form_view, field, enabled=True)
    options_2 = data_fixture.create_form_view_field_option(
        form_view, field_2, enabled=True
    )

    FieldHandler().update_field(
        user=user,
        table=table,
        field=field,
        new_type_name="created_on",
    )
    options.refresh_from_db()
    options_2.refresh_from_db()
    assert options.enabled is False
    assert options_2.enabled is True


@pytest.mark.django_db
def test_import_export_form_view(data_fixture, tmpdir):
    user = data_fixture.create_user()

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()
    user_file = handler.upload_user_file(
        user, "test.jpg", ContentFile(b"Hello World"), storage=storage
    )

    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(
        table=table,
        slug="public-test-slug",
        public=True,
        title="Title",
        description="Description",
        cover_image=user_file,
        logo_image=user_file,
        submit_text="My Submit",
        submit_action="REDIRECT",
        submit_action_message="TEst message",
        submit_action_redirect_url="https://localhost",
    )
    text_field = data_fixture.create_text_field(table=table)
    imported_text_field = data_fixture.create_text_field(table=form_view.table)
    field_option = data_fixture.create_form_view_field_option(
        form_view,
        text_field,
        required=True,
        enabled=True,
        name="Test name",
        description="Field description",
        order=1,
    )
    condition = data_fixture.create_form_view_field_options_condition(
        field_option=field_option, field=text_field, group=None
    )
    condition_2 = data_fixture.create_form_view_field_options_condition(
        field_option=field_option,
        field=text_field,
        type="multiple_select_has",
        value="1",
        group=None,
    )

    files_buffer = BytesIO()
    form_view_type = view_type_registry.get("form")

    zip_file = ExportZipFile(
        compress_level=settings.BASEROW_DEFAULT_ZIP_COMPRESS_LEVEL,
        compress_type=zipstream.ZIP_DEFLATED,
    )

    serialized = form_view_type.export_serialized(
        form_view,
        ImportExportConfig(include_permission_data=False),
        None,
        files_zip=zip_file,
        storage=storage,
    )

    for chunk in zip_file:
        files_buffer.write(chunk)

    assert serialized["id"] == form_view.id
    assert serialized["type"] == "form"
    assert serialized["name"] == form_view.name
    assert serialized["order"] == 0
    assert "slug" not in serialized
    assert serialized["public"] == form_view.public
    assert serialized["title"] == form_view.title
    assert serialized["cover_image"] == {
        "name": form_view.cover_image.name,
        "original_name": form_view.cover_image.original_name,
    }
    assert serialized["logo_image"] == {
        "name": form_view.logo_image.name,
        "original_name": form_view.logo_image.original_name,
    }
    assert serialized["submit_text"] == form_view.submit_text
    assert serialized["submit_action"] == form_view.submit_action
    assert serialized["submit_action_message"] == form_view.submit_action_message
    assert (
        serialized["submit_action_redirect_url"] == form_view.submit_action_redirect_url
    )
    assert len(serialized["field_options"]) == 1
    assert serialized["field_options"][0]["id"] == field_option.id
    assert serialized["field_options"][0]["field_id"] == field_option.field_id
    assert serialized["field_options"][0]["name"] == field_option.name
    assert serialized["field_options"][0]["description"] == field_option.description
    assert serialized["field_options"][0]["enabled"] == field_option.enabled
    assert serialized["field_options"][0]["required"] == field_option.required
    assert serialized["field_options"][0]["conditions"] == [
        {
            "id": condition.id,
            "field": condition.field_id,
            "type": condition.type,
            "group": None,
            "value": condition.value,
        },
        {
            "id": condition_2.id,
            "field": condition_2.field_id,
            "type": condition_2.type,
            "group": None,
            "value": condition_2.value,
        },
    ]

    with ZipFile(files_buffer, "r", ZIP_DEFLATED, False) as zip_file:
        assert zip_file.read(user_file.name) == b"Hello World"
        assert len(zip_file.infolist()) == 1

    id_mapping = {
        "database_fields": {text_field.id: imported_text_field.id},
        "database_field_select_options": {1: 2},
    }

    with ZipFile(files_buffer, "a", ZIP_DEFLATED, False) as files_zip:
        imported_form_view = form_view_type.import_serialized(
            form_view.table,
            serialized,
            ImportExportConfig(include_permission_data=False),
            id_mapping,
            files_zip,
            storage,
        )

    assert form_view.id != imported_form_view.id
    assert form_view.name == imported_form_view.name
    assert form_view.order == imported_form_view.order
    assert form_view.slug != imported_form_view.slug
    assert len(secrets.token_urlsafe()) == len(imported_form_view.slug)
    assert form_view.public == imported_form_view.public
    assert form_view.title == imported_form_view.title
    assert form_view.description == imported_form_view.description
    assert form_view.cover_image_id == imported_form_view.cover_image_id
    assert form_view.logo_image_id == imported_form_view.logo_image_id
    assert form_view.submit_text == imported_form_view.submit_text
    assert form_view.submit_action == imported_form_view.submit_action
    assert form_view.submit_action_message == imported_form_view.submit_action_message
    assert (
        form_view.submit_action_redirect_url
        == imported_form_view.submit_action_redirect_url
    )

    imported_field_options = imported_form_view.get_field_options()
    assert len(imported_field_options) == 1
    imported_field_option = imported_field_options[0]
    assert field_option.id != imported_field_option.id
    assert imported_text_field.id == imported_field_option.field_id
    assert field_option.name == imported_field_option.name
    assert field_option.description == imported_field_option.description
    assert field_option.enabled == imported_field_option.enabled
    assert field_option.required == imported_field_option.required
    assert field_option.order == imported_field_option.order

    imported_field_option_conditions = imported_field_option.conditions.all()
    assert len(imported_field_option_conditions) == 2
    imported_field_option_condition = imported_field_option_conditions[0]
    assert imported_field_option_condition.field_id == imported_text_field.id
    assert imported_field_option_condition.field_option_id == imported_field_option.id
    assert imported_field_option_condition.type == condition.type
    assert imported_field_option_condition.value == condition.value
    imported_field_option_condition_2 = imported_field_option_conditions[1]
    assert imported_field_option_condition_2.field_id == imported_text_field.id
    assert imported_field_option_condition_2.field_option_id == imported_field_option.id
    assert imported_field_option_condition_2.type == condition_2.type
    assert imported_field_option_condition_2.value == "2"


@pytest.mark.django_db
def test_import_export_form_view_with_grouped_conditions(data_fixture, tmpdir):
    user = data_fixture.create_user()

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()
    user_file = handler.upload_user_file(
        user, "test.jpg", ContentFile(b"Hello World"), storage=storage
    )

    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(
        table=table,
        slug="public-test-slug",
        public=True,
        title="Title",
        description="Description",
        cover_image=user_file,
        logo_image=user_file,
        submit_text="My Submit",
        submit_action="REDIRECT",
        submit_action_message="TEst message",
        submit_action_redirect_url="https://localhost",
    )
    text_field = data_fixture.create_text_field(table=table)
    bool_field = data_fixture.create_boolean_field(table=table)

    imported_text_field = data_fixture.create_text_field(table=form_view.table)
    imported_bool_field = data_fixture.create_boolean_field(table=form_view.table)

    # use ReplayValues helper to check for group patterns. Each condition group will
    # have a different id after export/import, but the distribution will be similar
    r_groups = ReplayValues()

    field_option_text = data_fixture.create_form_view_field_option(
        form_view,
        text_field,
        required=True,
        enabled=True,
        name="Test name",
        description="Field description",
        order=1,
    )

    field_option_bool = data_fixture.create_form_view_field_option(
        form_view,
        bool_field,
        required=True,
        enabled=True,
        name="Bool field",
        description="Field description",
        condition_type=FILTER_TYPE_OR,
        order=2,
    )

    condition_group = data_fixture.create_form_view_field_options_condition_group(
        user=user, field_option=field_option_text
    )
    condition_group_2 = data_fixture.create_form_view_field_options_condition_group(
        user=user, field_option=field_option_text, filter_type=FILTER_TYPE_OR
    )
    condition_group_3 = data_fixture.create_form_view_field_options_condition_group(
        user=user, field_option=field_option_bool
    )

    condition = data_fixture.create_form_view_field_options_condition(
        field_option=field_option_text, field=text_field, group=r_groups.record(None)
    )
    condition_2 = data_fixture.create_form_view_field_options_condition(
        field_option=field_option_text,
        field=text_field,
        type="multiple_select_has",
        value="1",
        group=r_groups.record(condition_group),
    )
    condition_3 = data_fixture.create_form_view_field_options_condition(
        field_option=field_option_text,
        field=text_field,
        type="contains_not",
        value="2",
        group=r_groups.record(condition_group_2),
    )

    condition_4 = data_fixture.create_form_view_field_options_condition(
        field_option=field_option_text,
        field=text_field,
        type="contains_not",
        value="3",
        group=r_groups.record(condition_group_2),
    )
    condition_5 = data_fixture.create_form_view_field_options_condition(
        field_option=field_option_bool,
        field=text_field,
        type="contains",
        value="4",
        group=r_groups.record(condition_group_3),
    )
    condition_6 = data_fixture.create_form_view_field_options_condition(
        field_option=field_option_bool,
        field=text_field,
        type="contains",
        value="5",
        group=r_groups.record(condition_group_3),
    )

    recorded_groups_created = r_groups.stored
    r_groups.reset()

    files_buffer = BytesIO()
    form_view_type = view_type_registry.get("form")

    zip_file = ExportZipFile(
        compress_level=settings.BASEROW_DEFAULT_ZIP_COMPRESS_LEVEL,
        compress_type=zipstream.ZIP_DEFLATED,
    )

    serialized = form_view_type.export_serialized(
        form_view,
        ImportExportConfig(include_permission_data=False),
        None,
        files_zip=zip_file,
        storage=storage,
    )

    for chunk in zip_file:
        files_buffer.write(chunk)

    assert serialized["id"] == form_view.id
    assert serialized["type"] == "form"
    assert serialized["name"] == form_view.name
    assert serialized["order"] == 0
    assert "slug" not in serialized
    assert serialized["public"] == form_view.public
    assert serialized["title"] == form_view.title
    assert serialized["cover_image"] == {
        "name": form_view.cover_image.name,
        "original_name": form_view.cover_image.original_name,
    }
    assert serialized["logo_image"] == {
        "name": form_view.logo_image.name,
        "original_name": form_view.logo_image.original_name,
    }
    assert serialized["submit_text"] == form_view.submit_text
    assert serialized["submit_action"] == form_view.submit_action
    assert serialized["submit_action_message"] == form_view.submit_action_message
    assert (
        serialized["submit_action_redirect_url"] == form_view.submit_action_redirect_url
    )
    assert len(serialized["field_options"]) == 2
    assert serialized["field_options"][0]["id"] == field_option_text.id
    assert serialized["field_options"][0]["field_id"] == field_option_text.field_id
    assert serialized["field_options"][0]["name"] == field_option_text.name
    assert (
        serialized["field_options"][0]["description"] == field_option_text.description
    )
    assert serialized["field_options"][0]["enabled"] == field_option_text.enabled
    assert serialized["field_options"][0]["required"] == field_option_text.required
    assert serialized["field_options"][0]["condition_type"] == FILTER_TYPE_AND
    assert serialized["field_options"][0]["condition_groups"] == [
        {
            "filter_type": "AND",
            "id": condition_group.id,
            "parent_group": None,
        },
        {
            "filter_type": "OR",
            "id": condition_group_2.id,
            "parent_group": None,
        },
    ]
    assert serialized["field_options"][0]["conditions"] == [
        {
            "id": condition.id,
            "field": condition.field_id,
            "type": condition.type,
            "group": r_groups.record(None),
            "value": condition.value,
        },
        {
            "id": condition_2.id,
            "field": condition_2.field_id,
            "type": condition_2.type,
            "group": r_groups.record(condition_group.id),
            "value": condition_2.value,
        },
        {
            "id": condition_3.id,
            "field": condition_3.field_id,
            "type": condition_3.type,
            "group": r_groups.record(condition_group_2.id),
            "value": condition_3.value,
        },
        {
            "id": condition_4.id,
            "field": condition_4.field_id,
            "type": condition_4.type,
            "group": r_groups.record(condition_group_2.id),
            "value": condition_4.value,
        },
    ]

    assert serialized["field_options"][1]["id"] == field_option_bool.id
    assert serialized["field_options"][1]["field_id"] == field_option_bool.field_id
    assert serialized["field_options"][1]["name"] == field_option_bool.name
    assert (
        serialized["field_options"][1]["description"] == field_option_bool.description
    )
    assert serialized["field_options"][1]["enabled"] == field_option_bool.enabled
    assert serialized["field_options"][1]["required"] == field_option_bool.required
    assert serialized["field_options"][1]["condition_type"] == FILTER_TYPE_OR
    assert serialized["field_options"][1]["conditions"] == [
        {
            "id": condition_5.id,
            "field": condition_5.field_id,
            "type": condition_5.type,
            "group": r_groups.record(condition_group_3.id),
            "value": condition_5.value,
        },
        {
            "id": condition_6.id,
            "field": condition_6.field_id,
            "type": condition_6.type,
            "group": r_groups.record(condition_group_3.id),
            "value": condition_6.value,
        },
    ]

    assert r_groups.stored == recorded_groups_created

    with ZipFile(files_buffer, "r", ZIP_DEFLATED, False) as zip_file:
        assert zip_file.read(user_file.name) == b"Hello World"
        assert len(zip_file.infolist()) == 1

    id_mapping = {
        "database_fields": {
            text_field.id: imported_text_field.id,
            bool_field.id: imported_bool_field.id,
        },
        "database_field_select_options": {1: 2},
    }

    with ZipFile(files_buffer, "a", ZIP_DEFLATED, False) as files_zip:
        imported_form_view = form_view_type.import_serialized(
            form_view.table,
            serialized,
            ImportExportConfig(include_permission_data=False),
            id_mapping,
            files_zip,
            storage,
        )

    form_expected = {
        "name": imported_form_view.name,
        "order": imported_form_view.order,
        "slug": form_view.slug,
    }
    assert form_view.id != imported_form_view.id
    assert form_view.slug != imported_form_view.slug
    assert is_dict_subset(form_expected, vars(form_view))

    imported_field_options = imported_form_view.get_field_options()
    assert len(imported_field_options) == 2

    fields_and_options = [field_option_text, field_option_bool]

    r_groups.reset()
    for source_option_field, imported_field_option in zip(
        fields_and_options, imported_field_options
    ):
        field_expected = {
            k: getattr(source_option_field, k)
            for k in ["name", "description", "enabled", "required", "order"]
        }

        assert source_option_field.id != imported_field_option.id
        assert is_dict_subset(field_expected, vars(imported_field_option))

        imported_field_option_conditions = imported_field_option.conditions.all()
        for cond in imported_field_option_conditions:
            r_groups.record(cond.group)
    assert r_groups.stored == recorded_groups_created


@pytest.mark.django_db
def test_import_export_form_view_with_conditions_in_groups(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )

    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)
    field_1 = data_fixture.create_text_field(table=table)
    field_2 = data_fixture.create_text_field(table=table)
    field_3 = data_fixture.create_text_field(table=table)

    field_1_option = data_fixture.create_form_view_field_option(
        form_view,
        field_1,
        required=True,
        enabled=True,
        name="Field ",
        order=1,
    )
    field_2_option = data_fixture.create_form_view_field_option(
        form_view,
        field_2,
        required=True,
        enabled=True,
        name="Field 2",
        condition_type=FILTER_TYPE_AND,
        order=2,
    )
    field_3_option = data_fixture.create_form_view_field_option(
        form_view,
        field_3,
        required=True,
        enabled=True,
        name="Field 3",
        condition_type=FILTER_TYPE_OR,
        order=3,
    )

    field_2_condition_group = (
        data_fixture.create_form_view_field_options_condition_group(
            user=user, field_option=field_2_option, filter_type=FILTER_TYPE_AND
        )
    )
    field_3_condition_group = (
        data_fixture.create_form_view_field_options_condition_group(
            user=user, field_option=field_3_option, filter_type=FILTER_TYPE_OR
        )
    )

    field_2_condition = data_fixture.create_form_view_field_options_condition(
        field_option=field_2_option, field=field_2, group=None
    )
    field_3_condition = data_fixture.create_form_view_field_options_condition(
        field_option=field_3_option, field=field_3, group_id=field_3_condition_group.id
    )

    database_type = application_type_registry.get("database")
    config = ImportExportConfig(include_permission_data=True)
    serialized = database_type.export_serialized(table.database, config)

    imported_workspace = data_fixture.create_workspace(user=user)

    id_mapping = {}
    imported_database = database_type.import_serialized(
        imported_workspace,
        serialized,
        config,
        id_mapping,
        None,
        None,
    )

    imported_table = imported_database.table_set.all().first()
    imported_view = imported_table.view_set.all().first().specific
    imported_field_options = list(imported_view.active_field_options)

    imported_field_1_condition_groups = imported_field_options[0].condition_groups.all()
    imported_field_2_condition_groups = imported_field_options[1].condition_groups.all()
    imported_field_3_condition_groups = imported_field_options[2].condition_groups.all()

    assert len(imported_field_1_condition_groups) == 0
    assert len(imported_field_2_condition_groups) == 1
    assert len(imported_field_3_condition_groups) == 1

    assert imported_field_2_condition_groups[0].filter_type == FILTER_TYPE_AND
    assert imported_field_3_condition_groups[0].filter_type == FILTER_TYPE_OR

    imported_field_1_conditions = imported_field_options[0].conditions.all()
    imported_field_2_conditions = imported_field_options[1].conditions.all()
    imported_field_3_conditions = imported_field_options[2].conditions.all()

    assert len(imported_field_1_conditions) == 0
    assert len(imported_field_2_conditions) == 1
    assert len(imported_field_3_conditions) == 1

    assert imported_field_2_conditions[0].group_id is None
    assert (
        imported_field_3_conditions[0].group_id
        == imported_field_3_condition_groups[0].id
    )


@pytest.mark.django_db
def test_import_export_form_view_with_allowed_select_options(data_fixture, api_client):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )

    table = data_fixture.create_database_table(user=user)
    form_view = data_fixture.create_form_view(table=table)
    field_1 = data_fixture.create_single_select_field(table=table)
    option_1 = data_fixture.create_select_option(field=field_1)
    option_2 = data_fixture.create_select_option(field=field_1)
    option_3 = data_fixture.create_select_option(field=field_1)

    field_1_option = data_fixture.create_form_view_field_option(
        form_view,
        field_1,
        required=True,
        enabled=True,
        name="Field ",
        order=1,
        include_all_select_options=False,
    )
    field_1_option.allowed_select_options.set([option_1.id, option_2.id])

    database_type = application_type_registry.get("database")
    config = ImportExportConfig(include_permission_data=True)
    serialized = database_type.export_serialized(table.database, config)

    imported_workspace = data_fixture.create_workspace(user=user)

    id_mapping = {}
    imported_database = database_type.import_serialized(
        imported_workspace,
        serialized,
        config,
        id_mapping,
        None,
        None,
    )

    imported_table = imported_database.table_set.all().first()
    imported_view = imported_table.view_set.all().first().specific
    imported_field_option = list(imported_view.active_field_options)[0]
    imported_field = imported_field_option.field
    select_options = imported_field.select_options.all()

    assert imported_field_option.include_all_select_options is False
    assert [s.id for s in imported_field_option.allowed_select_options.all()] == [
        select_options[0].id,
        select_options[1].id,
    ]


@pytest.mark.django_db
def test_import_export_view_ownership_type(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    user2 = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    grid_view = data_fixture.create_grid_view(
        table=table,
        name="Test",
        order=1,
        filter_type="AND",
        filters_disabled=False,
        row_identifier_type="count",
    )
    grid_view.ownership_type = "personal"
    grid_view.owned_by = user2
    grid_view.save()
    grid_view_type = view_type_registry.get("grid")

    serialized = grid_view_type.export_serialized(
        grid_view, ImportExportConfig(include_permission_data=False), None, None
    )
    imported_grid_view = grid_view_type.import_serialized(
        grid_view.table,
        serialized,
        ImportExportConfig(include_permission_data=False),
        {},
        None,
        None,
    )

    assert grid_view.id != imported_grid_view.id
    assert grid_view.ownership_type == imported_grid_view.ownership_type
    assert grid_view.owned_by == imported_grid_view.owned_by

    # view should not be imported if the user is gone

    WorkspaceUser.objects.filter(user=user2).delete()

    imported_grid_view = grid_view_type.import_serialized(
        grid_view.table,
        serialized,
        ImportExportConfig(include_permission_data=False),
        {},
        None,
        None,
    )

    assert imported_grid_view is None

    # created by is not set
    grid_view.owned_by = None
    grid_view.ownership_type = "collaborative"
    grid_view.save()

    serialized = grid_view_type.export_serialized(
        grid_view, ImportExportConfig(include_permission_data=False), None, None
    )
    imported_grid_view = grid_view_type.import_serialized(
        grid_view.table,
        serialized,
        ImportExportConfig(include_permission_data=False),
        {},
        None,
        None,
    )

    assert grid_view.id != imported_grid_view.id
    assert imported_grid_view.ownership_type == "collaborative"
    assert imported_grid_view.owned_by is None


@pytest.mark.django_db
def test_import_export_view_ownership_type_created_by_backward_compatible(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    user2 = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    grid_view = data_fixture.create_grid_view(table=table, owned_by=user2)

    grid_view_type = view_type_registry.get("grid")
    serialized = grid_view_type.export_serialized(
        grid_view, ImportExportConfig(include_permission_data=False), None, None
    )

    # Owned by was called created_by before, so test if everything still works
    # when importing the old name:
    serialized["created_by"] = serialized.pop("owned_by")

    imported_grid_view = grid_view_type.import_serialized(
        grid_view.table,
        serialized,
        ImportExportConfig(include_permission_data=False),
        {},
        None,
        None,
    )

    assert grid_view.owned_by == imported_grid_view.owned_by


@pytest.mark.django_db
def test_import_export_view_ownership_type_not_in_registry(data_fixture):
    ownership_types = {"collaborative": CollaborativeViewOwnershipType()}
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    user2 = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    grid_view = data_fixture.create_grid_view(
        table=table,
        name="Test",
        order=1,
        filter_type="AND",
        filters_disabled=False,
        row_identifier_type="count",
    )
    grid_view.ownership_type = "personal"
    grid_view.owned_by = user2
    grid_view.save()
    grid_view_type = view_type_registry.get("grid")
    serialized = grid_view_type.export_serialized(
        grid_view, ImportExportConfig(include_permission_data=False), None, None
    )

    with patch(
        "baserow.contrib.database.views.registries.view_ownership_type_registry.registry",
        ownership_types,
    ):
        imported_grid_view = grid_view_type.import_serialized(
            grid_view.table,
            serialized,
            ImportExportConfig(include_permission_data=False),
            {},
            None,
            None,
        )

        assert imported_grid_view is None


@pytest.mark.django_db
@pytest.mark.parametrize("view_type, default", [("grid", False), ("gallery", True)])
def test_new_fields_are_hidden_by_default_in_views_if_public(
    view_type, default, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table)

    create_view_func = getattr(data_fixture, f"create_{view_type}_view")
    public_view = create_view_func(table=table, public=True, create_options=False)

    options = public_view.get_field_options()
    assert len(options) == 0

    options = public_view.get_field_options(create_if_missing=True)
    assert len(options) == 1
    assert options[0].hidden is True

    private_view = create_view_func(table=table, create_options=False)

    options = private_view.get_field_options()
    assert len(options) == 0
    options = private_view.get_field_options(create_if_missing=True)
    assert len(options) == 1
    assert options[0].hidden is default


@pytest.mark.django_db
@pytest.mark.parametrize("view_type,default", [("grid", False), ("gallery", True)])
def test_new_fields_are_hidden_by_default_in_views_if_other_fields_are_hidden(
    view_type, default, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table)

    # let's use the handler here because options are set to visible in the view_created
    # view type callback
    view = ViewHandler().create_view(user, table, type_name=view_type)

    options = view.get_field_options(create_if_missing=True)
    assert len(options) == 1
    assert options[0].hidden is False

    data_fixture.create_text_field(table=table)
    options = view.get_field_options(create_if_missing=True)
    assert len(options) == 2
    assert options[0].hidden is False
    assert options[1].hidden is default

    # If we hide a field, a new field will be hidden by default
    options[1].hidden = True
    options[1].save()

    data_fixture.create_text_field(table=table)
    options = view.get_field_options(create_if_missing=True)
    assert len(options) == 3
    assert options[0].hidden is False
    assert options[1].hidden is True
    assert options[2].hidden is True
