from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.views.decorator_value_provider_types import (
    ConditionalColorValueProviderType,
)
from rest_framework.status import HTTP_400_BAD_REQUEST

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import ViewDecoration
from baserow.contrib.database.views.registries import view_type_registry
from baserow.core.registries import ImportExportConfig
from baserow.test_utils.helpers import AnyStr


@pytest.mark.django_db
def test_import_export_grid_view_w_decorator(data_fixture):
    grid_view = data_fixture.create_grid_view(
        name="Test", order=1, filter_type="AND", filters_disabled=False
    )
    field = data_fixture.create_text_field(table=grid_view.table)
    single_select = data_fixture.create_single_select_field(table=grid_view.table)
    option = data_fixture.create_select_option(
        field=single_select, value="A", color="blue"
    )
    imported_field = data_fixture.create_text_field(table=grid_view.table)
    imported_single_select = data_fixture.create_single_select_field(
        table=grid_view.table
    )
    imported_option = data_fixture.create_select_option(
        field=imported_single_select, value="A", color="blue"
    )

    view_decoration = data_fixture.create_view_decoration(
        view=grid_view,
        type="left_border_color",
        value_provider_type="single_select_color",
        value_provider_conf={"field_id": field.id},
        order=1,
    )

    view_decoration_2 = data_fixture.create_view_decoration(
        view=grid_view,
        type="left_border_color",
        value_provider_type="conditional_color",
        value_provider_conf={
            "colors": [
                {
                    "filter_groups": [{"id": 1}],
                    "filters": [
                        # no filter type, so it will be ignored in imported value
                        {"field": field.id, "group": 1, "value": ""},
                        {
                            "type": "single_select_equal",
                            "field": single_select.id,
                            "group": 1,
                            "value": option.id,
                        },
                    ],
                },
                # no filter type, so it will be ignored in imported value
                {"filters": [{"field": field.id, "value": ""}]},
            ]
        },
        order=2,
    )

    view_decoration_3 = data_fixture.create_view_decoration(
        view=grid_view,
        type="left_border_color",
        value_provider_type="conditional_color",
        value_provider_conf={
            "colors": [
                {
                    "filters": [
                        {
                            "type": "single_select_is_any_of",
                            "field": single_select.id,
                            "group": 1,
                            "value": f"{option.id},100",
                        },
                        {
                            "type": "boolean",
                            "field": single_select.id,
                            "group": 1,
                            "value": f"true",
                        },
                        {
                            "type": "invalid_filter",
                            "field": single_select.id,
                            "group": 1,
                            "value": f"foobar",
                        },
                        {
                            "type": "single_select_is_any_of",
                            "field": single_select.id,
                            "group": 1,
                            "value": f"100,{option.id}",
                        },
                    ],
                },
            ]
        },
        order=3,
    )

    id_mapping = {
        "database_fields": {
            field.id: imported_field.id,
            single_select.id: imported_single_select.id,
        },
        "database_field_select_options": {option.id: imported_option.id},
    }

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

    imported_view_decorations = imported_grid_view.viewdecoration_set.all()
    assert view_decoration.id != imported_view_decorations[0].id
    assert view_decoration.type == imported_view_decorations[0].type
    assert (
        view_decoration.value_provider_type
        == imported_view_decorations[0].value_provider_type
    )
    assert imported_view_decorations[0].value_provider_conf == {
        "field_id": imported_field.id
    }

    assert view_decoration_2.id != imported_view_decorations[1].id
    assert view_decoration_2.type == imported_view_decorations[1].type
    assert (
        view_decoration_2.value_provider_type
        == imported_view_decorations[1].value_provider_type
    )

    assert imported_view_decorations[1].value_provider_conf["colors"] == [
        {
            "id": AnyStr(),  # a new id is generated for every inserted color
            "filters": [
                # first filter will be ignored, because it's missing
                # proper type value
                {
                    "type": "single_select_equal",
                    "field": imported_single_select.id,
                    "group": 1,
                    # filter value should be a string
                    "value": str(imported_option.id),
                },
            ],
            "filter_groups": [{"id": 1}],
        },
        {
            "id": AnyStr(),
            # empty list because filter def is missing proper type value
            "filters": [],
        },
    ]

    assert view_decoration_3.id != imported_view_decorations[2].id
    assert view_decoration_3.type == imported_view_decorations[2].type
    assert (
        view_decoration_3.value_provider_type
        == imported_view_decorations[2].value_provider_type
    )

    # test a list of values with one value id not present in the mapping
    assert imported_view_decorations[2].value_provider_conf["colors"] == [
        {
            "id": AnyStr(),  # a new id is generated for every inserted color
            "filters": [
                {
                    "type": "single_select_is_any_of",
                    "field": imported_single_select.id,
                    "group": 1,
                    # old 100 option will be scrapped, because
                    # it's not in the mapping
                    "value": f"{imported_option.id}",
                },
                # boolean should not be modified
                {
                    "type": "boolean",
                    "field": imported_single_select.id,
                    "group": 1,
                    # old 100 option will be scrapped, because
                    # it's not in the mapping
                    "value": "true",
                },
                # no invalid_filter
                {
                    "type": "single_select_is_any_of",
                    "field": imported_single_select.id,
                    "group": 1,
                    # old 100 option will be scrapped, because
                    # it's not in the mapping
                    "value": f"{imported_option.id}",
                },
            ],
        },
    ]


