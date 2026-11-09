"""
The tool input models refuse names and paths the database columns can't hold, so
the client gets a validation error instead of 'Internal error.'.
"""

import pytest
from pydantic import ValidationError

from baserow_enterprise.builder.tools.types import (
    DataSourceCreate,
    DisplayElementCreate,
    ElementEdits,
    ElementItemCreate,
    LayoutElementCreate,
    PageChanges,
    PageCreate,
)
from baserow_enterprise.builder.tools.types.element import (
    MenuItemCreate,
    TableFieldConfig,
)
from baserow_enterprise.builder.tools.types.user_source import UserSourceSetup

LONG = "a" * 256


@pytest.mark.parametrize(
    "make",
    [
        lambda: PageCreate(name=LONG, path="/products"),
        lambda: PageCreate(name="Products", path="/" + LONG),
        lambda: PageCreate(name="   ", path="/products"),
        lambda: PageChanges(name=LONG),
        lambda: PageChanges(name=""),
        lambda: PageChanges(path="/" + LONG),
        lambda: UserSourceSetup(name=LONG, database_id=1),
        lambda: UserSourceSetup(name=" ", database_id=1),
        lambda: MenuItemCreate(name="a" * 226, page_id=1),
        lambda: MenuItemCreate(name=" ", page_id=1),
        lambda: TableFieldConfig(name="a" * 226),
        lambda: DataSourceCreate(ref="ds", name=LONG, type="list_rows", table_id=1),
    ],
)
def test_too_long_or_blank_names_are_refused(make):
    with pytest.raises(ValidationError):
        make()


@pytest.mark.parametrize(
    "model, values",
    [
        (DisplayElementCreate, {"type": "heading", "value": "x", "level": 0}),
        (DisplayElementCreate, {"type": "heading", "value": "x", "level": 99}),
        (DisplayElementCreate, {"type": "text", "value": "x", "format": "html"}),
        (LayoutElementCreate, {"type": "column", "column_amount": 500}),
        (LayoutElementCreate, {"type": "column", "column_amount": 0}),
        (ElementItemCreate, {"type": "column", "column_gap": -1}),
        (ElementItemCreate, {"type": "column", "column_gap": 2001}),
        (ElementItemCreate, {"type": "input_text", "rows": 0}),
        (ElementItemCreate, {"type": "input_text", "rows": 101}),
        (ElementItemCreate, {"type": "repeat", "items_per_page": -1}),
        (ElementItemCreate, {"type": "repeat", "items_per_page": 0}),
    ],
)
def test_an_element_value_the_rest_api_refuses_is_refused_on_create(model, values):
    with pytest.raises(ValidationError):
        model(ref="e", **values)


@pytest.mark.parametrize(
    "changes",
    [
        {"level": 7},
        {"format": "html"},
        {"column_amount": 7},
        {"column_gap": -1},
        {"rows": 101},
        {"items_per_page": -1},
        {"items_per_page": 0},
    ],
)
def test_an_element_value_the_rest_api_refuses_is_refused_on_update(changes):
    with pytest.raises(ValidationError):
        ElementEdits(**changes)


def test_names_within_the_bounds_are_kept():
    assert PageCreate(name="a" * 255, path="/products").name == "a" * 255
    assert UserSourceSetup(name=" Users ", database_id=1).name == "Users"
    assert MenuItemCreate(name="a" * 225, page_id=1).name == "a" * 225
    assert TableFieldConfig(name="a" * 225).name == "a" * 225
