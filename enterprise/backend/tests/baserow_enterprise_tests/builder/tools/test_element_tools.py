"""
The shared element tools store the formulas they are given and report the rest,
without a model. The conftest of this folder fails any model call.
"""

import pytest
from pydantic import ValidationError as PydanticValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.builder.elements.exceptions import ElementDoesNotExist
from baserow.contrib.builder.elements.models import Element, LinkElement, TableElement
from baserow.contrib.builder.pages.exceptions import PageDoesNotExist
from baserow.core.exceptions import PermissionException
from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
from baserow.core.tools.errors import ToolInputError
from baserow_enterprise.builder.tools import (
    elements,
    helpers,
)
from baserow_enterprise.builder.tools.formulas import (
    current_record_of,
    formula_problem,
    page_formula_context,
)
from baserow_enterprise.builder.tools.types import (
    CollectionElementCreate,
    DisplayElementCreate,
    ElementEdits,
    ElementItemCreate,
    ElementMove,
    ElementStyleChanges,
    FormElementCreate,
    LayoutElementCreate,
    MenuItemCreate,
    TableColumnAdd,
    TableColumnUpdate,
    TableFieldConfig,
)
from baserow_enterprise.builder.tools.types.menu_items import (
    MenuItemAdd,
    MenuItemUpdate,
)


def heading(ref="h", **kwargs):
    return ElementItemCreate(ref=ref, type="heading", value="Hi", **kwargs)


def saved(element_id):
    return Element.objects.get(id=element_id).specific


@pytest.fixture
def table_field(builder_ctx):
    table = builder_ctx["data_source"].service.specific.table
    return table.field_set.get(name="Name")


@pytest.fixture
def repeat(data_fixture, builder_ctx):
    return data_fixture.create_builder_repeat_element(
        page=builder_ctx["page"], data_source=builder_ctx["data_source"]
    )


# ---------------------------------------------------------------------------
# Refs
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_ref_from_an_earlier_call_fails_the_item(builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    first = elements.create_elements(
        ctx, page.id, [ElementItemCreate(ref="box", type="simple_container")]
    )
    count = Element.objects.count()

    result = elements.create_elements(ctx, page.id, [heading(parent_element="box")])

    assert first["ref_to_id_map"]["box"]
    assert result["created_elements"] == []
    assert result["errors"] == [
        "h: Unknown ref 'box'. Refs only work inside one call; use the element ID."
    ]
    assert Element.objects.count() == count


@pytest.mark.django_db
def test_a_ref_works_inside_one_call(builder_ctx):
    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(ref="box", type="simple_container"),
            heading(parent_element="box"),
        ],
    )

    ids = result["ref_to_id_map"]
    assert saved(ids["h"]).parent_element_id == ids["box"]
    assert "errors" not in result


@pytest.mark.django_db
def test_a_data_source_ref_from_an_earlier_call_fails_the_item(builder_ctx):
    result = elements.create_collection_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [CollectionElementCreate(ref="r", type="repeat", data_source="products")],
    )

    assert result["created_elements"] == []
    assert result["errors"] == [
        "r: Unknown data source ref 'products'. Refs only work inside one call; use "
        "the data source ID from list_data_sources."
    ]


# ---------------------------------------------------------------------------
# Shared page
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_header_lands_on_the_shared_page_and_shows_on_other_pages(
    data_fixture, builder_ctx
):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    other = data_fixture.create_builder_page(builder=builder_ctx["builder"])

    result = elements.create_layout_elements(
        ctx,
        page.id,
        [
            LayoutElementCreate(ref="top", type="header"),
            LayoutElementCreate(
                ref="box", type="simple_container", parent_element="top"
            ),
        ],
    )

    ids = result["ref_to_id_map"]
    assert saved(ids["top"]).page == builder_ctx["builder"].shared_page
    # A child of a shared page element goes to the shared page too.
    assert saved(ids["box"]).page == builder_ctx["builder"].shared_page
    listed = elements.list_elements(ctx, other.id)["elements"]
    assert {ids["top"], ids["box"]} <= {element["id"] for element in listed}


@pytest.mark.django_db
def test_a_header_form_can_not_read_its_own_inputs(data_fixture, builder_ctx):
    ctx = builder_ctx["ctx"]
    created = elements.create_elements(
        ctx,
        builder_ctx["page"].id,
        [
            ElementItemCreate(ref="top", type="header"),
            ElementItemCreate(ref="form", type="form_container", parent_element="top"),
            ElementItemCreate(ref="in", type="input_text", parent_element="form"),
        ],
    )["ref_to_id_map"]

    result = elements.create_elements(
        ctx,
        builder_ctx["page"].id,
        [
            ElementItemCreate(
                ref="echo",
                type="heading",
                parent_element=created["form"],
                value=f"get('form_data.{created['in']}')",
            )
        ],
    )

    entry = result["formula_errors"][0]
    assert entry["element_id"] == result["ref_to_id_map"]["echo"]
    assert "shared page" in entry["error"]


@pytest.mark.django_db
def test_a_header_can_not_read_what_only_one_page_has(data_fixture, builder_ctx):
    page = data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        name="Item",
        path="/item/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )

    result = elements.create_elements(
        builder_ctx["ctx"],
        page.id,
        [
            ElementItemCreate(ref="top", type="header"),
            ElementItemCreate(
                ref="h",
                type="heading",
                parent_element="top",
                value="get('page_parameter.id')",
            ),
        ],
    )

    entry = result["formula_errors"][0]
    assert entry["element_id"] == result["ref_to_id_map"]["h"]
    assert "page parameter" in entry["error"]


@pytest.mark.django_db
def test_a_normal_page_can_not_read_a_header_form(builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    created = elements.create_elements(
        ctx,
        page.id,
        [
            ElementItemCreate(ref="top", type="header"),
            ElementItemCreate(ref="form", type="form_container", parent_element="top"),
            ElementItemCreate(ref="in", type="input_text", parent_element="form"),
        ],
    )["ref_to_id_map"]

    result = elements.create_elements(
        ctx,
        page.id,
        [
            ElementItemCreate(
                ref="echo", type="heading", value=f"get('form_data.{created['in']}')"
            )
        ],
    )

    assert "form element" in result["formula_errors"][0]["error"]


# ---------------------------------------------------------------------------
# Formulas
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_description_inside_a_repeat_is_reported(builder_ctx, repeat):
    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(
                ref="child",
                type="heading",
                parent_element=repeat.id,
                value="$formula: the name of the product",
            )
        ],
    )

    child = result["ref_to_id_map"]["child"]
    assert saved(child).value["formula"] == "''"
    assert result["formula_errors"] == [
        {
            "element_id": child,
            "field": "value",
            "formula": "$formula: the name of the product",
            "error": (
                "'value' needs a formula, not a description. Write it in Baserow "
                "formula syntax, like get('page_parameter.id')."
            ),
        }
    ]


@pytest.mark.django_db
def test_an_explicit_formula_inside_a_repeat_is_stored(builder_ctx, repeat):
    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(
                ref="child",
                type="heading",
                parent_element=repeat.id,
                value="get('current_record.id')",
            )
        ],
    )

    value = saved(result["ref_to_id_map"]["child"]).value
    assert value["formula"] == "get('current_record.id')"
    assert value["mode"] == BASEROW_FORMULA_MODE_ADVANCED
    assert "formula_errors" not in result


@pytest.mark.django_db
def test_current_record_is_refused_outside_a_collection(builder_ctx):
    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [ElementItemCreate(ref="h", type="heading", value="get('current_record.id')")],
    )

    assert "inside a repeat or a table" in result["formula_errors"][0]["error"]


@pytest.mark.django_db
def test_current_record_in_a_repeat_without_a_data_source_says_so(
    data_fixture, builder_ctx
):
    repeat = data_fixture.create_builder_repeat_element(page=builder_ctx["page"])
    repeat.data_source = None
    repeat.save()

    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(
                ref="h",
                type="heading",
                parent_element=repeat.id,
                value="get('current_record.id')",
            )
        ],
    )

    assert "has no data source" in result["formula_errors"][0]["error"]


@pytest.mark.django_db
def test_a_row_field_named_by_its_name_is_listed_in_formula_errors(
    data_fixture, builder_ctx
):
    page = builder_ctx["page"]
    repeat = data_fixture.create_builder_repeat_element(
        page=page, data_source=builder_ctx["data_source"]
    )
    field = builder_ctx["data_source"].service.specific.table.field_set.first()

    result = elements.create_elements(
        builder_ctx["ctx"],
        page.id,
        [
            ElementItemCreate(
                ref="h",
                type="heading",
                parent_element=repeat.id,
                value=f"get('current_record.{field.name}')",
            )
        ],
    )

    assert result["formula_errors"][0]["field"] == "value"
    assert f"field_{field.id} ({field.name})" in result["formula_errors"][0]["error"]


