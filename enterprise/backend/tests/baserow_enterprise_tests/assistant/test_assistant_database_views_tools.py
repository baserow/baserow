from unittest.mock import Mock

import pytest
from udspy.module.callbacks import ModuleContext, is_module_callback

from baserow.contrib.database.views.models import View, ViewFilter
from baserow_enterprise.assistant.tools.database.tools import (
    get_list_views_tool,
    get_views_tool_factory,
)
from baserow_enterprise.assistant.tools.database.types import (
    BooleanIsViewFilterItemCreate,
    CalendarViewItemCreate,
    DateAfterViewFilterItemCreate,
    DateBeforeViewFilterItemCreate,
    DateEqualsViewFilterItemCreate,
    DateNotEqualsViewFilterItemCreate,
    FormFieldOption,
    FormViewItemCreate,
    GalleryViewItemCreate,
    GridViewItemCreate,
    KanbanViewItemCreate,
    MultipleSelectIsAnyViewFilterItemCreate,
    MultipleSelectIsNoneOfNotViewFilterItemCreate,
    NumberEqualsViewFilterItemCreate,
    NumberHigherThanViewFilterItemCreate,
    NumberLowerThanViewFilterItemCreate,
    NumberNotEqualsViewFilterItemCreate,
    SingleSelectIsAnyViewFilterItemCreate,
    SingleSelectIsNoneOfNotViewFilterItemCreate,
    TextContainsViewFilterItemCreate,
    TextEqualViewFilterItemCreate,
    TextNotContainsViewFilterItemCreate,
    TextNotEqualViewFilterItemCreate,
    TimelineViewItemCreate,
)
from baserow_enterprise.assistant.tools.database.types.base import Date
from baserow_enterprise.assistant.tools.database.types.view_filters import (
    ViewFiltersArgs,
)

from .utils import fake_tool_helpers


def get_create_views_tool(user, workspace):
    """Helper to get the create_views tool from the factory"""

    factory = get_views_tool_factory(user, workspace, fake_tool_helpers)
    assert callable(factory)

    tools_upgrade = factory()
    assert is_module_callback(tools_upgrade)

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))
    assert mock_module.init_module.called

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_views_tool = next(
        (tool for tool in added_tools if tool.name == "create_views"), None
    )
    assert create_views_tool is not None
    return create_views_tool


def get_create_view_filters_tool(user, workspace):
    """Helper to get the create_view_filters tool from the factory"""

    factory = get_views_tool_factory(user, workspace, fake_tool_helpers)
    assert callable(factory)

    tools_upgrade = factory()
    assert is_module_callback(tools_upgrade)

    mock_module = Mock()
    mock_module._tools = []
    mock_module.init_module = Mock()
    tools_upgrade(ModuleContext(module=mock_module))
    assert mock_module.init_module.called

    added_tools = mock_module.init_module.call_args[1]["tools"]
    create_filters_tool = next(
        (tool for tool in added_tools if tool.name == "create_view_filters"), None
    )
    assert create_filters_tool is not None
    return create_filters_tool


