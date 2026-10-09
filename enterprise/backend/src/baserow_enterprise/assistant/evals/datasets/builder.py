"""Kuma-builder eval dataset: Application Builder page/element/theme/user-source actions.

Includes the former ``test_eval_builder.py`` (12), ``test_eval_builder_proactive.py``
(2) and ``test_eval_builder_user_source.py`` (2) suites — all three shared the same
``application``-slot ``UIContext`` shape, so they live in one dataset.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, NamedTuple

from django.db.models import BooleanField, IntegerField, Q, Value
from django.db.models.functions import Coalesce

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.elements.actions import (
    CreateElementActionType,
    UpdateElementActionType,
)
from baserow.contrib.builder.elements.models import (
    Element,
    MenuElement,
    MenuItemElement,
    TableElement,
)
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.theme.models import ColorThemeConfigBlock
from baserow.contrib.builder.workflow_actions.models import (
    BuilderWorkflowAction,
    OpenPageWorkflowAction,
)
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View, ViewFilter
from baserow.contrib.integrations.local_baserow.models import LocalBaserowListRows
from baserow.core.cache import local_cache
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import BaserowFormulaObject, FormulaContext
from baserow.core.graph.types import GraphPointPosition
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.utils import get_value_at_path
from baserow.test_utils.fixtures import Fixtures
from baserow_enterprise.assistant.deps import AgentMode
from baserow_enterprise.assistant.evals.harness import tool_call_order_ok, tool_called
from baserow_enterprise.assistant.evals.registry import (
    register_case,
    register_scenario,
)
from baserow_enterprise.assistant.evals.scenarios import (
    build_builder_ui_context,
    build_workspace_ui_context,
)
from baserow_enterprise.assistant.evals.types import (
    CheckResult,
    EvalCase,
    EvalRunOutput,
    EvalScenario,
)
from baserow_enterprise.assistant.tools.builder.themes import builder_uses_theme
from baserow_enterprise.assistant.tools.builder.types.changes import name_key
from baserow_enterprise.assistant.tools.builder.types.menu_items import new_menu_link

# ---------------------------------------------------------------------------
# Prompts — verbatim from the legacy files
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

PROMPT_CREATE_PROJECTS_APP = (
    "Create an app showing projects in a list with cards showing "
    "project name and status."
)

PROMPT_NEW_TABLE = (
    "In builder '{builder_name}', set up a user source called 'App Users' "
    "so users can log in with roles: Admin and Viewer."
)

PROMPT_EXISTING_TABLE = (
    "In builder '{builder_name}', set up a user source called 'Members' "
    "using the existing table '{table_name}'."
)

PROMPT_EDIT_TABLE_COLUMNS = (
    "On the Students page of '{builder_name}', rename the table's Name column to "
    "Full name, move the Email column to the end, and fix the Adding date column: "
    "it is empty although every student has a Joined date."
)

PROMPT_MOVE_TABLE_COLUMN = (
    "On the Students page of '{builder_name}', move the table's Email column after "
    "the Website column."
)

PROMPT_LINK_COLUMN_NEW_TAB = (
    "On the Students page of '{builder_name}', make the table's Website column open "
    "in a new tab."
)

PROMPT_ADD_EDITAR_BUTTON_COLUMN = (
    "On the Students page of '{builder_name}', add a last column called Editar to "
    "the table, with a button that opens the Edit student page for that row."
)

# ---------------------------------------------------------------------------
# Local helpers — args inspection over output.messages (assistant-side entries)
# ---------------------------------------------------------------------------


def _filter_tool_calls(
    output: EvalRunOutput, tool_names: str | list[str] | set[str] | None = None
) -> list[dict]:
    """Return assistant-side tool call entries, optionally filtered by name(s)."""

    # Original arguments can remain malformed after successful tool-side repair.
    calls = [
        e
        for e in output.messages
        if e["role"] == "assistant" and isinstance(e.get("args"), dict)
    ]
    if tool_names is None:
        return calls
    names = {tool_names} if isinstance(tool_names, str) else set(tool_names)
    return [e for e in calls if e.get("tool_name") in names]


def _get_theme_primary_color(builder: Builder) -> str:
    """Refresh *builder* from the DB and return its theme primary color."""

    builder.refresh_from_db()
    try:
        return builder.colorthemeconfigblock.primary_color
    except ColorThemeConfigBlock.DoesNotExist:
        return ""


# ---------------------------------------------------------------------------
# Lists pages
# ---------------------------------------------------------------------------


@register_scenario("builder-lists-pages")
def _lists_pages_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="My App"
    )
    fx.create_builder_page(builder=builder, name="Home", path="/")
    fx.create_builder_page(builder=builder, name="About", path="/about")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
    )


def _check_lists_pages(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    return [
        CheckResult("called list_pages", tool_called(output, "list_pages") >= 1),
        CheckResult(
            "response mentions 'Home'",
            "Home" in output.answer,
            hint=output.answer[:300],
        ),
        CheckResult(
            "response mentions 'About'",
            "About" in output.answer,
            hint=output.answer[:300],
        ),
    ]


register_case(
    EvalCase(
        id="builder/lists-pages",
        dataset="kuma-builder",
        prompt=PROMPT_LIST_PAGES.format(builder_name="My App"),
        scenario="builder-lists-pages",
        checks=_check_lists_pages,
        mode=AgentMode.APPLICATION,
        max_iters=10,
    )
)

# ---------------------------------------------------------------------------
# Creates landing page
# ---------------------------------------------------------------------------


@register_scenario("builder-creates-landing-page")
def _creates_landing_page_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="Website"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={"builder": builder},
    )


class _SavedFormulaContext(FormulaContext):
    """Resolve saved formulas against explicit client data without generating formulas."""

    def __init__(self, values):
        super().__init__()
        self.values = values

    def __getitem__(self, key):
        missing = object()
        value = get_value_at_path(self.values, key, default=missing)
        if value is missing:
            raise KeyError(key)
        return value


def _render_saved_formula(formula, values=None) -> str | None:
    try:
        return str(
            resolve_formula(
                formula,
                formula_runtime_function_registry,
                _SavedFormulaContext(values or {}),
            )
        )
    except Exception:
        # An invalid or unsupported saved expression is a failed behavior check.
        return None


def _asked_user(output: EvalRunOutput) -> bool:
    """Whether the run ended by asking the user, through ask_user or plain text."""

    return bool(tool_called(output, "ask_user")) or "?" in output.answer


def _navigates_to_path(navigation, builder, path) -> bool:
    if navigation.navigation_type == "page":
        target = navigation.navigate_to_page
        return bool(
            target
            and not target.trashed
            and target.builder_id == builder.id
            and target.path == path
        )
    return (
        navigation.navigation_type == "custom"
        and _render_saved_formula(navigation.navigate_to_url) == path
    )


def _check_creates_landing_page(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builder = scenario.refs["builder"]
    page = Page.objects.filter(builder=builder, shared=False, path="/").first()
    elements = list(Element.objects.filter(page=page)) if page else []
    rendered = [
        (element, _render_saved_formula(getattr(element.specific, "value", "")))
        for element in elements
    ]
    headings = [
        text for element, text in rendered if element.get_type().type == "heading"
    ]
    descriptions = [
        text for element, text in rendered if element.get_type().type == "text"
    ]
    buttons = [
        element
        for element, text in rendered
        if (
            element.get_type().type == "button"
            or (
                element.get_type().type == "link"
                and element.specific.variant == "button"
            )
        )
        and text
        and "get started" in text.casefold()
    ]
    navigation = [
        _navigates_to_path(element.specific, builder, "/contact")
        for element in buttons
        if element.get_type().type == "link"
    ]
    for action in BuilderWorkflowAction.objects.filter(
        page=page,
        element__in=buttons,
        event="click",
        content_type__model="openpageworkflowaction",
    ):
        navigation.append(_navigates_to_path(action.specific, builder, "/contact"))
    return [
        CheckResult(
            "Home page exists at '/'", bool(page and "home" in page.name.casefold())
        ),
        CheckResult(
            "heading element with 'Welcome'",
            any(text and "welcome" in text.casefold() for text in headings),
            hint=f"saved headings: {headings}",
        ),
        CheckResult(
            "landing description is displayed",
            any(
                text and "this is our landing page" in text.casefold()
                for text in descriptions
            ),
            hint=f"saved descriptions: {descriptions}",
        ),
        CheckResult("button labeled 'Get Started'", bool(buttons)),
        CheckResult(
            "Get Started click navigates to /contact",
            any(navigation),
            hint="Requires a saved button click action or a LinkElement with button styling and working navigation.",
        ),
    ]


register_case(
    EvalCase(
        id="builder/creates-landing-page",
        dataset="kuma-builder",
        prompt=PROMPT_CREATE_LANDING_PAGE.format(builder_name="Website"),
        scenario="builder-creates-landing-page",
        checks=_check_creates_landing_page,
        mode=AgentMode.APPLICATION,
        max_iters=20,
    )
)

# ---------------------------------------------------------------------------
# Creates contact form
# ---------------------------------------------------------------------------


@register_scenario("builder-creates-contact-form")
def _creates_contact_form_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="Contact App"
    )
    database = fx.create_database_application(
        user=user, workspace=workspace, name="CRM"
    )
    table = fx.create_database_table(user=user, database=database, name="Contacts")
    name_field = fx.create_text_field(table=table, name="Name", primary=True)
    email_field = fx.create_email_field(table=table, name="Email")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={
            "builder": builder,
            "table": table,
            "name_field": name_field,
            "email_field": email_field,
        },
    )


def _check_creates_contact_form(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builder = scenario.refs["builder"]
    table = scenario.refs["table"]
    name_field = scenario.refs["name_field"]
    email_field = scenario.refs["email_field"]

    pages = Page.objects.filter(builder=builder, shared=False)
    page = pages.filter(path="/contact").first()
    elements = Element.objects.filter(page=page) if page else Element.objects.none()

    actions = (
        BuilderWorkflowAction.objects.filter(page=page)
        if page
        else BuilderWorkflowAction.objects.none()
    )
    create_row_action = actions.filter(
        content_type__model="localbaserowcreaterowworkflowaction",
        element__content_type__model="formcontainerelement",
        event="submit",
    ).first()

    service = None
    mappings: dict = {}
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

    return [
        CheckResult("page created", pages.exists(), hint="no pages found in DB"),
        CheckResult(
            "page name is 'Contact'",
            page is not None and "contact" in page.name.lower(),
            hint=f"page name: {page.name if page else None}",
        ),
        CheckResult(
            "page path is '/contact'",
            page is not None and page.path == "/contact",
            hint=f"page path: {page.path if page else None}",
        ),
        CheckResult(
            ">=3 elements (form container + inputs)",
            elements.count() >= 3,
            hint=f"got {elements.count()} elements",
        ),
        CheckResult(
            "form submit create_row action exists",
            create_row_action is not None,
            hint=f"action types: {list(actions.values_list('content_type__model', flat=True))}",
        ),
        CheckResult(
            "create_row targets Contacts table",
            service is not None and service.table_id == table.id,
            hint=(
                f"service table_id={service.table_id if service else None}, "
                f"expected={table.id}"
            ),
        ),
        CheckResult(
            "Name field is mapped",
            name_field.id in mappings,
            hint=f"mapped field IDs: {set(mappings)}",
        ),
        CheckResult(
            "Email field is mapped",
            email_field.id in mappings,
            hint=f"mapped field IDs: {set(mappings)}",
        ),
        CheckResult(
            "all field mappings reference form input elements",
            all_map_formulas_ok,
            hint=f"formulas: {list(mappings.values())}, form input IDs: {form_input_ids}",
        ),
    ]


register_case(
    EvalCase(
        id="builder/creates-contact-form",
        dataset="kuma-builder",
        # table_id/name_field_id/email_field_id are unused by the template — the
        # ids are deliberately withheld from the LLM (see legacy C.3 quirk).
        prompt=PROMPT_CREATE_CONTACT_FORM.format(
            builder_name="Contact App",
            table_name="Contacts",
            table_id=0,
            name_field_id=0,
            email_field_id=0,
        ),
        scenario="builder-creates-contact-form",
        checks=_check_creates_contact_form,
        mode=AgentMode.APPLICATION,
        max_iters=25,
    )
)

# ---------------------------------------------------------------------------
# Creates data source with repeat
# ---------------------------------------------------------------------------


@register_scenario("builder-creates-data-source-with-repeat")
def _creates_data_source_with_repeat_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="Product Catalog"
    )
    database = fx.create_database_application(
        user=user, workspace=workspace, name="Store"
    )
    table = fx.create_database_table(user=user, database=database, name="Products")
    fx.create_text_field(table=table, name="Name", primary=True)
    fx.create_number_field(table=table, name="Price")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={"builder": builder, "table": table},
    )


def _check_creates_data_source_with_repeat(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builder = scenario.refs["builder"]
    table = scenario.refs["table"]

    page = Page.objects.filter(builder=builder, shared=False, path="/products").first()
    if tool_called(output, "setup_page"):
        order_ok = tool_call_order_ok(output, ["create_pages", "setup_page"])
    else:
        order_ok = tool_call_order_ok(
            output,
            ["create_pages", "create_data_sources", "create_collection_elements"],
        )

    sources = list(DataSource.objects.filter(page=page)) if page else []
    matching_sources = {
        source.id
        for source in sources
        if source.name.casefold() == "all products"
        and source.service_id is not None
        and isinstance(source.service.specific, LocalBaserowListRows)
        and source.service.specific.table_id == table.id
    }
    repeats = [
        element
        for element in (Element.objects.filter(page=page) if page else [])
        if element.get_type().type == "repeat"
        and element.specific.data_source_id in matching_sources
    ]

    return [
        CheckResult(
            "create_pages before setup_page or "
            "create_data_sources+create_collection_elements",
            order_ok,
        ),
        CheckResult("page created at '/products'", page is not None),
        CheckResult(
            "page name is 'Products'",
            page is not None and "product" in page.name.lower(),
            hint=f"page name: {page.name if page else None}",
        ),
        CheckResult(
            "saved All Products data source lists the Products table",
            bool(matching_sources),
            hint=f"saved data sources: {[source.name for source in sources]}",
        ),
        CheckResult(
            "repeat uses the All Products data source",
            bool(repeats),
        ),
        CheckResult(
            "heading is inside the Products repeat",
            any(
                child.get_type().type == "heading"
                for repeat in repeats
                for child in page.get_graph().get_descendants(repeat)
            ),
        ),
    ]


register_case(
    EvalCase(
        id="builder/creates-data-source-with-repeat",
        dataset="kuma-builder",
        # table_id is unused by the template — withheld from the LLM.
        prompt=PROMPT_CREATE_DATA_SOURCE_PAGE.format(
            builder_name="Product Catalog", table_name="Products", table_id=0
        ),
        scenario="builder-creates-data-source-with-repeat",
        checks=_check_creates_data_source_with_repeat,
        mode=AgentMode.APPLICATION,
        max_iters=25,
    )
)

# ---------------------------------------------------------------------------
# Shared header with menu
# ---------------------------------------------------------------------------


@register_scenario("builder-creates-header-with-menu")
def _creates_header_with_menu_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="Nav App"
    )
    home = fx.create_builder_page(builder=builder, name="Home", path="/")
    about = fx.create_builder_page(builder=builder, name="About", path="/about")
    contact = fx.create_builder_page(builder=builder, name="Contact", path="/contact")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={"builder": builder, "home": home, "about": about, "contact": contact},
    )


def _check_creates_header_with_menu(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builder = scenario.refs["builder"]
    home = scenario.refs["home"]
    about = scenario.refs["about"]
    contact = scenario.refs["contact"]

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

    return [
        CheckResult(
            "called create_layout_elements",
            tool_called(output, "create_layout_elements") >= 1,
        ),
        CheckResult(
            "header element on shared page",
            header_elements.exists(),
            hint=(
                "shared page elements: "
                f"{list(shared_elements.values_list('content_type__model', flat=True))}"
            ),
        ),
        CheckResult(
            "menu element on shared page",
            menu_elements.exists(),
            hint="expected a menu element inside the header on the shared page",
        ),
        CheckResult(
            ">=3 menu items (Home, About, Contact)",
            menu_items.count() >= 3,
            hint=f"got {menu_items.count()} menu items",
        ),
        CheckResult(
            "menu links to Home page",
            home.id in linked_page_ids,
            hint=f"linked page IDs: {linked_page_ids}, expected Home={home.id}",
        ),
        CheckResult(
            "menu links to About page",
            about.id in linked_page_ids,
            hint=f"linked page IDs: {linked_page_ids}, expected About={about.id}",
        ),
        CheckResult(
            "menu links to Contact page",
            contact.id in linked_page_ids,
            hint=f"linked page IDs: {linked_page_ids}, expected Contact={contact.id}",
        ),
    ]


register_case(
    EvalCase(
        id="builder/creates-header-with-menu",
        dataset="kuma-builder",
        prompt=PROMPT_SHARED_HEADER_WITH_MENU.format(builder_name="Nav App"),
        scenario="builder-creates-header-with-menu",
        checks=_check_creates_header_with_menu,
        mode=AgentMode.APPLICATION,
        max_iters=25,
    )
)

# ---------------------------------------------------------------------------
# Back button on page, not header
# ---------------------------------------------------------------------------


@register_scenario("builder-back-button-on-page-not-header")
def _back_button_on_page_not_header_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(user=user, workspace=workspace, name="App")
    fx.create_builder_page(builder=builder, name="List", path="/list")
    detail_page = fx.create_builder_page(builder=builder, name="Detail", path="/detail")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={"builder": builder, "detail_page": detail_page},
    )


def _check_back_button_on_page_not_header(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builder = scenario.refs["builder"]
    detail_page = scenario.refs["detail_page"]

    detail_elements = Element.objects.filter(page=detail_page)
    shared_elements = Element.objects.filter(page=builder.shared_page)

    buttons = [
        element
        for element in detail_elements
        if (
            element.get_type().type == "button"
            or (
                element.get_type().type == "link"
                and element.specific.variant == "button"
            )
        )
        and (_render_saved_formula(element.specific.value) or "").casefold()
        == "back to list"
    ]
    navigation = [
        _navigates_to_path(element.specific, builder, "/list")
        for element in buttons
        if element.get_type().type == "link"
    ]
    navigation.extend(
        _navigates_to_path(action.specific, builder, "/list")
        for action in BuilderWorkflowAction.objects.filter(
            page=detail_page,
            element__in=buttons,
            event="click",
            content_type__model="openpageworkflowaction",
        )
    )

    return [
        CheckResult(
            "called create_display_elements",
            tool_called(output, "create_display_elements") >= 1,
        ),
        CheckResult(
            "elements exist on Detail page",
            detail_elements.exists(),
            hint="no elements on Detail page",
        ),
        CheckResult("saved button labeled 'Back to List'", bool(buttons)),
        CheckResult("back button navigates to List", any(navigation)),
        CheckResult(
            "no elements added to shared page",
            not shared_elements.exists(),
            hint=(
                "shared page has: "
                f"{list(shared_elements.values_list('content_type__model', flat=True))}"
            ),
        ),
    ]


register_case(
    EvalCase(
        id="builder/back-button-on-page-not-header",
        dataset="kuma-builder",
        prompt=PROMPT_BACK_BUTTON_ON_DETAIL.format(builder_name="App"),
        scenario="builder-back-button-on-page-not-header",
        checks=_check_back_button_on_page_not_header,
        mode=AgentMode.APPLICATION,
        max_iters=25,
    )
)

# ---------------------------------------------------------------------------
# Page-specific nav on page (not header)
# ---------------------------------------------------------------------------


@register_scenario("builder-page-specific-nav-on-page")
def _page_specific_nav_on_page_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(user=user, workspace=workspace, name="App")
    list_page = fx.create_builder_page(builder=builder, name="List", path="/list")
    detail_page = fx.create_builder_page(builder=builder, name="Detail", path="/detail")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={"builder": builder, "list_page": list_page, "detail_page": detail_page},
    )


def _check_page_specific_nav_on_page(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builder = scenario.refs["builder"]
    list_page = scenario.refs["list_page"]
    detail_page = scenario.refs["detail_page"]

    detail_elements = Element.objects.filter(page=detail_page)
    shared_elements = Element.objects.filter(page=builder.shared_page)

    link_elements = detail_elements.filter(content_type__model="linkelement")
    button_elements = detail_elements.filter(content_type__model="buttonelement")
    menu_elements = detail_elements.filter(content_type__model="menuelement")

    link_targets_list = False
    if link_elements.exists():
        link_el = link_elements.first().specific
        link_targets_list = link_el.navigate_to_page_id == list_page.id or (
            "/list" in str(link_el.navigate_to_url)
        )

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

    return [
        CheckResult(
            "called create_display_elements",
            tool_called(output, "create_display_elements") >= 1,
        ),
        CheckResult(
            "elements exist on Detail page",
            detail_elements.exists(),
            hint="no elements on Detail page",
        ),
        CheckResult(
            "link/button/menu element on Detail page",
            has_nav_element,
            hint=(
                "detail page elements: "
                f"{list(detail_elements.values_list('content_type__model', flat=True))}"
            ),
        ),
        CheckResult(
            "nav element targets List page",
            link_targets_list or menu_links_list,
            hint=f"link_targets_list={link_targets_list}, menu_links_list={menu_links_list}",
        ),
        CheckResult(
            "no elements added to shared page",
            not shared_elements.exists(),
            hint=(
                "shared page has: "
                f"{list(shared_elements.values_list('content_type__model', flat=True))}"
            ),
        ),
    ]


register_case(
    EvalCase(
        id="builder/page-specific-nav-on-page",
        dataset="kuma-builder",
        prompt=PROMPT_BACK_LINK_ON_DETAIL.format(builder_name="App"),
        scenario="builder-page-specific-nav-on-page",
        checks=_check_page_specific_nav_on_page,
        mode=AgentMode.APPLICATION,
        max_iters=25,
    )
)

# ---------------------------------------------------------------------------
# Creates app with theme (workspace-only ui_context — DATABASE mode)
# ---------------------------------------------------------------------------


@register_scenario("builder-creates-app-with-theme")
def _creates_app_with_theme_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_workspace_ui_context(user, workspace),
    )


def _check_creates_app_with_theme(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builders = Builder.objects.filter(
        workspace=scenario.workspace, name__icontains="Dashboard"
    )
    builder = builders.first()
    primary_color = _get_theme_primary_color(builder) if builder else ""
    default_color = "#5190efff"

    return [
        CheckResult(
            "called create_builders", tool_called(output, "create_builders") >= 1
        ),
        CheckResult(
            "builder 'Dashboard' created",
            builders.exists(),
            hint="no builder named 'Dashboard' found",
        ),
        CheckResult(
            "eclipse theme applied (color differs from default)",
            primary_color != default_color,
            hint=f"primary_color={primary_color}, default={default_color}",
        ),
    ]


register_case(
    EvalCase(
        id="builder/creates-app-with-theme",
        dataset="kuma-builder",
        prompt=PROMPT_CREATE_APP_WITH_DARK_THEME,
        scenario="builder-creates-app-with-theme",
        checks=_check_creates_app_with_theme,
        # The legacy test built a bare workspace UIContext and called
        # agent.run_sync directly, bypassing mode derivation — deps.mode stayed
        # at its AssistantDeps default of DATABASE. Preserved as-is.
        mode=AgentMode.DATABASE,
        max_iters=15,
    )
)

# ---------------------------------------------------------------------------
# Changes theme
# ---------------------------------------------------------------------------


@register_scenario("builder-changes-theme")
def _changes_theme_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="My App"
    )
    initial_color = _get_theme_primary_color(builder)
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={"builder": builder},
        pre_state={"initial_color": initial_color},
    )


def _check_changes_theme(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builder = scenario.refs["builder"]
    initial_color = scenario.pre_state["initial_color"]

    new_color = _get_theme_primary_color(builder)

    return [
        CheckResult("called set_theme", bool(tool_called(output, "set_theme"))),
        CheckResult("saved theme is midnight", builder_uses_theme(builder, "midnight")),
        CheckResult(
            "theme color changed",
            new_color != initial_color,
            hint=f"color still '{initial_color}' after set_theme",
        ),
    ]


register_case(
    EvalCase(
        id="builder/changes-theme",
        dataset="kuma-builder",
        prompt=PROMPT_CHANGE_THEME.format(builder_name="My App"),
        scenario="builder-changes-theme",
        checks=_check_changes_theme,
        mode=AgentMode.APPLICATION,
        max_iters=15,
    )
)

# ---------------------------------------------------------------------------
# Creates table with edit button (deepest check in the dataset)
# ---------------------------------------------------------------------------


@register_scenario("builder-creates-table-with-edit-button")
def _creates_table_with_edit_button_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="Product App"
    )
    database = fx.create_database_application(
        user=user, workspace=workspace, name="Store"
    )
    table = fx.create_database_table(user=user, database=database, name="Products")
    name_field = fx.create_text_field(table=table, name="Name", primary=True)
    fx.create_number_field(table=table, name="Price")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={"builder": builder, "name_field": name_field},
    )


def _check_creates_table_with_edit_button(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builder = scenario.refs["builder"]
    name_field = scenario.refs["name_field"]

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

    field_id_re = re.compile(r"field_(\d+)")
    referenced_field_ids: set[int] = set()
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

    action = None
    if link_columns:
        link_col = link_columns[0]
        action = BuilderWorkflowAction.objects.filter(
            page=list_page, event=f"{link_col.uid}_click", element=table_el
        ).first()

    return [
        CheckResult(
            "called setup_page or create_pages",
            len(_filter_tool_calls(output, ["setup_page", "create_pages"])) >= 1,
        ),
        CheckResult(
            "List page created",
            list_page is not None,
            hint=f"pages: {list(pages.values_list('name', flat=True))}",
        ),
        CheckResult(
            "List page path is '/list'",
            list_page is not None and list_page.path == "/list",
            hint=f"list page path: {list_page.path if list_page else None}",
        ),
        CheckResult(
            "Edit page created",
            edit_page is not None,
            hint=f"pages: {list(pages.values_list('name', flat=True))}",
        ),
        CheckResult(
            "Edit page path contains '/edit'",
            edit_page is not None and "/edit" in edit_page.path,
            hint=f"edit page path: {edit_page.path if edit_page else None}",
        ),
        CheckResult(
            "table element on List page",
            table_elements.exists(),
            hint=(
                "list page elements: "
                f"{list(list_elements.values_list('content_type__model', flat=True))}"
            ),
        ),
        CheckResult(
            ">=2 columns (Name, Price)", col_count >= 2, hint=f"got {col_count} columns"
        ),
        CheckResult(
            "Name field referenced in column config",
            name_col_ok,
            hint=(
                f"referenced field IDs: {referenced_field_ids}, "
                f"name_field.id={name_field.id}"
            ),
        ),
        CheckResult(
            "link/button column for 'Edit'",
            len(link_columns) >= 1,
            hint=f"column types: {[getattr(c, 'type', None) for c in columns]}",
        ),
        CheckResult(
            "edit button column is type 'button'",
            any(getattr(c, "type", None) == "button" for c in link_columns),
            hint=f"link column types: {[getattr(c, 'type', None) for c in link_columns]}",
        ),
        CheckResult(
            "edit button action navigates to Edit page",
            action is not None and action.specific.navigate_to_page_id == edit_page.id,
            hint=(
                f"action={action}, navigate_to_page_id="
                f"{action.specific.navigate_to_page_id if action else None}, "
                f"expected={edit_page.id if edit_page else None}"
            ),
        ),
    ]


register_case(
    EvalCase(
        id="builder/creates-table-with-edit-button",
        dataset="kuma-builder",
        prompt=PROMPT_TABLE_WITH_EDIT_BUTTON.format(
            builder_name="Product App",
            table_name="Products",
            field_names="Name and Price",
        ),
        scenario="builder-creates-table-with-edit-button",
        checks=_check_creates_table_with_edit_button,
        mode=AgentMode.APPLICATION,
        max_iters=30,
    )
)


class _ColumnSnapshot(NamedTuple):
    uid: str
    name: str
    type: str
    config: dict
    styles: dict | None


def _table_column_snapshot(table_element_id: int) -> list[_ColumnSnapshot]:
    """
    Read a table element's columns as comparable tuples, in display order.

    :param table_element_id: The table element to read.
    :return: (uid, name, type, config, styles) per column. Empty when the element was
        deleted, so checks fail instead of raising.
    """

    table_element = TableElement.objects.filter(id=table_element_id).first()
    if table_element is None:
        return []
    return [
        _ColumnSnapshot(
            str(column.uid), column.name, column.type, column.config, column.styles
        )
        for column in table_element.fields.order_by("order", "id")
    ]


def _by_uid(snapshot: list[_ColumnSnapshot]) -> dict[str, _ColumnSnapshot]:
    return {column.uid: column for column in snapshot}


def _column_differences(
    before: list[_ColumnSnapshot], after: list[_ColumnSnapshot]
) -> str:
    """
    Summarize how a table's columns differ from the seed, for a check hint.

    :param before: The columns right after seeding.
    :param after: The columns now.
    :return: The current column names in order, the ones that changed or were added,
        and the ones removed.
    """

    changed = [column.name for column in after if column not in before]
    removed = [column.name for column in before if column not in after]
    return (
        f"columns: {[column.name for column in after]}, "
        f"changed or added: {changed}, removed: {removed}"
    )


def _references_field(config: dict, field_id: int) -> bool:
    return re.search(rf"\bfield_{field_id}\b", str(config)) is not None


def _formula_text(value: Any) -> str:
    return BaserowFormulaObject.to_formula(value).get("formula") or ""


def _record_field_formula(field: Field) -> BaserowFormulaObject:
    return BaserowFormulaObject.create(f"get('current_record.field_{field.id}')")


def _edit_action_exists(refs: dict[str, Any]) -> bool:
    return BuilderWorkflowAction.objects.filter(id=refs["edit_action_id"]).exists()


def _opens_page_with_row_id(action: OpenPageWorkflowAction, page: Page) -> bool:
    return (
        action.navigation_type == "page"
        and action.navigate_to_page_id == page.id
        and any(
            "current_record.id" in _formula_text(parameter.get("value"))
            for parameter in action.page_parameters or []
        )
    )


@register_scenario("builder-edits-table-columns")
def _edits_table_columns_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="School App"
    )
    database = fx.create_database_application(
        user=user, workspace=workspace, name="School"
    )
    table = fx.create_database_table(user=user, database=database, name="Students")
    name_field = fx.create_text_field(table=table, name="Name", primary=True)
    email_field = fx.create_text_field(table=table, name="Email")
    joined_field = fx.create_date_field(table=table, name="Joined")
    website_field = fx.create_url_field(table=table, name="Website")
    RowHandler().force_create_rows(
        user,
        table,
        [
            {
                name_field.db_column: "Ada Lovelace",
                email_field.db_column: "ada@example.com",
                joined_field.db_column: "2025-09-01",
                website_field.db_column: "https://example.com/ada",
            },
            {
                name_field.db_column: "Alan Turing",
                email_field.db_column: "alan@example.com",
                joined_field.db_column: "2025-09-15",
                website_field.db_column: "https://example.com/alan",
            },
        ],
    )
    integration = fx.create_local_baserow_integration(user=user, application=builder)
    students_page = fx.create_builder_page(
        builder=builder, name="Students", path="/students"
    )
    edit_page = fx.create_builder_page(
        builder=builder,
        name="Edit student",
        path="/student/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )
    data_source = fx.create_builder_local_baserow_list_rows_data_source(
        page=students_page, name="Students", table=table, integration=integration
    )

    # Simple-mode formulas, as the editor writes them; Kuma writes advanced ones.
    table_element = fx.create_builder_table_element(
        user=user,
        page=students_page,
        data_source=data_source,
        fields=[
            {
                "name": "Name",
                "type": "text",
                "config": {"value": _record_field_formula(name_field)},
                "styles": {"cell": {"cell_font_color": "red"}},
            },
            {
                "name": "Email",
                "type": "text",
                "config": {"value": _record_field_formula(email_field)},
            },
            {
                "name": "Adding date",
                "type": "text",
                "config": {"value": BaserowFormulaObject.create("")},
            },
            {
                "name": "Website",
                "type": "link",
                "config": {
                    "navigation_type": "custom",
                    "navigate_to_url": _record_field_formula(website_field),
                    "link_name": _record_field_formula(website_field),
                    "target": "self",
                    "variant": "link",
                    "page_parameters": [],
                    "query_parameters": [],
                },
            },
            {
                "name": "Edit",
                "type": "button",
                "config": {"label": BaserowFormulaObject.create("'Edit'")},
            },
        ],
    )
    uids = {column.name: str(column.uid) for column in table_element.fields.all()}
    edit_action = fx.create_open_page_workflow_action(
        page=students_page,
        element=table_element,
        event=f"{uids['Edit']}_click",
        navigation_type="page",
        navigate_to_page=edit_page,
        page_parameters=[
            {
                "name": "id",
                "value": BaserowFormulaObject.create("get('current_record.id')"),
            }
        ],
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={
            "builder": builder,
            "table_element_id": table_element.id,
            "edit_page": edit_page,
            "joined_field": joined_field,
            "uids": uids,
            "before": _table_column_snapshot(table_element.id),
            "edit_action_id": edit_action.id,
        },
    )


def _check_edits_table_columns(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    refs = scenario.refs
    uids = refs["uids"]
    before = _by_uid(refs["before"])
    after = _table_column_snapshot(refs["table_element_id"])
    by_uid = _by_uid(after)
    names = [column.name for column in after]
    name_before = before[uids["Name"]]
    name_now = by_uid.get(uids["Name"])
    adding_date = by_uid.get(uids["Adding date"])
    website = by_uid.get(uids["Website"])
    email = by_uid.get(uids["Email"])
    edit = by_uid.get(uids["Edit"])
    edit_action_exists = _edit_action_exists(refs)

    return [
        CheckResult("table has 5 columns", len(after) == 5, hint=f"columns: {names}"),
        CheckResult(
            "no two column names match after trimming and ignoring case",
            len({name.strip().casefold() for name in names}) == len(names),
            hint=f"columns: {names}",
        ),
        CheckResult(
            "Name column is named 'Full name' and keeps its config and styles",
            name_now is not None
            and name_now.name == "Full name"
            and name_now.config == name_before.config
            and name_now.styles == name_before.styles,
            hint=f"Name column now: {name_now}",
        ),
        CheckResult(
            "Email column is last",
            bool(after) and after[-1].uid == uids["Email"],
            hint=f"columns: {names}",
        ),
        CheckResult(
            "Email column is unchanged apart from its position",
            email == before[uids["Email"]],
            hint=f"Email column now: {email}",
        ),
        CheckResult(
            "Adding date column keeps its uid and reads the Joined field",
            adding_date is not None
            and _references_field(adding_date.config, refs["joined_field"].id),
            hint=f"Adding date column now: {adding_date}",
        ),
        CheckResult(
            "Website column is unchanged",
            website == before[uids["Website"]],
            hint=f"Website column now: {website}",
        ),
        CheckResult(
            "Edit column is unchanged and keeps its click action",
            edit == before[uids["Edit"]] and edit_action_exists,
            hint=f"Edit column now: {edit}, click action exists: {edit_action_exists}",
        ),
    ]


def _check_moves_table_column(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    uids = scenario.refs["uids"]
    before = scenario.refs["before"]
    after = _table_column_snapshot(scenario.refs["table_element_id"])
    expected_order = ["Name", "Adding date", "Website", "Email", "Edit"]

    return [
        CheckResult(
            f"columns are ordered {', '.join(expected_order)}",
            [column.uid for column in after] == [uids[name] for name in expected_order],
            hint=f"columns: {[column.name for column in after]}",
        ),
        CheckResult(
            "no column changed apart from its position",
            _by_uid(after) == _by_uid(before),
            hint=_column_differences(before, after),
        ),
    ]


def _check_keeps_link_column_settings(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    before = scenario.refs["before"]
    after = _table_column_snapshot(scenario.refs["table_element_id"])

    return [
        CheckResult("called list_elements", tool_called(output, "list_elements") >= 1),
        CheckResult(
            "no table column was changed, moved, added or removed",
            after == before,
            hint=_column_differences(before, after),
        ),
    ]


def _check_adds_edit_button_column(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    refs = scenario.refs
    before = refs["before"]
    after = _table_column_snapshot(refs["table_element_id"])
    last = after[-1] if after else None
    new_column = last if last is not None and last.uid not in _by_uid(before) else None
    is_editar_button = (
        new_column is not None
        and new_column.type == "button"
        and new_column.name.strip().casefold() == "editar"
    )
    opens_edit_page = new_column is not None and any(
        _opens_page_with_row_id(action, refs["edit_page"])
        for action in OpenPageWorkflowAction.objects.filter(
            element_id=refs["table_element_id"], event=f"{new_column.uid}_click"
        )
    )
    table_events = list(
        BuilderWorkflowAction.objects.filter(
            element_id=refs["table_element_id"]
        ).values_list("event", flat=True)
    )
    edit_action_exists = _edit_action_exists(refs)

    return [
        CheckResult(
            "table has 6 columns",
            len(after) == 6,
            hint=f"columns: {[column.name for column in after]}",
        ),
        CheckResult(
            "the first five columns are unchanged",
            after[:5] == before,
            hint=_column_differences(before, after[:5]),
        ),
        CheckResult(
            "last column is a new button column named Editar",
            is_editar_button,
            hint=f"last column: {last}",
        ),
        CheckResult(
            "new column's button opens the Edit student page with the row id",
            opens_edit_page,
            hint=f"events of the table's actions: {table_events}",
        ),
        CheckResult(
            "Edit column's click action still exists",
            edit_action_exists,
            hint=f"events of the table's actions: {table_events}",
        ),
    ]


register_case(
    EvalCase(
        id="builder/edits-table-columns",
        dataset="kuma-builder",
        prompt=PROMPT_EDIT_TABLE_COLUMNS.format(builder_name="School App"),
        scenario="builder-edits-table-columns",
        checks=_check_edits_table_columns,
        mode=AgentMode.APPLICATION,
        max_iters=20,
    )
)

register_case(
    EvalCase(
        id="builder/moves-table-column",
        dataset="kuma-builder",
        prompt=PROMPT_MOVE_TABLE_COLUMN.format(builder_name="School App"),
        scenario="builder-edits-table-columns",
        checks=_check_moves_table_column,
        mode=AgentMode.APPLICATION,
        max_iters=20,
    )
)

register_case(
    EvalCase(
        id="builder/keeps-link-column-settings",
        dataset="kuma-builder",
        prompt=PROMPT_LINK_COLUMN_NEW_TAB.format(builder_name="School App"),
        scenario="builder-edits-table-columns",
        checks=_check_keeps_link_column_settings,
        mode=AgentMode.APPLICATION,
        max_iters=20,
        # A refused attempt is fine here: the columns' state decides the case.
        max_tool_errors=2,
    )
)

register_case(
    EvalCase(
        id="builder/adds-edit-button-column",
        dataset="kuma-builder",
        prompt=PROMPT_ADD_EDITAR_BUTTON_COLUMN.format(builder_name="School App"),
        scenario="builder-edits-table-columns",
        checks=_check_adds_edit_button_column,
        mode=AgentMode.APPLICATION,
        max_iters=20,
    )
)

# ---------------------------------------------------------------------------
# Filtered data source via view (cross-mode)
# ---------------------------------------------------------------------------


@register_scenario("builder-filtered-data-source-via-view")
def _filtered_data_source_via_view_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(
        user=user, workspace=workspace, name="Project DB"
    )
    table = fx.create_database_table(user=user, database=database, name="Tasks")
    fx.create_text_field(table=table, name="Name", primary=True)
    status_field = fx.create_single_select_field(table=table, name="Status")
    fx.create_select_option(field=status_field, value="Pending", color="light-orange")
    fx.create_select_option(field=status_field, value="Done", color="light-green")
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="Task App"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={"builder": builder, "table": table, "status_field": status_field},
    )


def _check_filtered_data_source_via_view(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builder = scenario.refs["builder"]
    table = scenario.refs["table"]
    status_field = scenario.refs["status_field"]
    options = dict(status_field.select_options.values_list("id", "value"))
    model = table.get_model()
    matching_view_ids = set()
    for view in View.objects.filter(table=table):
        filters = list(ViewFilter.objects.filter(view=view))
        # This case requests only a Status predicate. Use the same grouped
        # expression as the data source, probing every Status and the empty value
        # without inserting rows. Data sources apply it even if the view UI has
        # filters_disabled, unlike ViewHandler.apply_filters.
        if not filters or any(
            item.field_id != status_field.id
            or item.type not in {"single_select_equal", "single_select_is_any_of"}
            for item in filters
        ):
            continue
        predicate, annotations = (
            ViewHandler().get_filter_builder(view, model).get_filters_and_annotations()
        )
        if annotations:
            continue
        # SQL WHERE excludes NULL, whereas Q.check defaults unknown to true.
        predicate = Q(Coalesce(predicate, False, output_field=BooleanField()))
        if "Pending" in options.values() and all(
            predicate.check(
                {f"{status_field.db_column}_id": Value(option_id, IntegerField())}
            )
            == (label == "Pending")
            for option_id, label in [*options.items(), (None, None)]
        ):
            matching_view_ids.add(view.id)
    sources = DataSource.objects.filter(page__builder=builder, page__shared=False)
    matching_sources = []
    for source in sources:
        service = source.service.specific if source.service else None
        if (
            isinstance(service, LocalBaserowListRows)
            and service.table_id == table.id
            and service.view_id in matching_view_ids
        ):
            matching_sources.append(source.id)
    return [
        CheckResult(
            "view restricts Tasks to Pending Status",
            bool(matching_view_ids),
            hint=f"matching view IDs: {sorted(matching_view_ids)}",
        ),
        CheckResult(
            "page created", Page.objects.filter(builder=builder, shared=False).exists()
        ),
        CheckResult(
            "saved data source uses the filtered Tasks view",
            bool(matching_sources),
            hint=f"matching source IDs: {matching_sources}",
        ),
    ]


register_case(
    EvalCase(
        id="builder/filtered-data-source-via-view",
        dataset="kuma-builder",
        prompt=PROMPT_FILTERED_DATA_SOURCE.format(
            builder_name="Task App", table_name="Tasks"
        ),
        scenario="builder-filtered-data-source-via-view",
        checks=_check_filtered_data_source_via_view,
        mode=AgentMode.APPLICATION,
        max_iters=30,
    )
)

# ---------------------------------------------------------------------------
# Creates new page, does not modify existing page
# ---------------------------------------------------------------------------


@register_scenario("builder-creates-new-page-not-modifies-existing")
def _creates_new_page_not_modifies_existing_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="Back to Local"
    )
    home_page = fx.create_builder_page(builder=builder, name="Home", path="/")
    fx.create_builder_heading_element(page=home_page, value="'Welcome Home'")
    fx.create_builder_text_element(
        page=home_page, value="'Existing content on the home page.'"
    )
    home_element_count = Element.objects.filter(page=home_page).count()
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={"builder": builder, "home_page": home_page},
        pre_state={
            "home_element_count": home_element_count,
            "home_page_id": home_page.id,
        },
    )


def _check_creates_new_page_not_modifies_existing(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builder = scenario.refs["builder"]
    home_page = scenario.refs["home_page"]
    home_element_count_before = scenario.pre_state["home_element_count"]

    pages = Page.objects.filter(builder=builder, shared=False)
    new_pages = pages.exclude(id=home_page.id)

    home_elements_after = Element.objects.filter(page=home_page)
    new_page_elements = (
        Element.objects.filter(page=new_pages.first())
        if new_pages.exists()
        else Element.objects.none()
    )
    home_was_modified = home_elements_after.count() > home_element_count_before

    setup_page_calls = _filter_tool_calls(output, "setup_page")
    setup_targeted_home = any(
        c["args"].get("page_id") == home_page.id for c in setup_page_calls
    )

    return [
        CheckResult("called create_pages", tool_called(output, "create_pages") >= 1),
        CheckResult(
            "new page exists in DB",
            new_pages.exists(),
            hint=f"all pages: {list(pages.values_list('name', flat=True))}",
        ),
        CheckResult(
            "new page has elements",
            new_page_elements.count() >= 2,
            hint=f"new page elements: {new_page_elements.count()}",
        ),
        CheckResult(
            "home page was NOT modified",
            not home_was_modified,
            hint=(
                f"home page elements: {home_elements_after.count()} "
                f"(started with {home_element_count_before})"
            ),
        ),
        CheckResult(
            "setup_page did NOT target existing Home page",
            not setup_targeted_home,
            hint=f"setup_page page_ids: {[c['args'].get('page_id') for c in setup_page_calls]}",
        ),
    ]


register_case(
    EvalCase(
        id="builder/creates-new-page-not-modifies-existing",
        dataset="kuma-builder",
        prompt=PROMPT_CREATE_LANDING_PAGE_WITH_EXISTING.format(
            builder_name="Back to Local"
        ),
        scenario="builder-creates-new-page-not-modifies-existing",
        checks=_check_creates_new_page_not_modifies_existing,
        mode=AgentMode.APPLICATION,
        max_iters=25,
    )
)

# ---------------------------------------------------------------------------
# Data-backed app: asks where the projects come from when no table holds them
# ---------------------------------------------------------------------------


@register_scenario("builder-projects-table-missing")
def _projects_table_missing_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(
        user=user, workspace=workspace, name="Finance"
    )
    table = fx.create_database_table(user=user, database=database, name="Invoices")
    fx.create_text_field(table=table, name="Invoice Number", primary=True)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="My App"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
    )


def _check_builds_projects_app_without_asking(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    pages = Page.objects.filter(builder__workspace=scenario.workspace, shared=False)

    return [
        CheckResult(
            "created the scaffolding it needed",
            tool_called(output, "create_tables") >= 1,
        ),
        CheckResult(
            "built the app pages",
            tool_called(output, "create_pages") + tool_called(output, "setup_page")
            >= 1,
        ),
        CheckResult(
            "page exists in DB",
            pages.exists(),
            hint=f"pages: {list(pages.values_list('name', flat=True))}",
        ),
        CheckResult(
            "created at least one element",
            Element.objects.filter(
                page__builder__workspace=scenario.workspace
            ).exists(),
        ),
        CheckResult(
            "did NOT call ask_user",
            tool_called(output, "ask_user") == 0,
            hint=f"tools called: {output.tool_calls}",
        ),
    ]


def _check_asks_when_implied_table_missing(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    pages = Page.objects.filter(builder__workspace=scenario.workspace, shared=False)

    return [
        CheckResult(
            "looked the table up first",
            tool_called(output, "list_tables") >= 1,
        ),
        CheckResult(
            "did NOT invent a Projects table",
            tool_called(output, "create_tables") == 0,
        ),
        CheckResult(
            "did NOT build the app pages",
            tool_called(output, "create_pages") + tool_called(output, "setup_page")
            == 0,
        ),
        CheckResult(
            "no page created in DB",
            not pages.exists(),
            hint=f"pages: {list(pages.values_list('name', flat=True))}",
        ),
        CheckResult(
            "asked the user about the missing records",
            _asked_user(output),
            hint=f"tools called: {output.tool_calls}",
        ),
        CheckResult(
            "offers to create a table with sample data",
            "sample" in output.answer.casefold(),
            hint=f"answer: {output.answer[:300]}",
        ),
    ]


register_case(
    EvalCase(
        id="builder/asks-when-implied-table-missing",
        dataset="kuma-builder",
        # Showing records needs real data: no matching table means ask, not invent.
        prompt=PROMPT_CREATE_PROJECTS_APP,
        scenario="builder-projects-table-missing",
        checks=_check_asks_when_implied_table_missing,
        mode=AgentMode.APPLICATION,
        max_iters=15,
    )
)

# ---------------------------------------------------------------------------
# Proactive: creates app when the implied table exists
# ---------------------------------------------------------------------------


@register_scenario("builder-creates-app-when-table-exists")
def _creates_app_when_table_exists_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(
        user=user, workspace=workspace, name="Work"
    )
    projects_table = fx.create_database_table(
        user=user, database=database, name="Projects"
    )
    fx.create_text_field(table=projects_table, name="Name", primary=True)
    fx.create_text_field(table=projects_table, name="Status")
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="Project Tracker"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={
            "builder": builder,
            "projects_table": projects_table,
            "initial_builder_ids": list(
                Builder.objects.filter(workspace=workspace).values_list("id", flat=True)
            ),
        },
    )


def _project_card_values(repeat, source, table) -> tuple[bool, str]:
    fields = {
        field.name: field
        for field in table.field_set.filter(name__in=["Name", "Status"])
    }
    if set(fields) != {"Name", "Status"}:
        return False, "Projects must have Name and Status fields."
    records = [
        {
            "id": 101,
            fields["Name"].db_column: "First project",
            fields["Status"].db_column: "Open",
        },
        {
            "id": 202,
            fields["Name"].db_column: "Second project",
            fields["Status"].db_column: "Closed",
        },
    ]
    # Read graph relationships and model values fresh, independently of caches
    # populated while the agent was mutating the page.
    with local_cache.context():
        if any(
            parent.content_type.model == "repeatelement"
            for parent in repeat.get_parent_points()
        ):
            return False, "Project cards must not repeat inside another repeat."
        descendant_ids = [
            element.id
            for element in repeat.page.get_graph().get_descendants(repeat)
            if not any(
                parent.id != repeat.id and parent.content_type.model == "repeatelement"
                for parent in element.get_parent_points()
            )
        ]
    elements = [
        element.specific
        for element in Element.objects.filter(
            id__in=descendant_ids,
            content_type__model__in=["headingelement", "textelement"],
        )
    ]
    rendered_records = []
    for current in records:
        values = {"current_record": current, "data_source": {str(source.id): records}}
        rendered_records.append(
            [_render_saved_formula(element.value, values) for element in elements]
        )
    for index, rendered in enumerate(rendered_records):
        text = " ".join(value for value in rendered if value is not None).casefold()
        own = records[index]
        other = records[1 - index]
        if any(
            own[field.db_column].casefold() not in text for field in fields.values()
        ) or any(
            other[field.db_column].casefold() in text for field in fields.values()
        ):
            return False, f"Saved card values for two records: {rendered_records}"
    return True, f"Saved card values for two records: {rendered_records}"


def _check_creates_app_when_table_exists(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builder = scenario.refs["builder"]
    table = scenario.refs["projects_table"]
    # The request says "Create an app" without naming a target. Both completing
    # the current empty app and creating a new app in this workspace satisfy it.
    # Existing unrelated apps and apps in other workspaces must not satisfy it.
    unrelated_ids = set(scenario.refs["initial_builder_ids"]) - {builder.id}
    builders = Builder.objects.filter(workspace=scenario.workspace).exclude(
        id__in=unrelated_ids
    )
    pages = Page.objects.filter(builder__in=builders, shared=False)
    sources = []
    for source in DataSource.objects.filter(page__in=pages):
        service = source.service.specific if source.service else None
        if isinstance(service, LocalBaserowListRows) and service.table_id == table.id:
            sources.append(source)
    repeats = Element.objects.filter(
        page__in=pages, content_type__model="repeatelement"
    )
    card_checks = []
    for repeat in repeats:
        specific = repeat.specific
        for source in sources:
            if (
                specific.data_source_id == source.id
                and specific.page_id == source.page_id
            ):
                card_checks.append(_project_card_values(specific, source, table))
    return [
        CheckResult(
            "Projects table reused without a duplicate",
            Table.objects.filter(
                database__workspace=scenario.workspace, name__iexact="Projects"
            ).count()
            == 1,
        ),
        CheckResult("page exists in DB", pages.exists()),
        CheckResult("saved list_rows data source targets Projects", bool(sources)),
        CheckResult("repeat is bound to the Projects data source", bool(card_checks)),
        CheckResult(
            "cards show each project's Name and Status",
            any(passed for passed, _ in card_checks),
            hint="; ".join(hint for _, hint in card_checks)
            or "No matching repeat/card configuration.",
        ),
    ]


register_case(
    EvalCase(
        id="builder/creates-app-when-table-exists",
        dataset="kuma-builder",
        prompt=PROMPT_CREATE_PROJECTS_APP,
        scenario="builder-creates-app-when-table-exists",
        checks=_check_creates_app_when_table_exists,
        mode=AgentMode.APPLICATION,
        max_iters=25,
    )
)

# ---------------------------------------------------------------------------
# User source: brand-new users table
# ---------------------------------------------------------------------------


@register_scenario("builder-setup-user-source-new-table")
def _setup_user_source_new_table_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="My App"
    )
    fx.create_database_application(user=user, workspace=workspace, name="My DB")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={"builder": builder},
    )


def _check_setup_user_source_new_table(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builder = scenario.refs["builder"]
    user_sources = UserSourceHandler().get_user_sources(builder)
    us = user_sources[0] if user_sources else None
    roles = us.get_type().get_roles(us) if us is not None else []

    return [
        CheckResult(
            "called setup_user_source", tool_called(output, "setup_user_source") >= 1
        ),
        CheckResult(
            "user source created",
            len(user_sources) >= 1,
            hint=f"found {len(user_sources)} user sources",
        ),
        CheckResult(
            "has Admin role",
            us is not None and "Admin" in roles,
            hint="no user source created" if us is None else f"roles: {roles}",
        ),
    ]


register_case(
    EvalCase(
        id="builder/setup-user-source-new-table",
        dataset="kuma-builder",
        # database_name is unused by the template — withheld from the LLM.
        prompt=PROMPT_NEW_TABLE.format(builder_name="My App", database_name="My DB"),
        scenario="builder-setup-user-source-new-table",
        checks=_check_setup_user_source_new_table,
        mode=AgentMode.APPLICATION,
        max_iters=15,
    )
)

# ---------------------------------------------------------------------------
# User source: existing table
# ---------------------------------------------------------------------------


@register_scenario("builder-setup-user-source-existing-table")
def _setup_user_source_existing_table_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="My App"
    )
    database = fx.create_database_application(
        user=user, workspace=workspace, name="My DB"
    )
    table = fx.create_database_table(database=database, name="Members", user=user)
    fx.create_text_field(table=table, name="Name", primary=True)
    fx.create_email_field(table=table, name="Email")
    fx.create_password_field(table=table, name="Password")
    fx.create_single_select_field(table=table, name="Role")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={"builder": builder, "table": table},
    )


def _check_setup_user_source_existing_table(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builder = scenario.refs["builder"]
    table = scenario.refs["table"]
    user_sources = UserSourceHandler().get_user_sources(builder)
    us = user_sources[0] if user_sources else None

    return [
        CheckResult(
            "called setup_user_source", tool_called(output, "setup_user_source") >= 1
        ),
        CheckResult(
            "user source created",
            len(user_sources) >= 1,
            hint=f"found {len(user_sources)} user sources",
        ),
        CheckResult(
            "uses correct table",
            us is not None and us.specific.table_id == table.id,
            hint=(
                "no user source created"
                if us is None
                else f"expected table {table.id}, got {us.specific.table_id}"
            ),
        ),
    ]


register_case(
    EvalCase(
        id="builder/setup-user-source-existing-table",
        dataset="kuma-builder",
        # table_id/database_name are unused by the template — withheld from the LLM.
        prompt=PROMPT_EXISTING_TABLE.format(
            builder_name="My App",
            table_name="Members",
            table_id=0,
            database_name="My DB",
        ),
        scenario="builder-setup-user-source-existing-table",
        checks=_check_setup_user_source_existing_table,
        mode=AgentMode.APPLICATION,
        max_iters=15,
    )
)

# ---------------------------------------------------------------------------
# Moves an element out of a column to the bottom of the page
# ---------------------------------------------------------------------------

PROMPT_MOVE_OUT_OF_COLUMN = (
    "In builder '{builder_name}', on the page 'Home', move the heading "
    "'Inside the column' out of the column so that it becomes the last element "
    "at the bottom of the page."
)


@register_scenario("builder-moves-element-out-of-column")
def _moves_element_out_of_column_scenario(fx: Fixtures) -> EvalScenario:
    # Regression for BASEROW-SAAS-BACKEND-16Z: a root-level move that kept the
    # column slot used to write the element under a `next["0"]` output that
    # nothing renders. The move tool now refuses a slot without a parent.
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="Layout Lab"
    )
    page = fx.create_builder_page(builder=builder, name="Home", path="/")
    column = fx.create_builder_column_element(page=page, column_amount=2)
    inside = fx.create_builder_heading_element(
        page=page,
        value="'Inside the column'",
        reference_element=column,
        position=GraphPointPosition.CHILD,
        place_in_container="0",
    )
    fx.create_builder_text_element(page=page, value="'Text below the column.'")
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={"page": page, "column": column, "inside": inside},
    )


def _check_moves_element_out_of_column(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    page = scenario.refs["page"]
    column = scenario.refs["column"]
    inside = scenario.refs["inside"]
    page.refresh_from_db(fields=["graph"])
    graph_handler = page.get_graph()
    stray_outputs = graph_handler.find_non_default_next_edge_pairs(page.graph)
    last_root_element, _, _ = graph_handler.get_last_position()
    element = Element.objects.filter(id=inside.id).first()

    return [
        CheckResult("called move_elements", tool_called(output, "move_elements") >= 1),
        CheckResult(
            "heading still exists (moved, not recreated)",
            element is not None,
            hint=f"element {inside.id} no longer exists",
        ),
        CheckResult(
            "heading is at the root level",
            element is not None and element.parent_element_id is None,
            hint=f"parent: {element.parent_element_id if element else None}",
        ),
        CheckResult(
            "heading is the last root element",
            last_root_element is not None and last_root_element.id == inside.id,
            hint=f"last root element: {last_root_element}",
        ),
        CheckResult(
            "column still exists", Element.objects.filter(id=column.id).exists()
        ),
        CheckResult(
            "page graph uses only the default next output",
            not stray_outputs,
            hint=f"stray outputs: {sorted(stray_outputs)}",
        ),
    ]


register_case(
    EvalCase(
        id="builder/moves-element-out-of-column",
        dataset="kuma-builder",
        prompt=PROMPT_MOVE_OUT_OF_COLUMN.format(builder_name="Layout Lab"),
        scenario="builder-moves-element-out-of-column",
        checks=_check_moves_element_out_of_column,
        mode=AgentMode.APPLICATION,
        max_iters=15,
    )
)


# ---------------------------------------------------------------------------
# Intent: missing data or an unclear goal asks once; examples and demos build
# ---------------------------------------------------------------------------

PROMPT_CUSTOMERS_PAGE = (
    "In builder 'My App', create a page listing our Customers with their "
    "name and email."
)

PROMPT_EXAMPLE_PROJECTS_APP = (
    "Create a simple example app showing projects in a list with cards "
    "showing project name and status."
)

PROMPT_DEMO_PAGE = (
    "In builder 'My App', add a quick demo page at '/demo' with a heading "
    "saying 'Demo' and a sign-up button."
)

PROMPT_TEAM_APP = "Create an app for my team."


def _check_asks_when_named_table_missing(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builder = scenario.refs["builder"]

    return [
        CheckResult(
            "looked the table up first",
            tool_called(output, "list_tables") >= 1,
        ),
        CheckResult(
            "did NOT invent a Customers table",
            tool_called(output, "create_tables") == 0,
        ),
        CheckResult(
            "did NOT build the page",
            tool_called(output, "create_pages") + tool_called(output, "setup_page")
            == 0,
        ),
        CheckResult(
            "no page created in DB",
            not Page.objects.filter(builder=builder, shared=False).exists(),
        ),
        CheckResult(
            "asked the user about the missing table",
            _asked_user(output),
            hint=f"tools called: {output.tool_calls}",
        ),
    ]


def _check_builds_demo_page_without_asking(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builder = scenario.refs["builder"]
    pages = Page.objects.filter(builder=builder, shared=False)
    elements = Element.objects.filter(page__in=pages)

    return [
        CheckResult(
            "built the page",
            tool_called(output, "create_pages") + tool_called(output, "setup_page")
            >= 1,
        ),
        CheckResult(
            "page exists at /demo",
            pages.filter(path="/demo").exists(),
            hint=f"paths: {list(pages.values_list('path', flat=True))}",
        ),
        CheckResult(
            "created at least two elements (heading and button)",
            elements.count() >= 2,
            hint=f"elements: {elements.count()}",
        ),
        CheckResult(
            "did NOT ask before building",
            tool_called(output, "ask_user") == 0,
            hint=f"tools called: {output.tool_calls}",
        ),
    ]


@register_scenario("builder-asks-when-named-table-missing")
def _asks_when_named_table_missing_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    database = fx.create_database_application(
        user=user, workspace=workspace, name="Ops"
    )
    table = fx.create_database_table(user=user, database=database, name="Suppliers")
    fx.create_text_field(table=table, name="Supplier", primary=True)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="My App"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={"builder": builder},
    )


@register_scenario("builder-blank-app")
def _blank_app_scenario(fx: Fixtures) -> EvalScenario:
    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="My App"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={"builder": builder},
    )


register_case(
    EvalCase(
        id="builder/asks-when-named-table-missing",
        dataset="kuma-builder",
        prompt=PROMPT_CUSTOMERS_PAGE,
        scenario="builder-asks-when-named-table-missing",
        checks=_check_asks_when_named_table_missing,
        mode=AgentMode.APPLICATION,
        max_iters=15,
    )
)


register_case(
    EvalCase(
        id="builder/builds-example-app-without-asking",
        dataset="kuma-builder",
        prompt=PROMPT_EXAMPLE_PROJECTS_APP,
        # Same state as asks-when-implied-table-missing: an example authorizes samples.
        scenario="builder-projects-table-missing",
        checks=_check_builds_projects_app_without_asking,
        mode=AgentMode.APPLICATION,
        max_iters=25,
    )
)


register_case(
    EvalCase(
        id="builder/builds-demo-page-without-asking",
        dataset="kuma-builder",
        prompt=PROMPT_DEMO_PAGE,
        scenario="builder-blank-app",
        checks=_check_builds_demo_page_without_asking,
        mode=AgentMode.APPLICATION,
        max_iters=25,
    )
)


def _check_asks_once_when_goal_unclear(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    pages = Page.objects.filter(builder__workspace=scenario.workspace, shared=False)
    build_calls = (
        tool_called(output, "create_tables")
        + tool_called(output, "create_pages")
        + tool_called(output, "setup_page")
        + tool_called(output, "create_builders")
    )

    return [
        CheckResult(
            "asked exactly one question",
            tool_called(output, "ask_user") <= 1 and _asked_user(output),
            hint=f"tools called: {output.tool_calls}",
        ),
        CheckResult(
            "did NOT build anything",
            build_calls == 0,
            hint=f"tools called: {output.tool_calls}",
        ),
        CheckResult(
            "no page created in DB",
            not pages.exists(),
            hint=f"pages: {list(pages.values_list('name', flat=True))}",
        ),
    ]


register_case(
    EvalCase(
        id="builder/asks-once-when-goal-unclear",
        dataset="kuma-builder",
        # Nothing pins what the app is for: one question first, not a guess.
        prompt=PROMPT_TEAM_APP,
        scenario="builder-blank-app",
        checks=_check_asks_once_when_goal_unclear,
        mode=AgentMode.APPLICATION,
        max_iters=15,
    )
)


# ---------------------------------------------------------------------------
# Header menu edits keep the items they don't change
# ---------------------------------------------------------------------------

PROMPT_MENU_ADD_LINK = (
    "In builder '{builder_name}', add a link to the Contact page to the header menu."
)
PROMPT_MENU_RENAME_BUTTON = (
    "In builder '{builder_name}', rename the Help item in the header menu to Support."
)
PROMPT_MENU_REMOVE_SUB_LINK = (
    "In builder '{builder_name}', remove Pricing from the Products dropdown in the "
    "header menu."
)
PROMPT_MENU_BUTTON_OPENS_PAGE = (
    "In builder '{builder_name}', make the Help button in the header menu open the "
    "About page."
)
PROMPT_MENU_ADD_PAGES_ONE_BY_ONE = (
    "In builder '{builder_name}', create a Blog page at /blog and a Careers page at "
    "/careers, and add each one to the header menu right after creating it."
)
PROMPT_MENU_REORDER = (
    "In builder '{builder_name}', move Help so it comes right after Home in the "
    "header menu."
)
PROMPT_MENU_REMOVE_DROPDOWN = (
    "In builder '{builder_name}', remove the Products dropdown from the header menu."
)

SITE_MENU_ITEMS = ("Home", "Products", "Pricing", "Features", "Divider", "Help")


@register_scenario("builder-site-header-menu")
def _site_header_menu_scenario(fx: Fixtures) -> EvalScenario:
    """A header menu with a link, a dropdown, a separator and a button."""

    user = fx.create_user()
    workspace = fx.create_workspace(user=user)
    builder = fx.create_builder_application(
        user=user, workspace=workspace, name="Shop Site"
    )
    pages = {
        name: fx.create_builder_page(builder=builder, name=name, path=path)
        for name, path in (
            ("Home", "/"),
            ("Products", "/products"),
            ("Pricing", "/pricing"),
            ("Features", "/features"),
            ("About", "/about"),
            ("Contact", "/contact"),
        )
    }
    header = CreateElementActionType.do(
        user,
        element_type_registry.get("header"),
        builder.shared_page,
        {"share_type": "all"},
    )
    menu = CreateElementActionType.do(
        user,
        element_type_registry.get("menu"),
        builder.shared_page,
        {"reference_element_id": header.id, "position": "child"},
    )
    UpdateElementActionType.do(
        user,
        menu,
        {
            "menu_items": [
                new_menu_link("Home", pages["Home"].id),
                {
                    **new_menu_link("Products", pages["Products"].id),
                    "children": [
                        new_menu_link("Pricing", pages["Pricing"].id),
                        new_menu_link("Features", pages["Features"].id),
                    ],
                },
                {
                    "uid": str(uuid.uuid4()),
                    "type": "separator",
                    "variant": "link",
                    "name": "Divider",
                },
                {
                    "uid": str(uuid.uuid4()),
                    "type": "button",
                    "variant": "button",
                    "name": "Help",
                },
            ]
        },
    )
    items = {item.name: item for item in menu.specific.menu_items.all()}
    help_action = fx.create_notification_workflow_action(
        element=menu, event=f"{items['Help'].uid}_click"
    )
    return EvalScenario(
        user=user,
        workspace=workspace,
        ui_context=build_builder_ui_context(user, workspace, builder),
        refs={"builder": builder, "pages": pages, "menu": menu.specific},
        pre_state={
            "uids": {name: str(item.uid) for name, item in items.items()},
            "types": {name: item.type for name, item in items.items()},
            "help_action_id": help_action.id,
        },
    )


def _site_menu_items(scenario: EvalScenario) -> dict[str, MenuItemElement]:
    menu = scenario.refs["menu"]
    if not MenuElement.objects.filter(id=menu.id, trashed=False).exists():
        return {}
    return {
        str(item.uid): item
        for item in menu.menu_items.select_related("parent_menu_item").order_by(
            "menu_item_order"
        )
    }


def _describe_site_menu(items: dict[str, MenuItemElement]) -> str:
    return str(
        [
            (item.name, item.type, item.parent_menu_item and item.parent_menu_item.name)
            for item in items.values()
        ]
    )


def _site_menu_keeps(
    scenario: EvalScenario, items: dict[str, MenuItemElement], names: tuple[str, ...]
) -> CheckResult:
    uids = scenario.pre_state["uids"]
    types = scenario.pre_state["types"]
    changed = [
        name
        for name in names
        if uids[name] not in items or items[uids[name]].type != types[name]
    ]
    return CheckResult(
        f"kept {', '.join(names)} with their uids and types",
        not changed,
        hint=f"lost or retyped: {changed}; menu: {_describe_site_menu(items)}",
    )


def _site_menu_help_action_kept(scenario: EvalScenario) -> CheckResult:
    return CheckResult(
        "Help keeps its click action",
        BuilderWorkflowAction.objects.filter(
            id=scenario.pre_state["help_action_id"]
        ).exists(),
    )


def _products_sub_links(
    scenario: EvalScenario, items: dict[str, MenuItemElement]
) -> list[str]:
    products_uid = scenario.pre_state["uids"]["Products"]
    return [
        item.name
        for item in items.values()
        if item.parent_menu_item and str(item.parent_menu_item.uid) == products_uid
    ]


def _top_level_names(items: dict[str, MenuItemElement]) -> list[str]:
    return [item.name for item in items.values() if item.parent_menu_item_id is None]


def _top_level_links_to(
    items: dict[str, MenuItemElement], page: Page | None
) -> list[MenuItemElement]:
    return [
        item
        for item in items.values()
        if page is not None
        and item.parent_menu_item_id is None
        and item.type == "link"
        and item.navigation_type == "page"
        and item.navigate_to_page_id == page.id
    ]


def _check_menu_adds_link_keeps_button(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    items = _site_menu_items(scenario)
    contact_links = _top_level_links_to(items, scenario.refs["pages"]["Contact"])
    return [
        _site_menu_keeps(scenario, items, SITE_MENU_ITEMS),
        _site_menu_help_action_kept(scenario),
        CheckResult(
            "Pricing and Features still under Products",
            _products_sub_links(scenario, items) == ["Pricing", "Features"],
            hint=f"menu: {_describe_site_menu(items)}",
        ),
        CheckResult(
            "added one top-level link to Contact",
            len(contact_links) == 1,
            hint=f"menu: {_describe_site_menu(items)}",
        ),
        CheckResult(
            "added nothing else",
            len(items) == len(SITE_MENU_ITEMS) + 1,
            hint=f"menu: {_describe_site_menu(items)}",
        ),
    ]


def _check_menu_renames_button(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    items = _site_menu_items(scenario)
    help_item = items.get(scenario.pre_state["uids"]["Help"])
    return [
        _site_menu_keeps(scenario, items, SITE_MENU_ITEMS),
        _site_menu_help_action_kept(scenario),
        CheckResult(
            "Help renamed to Support",
            help_item is not None and help_item.name == "Support",
            hint=f"menu: {_describe_site_menu(items)}",
        ),
    ]


def _check_menu_removes_sub_link(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    items = _site_menu_items(scenario)
    return [
        _site_menu_keeps(
            scenario, items, ("Home", "Products", "Features", "Divider", "Help")
        ),
        _site_menu_help_action_kept(scenario),
        CheckResult(
            "Pricing removed",
            all(item.name != "Pricing" for item in items.values()),
            hint=f"menu: {_describe_site_menu(items)}",
        ),
        CheckResult(
            "Features still under Products",
            _products_sub_links(scenario, items) == ["Features"],
            hint=f"menu: {_describe_site_menu(items)}",
        ),
    ]


def _check_menu_button_opens_page(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    items = _site_menu_items(scenario)
    help_click = f"{scenario.pre_state['uids']['Help']}_click"
    actions = [
        action.specific
        for action in BuilderWorkflowAction.objects.filter(
            element_id=scenario.refs["menu"].id, event=help_click
        )
    ]
    return [
        _site_menu_keeps(scenario, items, SITE_MENU_ITEMS),
        _site_menu_help_action_kept(scenario),
        CheckResult(
            "Help's click opens the About page",
            any(
                isinstance(action, OpenPageWorkflowAction)
                and _navigates_to_path(action, scenario.refs["builder"], "/about")
                for action in actions
            ),
            hint=f"actions on {help_click}: {[type(a).__name__ for a in actions]}",
        ),
    ]


def _check_menu_adds_pages_one_by_one(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    builder = scenario.refs["builder"]
    items = _site_menu_items(scenario)
    new_pages = {
        path: Page.objects.filter(builder=builder, path=path).first()
        for path in ("/blog", "/careers")
    }
    top_level_keys = [name_key(name) for name in _top_level_names(items)]
    return [
        CheckResult(
            "created the Blog and Careers pages",
            all(new_pages.values()),
            hint=f"pages: {list(Page.objects.filter(builder=builder).values_list('path', flat=True))}",
        ),
        _site_menu_keeps(scenario, items, SITE_MENU_ITEMS),
        _site_menu_help_action_kept(scenario),
        CheckResult(
            "one top-level link to each new page",
            all(
                len(_top_level_links_to(items, page)) == 1
                for page in new_pages.values()
            ),
            hint=f"menu: {_describe_site_menu(items)}",
        ),
        CheckResult(
            "no duplicate top-level items",
            len(top_level_keys) == len(set(top_level_keys)),
            hint=f"menu: {_describe_site_menu(items)}",
        ),
    ]


def _check_menu_reorders_items(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    items = _site_menu_items(scenario)
    return [
        _site_menu_keeps(scenario, items, SITE_MENU_ITEMS),
        _site_menu_help_action_kept(scenario),
        CheckResult(
            "Help moved right after Home",
            _top_level_names(items) == ["Home", "Help", "Products", "Divider"],
            hint=f"top-level order: {_top_level_names(items)}",
        ),
        CheckResult(
            "Pricing and Features still under Products",
            _products_sub_links(scenario, items) == ["Pricing", "Features"],
            hint=f"menu: {_describe_site_menu(items)}",
        ),
    ]


def _check_menu_removes_dropdown(
    case: EvalCase, scenario: EvalScenario, output: EvalRunOutput
) -> list[CheckResult]:
    items = _site_menu_items(scenario)
    names = {item.name for item in items.values()}
    kept = ("Home", "Divider", "Help")
    return [
        _site_menu_keeps(scenario, items, kept),
        _site_menu_help_action_kept(scenario),
        CheckResult(
            "removed Products with Pricing and Features",
            names.isdisjoint({"Products", "Pricing", "Features"}),
            hint=f"menu: {_describe_site_menu(items)}",
        ),
        CheckResult(
            "removed nothing else, added nothing and kept the order",
            len(items) == len(kept) and _top_level_names(items) == list(kept),
            hint=f"top-level order: {_top_level_names(items)}",
        ),
    ]


register_case(
    EvalCase(
        id="builder/menu-adds-link-keeps-button",
        dataset="kuma-builder",
        prompt=PROMPT_MENU_ADD_LINK.format(builder_name="Shop Site"),
        scenario="builder-site-header-menu",
        checks=_check_menu_adds_link_keeps_button,
        mode=AgentMode.APPLICATION,
        max_iters=25,
    )
)


register_case(
    EvalCase(
        id="builder/menu-renames-button",
        dataset="kuma-builder",
        prompt=PROMPT_MENU_RENAME_BUTTON.format(builder_name="Shop Site"),
        scenario="builder-site-header-menu",
        checks=_check_menu_renames_button,
        mode=AgentMode.APPLICATION,
        max_iters=25,
    )
)


register_case(
    EvalCase(
        id="builder/menu-removes-sub-link",
        dataset="kuma-builder",
        prompt=PROMPT_MENU_REMOVE_SUB_LINK.format(builder_name="Shop Site"),
        scenario="builder-site-header-menu",
        checks=_check_menu_removes_sub_link,
        mode=AgentMode.APPLICATION,
        max_iters=25,
    )
)


register_case(
    EvalCase(
        id="builder/menu-button-opens-page",
        dataset="kuma-builder",
        prompt=PROMPT_MENU_BUTTON_OPENS_PAGE.format(builder_name="Shop Site"),
        scenario="builder-site-header-menu",
        checks=_check_menu_button_opens_page,
        mode=AgentMode.APPLICATION,
        max_iters=25,
    )
)


register_case(
    EvalCase(
        id="builder/menu-adds-pages-one-by-one",
        dataset="kuma-builder",
        prompt=PROMPT_MENU_ADD_PAGES_ONE_BY_ONE.format(builder_name="Shop Site"),
        scenario="builder-site-header-menu",
        checks=_check_menu_adds_pages_one_by_one,
        mode=AgentMode.APPLICATION,
        max_iters=25,
    )
)


register_case(
    EvalCase(
        id="builder/menu-reorders-items",
        dataset="kuma-builder",
        prompt=PROMPT_MENU_REORDER.format(builder_name="Shop Site"),
        scenario="builder-site-header-menu",
        checks=_check_menu_reorders_items,
        mode=AgentMode.APPLICATION,
        max_iters=25,
    )
)


register_case(
    EvalCase(
        id="builder/menu-removes-dropdown",
        dataset="kuma-builder",
        prompt=PROMPT_MENU_REMOVE_DROPDOWN.format(builder_name="Shop Site"),
        scenario="builder-site-header-menu",
        checks=_check_menu_removes_dropdown,
        mode=AgentMode.APPLICATION,
        max_iters=25,
    )
)
