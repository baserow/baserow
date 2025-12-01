import json
import uuid
from copy import deepcopy
from io import BytesIO
from unittest.mock import patch

from django.conf import settings
from django.core.files.storage import FileSystemStorage

import pytest
import zipstream
from PIL import Image

from baserow.contrib.builder.application_types import BuilderApplicationType
from baserow.contrib.builder.builder_beta_init_application import (
    BuilderApplicationTypeInitApplication,
)
from baserow.contrib.builder.elements.models import (
    ColumnElement,
    Element,
    HeadingElement,
    LinkElement,
    TableElement,
    TextElement,
)
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.theme.handler import ThemeHandler
from baserow.contrib.builder.workflow_actions.handler import (
    BuilderWorkflowActionHandler,
)
from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.contrib.database.application_types import DatabaseApplicationType
from baserow.core.action.models import Action
from baserow.core.action.registries import action_type_registry
from baserow.core.actions import CreateApplicationActionType
from baserow.core.db import specific_iterator
from baserow.core.formula import BaserowFormulaObject
from baserow.core.formula.field import BASEROW_FORMULA_VERSION_INITIAL
from baserow.core.formula.types import BASEROW_FORMULA_MODE_SIMPLE
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.storage import ExportZipFile
from baserow.core.trash.handler import TrashHandler
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_sources.registries import DEFAULT_USER_ROLE_PREFIX
from baserow.test_utils.helpers import AnyStr
from baserow_enterprise.integrations.local_baserow.user_source_types import (
    LocalBaserowUserSourceType,
)


def test_builder_application_type_import_application_priority():
    database_type = application_type_registry.get(DatabaseApplicationType.type)
    builder_type = application_type_registry.get(BuilderApplicationType.type)
    manual_ordering = [database_type, builder_type]
    expected_ordering = sorted(
        application_type_registry.get_all(),
        key=lambda element_type: element_type.import_application_priority,
        reverse=True,
    )
    assert manual_ordering == expected_ordering[0 : len(manual_ordering)], (
        "The application types ordering are expected to be: "
        "databases first, then applications, then everything else."
    )


@pytest.mark.django_db
def test_builder_application_type_init_application(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)

    assert Page.objects_without_shared.count() == 0

    BuilderApplicationType().init_application(user, builder)

    assert Page.objects_without_shared.count() == 2  # With demo data


@pytest.mark.django_db
def test_builder_application_type_init_application_customers_table_use(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(user=user, workspace=workspace)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)

    from baserow.contrib.builder.builder_beta_init_application import (
        BuilderApplicationTypeInitApplication,
    )

    builder_init = BuilderApplicationTypeInitApplication(user, builder)

    # Correct: name, workspace. Wrong: fields (none).
    table = data_fixture.create_database_table(name="Customers", database=database)
    assert table.field_set.count() == 0
    assert builder_init.get_target_table() is None
    table.delete()

    # Correct: name, field names, workspace. Wrong: fields types.
    table = data_fixture.create_database_table(name="Customers", database=database)
    data_fixture.create_number_field(table=table, name="Name")
    data_fixture.create_number_field(table=table, name="Last name")
    assert builder_init.get_target_table() is None
    table.delete()

    # Correct: name, single field, workspace. Wrong: Last name field.
    table = data_fixture.create_database_table(name="Customers", database=database)
    data_fixture.create_text_field(table=table, name="Name")
    assert builder_init.get_target_table() is None
    table.delete()

    # Correct: nearly all. Wrong: workspace.
    table = data_fixture.create_database_table(name="Customers")
    data_fixture.create_text_field(table=table, name="Name")
    data_fixture.create_text_field(table=table, name="Last name")
    assert builder_init.get_target_table() is None
    table.delete()

    # Everything matches.
    table = data_fixture.create_database_table(name="Customers", database=database)
    data_fixture.create_text_field(table=table, name="Name")
    data_fixture.create_text_field(table=table, name="Last name")
    assert builder_init.get_target_table() == table
    table.delete()


