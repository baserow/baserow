from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, List

from django.db import transaction

from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.pages.models import Page
from baserow.core.graph.handler import BaseGraphHandler
from baserow.core.graph.types import GraphPointPosition


@dataclass(frozen=True)
class GraphDrift:
    """
    The divergence between a page's graph and the element rows that actually
    exist, as computed by `PageHealingHandler`. Each field holds the ids (or
    id pairs) for one corruption class; `has_drift` is True when any of them is
    non-empty, i.e. there is something to reconcile.
    """

    # Rows present in the DB but absent from the graph.
    orphan_ids: set
    # Ids referenced by the graph whose row no longer exists.
    stale_ids: set
    # Points listing themselves as their own next/child.
    self_ref_ids: set
    # References to points with no serialized graph entry.
    dangling_ids: set
    # (from_id, target_id) references that close a cycle.
    cycle_ref_pairs: set
    # (from_id, target_id) surplus references converging on one point.
    converging_ref_pairs: set
    # (element_id, edge) children edges the element cannot have.
    invalid_children_pairs: set
    # Live points keyed in the graph but unreachable from the root.
    detached_ids: set

    @property
    def has_drift(self) -> bool:
        return any(
            (
                self.orphan_ids,
                self.stale_ids,
                self.self_ref_ids,
                self.dangling_ids,
                self.cycle_ref_pairs,
                self.converging_ref_pairs,
                self.invalid_children_pairs,
                self.detached_ids,
            )
        )