@pytest.mark.django_db
def test_list_views_tool(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    view = data_fixture.create_grid_view(table=table, name="View 1", order=1)

    tool = get_list_views_tool(user, workspace, fake_tool_helpers)
    response = tool(table_id=table.id)

    assert response == {
        "views": [
            {
                "id": view.id,
                "name": "View 1",
                "type": "grid",
                "row_height": "small",
                "public": False,
            }
        ]
    }

    view_2 = data_fixture.create_grid_view(table=table, name="View 2", order=2)
    response = tool(table_id=table.id)
    assert len(response["views"]) == 2
    assert response["views"][0]["name"] == "View 1"
    assert response["views"][1]["name"] == "View 2"


@pytest.mark.django_db
def test_create_grid_view(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    tool = get_create_views_tool(user, workspace)
    response = tool.func(
        table_id=table.id,
        views=[
            GridViewItemCreate(
                type="grid", name="Grid View", public=False, row_height="medium"
            )
        ],
    )

    assert len(response["created_views"]) == 1
    assert response["created_views"][0]["name"] == "Grid View"
    assert View.objects.filter(name="Grid View").exists()


@pytest.mark.django_db
def test_create_kanban_view(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    single_select = data_fixture.create_single_select_field(table=table, name="Status")

    tool = get_create_views_tool(user, workspace)
    response = tool.func(
        table_id=table.id,
        views=[
            KanbanViewItemCreate(
                type="kanban",
                name="Kanban View",
                public=False,
                column_field_id=single_select.id,
            )
        ],
    )

    assert len(response["created_views"]) == 1
    assert response["created_views"][0]["name"] == "Kanban View"
    assert View.objects.filter(name="Kanban View").exists()


@pytest.mark.django_db
def test_create_calendar_view(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    date_field = data_fixture.create_date_field(table=table, name="Date")

    tool = get_create_views_tool(user, workspace)
    response = tool.func(
        table_id=table.id,
        views=[
            CalendarViewItemCreate(
                type="calendar",
                name="Calendar View",
                public=False,
                date_field_id=date_field.id,
            )
        ],
    )

    assert len(response["created_views"]) == 1
    assert response["created_views"][0]["name"] == "Calendar View"
    assert View.objects.filter(name="Calendar View").exists()


@pytest.mark.django_db
def test_create_gallery_view(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    file_field = data_fixture.create_file_field(table=table, name="Files")

    tool = get_create_views_tool(user, workspace)
    response = tool.func(
        table_id=table.id,
        views=[
            GalleryViewItemCreate(
                type="gallery",
                name="Gallery View",
                public=False,
                cover_field_id=file_field.id,
            )
        ],
    )

    assert len(response["created_views"]) == 1
    assert response["created_views"][0]["name"] == "Gallery View"
    assert View.objects.filter(name="Gallery View").exists()


@pytest.mark.django_db
def test_create_timeline_view(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    start_date = data_fixture.create_date_field(table=table, name="Start Date")
    end_date = data_fixture.create_date_field(table=table, name="End Date")

    tool = get_create_views_tool(user, workspace)
    response = tool.func(
        table_id=table.id,
        views=[
            TimelineViewItemCreate(
                type="timeline",
                name="Timeline View",
                public=False,
                start_date_field_id=start_date.id,
                end_date_field_id=end_date.id,
            )
        ],
    )

    assert len(response["created_views"]) == 1
    assert response["created_views"][0]["name"] == "Timeline View"
    assert View.objects.filter(name="Timeline View").exists()


@pytest.mark.django_db
def test_create_form_view(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, name="Name", primary=True)

    tool = get_create_views_tool(user, workspace)
    response = tool.func(
        table_id=table.id,
        views=[
            FormViewItemCreate(
                type="form",
                name="Form View",
                public=True,
                title="Contact Form",
                description="Fill out this form",
                submit_button_label="Submit",
                receive_notification_on_submit=False,
                submit_action="MESSAGE",
                submit_action_message="Thank you!",
                submit_action_redirect_url="",
                field_options=[
                    FormFieldOption(
                        field_id=field.id,
                        name="Your Name",
                        description="Enter your name",
                        required=True,
                        order=1,
                    )
                ],
            )
        ],
    )

    assert len(response["created_views"]) == 1
    assert response["created_views"][0]["name"] == "Form View"
    assert View.objects.filter(name="Form View").exists()


# Text filter tests
@pytest.mark.django_db
def test_create_text_equal_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, name="Name")
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    TextEqualViewFilterItemCreate(
                        field_id=field.id, type="text", operator="equal", value="test"
                    )
                ],
            )
        ]
    )

    assert len(response["created_view_filters"]) == 1
    assert len(response["created_view_filters"][0]["filters"]) == 1
    assert response["created_view_filters"][0]["filters"][0]["operator"] == "equal"
    assert ViewFilter.objects.filter(view=view, field=field, type="equal").exists()


@pytest.mark.django_db
def test_create_text_not_equal_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    TextNotEqualViewFilterItemCreate(
                        field_id=field.id,
                        type="text",
                        operator="not_equal",
                        value="test",
                    )
                ],
            ),
        ]
    )

    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(view=view, field=field, type="not_equal").exists()


@pytest.mark.django_db
def test_create_text_contains_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    TextContainsViewFilterItemCreate(
                        field_id=field.id,
                        type="text",
                        operator="contains",
                        value="test",
                    )
                ],
            ),
        ]
    )

    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(view=view, field=field, type="contains").exists()


@pytest.mark.django_db
def test_create_text_not_contains_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    TextNotContainsViewFilterItemCreate(
                        field_id=field.id,
                        type="text",
                        operator="contains_not",
                        value="test",
                    )
                ],
            ),
        ]
    )

    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(
        view=view, field=field, type="contains_not"
    ).exists()


# Number filter tests
@pytest.mark.django_db
def test_create_number_equal_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    NumberEqualsViewFilterItemCreate(
                        field_id=field.id, type="number", operator="equal", value=42.0
                    )
                ],
            ),
        ]
    )

    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(view=view, field=field, type="equal").exists()


@pytest.mark.django_db
def test_create_number_not_equal_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    NumberNotEqualsViewFilterItemCreate(
                        field_id=field.id,
                        type="number",
                        operator="not_equal",
                        value=42.0,
                    )
                ],
            ),
        ]
    )

    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(view=view, field=field, type="not_equal").exists()


@pytest.mark.django_db
def test_create_number_higher_than_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    NumberHigherThanViewFilterItemCreate(
                        field_id=field.id,
                        type="number",
                        operator="higher_than",
                        value=10.0,
                        or_equal=False,
                    )
                ],
            )
        ],
    )

    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(
        view=view, field=field, type="higher_than"
    ).exists()


