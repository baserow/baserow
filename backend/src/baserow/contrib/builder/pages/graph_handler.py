from typing import Dict, List

from baserow.contrib.builder.elements.exceptions import ElementDoesNotExist
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import Element
from baserow.core.graph.handler import BaseGraphHandler
from baserow.core.graph.types import SerializedGraph


class PageGraphHandler(BaseGraphHandler):
    """
    The application builder page graph handler is responsible for managing
    the graph of a page.

    Unlike an automation workflow, a page never branches: every `next` edge
    uses the default `""` output. The helpers below detect and repair a graph
    that stores a chain under another output.
    """

    base_point_class = Element
    instance_id_mapping = "builder_page_elements"
    does_not_exist_exception = ElementDoesNotExist

    def get_point_map(self) -> Dict[int, Element]:
        return {e.id: e for e in ElementHandler().get_elements(self.instance)}

    @classmethod
    def find_non_default_next_edge_pairs(
        cls, graph: SerializedGraph | None
    ) -> set[tuple[int, str]]:
        """
        Return every `(element_id, output)` of a `next` edge stored under an
        output other than the default `""`. Such an edge was written when a
        `place_in_container` reached the graph with a `south`/`north` position;
        no page renderer follows it, so its elements exist but never show, and
        the graph otherwise looks healthy (the elements are reachable).

        :param graph: The serialized graph to scan.
        :return: The set of `(element_id, output)` pairs.
        """

        if not graph:
            return set()

        return {
            (int(key), str(output))
            for key, info in graph.items()
            if key != cls.GRAPH_ROOT_KEY and isinstance(info, dict)
            for output in info.get("next", {})
            if output != ""
        }

    def merge_non_default_next_edges(self) -> List[tuple[int, str]]:
        """
        Fold every `next` chain stored under a non-default output back into the
        default chain, right after the element that references it (where a
        `south` insert would have put it), followed by that element's previous
        default successors. The outputs of one element are merged in sorted
        order. A reference to an element without a graph entry is dropped, like
        a dangling reference. The graph is persisted when anything was merged.

        :return: The `(element_id, output)` pairs that were merged.
        """

        self._lock_instance_for_update()

        merged: List[tuple[int, str]] = []
        for point_id in sorted(
            {pid for pid, _ in self.find_non_default_next_edge_pairs(self.graph)}
        ):
            point_key = str(point_id)
            next_dict = self.graph[point_key]["next"]
            insert_after = point_key
            for output in sorted(o for o in next_dict if o != ""):
                merged.append((point_id, output))
                for head in next_dict.pop(output):
                    if str(head) not in self.graph:
                        continue
                    chain = self._walk_chain_ids(head, set())
                    after_next = self.graph[insert_after].setdefault("next", {})
                    # Keep the previous default successors after the merged
                    # chain, minus anything already in it (a converging ref).
                    successors = [
                        nid for nid in after_next.get("", []) if str(nid) not in chain
                    ]
                    after_next[""] = [head]
                    tail = chain[-1]
                    if successors:
                        self.graph[tail].setdefault("next", {})[""] = successors
                    insert_after = tail
            if not next_dict:
                del self.graph[point_key]["next"]

        if merged:
            self._update_graph()

        return merged