@pytest.mark.django_db
def test_a_repeat_bound_through_a_schema_property_offers_current_record(
    data_fixture, builder_ctx
):
    page = builder_ctx["page"]
    outer = data_fixture.create_builder_repeat_element(
        page=page, data_source=builder_ctx["data_source"]
    )
    nested = data_fixture.create_builder_repeat_element(
        page=page, parent_element=outer, schema_property="field_1"
    )
    nested.data_source = None
    nested.save()

    result = elements.create_elements(
        builder_ctx["ctx"],
        page.id,
        [
            ElementItemCreate(
                ref="h",
                type="heading",
                parent_element=nested.id,
                value="get('current_record.value')",
            )
        ],
    )

    assert "formula_errors" not in result

    context = page_formula_context(page)
    with current_record_of(context, "element", nested):
        assert formula_problem("value", "get('current_record.id')", context) is None
    assert context._current_record_stack == []


@pytest.mark.django_db
def test_table_columns_store_formulas_and_report_descriptions(builder_ctx):
    data_source = builder_ctx["data_source"]
    result = elements.create_collection_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            CollectionElementCreate(
                ref="t",
                type="table",
                data_source=data_source.id,
                fields=[
                    TableFieldConfig(name="Id", value="get('current_record.id')"),
                    TableFieldConfig(name="Described", value="$formula: the price"),
                    TableFieldConfig(
                        name="Go", type="button", label="$formula: the action"
                    ),
                ],
            )
        ],
    )

    table = TableElement.objects.get(id=result["ref_to_id_map"]["t"])
    columns = list(table.fields.order_by("order"))
    assert columns[0].config["value"]["formula"] == "get('current_record.id')"
    assert columns[1].config["value"]["formula"] == "''"
    assert [
        (entry["element_id"], entry["field"], entry["formula"])
        for entry in result["formula_errors"]
    ] == [
        (table.id, "fields.1.value", "$formula: the price"),
        (table.id, "fields.2.label", "$formula: the action"),
    ]


@pytest.mark.django_db
def test_a_formula_error_reports_the_value_the_client_sent(builder_ctx):
    result = elements.create_display_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            DisplayElementCreate(
                ref="h", type="heading", value="New deal: $formula: the deal name"
            )
        ],
    )

    [entry] = result["formula_errors"]
    assert entry["formula"] == "New deal: $formula: the deal name"


@pytest.mark.django_db
def test_an_empty_table_column_reports_an_empty_formula(builder_ctx):
    result = elements.create_collection_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            CollectionElementCreate(
                ref="t",
                type="table",
                data_source=builder_ctx["data_source"].id,
                fields=[TableFieldConfig(name="Not a field")],
            )
        ],
    )

    [entry] = result["formula_errors"]
    assert entry["field"] == "fields.0.value"
    assert entry["formula"] == ""


@pytest.mark.django_db
def test_a_column_named_like_a_field_keeps_its_own_formula(builder_ctx):
    result = elements.create_collection_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            CollectionElementCreate(
                ref="t",
                type="table",
                data_source=builder_ctx["data_source"].id,
                fields=[
                    TableFieldConfig(name="Name", value="get('current_record.id')")
                ],
            ),
            CollectionElementCreate(
                ref="t2",
                type="table",
                data_source=builder_ctx["data_source"].id,
                fields=[TableFieldConfig(name="Name", value="$formula: upper name")],
            ),
        ],
    )

    explicit = TableElement.objects.get(id=result["ref_to_id_map"]["t"])
    assert (
        explicit.fields.get().config["value"]["formula"] == "get('current_record.id')"
    )
    described = TableElement.objects.get(id=result["ref_to_id_map"]["t2"])
    assert described.fields.get().config["value"]["formula"] == "''"
    assert [(e["element_id"], e["field"]) for e in result["formula_errors"]] == [
        (described.id, "fields.0.value")
    ]


@pytest.mark.django_db
def test_a_column_named_like_a_field_without_a_value_shows_that_field(
    builder_ctx, table_field
):
    result = elements.create_collection_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            CollectionElementCreate(
                ref="t",
                type="table",
                data_source=builder_ctx["data_source"].id,
                fields=[TableFieldConfig(name="Name")],
            )
        ],
    )

    table = TableElement.objects.get(id=result["ref_to_id_map"]["t"])
    assert f"field_{table_field.id}" in table.fields.get().config["value"]["formula"]
    assert "formula_errors" not in result


@pytest.mark.django_db
def test_a_table_without_columns_says_so(builder_ctx):
    result = elements.create_collection_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            CollectionElementCreate(
                ref="t", type="table", data_source=builder_ctx["data_source"].id
            )
        ],
    )

    assert result["created_elements"] == []
    assert "needs fields" in result["errors"][0]


@pytest.mark.django_db
def test_form_fields_store_formulas_and_report_descriptions(data_fixture, builder_ctx):
    page = data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        name="Item",
        path="/item/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )
    result = elements.create_form_elements(
        builder_ctx["ctx"],
        page.id,
        [
            FormElementCreate(ref="form", type="form_container"),
            FormElementCreate(
                ref="a",
                type="input_text",
                parent_element="form",
                label="A",
                default_value="get('page_parameter.id')",
            ),
            FormElementCreate(
                ref="b",
                type="input_text",
                parent_element="form",
                label="B",
                default_value="$formula: the id",
            ),
        ],
    )

    ids = result["ref_to_id_map"]
    assert saved(ids["a"]).default_value["formula"] == "get('page_parameter.id')"
    assert saved(ids["b"]).default_value["formula"] == "''"
    assert [(e["element_id"], e["field"]) for e in result["formula_errors"]] == [
        (ids["b"], "default_value")
    ]


# ---------------------------------------------------------------------------
# Batches
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_one_bad_element_in_a_batch_keeps_the_rest(builder_ctx):
    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            heading("first"),
            heading("bad", parent_element=999999),
            heading("last"),
        ],
    )

    assert [item["ref"] for item in result["created_elements"]] == ["first", "last"]
    assert result["errors"][0].startswith("bad: Parent element with ID 999999")
    assert set(result["ref_to_id_map"]) == {"first", "last"}
    assert saved(result["ref_to_id_map"]["last"])


@pytest.mark.django_db
def test_navigation_on_a_type_without_it_is_a_message_not_an_internal_error(
    builder_ctx,
):
    result = elements.create_display_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            DisplayElementCreate(
                ref="h", type="heading", value="Hi", navigate_to_url="https://a.b"
            )
        ],
    )

    assert result["errors"][0].startswith(
        "h: Unsupported properties for heading: navigate_to_url."
    )


@pytest.mark.django_db
def test_a_denied_create_stops_the_call_and_keeps_nothing(builder_ctx, monkeypatch):
    count = Element.objects.count()
    original = helpers.create_element

    def deny_the_second(user, page, element_create, *args, **kwargs):
        if element_create.ref == "second":
            raise PermissionException()
        return original(user, page, element_create, *args, **kwargs)

    monkeypatch.setattr(helpers, "create_element", deny_the_second)

    with pytest.raises(PermissionException):
        elements.create_elements(
            builder_ctx["ctx"],
            builder_ctx["page"].id,
            [heading("first"), heading("second")],
        )

    assert Element.objects.count() == count


@pytest.mark.django_db
def test_empty_containers_are_data_without_coaching(builder_ctx):
    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(ref="empty", type="simple_container"),
            ElementItemCreate(ref="full", type="simple_container"),
            heading(parent_element="full"),
        ],
    )

    assert result["empty_containers"] == [
        {
            "id": result["ref_to_id_map"]["empty"],
            "ref": "empty",
            "type": "simple_container",
        }
    ]
    assert "next_steps" not in result


# ---------------------------------------------------------------------------
# Scoping
# ---------------------------------------------------------------------------


@pytest.fixture
def elsewhere(data_fixture, builder_ctx):
    """A page of the same builder, a sibling builder and another workspace."""

    user = builder_ctx["user"]
    same_builder = data_fixture.create_builder_page(
        builder=builder_ctx["builder"], name="Same builder"
    )
    sibling = data_fixture.create_builder_application(
        workspace=builder_ctx["workspace"]
    )
    sibling_page = data_fixture.create_builder_page(builder=sibling, name="Sibling")
    other_workspace = data_fixture.create_workspace(user=user)
    other = data_fixture.create_builder_application(workspace=other_workspace)
    other_page = data_fixture.create_builder_page(builder=other, name="Other")
    return {
        "same_builder": same_builder,
        "same_builder_box": data_fixture.create_builder_column_element(
            page=same_builder
        ),
        "sibling_page": sibling_page,
        "sibling_box": data_fixture.create_builder_column_element(page=sibling_page),
        "sibling_data_source": (
            data_fixture.create_builder_local_baserow_list_rows_data_source(
                page=sibling_page
            )
        ),
        "other_page": other_page,
        "other_box": data_fixture.create_builder_column_element(page=other_page),
    }


@pytest.mark.django_db
def test_create_refuses_a_page_of_another_workspace(builder_ctx, elsewhere):
    with pytest.raises(PageDoesNotExist):
        elements.create_elements(
            builder_ctx["ctx"], elsewhere["other_page"].id, [heading()]
        )