@pytest.mark.django_db
def test_builder_application_export(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)

    shared_page = builder.shared_page
    page1 = data_fixture.create_builder_page(builder=builder)
    page2 = data_fixture.create_builder_page(builder=builder)

    builder.login_page = page2
    builder.save()

    element1 = data_fixture.create_builder_heading_element(
        page=page1, level=2, value="foo"
    )
    element2 = data_fixture.create_builder_text_element(page=page1)
    element3 = data_fixture.create_builder_heading_element(page=page2)
    element_container = data_fixture.create_builder_column_element(
        page=page1, column_amount=3, column_gap=50
    )
    element_inside_container = data_fixture.create_builder_text_element(
        page=page1, parent_element=element_container, place_in_container="0"
    )

    integration = data_fixture.create_local_baserow_integration(
        application=builder, authorized_user=user, name="test"
    )

    user_source = data_fixture.create_user_source_with_first_type(
        application=builder, user=user, integration=integration
    )

    auth_provider = data_fixture.create_app_auth_provider_with_first_type(
        user_source=user_source
    )

    shared_datasource = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=shared_page, user=user, name="Shared", integration=integration
    )
    datasource1 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page1, user=user, name="source 1", integration=integration
    )
    datasource2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page2, user=user, name="source 2", integration=integration
    )
    datasource3 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page2, user=user, name="source 3", integration=integration
    )

    element4 = data_fixture.create_builder_table_element(
        page=page2, data_source=datasource3, items_per_page=42
    )
    element4.property_options.create(
        schema_property="location", filterable=True, sortable=True, searchable=False
    )

    workflow_action_1 = data_fixture.create_notification_workflow_action(
        page=page1,
        element=element1,
        event=EventTypes.CLICK,
        description="hello",
        title="there",
    )

    serialized = BuilderApplicationType().export_serialized(
        builder, ImportExportConfig(include_permission_data=True)
    )

    # To make sure a really JSON file can be imported
    serialized = json.loads(json.dumps(serialized))

    page_2_serialized = {
        "id": page2.id,
        "name": page2.name,
        "order": page2.order,
        "path": page2.path,
        "path_params": page2.path_params,
        "query_params": [],
        "visibility": Page.VISIBILITY_TYPES.ALL.value,
        "role_type": Page.ROLE_TYPES.ALLOW_ALL.value,
        "roles": [],
        "shared": False,
        "workflow_actions": [],
        "data_sources": [
            {
                "id": datasource2.id,
                "name": "source 2",
                "order": "1.00000000000000000000",
                "service": {
                    "id": datasource2.service.id,
                    "sample_data": None,
                    "integration_id": integration.id,
                    "filter_type": "AND",
                    "filters": [],
                    "row_id": datasource2.service.row_id,
                    "view_id": None,
                    "table_id": None,
                    "search_query": datasource2.service.search_query,
                    "type": "local_baserow_get_row",
                },
            },
            {
                "id": datasource3.id,
                "name": "source 3",
                "order": "2.00000000000000000000",
                "service": {
                    "id": datasource3.service.id,
                    "sample_data": None,
                    "integration_id": integration.id,
                    "default_result_count": 20,
                    "filters": [],
                    "sortings": [],
                    "view_id": None,
                    "table_id": None,
                    "search_query": datasource3.service.search_query,
                    "filter_type": "AND",
                    "type": "local_baserow_list_rows",
                },
            },
        ],
        "elements": [
            {
                "id": element3.id,
                "type": "heading",
                "order": str(element3.order),
                "parent_element_id": None,
                "place_in_container": None,
                "visibility": "all",
                "visibility_condition": BaserowFormulaObject(
                    formula="",
                    mode=BASEROW_FORMULA_MODE_SIMPLE,
                    version=BASEROW_FORMULA_VERSION_INITIAL,
                ),
                "css_classes": "",
                "styles": {},
                "style_border_top_color": "border",
                "style_border_top_size": 0,
                "style_padding_top": 10,
                "style_margin_top": 0,
                "style_border_bottom_color": "border",
                "style_border_bottom_size": 0,
                "style_padding_bottom": 10,
                "style_margin_bottom": 0,
                "style_border_left_color": "border",
                "style_border_left_size": 0,
                "style_padding_left": 20,
                "style_margin_left": 0,
                "style_border_right_color": "border",
                "style_border_right_size": 0,
                "style_padding_right": 20,
                "style_margin_right": 0,
                "style_background_radius": 0,
                "style_border_radius": 0,
                "style_background": "none",
                "style_background_color": "#ffffffff",
                "style_background_file_id": None,
                "style_background_mode": "fill",
                "style_width": "normal",
                "style_width_child": "normal",
                "value": element3.value,
                "level": element3.level,
                "roles": [],
                "role_type": "allow_all",
            },
            {
                "id": element4.id,
                "type": "table",
                "schema_property": None,
                "button_load_more_label": element4.button_load_more_label,
                "order": str(element4.order),
                "roles": [],
                "role_type": "allow_all",
                "orientation": {
                    "smartphone": "horizontal",
                    "tablet": "horizontal",
                    "desktop": "horizontal",
                },
                "parent_element_id": None,
                "place_in_container": None,
                "css_classes": "",
                "visibility": "all",
                "visibility_condition": BaserowFormulaObject(
                    formula="",
                    mode=BASEROW_FORMULA_MODE_SIMPLE,
                    version=BASEROW_FORMULA_VERSION_INITIAL,
                ),
                "styles": {},
                "style_border_top_color": "border",
                "style_border_top_size": 0,
                "style_padding_top": 10,
                "style_margin_top": 0,
                "style_border_bottom_color": "border",
                "style_border_bottom_size": 0,
                "style_padding_bottom": 10,
                "style_margin_bottom": 0,
                "style_border_left_color": "border",
                "style_border_left_size": 0,
                "style_padding_left": 20,
                "style_margin_left": 0,
                "style_border_right_color": "border",
                "style_border_right_size": 0,
                "style_padding_right": 20,
                "style_margin_right": 0,
                "style_background_radius": 0,
                "style_border_radius": 0,
                "style_background": "none",
                "style_background_color": "#ffffffff",
                "style_background_file_id": None,
                "style_background_mode": "fill",
                "style_width": "normal",
                "style_width_child": "normal",
                "items_per_page": 42,
                "data_source_id": element4.data_source.id,
                "fields": [
                    {
                        "name": f.name,
                        "type": f.type,
                        "config": f.config,
                        "uid": str(f.uid),
                        "styles": {},
                    }
                    for f in element4.fields.all()
                ],
                "property_options": [
                    {
                        "schema_property": po.schema_property,
                        "filterable": po.filterable,
                        "sortable": po.sortable,
                        "searchable": po.searchable,
                    }
                    for po in element4.property_options.all()
                ],
            },
        ],
    }

    reference = {
        "pages": [
            {
                "id": shared_page.id,
                "name": shared_page.name,
                "order": shared_page.order,
                "path": shared_page.path,
                "path_params": shared_page.path_params,
                "query_params": [],
                "shared": True,
                "visibility": Page.VISIBILITY_TYPES.ALL.value,
                "role_type": Page.ROLE_TYPES.ALLOW_ALL.value,
                "roles": [],
                "workflow_actions": [],
                "data_sources": [
                    {
                        "id": shared_datasource.id,
                        "name": shared_datasource.name,
                        "order": "1.00000000000000000000",
                        "service": {
                            "id": shared_datasource.service.id,
                            "sample_data": None,
                            "integration_id": integration.id,
                            "filter_type": "AND",
                            "filters": [],
                            "row_id": shared_datasource.service.row_id,
                            "view_id": None,
                            "table_id": None,
                            "search_query": shared_datasource.service.search_query,
                            "type": "local_baserow_get_row",
                        },
                    },
                ],
                "elements": [],
            },
            {
                "id": page1.id,
                "name": page1.name,
                "order": page1.order,
                "path": page1.path,
                "path_params": page1.path_params,
                "query_params": [],
                "shared": False,
                "visibility": Page.VISIBILITY_TYPES.ALL.value,
                "role_type": Page.ROLE_TYPES.ALLOW_ALL.value,
                "roles": [],
                "workflow_actions": [
                    {
                        "id": workflow_action_1.id,
                        "order": 0,
                        "type": "notification",
                        "element_id": element1.id,
                        "event": EventTypes.CLICK.value,
                        "page_id": page1.id,
                        "description": workflow_action_1.description,
                        "title": workflow_action_1.title,
                    }
                ],
                "data_sources": [
                    {
                        "id": datasource1.id,
                        "name": "source 1",
                        "order": "1.00000000000000000000",
                        "service": {
                            "id": datasource1.service.id,
                            "sample_data": None,
                            "integration_id": integration.id,
                            "filter_type": "AND",
                            "filters": [],
                            "row_id": datasource1.service.row_id,
                            "view_id": None,
                            "table_id": None,
                            "search_query": datasource1.service.search_query,
                            "type": "local_baserow_get_row",
                        },
                    },
                ],
                "elements": [
                    {
                        "id": element1.id,
                        "type": "heading",
                        "order": str(element1.order),
                        "parent_element_id": None,
                        "place_in_container": None,
                        "css_classes": "",
                        "visibility": "all",
                        "visibility_condition": BaserowFormulaObject(
                            formula="",
                            mode=BASEROW_FORMULA_MODE_SIMPLE,
                            version=BASEROW_FORMULA_VERSION_INITIAL,
                        ),
                        "styles": {},
                        "style_border_top_color": "border",
                        "style_border_top_size": 0,
                        "style_padding_top": 10,
                        "style_margin_top": 0,
                        "style_border_bottom_color": "border",
                        "style_border_bottom_size": 0,
                        "style_padding_bottom": 10,
                        "style_margin_bottom": 0,
                        "style_border_left_color": "border",
                        "style_border_left_size": 0,
                        "style_padding_left": 20,
                        "style_margin_left": 0,
                        "style_border_right_color": "border",
                        "style_border_right_size": 0,
                        "style_padding_right": 20,
                        "style_margin_right": 0,
                        "style_background_radius": 0,
                        "style_border_radius": 0,
                        "style_background": "none",
                        "style_background_color": "#ffffffff",
                        "style_background_file_id": None,
                        "style_background_mode": "fill",
                        "style_width": "normal",
                        "style_width_child": "normal",
                        "value": element1.value,
                        "level": element1.level,
                        "roles": [],
                        "role_type": "allow_all",
                    },
                    {
                        "id": element2.id,
                        "type": "text",
                        "order": str(element2.order),
                        "parent_element_id": None,
                        "place_in_container": None,
                        "css_classes": "",
                        "visibility": "all",
                        "visibility_condition": BaserowFormulaObject(
                            formula="",
                            mode=BASEROW_FORMULA_MODE_SIMPLE,
                            version=BASEROW_FORMULA_VERSION_INITIAL,
                        ),
                        "styles": {},
                        "style_border_top_color": "border",
                        "style_border_top_size": 0,
                        "style_padding_top": 10,
                        "style_margin_top": 0,
                        "style_border_bottom_color": "border",
                        "style_border_bottom_size": 0,
                        "style_padding_bottom": 10,
                        "style_margin_bottom": 0,
                        "style_border_left_color": "border",
                        "style_border_left_size": 0,
                        "style_padding_left": 20,
                        "style_margin_left": 0,
                        "style_border_right_color": "border",
                        "style_border_right_size": 0,
                        "style_padding_right": 20,
                        "style_margin_right": 0,
                        "style_background_radius": 0,
                        "style_border_radius": 0,
                        "style_background": "none",
                        "style_background_color": "#ffffffff",
                        "style_background_file_id": None,
                        "style_background_mode": "fill",
                        "style_width": "normal",
                        "style_width_child": "normal",
                        "value": element2.value,
                        "roles": [],
                        "role_type": "allow_all",
                        "format": "plain",
                    },
                    {
                        "id": element_container.id,
                        "type": "column",
                        "parent_element_id": None,
                        "place_in_container": None,
                        "css_classes": "",
                        "visibility": "all",
                        "visibility_condition": BaserowFormulaObject(
                            formula="",
                            mode=BASEROW_FORMULA_MODE_SIMPLE,
                            version=BASEROW_FORMULA_VERSION_INITIAL,
                        ),
                        "styles": {},
                        "style_border_top_color": "border",
                        "style_border_top_size": 0,
                        "style_padding_top": 10,
                        "style_margin_top": 0,
                        "style_border_bottom_color": "border",
                        "style_border_bottom_size": 0,
                        "style_padding_bottom": 10,
                        "style_margin_bottom": 0,
                        "style_border_left_color": "border",
                        "style_border_left_size": 0,
                        "style_padding_left": 20,
                        "style_margin_left": 0,
                        "style_border_right_color": "border",
                        "style_border_right_size": 0,
                        "style_padding_right": 20,
                        "style_margin_right": 0,
                        "style_background_radius": 0,
                        "style_border_radius": 0,
                        "style_background": "none",
                        "style_background_color": "#ffffffff",
                        "style_background_file_id": None,
                        "style_background_mode": "fill",
                        "style_width": "normal",
                        "style_width_child": "normal",
                        "order": str(element_container.order),
                        "column_amount": 3,
                        "column_gap": 50,
                        "alignment": "top",
                        "roles": [],
                        "role_type": "allow_all",
                    },
                    {
                        "id": element_inside_container.id,
                        "type": "text",
                        "parent_element_id": element_container.id,
                        "place_in_container": "0",
                        "css_classes": "",
                        "visibility": "all",
                        "visibility_condition": BaserowFormulaObject(
                            formula="",
                            mode=BASEROW_FORMULA_MODE_SIMPLE,
                            version=BASEROW_FORMULA_VERSION_INITIAL,
                        ),
                        "styles": {},
                        "style_border_top_color": "border",
                        "style_border_top_size": 0,
                        "style_padding_top": 10,
                        "style_margin_top": 0,
                        "style_border_bottom_color": "border",
                        "style_border_bottom_size": 0,
                        "style_padding_bottom": 10,
                        "style_margin_bottom": 0,
                        "style_border_left_color": "border",
                        "style_border_left_size": 0,
                        "style_padding_left": 20,
                        "style_margin_left": 0,
                        "style_border_right_color": "border",
                        "style_border_right_size": 0,
                        "style_padding_right": 20,
                        "style_margin_right": 0,
                        "style_background_radius": 0,
                        "style_border_radius": 0,
                        "style_background": "none",
                        "style_background_color": "#ffffffff",
                        "style_background_file_id": None,
                        "style_background_mode": "fill",
                        "style_width": "normal",
                        "style_width_child": "normal",
                        "order": str(element_inside_container.order),
                        "value": element_inside_container.value,
                        "roles": [],
                        "role_type": "allow_all",
                        "format": "plain",
                    },
                ],
            },
            page_2_serialized,
        ],
        "integrations": [
            {
                "authorized_user": None,
                "id": integration.id,
                "name": "test",
                "order": "1.00000000000000000000",
                "type": "local_baserow",
            },
        ],
        "user_sources": [
            {
                "email_field_id": None,
                "id": user_source.id,
                "integration_id": integration.id,
                "name": "",
                "name_field_id": None,
                "order": "1.00000000000000000000",
                "role_field_id": None,
                "table_id": None,
                "type": "local_baserow",
                "uid": AnyStr(),
                "auth_providers": [
                    {
                        "id": auth_provider.id,
                        "type": auth_provider.get_type().type,
                        "domain": None,
                        "enabled": True,
                        "password_field_id": None,
                    }
                ],
            },
        ],
        "theme": {
            "primary_color": "#5190efff",
            "secondary_color": "#0eaa42ff",
            "border_color": "#d7d8d9ff",
            "main_success_color": "#12D452",
            "main_error_color": "#FF5A4A",
            "main_warning_color": "#FCC74A",
            "body_font_family": "inter",
            "body_font_size": 14,
            "body_font_weight": "regular",
            "body_text_color": "#070810ff",
            "body_text_alignment": "left",
            "heading_1_font_family": "inter",
            "heading_1_font_size": 24,
            "heading_1_font_weight": "bold",
            "heading_1_text_color": "#070810ff",
            "heading_1_text_alignment": "left",
            "heading_1_text_decoration": [False, False, False, False],
            "heading_2_font_family": "inter",
            "heading_2_font_size": 20,
            "heading_2_font_weight": "semi-bold",
            "heading_2_text_color": "#070810ff",
            "heading_2_text_alignment": "left",
            "heading_2_text_decoration": [False, False, False, False],
            "heading_3_font_family": "inter",
            "heading_3_font_size": 16,
            "heading_3_font_weight": "medium",
            "heading_3_text_color": "#070810ff",
            "heading_3_text_alignment": "left",
            "heading_3_text_decoration": [False, False, False, False],
            "heading_4_font_family": "inter",
            "heading_4_font_size": 16,
            "heading_4_font_weight": "medium",
            "heading_4_text_color": "#070810ff",
            "heading_4_text_alignment": "left",
            "heading_4_text_decoration": [False, False, False, False],
            "heading_5_font_family": "inter",
            "heading_5_font_size": 14,
            "heading_5_font_weight": "regular",
            "heading_5_text_color": "#070810ff",
            "heading_5_text_alignment": "left",
            "heading_5_text_decoration": [False, False, False, False],
            "heading_6_font_family": "inter",
            "heading_6_font_size": 14,
            "heading_6_font_weight": "regular",
            "heading_6_text_color": "#202128",
            "heading_6_text_alignment": "left",
            "heading_6_text_decoration": [False, False, False, False],
            "button_font_family": "inter",
            "button_font_size": 13,
            "button_font_weight": "regular",
            "button_alignment": "left",
            "button_text_alignment": "center",
            "button_width": "auto",
            "custom_colors": [],
            "button_background_color": "primary",
            "button_text_color": "#ffffffff",
            "button_border_color": "border",
            "button_border_size": 0,
            "button_border_radius": 4,
            "button_vertical_padding": 12,
            "button_horizontal_padding": 12,
            "button_hover_background_color": "#96baf6ff",
            "button_hover_text_color": "#ffffffff",
            "button_hover_border_color": "border",
            "button_active_background_color": "#4783db",
            "button_active_text_color": "#ffffffff",
            "button_active_border_color": "#275d9f",
            "link_font_family": "inter",
            "link_font_size": 13,
            "link_font_weight": "regular",
            "link_text_alignment": "left",
            "link_text_color": "primary",
            "link_hover_text_color": "#96baf6ff",
            "link_active_text_color": "#275d9f",
            "link_active_text_decoration": [True, False, False, False],
            "link_default_text_decoration": [True, False, False, False],
            "link_hover_text_decoration": [True, False, False, False],
            "image_alignment": "left",
            "image_border_radius": 0,
            "image_max_width": 100,
            "image_max_height": None,
            "image_constraint": "contain",
            "page_background_color": "#ffffffff",
            "page_background_file_id": None,
            "page_background_mode": "tile",
            "input_background_color": "#FFFFFFFF",
            "input_border_color": "#000000FF",
            "input_border_radius": 0,
            "input_border_size": 1,
            "input_font_family": "inter",
            "input_font_size": 13,
            "input_font_weight": "regular",
            "input_horizontal_padding": 12,
            "input_text_color": "#070810FF",
            "input_vertical_padding": 8,
            "label_font_family": "inter",
            "label_font_size": 13,
            "label_font_weight": "medium",
            "label_text_color": "#070810FF",
            "table_border_color": "#000000FF",
            "table_border_radius": 0,
            "table_border_size": 1,
            "table_cell_alternate_background_color": "transparent",
            "table_cell_background_color": "transparent",
            "table_cell_horizontal_padding": 20,
            "table_cell_alignment": "left",
            "table_cell_vertical_padding": 10,
            "table_header_background_color": "#edededff",
            "table_header_font_family": "inter",
            "table_header_font_size": 13,
            "table_header_font_weight": "semi-bold",
            "table_header_text_alignment": "left",
            "table_header_text_color": "#000000ff",
            "table_horizontal_separator_color": "#000000FF",
            "table_horizontal_separator_size": 1,
            "table_vertical_separator_color": "#000000FF",
            "table_vertical_separator_size": 0,
        },
        "id": builder.id,
        "name": builder.name,
        "order": builder.order,
        "type": "builder",
        "favicon_file": None,
        "login_page": page_2_serialized,
    }

    assert serialized == reference


