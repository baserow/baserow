"""Tests for the row colour tools shared by MCP and Kuma."""

import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)
from pydantic import ValidationError

from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.tools.view_config import (
    ConditionalColour,
    RowColour,
    delete_row_colours,
    set_row_colours,
)
from baserow.contrib.database.tools.views import ViewFilterItemCreate, list_views
from baserow.contrib.database.views.actions import (
    CreateDecorationActionType,
    DeleteDecorationActionType,
)
from baserow.contrib.database.views.models import ViewDecoration
from baserow.core.action.models import Action
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import ToolInputError
from baserow_premium.license.exceptions import FeaturesNotAvailableError


@pytest.fixture(autouse=True)
def debug_licences(settings):
    # `has_active_premium_license` only works in debug mode.
    settings.DEBUG = True


def _call(endpoint, name, arguments):
    async def inner():
        token = current_key.set(endpoint.key)
        try:
            async with client_session(BaserowMCPServer()._mcp_server) as client:
                return await client.call_tool(name, arguments)
        finally:
            current_key.reset(token)

    with transaction.atomic():
        return async_to_sync(inner)()


def _setup(fixture, **user_kwargs):
    user = fixture.create_user(session_id="session", **user_kwargs)
    workspace = fixture.create_workspace(user=user)
    database = fixture.create_database_application(workspace=workspace)
    table = fixture.create_database_table(database=database)
    fixture.create_text_field(table=table, name="Name", primary=True)
    status = fixture.create_single_select_field(table=table, name="Status")
    amount = fixture.create_number_field(table=table, name="Amount")
    view = fixture.create_grid_view(table=table)
    return ToolContext(user=user, workspace=workspace), view, status, amount


def _by_select(field_id):
    return RowColour(
        style="left_border_color", by="single_select_color", field_id=field_id
    )


def _when_above_100(field_id):
    return RowColour(
        style="background_color",
        by="conditional_color",
        colours=[
            ConditionalColour(
                color="red",
                filters=[
                    ViewFilterItemCreate(
                        field_id=field_id,
                        type="number",
                        operator="greater_than",
                        value=100,
                    )
                ],
            )
        ],
    )


@pytest.mark.django_db
def test_row_colour_by_single_select(premium_data_fixture):
    ctx, view, status, _ = _setup(premium_data_fixture, has_active_premium_license=True)

    result = set_row_colours(ctx, view.id, _by_select(status.id))

    decoration = ViewDecoration.objects.get(id=result["decoration_id"])
    assert decoration.type == "left_border_color"
    assert decoration.value_provider_type == "single_select_color"
    assert decoration.value_provider_conf == {"field_id": status.id}
    assert Action.objects.filter(type=CreateDecorationActionType.type).count() == 1


@pytest.mark.django_db
def test_row_colour_conditional_builds_filters(premium_data_fixture):
    ctx, view, _, amount = _setup(premium_data_fixture, has_active_premium_license=True)

    result = set_row_colours(ctx, view.id, _when_above_100(amount.id))

    conf = ViewDecoration.objects.get(id=result["decoration_id"]).value_provider_conf
    colour = conf["colors"][0]
    assert colour["color"] == "red"
    assert colour["operator"] == "AND"
    assert colour["id"]
    assert colour["filters"][0]["id"]
    assert colour["filters"][0]["field"] == amount.id
    assert colour["filters"][0]["type"] == "higher_than"
    assert colour["filters"][0]["value"] == "100"


@pytest.mark.django_db
def test_row_colour_needs_premium(premium_data_fixture):
    ctx, view, status, _ = _setup(premium_data_fixture)

    with pytest.raises(FeaturesNotAvailableError):
        set_row_colours(ctx, view.id, _by_select(status.id))

    assert ViewDecoration.objects.count() == 0


@pytest.mark.django_db
def test_row_colour_rejects_field_of_other_table(premium_data_fixture):
    ctx, view, _, _ = _setup(premium_data_fixture, has_active_premium_license=True)
    other = premium_data_fixture.create_database_table(database=view.table.database)
    foreign = premium_data_fixture.create_single_select_field(table=other)

    with pytest.raises(FieldDoesNotExist):
        set_row_colours(ctx, view.id, _by_select(foreign.id))
    with pytest.raises(ToolInputError):
        foreign_number = premium_data_fixture.create_number_field(table=other)
        set_row_colours(ctx, view.id, _when_above_100(foreign_number.id))

    assert ViewDecoration.objects.count() == 0


@pytest.mark.django_db
def test_row_colour_rejects_a_field_that_is_not_a_single_select(premium_data_fixture):
    ctx, view, _, amount = _setup(premium_data_fixture, has_active_premium_license=True)

    with pytest.raises(ToolInputError):
        set_row_colours(ctx, view.id, _by_select(amount.id))


@pytest.mark.django_db
def test_row_colour_explains_a_view_without_colours(premium_data_fixture):
    ctx, view, status, _ = _setup(premium_data_fixture, has_active_premium_license=True)
    form = premium_data_fixture.create_form_view(table=view.table)

    with pytest.raises(ToolInputError):
        set_row_colours(ctx, form.id, _by_select(status.id))