@pytest.mark.django_db
@pytest.mark.parametrize("box", ["same_builder_box", "sibling_box", "other_box"])
def test_create_refuses_a_parent_or_before_element_elsewhere(
    builder_ctx, elsewhere, box
):
    box_id = elsewhere[box].id
    count = Element.objects.count()
    ctx, page_id = builder_ctx["ctx"], builder_ctx["page"].id

    as_parent = elements.create_elements(ctx, page_id, [heading(parent_element=box_id)])
    as_before = elements.create_elements(ctx, page_id, [heading()], box_id)

    assert "not found on this page" in as_parent["errors"][0]
    assert "not found on this page" in as_before["errors"][0]
    assert Element.objects.count() == count


@pytest.mark.django_db
def test_create_refuses_a_data_source_of_another_builder(builder_ctx, elsewhere):
    result = elements.create_collection_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            CollectionElementCreate(
                ref="r", type="repeat", data_source=elsewhere["sibling_data_source"].id
            )
        ],
    )

    assert result["created_elements"] == []
    assert "not found on this page" in result["errors"][0]


@pytest.mark.django_db
@pytest.mark.parametrize("target", ["sibling_page", "other_page"])
def test_nested_page_ids_must_be_of_this_builder(builder_ctx, elsewhere, target):
    page_id = elsewhere[target].id
    count = Element.objects.count()

    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(
                ref="link",
                type="link",
                value="Go",
                navigation_type="page",
                navigate_to_page_id=page_id,
            ),
            ElementItemCreate(
                ref="menu",
                type="menu",
                menu_items=[MenuItemCreate(name="Away", page_id=page_id)],
            ),
            ElementItemCreate(
                ref="top",
                type="header",
                menu_items=[MenuItemCreate(name="Away", page_id=page_id)],
            ),
            ElementItemCreate(
                ref="only", type="header", share_type="only", page_ids=[page_id]
            ),
        ],
    )

    assert result["created_elements"] == []
    assert [error.split(":")[0] for error in result["errors"]] == [
        "link",
        "menu",
        "top",
        "only",
    ]
    assert Element.objects.count() == count


@pytest.mark.django_db
def test_update_scopes_the_element_to_the_workspace(builder_ctx, elsewhere):
    ctx = builder_ctx["ctx"]
    changes = ElementEdits(column_amount=3)

    with pytest.raises(ElementDoesNotExist):
        elements.update_element(ctx, elsewhere["other_box"].id, changes)
    with pytest.raises(ElementDoesNotExist):
        elements.update_element_style(
            ctx, elsewhere["other_box"].id, ElementStyleChanges(padding=1)
        )


@pytest.mark.django_db
def test_update_refuses_a_link_or_menu_item_to_another_builder(builder_ctx, elsewhere):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    created = elements.create_elements(
        ctx,
        page.id,
        [
            ElementItemCreate(ref="link", type="link", value="Go"),
            ElementItemCreate(ref="menu", type="menu"),
        ],
    )["ref_to_id_map"]
    away = elsewhere["sibling_page"].id

    with pytest.raises(DRFValidationError, match="doesn't exist"):
        elements.update_element(
            ctx,
            created["link"],
            ElementEdits(navigate_to_page_id=away),
        )
    with pytest.raises(ToolInputError):
        elements.update_element(
            ctx,
            created["menu"],
            ElementEdits(add_menu_items=[MenuItemAdd(name="Away", page_id=away)]),
        )


@pytest.mark.django_db
def test_move_to_a_container_on_another_page_is_refused(
    data_fixture, builder_ctx, elsewhere
):
    element = builder_ctx["button"]
    before = (element.parent_element_id, element.page_id)
    for box in ("same_builder_box", "sibling_box", "other_box"):
        result = elements.move_elements(
            builder_ctx["ctx"],
            [ElementMove(element_id=element.id, parent_element_id=elsewhere[box].id)],
        )
        assert result["moved_elements"] == []
        assert result["errors"][0].startswith(f"{element.id}: ")

    element.refresh_from_db()
    assert (element.parent_element_id, element.page_id) == before


@pytest.mark.django_db
def test_move_into_the_shared_page_is_refused(data_fixture, builder_ctx):
    element = builder_ctx["button"]
    header = data_fixture.create_builder_column_element(
        page=builder_ctx["builder"].shared_page
    )

    result = elements.move_elements(
        builder_ctx["ctx"],
        [
            ElementMove(
                element_id=element.id,
                parent_element_id=header.id,
                place_in_container="0",
            )
        ],
    )

    assert result["moved_elements"] == []
    assert result["errors"][0].startswith(f"{element.id}: ")
    element.refresh_from_db()
    assert element.page_id == builder_ctx["page"].id


@pytest.mark.django_db
def test_move_of_an_element_in_another_workspace_is_refused(builder_ctx, elsewhere):
    result = elements.move_elements(
        builder_ctx["ctx"], [ElementMove(element_id=elsewhere["other_box"].id)]
    )

    assert result["moved_elements"] == []
    assert result["errors"] == [
        f"{elsewhere['other_box'].id}: Not found in this workspace."
    ]


# ---------------------------------------------------------------------------
# Moves
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_move_keeps_the_good_moves(data_fixture, builder_ctx):
    page = builder_ctx["page"]
    box = data_fixture.create_builder_column_element(page=page, column_amount=2)
    element = builder_ctx["button"]

    result = elements.move_elements(
        builder_ctx["ctx"],
        [
            ElementMove(element_id=999999),
            ElementMove(
                element_id=element.id, parent_element_id=box.id, place_in_container="1"
            ),
        ],
    )

    assert result["moved_elements"] == [
        {
            "element_id": element.id,
            "parent_element_id": box.id,
            "place_in_container": "1",
        }
    ]
    assert result["errors"] == ["999999: Not found in this workspace."]


# ---------------------------------------------------------------------------
# Updates
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_update_stores_a_formula_and_returns_the_element(data_fixture, builder_ctx):
    page = data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        name="Item",
        path="/item/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )
    element = data_fixture.create_builder_heading_element(page=page, value="'Old'")

    result = elements.update_element(
        builder_ctx["ctx"],
        element.id,
        ElementEdits(value="get('page_parameter.id')", level=2),
    )

    assert result["updated_element"]["id"] == element.id
    assert "formula_errors" not in result
    element = saved(element.id)
    assert element.value["formula"] == "get('page_parameter.id')"
    assert element.value["mode"] == BASEROW_FORMULA_MODE_ADVANCED
    assert element.level == 2


@pytest.mark.django_db
def test_update_keeps_the_old_value_for_a_description(data_fixture, builder_ctx):
    element = data_fixture.create_builder_heading_element(
        page=builder_ctx["page"], value="'Old'"
    )

    result = elements.update_element(
        builder_ctx["ctx"],
        element.id,
        ElementEdits(value="$formula: a new title", level=3),
    )

    assert result["formula_errors"][0]["element_id"] == element.id
    assert result["formula_errors"][0]["field"] == "value"
    element = saved(element.id)
    assert element.value["formula"] == "'Old'"
    assert element.level == 3


@pytest.mark.django_db
def test_update_a_link_url_formula_switches_its_type_only_when_stored(
    data_fixture, builder_ctx
):
    element = data_fixture.create_builder_link_element(
        page=builder_ctx["page"], navigation_type="page"
    )
    ctx = builder_ctx["ctx"]

    described = elements.update_element(
        ctx,
        element.id,
        ElementEdits(navigation_type="custom", navigate_to_url="$formula: a url"),
    )
    assert described["formula_errors"][0]["field"] == "navigate_to_url"
    assert saved(element.id).navigation_type == "page"

    stored = elements.update_element(
        ctx,
        element.id,
        ElementEdits(navigation_type="custom", navigate_to_url="get('user.email')"),
    )
    assert "formula_errors" not in stored
    element = saved(element.id)
    assert element.navigation_type == "custom"
    assert element.navigate_to_url["formula"] == "get('user.email')"