PAGE_2_IMPORT_REFERENCE = {
    "id": 998,
    "name": "Megan Clark",
    "order": 2,
    "path": "/test2",
    "path_params": {},
    "workflow_actions": [],
    "shared": False,
    "visibility": Page.VISIBILITY_TYPES.ALL.value,
    "role_type": Page.ROLE_TYPES.ALLOW_ALL.value,
    "roles": [],
    "elements": [
        {
            "id": 997,
            "type": "heading",
            "parent_element_id": None,
            "place_in_container": None,
            "style_background": "none",
            "style_background_color": "#ffffffff",
            "style_border_bottom_color": "border",
            "style_border_bottom_size": 0,
            "style_border_top_color": "border",
            "style_border_top_size": 0,
            "style_width": "normal",
            "style_width_child": "normal",
            "order": 1,
            "value": "",
            "level": 1,
            "roles": [],
            "role_type": "allow_all",
        }
    ],
    "data_sources": [
        {
            "id": 1,
            "name": "source 2",
            "order": "1.00000000000000000000",
            "service": {
                "id": 1,
                "integration_id": 42,
                "row_id": "",
                "view_id": None,
                "table_id": None,
                "search_query": "",
                "filter_type": "AND",
                "type": "local_baserow_get_row",
            },
        },
        {
            "id": 3,
            "name": "source 3",
            "order": "2.00000000000000000000",
            "service": {
                "id": 2,
                "default_result_count": 20,
                "integration_id": 42,
                "view_id": None,
                "table_id": None,
                "search_query": "",
                "filter_type": "AND",
                "type": "local_baserow_list_rows",
            },
        },
    ],
}

