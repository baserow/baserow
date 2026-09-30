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
        a dangling reference, and so is one that would close a loop (two
        outputs sharing a head, an element referencing itself, a chain leading
        back into what was already folded), like the converging and cycle
        strips would. The graph is persisted when anything was merged.

        :return: The `(element_id, output)` pairs that were merged.
        """

        self._lock_instance_for_update()

        merged: List[tuple[int, str]] = []
        # Every element whose outputs were folded plus every id the fold has
        # placed on a default chain so far. A stray reference leading back into
        # them would close a loop, so it is dropped instead.
        placed_ids: set[str] = set()
        for point_id in sorted(
            {pid for pid, _ in self.find_non_default_next_edge_pairs(self.graph)}
        ):
            point_key = str(point_id)
            placed_ids.add(point_key)
            next_dict = self.graph[point_key]["next"]
            insert_after = point_key
            for output in sorted(o for o in next_dict if o != ""):
                merged.append((point_id, output))
                for head in next_dict.pop(output):
                    if str(head) not in self.graph:
                        continue
                    chain = self._walk_chain_ids(head, set())
                    if placed_ids.intersection(chain):
                        continue
                    placed_ids.update(chain)
                    # The walk follows `next` ids whether or not they are keyed
                    # (an exported orphan can be referenced without having an
                    # entry). Only a keyed point can carry the successors, so
                    # the last keyed one is the tail and its reference to the
                    # unkeyed rest is dropped, like a dangling reference.
                    tail = [cid for cid in chain if cid in self.graph][-1]
                    tail_next = self.graph[tail].setdefault("next", {})
                    tail_next[""] = [
                        nid for nid in tail_next.get("", []) if str(nid) in self.graph
                    ]
                    after_next = self.graph[insert_after].setdefault("next", {})
                    # Keep the previous default successors after the merged
                    # chain, minus anything already in it (a converging ref).
                    successors = [
                        nid for nid in after_next.get("", []) if str(nid) not in chain
                    ]
                    after_next[""] = [head]
                    if successors:
                        tail_next[""] = successors
                    elif not tail_next[""]:
                        del tail_next[""]
                    if not tail_next:
                        del self.graph[tail]["next"]
                    insert_after = tail
            if not next_dict:
                del self.graph[point_key]["next"]

        if merged:
            self._update_graph()

        return merged
