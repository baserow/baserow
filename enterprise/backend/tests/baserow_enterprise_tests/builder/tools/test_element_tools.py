"""
The shared element tools store the formulas they are given and report the rest,
without a model. The conftest of this folder fails any model call.
"""

import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.builder.elements.exceptions import ElementDoesNotExist
from baserow.contrib.builder.elements.models import Element, TableElement
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
    ElementChanges,
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
from baserow_enterprise.builder.tools.types.menu_items import MenuItemAdd


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
def test_a_header_form_can_read_its_own_inputs(data_fixture, builder_ctx):
    ctx, builder = builder_ctx["ctx"], builder_ctx["builder"]
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

    assert "formula_errors" not in result
    echo = saved(result["ref_to_id_map"]["echo"])
    assert echo.page == builder.shared_page
    assert echo.value["formula"] == f"get('form_data.{created['in']}')"


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
            "formula": "the name of the product",
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
        (table.id, "fields.1.value", "the price"),
        (table.id, "fields.2.label", "the action"),
    ]


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
    changes = ElementChanges(column_amount=3)

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
            ElementChanges(navigate_to_page_id=away),
        )
    with pytest.raises(ToolInputError):
        elements.update_element(
            ctx,
            created["menu"],
            ElementChanges(add_menu_items=[MenuItemAdd(name="Away", page_id=away)]),
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


@pytest.mark.django_db
def test_a_denied_move_stops_the_call(builder_ctx, monkeypatch):
    def deny(*args, **kwargs):
        raise PermissionException()

    monkeypatch.setattr(helpers, "move_element", deny)

    with pytest.raises(PermissionException):
        elements.move_elements(
            builder_ctx["ctx"], [ElementMove(element_id=builder_ctx["button"].id)]
        )


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
        ElementChanges(value="get('page_parameter.id')", level=2),
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
        ElementChanges(value="$formula: a new title", level=3),
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
        ElementChanges(navigation_type="custom", navigate_to_url="$formula: a url"),
    )
    assert described["formula_errors"][0]["field"] == "navigate_to_url"
    assert saved(element.id).navigation_type == "page"

    stored = elements.update_element(
        ctx,
        element.id,
        ElementChanges(navigation_type="custom", navigate_to_url="get('user.email')"),
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
        ElementChanges(
            add_table_columns=[
                TableColumnAdd(name="Id", value="get('current_record.id')")
            ]
        ),
    )
    uid = table["updated_element"]["table_columns"][0]["uid"]
    renamed = elements.update_element(
        ctx,
        created["t"],
        ElementChanges(
            update_table_columns=[TableColumnUpdate(uid=uid, name="Renamed")]
        ),
    )
    menu = elements.update_element(
        ctx,
        created["menu"],
        ElementChanges(add_menu_items=[MenuItemAdd(name="Home", page_id=page.id)]),
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
        ElementChanges(add_menu_items=[MenuItemAdd(name="Home", page_id=page.id)]),
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
            ElementChanges(column_amount=3, value="New"),
        )

    assert saved(element.id).value["formula"] == "'Old'"


def test_a_column_named_like_a_field_does_not_beat_a_formula_by_default():
    assert ElementItemCreate(ref="t", type="table")._column_name_beats_formula is False


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
        builder_ctx["ctx"], save_button.id, ElementChanges(label="All done!")
    )

    save_button.refresh_from_db()
    action.refresh_from_db()
    assert save_button.value["formula"] == "'All done!'"
    assert action.title["formula"] == "'Saved'"
    assert "update_action" in result["note"]
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
        builder_ctx["ctx"], save_button.id, ElementChanges(value="Store")
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
        builder_ctx["ctx"], save_button.id, ElementChanges(visibility="logged-in")
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
            ElementChanges(add_table_columns=[TableColumnAdd(name="Bad", value=value)]),
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
        ElementChanges(update_table_columns=[TableColumnUpdate(uid=uid, value=good)]),
    )
    with pytest.raises(ToolInputError, match="current_record.Name"):
        elements.update_element(
            ctx,
            table.id,
            ElementChanges(
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
            ElementChanges(
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
        ElementChanges(update_table_columns=[TableColumnUpdate(uid=uid, name="Old")]),
    )
    result = elements.update_element(
        ctx,
        table.id,
        ElementChanges(
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
        builder_ctx["ctx"], selector.id, ElementChanges(default_value=formula)
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
        ElementChanges(default_value=f"get('current_record.field_{own_field.id}')"),
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


@pytest.mark.django_db
def test_moving_the_last_child_into_its_container_changes_nothing(builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    ids = elements.create_elements(
        ctx,
        page.id,
        [
            ElementItemCreate(ref="box", type="simple_container"),
            text("a", "First", parent_element="box"),
            text("b", "Second", parent_element="box"),
        ],
    )["ref_to_id_map"]

    result = elements.move_elements(
        ctx, [ElementMove(element_id=ids["b"], parent_element_id=ids["box"])]
    )

    assert not result.get("errors")
    assert children_of(ids["box"]) == ["'First'", "'Second'"]


@pytest.mark.django_db
def test_moving_a_child_to_the_end_of_its_container(builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    ids = elements.create_elements(
        ctx,
        page.id,
        [
            ElementItemCreate(ref="box", type="simple_container"),
            text("a", "First", parent_element="box"),
            text("b", "Second", parent_element="box"),
        ],
    )["ref_to_id_map"]

    elements.move_elements(
        ctx, [ElementMove(element_id=ids["a"], parent_element_id=ids["box"])]
    )

    assert children_of(ids["box"]) == ["'Second'", "'First'"]


@pytest.mark.django_db
def test_moving_into_a_container_before_one_of_its_children(data_fixture, builder_ctx):
    ctx, page = builder_ctx["ctx"], builder_ctx["page"]
    ids = elements.create_elements(
        ctx,
        page.id,
        [
            ElementItemCreate(ref="box", type="simple_container"),
            text("a", "First", parent_element="box"),
            text("b", "Second", parent_element="box"),
        ],
    )["ref_to_id_map"]
    middle = data_fixture.create_builder_heading_element(page=page, value="'Middle'")

    result = elements.move_elements(
        ctx,
        [
            ElementMove(
                element_id=middle.id, parent_element_id=ids["box"], before_id=ids["b"]
            )
        ],
    )

    assert not result.get("errors")
    assert children_of(ids["box"]) == ["'First'", "'Middle'", "'Second'"]