@pytest.mark.django_db
def test_update_changes_table_columns_and_menu_items(data_fixture, builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    created = elements.create_elements(
        ctx,
        page.id,
        [
            ElementItemCreate(
                ref="t",
                type="table",
                data_source=builder_ctx["data_source"].id,
                fields=[TableFieldConfig(name="Name")],
            ),
            ElementItemCreate(ref="menu", type="menu"),
        ],
    )["ref_to_id_map"]

    table = elements.update_element(
        ctx,
        created["t"],
        ElementEdits(
            add_table_columns=[
                TableColumnAdd(name="Id", value="get('current_record.id')")
            ]
        ),
    )
    uid = table["updated_element"]["table_columns"][0]["uid"]
    renamed = elements.update_element(
        ctx,
        created["t"],
        ElementEdits(update_table_columns=[TableColumnUpdate(uid=uid, name="Renamed")]),
    )
    menu = elements.update_element(
        ctx,
        created["menu"],
        ElementEdits(add_menu_items=[MenuItemAdd(name="Home", page_id=page.id)]),
    )

    assert [c["name"] for c in table["updated_element"]["table_columns"]] == [
        "Name",
        "Id",
    ]
    assert renamed["updated_element"]["table_columns"][0]["name"] == "Renamed"
    assert [i["name"] for i in menu["updated_element"]["menu_items"]] == ["Home"]


@pytest.mark.django_db
def test_update_a_header_changes_its_menu_and_returns_it(data_fixture, builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    header = elements.create_layout_elements(
        ctx, page.id, [LayoutElementCreate(ref="top", type="header")]
    )["ref_to_id_map"]["top"]

    result = elements.update_element(
        ctx,
        header,
        ElementEdits(add_menu_items=[MenuItemAdd(name="Home", page_id=page.id)]),
    )

    assert result["updated_element"]["page_name"] == "[shared]"
    assert [item["name"] for item in result["menu_items"]] == ["Home"]


@pytest.mark.django_db
def test_update_of_an_unknown_property_changes_nothing(data_fixture, builder_ctx):
    element = data_fixture.create_builder_heading_element(
        page=builder_ctx["page"], value="'Old'"
    )

    with pytest.raises(ToolInputError, match="Unsupported properties"):
        elements.update_element(
            builder_ctx["ctx"],
            element.id,
            ElementEdits(column_amount=3, value="New"),
        )

    assert saved(element.id).value["formula"] == "'Old'"


@pytest.mark.django_db
def test_record_selector_and_datetime_picker_store_their_default_value(
    data_fixture, builder_ctx
):
    result = elements.create_form_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            FormElementCreate(ref="form", type="form_container"),
            FormElementCreate(
                ref="plain",
                type="record_selector",
                parent_element="form",
                data_source=builder_ctx["data_source"].id,
                default_value="7",
            ),
            FormElementCreate(
                ref="dynamic",
                type="record_selector",
                parent_element="form",
                data_source=builder_ctx["data_source"].id,
                default_value="get('user.id')",
            ),
            FormElementCreate(
                ref="described",
                type="record_selector",
                parent_element="form",
                data_source=builder_ctx["data_source"].id,
                default_value="$formula: the id of the user",
            ),
            FormElementCreate(
                ref="date", type="datetime_picker", default_value="2024-01-01"
            ),
            FormElementCreate(
                ref="date_formula",
                type="datetime_picker",
                default_value="get('user.id')",
            ),
        ],
    )

    ids = result["ref_to_id_map"]
    assert not result.get("errors")
    assert saved(ids["plain"]).default_value["formula"] == "'7'"
    assert saved(ids["dynamic"]).default_value["formula"] == "get('user.id')"
    assert saved(ids["described"]).default_value["formula"] == "''"
    assert saved(ids["date"]).default_value["formula"] == "'2024-01-01'"
    assert saved(ids["date_formula"]).default_value["formula"] == "get('user.id')"
    assert [(e["element_id"], e["field"]) for e in result["formula_errors"]] == [
        (ids["described"], "default_value")
    ]


@pytest.mark.django_db
def test_a_link_with_a_url_and_no_navigation_type_goes_to_the_url(builder_ctx):
    result = elements.create_display_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            DisplayElementCreate(
                ref="plain", type="link", value="Go", navigate_to_url="https://a.b"
            ),
            DisplayElementCreate(
                ref="dynamic",
                type="link",
                value="Mail",
                navigate_to_url="get('user.email')",
            ),
            DisplayElementCreate(ref="page", type="link", value="Stay"),
        ],
    )

    ids = result["ref_to_id_map"]
    assert not result.get("errors")
    assert not result.get("formula_errors")
    plain = saved(ids["plain"])
    assert plain.navigation_type == "custom"
    assert plain.navigate_to_url["formula"] == "'https://a.b'"
    dynamic = saved(ids["dynamic"])
    assert dynamic.navigation_type == "custom"
    assert dynamic.navigate_to_url["formula"] == "get('user.email')"
    assert saved(ids["page"]).navigation_type == "page"


@pytest.mark.django_db
def test_update_element_style(data_fixture, builder_ctx):
    element = data_fixture.create_builder_heading_element(page=builder_ctx["page"])

    result = elements.update_element_style(
        builder_ctx["ctx"], element.id, ElementStyleChanges(padding=7)
    )

    assert result["updated_element"]["id"] == element.id
    assert "style_padding_top" in result["updated_fields"]
    assert saved(element.id).style_padding_top == 7


@pytest.mark.django_db
def test_the_highest_style_values_are_stored(builder_ctx):
    button = builder_ctx["button"]

    elements.update_element_style(
        builder_ctx["ctx"],
        button.id,
        ElementStyleChanges(
            border_radius=32767,
            background_radius=0,
            background_color="x" * 255,
            border_color="y" * 255,
            padding=2147483647,
        ),
    )

    stored = Element.objects.get(id=button.id)
    assert stored.style_border_radius == 32767
    assert stored.style_background_radius == 0
    assert stored.style_background_color == "x" * 255
    assert stored.style_border_left_color == "y" * 255
    assert stored.style_padding_top == 2147483647


@pytest.mark.django_db
@pytest.mark.parametrize(
    "style",
    [
        {"padding": -5},
        {"border_radius": 32768},
        {"border_radius": -5},
        {"background_radius": 32768},
        {"background_radius": -5},
        {"background_color": "x" * 256},
        {"border_color": "x" * 256},
        {"border_color": {"left": "x" * 256}},
        {"padding": 2147483648},
        {"margin": {"top": 2147483648}},
        {"border_size": 2147483648},
    ],
)
def test_a_style_the_rest_api_refuses_changes_nothing(builder_ctx, style):
    button = builder_ctx["button"]
    before = Element.objects.filter(id=button.id).values().get()

    # The input model refuses most; the rest are refused when the style is built.
    with pytest.raises((PydanticValidationError, ToolInputError)):
        elements.update_element_style(
            builder_ctx["ctx"], button.id, ElementStyleChanges(**style)
        )

    assert Element.objects.filter(id=button.id).values().get() == before


@pytest.mark.django_db
def test_update_element_style_with_a_bad_side_is_an_input_error(
    data_fixture, builder_ctx
):
    element = data_fixture.create_builder_heading_element(page=builder_ctx["page"])

    with pytest.raises(ToolInputError):
        elements.update_element_style(
            builder_ctx["ctx"], element.id, ElementStyleChanges(padding={"up": 1})
        )


@pytest.fixture
def save_button(data_fixture, builder_ctx):
    return data_fixture.create_builder_button_element(
        page=builder_ctx["page"], value="'Save'"
    )


@pytest.mark.django_db
def test_changing_a_button_text_points_to_its_notification(
    data_fixture, builder_ctx, save_button
):
    action = data_fixture.create_notification_workflow_action(
        page=builder_ctx["page"], element=save_button, event="click", title="'Saved'"
    )

    result = elements.update_element(
        builder_ctx["ctx"], save_button.id, ElementEdits(label="All done!")
    )

    save_button.refresh_from_db()
    action.refresh_from_db()
    assert save_button.value["formula"] == "'All done!'"
    assert action.title["formula"] == "'Saved'"
    assert "change that action" in result["note"]
    assert str(action.id) in result["note"]
    assert "'Saved'" in result["note"]


@pytest.mark.django_db
def test_changing_the_text_of_a_button_without_a_notification_adds_no_note(
    data_fixture, builder_ctx, save_button
):
    data_fixture.create_open_page_workflow_action(
        page=builder_ctx["page"], element=save_button, event="click"
    )

    result = elements.update_element(
        builder_ctx["ctx"], save_button.id, ElementEdits(value="Store")
    )

    assert "note" not in result


@pytest.mark.django_db
def test_changing_a_button_without_touching_its_text_adds_no_note(
    data_fixture, builder_ctx, save_button
):
    data_fixture.create_notification_workflow_action(
        page=builder_ctx["page"], element=save_button, event="click", title="'Saved'"
    )

    result = elements.update_element(
        builder_ctx["ctx"], save_button.id, ElementEdits(visibility="logged-in")
    )

    assert "note" not in result


# ---------------------------------------------------------------------------
# Table column formulas
# ---------------------------------------------------------------------------


@pytest.fixture
def table_with_stale_column(data_fixture, builder_ctx):
    """A table reading the data source, with a column that reads a field by name."""

    return data_fixture.create_builder_table_element(
        page=builder_ctx["page"],
        data_source=builder_ctx["data_source"],
        fields=[
            {
                "name": "Stale",
                "type": "text",
                "config": {
                    "value": {
                        "formula": "get('current_record.Name')",
                        "mode": "advanced",
                        "version": "0.1",
                    }
                },
            },
        ],
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value",
    [
        "get('current_record.Name')",
        "get('data_source.999999.0.field_1')",
        "get('nosuch.x')",
    ],
    ids=["by-name", "other-data-source", "unknown-provider"],
)
def test_a_new_column_reading_what_the_page_lacks_is_refused(
    builder_ctx, table_with_stale_column, value
):
    table = table_with_stale_column

    with pytest.raises(ToolInputError, match="No changes were applied"):
        elements.update_element(
            builder_ctx["ctx"],
            table.id,
            ElementEdits(add_table_columns=[TableColumnAdd(name="Bad", value=value)]),
        )

    assert [column.name for column in saved(table.id).fields.all()] == ["Stale"]


