"""
Evals for builder element formula generation.

Tests the full pipeline:
  $formula: description → get_formulas_to_create() → generate_formulas()
  → update_element_with_formulas()

The LLM is mocked (via mock_generate_formulas) to return known formulas.
We verify:
- The formula is applied to the ORM element
- No exceptions are raised
- Elements are created in the DB
"""

from unittest.mock import patch

import pytest

from baserow.contrib.builder.elements.models import (
    HeadingElement,
    ImageElement,
    LinkElement,
    TextElement,
)
from baserow_enterprise.assistant.tools.builder.types import (
    HeadingElementCreate,
    ImageElementCreate,
    LinkElementCreate,
    TextElementCreate,
)


@pytest.mark.django_db
def test_heading_with_formula_value(
    data_fixture, mock_generate_formulas, create_elements_tool
):
    """A heading with $formula: value should get a generated formula applied."""

    mock_generate_formulas({"value": "get('user.email')"})

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    create_elements = create_elements_tool(user, workspace)
    result = create_elements(
        page_id=page.id,
        elements=[
            HeadingElementCreate(
                ref="h1",
                value="$formula: the user's email",
                level=1,
            )
        ],
    )

    assert len(result["created_elements"]) == 1
    element_id = result["created_elements"][0]["id"]
    heading = HeadingElement.objects.get(id=element_id)
    # Formula should have been applied (not the placeholder empty string)
    assert "user" in heading.value["formula"]


@pytest.mark.django_db
def test_text_with_formula_value(
    data_fixture, mock_generate_formulas, create_elements_tool
):
    """A text element with $formula: should get formula applied."""

    mock_generate_formulas({"value": "get('user.username')"})

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    create_elements = create_elements_tool(user, workspace)
    result = create_elements(
        page_id=page.id,
        elements=[
            TextElementCreate(
                ref="t1",
                value="$formula: the user's username",
            )
        ],
    )

    element_id = result["created_elements"][0]["id"]
    text = TextElement.objects.get(id=element_id)
    assert "user" in text.value["formula"]


@pytest.mark.django_db
def test_link_with_formula_fields(
    data_fixture, mock_generate_formulas, create_elements_tool
):
    """A link with $formula: in both value and navigate_to_url."""

    mock_generate_formulas(
        {
            "value": "'Click here'",
            "navigate_to_url": "concat('https://example.com/', get('user.id'))",
        }
    )

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    create_elements = create_elements_tool(user, workspace)
    result = create_elements(
        page_id=page.id,
        elements=[
            LinkElementCreate(
                ref="link1",
                value="$formula: display text",
                navigation_type="custom",
                navigate_to_url="$formula: URL with user id",
            )
        ],
    )

    element_id = result["created_elements"][0]["id"]
    link = LinkElement.objects.get(id=element_id)
    assert "Click here" in link.value["formula"]
    assert "example.com" in link.navigate_to_url["formula"]


@pytest.mark.django_db
def test_image_with_formula_urls(
    data_fixture, mock_generate_formulas, create_elements_tool
):
    """An image with $formula: urls should get formulas applied."""

    mock_generate_formulas(
        {
            "image_url": "'https://example.com/photo.jpg'",
            "alt_text": "'A photo'",
        }
    )

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    create_elements = create_elements_tool(user, workspace)
    result = create_elements(
        page_id=page.id,
        elements=[
            ImageElementCreate(
                ref="img1",
                image_url="$formula: the product image URL",
                alt_text="$formula: the product name",
            )
        ],
    )

    element_id = result["created_elements"][0]["id"]
    image = ImageElement.objects.get(id=element_id)
    assert "example.com" in image.image_url["formula"]
    assert "photo" in image.alt_text["formula"]


@pytest.mark.django_db
def test_element_without_formula_skipped(
    data_fixture, create_elements_tool
):
    """Static elements (no $formula:) should not trigger formula generation."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    with patch(
        "baserow_enterprise.assistant.tools.shared.formula_utils.udspy.Predict"
    ) as mock_predict:
        create_elements = create_elements_tool(user, workspace)
        create_elements(
            page_id=page.id,
            elements=[
                HeadingElementCreate(
                    ref="h1",
                    value="'Hello World'",
                    level=1,
                )
            ],
        )
        mock_predict.assert_not_called()


@pytest.mark.django_db
def test_formula_generation_failure_does_not_crash(
    data_fixture, create_elements_tool
):
    """If formula generation raises, the element is still created (just no formula)."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    with patch(
        "baserow_enterprise.assistant.tools.shared.formula_utils.udspy.Predict",
        side_effect=ValueError("LLM failed"),
    ):
        create_elements = create_elements_tool(user, workspace)
        result = create_elements(
            page_id=page.id,
            elements=[
                HeadingElementCreate(
                    ref="h1",
                    value="$formula: something dynamic",
                    level=1,
                )
            ],
        )

    # Element should still exist in DB despite formula failure
    element_id = result["created_elements"][0]["id"]
    assert HeadingElement.objects.filter(id=element_id).exists()


@pytest.mark.django_db
def test_formula_with_data_source_context(data_fixture):
    """
    BuilderFormulaContext should load data sources so formulas can reference them.
    This verifies the context is populated; actual formula generation is tested
    by the other tests.
    """

    from baserow_enterprise.assistant.tools.builder.utils import BuilderFormulaContext

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, name="Name")

    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, user=user, table=table,
    )

    ctx = BuilderFormulaContext(page)
    ctx.load_page_context()

    # Data source should be in the context
    ds_key = f"data_source.{data_source.id}"
    assert ds_key in ctx.context, (
        f"Expected '{ds_key}' in context keys: {list(ctx.context.keys())}"
    )


@pytest.mark.django_db
def test_formula_with_form_data_context(
    data_fixture, mock_generate_formulas, create_elements_tool
):
    """Formula referencing form_data should have form elements in context."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(builder=builder)

    # Create a form input element first
    input_el = data_fixture.create_builder_input_text_element(user=user, page=page)

    mock_generate_formulas(
        {"value": f"get('form_data.{input_el.id}')"}
    )

    create_elements = create_elements_tool(user, workspace)
    result = create_elements(
        page_id=page.id,
        elements=[
            TextElementCreate(
                ref="t1",
                value="$formula: the value from the form input",
            )
        ],
    )

    element_id = result["created_elements"][0]["id"]
    text = TextElement.objects.get(id=element_id)
    assert "form_data" in text.value["formula"]
