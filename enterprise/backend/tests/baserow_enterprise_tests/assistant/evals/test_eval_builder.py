import pytest

from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow_enterprise.assistant.types import (
    ApplicationUIContext,
    UIContext,
    UserUIContext,
    WorkspaceUIContext,
)

from .eval_utils import (
    assert_no_tool_errors,
    create_eval_assistant,
    format_message_history,
    print_message_history,
)

# ---------------------------------------------------------------------------
# UI context helper
# ---------------------------------------------------------------------------


def build_builder_ui_context(user, workspace, builder, page=None) -> str:
    ctx = UIContext(
        workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
        application=ApplicationUIContext(id=str(builder.id), name=builder.name),
        user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
    )
    return ctx.format()


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PROMPT_LIST_PAGES = "List all pages in builder '{builder_name}' (ID {builder_id})."

PROMPT_CREATE_CONTACT_FORM = (
    "In builder '{builder_name}' (ID {builder_id}), create a page called "
    "'Contact' at path '/contact'. Add a form container with text inputs "
    "for Name and Email, and a submit button. "
    "Add a create_row action on the form's submit event that creates a row "
    "in table '{table_name}' (ID {table_id}) mapping the Name field "
    "(ID {name_field_id}) and Email field (ID {email_field_id})."
)

PROMPT_CREATE_LANDING_PAGE = (
    "In builder '{builder_name}' (ID {builder_id}), create a page called "
    "'Home' at path '/'. Add a heading saying 'Welcome' and a text element "
    "saying 'This is our landing page'. Also add a button labeled 'Get Started' "
    "that links to '/contact'."
)

