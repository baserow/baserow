from typing import Any, Dict, List, TypedDict

from django.db.models import QuerySet

from baserow.core.graph.types import SerializedGraph


class ElementToMigrate(TypedDict):
    id: int
    order: str  # e.g. "1.00000000000000000000"
    parent_element_id: int | None


class PageGraphMigrator:
    def __init__(self, elements: List[ElementToMigrate]):
        self.elements = elements

    @classmethod
    def serialize_page_elements(
        cls,
        elements: QuerySet,
    ) -> List[ElementToMigrate]:
        return [
            ElementToMigrate(
                id=element.id,
                order=element.order,
                parent_element_id=element.parent_element_id,
            )
            for element in elements
        ]

    def migrate_element(self, graph: Dict[str, Any], element: ElementToMigrate):
        graph_element = {}

        # Find any children this element has.
        children = [e for e in self.elements if e["parent_element_id"] == element["id"]]
        if children:
            graph_element["children"] = []
            sorted_children = sorted(children, key=lambda c: c["order"])
            for child in sorted_children:
                graph[str(child["id"])] = {}
                graph_element["children"].append(child["id"])

        # Find the next element based on the `order`.
        next_element = next(
            (
                e
                for e in self.elements
                if e["order"] > element["order"]
                and e["parent_element_id"] == element["parent_element_id"]
            ),
            None,
        )
        if next_element:
            graph_element["next"] = {"": [next_element["id"]]}

        graph[str(element["id"])] = graph_element
        return graph

    def to_graph(self) -> SerializedGraph:
        graph = {}
        root_page_elements = [
            e for e in self.elements if e["parent_element_id"] is None
        ]
        for index, root_page_element in enumerate(root_page_elements):
            if index == 0:
                graph["0"] = str(root_page_element["id"])
            graph = self.migrate_element(graph, root_page_element)
        return graph
