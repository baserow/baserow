import pytest

from tests.baserow.core.graph.fixtures import make_graph_model


@pytest.fixture(scope="session", autouse=True)
def baserow_db_setup():
    """
    Override the global baserow_db_setup fixture so that graph handler tests,
    which are pure Python with no database involvement, don't trigger
    django_db_setup and race with other xdist workers on the migrations table.
    """
    pass


@pytest.fixture()
def graph_model_fixture():
    graph = {
        "0": 1,
        "1": {"next": {"": [2]}},
        "2": {
            "next": {
                "uuid1": [3],
                "uuid2": [5],
                "": [4],
            }
        },
        "3": {},
        "5": {"next": {"": [12]}},
        "4": {"next": {"": [6]}},
        "6": {"children": {"": [7], "0": [8], "1": [9]}},
        "7": {},
        "8": {},
        "9": {"next": {"": [10]}},
        "10": {"next": {"": [11]}},
        "11": {},
        "12": {},
    }
    return make_graph_model(graph)


@pytest.fixture()
def container_graph_fixture():
    """
    A graph with a root container (point 1) holding children in three places::

        place "0": 2 → 3
        place "1": 4
        place "2": 5 → 6
    """
    graph = {
        "0": 1,
        "1": {"children": {"0": [2], "1": [4], "2": [5]}},
        "2": {"next": {"": [3]}},
        "3": {},
        "4": {},
        "5": {"next": {"": [6]}},
        "6": {},
    }
    return make_graph_model(graph)
