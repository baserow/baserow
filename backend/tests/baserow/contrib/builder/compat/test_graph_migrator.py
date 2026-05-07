from baserow.contrib.builder.compat.graph_migrator import (
    ElementToMigrate,
    PageGraphMigrator,
)


def test_migrate_to_graph_string_orders_sort_numerically():
    elements = [
        ElementToMigrate(
            id=1,
            parent_element_id=None,
            order="1.00000000000000000000",
            place_in_container="",
        ),
        ElementToMigrate(
            id=2,
            parent_element_id=None,
            order="9.00000000000000000000",
            place_in_container="",
        ),
        ElementToMigrate(
            id=3,
            parent_element_id=None,
            order="10.00000000000000000000",
            place_in_container="",
        ),
    ]
    migrator = PageGraphMigrator(elements)
    assert migrator.to_graph() == {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"next": {"": [3]}},
        "3": {},
    }


def test_migrate_to_graph():
    """
    - element1
        - element2 (child1, default place)
        - element3 (child2, default place)
    - element4
    """

    elements = [
        ElementToMigrate(
            id=1,
            parent_element_id=None,
            order="1.00000000000000000000",
            place_in_container="",
        ),
        ElementToMigrate(
            id=2,
            parent_element_id=1,
            order="1.00000000000000000000",
            place_in_container="",
        ),
        ElementToMigrate(
            id=3,
            parent_element_id=1,
            order="2.00000000000000000000",
            place_in_container="",
        ),
        ElementToMigrate(
            id=4,
            parent_element_id=None,
            order="2.00000000000000000000",
            place_in_container="",
        ),
    ]
    migrator = PageGraphMigrator(elements)
    assert migrator.to_graph() == {
        "0": 1,
        "1": {"next": {"": [4]}, "children": {"": [2, 3]}},
        "2": {"next": {"": [3]}},  # element 2 is followed by element 3 (same place)
        "3": {},
        "4": {},
    }


def test_migrate_to_graph_with_places():
    """
    - element1 (container with places)
        - element2 (child in place "0")
        - element3 (child in place "1")
        - element4 (child in place "1", after element3)
    - element5
    """

    elements = [
        ElementToMigrate(
            id=1,
            parent_element_id=None,
            order="1.00000000000000000000",
            place_in_container="",
        ),
        ElementToMigrate(
            id=2,
            parent_element_id=1,
            order="1.00000000000000000000",
            place_in_container="0",
        ),
        ElementToMigrate(
            id=3,
            parent_element_id=1,
            order="1.00000000000000000000",
            place_in_container="1",
        ),
        ElementToMigrate(
            id=4,
            parent_element_id=1,
            order="2.00000000000000000000",
            place_in_container="1",
        ),
        ElementToMigrate(
            id=5,
            parent_element_id=None,
            order="2.00000000000000000000",
            place_in_container="",
        ),
    ]
    migrator = PageGraphMigrator(elements)
    assert migrator.to_graph() == {
        "0": 1,
        "1": {
            "next": {"": [5]},
            "children": {
                "0": [2],
                "1": [3, 4],
            },
        },
        "2": {},
        "3": {"next": {"": [4]}},
        "4": {},
        "5": {},
    }