@pytest.mark.django_db
def test_a_changed_column_reading_a_field_by_name_is_refused(
    builder_ctx, table_field, table_with_stale_column
):
    table = table_with_stale_column
    uid = str(table.fields.get().uid)
    good = f"get('current_record.field_{table_field.id}')"
    ctx = builder_ctx["ctx"]

    elements.update_element(
        ctx,
        table.id,
        ElementEdits(update_table_columns=[TableColumnUpdate(uid=uid, value=good)]),
    )
    with pytest.raises(ToolInputError, match="current_record.Name"):
        elements.update_element(
            ctx,
            table.id,
            ElementEdits(
                update_table_columns=[
                    TableColumnUpdate(uid=uid, value="get('current_record.Name')")
                ]
            ),
        )

    assert saved(table.id).fields.get().config["value"]["formula"] == good


@pytest.mark.django_db
def test_a_new_button_column_label_reading_a_field_by_name_is_refused(
    builder_ctx, table_with_stale_column
):
    with pytest.raises(ToolInputError, match="current_record.Name"):
        elements.update_element(
            builder_ctx["ctx"],
            table_with_stale_column.id,
            ElementEdits(
                add_table_columns=[
                    TableColumnAdd(
                        name="Go", type="button", label="get('current_record.Name')"
                    )
                ]
            ),
        )


@pytest.mark.django_db
def test_a_stored_column_does_not_block_an_unrelated_change(
    builder_ctx, table_field, table_with_stale_column
):
    table = table_with_stale_column
    uid = str(table.fields.get().uid)
    ctx = builder_ctx["ctx"]

    elements.update_element(
        ctx,
        table.id,
        ElementEdits(update_table_columns=[TableColumnUpdate(uid=uid, name="Old")]),
    )
    result = elements.update_element(
        ctx,
        table.id,
        ElementEdits(
            add_table_columns=[
                TableColumnAdd(
                    name="Good", value=f"get('current_record.field_{table_field.id}')"
                ),
                TableColumnAdd(name="Fixed", value="plain text"),
                TableColumnAdd(name="Bound", field_id=table_field.id),
            ]
        ),
    )

    assert [c["name"] for c in result["updated_element"]["table_columns"]] == [
        "Old",
        "Good",
        "Fixed",
        "Bound",
    ]


# ---------------------------------------------------------------------------
# A form element's default value
# ---------------------------------------------------------------------------


@pytest.fixture
def own_rows(data_fixture, builder_ctx):
    """A data source reading another table, and that table's field."""

    other = data_fixture.create_database_table(
        database=builder_ctx["data_source"].service.specific.table.database
    )
    own_field = data_fixture.create_text_field(table=other, name="Own", primary=True)
    own_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=builder_ctx["page"], table=other, name="Own rows"
    )
    return own_source, own_field


@pytest.fixture
def selector_in_repeat(builder_ctx, repeat, own_rows):
    """A record selector inside a repeat, reading rows of another table."""

    own_source, own_field = own_rows
    result = elements.create_form_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            FormElementCreate(
                ref="selector",
                type="record_selector",
                parent_element=repeat.id,
                data_source=own_source.id,
            )
        ],
    )
    assert not result.get("errors")
    selector = saved(result["ref_to_id_map"]["selector"])
    assert selector.parent_element_id == repeat.id
    return selector, own_field


@pytest.mark.django_db
def test_a_default_value_reads_the_row_of_the_repeat_around_it(
    builder_ctx, table_field, selector_in_repeat
):
    selector, _own_field = selector_in_repeat
    formula = f"get('current_record.field_{table_field.id}')"

    result = elements.update_element(
        builder_ctx["ctx"], selector.id, ElementEdits(default_value=formula)
    )

    assert "formula_errors" not in result
    assert saved(selector.id).default_value["formula"] == formula


@pytest.mark.django_db
def test_a_default_value_can_not_read_the_selectors_own_rows(
    builder_ctx, selector_in_repeat
):
    selector, own_field = selector_in_repeat

    result = elements.update_element(
        builder_ctx["ctx"],
        selector.id,
        ElementEdits(default_value=f"get('current_record.field_{own_field.id}')"),
    )

    assert [e["field"] for e in result["formula_errors"]] == ["default_value"]
    assert saved(selector.id).default_value["formula"] == "''"


@pytest.mark.django_db
def test_a_default_value_of_a_new_selector_reads_the_repeat_around_it(
    builder_ctx, repeat, table_field, own_rows
):
    formula = f"get('current_record.field_{table_field.id}')"
    result = elements.create_form_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            FormElementCreate(
                ref="selector",
                type="record_selector",
                parent_element=repeat.id,
                data_source=own_rows[0].id,
                default_value=formula,
            )
        ],
    )

    assert "formula_errors" not in result
    selector = saved(result["ref_to_id_map"]["selector"])
    assert selector.default_value["formula"] == formula


@pytest.mark.django_db
def test_a_default_value_outside_a_repeat_has_no_row_to_read(builder_ctx, table_field):
    result = elements.create_form_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            FormElementCreate(
                ref="selector",
                type="record_selector",
                data_source=builder_ctx["data_source"].id,
                default_value=f"get('current_record.field_{table_field.id}')",
            )
        ],
    )

    assert "inside a repeat or a table" in result["formula_errors"][0]["error"]


# ---------------------------------------------------------------------------
# The order of children
# ---------------------------------------------------------------------------


def children_of(parent_id, place=None):
    """The text of a container's children as the page shows them, read again."""

    page = Element.objects.get(id=parent_id).page
    page.reload_graph()
    return [
        saved(child.id).value["formula"]
        for child in page.get_graph().get_children(parent_id, place)
    ]


def text(ref, value, element_type="heading", **kwargs):
    return ElementItemCreate(ref=ref, type=element_type, value=value, **kwargs)


@pytest.mark.django_db
def test_children_in_a_container_keep_their_order(builder_ctx):
    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(ref="box", type="simple_container"),
            text("a", "First", parent_element="box"),
            text("b", "Second", parent_element="box"),
        ],
    )

    assert children_of(result["ref_to_id_map"]["box"]) == ["'First'", "'Second'"]
    assert (
        saved(result["ref_to_id_map"]["b"]).parent_element_id
        == (result["ref_to_id_map"]["box"])
    )


@pytest.mark.django_db
def test_buttons_in_a_header_keep_their_order(builder_ctx):
    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(ref="top", type="header"),
            text("a", "First", "button", parent_element="top"),
            text("b", "Second", "button", parent_element="top"),
        ],
    )

    assert children_of(result["ref_to_id_map"]["top"]) == ["'First'", "'Second'"]


@pytest.mark.django_db
def test_children_added_in_a_later_call_go_last(builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    box = elements.create_elements(
        ctx, page.id, [ElementItemCreate(ref="box", type="simple_container")]
    )["ref_to_id_map"]["box"]

    elements.create_elements(ctx, page.id, [text("a", "First", parent_element=box)])
    elements.create_elements(ctx, page.id, [text("b", "Second", parent_element=box)])

    assert children_of(box) == ["'First'", "'Second'"]


@pytest.mark.django_db
def test_children_keep_their_order_in_each_column(builder_ctx):
    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(ref="cols", type="column", column_amount=2),
            text("a", "First", parent_element="cols", place_in_container="1"),
            text("b", "Other", parent_element="cols", place_in_container="0"),
            text("c", "Second", parent_element="cols", place_in_container="1"),
            text("d", "Unset", parent_element="cols"),
        ],
    )

    assert not result.get("errors")
    cols = result["ref_to_id_map"]["cols"]
    assert children_of(cols, "1") == ["'First'", "'Second'"]
    assert children_of(cols, "0") == ["'Other'", "'Unset'"]
    assert saved(result["ref_to_id_map"]["c"]).place_in_container == "1"


