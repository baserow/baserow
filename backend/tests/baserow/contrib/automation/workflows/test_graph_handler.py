from unittest.mock import MagicMock, patch

import pytest

from baserow.contrib.automation.workflows.graph_handler import (
    AutomationWorkflowGraphHandler,
)


class FakePoint:
    def __init__(self, nid):
        self.id = int(nid)

    def __eq__(self, other):
        if isinstance(other, int):
            return self.id == other
        else:
            return self.id == other.id

    def __str__(self):
        return f"Node {self.id}"

    def __repr__(self):
        return f"FakePoint({self.id})"

    def get_label(self):
        return str(self)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "reference_node_id, position, output ,expected_result",
    [
        (None, "south", "", "Node 1"),
        (1, "south", "", "Node 2"),
        (3, "south", "", "Node 4"),
        (3, "child", "", "Node 7"),
        (1, "child", "", None),
        (4, "south", "", "Node 5"),
        (4, "south", "randomUid", "Node 9"),
        (9, "south", "randomUid", None),
        (9, "south", "", None),
        (9, "child", "", "Node 10"),
    ],
)
@patch(
    "baserow.contrib.automation.workflows.graph_handler.AutomationWorkflowGraphHandler.get_point"
)
def test_graph_handler_get_point_at_position(
    mock_get_points, reference_node_id, position, output, expected_result
):
    workflow = MagicMock()
    workflow.graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"next": {"": [3]}},
        "3": {"children": [7], "next": {"": [4]}},
        "5": {"next": {"": [6]}},
        "4": {"next": {"": [5], "randomUid": [9]}},
        "6": {},
        "7": {"next": {"": [8]}},
        "8": {},
        "9": {"children": [10]},
        "10": {},
    }

    mock_get_points.side_effect = lambda n: f"Node {n}"

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    assert (
        graph_handler.get_point_at_position(reference_node_id, position, output)
        == expected_result
    )


@pytest.mark.django_db
@patch(
    "baserow.contrib.automation.workflows.graph_handler.AutomationWorkflowGraphHandler.get_point"
)
def test_graph_handler_get_point_at_position_empty_graph(mock_get_points):
    workflow = MagicMock()
    workflow.graph = {}

    mock_get_points.side_effect = lambda n: f"Node {n}"

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    assert graph_handler.get_point_at_position(None, "south", "") is None


@pytest.mark.django_db
@patch(
    "baserow.contrib.automation.workflows.graph_handler.AutomationWorkflowGraphHandler.get_point"
)
def test_graph_handler_get_last_position(mock_get_points):
    workflow = MagicMock()
    workflow.graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"next": {"": [3]}},
        "3": {"children": [7], "next": {"": [4]}},
        "5": {"next": {"": [6]}},
        "4": {"next": {"": [5], "randomUid": [9]}},
        "6": {},  # This is the last node
        "7": {"next": {"": [8]}},
        "8": {},
        "9": {"children": [10]},
        "10": {},
    }

    mock_get_points.side_effect = lambda n: f"Node {n}"

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    assert graph_handler.get_last_position() == (
        "Node 6",
        "south",
        "",
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "node_id,  expected_result",
    [
        (1, (None, "north", "")),
        (2, ("1", "south", "")),
        (3, ("2", "south", "")),
        (4, ("3", "south", "")),
        (5, ("4", "south", "")),
        (6, ("5", "south", "")),
        (7, ("3", "child", "")),
        (8, ("7", "south", "")),
        (9, ("4", "south", "randomUid")),
        (10, ("9", "child", "")),
    ],
)
@patch(
    "baserow.contrib.automation.workflows.graph_handler.AutomationWorkflowGraphHandler.get_point"
)
def test_graph_handler_get_position(mock_get_points, node_id, expected_result):
    workflow = MagicMock()
    workflow.graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"next": {"": [3]}},
        "3": {"children": [7], "next": {"": [4]}},
        "4": {"next": {"": [5], "randomUid": [9]}},
        "5": {"next": {"": [6]}},
        "6": {},
        "7": {"next": {"": [8]}},
        "8": {},
        "9": {"children": [10]},
        "10": {},
    }

    mock_get_points.side_effect = lambda n: f"Node {n}"

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    node = MagicMock()

    node.id = node_id

    assert graph_handler.get_position(node) == expected_result


