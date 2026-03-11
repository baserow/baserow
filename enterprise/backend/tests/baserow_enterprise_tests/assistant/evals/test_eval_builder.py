import pytest

from baserow.contrib.builder.elements.models import (
    Element,
    MenuItemElement,
)
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.theme.models import ColorThemeConfigBlock
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow_enterprise.assistant.types import (
    ApplicationUIContext,
    UIContext,
    UserUIContext,
    WorkspaceUIContext,
)

from .eval_utils import (
    assert_no_tool_errors,
    assert_tool_call_order,
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

PROMPT_LIST_PAGES = "List all pages in builder '{builder_name}'."

PROMPT_CREATE_CONTACT_FORM = (
    "In builder '{builder_name}', create a page called "
    "'Contact' at path '/contact'. Add a form container with text inputs "
    "for Name and Email, and a submit button. "
    "Add a create_row action on the form's submit event that creates a row "
    "in table '{table_name}' mapping the Name and the Email."
)

PROMPT_CREATE_LANDING_PAGE = (
    "In builder '{builder_name}', create a page called "
    "'Home' at path '/'. Add a heading saying 'Welcome' and a text element "
    "saying 'This is our landing page'. Also add a button labeled 'Get Started' "
    "that links to '/contact'."
)

PROMPT_CREATE_DATA_SOURCE_PAGE = (
    "In builder '{builder_name}', create a page called "
    "'Products' at path '/products'. Add a list_rows data source called "
    "'All Products' that reads from table '{table_name}'. "
    "Then add a repeat element using that data source and inside it "
    "a heading element."
)

PROMPT_CREATE_APP_WITH_DARK_THEME = (
    "Create a new application called 'Dashboard' with the eclipse theme."
)

PROMPT_CHANGE_THEME = "Change the theme of builder '{builder_name}' to midnight."

PROMPT_TABLE_WITH_EDIT_BUTTON = (
    "In builder '{builder_name}', create two pages: "
    "a 'List' page at '/list' and an 'Edit' page at '/edit/:id'. "
    "On the List page, add a list_rows data source for table '{table_name}', "
    "then add a table element showing columns for {field_names}. "
    "Add an Edit button that links to the Edit page, passing the row id."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_agent(
    agent, deps, tracker, model, usage_limits, toolset, question, ui_context
):
    deps.tool_helpers.request_context["ui_context"] = ui_context

    # Auto-detect starting mode from UI context, matching astream_messages()
    from baserow_enterprise.assistant.deps import AgentMode

    ctx = UIContext.model_validate_json(ui_context)
    if ctx.application or ctx.page:
        deps.mode = AgentMode.APPLICATION
    elif ctx.automation or ctx.workflow:
        deps.mode = AgentMode.AUTOMATION
    else:
        deps.mode = AgentMode.DATABASE

    return agent.run_sync(
        user_prompt=question,
        deps=deps,
        model=model,
        usage_limits=usage_limits,
        toolsets=[toolset],
    )


def _filter_tool_calls(result, tool_names=None):
    """Return assistant-side tool call entries, optionally filtered by name(s).

    :param tool_names: A single tool name (str), a collection of names, or
        ``None`` to return all tool calls.
    """

    history = format_message_history(result)
    calls = [e for e in history if e["role"] == "assistant" and "args" in e]
    if tool_names is None:
        return calls
    if isinstance(tool_names, str):
        tool_names = {tool_names}
    else:
        tool_names = set(tool_names)
    return [e for e in calls if e.get("tool_name") in tool_names]


_ELEMENT_CREATION_TOOLS = {
    "create_display_elements",
    "create_layout_elements",
    "create_form_elements",
    "create_collection_elements",
}


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

    calls = _filter_tool_calls(result, "list_pages")
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
    pages = Page.objects.filter(builder=builder, shared=False)
    assert pages.exists(), "No page was created"

    # Pages must be created before elements
    assert_tool_call_order(result, ["create_pages", "create_display_elements"])

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
    # Pages → form elements → actions
    assert_tool_call_order(result, ["setup_page"])

    # Page should be created
    pages = Page.objects.filter(builder=builder, shared=False)
    assert pages.exists(), "No page was created"

    # Elements should exist (form_container + inputs + button at minimum)
    page = pages.first()
    elements = Element.objects.filter(page=page)
    assert elements.count() >= 3, (
        f"Expected at least 3 elements (form + 2 inputs), got {elements.count()}"
    )

    # A create_row workflow action should exist, targeting the Contacts table
    actions = BuilderWorkflowAction.objects.filter(page=page)
    assert actions.exists(), "No workflow action was created for the form submit"

    create_row_action = actions.filter(
        content_type__model="localbaserowcreaterowworkflowaction"
    ).first()
    assert create_row_action is not None, (
        f"Expected a create_row action, got types: "
        f"{list(actions.values_list('content_type__model', flat=True))}"
    )

    # The action's service should point to the Contacts table
    service = create_row_action.specific.service.specific
    assert service.table_id == table.id, (
        f"create_row action should target table '{table.name}' (id={table.id}), "
        f"but targets table_id={service.table_id}"
    )

    # Field mappings should cover Name and Email, referencing form inputs
    mappings = {
        m.field_id: m.value
        for m in service.field_mappings.filter(enabled=True).select_related("field")
    }
    assert name_field.id in mappings, (
        f"Name field (id={name_field.id}) not mapped. Mapped IDs: {set(mappings)}"
    )
    assert email_field.id in mappings, (
        f"Email field (id={email_field.id}) not mapped. Mapped IDs: {set(mappings)}"
    )

    # Each mapping value should reference a form input via get('form_data.<element_id>')
    import re

    form_input_ids = set(
        elements.filter(
            content_type__model__in=["inputtextelement", "inputemailelement"]
        ).values_list("id", flat=True)
    )
    assert form_input_ids, "Expected form input elements on the page"

    form_data_re = re.compile(r"form_data\.(\d+)")
    for field_id, formula in mappings.items():
        formula_str = str(formula)
        referenced_ids = {int(m) for m in form_data_re.findall(formula_str)}
        assert referenced_ids & form_input_ids, (
            f"Mapping for field {field_id} should reference a form input element. "
            f"Formula: {formula_str}, form input IDs: {form_input_ids}"
        )


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
    pages = Page.objects.filter(builder=builder, shared=False)
    assert pages.exists(), "No page was created"

    # Pages → data sources → collection elements
    assert_tool_call_order(
        result,
        [
            "create_pages",
            "create_data_sources",
            "create_collection_elements",
        ],
    )

    # Data source args should reference the table
    ds_calls = _filter_tool_calls(result, "create_data_sources")
    ds_args = ds_calls[0]["args"]
    data_sources = ds_args.get("data_sources", [])
    assert len(data_sources) >= 1, "Expected at least 1 data source"
    assert data_sources[0].get("type") == "list_rows", (
        f"Expected list_rows data source, got {data_sources[0].get('type')}"
    )

    # Elements should include a repeat
    el_calls = _filter_tool_calls(result, _ELEMENT_CREATION_TOOLS)
    all_elements = []
    for call in el_calls:
        all_elements.extend(call["args"].get("elements", []))
    repeat_elements = [e for e in all_elements if e.get("type") == "repeat"]
    assert len(repeat_elements) >= 1, (
        f"Expected a repeat element, got types: {[e.get('type') for e in all_elements]}"
    )


# ---------------------------------------------------------------------------
# Shared element evals
# ---------------------------------------------------------------------------

PROMPT_SHARED_HEADER_WITH_MENU = (
    "In builder '{builder_name}', add a shared header with "
    "a menu that links to all three pages: Home, About, "
    "and Contact."
)

PROMPT_BACK_BUTTON_ON_DETAIL = (
    "In builder '{builder_name}', add a 'Back to List' button "
    "on the Detail page that navigates to the List page."
)

PROMPT_BACK_LINK_ON_DETAIL = (
    "In builder '{builder_name}', add a 'Back to list' link "
    "on the Detail page that goes to the List page."
)


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_header_with_menu(data_fixture, eval_model):
    """Agent should create a header on the shared page with a menu linking to pages."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="Nav App"
    )
    home = data_fixture.create_builder_page(builder=builder, name="Home", path="/")
    about = data_fixture.create_builder_page(
        builder=builder, name="About", path="/about"
    )
    contact = data_fixture.create_builder_page(
        builder=builder, name="Contact", path="/contact"
    )

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
        question=PROMPT_SHARED_HEADER_WITH_MENU.format(
            builder_name=builder.name,
            builder_id=builder.id,
            home_id=home.id,
            about_id=about.id,
            contact_id=contact.id,
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    # Layout (header) must be created before display elements (menu)
    assert_tool_call_order(result, ["create_layout_elements"])

    # Header should be created on the shared page
    shared_page = builder.shared_page
    shared_elements = Element.objects.filter(page=shared_page)
    header_elements = shared_elements.filter(content_type__model="headerelement")
    assert header_elements.exists(), (
        f"Expected a header element on the shared page, "
        f"got types: {list(shared_elements.values_list('content_type__model', flat=True))}"
    )

    # A menu element should exist on the shared page (child of the header)
    menu_elements = shared_elements.filter(content_type__model="menuelement")
    assert menu_elements.exists(), (
        "Expected a menu element on the shared page inside the header"
    )

    # The menu should have 3 items linking to Home, About, and Contact pages
    menu_element = menu_elements.first().specific
    menu_items = MenuItemElement.objects.filter(
        pk__in=menu_element.menu_items.values_list("pk", flat=True)
    ).select_related("navigate_to_page")

    assert menu_items.count() >= 3, (
        f"Expected at least 3 menu items (Home, About, Contact), "
        f"got {menu_items.count()}"
    )

    linked_page_ids = {
        item.navigate_to_page_id
        for item in menu_items
        if item.navigate_to_page_id is not None
    }
    expected_page_ids = {home.id, about.id, contact.id}
    assert expected_page_ids <= linked_page_ids, (
        f"Menu items should link to Home ({home.id}), About ({about.id}), "
        f"and Contact ({contact.id}) pages. "
        f"Linked page IDs: {linked_page_ids}"
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_puts_back_button_on_page_not_header(data_fixture, eval_model):
    """Agent should place a back button on the page itself, not in the shared header."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="App"
    )
    list_page = data_fixture.create_builder_page(
        builder=builder, name="List", path="/list"
    )
    detail_page = data_fixture.create_builder_page(
        builder=builder, name="Detail", path="/detail"
    )

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
        question=PROMPT_BACK_BUTTON_ON_DETAIL.format(
            builder_name=builder.name,
            builder_id=builder.id,
            detail_id=detail_page.id,
            list_id=list_page.id,
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)
    assert len(_filter_tool_calls(result, "create_display_elements")) >= 1, (
        "Agent should have called create_display_elements for the back button"
    )

    # The back button/link should be on the Detail page, NOT on the shared page
    detail_elements = Element.objects.filter(page=detail_page)
    assert detail_elements.exists(), "Expected elements on the Detail page"

    shared_page = builder.shared_page
    shared_elements = Element.objects.filter(page=shared_page)
    # No new elements should have been added to the shared page
    assert not shared_elements.exists(), (
        "Back button should NOT be on the shared page. "
        f"Shared page has: {list(shared_elements.values_list('content_type__model', flat=True))}"
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_page_specific_nav_on_page(data_fixture, eval_model):
    """Agent should create a 'Back to list' link on the page, not shared header."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="App"
    )
    list_page = data_fixture.create_builder_page(
        builder=builder, name="List", path="/list"
    )
    detail_page = data_fixture.create_builder_page(
        builder=builder, name="Detail", path="/detail"
    )

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
        question=PROMPT_BACK_LINK_ON_DETAIL.format(
            builder_name=builder.name,
            builder_id=builder.id,
            detail_id=detail_page.id,
            list_id=list_page.id,
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)
    assert len(_filter_tool_calls(result, "create_display_elements")) >= 1, (
        "Agent should have called create_display_elements for the back link"
    )

    # The link should be on the Detail page
    detail_elements = Element.objects.filter(page=detail_page)
    assert detail_elements.exists(), "Expected elements on the Detail page"

    # Check that a link, button, or menu element exists on the detail page
    link_elements = detail_elements.filter(content_type__model="linkelement")
    button_elements = detail_elements.filter(content_type__model="buttonelement")
    menu_elements = detail_elements.filter(content_type__model="menuelement")
    element_types = list(detail_elements.values_list("content_type__model", flat=True))
    assert (
        link_elements.exists() or button_elements.exists() or menu_elements.exists()
    ), (
        f"Expected a link, button, or menu element on the Detail page, "
        f"got types: {element_types}"
    )

    # If a menu element was created, verify it has items linking to the List page
    if menu_elements.exists():
        menu_element = menu_elements.first().specific
        menu_items = MenuItemElement.objects.filter(
            pk__in=menu_element.menu_items.values_list("pk", flat=True)
        ).select_related("navigate_to_page")
        assert menu_items.count() >= 1, (
            f"Menu element exists but has no menu items. "
            f"Expected at least 1 item linking to the List page."
        )
        linked_page_ids = {
            item.navigate_to_page_id
            for item in menu_items
            if item.navigate_to_page_id is not None
        }
        assert list_page.id in linked_page_ids, (
            f"Menu items should link to the List page (id={list_page.id}). "
            f"Linked page IDs: {linked_page_ids}"
        )

    # If a link element was created, verify it navigates to the List page
    if link_elements.exists():
        link_el = link_elements.first().specific
        assert link_el.navigate_to_page_id == list_page.id or "/list" in str(
            link_el.navigate_to_url
        ), (
            f"Link element should navigate to List page (id={list_page.id}), "
            f"but navigate_to_page_id={link_el.navigate_to_page_id}, "
            f"navigate_to_url={link_el.navigate_to_url}"
        )

    # No elements should have been added to the shared page
    shared_page = builder.shared_page
    shared_elements = Element.objects.filter(page=shared_page)
    assert not shared_elements.exists(), (
        "Page-specific nav should NOT be on the shared page. "
        f"Shared page has: {list(shared_elements.values_list('content_type__model', flat=True))}"
    )


# ---------------------------------------------------------------------------
# Theme evals
# ---------------------------------------------------------------------------


def _get_theme_primary_color(builder) -> str:
    """Return the current primary_color for a builder, refreshed from DB."""

    builder.refresh_from_db()
    try:
        return builder.colorthemeconfigblock.primary_color
    except ColorThemeConfigBlock.DoesNotExist:
        return ""


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_app_with_theme(data_fixture, eval_model):
    """Agent should create an application and apply the requested theme."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=15, model=eval_model
    )
    ui_context = UIContext(
        workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
        user=UserUIContext(id=user.id, name=user.first_name, email=user.email),
    ).format()
    deps.tool_helpers.request_context["ui_context"] = ui_context

    result = agent.run_sync(
        user_prompt=PROMPT_CREATE_APP_WITH_DARK_THEME,
        deps=deps,
        model=model,
        usage_limits=usage_limits,
        toolsets=[toolset],
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    # The agent should have called create_builders
    assert len(_filter_tool_calls(result, "create_builders")) >= 1, (
        "Agent should have called create_builders"
    )

    # Verify the builder was created
    from baserow.contrib.builder.models import Builder

    builders = Builder.objects.filter(workspace=workspace, name__icontains="Dashboard")
    assert builders.exists(), "No builder named 'Dashboard' was created"

    # Verify eclipse theme was applied (primary_color differs from default)
    builder = builders.first()
    primary_color = _get_theme_primary_color(builder)
    default_color = "#5190efff"
    assert primary_color != default_color, (
        f"Theme was not applied — primary_color is still the default ({default_color}). "
        f"Expected eclipse theme color."
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_changes_theme(data_fixture, eval_model):
    """Agent should change the theme of an existing application."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="My App"
    )

    # Record the initial primary color
    initial_color = _get_theme_primary_color(builder)

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=15, model=eval_model
    )
    ui_context = build_builder_ui_context(user, workspace, builder)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CHANGE_THEME.format(builder_name=builder.name),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)

    # The agent should have called set_theme
    set_theme_calls = _filter_tool_calls(result, "set_theme")
    assert len(set_theme_calls) >= 1, "Agent should have called set_theme"

    # Verify theme_name argument was "midnight"
    theme_arg = set_theme_calls[0]["args"].get("theme_name")
    assert theme_arg == "midnight", (
        f"Expected set_theme with theme_name='midnight', got '{theme_arg}'"
    )

    # Verify the color actually changed
    new_color = _get_theme_primary_color(builder)
    assert new_color != initial_color, (
        f"Theme color did not change — still '{initial_color}' after set_theme"
    )


# ---------------------------------------------------------------------------
# Table element with edit button eval
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_table_with_edit_button(data_fixture, eval_model):
    """Agent should create a list page with a table element showing columns
    and an edit button that navigates to the edit page with the row id."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="Product App"
    )
    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="Store"
    )
    table = data_fixture.create_database_table(
        user=user, database=database, name="Products"
    )
    name_field = data_fixture.create_text_field(table=table, name="Name", primary=True)
    price_field = data_fixture.create_number_field(table=table, name="Price")

    agent, deps, tracker, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=30, model=eval_model
    )
    ui_context = build_builder_ui_context(user, workspace, builder)

    result = _run_agent(
        agent,
        deps,
        tracker,
        model,
        usage_limits,
        toolset,
        question=PROMPT_TABLE_WITH_EDIT_BUTTON.format(
            builder_name=builder.name,
            table_name=table.name,
            field_names="Name and Price",
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    assert_no_tool_errors(tracker, result)
    assert len(_filter_tool_calls(result, ["setup_page", "create_pages"])) >= 1, (
        "Agent should have called setup_page for creating pages and elements"
    )

    # Both pages should exist
    pages = Page.objects.filter(builder=builder, shared=False)
    list_page = pages.filter(name__icontains="List").first()
    edit_page = pages.filter(name__icontains="Edit").first()
    assert list_page is not None, (
        f"No 'List' page found. Pages: {list(pages.values_list('name', flat=True))}"
    )
    assert edit_page is not None, (
        f"No 'Edit' page found. Pages: {list(pages.values_list('name', flat=True))}"
    )

    # A table element should exist on the list page
    list_elements = Element.objects.filter(page=list_page)
    table_elements = list_elements.filter(content_type__model="tableelement")
    assert table_elements.exists(), (
        f"Expected a table element on the List page, "
        f"got types: {list(list_elements.values_list('content_type__model', flat=True))}"
    )

    # The table should have columns
    table_el = table_elements.first().specific
    columns = table_el.fields.all().order_by("order")
    assert columns.count() >= 2, (
        f"Expected at least 2 columns (Name, Price), got {columns.count()}"
    )

    # Verify data columns reference the right fields via formulas
    import re

    data_columns = columns.filter(type__in=["text", "number"])
    col_formulas = {c.name: str(c.config) for c in data_columns}
    field_id_re = re.compile(r"field_(\d+)")
    referenced_field_ids = set()
    for formula in col_formulas.values():
        referenced_field_ids.update(int(m) for m in field_id_re.findall(formula))
    assert name_field.id in referenced_field_ids or any(
        "Name" in name for name in col_formulas
    ), (
        f"No column references the Name field (id={name_field.id}). "
        f"Column formulas: {col_formulas}"
    )

    # Verify there's a button/link column pointing to the edit page
    link_columns = columns.filter(type__in=["link", "button"])
    assert link_columns.exists(), (
        f"Expected a link/button column for 'Edit'. "
        f"Column types: {list(columns.values_list('type', flat=True))}"
    )

    # The link column's config should navigate to the edit page
    link_col = link_columns.first()
    assert link_col.type == "button", (
        f"Expected a button column for 'Edit', got type '{link_col.type}'"
    )

    action = BuilderWorkflowAction.objects.filter(
        page=list_page, event=f"{link_col.uid}_click", element=table_el
    ).first()
    assert action is not None, (
        f"No workflow action found for the edit button clicks. "
        f"Expected event: '{link_col.uid}_click'"
    )
    assert action.specific.navigate_to_page_id == edit_page.id, (
        f"Edit button action should navigate to page id {edit_page.id}, "
        f"but navigates to {action.specific.navigate_to_page_id}"
    )