IMPORT_REFERENCE = {
    "pages": [
        {
            "id": 999,
            "name": "Tammy Hall",
            "order": 1,
            "path": "/test",
            "path_params": {},
            "query_params": [],
            "visibility": Page.VISIBILITY_TYPES.ALL.value,
            "role_type": Page.ROLE_TYPES.ALLOW_ALL.value,
            "roles": [],
            "workflow_actions": [
                {
                    "id": 123,
                    "order": 1,
                    "page_id": 999,
                    "element_id": 998,
                    "event": "click",
                    "type": "notification",
                    "description": "'hello'",
                    "title": "'there'",
                }
            ],
            "elements": [
                {
                    "id": 998,
                    "type": "heading",
                    "parent_element_id": None,
                    "place_in_container": None,
                    "style_background": "none",
                    "style_background_color": "#ffffffff",
                    "style_border_bottom_color": "border",
                    "style_border_bottom_size": 0,
                    "style_border_top_color": "border",
                    "style_border_top_size": 0,
                    "style_width": "normal",
                    "style_width_child": "normal",
                    "order": 1,
                    "value": "'foo'",
                    "level": 2,
                    "roles": [],
                    "role_type": "allow_all",
                },
                {
                    "id": 999,
                    "type": "text",
                    "parent_element_id": None,
                    "place_in_container": None,
                    "style_background": "none",
                    "style_background_color": "#ffffffff",
                    "style_border_bottom_color": "border",
                    "style_border_bottom_size": 0,
                    "style_border_top_color": "border",
                    "style_border_top_size": 0,
                    "style_width": "normal",
                    "style_width_child": "normal",
                    "order": 2,
                    "value": "",
                    "roles": [],
                    "role_type": "allow_all",
                },
                {
                    "id": 1000,
                    "type": "table",
                    "parent_element_id": None,
                    "place_in_container": None,
                    "style_background": "none",
                    "style_background_color": "#ffffffff",
                    "style_border_bottom_color": "border",
                    "style_border_bottom_size": 0,
                    "style_border_top_color": "border",
                    "style_border_top_size": 0,
                    "style_width": "normal",
                    "style_width_child": "normal",
                    "items_per_page": 42,
                    "order": 2.5,
                    "data_source_id": 5,
                    "roles": [],
                    "role_type": "allow_all",
                    "fields": [
                        {
                            "name": "F 1",
                            "type": "text",
                            "styles": {},
                            "config": {"value": "get('current_record.field_25')"},
                            "uid": str(uuid.uuid4()),
                        },
                        {
                            "name": "F 2",
                            "type": "link",
                            "styles": {},
                            "uid": str(uuid.uuid4()),
                            "config": {
                                "page_parameters": [],
                                # "query_parameters": [],
                                "navigation_type": "custom",
                                "navigate_to_page_id": None,
                                "navigate_to_url": "get('current_record.field_25')",
                                "link_name": "'Test'",
                                "target": "self",
                                "variant": LinkElement.VARIANTS.BUTTON,
                            },
                        },
                    ],
                    "property_options": [],
                },
                {
                    "id": 502,
                    "type": "text",
                    "parent_element_id": 500,
                    "place_in_container": "1",
                    "style_background": "none",
                    "style_background_color": "#ffffffff",
                    "style_border_bottom_color": "border",
                    "style_border_bottom_size": 0,
                    "style_border_top_color": "border",
                    "style_border_top_size": 0,
                    "style_width": "normal",
                    "style_width_child": "normal",
                    "style_padding_top": 10,
                    "style_padding_bottom": 10,
                    "order": 1.5,
                    "value": "'test'",
                    "roles": [],
                    "role_type": "allow_all",
                },
                {
                    "id": 500,
                    "type": "column",
                    "parent_element_id": None,
                    "place_in_container": None,
                    "style_background": "none",
                    "style_background_color": "#ffffffff",
                    "style_border_bottom_color": "border",
                    "style_border_bottom_size": 0,
                    "style_border_top_color": "border",
                    "style_border_top_size": 0,
                    "style_width": "normal",
                    "style_width_child": "normal",
                    "style_padding_top": 10,
                    "style_padding_bottom": 10,
                    "order": 3,
                    "column_amount": 3,
                    "column_gap": 50,
                    "alignment": "top",
                    "roles": [],
                    "role_type": "allow_all",
                },
                {
                    "id": 501,
                    "type": "text",
                    "parent_element_id": 500,
                    "place_in_container": "0",
                    "style_background": "none",
                    "style_background_color": "#ffffffff",
                    "style_border_bottom_color": "border",
                    "style_border_bottom_size": 0,
                    "style_border_top_color": "border",
                    "style_border_top_size": 0,
                    "style_width": "normal",
                    "style_width_child": "normal",
                    "style_padding_top": 10,
                    "style_padding_bottom": 10,
                    "order": 1,
                    "value": "'test'",
                    "roles": [],
                    "role_type": "allow_all",
                },
            ],
            "data_sources": [
                {
                    "id": 4,
                    "name": "source 0",
                    "order": "1.00000000000000000000",
                    "service": None,
                },
                {
                    "id": 5,
                    "name": "source 1",
                    "order": "2.00000000000000000000",
                    "service": {
                        "id": 17,
                        "integration_id": None,
                        "view_id": None,
                        "table_id": None,
                        "search_query": "",
                        "filter_type": "AND",
                        "type": "local_baserow_list_rows",
                    },
                },
            ],
        },
        PAGE_2_IMPORT_REFERENCE,
    ],
    "integrations": [
        {
            "authorized_user": "test@baserow.io",
            "id": 42,
            "name": "test",
            "order": "1.00000000000000000000",
            "type": "local_baserow",
        },
    ],
    "user_sources": [
        {
            "auth_providers": [],
            "email_field_id": None,
            "id": 42,
            "integration_id": 42,
            "name": "My user source",
            "name_field_id": None,
            "order": "1.00000000000000000000",
            "table_id": None,
            "type": "local_baserow",
        },
    ],
    "theme": {
        "body_text_color": "#ccccccff",
        "body_font_size": 14,
        "body_text_alignment": "left",
        "primary_color": "#ccccccff",
        "secondary_color": "#ccccccff",
        "border_color": "#ccccccff",
        "heading_1_font_size": 25,
        "heading_1_text_color": "#ccccccff",
        "heading_1_text_alignment": "left",
        "heading_2_font_size": 21,
        "heading_2_text_color": "#ccccccff",
        "heading_2_text_alignment": "left",
        "heading_3_font_size": 17,
        "heading_3_text_color": "#ccccccff",
        "heading_3_text_alignment": "left",
        "heading_4_font_size": 16,
        "heading_4_text_color": "#ccccccff",
        "heading_4_text_alignment": "left",
        "heading_5_font_size": 14,
        "heading_5_text_color": "#ccccccff",
        "heading_5_text_alignment": "left",
        "heading_6_font_size": 14,
        "heading_6_text_color": "#ccccccff",
        "heading_6_text_alignment": "left",
        "button_background_color": "#ccccccff",
        "button_hover_background_color": "#ccccccff",
        "button_alignment": "left",
        "button_width": "auto",
        "image_alignment": "left",
        "image_constraint": "contain",
        "image_max_height": None,
        "image_max_width": 100,
        "link_alignment": "left",
        "link_text_color": "primary",
        "link_hover_text_color": "#ccccccff",
        "link_active_text_color": "#275d9f",
    },
    "id": 999,
    "name": "Holly Sherman",
    "order": 0,
    "type": "builder",
    "login_page": PAGE_2_IMPORT_REFERENCE,
}