@pytest.mark.django_db
@pytest.mark.parametrize(
    "node_id,  expected_result",
    [
        (1, []),
        (2, [(FakePoint(1), "south", "")]),
        (3, [(FakePoint(1), "south", ""), (FakePoint(2), "south", "")]),
        (
            6,
            [
                (FakePoint(1), "south", ""),
                (FakePoint(2), "south", ""),
                (FakePoint(3), "south", ""),
                (FakePoint(4), "south", ""),
                (FakePoint(5), "south", ""),
            ],
        ),
        (
            8,
            [
                (FakePoint(1), "south", ""),
                (FakePoint(2), "south", ""),
                (FakePoint(3), "child", ""),
                (FakePoint(7), "south", ""),
            ],
        ),
        (
            9,
            [
                (FakePoint(1), "south", ""),
                (FakePoint(2), "south", ""),
                (FakePoint(3), "south", ""),
                (FakePoint(4), "south", "randomUid"),
            ],
        ),
        (
            10,
            [
                (FakePoint(1), "south", ""),
                (FakePoint(2), "south", ""),
                (FakePoint(3), "south", ""),
                (FakePoint(4), "south", "randomUid"),
                (FakePoint(9), "child", ""),
            ],
        ),
        (11, None),
    ],
)
@patch(
    "baserow.contrib.automation.workflows.graph_handler.AutomationWorkflowGraphHandler.get_point"
)
def test_graph_handler_get_previous_position(mock_get_points, node_id, expected_result):
    workflow = MagicMock()
    workflow.graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"next": {"": [3]}},
        "3": {"children": [7], "next": {"": [4]}},
        "4": {"next": {"": [5], "randomUid": [9]}},
        "5": {"next": {"": [6]}},
        "6": {"next": {"": []}},
        "7": {"next": {"": [8]}},
        "8": {"children": []},
        "9": {"children": [10]},
        "10": {},
    }

    mock_get_points.side_effect = FakePoint

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    assert graph_handler.get_previous_positions(FakePoint(node_id)) == expected_result


@pytest.mark.django_db
@pytest.mark.parametrize(
    "node_id,  output, expected_result",
    [
        (1, "", [FakePoint(2)]),
        (2, "", [FakePoint(3)]),
        (4, None, [FakePoint(5), FakePoint(9)]),
        (4, "", [FakePoint(5)]),
        (4, "randomUid", [FakePoint(9)]),
        (4, "missing", []),
        (9, "", []),
        (10, "", []),
    ],
)
@patch(
    "baserow.contrib.automation.workflows.graph_handler.AutomationWorkflowGraphHandler.get_point"
)
def test_graph_handler_get_next_points(
    mock_get_points, node_id, output, expected_result
):
    workflow = MagicMock()
    workflow.graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"next": {"": [3]}},
        "3": {"children": [7], "next": {"": [4]}},
        "4": {"next": {"": [5], "randomUid": [9]}},
        "5": {"next": {"": [6]}},
        "6": {"next": {"": []}},
        "7": {"next": {"": [8]}},
        "8": {"children": []},
        "9": {"children": [10]},
        "10": {},
    }

    mock_get_points.side_effect = FakePoint

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    assert graph_handler.get_next_points(FakePoint(node_id), output) == expected_result


@pytest.mark.django_db
@pytest.mark.parametrize(
    "node_id, expected_result",
    [
        (1, []),
        (3, [FakePoint(7), FakePoint(8)]),
        (8, []),
        (9, [FakePoint(10)]),
        (10, []),
    ],
)
@patch(
    "baserow.contrib.automation.workflows.graph_handler.AutomationWorkflowGraphHandler.get_point"
)
def test_graph_handler_get_children(mock_get_points, node_id, expected_result):
    workflow = MagicMock()
    workflow.graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"next": {"": [3]}},
        "3": {"children": [7], "next": {"": [4]}},
        "4": {"next": {"": [5], "randomUid": [9]}},
        "5": {"next": {"": [6]}},
        "6": {"next": {"": []}},
        "7": {"next": {"": [8]}},
        "8": {"children": []},
        "9": {"children": [10]},
        "10": {},
    }

    mock_get_points.side_effect = FakePoint

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    assert graph_handler.get_children(FakePoint(node_id)) == expected_result


