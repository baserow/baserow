import pytest

from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
from baserow_enterprise.assistant.tools.builder.utils import BuilderFormulaContext


def _check_formula(formula: str, context: BuilderFormulaContext) -> str:
    """Validate a formula against the given context."""

    try:
        resolve_formula(
            {"formula": formula, "mode": BASEROW_FORMULA_MODE_ADVANCED},
            formula_runtime_function_registry,
            context,
        )
    except Exception as exc:
        raise ValueError(f"Generated formula is invalid: {str(exc)}")
    return "ok"


@pytest.mark.django_db
def test_load_user_context(data_fixture):
    """Test that user context includes all expected fields."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    ctx = BuilderFormulaContext(page)
    ctx._load_user_context()

    assert ctx.context["user"]["id"] == 1
    assert ctx.context["user"]["email"] == "user@example.com"
    assert ctx.context["user"]["username"] == "user"
    assert ctx.context["user"]["role"] == "member"
    assert ctx.context["user"]["is_authenticated"] is True

    # Validate formulas resolve against user context
    assert _check_formula("get('user.email')", ctx) == "ok"
    assert _check_formula("get('user.id')", ctx) == "ok"
    assert _check_formula("get('user.username')", ctx) == "ok"
    assert _check_formula("get('user.role')", ctx) == "ok"
    assert _check_formula("get('user.is_authenticated')", ctx) == "ok"

    # Metadata includes all fields
    meta = ctx.context_metadata["user"]
    assert "id" in meta
    assert "email" in meta
    assert "username" in meta
    assert "role" in meta
    assert "is_authenticated" in meta


@pytest.mark.django_db
def test_load_page_parameters(data_fixture):
    """Test that page parameters are loaded from path and query params."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(
        builder=builder,
        path="/test/:id",
        path_params=[{"name": "id", "type": "numeric"}],
        query_params=[{"name": "search", "type": "text"}],
    )

    ctx = BuilderFormulaContext(page)
    ctx._load_page_parameters()

    assert "page_parameter" in ctx.context
    assert "id" in ctx.context["page_parameter"]
    assert "search" in ctx.context["page_parameter"]

    assert _check_formula("get('page_parameter.id')", ctx) == "ok"
    assert _check_formula("get('page_parameter.search')", ctx) == "ok"


@pytest.mark.django_db
def test_load_form_data(data_fixture):
    """Test that form elements are loaded into form_data context."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    input_el = data_fixture.create_builder_input_text_element(user=user, page=page)
    choice_el = data_fixture.create_builder_choice_element(user=user, page=page)

    from baserow.contrib.builder.elements.handler import ElementHandler

    elements = ElementHandler().get_elements(page)

    ctx = BuilderFormulaContext(page)
    ctx._load_form_data(elements)

    assert "form_data" in ctx.context
    assert str(input_el.id) in ctx.context["form_data"]
    assert str(choice_el.id) in ctx.context["form_data"]

    # Check data types
    assert ctx.context["form_data"][str(input_el.id)] == "string"
    assert ctx.context["form_data"][str(choice_el.id)] == "string"

    # Check metadata
    meta = ctx.context_metadata["form_data"]
    assert meta[str(input_el.id)]["type"] == "input_text"
    assert meta[str(choice_el.id)]["type"] == "choice"

    # Formula validation
    assert _check_formula(f"get('form_data.{input_el.id}')", ctx) == "ok"
    assert _check_formula(f"get('form_data.{choice_el.id}')", ctx) == "ok"


@pytest.mark.django_db
def test_load_form_data_skips_non_form_elements(data_fixture):
    """Test that non-form elements are not included in form_data."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    # Create a heading (not a form element)
    data_fixture.create_builder_heading_element(user=user, page=page)

    from baserow.contrib.builder.elements.handler import ElementHandler

    elements = ElementHandler().get_elements(page)

    ctx = BuilderFormulaContext(page)
    ctx._load_form_data(elements)

    # No form elements -> no form_data in context
    assert "form_data" not in ctx.context