@pytest.mark.django_db
def test_builder_application_import(data_fixture):
    user = data_fixture.create_user(email="test@baserow.io")
    workspace = data_fixture.create_workspace(user=user)

    config = ImportExportConfig(include_permission_data=True)
    serialized_values = IMPORT_REFERENCE.copy()
    builder = BuilderApplicationType().import_serialized(
        workspace, serialized_values, config, {}
    )

    assert builder.id != serialized_values["id"]
    assert builder.visible_pages.count() == 2
    # ensure we have the shared page even if it's not in the reference
    assert builder.page_set.filter(shared=True).count() == 1

    assert builder.integrations.count() == 1
    first_integration = builder.integrations.first().specific
    assert first_integration.authorized_user.id == user.id

    assert builder.user_sources.count() == 1

    [page1, page2] = builder.visible_pages.all()

    assert page1.element_set.count() == 6
    assert page2.element_set.count() == 1

    assert page1.datasource_set.count() == 2
    assert page2.datasource_set.count() == 2

    assert builder.login_page == page2

    first_data_source = page2.datasource_set.first()
    assert first_data_source.name == "source 2"
    assert first_data_source.service.integration.id == first_integration.id

    typography_config_block = builder.typographythemeconfigblock
    assert typography_config_block.heading_1_text_color == "#ccccccff"
    assert typography_config_block.heading_1_font_size == 25
    assert typography_config_block.heading_2_text_color == "#ccccccff"
    assert typography_config_block.heading_2_font_size == 21
    assert typography_config_block.heading_3_text_color == "#ccccccff"
    assert typography_config_block.heading_3_font_size == 17

    color_config_block = builder.colorthemeconfigblock
    assert color_config_block.primary_color == "#ccccccff"
    assert color_config_block.secondary_color == "#ccccccff"
    assert color_config_block.border_color == "#ccccccff"

    button_config_block = builder.buttonthemeconfigblock
    assert button_config_block.button_background_color == "#ccccccff"
    assert button_config_block.button_hover_background_color == "#ccccccff"

    [
        element1,
        element_inside_container,
        element_inside_container2,
        element2,
        table_element,
        container_element,
    ] = specific_iterator(page1.element_set.all())

    assert isinstance(element1, HeadingElement)
    assert isinstance(element2, TextElement)
    assert isinstance(container_element, ColumnElement)
    assert isinstance(table_element, TableElement)

    assert table_element.fields.count() == 2
    assert table_element.items_per_page == 42

    assert element1.order == 1
    assert element1.level == 2

    assert element_inside_container.parent_element.specific == container_element
    assert element_inside_container2.parent_element.specific == container_element

    [workflow_action] = BuilderWorkflowActionHandler().get_workflow_actions(page1)

    assert workflow_action.element_id == element1.id
    assert workflow_action.description["formula"] == "'hello'"
    assert workflow_action.title["formula"] == "'there'"


