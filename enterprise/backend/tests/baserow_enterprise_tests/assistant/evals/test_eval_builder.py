import re

import pytest

from baserow.contrib.builder.data_sources.models import DataSource
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
    EvalChecklist,
    assert_tool_call_order,
    count_tool_errors,
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
# Prompts — one per test, all at the top for easy coverage scanning
# ---------------------------------------------------------------------------

PROMPT_LIST_PAGES = "List all pages in builder '{builder_name}'."

PROMPT_CREATE_LANDING_PAGE = (
    "In builder '{builder_name}', create a page called "
    "'Home' at path '/'. Add a heading saying 'Welcome' and a text element "
    "saying 'This is our landing page'. Also add a button labeled 'Get Started' "
    "that links to '/contact'."
)

PROMPT_CREATE_CONTACT_FORM = (
    "In builder '{builder_name}', create a page called "
    "'Contact' at path '/contact'. Add a form container with text inputs "
    "for Name and Email, and a submit button. "
    "Add a create_row action on the form's submit event that creates a row "
    "in table '{table_name}' mapping the Name and the Email."
)

PROMPT_CREATE_DATA_SOURCE_PAGE = (
    "In builder '{builder_name}', create a page called "
    "'Products' at path '/products'. Add a list_rows data source called "
    "'All Products' that reads from table '{table_name}'. "
    "Then add a repeat element using that data source and inside it "
    "a heading element."
)

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

PROMPT_TABLE_WITH_EDIT_BUTTON = (
    "In builder '{builder_name}', create two pages: "
    "a 'List' page at '/list' and an 'Edit' page at '/edit/:id'. "
    "On the List page, add a list_rows data source for table '{table_name}', "
    "then add a table element showing columns for {field_names}. "
    "Add an Edit button that links to the Edit page, passing the row id."
)

PROMPT_CREATE_LANDING_PAGE_WITH_EXISTING = (
    "Create a landing page with a heading, description, "
    "and CTA button for my {builder_name}"
)

PROMPT_FILTERED_DATA_SOURCE = (
    "In builder '{builder_name}', create a page called 'Pending Tasks' at "
    "'/pending'. Show only tasks where Status is 'Pending' from the "
    "'{table_name}' table in a table element with columns for Name and Status."
)

PROMPT_CREATE_APP_WITH_DARK_THEME = (
    "Create a new application called 'Dashboard' with the eclipse theme."
)

PROMPT_CHANGE_THEME = "Change the theme of builder '{builder_name}' to midnight."

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_agent(
    agent, deps, tracker, model, usage_limits, toolset, question, ui_context
):
    deps.tool_helpers.request_context["ui_context"] = ui_context

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
    """Return assistant-side tool call entries, optionally filtered by name(s)."""
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