@pytest.mark.django_db
@pytest.mark.parametrize(
    "node_id, expected_result",
    [
        (1, []),
        (7, [FakePoint(8)]),
        (10, [FakePoint(11)]),
        (11, []),
    ],
)
@patch(
    "baserow.contrib.automation.workflows.graph_handler.AutomationWorkflowGraphHandler.get_point"
)
def test_graph_handler_get_siblings(mock_get_points, node_id, expected_result):
    workflow = MagicMock()
    workflow.graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"next": {"": [3]}},
        "3": {"children": [7], "next": {"": [4]}},
        "4": {"next": {"": [5], "randomUid": [9]}},
        "5": {"next": {"": [6]}},
        "6": {"next": {"": []}},
        "7": {"next": {"": [8]}},
        "8": {"children": []},
        "9": {"children": [10, 11]},
        "10": {},
        "11": {},
    }

    mock_get_points.side_effect = FakePoint

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    assert graph_handler.get_siblings(FakePoint(node_id)) == expected_result


@pytest.mark.django_db
@pytest.mark.parametrize(
    "node_id, reference_node_id, position, output, expected_result",
    [
        (
            11,
            1,
            "south",
            "",
            {
                "0": 1,
                "1": {"next": {"": [11]}},
                "11": {"next": {"": [2]}},
                "2": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
        (
            11,
            3,
            "south",
            "",
            {
                "0": 1,
                "1": {"next": {"": [2]}},
                "2": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [11]}},
                "11": {"next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
        (
            11,
            3,
            "child",
            "",
            {
                "0": 1,
                "1": {"next": {"": [2]}},
                "2": {"next": {"": [3]}},
                # The new child is prepended as the head of the slot; the previous
                # head (7) becomes its next.
                "3": {"children": {"": [11]}, "next": {"": [4]}},
                "11": {"next": {"": [7]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
        (
            11,
            7,
            "south",
            "",
            {
                "0": 1,
                "1": {"next": {"": [2]}},
                "2": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "7": {"next": {"": [11]}},
                "8": {"children": []},
                "9": {},
                "11": {"next": {"": [8]}},
            },
        ),
        (
            11,
            9,
            "south",
            "",
            {
                "0": 1,
                "1": {"next": {"": [2]}},
                "2": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {"next": {"": [11]}},
                "11": {},
            },
        ),
        (
            11,
            4,
            "south",
            "randomUid",
            {
                "0": 1,
                "1": {"next": {"": [2]}},
                "2": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [11]}},
                "11": {"next": {"": [9]}},
                "9": {},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
            },
        ),
        (
            11,
            None,
            "south",
            "",
            {
                "0": 11,
                "11": {"next": {"": [1]}},
                "1": {"next": {"": [2]}},
                "2": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
        # position="north" test cases
        # Insert north of the root node - new node becomes root
        (
            11,
            1,
            "north",
            "",
            {
                "0": 11,
                "11": {"next": {"": [1]}},
                "1": {"next": {"": [2]}},
                "2": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
        # Insert north of a middle node in the default output chain
        (
            11,
            3,
            "north",
            "",
            {
                "0": 1,
                "1": {"next": {"": [2]}},
                "2": {"next": {"": [11]}},
                "11": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
        # Insert north of a node on a non-default output (randomUid)
        (
            11,
            9,
            "north",
            "",
            {
                "0": 1,
                "1": {"next": {"": [2]}},
                "2": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [11]}},
                "11": {"next": {"": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
        # Insert north of a child node
        (
            11,
            7,
            "north",
            "",
            {
                "0": 1,
                "1": {"next": {"": [2]}},
                "2": {"next": {"": [3]}},
                "3": {"children": {"": [11]}, "next": {"": [4]}},
                "11": {"next": {"": [7]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
    ],
)
@patch(
    "baserow.contrib.automation.workflows.graph_handler.AutomationWorkflowGraphHandler.get_point"
)
def test_graph_handler_insert(
    mock_get_points,
    node_id,
    reference_node_id,
    position,
    output,
    expected_result,
):
    workflow = MagicMock()
    workflow.graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"next": {"": [3]}},
        "3": {"children": [7], "next": {"": [4]}},
        "4": {"next": {"": [5], "randomUid": [9]}},
        "7": {"next": {"": [8]}},
        "8": {"children": []},
        "9": {},
    }

    mock_get_points.side_effect = FakePoint

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    graph_handler.insert(
        FakePoint(node_id),
        FakePoint(reference_node_id) if reference_node_id is not None else None,
        position,
        output,
    )

    assert graph_handler.graph == expected_result


@pytest.mark.django_dbw
@patch(
    "baserow.contrib.automation.workflows.graph_handler.AutomationWorkflowGraphHandler.get_point"
)
def test_graph_handler_insert_first_node(
    mock_get_points,
):
    workflow = MagicMock()
    workflow.graph = {}

    mock_get_points.side_effect = FakePoint

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    graph_handler.insert(FakePoint(1), None, "south", "")

    assert graph_handler.graph == {"1": {}, "0": 1}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "node_id,  expected_result",
    [
        (
            1,
            {
                "0": 2,
                "2": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
        (
            2,
            {
                "0": 1,
                "1": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
        (
            3,
            {
                "0": 1,
                "1": {"next": {"": [2]}},
                "2": {"next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "9": {},
            },
        ),
        (
            4,
            {
                "0": 1,
                "1": {"next": {"": [2]}},
                "2": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [5, 9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
    ],
)
@patch(
    "baserow.contrib.automation.workflows.graph_handler.AutomationWorkflowGraphHandler.get_point"
)
def test_graph_handler_remove(
    mock_get_points,
    node_id,
    expected_result,
):
    workflow = MagicMock()
    workflow.graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"next": {"": [3]}},
        "3": {"children": [7], "next": {"": [4]}},
        "4": {"next": {"": [5], "randomUid": [9]}},
        "7": {"next": {"": [8]}},
        "8": {"children": []},
        "9": {},
    }

    mock_get_points.side_effect = FakePoint

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    graph_handler.remove(
        FakePoint(node_id),
    )

    assert graph_handler.graph == expected_result


@pytest.mark.django_db
@patch(
    "baserow.contrib.automation.workflows.graph_handler.AutomationWorkflowGraphHandler.get_point"
)
def test_graph_handler_remove_last_node(
    mock_get_points,
):
    workflow = MagicMock()
    workflow.graph = {
        "0": 1,
        "1": {"next": {"": []}},
    }

    mock_get_points.side_effect = FakePoint

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    graph_handler.remove(
        FakePoint(1),
    )

    assert graph_handler.graph == {}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "node_id, replace_id, expected_result",
    [
        (
            1,
            11,
            {
                "0": 11,
                "11": {"next": {"": [2]}},
                "2": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
        (
            3,
            11,
            {
                "0": 1,
                "1": {"next": {"": [2]}},
                "2": {"next": {"": [11]}},
                "11": {"children": [7], "next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
        (
            4,
            11,
            {
                "0": 1,
                "1": {"next": {"": [2]}},
                "2": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [11]}},
                "11": {"next": {"": [5], "randomUid": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
    ],
)
@patch(
    "baserow.contrib.automation.workflows.graph_handler.AutomationWorkflowGraphHandler.get_point"
)
def test_graph_handler_replace(
    mock_get_points,
    node_id,
    replace_id,
    expected_result,
):
    workflow = MagicMock()
    workflow.graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"next": {"": [3]}},
        "3": {"children": [7], "next": {"": [4]}},
        "4": {"next": {"": [5], "randomUid": [9]}},
        "7": {"next": {"": [8]}},
        "8": {"children": []},
        "9": {},
    }

    mock_get_points.side_effect = FakePoint

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    graph_handler.replace(FakePoint(node_id), FakePoint(replace_id))

    assert graph_handler.graph == expected_result


@pytest.mark.django_db
@pytest.mark.parametrize(
    "node_id, reference_node_id, position, output, expected_result",
    [
        (
            2,
            3,
            "south",
            "",
            {
                "0": 1,
                "1": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [2]}},
                "2": {"next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
        (
            2,
            3,
            "child",
            "",
            {
                "0": 1,
                "1": {"next": {"": [3]}},
                # Moved in as the head of node 3's child slot; the previous head (7)
                # becomes the moved node's next.
                "3": {"children": {"": [2]}, "next": {"": [4]}},
                "2": {"next": {"": [7]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
        (
            2,
            4,
            "south",
            "randomUid",
            {
                "0": 1,
                "1": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [2]}},
                "2": {"next": {"": [9]}},
                "7": {"next": {"": [8]}},
                "8": {"children": []},
                "9": {},
            },
        ),
        (
            7,
            3,
            "south",
            "randomUid",
            {
                "0": 1,
                "1": {"next": {"": [2]}},
                "2": {"next": {"": [3]}},
                "3": {"children": {"": [8]}, "next": {"": [4], "randomUid": [7]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "9": {},
                "7": {},
                "8": {"children": []},
            },
        ),
        (
            8,
            9,
            "south",
            "anotherUid",
            {
                "0": 1,
                "1": {"next": {"": [2]}},
                "2": {"next": {"": [3]}},
                "3": {"children": [7], "next": {"": [4]}},
                "4": {"next": {"": [5], "randomUid": [9]}},
                "7": {},
                "8": {"children": []},
                "9": {"next": {"anotherUid": [8]}},
            },
        ),
    ],
)
@patch(
    "baserow.contrib.automation.workflows.graph_handler.AutomationWorkflowGraphHandler.get_point"
)
def test_graph_handler_move(
    mock_get_points,
    node_id,
    reference_node_id,
    position,
    output,
    expected_result,
):
    workflow = MagicMock()
    workflow.graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"next": {"": [3]}},
        "3": {"children": [7], "next": {"": [4]}},
        "4": {"next": {"": [5], "randomUid": [9]}},
        "7": {"next": {"": [8]}},
        "8": {"children": []},
        "9": {},
    }

    mock_get_points.side_effect = FakePoint

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    graph_handler.move(
        FakePoint(node_id),
        FakePoint(reference_node_id) if reference_node_id is not None else None,
        position,
        output,
    )

    assert graph_handler.graph == expected_result


@pytest.mark.django_db
def test_graph_handler_migrate():
    workflow = MagicMock()
    workflow.graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"next": {"": [3]}},
        "3": {"children": [7], "next": {"": [4]}},
        "4": {"next": {"": [5], "randomUid": [9]}},
        "7": {"next": {"": [8]}},
        "8": {"children": []},
        "9": {},
    }

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    graph_handler.migrate_graph(
        {
            "automation_workflow_nodes": {
                1: 41,
                2: 42,
                3: 43,
                4: 44,
                5: 45,
                6: 46,
                7: 47,
                8: 48,
                9: 49,
            },
            "automation_edge_outputs": {"randomUid": "anotherRandomUid"},
        }
    )

    assert graph_handler.graph == {
        "0": 41,
        "41": {"next": {"": [42]}},
        "42": {"next": {"": [43]}},
        "43": {"next": {"": [44]}, "children": {"": [47]}},
        "44": {"next": {"": [45], "anotherRandomUid": [49]}},
        "47": {"next": {"": [48]}},
        "48": {"children": {"": []}},
        "49": {},
    }


@pytest.mark.django_db
def test_graph_handler_migrate_with_unmapped_points():
    # Regression: a corrupted export can reference points that were never
    # exported (e.g. a stale reference to a record hard-deleted before export).
    # Those ids have no entry in the id_mapping, which used to raise KeyError
    # and abort the whole import. Keyed stale entries must be pruned (splicing
    # their successors into the chain) and unkeyed dangling references dropped.
    workflow = MagicMock()
    workflow.graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {"next": {"": [3]}},
        "3": {"children": [7], "next": {"": [4]}},
        "4": {"next": {"": [5], "randomUid": [9]}},
        "7": {"next": {"": [8]}},
        "8": {"children": []},
        "9": {},
    }

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    # 2 (keyed) and 5 (referenced but unkeyed) have no imported counterpart.
    graph_handler.migrate_graph(
        {
            "automation_workflow_nodes": {1: 41, 3: 43, 4: 44, 7: 47, 8: 48, 9: 49},
            "automation_edge_outputs": {"randomUid": "anotherRandomUid"},
        }
    )

    assert graph_handler.graph == {
        "0": 41,
        # 2 was pruned and its successor spliced in: 1 -> 3.
        "41": {"next": {"": [43]}},
        "43": {"next": {"": [44]}, "children": {"": [47]}},
        # The dangling reference to 5 is dropped.
        "44": {"next": {"": [], "anotherRandomUid": [49]}},
        "47": {"next": {"": [48]}},
        "48": {"children": {"": []}},
        "49": {},
    }


@pytest.mark.django_db
def test_graph_handler_migrate_with_unmapped_root():
    # A root reference that is unkeyed and unmapped is dropped instead of
    # raising; the surviving points are re-attached by the heal on next load.
    workflow = MagicMock()
    workflow.graph = {"0": 99, "1": {}}

    graph_handler = AutomationWorkflowGraphHandler(workflow)

    graph_handler.migrate_graph(
        {"automation_workflow_nodes": {1: 41}, "automation_edge_outputs": {}}
    )

    assert graph_handler.graph == {"41": {}}