IMPORT_REFERENCE_COMPLEX = {
    "pages": [
        {
            "id": 998,
            "name": "Megan Clark",
            "order": 2,
            "path": "/test2",
            "path_params": {},
            "workflow_actions": [],
            "visibility": Page.VISIBILITY_TYPES.ALL.value,
            "role_type": Page.ROLE_TYPES.ALLOW_ALL.value,
            "roles": [],
            "elements": [
                {
                    "id": 997,
                    "type": "heading",
                    "parent_element_id": None,
                    "place_in_container": None,
                    "style_background": "none",
                    "style_background_color": "#ffffffff",
                    "style_border_bottom_color": "border",
                    "style_border_bottom_size": 0,
                    "style_border_top_color": "border",
                    "style_border_top_size": 0,
                    "style_width": "normal",
                    "style_width_child": "normal",
                    "order": 1,
                    "value": "",
                    "level": 1,
                    "roles": [],
                    "role_type": "allow_all",
                }
            ],
            "data_sources": [
                {
                    "id": 1,
                    "name": "source 2",
                    "order": "1.00000000000000000000",
                    "service": {
                        "id": 1,
                        "integration_id": 42,
                        "row_id": "",
                        "view_id": None,
                        "table_id": None,
                        "search_query": "",
                        "filter_type": "AND",
                        "type": "local_baserow_get_row",
                    },
                },
                {
                    "id": 3,
                    "name": "source 3",
                    "order": "2.00000000000000000000",
                    "service": {
                        "id": 2,
                        "integration_id": 42,
                        "view_id": None,
                        "table_id": None,
                        "search_query": "",
                        "filter_type": "AND",
                        "type": "local_baserow_list_rows",
                    },
                },
            ],
        },
    ],
    "integrations": [
        {
            "authorized_user": "test@baserow.io",
            "id": 42,
            "name": "test",
            "order": "1.00000000000000000000",
            "type": "local_baserow",
        },
    ],
    "user_sources": [
        {
            "auth_providers": [],
            "email_field_id": None,
            "id": 42,
            "integration_id": 42,
            "name": "My user source",
            "name_field_id": None,
            "order": "1.00000000000000000000",
            "table_id": None,
            "type": "local_baserow",
        },
    ],
    "theme": {
        "primary_color": "#ccccccff",
        "secondary_color": "#ccccccff",
        "border_color": "#ccccccff",
        "heading_1_font_size": 25,
        "heading_1_text_color": "#ccccccff",
        "heading_2_font_size": 21,
        "heading_2_color": "#ccccccff",  # Old property name
        "heading_3_font_size": 17,
        "heading_3_color": "#ccccccff",
    },
    "id": 999,
    "name": "Holly Sherman",
    "order": 0,
    "type": "builder",
}