@pytest.mark.django_db
def test_top_level_elements_keep_their_order(builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    ids = elements.create_elements(
        ctx, page.id, [text("a", "First"), text("b", "Second")]
    )["ref_to_id_map"]

    page.reload_graph()
    assert page.get_graph().get_next_points(saved(ids["a"])) == [saved(ids["b"])]


@pytest.mark.django_db
def test_elements_moved_into_a_container_keep_their_order(data_fixture, builder_ctx):
    page = builder_ctx["page"]
    box = data_fixture.create_builder_column_element(page=page, column_amount=2)
    first = data_fixture.create_builder_heading_element(page=page, value="'First'")
    second = data_fixture.create_builder_heading_element(page=page, value="'Second'")

    result = elements.move_elements(
        builder_ctx["ctx"],
        [
            ElementMove(
                element_id=element.id, parent_element_id=box.id, place_in_container="1"
            )
            for element in (first, second)
        ],
    )

    assert children_of(box.id, "1") == ["'First'", "'Second'"]
    assert [move["place_in_container"] for move in result["moved_elements"]] == [
        "1",
        "1",
    ]


@pytest.fixture
def box(data_fixture, builder_ctx):
    """
    A container holding First and Second, a Middle heading outside it, and the
    page's button, by name.
    """

    ids = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(ref="box", type="simple_container"),
            text("a", "First", parent_element="box"),
            text("b", "Second", parent_element="box"),
        ],
    )["ref_to_id_map"]
    middle = data_fixture.create_builder_heading_element(
        page=builder_ctx["page"], value="'Middle'"
    )
    return {**ids, "middle": middle.id, "button": builder_ctx["button"].id}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "move, children, error",
    [
        pytest.param(
            {"element_id": "b", "parent_element_id": "box"},
            ["'First'", "'Second'"],
            None,
            id="the last child into its container changes nothing",
        ),
        pytest.param(
            {"element_id": "a", "parent_element_id": "box"},
            ["'Second'", "'First'"],
            None,
            id="a child to the end of its container",
        ),
        pytest.param(
            {"element_id": "middle", "parent_element_id": "box", "before_id": "b"},
            ["'First'", "'Middle'", "'Second'"],
            None,
            id="into a container before one of its children",
        ),
        pytest.param(
            {"element_id": "middle", "parent_element_id": "box", "before_id": "button"},
            ["'First'", "'Second'"],
            "isn't in",
            id="before an element outside the parent is refused",
        ),
    ],
)
def test_move_in_a_container(builder_ctx, box, move, children, error):
    result = elements.move_elements(
        builder_ctx["ctx"],
        [ElementMove(**{key: box[name] for key, name in move.items()})],
    )

    if error:
        assert error in result["errors"][0]
        assert str(box[move["before_id"]]) in result["errors"][0]
    else:
        assert not result.get("errors")
    assert children_of(box["box"]) == children


@pytest.mark.django_db
def test_elements_are_listed_in_page_order_with_children_after_their_container(
    data_fixture, builder_ctx
):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    ids = elements.create_elements(
        ctx,
        page.id,
        [
            text("a", "A"),
            ElementItemCreate(ref="box", type="simple_container"),
            text("in", "Inside", parent_element="box"),
            text("b", "B"),
        ],
    )["ref_to_id_map"]

    elements.move_elements(ctx, [ElementMove(element_id=ids["b"], before_id=ids["a"])])

    listed = [e["id"] for e in elements.list_elements(ctx, page.id)["elements"]]
    assert [i for i in listed if i in ids.values()] == [
        ids["b"],
        ids["a"],
        ids["box"],
        ids["in"],
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "place, error",
    [
        pytest.param("", None, id="an empty place uses the child's place"),
        pytest.param("1", "not '1'", id="another place is refused"),
    ],
)
def test_move_before_a_child_of_a_column(data_fixture, builder_ctx, place, error):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    ids = elements.create_elements(
        ctx,
        page.id,
        [
            ElementItemCreate(ref="cols", type="column"),
            text("a", "A", parent_element="cols"),
        ],
    )["ref_to_id_map"]
    moved = data_fixture.create_builder_heading_element(page=page, value="'M'")

    result = elements.move_elements(
        ctx,
        [
            ElementMove(
                element_id=moved.id,
                parent_element_id=ids["cols"],
                before_id=ids["a"],
                place_in_container=place,
            )
        ],
    )

    if error:
        assert error in str(result["errors"])
        assert children_of(ids["cols"]) == ["'A'"]
    else:
        assert not result.get("errors")
        assert children_of(ids["cols"]) == ["'M'", "'A'"]