@pytest.mark.django_db
def test_load_data_source_context_for_list_sources(data_fixture):
    """Test that data_source_context is populated for list data sources."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    ctx = BuilderFormulaContext(page)

    # Simulate a list data source in metadata
    ctx.context_metadata["data_source.42"] = {
        "name": "Customers",
        "returns_list": True,
        "fields": {},
    }
    ctx.context["data_source.42"] = [{"name": "text"}]

    ctx._load_data_source_context()

    assert "data_source_context" in ctx.context
    assert "42" in ctx.context["data_source_context"]
    assert ctx.context["data_source_context"]["42"]["total_count"] == 100

    meta = ctx.context_metadata["data_source_context"]
    assert "42" in meta
    assert meta["42"]["name"] == "Customers"

    # Formula validation
    assert _check_formula("get('data_source_context.42.total_count')", ctx) == "ok"


@pytest.mark.django_db
def test_load_data_source_context_skips_non_list_sources(data_fixture):
    """Test that non-list data sources don't get context metadata."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    ctx = BuilderFormulaContext(page)

    # Simulate a single-row data source
    ctx.context_metadata["data_source.10"] = {
        "name": "CurrentUser",
        "returns_list": False,
        "fields": {},
    }
    ctx.context["data_source.10"] = {"name": "text"}

    ctx._load_data_source_context()

    assert "data_source_context" not in ctx.context


@pytest.mark.django_db
def test_current_record_push_pop(data_fixture):
    """Test push/pop of current_record context for collection elements."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    ctx = BuilderFormulaContext(page)

    # Simulate a list data source
    ctx.context["data_source.5"] = [{"field_name": "text"}]
    ctx.context_metadata["data_source.5"] = {
        "name": "Items",
        "returns_list": True,
        "fields": {"field_name": {"type": "text"}},
    }

    # Push current record
    ctx.push_current_record_context(5)
    assert "current_record" in ctx.context
    assert ctx.context["current_record"] == {"field_name": "text"}
    assert _check_formula("get('current_record.field_name')", ctx) == "ok"

    # Pop current record
    ctx.pop_current_record_context()
    assert "current_record" not in ctx.context


@pytest.mark.django_db
def test_getitem_resolves_all_providers(data_fixture):
    """Test __getitem__ resolves paths for all data providers."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    ctx = BuilderFormulaContext(page)
    ctx._load_user_context()

    # Set up form_data manually
    ctx.context["form_data"] = {"99": "string"}

    # Set up data_source_context manually
    ctx.context["data_source_context"] = {"42": {"total_count": 100}}

    # Set up page_parameter manually
    ctx.context["page_parameter"] = {"id": "example_value"}

    # Test resolution
    assert ctx["user.email"] == "user@example.com"
    assert ctx["user.username"] == "user"
    assert ctx["user.role"] == "member"
    assert ctx["form_data.99"] == "string"
    assert ctx["data_source_context.42.total_count"] == 100
    assert ctx["page_parameter.id"] == "example_value"


@pytest.mark.django_db
def test_getitem_raises_on_invalid_path(data_fixture):
    """Test __getitem__ raises KeyError for invalid paths."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    ctx = BuilderFormulaContext(page)
    ctx._load_user_context()

    with pytest.raises(KeyError):
        ctx["nonexistent.path"]

    with pytest.raises(KeyError):
        ctx["user.nonexistent_field"]


@pytest.mark.django_db
def test_full_load_page_context(data_fixture):
    """Test that load_page_context loads all providers without error."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(
        builder=builder,
        path="/items/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )

    # Create a form element
    data_fixture.create_builder_input_text_element(user=user, page=page)

    ctx = BuilderFormulaContext(page)
    ctx.load_page_context()

    # User context always present
    assert "user" in ctx.context
    assert ctx.context["user"]["username"] == "user"

    # Page parameters loaded
    assert "page_parameter" in ctx.context
    assert "id" in ctx.context["page_parameter"]

    # Form data loaded
    assert "form_data" in ctx.context

    # All user formulas valid
    assert _check_formula("get('user.email')", ctx) == "ok"
    assert _check_formula("get('page_parameter.id')", ctx) == "ok"