def test_row_colour_needs_the_input_of_its_kind():
    with pytest.raises(ValidationError):
        RowColour(style="background_color", by="single_select_color")
    with pytest.raises(ValidationError):
        RowColour(style="background_color", by="conditional_color", field_id=1)
    with pytest.raises(ValidationError):
        RowColour(style="background_color", by="conditional_color", colours=[])
    with pytest.raises(ValidationError):
        RowColour(
            style="background_color",
            by="single_select_color",
            field_id=1,
            colours=[ConditionalColour(color="red", filters=[])],
        )


@pytest.mark.django_db
def test_delete_row_colours_hides_foreign_and_keeps_going(premium_data_fixture):
    ctx, view, status, _ = _setup(premium_data_fixture, has_active_premium_license=True)
    own = set_row_colours(ctx, view.id, _by_select(status.id))["decoration_id"]
    other_ctx, other_view, other_status, _ = _setup(
        premium_data_fixture, has_active_premium_license=True
    )
    foreign = set_row_colours(other_ctx, other_view.id, _by_select(other_status.id))[
        "decoration_id"
    ]

    result = delete_row_colours(ctx, [foreign, own])

    assert result == {
        "deleted_row_colours": [own],
        "errors": [
            {
                "index": 0,
                "decoration_id": foreign,
                "error": "Not found in this workspace.",
            }
        ],
    }
    assert list(ViewDecoration.objects.values_list("id", flat=True)) == [foreign]
    assert Action.objects.filter(type=DeleteDecorationActionType.type).count() == 1


@pytest.mark.django_db
def test_list_views_returns_row_colours(premium_data_fixture):
    ctx, view, status, _ = _setup(premium_data_fixture, has_active_premium_license=True)
    decoration = set_row_colours(ctx, view.id, _by_select(status.id))["decoration_id"]

    listed = list_views(ctx, view.table_id)["views"][0]

    assert listed["row_colours"] == [
        {
            "id": decoration,
            "style": "left_border_color",
            "by": "single_select_color",
            "conf": {"field_id": status.id},
        }
    ]


@pytest.mark.django_db(transaction=True)
def test_row_colour_over_mcp_tells_the_client_about_the_licence(premium_data_fixture):
    ctx, view, status, _ = _setup(premium_data_fixture)
    endpoint = premium_data_fixture.create_mcp_endpoint(
        user=ctx.user, workspace=ctx.workspace, allowed_tools=["set_row_colours"]
    )

    result = _call(
        endpoint,
        "set_row_colours",
        {
            "view_id": view.id,
            "colour": {
                "style": "background_color",
                "by": "single_select_color",
                "field_id": status.id,
            },
        },
    )

    assert result.isError
    assert result.content[0].text == (
        "The related user does not have access to these features."
    )
    assert ViewDecoration.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_row_colour_over_mcp(premium_data_fixture):
    ctx, view, status, amount = _setup(
        premium_data_fixture, has_active_premium_license=True
    )
    endpoint = premium_data_fixture.create_mcp_endpoint(
        user=ctx.user, workspace=ctx.workspace, allowed_tools=["set_row_colours"]
    )

    result = _call(
        endpoint,
        "set_row_colours",
        {
            "view_id": view.id,
            "colour": {
                "style": "background_color",
                "by": "conditional_color",
                "colours": [
                    {
                        "color": "red",
                        "filters": [
                            {
                                "field_id": amount.id,
                                "type": "number",
                                "operator": "greater_than",
                                "value": 100,
                            }
                        ],
                    }
                ],
            },
        },
    )

    assert not result.isError
    decoration_id = json.loads(result.content[0].text)["decoration_id"]
    assert ViewDecoration.objects.filter(id=decoration_id).exists()


@pytest.mark.django_db(transaction=True)
def test_row_colour_tools_open_their_own_transaction(premium_data_fixture):
    # The MCP server and Kuma call the tools outside a transaction, unlike a test's
    # database fixture.
    ctx, view, status, _ = _setup(premium_data_fixture, has_active_premium_license=True)

    decoration = set_row_colours(ctx, view.id, _by_select(status.id))["decoration_id"]
    deleted = delete_row_colours(ctx, [decoration])

    assert deleted["deleted_row_colours"] == [decoration]


@pytest.mark.parametrize("color", ["#ff0000", "", "teal", "light-", "red "])
def test_row_colour_rejects_a_colour_a_row_cannot_show(color):
    # A row takes its colour from a CSS class per palette name, anything else shows
    # nothing while the tool reports success.
    with pytest.raises(ValidationError):
        ConditionalColour(color=color, filters=[])


@pytest.mark.parametrize("color", ["red", "light-blue", "dark-green", "darker-gray"])
def test_row_colour_accepts_the_palette(color):
    assert ConditionalColour(color=color, filters=[]).color == color