PROMPT_CREATE_DATA_SOURCE_PAGE = (
    "In builder '{builder_name}' (ID {builder_id}), create a page called "
    "'Products' at path '/products'. Add a list_rows data source called "
    "'All Products' that reads from table '{table_name}' (ID {table_id}). "
    "Then add a repeat element using that data source and inside it "
    "a heading element."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_agent(
    agent, deps, tracker, model, usage_limits, toolset, question, ui_context
):
    deps.tool_helpers.request_context["ui_context"] = ui_context
    return agent.run_sync(
        user_prompt=question,
        deps=deps,
        model=model,
        usage_limits=usage_limits,
        toolsets=[toolset],
    )


def _get_tool_calls(result, tool_name):
    """Return assistant-side tool call entries for a given tool name."""
    history = format_message_history(result)
    return [
        e
        for e in history
        if e["role"] == "assistant" and e.get("tool_name") == tool_name and "args" in e
    ]


_ELEMENT_CREATION_TOOLS = {
    "create_display_elements",
    "create_layout_elements",
    "create_form_elements",
    "create_collection_elements",
}


def _get_element_creation_calls(result):
    """Return all element creation tool calls (any of the 4 category tools)."""
    calls = []
    for tool_name in _ELEMENT_CREATION_TOOLS:
        calls.extend(_get_tool_calls(result, tool_name))
    return calls


# ---------------------------------------------------------------------------
# Evals
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_lists_pages(data_fixture, eval_model):
    """Agent should call list_pages when asked about builder pages."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="My App"
    )
    data_fixture.create_builder_page(builder=builder, name="Home", path="/")
    data_fixture.create_builder_page(builder=builder, name="About", path="/about")

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=10, model=eval_model
    )
    ui_context = build_builder_ui_context(user, workspace, builder)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_LIST_PAGES.format(
            builder_name=builder.name, builder_id=builder.id
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    calls = _get_tool_calls(result, "list_pages")
    assert len(calls) >= 1, (
        "Agent should have called list_pages. "
        f"Tools called: {[e.get('tool_name') for e in format_message_history(result) if e.get('tool_name')]}"
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_landing_page(data_fixture, eval_model):
    """Agent should create a page with heading, text, and button elements."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="Website"
    )

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=20, model=eval_model
    )
    ui_context = build_builder_ui_context(user, workspace, builder)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATE_LANDING_PAGE.format(
            builder_name=builder.name, builder_id=builder.id
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    # Page should be created
    pages = Page.objects.filter(builder=builder)
    assert pages.exists(), "No page was created"

    # Should have called create_pages and element creation tools
    assert len(_get_tool_calls(result, "create_pages")) >= 1, (
        "Agent should have called create_pages"
    )
    assert len(_get_element_creation_calls(result)) >= 1, (
        "Agent should have called an element creation tool"
    )

    # Verify elements were created on the page
    page = pages.first()
    elements = Element.objects.filter(page=page)
    assert elements.count() >= 3, (
        f"Expected at least 3 elements (heading, text, button), got {elements.count()}"
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_contact_form(data_fixture, eval_model):
    """Agent should create a contact form page with form inputs and a
    create_row action on submit."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="Contact App"
    )
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="CRM"
    )
    table = data_fixture.create_database_table(
        user=user, database=database, name="Contacts"
    )
    name_field = data_fixture.create_text_field(table=table, name="Name", primary=True)
    email_field = data_fixture.create_email_field(table=table, name="Email")

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=25, model=eval_model
    )
    ui_context = build_builder_ui_context(user, workspace, builder)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATE_CONTACT_FORM.format(
            builder_name=builder.name,
            builder_id=builder.id,
            table_name=table.name,
            table_id=table.id,
            name_field_id=name_field.id,
            email_field_id=email_field.id,
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    # Page should be created
    pages = Page.objects.filter(builder=builder)
    assert pages.exists(), "No page was created"

    # Elements should exist (form_container + inputs + button at minimum)
    page = pages.first()
    elements = Element.objects.filter(page=page)
    assert elements.count() >= 3, (
        f"Expected at least 3 elements (form + 2 inputs), got {elements.count()}"
    )

    # A workflow action should exist
    actions = BuilderWorkflowAction.objects.filter(page=page)
    assert actions.exists(), "No workflow action was created for the form submit"

    # Verify tool calls
    assert len(_get_tool_calls(result, "create_pages")) >= 1
    assert len(_get_element_creation_calls(result)) >= 1
    assert len(_get_tool_calls(result, "create_actions")) >= 1


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_data_source_with_repeat(data_fixture, eval_model):
    """Agent should create a page with a data source and a repeat element."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="Product Catalog"
    )
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="Store"
    )
    table = data_fixture.create_database_table(
        user=user, database=database, name="Products"
    )
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    data_fixture.create_number_field(table=table, name="Price")

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=25, model=eval_model
    )
    ui_context = build_builder_ui_context(user, workspace, builder)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CREATE_DATA_SOURCE_PAGE.format(
            builder_name=builder.name,
            builder_id=builder.id,
            table_name=table.name,
            table_id=table.id,
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    # Page should be created
    pages = Page.objects.filter(builder=builder)
    assert pages.exists(), "No page was created"

    # Verify tool calls
    assert len(_get_tool_calls(result, "create_pages")) >= 1
    assert len(_get_tool_calls(result, "create_data_sources")) >= 1
    assert len(_get_element_creation_calls(result)) >= 1

    # Data source args should reference the table
    ds_calls = _get_tool_calls(result, "create_data_sources")
    ds_args = ds_calls[0]["args"]
    data_sources = ds_args.get("data_sources", [])
    assert len(data_sources) >= 1, "Expected at least 1 data source"
    assert data_sources[0].get("type") == "list_rows", (
        f"Expected list_rows data source, got {data_sources[0].get('type')}"
    )

    # Elements should include a repeat
    el_calls = _get_element_creation_calls(result)
    all_elements = []
    for call in el_calls:
        all_elements.extend(call["args"].get("elements", []))
    repeat_elements = [e for e in all_elements if e.get("type") == "repeat"]
    assert len(repeat_elements) >= 1, (
        f"Expected a repeat element, got types: {[e.get('type') for e in all_elements]}"
    )