@pytest.mark.django_db
def test_field_type_changed_w_decoration(data_fixture):
    workspace = data_fixture.create_workspace()
    user = data_fixture.create_user(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(user=user, database=database)
    text_field = data_fixture.create_text_field(table=table)
    option_field = data_fixture.create_single_select_field(
        table=table, name="option_field", order=1
    )
    data_fixture.create_select_option(field=option_field, value="A", color="blue")

    grid_view = data_fixture.create_grid_view(
        table=table, ownership_type="collaborative"
    )

    select_view_decoration = data_fixture.create_view_decoration(
        view=grid_view,
        type="left_border_color",
        value_provider_type="single_select_color",
        value_provider_conf={"field_id": option_field.id},
        order=1,
    )

    condition_view_decoration = data_fixture.create_view_decoration(
        view=grid_view,
        type="left_border_color",
        value_provider_type="conditional_color",
        value_provider_conf={
            "colors": [
                {
                    "filter_groups": [{"id": 1}],
                    "filters": [{"field": text_field.id, "type": "equal", "group": 1}],
                },
                {"filters": [{"field": option_field.id, "type": "equal"}]},
                {
                    "filter_groups": [{"id": 2}],
                    "filters": [
                        {
                            "field": option_field.id,
                            "type": "single_select_equal",
                            "group": 2,
                        }
                    ],
                },
                {"filters": []},
            ]
        },
        order=2,
    )

    field_handler = FieldHandler()

    decorations = list(ViewDecoration.objects.all())
    assert len(decorations) == 2
    assert (
        decorations[0].value_provider_conf == select_view_decoration.value_provider_conf
    )
    assert (
        decorations[1].value_provider_conf
        == condition_view_decoration.value_provider_conf
    )

    field_handler.update_field(
        user=user, field=option_field, new_type_name="single_select"
    )

    decorations = list(ViewDecoration.objects.all())
    assert (
        decorations[0].value_provider_conf == select_view_decoration.value_provider_conf
    )
    assert (
        decorations[1].value_provider_conf
        == condition_view_decoration.value_provider_conf
    )

    field_handler.update_field(user=user, field=option_field, new_type_name="text")

    decorations = list(ViewDecoration.objects.all())
    assert decorations[0].value_provider_conf == {"field_id": None}
    assert decorations[1].value_provider_conf == {
        "colors": [
            {
                "filter_groups": [{"id": 1}],
                "filters": [
                    {"type": "equal", "field": text_field.id, "group": 1},
                ],
            },
            {"filters": [{"type": "equal", "field": option_field.id}]},
            {"filter_groups": [], "filters": []},
            {"filters": []},
        ]
    }


@pytest.mark.django_db
def test_field_deleted_w_decoration(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table)
    option_field = data_fixture.create_single_select_field(
        table=table, name="option_field", order=1
    )
    data_fixture.create_select_option(field=option_field, value="A", color="blue")

    grid_view = data_fixture.create_grid_view(table=table)

    data_fixture.create_view_decoration(
        view=grid_view,
        type="left_border_color",
        value_provider_type="single_select_color",
        value_provider_conf={"field_id": option_field.id},
        order=1,
    )

    data_fixture.create_view_decoration(
        view=grid_view,
        type="left_border_color",
        value_provider_type="conditional_color",
        value_provider_conf={
            "colors": [
                {
                    "filter_groups": [{"id": 1}],
                    "filters": [{"field": text_field.id, "type": "equal", "group": 1}],
                },
                {"filters": [{"field": option_field.id, "type": "equal"}]},
                {
                    "filter_groups": [{"id": 2}],
                    "filters": [
                        {
                            "field": option_field.id,
                            "type": "single_select_equal",
                            "group": 2,
                        }
                    ],
                },
                {"filters": []},
            ]
        },
        order=2,
    )

    field_handler = FieldHandler()

    field_handler.delete_field(user=user, field=option_field)

    decorations = list(ViewDecoration.objects.all())
    assert decorations[0].value_provider_conf == {"field_id": None}
    assert decorations[1].value_provider_conf == {
        "colors": [
            {
                "filter_groups": [{"id": 1}],
                "filters": [{"type": "equal", "field": text_field.id, "group": 1}],
            },
            {"filters": []},
            {"filter_groups": [], "filters": []},
            {"filters": []},
        ]
    }

    field_handler.delete_field(user=user, field=text_field)

    decorations = list(ViewDecoration.objects.all())
    assert decorations[0].value_provider_conf == {"field_id": None}
    assert decorations[1].value_provider_conf == {
        "colors": [
            {"filter_groups": [], "filters": []},
            {"filters": []},
            {"filter_groups": [], "filters": []},
            {"filters": []},
        ]
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_single_select_color_with_premium_license(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    grid_view = premium_data_fixture.create_grid_view(user=user)

    handler = ViewHandler()
    decoration = handler.create_decoration(
        view=grid_view,
        decorator_type_name="left_border_color",
        value_provider_type_name="single_select_color",
        value_provider_conf={},
        user=user,
    )

    assert isinstance(decoration, ViewDecoration)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_single_select_color_without_premium_license(premium_data_fixture):
    workspace = premium_data_fixture.create_workspace()
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table = premium_data_fixture.create_database_table(database=database)
    user = premium_data_fixture.create_user(
        has_active_premium_license=False, workspace=workspace
    )
    grid_view = premium_data_fixture.create_grid_view(user=user, table=table)

    handler = ViewHandler()

    with pytest.raises(FeaturesNotAvailableError):
        handler.create_decoration(
            view=grid_view,
            decorator_type_name="left_border_color",
            value_provider_type_name="single_select_color",
            value_provider_conf={"field": None},
            user=user,
        )

    decoration = handler.create_decoration(
        view=grid_view,
        decorator_type_name="left_border_color",
        value_provider_type_name="single_select_color",
        value_provider_conf={"field": None},
    )
    assert isinstance(decoration, ViewDecoration)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_single_select_color_without_premium_license_for_workspace(
    premium_data_fixture, alternative_per_workspace_license_service
):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    grid_view = premium_data_fixture.create_grid_view(user=user)

    handler = ViewHandler()

    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, [grid_view.table.database.workspace.id]
    )
    handler.create_decoration(
        view=grid_view,
        decorator_type_name="left_border_color",
        value_provider_type_name="single_select_color",
        value_provider_conf={"field": None},
        user=user,
    )

    alternative_per_workspace_license_service.restrict_user_premium_to(user, [0])
    with pytest.raises(FeaturesNotAvailableError):
        handler.create_decoration(
            view=grid_view,
            decorator_type_name="left_border_color",
            value_provider_type_name="single_select_color",
            value_provider_conf={"field": None},
            user=user,
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_conditional_color_with_premium_license(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    grid_view = premium_data_fixture.create_grid_view(user=user)

    handler = ViewHandler()
    decoration = handler.create_decoration(
        view=grid_view,
        decorator_type_name="left_border_color",
        value_provider_type_name="conditional_color",
        value_provider_conf={},
        user=user,
    )

    assert isinstance(decoration, ViewDecoration)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_conditional_color_without_premium_license(premium_data_fixture):
    user = premium_data_fixture.create_user(has_active_premium_license=False)
    grid_view = premium_data_fixture.create_grid_view(user=user)

    handler = ViewHandler()

    with pytest.raises(FeaturesNotAvailableError):
        handler.create_decoration(
            view=grid_view,
            decorator_type_name="left_border_color",
            value_provider_type_name="conditional_color",
            value_provider_conf={},
            user=user,
        )

    decoration = handler.create_decoration(
        view=grid_view,
        decorator_type_name="background_color",
        value_provider_type_name="conditional_color",
        value_provider_conf={},
    )
    assert isinstance(decoration, ViewDecoration)


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_create_conditional_color_without_premium_license_for_workspace(
    premium_data_fixture, alternative_per_workspace_license_service
):
    user = premium_data_fixture.create_user(has_active_premium_license=True)
    grid_view = premium_data_fixture.create_grid_view(user=user)

    handler = ViewHandler()

    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, [grid_view.table.database.workspace.id]
    )
    handler.create_decoration(
        view=grid_view,
        decorator_type_name="left_border_color",
        value_provider_type_name="conditional_color",
        value_provider_conf={"field": None},
        user=user,
    )

    alternative_per_workspace_license_service.restrict_user_premium_to(user, [0])
    with pytest.raises(FeaturesNotAvailableError):
        handler.create_decoration(
            view=grid_view,
            decorator_type_name="left_border_color",
            value_provider_type_name="conditional_color",
            value_provider_conf={"field": None},
            user=user,
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_color_filters_cannot_reference_non_existing_groups(
    api_client, premium_data_fixture
):
    workspace = premium_data_fixture.create_workspace()
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True, workspace=workspace
    )
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table = premium_data_fixture.create_database_table(user=user, database=database)
    text_field = premium_data_fixture.create_text_field(table=table)

    grid_view = premium_data_fixture.create_grid_view(
        table=table, ownership_type="collaborative"
    )

    decoration = premium_data_fixture.create_view_decoration(
        view=grid_view,
        type="left_border_color",
        value_provider_type="conditional_color",
        value_provider_conf={"field_id": text_field.id},
        order=1,
    )

    response = api_client.patch(
        reverse(
            "api:database:views:decoration_item",
            kwargs={"view_decoration_id": decoration.id},
        ),
        {
            "value_provider_conf": {
                "colors": [
                    {
                        "color": "light-cyan",
                        "operator": "AND",
                        "filter_groups": [],
                        "filters": [
                            {
                                "id": "1",
                                "field": text_field.id,
                                "type": "equal",
                                "value": "",
                                "preload_values": {},
                                "group": "9999",
                            }
                        ],
                        "id": "a49fa05d-7edf-4569-b829-f00c81c563eb",
                    }
                ]
            }
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response_json["detail"]["value_provider_conf"]["colors"] == [
        {
            "non_field_errors": [
                {"error": "Filter references a non-existent group.", "code": "invalid"}
            ]
        }
    ]


def test_conditional_color_value_provider_type_map_filter_from_config():
    color_conf = {
        "colors": [
            {
                "filter_groups": [{"id": 1}],
                "filters": [{"field": 1, "type": "equal", "group": 1}],
            },
            {
                "filter_groups": [{"id": 2}],
                "filters": [{"field": 2, "type": "equal", "group": 2}],
            },
            {
                "filter_groups": [{"id": 3}],
                "filters": [
                    {
                        "field": 1,
                        "type": "equal",
                        "group": 3,
                    }
                ],
            },
            {"filters": []},
        ]
    }

    def filter_fn(filter):
        if filter["field"] == 1:
            return None
        return filter

    color_conf, modified = ConditionalColorValueProviderType()._map_filter_from_config(
        color_conf, filter_fn
    )

    assert modified is True
    expected_conf = {
        "colors": [
            {"filters": [], "filter_groups": []},
            {
                "filters": [{"field": 2, "type": "equal", "group": 2}],
                "filter_groups": [{"id": 2}],
            },
            {"filters": [], "filter_groups": []},
            {"filters": []},
        ]
    }
    assert color_conf == expected_conf

    color_conf, modified = ConditionalColorValueProviderType()._map_filter_from_config(
        color_conf, filter_fn
    )

    assert modified is False
    assert color_conf == expected_conf