def _collect_element_args(result, tool_names=None):
    """Flatten all element dicts from element-creation tool calls."""
    tools = tool_names or _ELEMENT_CREATION_TOOLS
    calls = _filter_tool_calls(result, tools)
    elements = []
    for call in calls:
        elements.extend(call["args"].get("elements", []))
    return elements


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
        question=PROMPT_LIST_PAGES.format(builder_name=builder.name),
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    history = format_message_history(result)
    list_page_calls = _filter_tool_calls(result, "list_pages")

    with EvalChecklist("lists pages") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "called list_pages",
            len(list_page_calls) >= 1,
            hint=f"tools called: {[e.get('tool_name') for e in history if e.get('tool_name')]}",
        )
        checks.check(
            "response mentions 'Home'",
            "Home" in result.output,
            hint=f"output: {result.output[:300]}",
        )
        checks.check(
            "response mentions 'About'",
            "About" in result.output,
            hint=f"output: {result.output[:300]}",
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
        question=PROMPT_CREATE_LANDING_PAGE.format(builder_name=builder.name),
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    # Pages must be created before elements — only enforce when no errors, because
    # a failed early call (retry) would make first_B appear before last_A even though
    # the model ultimately did it right. The EvalChecklist "no tool errors" check
    # captures the retry case.
    if err_count == 0:
        assert_tool_call_order(result, ["create_pages", "create_display_elements"])

    pages = Page.objects.filter(builder=builder, shared=False)
    page = pages.first()
    elements = Element.objects.filter(page=page) if page else Element.objects.none()

    all_el_args = _collect_element_args(result)
    heading_args = [e for e in all_el_args if e.get("type") == "heading"]
    button_args = [e for e in all_el_args if e.get("type") == "button"]
    heading_texts = [str(e.get("value", "")).lower() for e in heading_args]
    button_texts = [
        str(e.get("value", "") or e.get("label", "")).lower() for e in button_args
    ]

    with EvalChecklist("creates landing page") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check("page created", pages.exists(), hint="no pages found in DB")
        checks.check(
            "page name is 'Home'",
            page is not None and "home" in page.name.lower(),
            hint=f"page name: {page.name if page else None}",
        )
        checks.check(
            "page path is '/'",
            page is not None and page.path == "/",
            hint=f"page path: {page.path if page else None}",
        )
        checks.check(
            ">=3 elements (heading, text, button)",
            elements.count() >= 3,
            hint=f"got {elements.count()} elements",
        )
        checks.check(
            "heading element with 'Welcome'",
            any("welcome" in t for t in heading_texts),
            hint=f"heading texts from args: {heading_texts}",
        )
        checks.check(
            "button labeled 'Get Started'",
            any("get started" in t for t in button_texts),
            hint=f"button texts from args: {button_texts}",
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
            table_name=table.name,
            table_id=table.id,
            name_field_id=name_field.id,
            email_field_id=email_field.id,
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    # Pages → form elements → actions
    assert_tool_call_order(result, ["setup_page"])

    pages = Page.objects.filter(builder=builder, shared=False)
    page = pages.first()
    elements = Element.objects.filter(page=page) if page else Element.objects.none()

    actions = (
        BuilderWorkflowAction.objects.filter(page=page)
        if page
        else BuilderWorkflowAction.objects.none()
    )
    create_row_action = actions.filter(
        content_type__model="localbaserowcreaterowworkflowaction"
    ).first()

    # Field mappings
    service = None
    mappings = {}
    if create_row_action is not None:
        service = create_row_action.specific.service.specific
        mappings = {
            m.field_id: m.value for m in service.field_mappings.filter(enabled=True)
        }

    form_input_ids = set(
        elements.filter(
            content_type__model__in=["inputtextelement", "inputemailelement"]
        ).values_list("id", flat=True)
    )

    form_data_re = re.compile(r"form_data\.(\d+)")
    all_map_formulas_ok = (
        all(
            bool({int(m) for m in form_data_re.findall(str(formula))} & form_input_ids)
            for formula in mappings.values()
        )
        if mappings and form_input_ids
        else False
    )

    with EvalChecklist("creates contact form") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check("page created", pages.exists(), hint="no pages found in DB")
        checks.check(
            "page name is 'Contact'",
            page is not None and "contact" in page.name.lower(),
            hint=f"page name: {page.name if page else None}",
        )
        checks.check(
            "page path is '/contact'",
            page is not None and page.path == "/contact",
            hint=f"page path: {page.path if page else None}",
        )
        checks.check(
            ">=3 elements (form container + inputs)",
            elements.count() >= 3,
            hint=f"got {elements.count()} elements",
        )
        checks.check(
            "create_row workflow action exists",
            create_row_action is not None,
            hint=f"action types: {list(actions.values_list('content_type__model', flat=True))}",
        )
        checks.check(
            "create_row targets Contacts table",
            service is not None and service.table_id == table.id,
            hint=f"service table_id={service.table_id if service else None}, expected={table.id}",
        )
        checks.check(
            "Name field is mapped",
            name_field.id in mappings,
            hint=f"mapped field IDs: {set(mappings)}",
        )
        checks.check(
            "Email field is mapped",
            email_field.id in mappings,
            hint=f"mapped field IDs: {set(mappings)}",
        )
        checks.check(
            "all field mappings reference form input elements",
            all_map_formulas_ok,
            hint=f"formulas: {list(mappings.values())}, form input IDs: {form_input_ids}",
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
            table_name=table.name,
            table_id=table.id,
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    # Pages must be created before data setup. Accept either the low-level path
    # (create_data_sources + create_collection_elements) or the high-level
    # setup_page which handles both in one call.
    if _filter_tool_calls(result, "setup_page"):
        assert_tool_call_order(result, ["create_pages", "setup_page"])
    else:
        assert_tool_call_order(
            result,
            ["create_pages", "create_data_sources", "create_collection_elements"],
        )

    pages = Page.objects.filter(builder=builder, shared=False)
    page = pages.first()

    # Data source args — from create_data_sources or setup_page (both are valid)
    ds_calls = _filter_tool_calls(result, "create_data_sources")
    setup_calls = _filter_tool_calls(result, "setup_page")
    if ds_calls:
        data_sources = ds_calls[0]["args"].get("data_sources", [])
    elif setup_calls:
        data_sources = setup_calls[0]["args"].get("data_sources", []) or []
    else:
        data_sources = []
    first_ds = data_sources[0] if data_sources else {}
    ds_name = first_ds.get("name", "")
    ds_table_id = first_ds.get("table_id")
    ds_type = first_ds.get("type")

    # Element args — from individual tools or setup_page
    all_el_args = _collect_element_args(result)
    for call in setup_calls:
        all_el_args.extend(call["args"].get("elements", []) or [])
    repeat_elements = [e for e in all_el_args if e.get("type") == "repeat"]

    with EvalChecklist("creates data source with repeat") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check("page created", pages.exists(), hint="no pages found in DB")
        checks.check(
            "page name is 'Products'",
            page is not None and "product" in page.name.lower(),
            hint=f"page name: {page.name if page else None}",
        )
        checks.check(
            "page path is '/products'",
            page is not None and page.path == "/products",
            hint=f"page path: {page.path if page else None}",
        )
        checks.check(
            "data source created",
            len(data_sources) >= 1,
            hint=f"ds_calls: {len(ds_calls)}, setup_calls: {len(setup_calls)}",
        )
        checks.check(
            "data source type is list_rows",
            ds_type == "list_rows",
            hint=f"got type: {ds_type}",
        )
        checks.check(
            "data source named 'All Products'",
            "all products" in ds_name.lower(),
            hint=f"got name: '{ds_name}'",
        )
        checks.check(
            "data source table_id matches Products table",
            ds_table_id == table.id,
            hint=f"got table_id={ds_table_id}, expected={table.id}",
        )
        checks.check(
            "repeat element in args",
            len(repeat_elements) >= 1,
            hint=f"element types: {[e.get('type') for e in all_el_args]}",
        )


# ---------------------------------------------------------------------------
# Shared element evals
# ---------------------------------------------------------------------------


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
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    # Layout (header) must be created before display elements (menu)
    assert_tool_call_order(result, ["create_layout_elements"])

    shared_page = builder.shared_page
    shared_elements = Element.objects.filter(page=shared_page)
    header_elements = shared_elements.filter(content_type__model="headerelement")
    menu_elements = shared_elements.filter(content_type__model="menuelement")

    menu_element = menu_elements.first().specific if menu_elements.exists() else None
    menu_items = (
        MenuItemElement.objects.filter(
            pk__in=menu_element.menu_items.values_list("pk", flat=True)
        ).select_related("navigate_to_page")
        if menu_element is not None
        else MenuItemElement.objects.none()
    )
    linked_page_ids = {
        item.navigate_to_page_id
        for item in menu_items
        if item.navigate_to_page_id is not None
    }
    expected_page_ids = {home.id, about.id, contact.id}

    with EvalChecklist("creates header with menu") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "header element on shared page",
            header_elements.exists(),
            hint=f"shared page elements: {list(shared_elements.values_list('content_type__model', flat=True))}",
        )
        checks.check(
            "menu element on shared page",
            menu_elements.exists(),
            hint="expected a menu element inside the header on the shared page",
        )
        checks.check(
            ">=3 menu items (Home, About, Contact)",
            menu_items.count() >= 3,
            hint=f"got {menu_items.count()} menu items",
        )
        checks.check(
            "menu links to Home page",
            home.id in linked_page_ids,
            hint=f"linked page IDs: {linked_page_ids}, expected Home={home.id}",
        )
        checks.check(
            "menu links to About page",
            about.id in linked_page_ids,
            hint=f"linked page IDs: {linked_page_ids}, expected About={about.id}",
        )
        checks.check(
            "menu links to Contact page",
            contact.id in linked_page_ids,
            hint=f"linked page IDs: {linked_page_ids}, expected Contact={contact.id}",
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
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    detail_elements = Element.objects.filter(page=detail_page)
    shared_page = builder.shared_page
    shared_elements = Element.objects.filter(page=shared_page)

    button_args = [
        e for e in _collect_element_args(result) if e.get("type") == "button"
    ]
    button_texts = [
        str(e.get("value", "") or e.get("label", "")).lower() for e in button_args
    ]

    with EvalChecklist("back button on page not header") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "called create_display_elements",
            len(_filter_tool_calls(result, "create_display_elements")) >= 1,
            hint=f"tools: {[e.get('tool_name') for e in format_message_history(result) if e.get('tool_name')]}",
        )
        checks.check(
            "elements exist on Detail page",
            detail_elements.exists(),
            hint="no elements on Detail page",
        )
        checks.check(
            "button labeled 'Back to List'",
            any("back" in t for t in button_texts),
            hint=f"button texts: {button_texts}",
        )
        checks.check(
            "no elements added to shared page",
            not shared_elements.exists(),
            hint=f"shared page has: {list(shared_elements.values_list('content_type__model', flat=True))}",
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
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    detail_elements = Element.objects.filter(page=detail_page)
    shared_page = builder.shared_page
    shared_elements = Element.objects.filter(page=shared_page)

    link_elements = detail_elements.filter(content_type__model="linkelement")
    button_elements = detail_elements.filter(content_type__model="buttonelement")
    menu_elements = detail_elements.filter(content_type__model="menuelement")

    # Navigation target checks for link element
    link_targets_list = False
    if link_elements.exists():
        link_el = link_elements.first().specific
        link_targets_list = (
            link_el.navigate_to_page_id == list_page.id
            or "/list" in str(link_el.navigate_to_url)
        )

    # Navigation target checks for menu element
    menu_links_list = False
    if menu_elements.exists():
        menu_element = menu_elements.first().specific
        menu_items = MenuItemElement.objects.filter(
            pk__in=menu_element.menu_items.values_list("pk", flat=True)
        )
        linked_ids = {
            item.navigate_to_page_id
            for item in menu_items
            if item.navigate_to_page_id is not None
        }
        menu_links_list = list_page.id in linked_ids

    has_nav_element = (
        link_elements.exists() or button_elements.exists() or menu_elements.exists()
    )
    nav_targets_list_page = link_targets_list or menu_links_list

    with EvalChecklist("page-specific nav on page not header") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "called create_display_elements",
            len(_filter_tool_calls(result, "create_display_elements")) >= 1,
            hint=f"tools: {[e.get('tool_name') for e in format_message_history(result) if e.get('tool_name')]}",
        )
        checks.check(
            "elements exist on Detail page",
            detail_elements.exists(),
            hint="no elements on Detail page",
        )
        checks.check(
            "link/button/menu element on Detail page",
            has_nav_element,
            hint=f"detail page elements: {list(detail_elements.values_list('content_type__model', flat=True))}",
        )
        checks.check(
            "nav element targets List page",
            nav_targets_list_page,
            hint=f"link_targets_list={link_targets_list}, menu_links_list={menu_links_list}",
        )
        checks.check(
            "no elements added to shared page",
            not shared_elements.exists(),
            hint=f"shared page has: {list(shared_elements.values_list('content_type__model', flat=True))}",
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

    agent, deps, _, model, usage_limits, toolset = create_eval_assistant(
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
    err_count, err_hint = count_tool_errors(result)

    from baserow.contrib.builder.models import Builder

    builders = Builder.objects.filter(workspace=workspace, name__icontains="Dashboard")
    builder = builders.first()
    primary_color = _get_theme_primary_color(builder) if builder else ""
    default_color = "#5190efff"

    with EvalChecklist("creates app with theme") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "called create_builders",
            len(_filter_tool_calls(result, "create_builders")) >= 1,
            hint=f"tools: {[e.get('tool_name') for e in format_message_history(result) if e.get('tool_name')]}",
        )
        checks.check(
            "builder 'Dashboard' created",
            builders.exists(),
            hint="no builder named 'Dashboard' found",
        )
        checks.check(
            "eclipse theme applied (color differs from default)",
            primary_color != default_color,
            hint=f"primary_color={primary_color}, default={default_color}",
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

    agent, deps, _, model, usage_limits, toolset = create_eval_assistant(
        user, workspace, max_iters=15, model=eval_model
    )
    ui_context = build_builder_ui_context(user, workspace, builder)

    result = _run_agent(
        agent,
        deps,
        _,
        model,
        usage_limits,
        toolset,
        question=PROMPT_CHANGE_THEME.format(builder_name=builder.name),
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    set_theme_calls = _filter_tool_calls(result, "set_theme")
    theme_arg = (
        set_theme_calls[0]["args"].get("theme_name") if set_theme_calls else None
    )
    new_color = _get_theme_primary_color(builder)

    with EvalChecklist("changes theme") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "called set_theme",
            len(set_theme_calls) >= 1,
            hint=f"tools: {[e.get('tool_name') for e in format_message_history(result) if e.get('tool_name')]}",
        )
        checks.check(
            "theme_name is 'midnight'",
            theme_arg == "midnight",
            hint=f"got theme_name='{theme_arg}'",
        )
        checks.check(
            "theme color changed",
            new_color != initial_color,
            hint=f"color still '{initial_color}' after set_theme",
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
    err_count, err_hint = count_tool_errors(result)

    pages = Page.objects.filter(builder=builder, shared=False)
    list_page = pages.filter(name__icontains="List").first()
    edit_page = pages.filter(name__icontains="Edit").first()

    list_elements = (
        Element.objects.filter(page=list_page) if list_page else Element.objects.none()
    )
    table_elements = list_elements.filter(content_type__model="tableelement")
    table_el = table_elements.first().specific if table_elements.exists() else None

    columns = table_el.fields.all().order_by("order") if table_el else []
    col_count = len(list(columns)) if table_el else 0

    # Check data columns reference correct fields
    field_id_re = re.compile(r"field_(\d+)")
    referenced_field_ids = set()
    link_columns = []
    if table_el:
        for col in columns:
            formula = str(getattr(col, "config", "") or "")
            referenced_field_ids.update(int(m) for m in field_id_re.findall(formula))
            if getattr(col, "type", None) in ("link", "button"):
                link_columns.append(col)

    name_col_ok = name_field.id in referenced_field_ids or any(
        "Name" in (getattr(col, "name", "") or "")
        for col in (columns if table_el else [])
    )

    # Edit button workflow action
    action = None
    if link_columns:
        link_col = link_columns[0]
        action = BuilderWorkflowAction.objects.filter(
            page=list_page, event=f"{link_col.uid}_click", element=table_el
        ).first()

    with EvalChecklist("creates table with edit button") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "called setup_page or create_pages",
            len(_filter_tool_calls(result, ["setup_page", "create_pages"])) >= 1,
            hint=f"tools: {[e.get('tool_name') for e in format_message_history(result) if e.get('tool_name')]}",
        )
        checks.check(
            "List page created",
            list_page is not None,
            hint=f"pages: {list(pages.values_list('name', flat=True))}",
        )
        checks.check(
            "List page path is '/list'",
            list_page is not None and list_page.path == "/list",
            hint=f"list page path: {list_page.path if list_page else None}",
        )
        checks.check(
            "Edit page created",
            edit_page is not None,
            hint=f"pages: {list(pages.values_list('name', flat=True))}",
        )
        checks.check(
            "Edit page path contains '/edit'",
            edit_page is not None and "/edit" in edit_page.path,
            hint=f"edit page path: {edit_page.path if edit_page else None}",
        )
        checks.check(
            "table element on List page",
            table_elements.exists(),
            hint=f"list page elements: {list(list_elements.values_list('content_type__model', flat=True))}",
        )
        checks.check(
            ">=2 columns (Name, Price)",
            col_count >= 2,
            hint=f"got {col_count} columns",
        )
        checks.check(
            "Name field referenced in column config",
            name_col_ok,
            hint=f"referenced field IDs: {referenced_field_ids}, name_field.id={name_field.id}",
        )
        checks.check(
            "link/button column for 'Edit'",
            len(link_columns) >= 1,
            hint=f"column types: {[getattr(c, 'type', None) for c in columns]}",
        )
        checks.check(
            "edit button column is type 'button'",
            any(getattr(c, "type", None) == "button" for c in link_columns),
            hint=f"link column types: {[getattr(c, 'type', None) for c in link_columns]}",
        )
        checks.check(
            "edit button action navigates to Edit page",
            action is not None and action.specific.navigate_to_page_id == edit_page.id,
            hint=(
                f"action={action}, navigate_to_page_id="
                f"{action.specific.navigate_to_page_id if action else None}, "
                f"expected={edit_page.id if edit_page else None}"
            ),
        )


# ---------------------------------------------------------------------------
# Filtered data source via view eval
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_filtered_data_source_via_view(data_fixture, eval_model):
    """Agent should switch to database mode to create a filtered view, then
    switch back to application mode to create a data source referencing it.

    Scenario: Tasks table with a Status single_select field. User wants a page
    showing only 'Pending' tasks. The agent should:
    1. switch_mode("database")
    2. create_views (grid view for the filter)
    3. create_view_filters (Status = Pending)
    4. switch_mode("application")
    5. create a data source with the view_id
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    database = data_fixture.create_database_application(
        user=user, workspace=workspace, name="Project DB"
    )
    table = data_fixture.create_database_table(
        user=user, database=database, name="Tasks"
    )
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    status_field = data_fixture.create_single_select_field(table=table, name="Status")
    data_fixture.create_select_option(
        field=status_field, value="Pending", color="light-orange"
    )
    data_fixture.create_select_option(
        field=status_field, value="Done", color="light-green"
    )

    builder = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="Task App"
    )

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
        question=PROMPT_FILTERED_DATA_SOURCE.format(
            builder_name=builder.name,
            table_name=table.name,
        ),
        ui_context=ui_context,
    )

    from baserow.contrib.database.views.models import View, ViewFilter

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    # Check tool call sequence
    switch_mode_calls = _filter_tool_calls(result, "switch_mode")

    switched_to_db = any(c["args"].get("mode") == "database" for c in switch_mode_calls)
    switched_back_to_app = any(
        c["args"].get("mode") == "application" for c in switch_mode_calls
    )

    # Verify DB state: view + filter created on the Tasks table
    views = View.objects.filter(table=table)
    view_filters = ViewFilter.objects.filter(view__table=table, field=status_field)

    # Verify DB state: data source service has a view FK set
    pages = Page.objects.filter(builder=builder, shared=False)
    data_sources = DataSource.objects.filter(page__builder=builder, page__shared=False)
    ds_view_ids = []
    for ds in data_sources:
        service = ds.service.specific if ds.service else None
        if service and hasattr(service, "view_id") and service.view_id:
            ds_view_ids.append(service.view_id)

    with EvalChecklist("filtered data source via view") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "switched to database mode",
            switched_to_db,
            hint=f"switch_mode calls: {[c['args'] for c in switch_mode_calls]}",
        )
        checks.check(
            "view created on Tasks table",
            views.exists(),
            hint=f"views for table: {list(views.values_list('name', flat=True))}",
        )
        checks.check(
            "view filter on Status field",
            view_filters.exists(),
            hint=f"view_filters: {list(view_filters.values_list('field__name', 'value'))}",
        )
        checks.check(
            "switched back to application mode",
            switched_back_to_app,
            hint=f"switch_mode calls: {[c['args'] for c in switch_mode_calls]}",
        )
        checks.check(
            "page created",
            pages.exists(),
            hint=f"pages: {list(pages.values_list('name', flat=True))}",
        )
        checks.check(
            "data source in DB has view set",
            len(ds_view_ids) >= 1,
            hint=f"data source view_ids in DB: {ds_view_ids}",
        )


# ---------------------------------------------------------------------------
# New page vs modifying existing page eval
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_new_page_not_modifies_existing(data_fixture, eval_model):
    """Agent should create a NEW landing page, not add elements to an existing page.

    Scenario: Builder already has a Home page with some content. User asks to
    "create a landing page". The agent should create a new page rather than
    modifying the existing Home page.
    """

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="Back to Local"
    )
    home_page = data_fixture.create_builder_page(builder=builder, name="Home", path="/")
    # Pre-populate with existing content so the agent sees it's not empty
    data_fixture.create_builder_heading_element(page=home_page, value="'Welcome Home'")
    data_fixture.create_builder_text_element(
        page=home_page, value="'Existing content on the home page.'"
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
        question=PROMPT_CREATE_LANDING_PAGE_WITH_EXISTING.format(
            builder_name=builder.name,
        ),
        ui_context=ui_context,
    )

    print_message_history(result)
    err_count, err_hint = count_tool_errors(result)

    # Check that a new page was created (not just the existing Home)
    pages = Page.objects.filter(builder=builder, shared=False)
    new_pages = pages.exclude(id=home_page.id)

    # Check elements were added to the NEW page, not the existing Home
    home_elements_after = Element.objects.filter(page=home_page)
    new_page_elements = (
        Element.objects.filter(page=new_pages.first())
        if new_pages.exists()
        else Element.objects.none()
    )

    # The home page started with 2 elements — if more were added, the agent
    # modified it instead of creating a new page
    home_element_count_before = 2
    home_was_modified = home_elements_after.count() > home_element_count_before

    # Check create_pages was called (not just setup_page on existing page)
    create_page_calls = _filter_tool_calls(result, "create_pages")
    setup_page_calls = _filter_tool_calls(result, "setup_page")

    # If setup_page was called, check it targeted a new page, not home_page
    setup_targeted_home = any(
        c["args"].get("page_id") == home_page.id for c in setup_page_calls
    )

    with EvalChecklist("creates new page not modifies existing") as checks:
        checks.check("no tool errors", err_count == 0, hint=err_hint)
        checks.check(
            "called create_pages",
            len(create_page_calls) >= 1,
            hint=f"tools: {[e.get('tool_name') for e in format_message_history(result) if e.get('tool_name')]}",
        )
        checks.check(
            "new page exists in DB",
            new_pages.exists(),
            hint=f"all pages: {list(pages.values_list('name', flat=True))}",
        )
        checks.check(
            "new page has elements",
            new_page_elements.count() >= 2,
            hint=f"new page elements: {new_page_elements.count()}",
        )
        checks.check(
            "home page was NOT modified",
            not home_was_modified,
            hint=f"home page elements: {home_elements_after.count()} (started with {home_element_count_before})",
        )
        checks.check(
            "setup_page did NOT target existing Home page",
            not setup_targeted_home,
            hint=f"setup_page page_ids: {[c['args'].get('page_id') for c in setup_page_calls]}",
        )
