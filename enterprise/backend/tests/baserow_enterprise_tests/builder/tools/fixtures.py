"""
Fixtures for the tests of the shared builder tools, here and over MCP. The
conftest files of both folders import them.
"""

import pytest
from pydantic_ai import Agent

from baserow.core.tools import ToolContext


def block_model_calls(monkeypatch):
    """
    The shared tools must never call a model, whichever client runs them. Calls
    are also checked after the test, in case the caller swallowed the error.
    """

    calls = []

    def fail(*args, **kwargs):
        calls.append(args)
        raise AssertionError("A shared tool called a model.")

    for method in ("run", "run_sync", "run_stream", "iter"):
        monkeypatch.setattr(Agent, method, fail)
    yield
    assert not calls, "A shared tool called a model."


@pytest.fixture
def builder_ctx(data_fixture):
    """
    A user's workspace with a builder holding a page with a data source, a button
    with a click action and a table, and a footer on the shared page.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder, name="Home")
    data_fixture.create_builder_page(builder=builder, name="About")
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=table, name="Products"
    )
    button = data_fixture.create_builder_button_element(page=page, value="'Go'")
    action = data_fixture.create_notification_workflow_action(
        page=page, element=button, event="click"
    )
    footer = data_fixture.create_builder_heading_element(
        page=builder.shared_page, value="'Footer'"
    )
    return {
        "ctx": ToolContext(user=user, workspace=workspace),
        "user": user,
        "workspace": workspace,
        "builder": builder,
        "page": page,
        "data_source": data_source,
        "button": button,
        "action": action,
        "footer": footer,
    }
