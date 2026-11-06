import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Type, Union

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.storage import Storage
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from celery.canvas import Signature, chain, group
from loguru import logger
from opentelemetry import trace

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.constants import IMPORT_SERIALIZED_IMPORTING
from baserow.contrib.automation.formula_importer import import_formula
from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.exceptions import (
    AutomationWorkflowHistoryDoesNotExist,
)
from baserow.contrib.automation.history.handler import AutomationHistoryHandler
from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationWorkflowHistory,
)
from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.nodes.constants import (
    AUTOMATION_NODE_RETRY_COUNTDOWNS,
    AUTOMATION_PENDING_NODE_COUNTDOWN_CHUNK_SECONDS,
    AUTOMATION_PENDING_NODE_STALE_SECONDS,
    AutomationNodeOnFailure,
)
from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeDoesNotExist,
    AutomationNodeMaxDispatchesExceeded,
)
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.node_types import (
    AutomationActionNodeType,
    AutomationNodeType,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.signals import (
    automation_node_dispatch_completed,
    automation_node_dispatch_resumed,
    automation_node_dispatch_started,
    automation_node_dispatch_suspended,
    automation_node_updated,
)
from baserow.contrib.automation.nodes.tasks import (
    dispatch_node_celery_task,
    resume_deferred_node_celery_task,
    resume_pending_node_celery_task,
)
from baserow.contrib.automation.nodes.types import (
    AutomationNodeDict,
    NodeDispatchRetry,
    PendingNodeAlreadyClaimed,
    PendingNodeNotDue,
)
from baserow.core.cache import local_cache
from baserow.core.db import specific_iterator
from baserow.core.formula import BaserowFormulaException, resolve_formula
from baserow.core.formula.exceptions import (
    InvalidFormulaContext,
    InvalidFormulaContextContent,
)
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.validator import ensure_boolean
from baserow.core.graph.handler import BaseGraphHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.services.exceptions import (
    RuntimeDispatchException,
    ServiceImproperlyConfiguredDispatchException,
    UnexpectedDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.services.types import DispatchResult, PendingDispatch
from baserow.core.storage import ExportZipFile
from baserow.core.telemetry.utils import baserow_trace, baserow_trace_handler
from baserow.core.utils import ChildProgressBuilder, MirrorDict, extract_allowed

tracer = trace.get_tracer(__name__)


@baserow_trace_handler
class AutomationNodeHandler:
    allowed_fields = [
        "label",
        "service",
    ]

    def _get_node_cache_key(self, workflow, specific):
        return f"wa_get_{workflow.id}_nodes_{specific}"

    def get_nodes(
        self,
        workflow: AutomationWorkflow,
        specific: Optional[bool] = True,
        base_queryset: Optional[QuerySet] = None,
        with_cache: bool = True,
    ) -> Union[QuerySet[AutomationNode], Iterable[AutomationNode]]:
        """
        Returns all the nodes, filtered by a workflow.

        :param workflow: The workflow associated with the nodes.
        :param specific: A boolean flag indicating whether to return the specific
            nodes and their services
        :param base_queryset: Optional base queryset to filter the results.
        :param with_cache: Whether to return a cached value, if available.
        :return: A queryset or list of automation nodes.
        """

        def _get_nodes(base_queryset=base_queryset):
            if base_queryset is None:
                base_queryset = AutomationNode.objects.all()

            nodes = base_queryset.select_related(
                "workflow__automation__workspace"
            ).filter(workflow=workflow)

            if specific:
                nodes = specific_iterator(nodes.select_related("content_type"))
                service_ids = [
                    node.service_id for node in nodes if node.service_id is not None
                ]
                specific_services_map = {
                    s.id: s
                    for s in ServiceHandler().get_services(
                        base_queryset=Service.objects.filter(id__in=service_ids)
                    )
                }
                for node in nodes:
                    service_id = node.service_id
                    if service_id is not None and service_id in specific_services_map:
                        node.service = specific_services_map[service_id]
            return nodes

        if with_cache and not base_queryset:
            return local_cache.get(
                self._get_node_cache_key(workflow, specific),
                _get_nodes,
            )
        return _get_nodes()

    def invalidate_node_cache(self, workflow):
        """
        Invalidates the node cache. To be used when we add or remove a node from the
        graph.

        :param workflow: The target workflow cache.
        """

        local_cache.delete(self._get_node_cache_key(workflow, True))
        local_cache.delete(self._get_node_cache_key(workflow, False))
        local_cache.delete(BaseGraphHandler.generate_point_map_cache_key(workflow))

    def get_children(
        self, node: AutomationNode, first_only: bool = False
    ) -> List[AutomationNode]:
        """
        Returns the children of the given node.

        :param node: The parent node.
        :param first_only: When True, return only the entry-point child of each
            edge/slot without following the next[""] chain. Use this when the
            caller handles chaining via get_next_points itself.
        :return: A list of node instances that are the children of the given node.
        """

        return node.workflow.get_graph().get_children(node, first_only=first_only)

    def get_node(
        self, node_id: int, base_queryset: Optional[QuerySet] = None
    ) -> AutomationNode:
        """
        Return an AutomationNode by its ID.

        :param node_id: The ID of the AutomationNode.
        :param base_queryset: Can be provided to already filter or apply performance
            improvements to the queryset when it's being executed.
        :raises AutomationNodeDoesNotExist: If the node doesn't exist.
        :return: The model instance of the AutomationNode
        """

        if base_queryset is None:
            base_queryset = AutomationNode.objects.all()

        try:
            return (
                base_queryset.select_related("workflow__automation__workspace")
                .get(id=node_id)
                .specific
            )
        except AutomationNode.DoesNotExist:
            raise AutomationNodeDoesNotExist(node_id)

    def get_node_by_service_id(self, service_id: int) -> AutomationNode:
        """
        Return the AutomationNode that owns the given service. The node<->service
        relation is one-to-one, so a service maps to exactly one node.

        :param service_id: The ID of the node's service.
        :raises AutomationNodeDoesNotExist: If no node owns the service.
        :return: The specific model instance of the AutomationNode.
        """

        try:
            return (
                AutomationNode.objects.select_related("workflow__automation__workspace")
                .get(service_id=service_id)
                .specific
            )
        except AutomationNode.DoesNotExist:
            raise AutomationNodeDoesNotExist(service_id)

    def create_node(
        self,
        node_type: AutomationNodeType,
        workflow: AutomationWorkflow,
        **kwargs,
    ) -> AutomationNode:
        """
        Create a new automation node.

        :param node_type: The automation node's type.
        :param workflow: The workflow the automation node is associated with.
        :return: The newly created automation node instance.
        """

        allowed_prepared_values = extract_allowed(
            kwargs, self.allowed_fields + node_type.allowed_fields
        )

        node = node_type.model_class.objects.create(
            workflow=workflow, **allowed_prepared_values
        )

        self.invalidate_node_cache(workflow)

        return node

    def update_node(self, node: AutomationNode, **kwargs) -> AutomationNode:
        """
        Updates fields of the provided AutomationNode.

        :param node: The AutomationNode that should be updated.
        :param kwargs: The fields that should be updated with their
            corresponding values.
        :return: The updated AutomationNode.
        """

        # The node type decides what can be updated: action nodes accept the
        # error policy fields on top of the base ones, triggers do not.
        allowed_values = extract_allowed(kwargs, node.get_type().allowed_fields)

        for key, value in allowed_values.items():
            setattr(node, key, value)

        node.save()

        return node

    def duplicate_node(self, source_node: AutomationNode) -> AutomationNode:
        """
        Duplicates an existing AutomationNode instance.

        :param source_node: The AutomationNode that is being duplicated.
        :raises ValueError: When the provided node is not an instance of
            AutomationNode.
        :return: The duplicated node.
        """

        exported_node = self.export_node(source_node)

        id_mapping = defaultdict(lambda: MirrorDict())
        id_mapping["automation_workflow_nodes"] = MirrorDict()
        # A single-node duplicate leaves referenced nodes (and thus their
        # services) in place, so mirror service ids too. This lets a self
        # reference like a "Go to node" destination carry over unchanged.
        id_mapping["services"] = MirrorDict()

        import_export_config = ImportExportConfig(
            include_permission_data=True,
            reduce_disk_space_usage=False,
            is_duplicate=True,
            exclude_sensitive_data=False,
        )

        duplicated_node = self.import_node(
            source_node.workflow,
            exported_node,
            id_mapping=id_mapping,
            import_export_config=import_export_config,
        )

        self.invalidate_node_cache(duplicated_node.workflow)

        return duplicated_node

    def export_node(
        self,
        node: AutomationNode,
        import_export_config: Optional[ImportExportConfig] = None,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict] = None,
    ) -> AutomationNodeDict:
        """
        Serializes the given node.

        :param node: The AutomationNode instance to serialize.
        :param files_zip: A zip file to store files in necessary.
        :param storage: Storage to use.
        :param cache: A cache dictionary to store intermediate results.
        :return: The serialized version.
        """

        return node.get_type().export_serialized(
            node,
            import_export_config=import_export_config,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

    def import_node(
        self,
        workflow: AutomationWorkflow,
        serialized_node: AutomationNodeDict,
        id_mapping: Dict[str, Dict[int, int]],
        *args,
        **kwargs,
    ) -> AutomationNode:
        """
        Creates an instance of AutomationNode using the serialized version
        previously exported with '.export_node'.

        :param workflow: The workflow instance the new node should
            belong to.
        :param serialized_node: The serialized version of the
            AutomationNode.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :return: the newly created instance.
        """

        return self.import_nodes(
            workflow,
            [serialized_node],
            id_mapping,
            *args,
            **kwargs,
        )[0]

    @baserow_trace(tracer)
    def import_nodes(
        self,
        workflow: AutomationWorkflow,
        serialized_nodes: List[AutomationNodeDict],
        id_mapping: Dict[str, Dict[int, int]],
        cache: Optional[Dict] = None,
        progress: Optional[ChildProgressBuilder] = None,
        *args,
        **kwargs,
    ):
        """
        Import multiple nodes at once.

        :param workflow: The workflow instance the new node should
            belong to.
        :param serialized_nodes: The serialized version of the nodes.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :param cache: A cache dictionary to store intermediate results.
        :return: the newly created instances.
        """

        if cache is None:
            cache = {}

        imported_nodes = []
        for serialized_node in serialized_nodes:
            node_instance = self.import_node_only(
                workflow,
                serialized_node,
                id_mapping,
                cache=cache,
                *args,
                **kwargs,
            )
            imported_nodes.append(node_instance)

            if progress:
                progress.increment(state=IMPORT_SERIALIZED_IMPORTING)

        # We migrate service formulas and remap cross-service references here to
        # make sure all nodes are imported before we migrate them
        for imported_node in imported_nodes:
            service = imported_node.service.specific
            service_type = service.get_type()
            updated_models = service_type.import_formulas(
                service, id_mapping, import_formula, **kwargs
            )
            updated_models |= service_type.after_import(service, id_mapping, **kwargs)

            [u.save() for u in updated_models]

            # The node's own formulas (the retry condition) read the node's
            # result through the `current_node` provider, whose paths carry no
            # node id. The node is passed along so the provider can remap the
            # path against the imported service.
            node_type = imported_node.get_type()
            updated_nodes = node_type.import_formulas(
                imported_node,
                id_mapping,
                import_formula,
                current_node=imported_node,
                **kwargs,
            )
            [n.save() for n in updated_nodes]

        return imported_nodes

    def import_node_only(
        self,
        workflow: AutomationWorkflow,
        serialized_node: AutomationNodeDict,
        id_mapping: Dict[str, Dict[int, int]],
        import_export_config: Optional[ImportExportConfig] = None,
        *args: Any,
        **kwargs: Any,
    ) -> AutomationNode:
        node_type = automation_node_type_registry.get(serialized_node["type"])

        node_instance = node_type.import_serialized(
            workflow,
            serialized_node,
            id_mapping,
            import_export_config=import_export_config,
            *args,
            **kwargs,
        )

        return node_instance

    def _handle_workflow_error(
        self,
        node_history: AutomationNodeHistory,
        iteration_path: str,
        error: str,
        result: Optional[Union[Dict, List[Dict]]] = None,
    ) -> None:
        """
        Marks the node history and the whole run as errored. `result` is stored
        as the attempt's result when the node did produce data before it was
        considered failed, so the data can still be inspected in the history.
        """

        now = timezone.now()
        node_history.workflow_history.completed_on = now
        node_history.workflow_history.message = error
        node_history.workflow_history.status = HistoryStatusChoices.ERROR
        node_history.workflow_history.save()
        if node_history.workflow_history.simulate_until_node_id is None:
            AutomationHistoryHandler().ensure_default_response(
                node_history.workflow_history
            )

        node_history.completed_on = now
        node_history.message = error
        node_history.status = HistoryStatusChoices.ERROR
        node_history.save()

        AutomationHistoryHandler().create_node_result(
            node_history=node_history,
            result=result,
            iteration_path=iteration_path,
        )

    def _retry_countdown(self, attempt: int) -> int:
        """
        Seconds to wait before the attempt following `attempt`: 1, 1, 2, 3, 6 s.
        `_can_retry` bounds `attempt` by the node's `max_retries`, the last
        countdown is repeated should that bound ever grow.
        """

        countdowns = AUTOMATION_NODE_RETRY_COUNTDOWNS
        return countdowns[min(attempt, len(countdowns)) - 1]

    @staticmethod
    def _retries_phrase(count: int) -> str:
        return f"{count} {'retry' if count == 1 else 'retries'}"

    def _can_retry(
        self,
        node: AutomationNode,
        workflow_history: AutomationWorkflowHistory,
        attempt: int,
    ) -> bool:
        """
        Whether the node's error policy allows another attempt after `attempt`
        failed. Test runs retry like live runs, so the editor shows what the
        published workflow will do. Simulations never retry: they run up to a
        node to fetch its sample data.
        """

        return (
            node.on_failure == AutomationNodeOnFailure.RETRY
            and attempt <= node.max_retries
            and workflow_history.simulate_until_node_id is None
        )

    def _handle_node_retry(
        self,
        node_history: AutomationNodeHistory,
        iteration_path: str,
        message: str,
        result: Optional[Union[Dict, List[Dict]]] = None,
    ) -> None:
        """
        Closes this attempt's history as `retried`. The run is left `started`:
        the next attempt creates its own history entry when it runs.
        """

        now = timezone.now()
        node_history.completed_on = now
        node_history.message = message
        node_history.status = HistoryStatusChoices.RETRIED
        node_history.save()
        # Written even when empty: the history API derives the iteration path
        # from the result row. The next attempt writes its own row, and
        # get_node_result() picks the most recent one.
        AutomationHistoryHandler().create_node_result(
            node_history=node_history,
            result=result,
            iteration_path=iteration_path,
        )

    def _handle_dispatch_failure(
        self,
        node: AutomationNode,
        node_history: AutomationNodeHistory,
        workflow_history: AutomationWorkflowHistory,
        simulate_until_node: AutomationNode | None,
        iteration_path: str,
        attempt: int,
        error: str,
        retryable: bool,
    ) -> NodeDispatchRetry | None:
        """
        Applies the node's error policy to a failed attempt. Only a `retryable`
        failure (a transient `RuntimeDispatchException`) can be retried, and
        only when the node opted into retries at all; everything else ends the
        run as before.

        :return: A NodeDispatchRetry for the Celery task to schedule, or None
            when the run was marked as errored.
        """

        if retryable and self._can_retry(node, workflow_history, attempt):
            self._handle_node_retry(
                node_history,
                iteration_path,
                f"Retry {attempt} of {node.max_retries} scheduled. {error}",
            )
            return NodeDispatchRetry(
                node_id=node.id,
                history_id=workflow_history.id,
                attempt=attempt,
                countdown=self._retry_countdown(attempt),
            )

        if attempt > 1:
            # The node was retried before this attempt failed for good. Say so,
            # otherwise the row reads like a plain "Stop" failure.
            error = f"Failed after {self._retries_phrase(attempt - 1)}. {error}"

        self._handle_workflow_error(node_history, iteration_path, error)
        self._handle_simulation_notify(simulate_until_node, node)

        return None

    def _retry_condition_enabled(
        self, node: AutomationNode, workflow_history: AutomationWorkflowHistory
    ) -> bool:
        """
        Whether a successful attempt must still be checked against the node's
        retry condition. An empty condition means there is none. Simulations
        never evaluate it; test runs do, like live runs.
        """

        formula = (node.retry_condition or {}).get("formula") or ""
        return (
            node.on_failure == AutomationNodeOnFailure.RETRY
            and bool(formula.strip())
            and workflow_history.simulate_until_node_id is None
        )

    def _retry_condition_matches(
        self,
        node: AutomationNode,
        dispatch_context: AutomationDispatchContext,
        dispatch_result: DispatchResult,
    ) -> bool:
        """
        Evaluates the node's retry condition against the data it just
        produced, exposed to the formula through the `current_node` data
        provider. True means the attempt counts as failed.

        :raises InvalidFormulaContext: If a `get()` path cannot be resolved.
        :raises InvalidFormulaContextContent: If the resolved content is unusable.
        :raises ValidationError: If a runtime function rejects one of its values.
        :raises BaserowFormulaException: If the formula cannot be parsed.
        """

        context = dispatch_context.clone()
        context.current_node = node
        context.current_node_result = dispatch_result.data
        value = resolve_formula(
            node.retry_condition, formula_runtime_function_registry, context
        )
        return ensure_boolean(value, False)

    def _handle_retry_condition_matched(
        self,
        node: AutomationNode,
        node_history: AutomationNodeHistory,
        workflow_history: AutomationWorkflowHistory,
        iteration_path: str,
        attempt: int,
        result: Dict,
    ) -> NodeDispatchRetry | None:
        """
        The node produced data, but its retry condition says the attempt
        failed. The data is stored as the attempt's result either way, so it
        can still be inspected in the history.

        :return: A NodeDispatchRetry for the Celery task to schedule, or None
            when the retries are exhausted and the run was marked as errored.
        """

        if self._can_retry(node, workflow_history, attempt):
            self._handle_node_retry(
                node_history,
                iteration_path,
                f"The retry condition matched. Retry {attempt} of "
                f"{node.max_retries} scheduled.",
                result=result,
            )
            return NodeDispatchRetry(
                node_id=node.id,
                history_id=workflow_history.id,
                attempt=attempt,
                countdown=self._retry_countdown(attempt),
            )

        error = (
            "The retry condition still matched after "
            f"{self._retries_phrase(node.max_retries)}."
        )
        self._handle_workflow_error(node_history, iteration_path, error, result=result)
        return None

    def _node_dispatch_count_cache_key(self, history_id: int) -> str:
        return f"automation_node_dispatch_count_{history_id}"

    def _check_node_dispatch_limit(self, history_id: int) -> bool:
        """
        Increments and checks the per-run node dispatch counter. The counter
        is keyed per workflow run and self-expires after the workflow timeout.

        This is a safety backstop against infinite loops, e.g. a misconfigured
        "Go to node".
        """

        key = self._node_dispatch_count_cache_key(history_id)
        cache.add(key, 0, settings.AUTOMATION_WORKFLOW_TIMEOUT_HOURS * 60 * 60)
        dispatch_count = cache.incr(key)
        return dispatch_count > settings.AUTOMATION_MAX_NODE_DISPATCHES_PER_RUN

    def _handle_simulation_notify(
        self, simulate_until_node: AutomationNode | None, node: AutomationNode
    ) -> bool:
        """
        When the simulated node is the current node, refresh the sample data
        and send a node updated signal so that the frontend receives the
        updated sample data.

        Returns True if a signal was sent, False otherwise.
        """

        if simulate_until_node and simulate_until_node.id == node.id:
            service = node.service.specific
            service.refresh_from_db(fields=["sample_data"])
            automation_node_updated.send(self, user=None, node=node)
            return True

        return False

    def _before_node_dispatch(
        self,
        node: AutomationNode,
        workflow_history: AutomationWorkflowHistory,
    ) -> None:
        """
        Runs pre-dispatch checks and emits the started signal.

        :raises AutomationNodeMaxDispatchesExceeded: If the workflow run has
            exceeded the maximum number of node dispatches allowed.
        """

        # Stop the workflow run if it exceeds the max dispatches allowed.
        # Safety backstop against infinite loops, e.g. a misconfigured
        # "Go to node".
        if self._check_node_dispatch_limit(workflow_history.id):
            limit = settings.AUTOMATION_MAX_NODE_DISPATCHES_PER_RUN
            raise AutomationNodeMaxDispatchesExceeded(
                f"Workflow exceeded the maximum of {limit} node dispatches."
            )

        automation_node_dispatch_started.send(
            sender=self,
            node=node,
            workflow_history=workflow_history,
        )

    def _after_node_dispatch(
        self, node: AutomationNode, node_history: AutomationNodeHistory
    ) -> None:
        """
        Sends a signal after a node is dispatched.
        """

        automation_node_dispatch_completed.send(
            sender=self,
            node=node,
            node_history=node_history,
        )

    @baserow_trace(tracer)
    def dispatch_node(
        self,
        node_id: int,
        history_id: int,
        current_iterations: Optional[Dict[int, int]] = None,
        attempt: int = 1,
    ) -> Signature | NodeDispatchRetry | None:
        """
        Dispatch a single node and return a canvas for the next nodes.

        :param node_id: The node to dispatch.
        :param history_id: The AutomationWorkflowHistory ID from which the
            workflow's event payload and node results are derived.
        :param current_iterations: Used by the Iterator node's children.
        :param attempt: Which attempt of this node this is, starting at 1. The
            Celery task increments it when it retries a failed attempt.
        :return result: A signature is returned if there is a next node to
            dispatch, a NodeDispatchRetry if this attempt failed and the node's
            error policy allows another one, otherwise None.
        """

        history_handler = AutomationHistoryHandler()

        try:
            workflow_history = history_handler.get_workflow_history(
                history_id=history_id
            )
        except AutomationWorkflowHistoryDoesNotExist as e:
            logger.error(str(e))
            return None

        if workflow_history.status in (
            HistoryStatusChoices.CANCELLED,
            HistoryStatusChoices.ERROR,
        ):
            # The run was already finalized, e.g. by an earlier dispatch of this
            # run, a failed sibling node, or the timeout sweep. Iterator iterations
            # and sibling branches are pre-chained as Celery groups, so without this
            # guard they would keep running after one child errored.
            return None

        if (
            workflow_history.cancellation_requested_on is not None
            and workflow_history.status == HistoryStatusChoices.STARTED
        ):
            history_handler.finalize_workflow_history_cancellation(workflow_history)
            return None

        error = (
            "Node with ID {} was not found. The node was likely "
            "deleted before the task was executed."
        )
        try:
            node = self.get_node(node_id)
        except AutomationNodeDoesNotExist:
            logger.warning(error.format(node_id))
            return None

        try:
            simulate_until_node = (
                node.workflow.get_graph().get_point(
                    workflow_history.simulate_until_node_id
                )
                if workflow_history.simulate_until_node_id
                else None
            )
        except AutomationNodeDoesNotExist:
            logger.warning(error.format(workflow_history.simulate_until_node_id))
            return None

        if simulate_until_node:
            allowed_nodes = {
                *simulate_until_node.get_previous_points(),
                simulate_until_node,
            }
            if node not in allowed_nodes:
                # Return early as the node is not in the path leading to
                # the simulated node.
                return None

        node_history = history_handler.create_node_history(
            workflow_history=workflow_history,
            node=node,
            started_on=timezone.now(),
            attempt=attempt,
        )

        dispatch_context = AutomationDispatchContext(
            node.workflow,
            workflow_history,
            event_payload=workflow_history.event_payload,
            simulate_until_node=workflow_history.simulate_until_node,
            current_iterations=current_iterations,
        )
        iteration_path = dispatch_context.get_iteration_path(node)
        node_type: Type[AutomationActionNodeType] = node.get_type()

        try:
            self._before_node_dispatch(node, workflow_history)
            dispatch_result = node_type.dispatch(node, dispatch_context)
            if dispatch_result.pending is not None and simulate_until_node:
                # A simulation never waits, whatever the service did. A service
                # is expected to answer at once when it uses sample data; this
                # is the backstop, resuming it right away.
                dispatch_result = node_type.resume_dispatch(
                    node, dispatch_result.pending.state, dispatch_context
                )
            if (
                dispatch_result.destination_service_id is not None
                and not simulate_until_node
            ):
                # The dispatch requested a jump the runner is about to follow
                # (jumps are never followed while simulating). Let the node type
                # re-validate the destination against the live graph first.
                node_type.validate_jump_destination(
                    node, dispatch_result.destination_service_id
                )
        except AutomationNodeMaxDispatchesExceeded as e:
            error = str(e)
            logger.warning(error)
            return self._handle_dispatch_failure(
                node,
                node_history,
                workflow_history,
                simulate_until_node,
                iteration_path,
                attempt,
                error,
                retryable=False,
            )
        except RuntimeDispatchException as e:
            # Must come before ServiceImproperlyConfiguredDispatchException:
            # RemoteBusyDispatchException (a rate limit) is a subclass of both
            # and is the one failure a later attempt is expected to fix.
            original_workflow = node.workflow.get_original()
            error = (
                f"Error while running workflow {original_workflow.id}. Error: {str(e)}"
            )
            logger.warning(error)
            return self._handle_dispatch_failure(
                node,
                node_history,
                workflow_history,
                simulate_until_node,
                iteration_path,
                attempt,
                error,
                retryable=True,
            )
        except ServiceImproperlyConfiguredDispatchException as e:
            error = f"The node is misconfigured and cannot be dispatched. {str(e)}"
            return self._handle_dispatch_failure(
                node,
                node_history,
                workflow_history,
                simulate_until_node,
                iteration_path,
                attempt,
                error,
                retryable=False,
            )
        except UnexpectedDispatchException as e:
            original_workflow = node.workflow.get_original()
            error = (
                f"Error while running workflow {original_workflow.id}. Error: {str(e)}"
            )
            logger.warning(error)
            return self._handle_dispatch_failure(
                node,
                node_history,
                workflow_history,
                simulate_until_node,
                iteration_path,
                attempt,
                error,
                retryable=False,
            )
        except Exception as e:
            original_workflow = node.workflow.get_original()

            error = (
                f"Unexpected error while running workflow {original_workflow.id}. "
                f"Error: {str(e)}"
            )
            logger.exception(error)
            return self._handle_dispatch_failure(
                node,
                node_history,
                workflow_history,
                simulate_until_node,
                iteration_path,
                attempt,
                error,
                retryable=False,
            )

        if dispatch_result.pending is not None:
            # The service asked to be resumed later: the node is parked and the
            # worker freed. Like a deferred node, a pending one gets its data
            # later, through complete_pending_node(), where the retry condition
            # does not apply.
            return self._suspend_node(
                node,
                node_history,
                workflow_history,
                dispatch_result.pending,
                iteration_path,
                current_iterations,
            )

        # The node produced data, but its retry condition may still count the
        # attempt as failed. A deferred node gets its data later, through
        # complete_deferred_node(), where the error policy does not apply.
        if (
            dispatch_result.deferred_history_id is None
            and self._retry_condition_enabled(node, workflow_history)
        ):
            try:
                matched = self._retry_condition_matches(
                    node, dispatch_context, dispatch_result
                )
            except (
                InvalidFormulaContext,
                InvalidFormulaContextContent,
                ValidationError,
                BaserowFormulaException,
            ) as e:
                detail = (
                    " ".join(e.messages) if isinstance(e, ValidationError) else str(e)
                )
                error = f"The retry condition of this node is invalid. {detail}"
                self._handle_workflow_error(
                    node_history, iteration_path, error, result=dispatch_result.data
                )
                return None
            except Exception as e:
                # A bug in a runtime function must not leave the run `started`
                # forever: it would only be swept after the workflow timeout.
                error = (
                    "Unexpected error while evaluating the retry condition of "
                    f"this node. Error: {str(e)}"
                )
                logger.exception(error)
                self._handle_workflow_error(
                    node_history, iteration_path, error, result=dispatch_result.data
                )
                return None

            if matched:
                return self._handle_retry_condition_matched(
                    node,
                    node_history,
                    workflow_history,
                    iteration_path,
                    attempt,
                    dispatch_result.data,
                )

        # A deferred node must first schedule and await its child workflow. The
        # simulation is completed when the deferred result is resumed below.
        if (
            dispatch_result.deferred_history_id is None
            and self._handle_simulation_notify(simulate_until_node, node)
        ):
            return None

        if dispatch_result.deferred_history_id is not None:
            from baserow.contrib.automation.workflows.tasks import (
                start_workflow_celery_task,
            )

            deferred_history = history_handler.get_workflow_history(
                dispatch_result.deferred_history_id
            )
            transaction.on_commit(
                lambda: start_workflow_celery_task.delay(
                    deferred_history.workflow_id,
                    deferred_history.id,
                )
            )
            timeout_seconds = dispatch_result.deferred_timeout_seconds or 30
            deadline = timezone.now().timestamp() + timeout_seconds
            return resume_deferred_node_celery_task.si(
                node_history.id,
                deferred_history.id,
                iteration_path,
                deadline,
                current_iterations,
            )

        return self._complete_node_dispatch(
            node,
            node_history,
            dispatch_context,
            iteration_path,
            dispatch_result,
            current_iterations,
        )

    def _pending_node_countdown(self, resume_at: datetime, now: datetime) -> int:
        """
        Seconds before the resume task of a waiting node wakes up next: the
        time left until `resume_at`, cut to one chunk so that no message waits
        in the broker longer than its visibility timeout. Rounded up, so a
        wake-up never lands just before the node is due.
        """

        remaining = math.ceil((resume_at - now).total_seconds())
        return max(0, min(remaining, AUTOMATION_PENDING_NODE_COUNTDOWN_CHUNK_SECONDS))

    def _suspend_node(
        self,
        node: AutomationNode,
        node_history: AutomationNodeHistory,
        workflow_history: AutomationWorkflowHistory,
        pending: PendingDispatch,
        iteration_path: str,
        current_iterations: Optional[Dict[int, int]],
    ) -> Signature | None:
        """
        Parks a node whose service asked to be resumed later (e.g. a "Wait"
        node): its history is marked `waiting` with everything the resume needs,
        and the resume task is scheduled with a countdown. No worker is held in
        the meantime and the run stays `started`.

        :return: The resume task's signature, which runs in place of this
            dispatch so the run's chain goes on from the resumed node, or None
            when the run was marked as errored.
        """

        if pending.resume_at is None:
            # Only time-based resumes are supported for now.
            error = (
                "The node is misconfigured and cannot be dispatched. The node "
                "suspended itself without a time to resume at."
            )
            self._handle_workflow_error(node_history, iteration_path, error)
            return None

        now = timezone.now()
        resume_at = pending.resume_at

        node_history.status = HistoryStatusChoices.WAITING
        node_history.resume_at = resume_at
        # The iterator positions are stored as received: their keys are strings
        # after Celery's JSON round trip, and the dispatch context converts them.
        node_history.resume_state = {
            "state": pending.state,
            "current_iterations": current_iterations,
        }
        node_history.save()

        automation_node_dispatch_suspended.send(
            sender=self, node=node, node_history=node_history
        )

        return resume_pending_node_celery_task.si(node_history.id).set(
            countdown=self._pending_node_countdown(resume_at, now)
        )

    def complete_deferred_node(
        self,
        node_history_id: int,
        deferred_history_id: int,
        iteration_path: str,
        timed_out: bool = False,
        current_iterations: Optional[Dict[int, int]] = None,
    ) -> Optional[Signature]:
        """Completes a parent node after a response, completion, or timeout."""

        history_handler = AutomationHistoryHandler()
        node_history = AutomationNodeHistory.objects.select_related(
            "node__workflow", "workflow_history"
        ).get(id=node_history_id)
        deferred_history = history_handler.get_workflow_history(deferred_history_id)
        workflow_response = (
            None
            if timed_out
            else history_handler.get_workflow_history_response(deferred_history)
        )
        if workflow_response is None and not timed_out:
            workflow_response = history_handler.ensure_default_response(
                deferred_history
            )
        dispatch_context = AutomationDispatchContext(
            node_history.node.workflow,
            node_history.workflow_history,
            event_payload=node_history.workflow_history.event_payload,
            simulate_until_node=node_history.workflow_history.simulate_until_node,
            current_iterations=current_iterations,
        )
        response_data = (
            {
                "status_code": workflow_response.status_code,
                "headers": workflow_response.headers,
                "body": workflow_response.body,
                "body_type": workflow_response.body_type,
            }
            if workflow_response is not None
            else {
                "status_code": 504,
                "headers": {},
                "body": None,
                "body_type": "empty",
            }
        )
        dispatch_result = DispatchResult(data=response_data)
        return self._complete_node_dispatch(
            node_history.node,
            node_history,
            dispatch_context,
            iteration_path,
            dispatch_result,
            current_iterations,
        )

    def resume_pending_node(
        self, node_history_id: int
    ) -> Signature | PendingNodeNotDue | PendingNodeAlreadyClaimed | None:
        """
        Entry point of the resume task of a waiting node, called at every
        wake-up. Checks that the run still wants the node, asks for another
        wake-up if the node is not due yet, and otherwise claims it and
        finishes its dispatch. The claim is a conditional update from `waiting`,
        so a duplicate delivery of the task (a redelivered message, the recovery
        sweep) resumes the node once at most.

        :param node_history_id: The `waiting` node history to resume.
        :return: As dispatch_node(): a signature for the next nodes, or None
            when this branch of the run is over (the run was resolved, the node
            was deleted, or nothing follows it). A PendingNodeNotDue asks the
            task to wake up again later, a PendingNodeAlreadyClaimed tells it
            that another delivery already resumed the node.
        """

        try:
            node_history = AutomationNodeHistory.objects.select_related(
                "workflow_history__workflow__automation__workspace",
                "workflow_history__cancellation_requested_by",
            ).get(id=node_history_id)
        except AutomationNodeHistory.DoesNotExist:
            # The node or its workflow was deleted while the node waited, e.g.
            # the workflow was republished. The run's chain goes on and resolves
            # the run, nothing else is left to do for this node.
            logger.warning(
                f"Node history with ID {node_history_id} was not found. It was "
                "likely deleted while the node was waiting."
            )
            return None

        workflow_history = node_history.workflow_history

        if workflow_history.status in (
            HistoryStatusChoices.CANCELLED,
            HistoryStatusChoices.ERROR,
        ):
            # Resolved while the node waited, e.g. by the timeout sweep.
            self._resolve_waiting_node(
                node_history, workflow_history.status, workflow_history.message
            )
            return None

        if (
            workflow_history.cancellation_requested_on is not None
            and workflow_history.status == HistoryStatusChoices.STARTED
        ):
            # The same cooperative cancellation as dispatch_node(): a "Stop run"
            # is noticed at the next wake-up, within one countdown chunk.
            AutomationHistoryHandler().finalize_workflow_history_cancellation(
                workflow_history
            )
            workflow_history.refresh_from_db(fields=["status", "message"])
            self._resolve_waiting_node(
                node_history, workflow_history.status, workflow_history.message
            )
            return None

        if node_history.status != HistoryStatusChoices.WAITING:
            return PendingNodeAlreadyClaimed()

        now = timezone.now()
        if node_history.resume_at > now:
            return PendingNodeNotDue(
                countdown=self._pending_node_countdown(node_history.resume_at, now)
            )

        claimed = AutomationNodeHistory.objects.filter(
            id=node_history.id, status=HistoryStatusChoices.WAITING
        ).update(status=HistoryStatusChoices.STARTED)
        if not claimed:
            return PendingNodeAlreadyClaimed()

        node_history.status = HistoryStatusChoices.STARTED
        return self.complete_pending_node(node_history)

    def _resolve_waiting_node(
        self, node_history: AutomationNodeHistory, status: str, message: str
    ) -> None:
        """
        Closes the history of a waiting node whose run was resolved elsewhere,
        with the run's outcome. Guarded on the row still being `waiting`, so a
        duplicate wake-up never rewrites it.
        """

        AutomationNodeHistory.objects.filter(
            id=node_history.id, status=HistoryStatusChoices.WAITING
        ).update(status=status, message=message, completed_on=timezone.now())

    def resume_stale_waiting_nodes(self) -> int:
        """
        Safety net for a waiting node whose resume task is gone: the broker lost
        its message (a flushed or restarted Redis without persistence), so
        nothing will ever wake the node up and its run would stay `started`
        until the run timeout. A node is considered stale when its resume is
        overdue by more than `AUTOMATION_PENDING_NODE_STALE_SECONDS`, which is
        longer than a live resume can be late (see the constant), and is given a
        fresh resume task. A message that turns out to have been late rather
        than lost loses the claim and is dropped, so a node still resumes once
        at most.

        Called by the periodic cleanup, after the runs that are over their
        budget were timed out: their waiting nodes are resolved with them and
        need no recovery.

        Known limitation: only the waiting node itself is recovered. If the
        broker really lost the run's messages, the sibling iterations and the
        nodes queued after an iterator are gone with them, so the run completes
        without ever running those. The alternative is a run that hangs
        `started` until it times out a day later.

        :return: How many waiting nodes were given a new resume task.
        """

        stale_before = timezone.now() - timedelta(
            seconds=AUTOMATION_PENDING_NODE_STALE_SECONDS
        )
        # Served by the conditional `resume_at` index on waiting rows.
        stale_nodes = AutomationNodeHistory.objects.filter(
            status=HistoryStatusChoices.WAITING,
            resume_at__lt=stale_before,
            workflow_history__status=HistoryStatusChoices.STARTED,
        ).values_list(
            "id", "workflow_history_id", "workflow_history__simulate_until_node"
        )

        resumed = 0
        for node_history_id, history_id, simulate_until_node_id in stale_nodes:
            logger.warning(
                f"The resume of waiting node history {node_history_id} of "
                f"workflow history {history_id} is overdue by more than "
                f"{AUTOMATION_PENDING_NODE_STALE_SECONDS} seconds. Its resume "
                "task was likely lost, scheduling a new one."
            )
            self._schedule_waiting_node_recovery(
                node_history_id, history_id, simulate_until_node_id
            )
            resumed += 1

        return resumed

    def _schedule_waiting_node_recovery(
        self,
        node_history_id: int,
        history_id: int,
        simulate_until_node_id: Optional[int],
    ) -> None:
        """
        Queues a replacement resume task for a stale waiting node, with the
        run's dispatch-done tail behind it as `start_workflow()` has, so the run
        is still completed once the recovered branch is finished.
        """

        from baserow.contrib.automation.workflows.tasks import (
            handle_workflow_dispatch_done,
        )

        recovery = chain(
            resume_pending_node_celery_task.si(node_history_id),
            handle_workflow_dispatch_done.si(
                history_id=history_id,
                simulate_until_node_id=simulate_until_node_id,
            ),
        )
        transaction.on_commit(recovery.delay)

    def complete_pending_node(
        self, node_history: AutomationNodeHistory
    ) -> Optional[Signature]:
        """
        Finishes the dispatch of a node that suspended itself, once its resume
        is due and claimed: the service is resumed with the state it stored, and
        the result is completed like any other dispatch, iterator positions
        included. A failure here is not retried by the node's error policy: the
        wait itself has nothing transient to recover from. A resume does not
        count as a dispatch for the per-run limit either.
        """

        node = node_history.node.specific
        workflow_history = node_history.workflow_history
        resume_state = node_history.resume_state or {}
        current_iterations = resume_state.get("current_iterations")
        dispatch_context = AutomationDispatchContext(
            node.workflow,
            workflow_history,
            event_payload=workflow_history.event_payload,
            simulate_until_node=workflow_history.simulate_until_node,
            current_iterations=current_iterations,
        )
        iteration_path = dispatch_context.get_iteration_path(node)
        node_type: Type[AutomationActionNodeType] = node.get_type()

        try:
            dispatch_result = node_type.resume_dispatch(
                node, resume_state.get("state") or {}, dispatch_context
            )
        except Exception as e:
            original_workflow = node.workflow.get_original()
            error = (
                f"Error while resuming workflow {original_workflow.id}. Error: {str(e)}"
            )
            logger.exception(error)
            self._handle_workflow_error(node_history, iteration_path, error)
            return None

        # The state served its purpose. `resume_at` is kept: the history still
        # tells when the node resumed.
        node_history.resume_state = None
        automation_node_dispatch_resumed.send(
            sender=self, node=node, node_history=node_history
        )

        return self._complete_node_dispatch(
            node,
            node_history,
            dispatch_context,
            iteration_path,
            dispatch_result,
            current_iterations,
        )

    def _complete_node_dispatch(
        self,
        node: AutomationNode,
        node_history: AutomationNodeHistory,
        dispatch_context: AutomationDispatchContext,
        iteration_path: str,
        dispatch_result: DispatchResult,
        current_iterations: Optional[Dict[int, int]],
    ) -> Optional[Signature]:
        """Persists a node result and returns the canvas for its next nodes."""

        history_handler = AutomationHistoryHandler()
        node_type: Type[AutomationActionNodeType] = node.get_type()
        history_id = node_history.workflow_history_id
        simulate_until_node = dispatch_context.simulate_until_node

        # Mark the node history as completed, so that post-dispatch hooks
        # can accurately rely on the completed_on field.
        now = timezone.now()
        node_history.completed_on = now
        node_history.status = node_type.get_history_status(dispatch_result)
        node_history.save()

        # The post-dispatch hook should also be able to safely access the
        # node result, since the dispatch is considered completed, so this
        # should also come before the post-dispatch hook.
        history_handler.create_node_result(
            node_history=node_history,
            result=dispatch_result.data,
            iteration_path=iteration_path,
        )

        self._after_node_dispatch(node, node_history)

        # Deferred nodes reach the simulated target only after their child result is
        # available. Notify the frontend now and do not traverse later parent nodes.
        if self._handle_simulation_notify(simulate_until_node, node):
            return None

        to_chain = []
        if children := node.get_children(first_only=True):
            node_data = dispatch_result.data["results"]

            # For simulations, we only need the first iteration.
            if simulate_until_node:
                iterations = [0]
            else:
                iterations = range(len(node_data))

            groups_to_chain = []
            for index in iterations:
                child_iterations = {
                    **dispatch_context.current_iterations,
                    node.id: index,
                }
                groups_to_chain.append(
                    group(
                        [
                            dispatch_node_celery_task.si(
                                c.id, history_id, child_iterations
                            )
                            for c in children
                        ]
                    ),
                )

            if groups_to_chain:
                canvas = chain(*groups_to_chain)
                to_chain.append(canvas)

        if (
            dispatch_result.destination_service_id is not None
            and not simulate_until_node
        ):
            # A node (e.g. "Go to node") requested a jump to a specific node,
            # identified by its service, rather than the natural next node.
            # While simulating, the jump is never followed: execution walks the
            # natural path towards the simulated node instead of looping on it.
            next_node_ids = [
                self.get_node_by_service_id(dispatch_result.destination_service_id).id
            ]
        else:
            # Handle non-iterator nodes, including iterator children.
            next_node_ids = [
                n.id for n in node.get_next_points(dispatch_result.output_uid)
            ]

        if next_node_ids:
            to_chain.append(
                group(
                    [
                        dispatch_node_celery_task.si(
                            next_id, history_id, current_iterations
                        )
                        for next_id in next_node_ids
                    ]
                ),
            )

        if to_chain:
            return chain(*to_chain)
        else:
            # This is the end of this branch
            return None