@pytest.mark.django_db
def test_create_number_lower_than_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_number_field(table=table)
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    NumberLowerThanViewFilterItemCreate(
                        field_id=field.id,
                        type="number",
                        operator="lower_than",
                        value=100.0,
                        or_equal=False,
                    )
                ],
            ),
        ]
    )

    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(view=view, field=field, type="lower_than").exists()


# Date filter tests
@pytest.mark.django_db
def test_create_date_equal_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_date_field(table=table)
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    DateEqualsViewFilterItemCreate(
                        field_id=field.id,
                        type="date",
                        operator="equal",
                        value=Date(year=2024, month=1, day=15),
                        mode="exact_date",
                    )
                ],
            ),
        ]
    )

    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(view=view, field=field, type="date_is").exists()


@pytest.mark.django_db
def test_create_date_not_equal_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_date_field(table=table)
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    DateNotEqualsViewFilterItemCreate(
                        field_id=field.id,
                        type="date",
                        operator="not_equal",
                        value=None,
                        mode="today",
                    )
                ],
            ),
        ]
    )

    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(
        view=view, field=field, type="date_is_not"
    ).exists()


@pytest.mark.django_db
def test_create_date_after_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_date_field(table=table)
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    DateAfterViewFilterItemCreate(
                        field_id=field.id,
                        type="date",
                        operator="after",
                        value=7,
                        mode="nr_days_ago",
                        or_equal=False,
                    )
                ],
            ),
        ]
    )

    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(
        view=view, field=field, type="date_is_after"
    ).exists()


@pytest.mark.django_db
def test_create_date_before_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_date_field(table=table)
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    DateBeforeViewFilterItemCreate(
                        field_id=field.id,
                        type="date",
                        operator="before",
                        value=None,
                        mode="tomorrow",
                        or_equal=True,
                    )
                ],
            ),
        ]
    )

    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(
        view=view, field=field, type="date_is_on_or_before"
    ).exists()


# Single select filter tests
@pytest.mark.django_db
def test_create_single_select_is_any_of_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_single_select_field(table=table)
    data_fixture.create_select_option(field=field, value="Option 1")
    data_fixture.create_select_option(field=field, value="Option 2")
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    SingleSelectIsAnyViewFilterItemCreate(
                        field_id=field.id,
                        type="single_select",
                        operator="is_any_of",
                        value=["Option 1", "Option 2"],
                    )
                ],
            ),
        ]
    )

    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(
        view=view, field=field, type="single_select_is_any_of"
    ).exists()


@pytest.mark.django_db
def test_create_single_select_is_none_of_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_single_select_field(table=table)
    data_fixture.create_select_option(field=field, value="Bad Option")
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    SingleSelectIsNoneOfNotViewFilterItemCreate(
                        field_id=field.id,
                        type="single_select",
                        operator="is_none_of",
                        value=["Bad Option"],
                    )
                ],
            ),
        ]
    )

    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(
        view=view, field=field, type="single_select_is_none_of"
    ).exists()


# Boolean filter tests
@pytest.mark.django_db
def test_create_boolean_is_true_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_boolean_field(table=table, name="Active")
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    BooleanIsViewFilterItemCreate(
                        field_id=field.id, type="boolean", operator="is", value=True
                    )
                ],
            ),
        ]
    )

    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(view=view, field=field, type="boolean").exists()


@pytest.mark.django_db
def test_create_boolean_is_false_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_boolean_field(table=table, name="Active")
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    BooleanIsViewFilterItemCreate(
                        field_id=field.id, type="boolean", operator="is", value=False
                    )
                ],
            ),
        ]
    )

    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(view=view, field=field, type="boolean").exists()


# Multiple select filter tests
@pytest.mark.django_db
def test_create_multiple_select_is_any_of_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_multiple_select_field(table=table)
    data_fixture.create_select_option(field=field, value="Tag 1")
    data_fixture.create_select_option(field=field, value="Tag 2")
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    MultipleSelectIsAnyViewFilterItemCreate(
                        field_id=field.id,
                        type="multiple_select",
                        operator="is_any_of",
                        value=["Tag 1", "Tag 2"],
                    )
                ],
            ),
        ]
    )

    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(
        view=view, field=field, type="multiple_select_has"
    ).exists()


@pytest.mark.django_db
def test_create_multiple_select_is_none_of_filter(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_multiple_select_field(table=table)
    data_fixture.create_select_option(field=field, value="Bad Tag")
    view = data_fixture.create_grid_view(table=table)

    tool = get_create_view_filters_tool(user, workspace)
    response = tool.func(
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    MultipleSelectIsNoneOfNotViewFilterItemCreate(
                        field_id=field.id,
                        type="multiple_select",
                        operator="is_none_of",
                        value=["Bad Tag"],
                    )
                ],
            ),
        ]
    )
    assert len(response["created_view_filters"]) == 1
    assert ViewFilter.objects.filter(
        view=view, field=field, type="multiple_select_has_not"
    ).exists()