@pytest.mark.django_db
def test_builder_application_import_with_complex_elements(data_fixture):
    user = data_fixture.create_user(email="test@baserow.io")
    workspace = data_fixture.create_workspace(user=user)

    config = ImportExportConfig(include_permission_data=True)
    serialized_values = IMPORT_REFERENCE_COMPLEX.copy()
    builder = BuilderApplicationType().import_serialized(
        workspace, serialized_values, config, {}
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "page_property,value",
    [
        ("visibility", Page.VISIBILITY_TYPES.ALL),
        ("role_type", Page.ROLE_TYPES.ALLOW_ALL),
        ("roles", []),
    ],
)
def test_builder_application_imports_page_with_default_visibility(
    data_fixture, page_property, value
):
    """
    Ensure that the importer sets default values for Page Visibility when the
    Page Visibility related values are missing in the exported data.
    """

    user = data_fixture.create_user(email="test@baserow.io")
    workspace = data_fixture.create_workspace(user=user)

    config = ImportExportConfig(include_permission_data=True)
    serialized_values = deepcopy(IMPORT_REFERENCE)

    first_page = serialized_values["pages"][0]
    del first_page[page_property]

    builder = BuilderApplicationType().import_serialized(
        workspace, serialized_values, config, {}
    )

    page = builder.visible_pages.first()

    assert getattr(page, page_property) == value


@pytest.mark.django_db
def test_builder_application_doesnt_import_favicon_file(data_fixture):
    """
    Ensure the importer doesn't attempt to import the favicon_file if it
    doesn't exist in the serialized values.
    """

    user = data_fixture.create_user(email="test@baserow.io")
    workspace = data_fixture.create_workspace(user=user)

    config = ImportExportConfig(include_permission_data=True)
    serialized_values = IMPORT_REFERENCE.copy()
    serialized_values.pop("favicon_file", None)

    with patch(
        "baserow.contrib.builder.application_types.UserFileHandler"
    ) as mocked_handler:
        builder = BuilderApplicationType().import_serialized(
            workspace, serialized_values, config, {}
        )

    mocked_handler.import_user_file.assert_not_called()
    assert builder.favicon_file is None


@pytest.mark.django_db
def test_builder_application_imports_favicon_file(data_fixture, tmpdir):
    """Ensure the favicon_file is imported and saved to the builder."""

    user = data_fixture.create_user(email="test@baserow.io")
    workspace = data_fixture.create_workspace(user=user)
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")

    image = Image.new("RGB", (100, 140), color="red")
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")

    original_name = "mock_image.png"
    handler = UserFileHandler()
    user_file = handler.upload_user_file(
        user, original_name, image_bytes, storage=storage
    )

    config = ImportExportConfig(include_permission_data=True)
    serialized_values = IMPORT_REFERENCE.copy()
    serialized_values["favicon_file"] = user_file.serialize()

    builder = BuilderApplicationType().import_serialized(
        workspace, serialized_values, config, {}
    )

    assert builder.favicon_file == user_file


@pytest.mark.django_db
def test_builder_application_does_not_import_login_page(data_fixture):
    """
    Ensure the importer doesn't attempt to import the login_page if it
    doesn't exist in the serialized values.
    """

    user = data_fixture.create_user(email="test@baserow.io")
    workspace = data_fixture.create_workspace(user=user)

    config = ImportExportConfig(include_permission_data=True)
    serialized_values = IMPORT_REFERENCE.copy()
    serialized_values.pop("login_page", None)

    builder = BuilderApplicationType().import_serialized(
        workspace, serialized_values, config, {}
    )

    assert builder.login_page is None