class PageHealingHandler:
    """
    Owns the reconciliation of a page's graph with the element rows that
    actually exist — every corruption class `heal_corrupted_graph` repairs
    (orphans, stale points, self-references, dangling references, cycles,
    converging references, invalid children edges and detached points) and its
    Sentry reporting.

    Kept separate from `PageHandler` and `ElementHandler` so the day-to-day
    CRUD surfaces stay readable; `PageHandler.heal_corrupted_graph` is the
    single entry point and delegates here. The regression suite for every corruption class
    lives in `test_graph_regressions.py`.
    """

    def __init__(self):
        # Imported here so pages doesn't import the elements handler at module
        # load; the heal needs it to resolve element rows/types and to
        # invalidate the element cache after a repair.
        from baserow.contrib.builder.elements.handler import ElementHandler

        self.element_handler = ElementHandler()

    def find_invalid_children_edge_pairs(
        self, page: Page, graph: Dict[str, Any]
    ) -> set[tuple[int, str]]:
        """
        Return every `(element_id, edge)` children edge that the element cannot
        actually have: any children edge on a non-container element, and any
        edge that is not among a container's current places (e.g. children
        left under column "2" after the column element shrank to two columns
        by a write that raced the shrink). Such elements are reachable and the
        graph looks consistent, so no other detector flags them — but the UI
        never renders those places, leaving the children invisible.

        Graph-side detection is a pure in-memory scan; element rows are only
        resolved (via the request-cached `get_elements`) when at least one
        children edge exists.

        :param page: The page the graph belongs to.
        :param graph: The serialized graph to scan.
        :return: The set of invalid `(element_id, edge)` pairs.
        """

        root_key = BaseGraphHandler.GRAPH_ROOT_KEY
        edge_pairs = {
            (int(key), str(edge))
            for key, info in graph.items()
            if key != root_key and isinstance(info, dict)
            for edge in BaseGraphHandler._get_children_dict_from_info(info)
        }
        if not edge_pairs:
            return set()

        element_map = {
            element.id: element for element in self.element_handler.get_elements(page)
        }

        invalid: set[tuple[int, str]] = set()
        for element_id, edge in edge_pairs:
            element = element_map.get(element_id)
            if element is None:
                # A stale point — prune_points' responsibility.
                continue
            element_type = element.get_type()
            if not element_type.is_container:
                invalid.add((element_id, edge))
            elif edge not in {str(place) for place in element_type.get_places(element)}:
                invalid.add((element_id, edge))
        return invalid

    def _repair_invalid_children_edges(
        self, page: Page, graph_handler: BaseGraphHandler
    ) -> set[tuple[int, str]]:
        """
        Repair the invalid children edges found by
        `find_invalid_children_edge_pairs`: children under an unknown place of
        a container are merged into a surviving place (keeping their order and
        visibility), and children edges on non-containers are stripped — their
        subtrees become unreachable and are picked up by the reattachment pass
        that follows in the heal.

        :param page: The page being healed.
        :param graph_handler: The page's (locked) graph handler.
        :return: The pairs that were repaired.
        """

        repaired = self.find_invalid_children_edge_pairs(page, graph_handler.graph)
        if not repaired:
            return set()

        element_map = {
            element.id: element for element in self.element_handler.get_elements(page)
        }
        edges_by_element: Dict[int, List[str]] = defaultdict(list)
        for element_id, edge in repaired:
            edges_by_element[element_id].append(edge)

        for element_id, edges in edges_by_element.items():
            element = element_map[element_id]
            element_type = element.get_type()
            valid_places = (
                [str(place) for place in element_type.get_places(element)]
                if element_type.is_container
                else []
            )
            if not valid_places:
                graph_handler.strip_children_edges(element, sorted(edges))
                continue

            # Prefer the type's own fallback (e.g. the last surviving column),
            # clamped to a place that actually exists.
            try:
                fallback = str(
                    element_type.get_new_place_in_container(element, sorted(edges))
                )
            except (TypeError, ValueError):
                fallback = None
            if fallback not in valid_places:
                fallback = valid_places[-1]
            graph_handler.merge_children_into_place(element, sorted(edges), fallback)

        return repaired

    def heal_corrupted_graph(self, page: Page) -> Dict[str, Any]:
        """
        Reconcile `page.graph` with the elements that actually exist in the
        database, repairing drift that can appear during a non-zero-downtime deploy
        when older code mutates element rows without touching the graph. Keeping the
        graph the single source of truth means downstream operations (move, delete,
        …) never have to special-case a missing or dangling graph entry.

        Eight kinds of inconsistency are reconciled:

        - "orphans": rows present in the DB but absent from the graph (e.g. created
          by old code). They are inserted where a newly added element would land:

          - Unshared page: appended to the end of the page's root chain.
          - Shared page: appended to the end of the first shared element (the
            Header/Footer container at the root of the shared page).

        - "stale points": ids still referenced by the graph whose row no longer
          exists (e.g. hard-deleted by old code). They are spliced out via
          `prune_points` so a traversal can never resolve a missing point (which
          would otherwise raise and 500 the editor's element list).

        - "self-references": points listing themselves as their own `next` or
          child — an invariant violation that would otherwise only be healed
          when a chain traversal happens to walk that subtree. The corrupted
          self-edges are stripped via `strip_self_references`; detection is a
          pure in-memory scan, so the steady-state fast path stays as cheap as
          before (one id-list query, no lock, no writes).

        - "dangling references": ids listed in `next` or `children` which have
          no corresponding point entry in the graph. They are simply dropped
          via `strip_dangling_references`.

        - "cycle references": `next`/`children` references that point back at a
          point already on the traversal path leading to them, making an
          element its own transitive successor or ancestor (e.g. a container's
          child chain looping back onto the container's predecessor). Ancestry
          resolution on such a graph returns cyclic parents, which would send
          unguarded `parent_element_id` walks (import context, ancestor
          lookups) into infinite loops. The cycle-closing references are
          stripped via `strip_cycle_references`; detection is a pure in-memory
          scan, so the steady-state fast path stays as cheap as before.

        - "converging references": points with more than one incoming
          `next`/`children` reference (two chains "merged" onto one point —
          the aftermath left behind by pre-guard double inserts). Splices only
          ever resolve one predecessor, so the surplus reference survives and
          compounds with every subsequent operation, and the write guards
          fail-closed on such points (`insert` rejects a point that is still
          referenced). The surplus references are stripped via
          `strip_converging_references`, keeping the root-reachable canonical
          reference per point; any subtree detached by the strip is
          re-attached by the reattachment pass below.

        - "invalid children edges": children stored under a place their
          element cannot have — any children edge on a non-container, or an
          edge outside a container's current places (e.g. written by a
          pre-guard operation that raced a column-shrink). The graph stays
          reachable and consistent, so only this element-type-aware check can
          find them; children of unknown container places are merged into a
          surviving place, non-container children edges are stripped and
          their subtrees re-attached.

        - "detached points": live elements keyed in the graph but unreachable
          from the root (no incoming reference) — invisible in the editor and
          undeletable (`get_position` raises). They are re-attached at the
          bottom of the graph via `reattach_unreachable_points` so they become
          the last element(s) of the page (or of the shared container's
          default slot on a shared page). Detection is also a pure in-memory
          scan.

        :param page: The page whose graph should be reconciled.
        :return: A graph "patch" — the top-level graph entries that changed, keyed by
            point id, each holding its full new value. Empty when nothing changed.
            Because the graph is a flat dict, a client can apply it with a shallow
            merge (`{...graph, ...patch}`). Note a pruned stale key is not in the
            patch (a shallow merge can't express a deletion), but its now-relinked
            predecessor is, so the stale key is left unreferenced — harmless, and the
            client drops it on the next full graph sync.
        """

        root_key = page.get_graph().GRAPH_ROOT_KEY

        def compute_drift(graph) -> GraphDrift:
            graph_ids = {int(k) for k in graph if k != root_key}
            db_ids = set(Element.objects.filter(page=page).values_list("id", flat=True))
            # All but the invalid-children-edge check are pure in-memory scans;
            # that one resolves element rows through the request-cached
            # get_elements, which this request loads anyway.
            return GraphDrift(
                orphan_ids=db_ids - graph_ids,
                stale_ids=graph_ids - db_ids,
                self_ref_ids=BaseGraphHandler.find_self_referencing_point_ids(graph),
                dangling_ids=BaseGraphHandler.find_dangling_reference_ids(graph),
                cycle_ref_pairs=BaseGraphHandler.find_cycle_reference_pairs(graph),
                converging_ref_pairs=BaseGraphHandler.find_converging_reference_pairs(
                    graph
                ),
                invalid_children_pairs=self.find_invalid_children_edge_pairs(
                    page, graph
                ),
                detached_ids=BaseGraphHandler.find_unreachable_point_ids(graph)
                & db_ids,
            )

        # Fast path: nothing to reconcile (the steady state). Avoid locking/writes.
        if not compute_drift(page.get_graph().graph).has_drift:
            return {}

        # Re-check under a row lock so concurrent reads can't race on the same graph.
        with transaction.atomic():
            graph_handler = page.get_graph()
            # Take the row lock and refresh the in-memory graph from the locked
            # row, so the re-check and every repair below run against the latest
            # committed state. get_graph() returns the request-cached handler
            # (seeded by the unlocked fast-path read above), so its graph must
            # be refreshed in place rather than trusted as-is.
            graph_handler.lock_for_update()
            drift = compute_drift(graph_handler.graph)
            if not drift.has_drift:
                return {}

            # Snapshot before mutating so we can return only what changed.
            before = deepcopy(graph_handler.graph)

            # Strip self-references first: a point that is its own next/child
            # violates the graph invariant and would otherwise stay corrupted
            # until a chain traversal happens to walk (and heal) that subtree.
            if drift.self_ref_ids:
                graph_handler.strip_self_references()

            # Drop references which cannot be traversed because the referenced
            # point has no serialized graph entry.
            if drift.dangling_ids:
                graph_handler.strip_dangling_references()

            # Break cycles by stripping the references that close them, so
            # that ancestry resolution can no longer make an element its own
            # transitive parent. Re-detected internally: stripping self
            # references above may already have broken some of the cycles
            # detected at drift time.
            if drift.cycle_ref_pairs:
                graph_handler.strip_cycle_references()

            # Strip surplus converging references (after the cycle pass, whose
            # back-edges are also surplus incoming references and are usually
            # gone by now), leaving each element a single canonical incoming
            # position so the fail-closed write guards accept it again.
            if drift.converging_ref_pairs:
                graph_handler.strip_converging_references()

            # Prune stale points next so orphan placement (which traverses the
            # graph, e.g. append → get_last_position) can't walk into a missing
            # point part-way through.
            if drift.stale_ids:
                graph_handler.prune_points(drift.stale_ids)

            # Repair children stored under a place their element cannot have:
            # merge them into a surviving place (containers) or strip the edge
            # (non-containers) so the reattach pass below rescues the subtree.
            # Re-detected internally: the strips above may have changed the
            # graph since drift time.
            if drift.invalid_children_pairs:
                self.element_handler.invalidate_element_cache(page)
                self._repair_invalid_children_edges(page, graph_handler)

            # On a shared page, append orphans to the first shared element (the root
            # Header/Footer container); otherwise append to the end of the page.
            container = None
            if page.shared:
                root_id = graph_handler.graph.get(root_key)
                container = (
                    graph_handler.get_point(root_id) if root_id is not None else None
                )

            # Re-attach detached subtrees (live elements keyed in the graph but
            # unreachable from the root — invisible and undeletable ghosts) at
            # the bottom of the graph, before appending orphans. Run even when
            # detached_ids was empty at detection time: pruning a stale
            # container above can itself leave live children detached, and this
            # is a no-op in-memory scan when there is nothing to re-attach.
            reattached_ids = graph_handler.reattach_unreachable_points(
                container=container
            )

            for orphan in Element.objects.filter(id__in=drift.orphan_ids).order_by(
                "id"
            ):
                if container is not None:
                    graph_handler.insert(
                        orphan, container, GraphPointPosition.CHILD, ""
                    )
                else:
                    graph_handler.append(orphan)

            after = graph_handler.graph
            patch = {k: v for k, v in after.items() if before.get(k) != v}

        # The graph was refreshed and mutated in place on `page` under the lock
        # above; just drop any cached elements so the reload sees the repaired graph.
        self.element_handler.invalidate_element_cache(page)

        self._report_graph_heal(page, drift, set(reattached_ids), patch)

        return patch

    def _report_graph_heal(
        self,
        page: Page,
        drift: GraphDrift,
        reattached_ids: set,
        graph_patch: Dict[str, Any],
    ) -> None:
        """
        Surface a graph reconciliation in Sentry so we know it happened. Drift means
        the page graph diverged from the DB — typically element rows written or
        hard-deleted by older code during a non-zero-downtime deploy — and has now
        been repaired. Reported at "warning" level (it signals an upstream
        inconsistency, even though it's self-corrected), with the counts, ids and
        the applied patch.
        """

        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            scope.set_context(
                "graph_heal",
                {
                    "page_id": page.id,
                    "builder_id": page.builder_id,
                    "shared": page.shared,
                    "healed_element_count": len(drift.orphan_ids),
                    "healed_element_ids": sorted(drift.orphan_ids),
                    "pruned_stale_count": len(drift.stale_ids),
                    "pruned_stale_ids": sorted(drift.stale_ids),
                    "stripped_self_reference_count": len(drift.self_ref_ids),
                    "stripped_self_reference_ids": sorted(drift.self_ref_ids),
                    "stripped_dangling_reference_count": len(drift.dangling_ids),
                    "stripped_dangling_reference_ids": sorted(drift.dangling_ids),
                    "stripped_cycle_reference_count": len(drift.cycle_ref_pairs),
                    "stripped_cycle_reference_pairs": sorted(drift.cycle_ref_pairs),
                    "stripped_converging_reference_count": len(
                        drift.converging_ref_pairs
                    ),
                    "stripped_converging_reference_pairs": sorted(
                        drift.converging_ref_pairs
                    ),
                    "repaired_invalid_children_edge_count": len(
                        drift.invalid_children_pairs
                    ),
                    "repaired_invalid_children_edges": sorted(
                        drift.invalid_children_pairs
                    ),
                    "reattached_detached_count": len(reattached_ids),
                    "reattached_detached_ids": sorted(reattached_ids),
                    "graph_patch": graph_patch,
                },
            )
            sentry_sdk.capture_message(
                f"Healed {len(drift.orphan_ids)} orphan element(s), pruned "
                f"{len(drift.stale_ids)} stale point(s), stripped "
                f"{len(drift.self_ref_ids)} self-reference(s), stripped "
                f"{len(drift.dangling_ids)} dangling reference(s), stripped "
                f"{len(drift.cycle_ref_pairs)} cycle reference(s), stripped "
                f"{len(drift.converging_ref_pairs)} converging reference(s), repaired "
                f"{len(drift.invalid_children_pairs)} invalid children edge(s) and "
                f"re-attached {len(reattached_ids)} detached point(s) in the graph "
                f"of builder page {page.id}.",
                level="warning",
            )