@pytest.mark.django_db
def test_a_child_goes_before_the_element_given_in_its_container(builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    ids = elements.create_elements(
        ctx,
        page.id,
        [
            ElementItemCreate(ref="box", type="simple_container"),
            text("a", "First", parent_element="box"),
            text("b", "Third", parent_element="box"),
        ],
    )["ref_to_id_map"]

    result = elements.create_elements(
        ctx,
        page.id,
        [text("x", "Second", parent_element=ids["box"])],
        before_element_id=ids["b"],
    )

    assert not result.get("errors")
    assert children_of(ids["box"]) == ["'First'", "'Second'", "'Third'"]
    assert saved(result["ref_to_id_map"]["x"]).parent_element_id == ids["box"]


@pytest.mark.django_db
def test_a_child_goes_before_the_element_given_in_its_column(builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    ids = elements.create_elements(
        ctx,
        page.id,
        [
            ElementItemCreate(ref="cols", type="column", column_amount=2),
            text("a", "Second", parent_element="cols", place_in_container="1"),
        ],
    )["ref_to_id_map"]

    result = elements.create_elements(
        ctx,
        page.id,
        [text("x", "First", parent_element=ids["cols"])],
        before_element_id=ids["a"],
    )

    assert not result.get("errors")
    assert children_of(ids["cols"], "1") == ["'First'", "'Second'"]
    assert saved(result["ref_to_id_map"]["x"]).place_in_container == "1"


@pytest.mark.django_db
def test_a_child_for_another_place_than_the_element_given_is_refused(builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    ids = elements.create_elements(
        ctx,
        page.id,
        [
            ElementItemCreate(ref="cols", type="column", column_amount=2),
            text("a", "Second", parent_element="cols", place_in_container="1"),
        ],
    )["ref_to_id_map"]

    result = elements.create_elements(
        ctx,
        page.id,
        [text("x", "First", parent_element=ids["cols"], place_in_container="0")],
        before_element_id=ids["a"],
    )

    assert result["created_elements"] == []
    assert "not '0'" in result["errors"][0]


@pytest.mark.django_db
def test_a_child_with_a_before_element_elsewhere_goes_last(builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    ids = elements.create_elements(
        ctx,
        page.id,
        [
            ElementItemCreate(ref="box", type="simple_container"),
            text("a", "First", parent_element="box"),
            text("other", "Elsewhere"),
        ],
    )["ref_to_id_map"]

    elements.create_elements(
        ctx,
        page.id,
        [text("x", "Second", parent_element=ids["box"])],
        before_element_id=ids["other"],
    )

    assert children_of(ids["box"]) == ["'First'", "'Second'"]


@pytest.mark.django_db
def test_moving_into_a_column_without_a_place_uses_its_first_place(builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    ids = elements.create_elements(
        ctx,
        page.id,
        [
            ElementItemCreate(ref="cols", type="column", column_amount=2),
            text("a", "First", parent_element="cols", place_in_container="0"),
            text("b", "Second"),
        ],
    )["ref_to_id_map"]

    result = elements.move_elements(
        ctx, [ElementMove(element_id=ids["b"], parent_element_id=ids["cols"])]
    )

    assert not result.get("errors")
    assert children_of(ids["cols"], "0") == ["'First'", "'Second'"]


@pytest.mark.django_db
def test_moving_an_empty_container_into_itself_is_refused(builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    box = elements.create_elements(
        ctx, page.id, [ElementItemCreate(ref="box", type="simple_container")]
    )["ref_to_id_map"]["box"]

    result = elements.move_elements(
        ctx, [ElementMove(element_id=box, parent_element_id=box)]
    )

    assert result["moved_elements"] == []
    assert "itself" in result["errors"][0]
    assert saved(box).parent_element_id is None


@pytest.mark.django_db
def test_moving_a_container_into_itself_is_refused(builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    ids = elements.create_elements(
        ctx,
        page.id,
        [
            ElementItemCreate(ref="box", type="simple_container"),
            text("a", "First", parent_element="box"),
        ],
    )["ref_to_id_map"]

    result = elements.move_elements(
        ctx, [ElementMove(element_id=ids["box"], parent_element_id=ids["box"])]
    )

    assert result["moved_elements"] == []
    assert len(result["errors"]) == 1
    assert children_of(ids["box"]) == ["'First'"]


@pytest.mark.django_db
def test_moving_the_last_child_to_the_end_of_its_container_stays_a_success(
    builder_ctx,
):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    ids = elements.create_elements(
        ctx,
        page.id,
        [
            ElementItemCreate(ref="box", type="simple_container"),
            text("a", "First", parent_element="box"),
        ],
    )["ref_to_id_map"]

    result = elements.move_elements(
        ctx, [ElementMove(element_id=ids["a"], parent_element_id=ids["box"])]
    )

    assert not result.get("errors")
    assert result["moved_elements"][0]["parent_element_id"] == ids["box"]


@pytest.mark.django_db
def test_a_display_link_can_give_the_parameters_of_its_page(data_fixture, builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    target = data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        name="Product",
        path="/products/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )

    result = elements.create_display_elements(
        ctx,
        page.id,
        [
            DisplayElementCreate(
                ref="link",
                type="link",
                value="Open",
                navigate_to_page_id=target.id,
                link_page_parameters=[{"name": "id", "value": "7"}],
            )
        ],
    )

    assert not result.get("errors")
    link = saved(result["ref_to_id_map"]["link"])
    assert [param["name"] for param in link.page_parameters] == ["id"]
    assert link.page_parameters[0]["value"]["formula"] == "7"


# ---------------------------------------------------------------------------
# A link's new target
# ---------------------------------------------------------------------------


@pytest.fixture
def link_pages(data_fixture, builder_ctx):
    def page_at(name, path, *params):
        return data_fixture.create_builder_page(
            builder=builder_ctx["builder"],
            name=name,
            path=path,
            path_params=[{"name": param, "type": "text"} for param in params],
        )

    return {
        "by_id": page_at("Product", "/products/:id", "id"),
        "also_by_id": page_at("Order", "/orders/:id", "id"),
        "by_slug": page_at("Post", "/posts/:slug", "slug"),
        "plain": page_at("Plain", "/plain"),
        "other_plain": page_at("Other", "/other"),
    }


def link_to(data_fixture, builder_ctx, target, *params):
    return data_fixture.create_builder_link_element(
        page=builder_ctx["page"],
        navigation_type="page",
        navigate_to_page_id=target.id,
        page_parameters=[{"name": name, "value": "'1'"} for name in params],
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "start,params,target,named",
    [
        ("by_id", ["id"], "by_slug", ["slug", "missing: slug", "unknown: id"]),
        ("by_id", ["id"], "plain", ["none", "unknown: id"]),
        ("plain", [], "by_id", ["id", "missing: id"]),
    ],
)
def test_a_new_target_that_does_not_fit_a_link_is_refused(
    data_fixture, builder_ctx, link_pages, start, params, target, named
):
    link = link_to(data_fixture, builder_ctx, link_pages[start], *params)

    with pytest.raises(ToolInputError) as error:
        elements.update_element(
            builder_ctx["ctx"],
            link.id,
            ElementEdits(navigate_to_page_id=link_pages[target].id, value="New"),
        )

    assert all(part in str(error.value) for part in named)
    assert "Give link_page_parameters for that page" in str(error.value)
    assert "Replace" not in str(error.value)
    stored = saved(link.id)
    assert stored.navigate_to_page_id == link_pages[start].id
    assert stored.value == link.value


@pytest.mark.django_db
@pytest.mark.parametrize(
    "start,params,target",
    [("plain", [], "other_plain"), ("by_id", ["id"], "also_by_id")],
)
def test_a_new_target_that_fits_a_link_is_stored(
    data_fixture, builder_ctx, link_pages, start, params, target
):
    link = link_to(data_fixture, builder_ctx, link_pages[start], *params)

    elements.update_element(
        builder_ctx["ctx"],
        link.id,
        ElementEdits(navigate_to_page_id=link_pages[target].id),
    )

    stored = saved(link.id)
    assert stored.navigate_to_page_id == link_pages[target].id
    assert [param["name"] for param in stored.page_parameters] == params


@pytest.mark.django_db
def test_a_link_that_keeps_its_target_is_not_checked(
    data_fixture, builder_ctx, link_pages
):
    link = link_to(data_fixture, builder_ctx, link_pages["by_id"])

    elements.update_element(
        builder_ctx["ctx"],
        link.id,
        ElementEdits(navigate_to_page_id=link_pages["by_id"].id, value="New"),
    )

    assert saved(link.id).value["formula"] == "'New'"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "target, params, named",
    [
        ("by_id", None, "missing: id"),
        ("by_id", [{"name": "slug", "value": "7"}], "unknown: slug"),
        ("plain", [{"name": "id", "value": "7"}], "unknown: id"),
    ],
)
def test_a_new_link_that_does_not_fit_its_page_is_refused(
    builder_ctx, link_pages, target, params, named
):
    before = Element.objects.count()

    result = elements.create_display_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            DisplayElementCreate(
                ref="link",
                type="link",
                value="Open",
                navigate_to_page_id=link_pages[target].id,
                link_page_parameters=params,
            )
        ],
    )

    assert result["created_elements"] == []
    assert named in result["errors"][0]
    assert "link_page_parameters" in result["errors"][0]
    assert Element.objects.count() == before


@pytest.mark.django_db
def test_a_new_link_to_a_page_it_fits_is_created(builder_ctx, link_pages):
    result = elements.create_display_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            DisplayElementCreate(
                ref="plain",
                type="link",
                value="Open",
                navigate_to_page_id=link_pages["plain"].id,
            )
        ],
    )

    assert not result.get("errors")


@pytest.mark.django_db
def test_two_changed_columns_of_one_name_are_both_checked(data_fixture, builder_ctx):
    table = data_fixture.create_builder_table_element(
        page=builder_ctx["page"],
        data_source=builder_ctx["data_source"],
        fields=[
            {"name": "Edit", "type": "text", "config": {"value": "''"}},
            {"name": "Edit", "type": "text", "config": {"value": "''"}},
        ],
    )
    first, second = [str(column.uid) for column in table.fields.all()]

    with pytest.raises(ToolInputError, match="No changes were applied"):
        elements.update_element(
            builder_ctx["ctx"],
            table.id,
            ElementEdits(
                update_table_columns=[
                    TableColumnUpdate(uid=first, value="get('page_parameter.nope')"),
                    TableColumnUpdate(uid=second, value="get('current_record.id')"),
                ]
            ),
        )


# ---------------------------------------------------------------------------
# Listing order
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_children_of_a_column_are_listed_by_place(data_fixture, builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    column = data_fixture.create_builder_column_element(page=page, column_amount=11)

    def add(ref, place):
        return elements.create_elements(
            ctx,
            page.id,
            [
                ElementItemCreate(
                    ref=ref,
                    type="heading",
                    value=ref,
                    parent_element=column.id,
                    place_in_container=place,
                )
            ],
        )["ref_to_id_map"][ref]

    ten, two, first, also_first = (
        add("ten", "10"),
        add("two", "2"),
        add("first", "0"),
        add("also_first", "0"),
    )

    listed = [item.id for item in helpers.list_elements(builder_ctx["user"], page)]

    assert [id for id in listed if id in (ten, two, first, also_first)] == [
        first,
        also_first,
        two,
        ten,
    ]


@pytest.mark.django_db
def test_an_auth_form_login_button_label_is_stored_as_text(data_fixture, builder_ctx):
    user_source = data_fixture.create_user_source_with_first_type(
        application=builder_ctx["builder"]
    )

    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(
                ref="login",
                type="auth_form",
                user_source_id=user_source.id,
                login_button_label="Sign in",
            )
        ],
    )

    login = saved(result["ref_to_id_map"]["login"])
    assert login.login_button_label["formula"] == "'Sign in'"
    assert login.login_button_label["mode"] == BASEROW_FORMULA_MODE_ADVANCED


@pytest.fixture
def two_parameter_pages(data_fixture, builder_ctx):
    return [
        data_fixture.create_builder_page(
            builder=builder_ctx["builder"],
            name=path,
            path=path,
            path_params=[{"name": name, "type": "text"} for name in names],
        )
        for path, names in (("/one/:a/:b", "ab"), ("/two/:b/:a", "ba"))
    ]


def _link_parameters(element_id):
    return [
        (param["name"], param["value"]["formula"])
        for param in saved(element_id).page_parameters
    ]


@pytest.mark.django_db
def test_a_new_link_stores_its_parameters_in_page_order(
    builder_ctx, two_parameter_pages
):
    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(
                ref="l",
                type="link",
                value="Open",
                navigate_to_page_id=two_parameter_pages[0].id,
                link_page_parameters=[
                    {"name": "b", "value": "upper('x')"},
                    {"name": "a", "value": "1"},
                ],
            )
        ],
    )

    assert _link_parameters(result["ref_to_id_map"]["l"]) == [
        ("a", "1"),
        ("b", "upper('x')"),
    ]


@pytest.mark.django_db
def test_a_link_given_a_new_page_keeps_its_parameters_in_that_page_order(
    builder_ctx, two_parameter_pages
):
    first, second = two_parameter_pages
    link_id = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(
                ref="l",
                type="link",
                value="Open",
                navigate_to_page_id=first.id,
                link_page_parameters=[
                    {"name": "a", "value": "1"},
                    {"name": "b", "value": "2"},
                ],
            )
        ],
    )["ref_to_id_map"]["l"]

    elements.update_element(
        builder_ctx["ctx"], link_id, ElementEdits(navigate_to_page_id=second.id)
    )

    assert _link_parameters(link_id) == [("b", "2"), ("a", "1")]


@pytest.fixture
def links(data_fixture, builder_ctx):
    target = data_fixture.create_builder_page(
        builder=builder_ctx["builder"], name="Target", path="/target"
    )
    ids = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(
                ref="custom",
                type="link",
                value="Out",
                navigate_to_url="https://example.com",
            ),
            ElementItemCreate(
                ref="page", type="link", value="In", navigate_to_page_id=target.id
            ),
        ],
    )["ref_to_id_map"]
    return {"target": target, **ids}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "link, edits, navigation_type, url_formula, url_error",
    [
        pytest.param(
            "custom",
            {"navigate_to_page_id": "target"},
            "page",
            None,
            False,
            id="a custom link given a page goes to the page",
        ),
        pytest.param(
            "page",
            {"navigate_to_url": "https://example.org"},
            "custom",
            "'https://example.org'",
            False,
            id="a page link given a url goes to the url",
        ),
        pytest.param(
            "page",
            {"navigate_to_url": "concat('https://', 'example.org')"},
            "custom",
            "concat('https://', 'example.org')",
            False,
            id="a page link given a formula url switches with the formula",
        ),
        pytest.param(
            "page",
            {"navigate_to_url": "$formula: the shop's address"},
            "page",
            None,
            True,
            id="a page link given a bad formula url stays on its page",
        ),
        pytest.param(
            "custom",
            {"navigation_type": "custom", "navigate_to_page_id": "target"},
            "custom",
            None,
            False,
            id="an explicit navigation type is kept",
        ),
    ],
)
def test_a_link_given_a_new_target(
    builder_ctx, links, link, edits, navigation_type, url_formula, url_error
):
    values = {
        key: links["target"].id if value == "target" else value
        for key, value in edits.items()
    }

    result = elements.update_element(
        builder_ctx["ctx"], links[link], ElementEdits(**values)
    )

    stored = saved(links[link])
    assert stored.navigation_type == navigation_type
    if navigation_type == "page" and "navigate_to_page_id" in values:
        assert stored.navigate_to_page_id == links["target"].id
    if url_formula is not None:
        assert stored.navigate_to_url["formula"] == url_formula
    if url_error:
        assert result["formula_errors"][0]["field"] == "navigate_to_url"


