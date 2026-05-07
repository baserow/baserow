from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, TypedDict

from django.db.models import QuerySet

from baserow.core.graph.types import SerializedGraph


class ElementToMigrate(TypedDict):
    id: int
    order: str  # e.g. "1.00000000000000000000"
    parent_element_id: int | None
    place_in_container: str | None


class PageGraphMigrator:
    def __init__(self, elements: List[ElementToMigrate]):
        # Normalize order to Decimal so both JSON strings ("10.00...") and
        # Decimal instances (from ORM .values()) sort and compare correctly.
        normalized = [{**e, "order": Decimal(str(e["order"]))} for e in elements]
        self.elements = sorted(normalized, key=lambda e: e["order"])

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
                place_in_container=getattr(element, "place_in_container", None) or "",
            )
            for element in elements
        ]

    def migrate_element(self, graph: Dict[str, Any], element: ElementToMigrate):
        graph_element = {}

        # Find any children this element has.
        children = [e for e in self.elements if e["parent_element_id"] == element["id"]]
        if children:
            # Group children by their place_in_container (edge key)
            children_by_place: Dict[str, List[ElementToMigrate]] = defaultdict(list)
            for child in children:
                place = child.get("place_in_container") or ""
                children_by_place[place].append(child)

            # Build the children dict with edges
            graph_element["children"] = {}
            for place, place_children in children_by_place.items():
                sorted_children = sorted(place_children, key=lambda c: c["order"])
                graph_element["children"][place] = []
                for child in sorted_children:
                    graph_element["children"][place].append(child["id"])
                    # Recursively migrate child elements
                    graph = self.migrate_element(graph, child)

        # Find the next element based on the `order`.
        # Next elements must have the same parent AND the same place_in_container
        next_element = next(
            (
                e
                for e in self.elements
                if e["order"] > element["order"]
                and e["parent_element_id"] == element["parent_element_id"]
                and (e.get("place_in_container") or "")
                == (element.get("place_in_container") or "")
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
                graph["0"] = root_page_element["id"]
            graph = self.migrate_element(graph, root_page_element)
        return graph
