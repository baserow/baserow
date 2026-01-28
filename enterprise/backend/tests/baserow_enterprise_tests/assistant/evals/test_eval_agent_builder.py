"""
Agent-level evals for the builder assistant.

These run the full ReAct loop with real tools and the production system prompt.
They verify:
- No tool errors in the trajectory (via AssistantCallbacks)
- Elements are created in the DB
- Formulas are applied correctly

Run with: pytest -m eval -v

Configuration (via environment variables):
- EVAL_LLM_MODEL: The model to use (default: "openai/gpt-4o")
- OPENAI_API_KEY: Required for OpenAI models
- GROQ_API_KEY: Required for Groq models
"""

import pytest
import udspy

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.elements.models import (
    ButtonElement,
    FormContainerElement,
    HeadingElement,
    InputTextElement,
    RepeatElement,
)
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.models import Page

from .eval_utils import (
    assert_no_tool_errors,
    build_builder_ui_context,
    create_eval_assistant,
)


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_heading_with_user_email(data_fixture):
    """Agent should create a heading showing the user's email without tool errors."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    react, callbacks, lm = create_eval_assistant(user, workspace, max_iters=10)
    ui_context = build_builder_ui_context(user, workspace, builder, page)

    with udspy.settings.context(lm=lm, callbacks=[callbacks]):
        result = react.forward(
            question=(
                "Add a heading that displays the logged-in user's email address."
            ),
            conversation_history=[],
            ui_context=ui_context,
        )

    assert_no_tool_errors(callbacks, result)

    assert list(Builder.objects.values_list("id", flat=True)) == [builder.id], (
        "Agent created an unexpected new builder"
    )

    assert list(Page.objects.filter(shared=False).values_list("id", flat=True)) == [
        page.id
    ], "Agent created an unexpected new page"

    assert HeadingElement.objects.filter(page=page).exists(), (
        "Agent did not create a HeadingElement on the selected page"
    )

    assert HeadingElement.objects.count() == 1, (
        "Agent created more than one HeadingElement"
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_repeat_with_data_source(data_fixture):
    """Agent should create a repeat element with child elements referencing data."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    data_fixture.create_text_field(table=table, name="Email")

    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    react, callbacks, lm = create_eval_assistant(user, workspace, max_iters=15)
    ui_context = build_builder_ui_context(user, workspace, builder, page)

    with udspy.settings.context(lm=lm, callbacks=[callbacks]):
        result = react.forward(
            question=(
                f"Create a repeat element that lists rows from table {table.id}, "
                f"showing the Name and Email fields as headings inside each item."
            ),
            conversation_history=[],
            ui_context=ui_context,
        )

    # Uncomment to debug: print_trajectory(result)
    assert_no_tool_errors(callbacks, result)

    assert list(Builder.objects.values_list("id", flat=True)) == [builder.id], (
        "Agent created an unexpected new builder"
    )

    assert list(Page.objects.filter(shared=False).values_list("id", flat=True)) == [
        page.id
    ], "Agent created an unexpected new page"

    assert RepeatElement.objects.filter(page=page).count() == 1, (
        "Agent should create exactly one RepeatElement on the page"
    )

    repeat = RepeatElement.objects.get(page=page)

    assert DataSource.objects.filter(page=page).count() == 1, (
        "Agent should create exactly one DataSource for the repeat element"
    )

    data_source = DataSource.objects.get(page=page)
    assert repeat.data_source_id == data_source.id, (
        "RepeatElement should be linked to the created DataSource"
    )

    child_headings = HeadingElement.objects.filter(
        page=page, parent_element_id=repeat.id
    )
    assert child_headings.count() == 2, (
        f"Expected 2 child headings (Name, Email), got {child_headings.count()}"
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_form_with_create_row_action(data_fixture):
    """Agent should create a form that submits data to a database table."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Contacts")
    name_field = data_fixture.create_text_field(table=table, name="Name", primary=True)
    email_field = data_fixture.create_text_field(table=table, name="Email")

    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    react, callbacks, lm = create_eval_assistant(user, workspace, max_iters=20)
    ui_context = build_builder_ui_context(user, workspace, builder, page)

    with udspy.settings.context(lm=lm, callbacks=[callbacks]):
        result = react.forward(
            question=(
                f"Create a form with Name and Email input fields and a submit button. "
                f"When submitted, it should create a new row in table {table.name} "
                f"with field {name_field.name} for name and field {email_field.name} for email."
            ),
            conversation_history=[],
            ui_context=ui_context,
        )

    # Uncomment to debug: print_trajectory(result)
    (
        assert_no_tool_errors(callbacks, result),
        result.get("trajectory", "Missing trajectory"),
    )

    assert list(Builder.objects.values_list("id", flat=True)) == [builder.id], (
        "Agent created an unexpected new builder"
    )
    assert list(Page.objects.filter(shared=False).values_list("id", flat=True)) == [
        page.id
    ], "Agent created an unexpected new page"

    assert FormContainerElement.objects.filter(page=page).count() == 1, (
        "Agent should create exactly one FormContainerElement"
    )

    form = FormContainerElement.objects.get(page=page)

    # Verify input elements were created inside the form
    input_elements = InputTextElement.objects.filter(
        page=page, parent_element_id=form.id
    )
    assert input_elements.count() == 2, (
        f"Expected 2 input elements (Name, Email), got {input_elements.count()}"
    )

    assert ButtonElement.objects.count() == 0, (
        f"Agent should not create any other ButtonElements. "
        "The form already has a submit button by default."
    )


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_updates_theme(data_fixture):
    """Agent should call update_theme exactly once when asked to change theme."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    react, callbacks, lm = create_eval_assistant(user, workspace, max_iters=10)
    ui_context = build_builder_ui_context(user, workspace, builder, page)

    with udspy.settings.context(lm=lm, callbacks=[callbacks]):
        result = react.forward(
            question=(
                "Change the primary color of the theme to blue (#0000FF) "
                "and the heading font size to 24px."
            ),
            conversation_history=[],
            ui_context=ui_context,
        )

    # Uncomment to debug: print_trajectory(result)
    assert_no_tool_errors(callbacks, result)

    # Verify update_theme was called exactly once (not multiple times)
    update_theme_calls = callbacks.get_tool_call_count("update_theme")
    assert update_theme_calls == 1, (
        f"Expected update_theme to be called exactly once, got {update_theme_calls} calls"
    )

    # Verify no pages or builders were created
    assert list(Builder.objects.values_list("id", flat=True)) == [builder.id], (
        "Agent created an unexpected new builder"
    )
    assert list(Page.objects.filter(shared=False).values_list("id", flat=True)) == [
        page.id
    ], "Agent created an unexpected new page"


@pytest.mark.eval
@pytest.mark.django_db(transaction=True)
def test_agent_creates_link_element(data_fixture):
    """Agent should create a link element with correct navigation."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)
    target_page = data_fixture.create_builder_page(builder=builder, name="About")

    react, callbacks, lm = create_eval_assistant(user, workspace, max_iters=10)
    ui_context = build_builder_ui_context(user, workspace, builder, page)

    with udspy.settings.context(lm=lm, callbacks=[callbacks]):
        result = react.forward(
            question=(
                f"Add a link that says 'Go to About' and navigates to page {target_page.id}."
            ),
            conversation_history=[],
            ui_context=ui_context,
        )

    # Uncomment to debug: print_trajectory(result)
    assert_no_tool_errors(callbacks, result)

    # Import LinkElement here to avoid circular imports at module level
    from baserow.contrib.builder.elements.models import LinkElement

    # Verify link was created
    links = LinkElement.objects.filter(page=page)
    assert links.count() == 1, f"Expected 1 link element, got {links.count()}"

    link = links.first()
    assert link.navigate_to_page_id == target_page.id, (
        f"Link should navigate to page {target_page.id}, got {link.navigate_to_page_id}"
    )