@pytest.mark.django_db
def test_a_custom_link_back_to_its_stored_page_needs_parameters_that_fit(
    data_fixture, builder_ctx, links
):
    target = data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        name="Item",
        path="/item/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )
    LinkElement.objects.filter(id=links["custom"]).update(navigate_to_page_id=target.id)

    with pytest.raises(ToolInputError, match="missing: id"):
        elements.update_element(
            builder_ctx["ctx"],
            links["custom"],
            ElementEdits(navigate_to_page_id=target.id),
        )

    assert saved(links["custom"]).navigation_type == "custom"


@pytest.fixture
def item_page(data_fixture, builder_ctx):
    return data_fixture.create_builder_page(
        builder=builder_ctx["builder"],
        name="Item",
        path="/item/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )


@pytest.mark.django_db
@pytest.mark.parametrize("element_type", ["menu", "header"])
def test_a_new_menu_can_not_link_to_a_page_with_path_parameters(
    builder_ctx, item_page, element_type
):
    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(
                ref="m",
                type=element_type,
                menu_items=[{"name": "Item", "page_id": item_page.id}],
            )
        ],
    )

    assert "created_elements" not in result or not result["created_elements"]
    assert "path parameters" in result["errors"][0]


@pytest.fixture
def menu_id(builder_ctx):
    return elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [
            ElementItemCreate(
                ref="m",
                type="menu",
                menu_items=[{"name": "Home", "page_id": builder_ctx["page"].id}],
            )
        ],
    )["ref_to_id_map"]["m"]


@pytest.mark.django_db
def test_add_menu_items_can_not_link_to_a_page_with_path_parameters(
    builder_ctx, item_page, menu_id
):
    with pytest.raises(ToolInputError, match="path parameters"):
        elements.update_element(
            builder_ctx["ctx"],
            menu_id,
            ElementEdits(
                add_menu_items=[MenuItemAdd(name="Item", page_id=item_page.id)]
            ),
        )

    assert saved(menu_id).menu_items.count() == 1


@pytest.mark.django_db
def test_update_menu_items_can_not_link_to_a_page_with_path_parameters(
    builder_ctx, item_page, menu_id
):
    uid = str(saved(menu_id).menu_items.get().uid)

    with pytest.raises(ToolInputError, match="path parameters"):
        elements.update_element(
            builder_ctx["ctx"],
            menu_id,
            ElementEdits(
                update_menu_items=[MenuItemUpdate(uid=uid, page_id=item_page.id)]
            ),
        )

    assert saved(menu_id).menu_items.get().navigate_to_page_id == builder_ctx["page"].id


@pytest.mark.django_db
def test_a_menu_item_set_up_with_parameters_in_the_editor_can_be_renamed(
    builder_ctx, item_page, menu_id
):
    item = saved(menu_id).menu_items.get()
    item.navigate_to_page_id = item_page.id
    item.page_parameters = [{"name": "id", "value": "1"}]
    item.save()

    elements.update_element(
        builder_ctx["ctx"],
        menu_id,
        ElementEdits(
            update_menu_items=[
                MenuItemUpdate(uid=str(item.uid), name="New", page_id=item_page.id)
            ]
        ),
    )

    item = saved(menu_id).menu_items.get()
    assert item.name == "New"
    assert [param["name"] for param in item.page_parameters] == ["id"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "values",
    [
        {"share_type": "only"},
        {"share_type": "only", "page_ids": []},
        {"page_ids": "page"},
        {"share_type": "all", "page_ids": "page"},
    ],
)
def test_create_header_refuses_pages_that_can_not_work(builder_ctx, values):
    page = builder_ctx["page"]
    if values.get("page_ids") == "page":
        values = {**values, "page_ids": [page.id]}

    result = elements.create_elements(
        builder_ctx["ctx"],
        page.id,
        [ElementItemCreate(ref="top", type="header", **values)],
    )

    assert result["created_elements"] == []
    assert result["errors"][0].startswith("top:")


@pytest.mark.django_db
@pytest.mark.parametrize("share_type", ["only", "except"])
def test_create_header_shown_on_some_pages(builder_ctx, share_type):
    page = builder_ctx["page"]

    result = elements.create_elements(
        builder_ctx["ctx"],
        page.id,
        [
            ElementItemCreate(
                ref="top", type="header", share_type=share_type, page_ids=[page.id]
            )
        ],
    )

    header = saved(result["ref_to_id_map"]["top"])
    assert header.share_type == share_type
    assert list(header.pages.all()) == [page]


def _create_header(builder_ctx, **values):
    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [ElementItemCreate(ref="top", type="header", **values)],
    )
    return result["ref_to_id_map"]["top"]


@pytest.mark.django_db
def test_update_header_can_not_show_on_only_no_pages(builder_ctx):
    header_id = _create_header(builder_ctx)

    with pytest.raises(ToolInputError, match="page_ids"):
        elements.update_element(
            builder_ctx["ctx"], header_id, ElementEdits(share_type="only")
        )

    assert saved(header_id).share_type == "all"


@pytest.mark.django_db
def test_update_header_can_go_back_to_the_pages_it_has(builder_ctx):
    header_id = _create_header(
        builder_ctx, share_type="except", page_ids=[builder_ctx["page"].id]
    )

    elements.update_element(
        builder_ctx["ctx"], header_id, ElementEdits(share_type="only")
    )

    assert saved(header_id).share_type == "only"


@pytest.mark.django_db
def test_create_element_keeps_a_zero_column_gap(builder_ctx):
    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [ElementItemCreate(ref="zero", type="column", column_gap=0)],
    )

    assert saved(result["ref_to_id_map"]["zero"]).column_gap == 0


@pytest.mark.parametrize("type", ["repeat", "table"])
def test_an_empty_page_size_is_refused(type):
    with pytest.raises(PydanticValidationError, match="greater than or equal to 1"):
        ElementItemCreate(ref="zero", type=type, items_per_page=0)


@pytest.mark.django_db
@pytest.mark.parametrize("type", ["repeat", "table"])
def test_create_element_keeps_a_page_size_of_one(builder_ctx, type):
    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [ElementItemCreate(ref="one", type=type, items_per_page=1)],
    )

    assert saved(result["ref_to_id_map"]["one"]).items_per_page == 1


@pytest.mark.django_db
def test_a_formula_from_list_elements_can_be_sent_back(data_fixture, builder_ctx):
    heading_element = data_fixture.create_builder_heading_element(
        page=builder_ctx["page"], value="upper('abc')"
    )
    listed = elements.list_elements(builder_ctx["ctx"], builder_ctx["page"].id)
    label = next(
        item["label"] for item in listed["elements"] if item["id"] == heading_element.id
    )

    result = elements.update_element(
        builder_ctx["ctx"], heading_element.id, ElementEdits(value=label)
    )

    assert "formula_errors" not in result
    assert saved(heading_element.id).value["formula"] == "upper('abc')"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value, expected",
    [
        ("upper('abc')", "upper('abc')"),
        ("Hello (world)", "'Hello (world)'"),
        ("nosuch('x')", "'nosuch(\\'x\\')'"),
        ("1+1", "'1+1'"),
    ],
)
def test_only_a_whole_function_call_on_an_element_is_a_formula(
    builder_ctx, value, expected
):
    result = elements.create_elements(
        builder_ctx["ctx"],
        builder_ctx["page"].id,
        [ElementItemCreate(ref="h", type="heading", value=value)],
    )

    assert "formula_errors" not in result
    assert saved(result["ref_to_id_map"]["h"]).value["formula"] == expected


@pytest.mark.django_db
def test_a_whole_function_call_on_a_table_column_is_a_formula(
    data_fixture, builder_ctx
):
    table = data_fixture.create_builder_table_element(
        page=builder_ctx["page"],
        data_source=builder_ctx["data_source"],
        fields=[{"name": "Shout", "type": "text", "config": {"value": "'a'"}}],
    )
    column = table.fields.get()

    elements.update_element(
        builder_ctx["ctx"],
        table.id,
        ElementEdits(
            update_table_columns=[
                TableColumnUpdate(uid=str(column.uid), value="upper('a')")
            ]
        ),
    )

    assert table.fields.get().config["value"]["formula"] == "upper('a')"
