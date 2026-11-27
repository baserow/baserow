import pytest
from genson import SchemaBuilder

from baserow.core.tools.formula_utils import create_example_from_json_schema


def test_example_of_a_declared_schema():
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "price": {"type": "number"},
            "seconds": {"type": "integer"},
            "active": {"type": "boolean"},
            "nothing": {"type": "null"},
            "owner": {"type": "object", "properties": {"id": {"type": "number"}}},
            "tags": {
                "type": "array",
                "items": {"type": "object", "properties": {"id": {"type": "number"}}},
            },
        },
    }

    assert create_example_from_json_schema(schema) == {
        "name": "1",
        "price": 1,
        "seconds": 1,
        "active": True,
        "nothing": None,
        "owner": {"id": 1},
        "tags": [{"id": 1}],
    }


def test_example_of_a_schema_inferred_from_sample_data():
    builder = SchemaBuilder()
    builder.add_object(
        [
            {
                "Active": True,
                "Email": "anna@example.com",
                "Hotel": [{"id": 1, "value": "Grand", "order": "1.00"}],
                "Nights": 3,
                "Notes": None,
                "Labels": ["vip"],
                "Extras": [],
                "Owner": {"id": 7},
                "Rooms": [{"number": 12}],
            },
            {
                "Active": False,
                "Email": None,
                "Hotel": [],
                "Nights": 2.5,
                "Notes": None,
                "Labels": [],
                "Extras": [],
                "Owner": None,
                "Rooms": None,
            },
        ]
    )

    assert create_example_from_json_schema(builder.to_schema()) == [
        {
            "Active": True,
            "Email": "1",
            "Hotel": [{"id": 1, "value": "1", "order": "1"}],
            "Nights": 1,
            "Notes": None,
            "Labels": ["1"],
            "Extras": [],
            # Null in one row and filled in another: the filled shape is kept.
            "Owner": {"id": 1},
            "Rooms": [{"number": 1}],
        }
    ]


@pytest.mark.parametrize(
    "prop",
    [
        # No type, like the body of a response that can be anything.
        {"title": "Body"},
        # What a Local Baserow field with no JSON type has, like a button.
        {"type": None},
        {"type": "unknown"},
        {"anyOf": [{"type": "null"}]},
    ],
)
def test_example_of_a_property_without_a_known_type_is_empty(prop):
    schema = {"type": "object", "properties": {"body": prop}}

    assert create_example_from_json_schema(schema) == {"body": None}


def test_example_of_an_array_without_items_is_empty():
    assert create_example_from_json_schema({"type": "array"}) == []


@pytest.mark.parametrize("schema", [{}, {"type": "string"}, {"type": "integer"}])
def test_example_needs_an_object_or_an_array(schema):
    with pytest.raises(ValueError):
        create_example_from_json_schema(schema)