@pytest.mark.django_db
def test_builder_application_imports_login_page(data_fixture):
    """Ensure the login_page is imported and saved to the builder."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="foo_login_page")
    builder.login_page = page
    builder.save()

    config = ImportExportConfig(include_permission_data=True)
    serialized = BuilderApplicationType().export_serialized(builder, config)

    new_builder = BuilderApplicationType().import_serialized(
        workspace, serialized, config, {}
    )

    assert new_builder.login_page.name == "foo_login_page"


@pytest.mark.django_db
def test_delete_builder_application_with_published_builder(data_fixture):
    builder = data_fixture.create_builder_application()
    builder_to = data_fixture.create_builder_application(workspace=None)
    domain1 = data_fixture.create_builder_custom_domain(
        builder=builder, published_to=builder_to
    )

    TrashHandler.permanently_delete(builder)

    assert Builder.objects.count() == 0


@pytest.mark.django_db
def test_builder_application_creation_does_not_register_an_action(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    assert Action.objects.count() == 0
    action_type_registry.get_by_type(CreateApplicationActionType).do(
        user,
        workspace,
        BuilderApplicationType.type,
        name="No actions please",
        init_with_data=False,
    )
    assert Action.objects.count() == 0


@pytest.mark.django_db
def test_builder_application_creation_uses_first_customers_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    database = data_fixture.create_database_application(workspace=workspace)
    table1 = data_fixture.create_database_table(database=database, name="Customers")
    data_fixture.create_text_field(table=table1, name="Name")
    data_fixture.create_text_field(table=table1, name="Last name")
    _ = data_fixture.create_database_table(database=database, name="Customers")
    _ = data_fixture.create_database_table(database=database, name="Customers")

    builder_init = BuilderApplicationTypeInitApplication(user, builder)
    target_table = builder_init.get_target_table()
    assert target_table == table1


@pytest.mark.django_db
def test_builder_application_imports_correct_default_roles(data_fixture):
    """
    Ensure that when importing, the correct Default User Roles are set.

    The UserSource ID is used to generate a default user role in an element's
    roles list. If a User Source uses the 'Use Default Role' value for the
    'Select role field', the backend will generate a default role with the
    pattern "__user_source_<user_source.id>".

    When the application is imported (e.g. during publishing), a new User
    Source is created, however the element's roles list will still have
    the default role which references the old UserSource ID.

    This test checks that when importing, the correct (new) User Source ID
    is used for any default roles.
    """

    user = data_fixture.create_user(email="test@baserow.io")
    workspace = data_fixture.create_workspace(user=user)

    serialized_values = IMPORT_REFERENCE.copy()
    first_page = serialized_values["pages"][0]

    serialized_user_source = serialized_values["user_sources"][0]
    serialized_user_source["role_field_id"] = None

    serialized_element = serialized_values["pages"][0]["elements"][0]
    serialized_element["role_type"] = "allow_all_except"
    serialized_element["roles"] = [
        f'__user_source_{serialized_user_source["id"]}',
    ]

    # Save the single element back to the list. We only need one element
    # to test.
    first_page["elements"] = [serialized_element]
    serialized_values["pages"] = [first_page]

    config = ImportExportConfig(include_permission_data=True)
    builder = BuilderApplicationType().import_serialized(
        workspace, serialized_values, config, {}
    )

    new_element = builder.visible_pages.first().element_set.all()[0]
    new_user_source = builder.user_sources.all()[0]

    # Ensure the "old" Default User Role doesn't exist
    assert f"__user_source_{serialized_user_source['id']}" not in new_element.roles
    # Ensure the "new" Default User Role uses the new User Source ID
    assert f"__user_source_{new_user_source.id}" in new_element.roles


@pytest.mark.django_db
@pytest.mark.parametrize(
    "initial_roles,expected_roles",
    [
        (
            ["foo_role"],
            [],
        ),
        (
            ["foo_role", "__user_source_{}"],
            ["__user_source_{}"],
        ),
        (
            ["foo_role", "__user_source_{}", "bar_role"],
            ["__user_source_{}"],
        ),
        (
            ["foo_role", "__user_source_{}", "bar_role"],
            ["__user_source_{}"],
        ),
    ],
)
def test_ensure_new_element_roles_are_sanitized_during_import_for_default_roles(
    data_fixture,
    initial_roles,
    expected_roles,
):
    """
    Ensure that during the import process, both the existing and new Element
    roles are sanitized when a Default Role is used.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, authorized_user=user, name="test"
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=builder, user=user, integration=integration
    )

    prefix = str(DEFAULT_USER_ROLE_PREFIX)

    # Update the user source ID in the role if needed
    _initial_roles = []
    for role in initial_roles:
        if role.startswith(prefix):
            _initial_roles.append(role.format(user_source.id))
        else:
            _initial_roles.append(role)
    initial_roles = _initial_roles

    old_element = data_fixture.create_builder_heading_element(page=page, level=2)
    old_element.roles = initial_roles
    old_element.save()

    config = ImportExportConfig(include_permission_data=True)
    serialized = BuilderApplicationType().export_serialized(builder, config)

    builder = BuilderApplicationType().import_serialized(
        workspace, serialized, config, {}
    )

    new_user_source = builder.user_sources.all()[0]
    _expected_roles = []
    for role in expected_roles:
        if role.startswith(prefix):
            _expected_roles.append(role.format(new_user_source.id))
        else:
            _expected_roles.append(role)
    expected_roles = _expected_roles

    # Ensure new element has roles updated
    new_element = builder.visible_pages.all()[0].element_set.all()[0]
    for index, role in enumerate(new_element.roles):
        # Default Role's User Source should have changed for new elements
        if role.startswith(prefix):
            assert role == role.format(new_user_source.id)
        else:
            assert role == expected_roles[index]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "user_source_roles,element_roles,expected_roles",
    [
        (
            [],
            [],
            [],
        ),
        (
            [],
            ["foo_role"],
            [],
        ),
        (
            ["foo_role"],
            ["bar_role"],
            [],
        ),
        (
            ["foo_role"],
            ["foo_role"],
            ["foo_role"],
        ),
        (
            ["foo_role", "bar_role", "baz_role"],
            ["invalid_role_a", "bar_role", "invalid_role_b"],
            ["bar_role"],
        ),
    ],
)
def test_ensure_new_element_roles_are_sanitized_during_import_for_roles(
    data_fixture,
    user_source_roles,
    element_roles,
    expected_roles,
):
    """
    Ensure that during the import process, both the existing and new Element
    roles are sanitized when using roles.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(user=user, workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    integration = data_fixture.create_local_baserow_integration(
        application=builder, authorized_user=user, name="test"
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=builder, user=user, integration=integration
    )
    user_source.role_type = Element.ROLE_TYPES.ALLOW_ALL_EXCEPT
    user_source.save()

    old_element = data_fixture.create_builder_heading_element(page=page, level=2)
    old_element.roles = element_roles
    old_element.save()

    config = ImportExportConfig(include_permission_data=True)
    serialized = BuilderApplicationType().export_serialized(builder, config)

    with patch.object(LocalBaserowUserSourceType, "get_roles") as m:
        m.return_value = user_source_roles
        builder = BuilderApplicationType().import_serialized(
            workspace, serialized, config, {}
        )

    new_element = builder.visible_pages.all()[0].element_set.all()[0]
    assert new_element.roles == expected_roles


@pytest.mark.django_db
def test_builder_application_exports_file_with_zip_file(
    data_fixture, api_client, tmpdir
):
    """
    Test that ensures any uploaded files are exported using a
    zip_file without errors.
    """

    user, token = data_fixture.create_user_and_token()
    image_file = data_fixture.create_user_file(is_image=True)
    builder = data_fixture.create_builder_application(
        user=user, favicon_file=image_file
    )
    page = data_fixture.create_builder_page(builder=builder)

    ThemeHandler().update_theme(
        builder,
        page_background_file=image_file,
    )

    data_fixture.create_builder_image_element(
        page=page,
        image_file=image_file,
    )

    zip_file = ExportZipFile(
        compress_level=settings.BASEROW_DEFAULT_ZIP_COMPRESS_LEVEL,
        compress_type=zipstream.ZIP_DEFLATED,
    )

    # Ensure Builder app (including the ImageElement) is exported without
    # raising any exceptions.
    serialized = BuilderApplicationType().export_serialized(
        builder, ImportExportConfig(include_permission_data=True), files_zip=zip_file
    )

    serialized_file = {
        "name": image_file.name,
        "original_name": image_file.original_name,
    }
    assert serialized["favicon_file"] == serialized_file
    assert serialized["theme"]["page_background_file_id"] == serialized_file
    visible_pages = [page for page in serialized["pages"] if not page["shared"]]
    serialized_image_element = visible_pages[0]["elements"][0]
    assert serialized_image_element["image_source_type"] == "upload"
    assert serialized_image_element["image_file_id"] == serialized_file


@pytest.mark.django_db
def test_get_default_application_urls(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    builder_to = data_fixture.create_builder_application(workspace=None)
    domain1 = data_fixture.create_builder_custom_domain(
        builder=builder, published_to=builder_to, domain_name="mytest.com"
    )

    assert builder.get_type().get_application_urls(builder) == [
        f"http://localhost:3000/builder/{builder.id}/preview/"
    ]
    assert builder_to.get_type().get_application_urls(builder_to) == [
        "http://mytest.com:3000",
        f"http://localhost:3000/builder/{builder.id}/preview/",
    ]


@pytest.mark.django_db
def test_get_application_id_for_url(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    builder_to = data_fixture.create_builder_application(workspace=None)
    domain1 = data_fixture.create_builder_custom_domain(
        builder=builder, published_to=builder_to, domain_name="mytest.com"
    )

    assert (
        builder.get_type().get_application_id_for_url(
            f"http://localhost:3000/builder/{builder.id}/preview/"
        )
        == builder.id
    )
    assert (
        builder.get_type().get_application_id_for_url(
            f"http://mytest.com/something/somethingelse/"
        )
        == builder_to.id
    )
