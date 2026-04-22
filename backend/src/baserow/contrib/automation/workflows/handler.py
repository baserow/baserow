from collections import defaultdict
from datetime import timedelta
from typing import Any, Dict, List, Optional
from zipfile import ZipFile

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from celery.canvas import Signature, chain
from opentelemetry import trace

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.constants import (
    IMPORT_SERIALIZED_IMPORTING,
    WORKFLOW_NAME_MAX_LEN,
)
from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.handler import AutomationHistoryHandler
from baserow.contrib.automation.history.models import AutomationWorkflowHistory
from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.signals import automation_node_updated
from baserow.contrib.automation.nodes.tasks import dispatch_node_celery_task
from baserow.contrib.automation.nodes.types import AutomationNodeDict
from baserow.contrib.automation.types import AutomationWorkflowDict
from baserow.contrib.automation.workflows.constants import (
    ALLOW_TEST_RUN_MINUTES,
    WorkflowState,
)
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowBeforeRunError,
    AutomationWorkflowDoesNotExist,
    AutomationWorkflowNotInAutomation,
    AutomationWorkflowRateLimited,
    AutomationWorkflowTooManyErrors,
)
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.signals import automation_workflow_updated
from baserow.contrib.automation.workflows.tasks import (
    handle_workflow_dispatch_done,
    start_workflow_celery_task,
)
from baserow.contrib.automation.workflows.types import UpdatedAutomationWorkflow
from baserow.core.cache import global_cache, local_cache
from baserow.core.exceptions import IdDoesNotExist
from baserow.core.registries import ImportExportConfig
from baserow.core.storage import ExportZipFile, get_default_storage
from baserow.core.telemetry.utils import baserow_trace_methods
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import (
    ChildProgressBuilder,
    MirrorDict,
    Progress,
    extract_allowed,
    find_unused_name,
)

WORKFLOW_HISTORY_RATE_LIMIT_CACHE_PREFIX = "automation_workflow_history_{}"
AUTOMATION_WORKFLOW_CACHE_LOCK_SECONDS = 5

tracer = trace.get_tracer(__name__)


class AutomationWorkflowHandler(metaclass=baserow_trace_methods(tracer)):
    allowed_fields = ["name", "allow_test_run_until", "state"]

    def get_workflow(
        self,
        workflow_id: int,
        base_queryset: Optional[QuerySet] = None,
        for_update: bool = False,
    ) -> AutomationWorkflow:
        """
        Gets an AutomationWorkflow by its ID.

        :param workflow_id: The ID of the AutomationWorkflow.
        :param base_queryset: Can be provided to already filter or apply performance
            improvements to the queryset when it's being executed.
        :param for_update: Ensure only one update can happen at a time.
        :raises AutomationWorkflowDoesNotExist: If the workflow doesn't exist.
        :return: The model instance of the AutomationWorkflow
        """

        if base_queryset is None:
            base_queryset = AutomationWorkflow.objects.all()

        if for_update:
            base_queryset = base_queryset.select_for_update(of=("self",))

        try:
            return base_queryset.select_related("automation__workspace").get(
                id=workflow_id
            )
        except AutomationWorkflow.DoesNotExist:
            raise AutomationWorkflowDoesNotExist()

    def get_published_workflow(
        self, workflow: AutomationWorkflow, with_cache: bool = True
    ) -> Optional[AutomationWorkflow]:
        """
        Gets the published AutomationWorkflow instance related to the
        provided workflow.

        :param workflow: The workflow for which the published version should
            be returned.
        :param with_cache: Whether to return a cached value, if available.
        :raises AutomationWorkflowDoesNotExist: If the workflow doesn't exist.
        :return: The published workflow, if it exists.
        """

        def _get_published_workflow(
            workflow: AutomationWorkflow,
        ) -> Optional[AutomationWorkflow]:
            latest_published = workflow.published_to.order_by("-id").first()
            return latest_published.workflows.first() if latest_published else None

        if with_cache:
            return local_cache.get(
                f"wa_published_workflow_{workflow.id}",
                lambda: _get_published_workflow(workflow),
            )

        return _get_published_workflow(workflow)

    def _invalidate_workflow_caches(self, workflow: AutomationWorkflow) -> None:
        original_workflow = workflow.get_original()

        global_cache.invalidate(f"wa_published_workflow_{original_workflow.id}")
        global_cache.invalidate(
            self._get_workflow_history_rate_limit_cache_key(original_workflow)
        )

    def get_workflows(
        self, automation: Automation, base_queryset: Optional[QuerySet] = None
    ) -> QuerySet:
        """
        Returns all the AutomationWorkflows in the provided automation.
        """

        if base_queryset is None:
            base_queryset = AutomationWorkflow.objects.all()

        return base_queryset.filter(automation=automation).prefetch_related(
            "automation__workspace"
        )

    def create_workflow(self, automation: Automation, name: str) -> AutomationWorkflow:
        """
        Creates a new AutomationWorkflow.

        :param automation: The Automation the workflow belongs to.
        :param name: The name of the workflow.
        :return: The newly created AutomationWorkflow instance.
        """

        last_order = AutomationWorkflow.get_last_order(automation)

        return AutomationWorkflow.objects.create(
            automation=automation,
            name=name,
            order=last_order,
        )

    def delete_workflow(self, user: AbstractUser, workflow: AutomationWorkflow) -> None:
        """
        Deletes the specified AutomationWorkflow.

        :param workflow: The AutomationWorkflow that must be deleted.
        """

        if published_workflow := self.get_published_workflow(workflow):
            published_workflow.delete()

        TrashHandler.trash(
            user, workflow.automation.workspace, workflow.automation, workflow
        )

    def export_prepared_values(self, workflow: AutomationWorkflow) -> Dict[Any, Any]:
        """
        Return a serializable dict of prepared values for the workflow attributes.

        It is called by undo/redo ActionHandler to store the values in a way that
        could be restored later.

        :param instance: The workflow instance to export values for.
        :return: A dict of prepared values.
        """

        return {key: getattr(workflow, key) for key in self.allowed_fields}

    def update_workflow(
        self, workflow: AutomationWorkflow, **kwargs
    ) -> UpdatedAutomationWorkflow:
        """
        Updates fields of the provided AutomationWorkflow.

        :param workflow: The AutomationWorkflow that should be updated.
        :param kwargs: The fields that should be updated with their
            corresponding values.
        :return: The updated AutomationWorkflow.
        """

        original_workflow_values = self.export_prepared_values(workflow)

        allowed_values = extract_allowed(kwargs, self.allowed_fields)

        # The state is a special value that should only be set on the
        # published workflow, if available.
        state = allowed_values.pop("state", None)
        if state is not None:
            if published_workflow := self.get_published_workflow(workflow):
                published_workflow.state = WorkflowState(state)
                published_workflow.save(update_fields=["state"])

        for key, value in allowed_values.items():
            setattr(workflow, key, value)

        workflow.save()

        new_workflow_values = self.export_prepared_values(workflow)

        return UpdatedAutomationWorkflow(
            workflow, original_workflow_values, new_workflow_values
        )

    def order_workflows(
        self, automation: Automation, order: List[int], base_qs=None
    ) -> List[int]:
        """
        Assigns a new order to the workflows in an Automation application.

        A base_qs can be provided to pre-filter the workflows affected by this change.

        :param automation: The Automation that the workflows belong to.
        :param order: The new order of the workflows.
        :param base_qs: A QS that can have filters already applied.
        :raises AutomationWorkflowNotInAutomation: If the workflow is not part of the
            provided automation.
        :return: The new order of the workflows.
        """

        if base_qs is None:
            base_qs = AutomationWorkflow.objects.filter(automation=automation)

        try:
            return AutomationWorkflow.order_objects(base_qs, order)
        except IdDoesNotExist as error:
            raise AutomationWorkflowNotInAutomation(error.not_existing_id)

    def get_workflows_order(self, automation: Automation) -> List[int]:
        """
        Returns the workflows in the automation ordered by the order field.

        :param automation: The automation that the workflows belong to.
        :return: A list containing the order of the workflows in the automation.
        """

        return [workflow.id for workflow in automation.workflows.order_by("order")]

    def duplicate_workflow(
        self,
        workflow: AutomationWorkflow,
        progress_automation: Optional[ChildProgressBuilder] = None,
    ):
        """
        Duplicates an existing AutomationWorkflow instance.

        :param workflow: The AutomationWorkflow that is being duplicated.
        :param progress_automation: A progress object that can be used to
            report progress.
        :raises ValueError: When the provided workflow is not an instance of
            AutomationWorkflow.
        :return: The duplicated workflow
        """

        start_progress, export_progress, import_progress = 10, 30, 60
        progress = ChildProgressBuilder.build(progress_automation, child_total=100)
        progress.increment(by=start_progress)

        automation = workflow.automation

        exported_workflow = self.export_workflow(workflow)

        # Set a unique name for the workflow to import back as a new one.
        exported_workflow["name"] = self.find_unused_workflow_name(
            automation, workflow.name
        )
        exported_workflow["order"] = AutomationWorkflow.get_last_order(automation)

        progress.increment(by=export_progress)

        id_mapping = defaultdict(lambda: MirrorDict())
        id_mapping["automation_workflows"] = MirrorDict()

        import_export_config = ImportExportConfig(
            include_permission_data=True,
            reduce_disk_space_usage=False,
            exclude_sensitive_data=False,
            is_duplicate=True,
        )

        new_workflow_clone = self.import_workflow(
            automation,
            exported_workflow,
            progress=progress.create_child_builder(represents_progress=import_progress),
            id_mapping=id_mapping,
            import_export_config=import_export_config,
        )

        return new_workflow_clone

    def find_unused_workflow_name(
        self, automation: Automation, proposed_name: str
    ) -> str:
        """
        Finds an unused name for a workflow in an automation.

        :param automation: The Automation instance that the workflow belongs to.
        :param proposed_name: The name that is proposed to be used.
        :return: A unique name to use.
        """

        # Since workflows can be trashed and potentially restored later,
        # when finding an unused name, we must consider the set of all
        # workflows including trashed ones.
        existing_workflow_names = list(
            AutomationWorkflow.objects_and_trash.filter(
                automation=automation
            ).values_list("name", flat=True)
        )
        return find_unused_name(
            [proposed_name], existing_workflow_names, max_length=WORKFLOW_NAME_MAX_LEN
        )

    def export_workflow(
        self,
        workflow: AutomationWorkflow,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, any]] = None,
    ) -> AutomationWorkflowDict:
        """
        Serializes the given workflow.

        :param workflow: The AutomationWorkflow instance to serialize.
        :param files_zip: A zip file to store files in necessary.
        :param storage: Storage to use.
        :param cache: A cache to use for storing temporary data.
        :return: The serialized version.
        """

        serialized_nodes = [
            AutomationNodeHandler().export_node(
                n, files_zip=files_zip, storage=storage, cache=cache
            )
            for n in AutomationNodeHandler().get_nodes(workflow=workflow)
        ]

        return AutomationWorkflowDict(
            id=workflow.id,
            name=workflow.name,
            order=workflow.order,
            nodes=serialized_nodes,
            state=workflow.state,
            graph=workflow.graph,
        )

    def _ops_count_for_import_workflow(
        self,
        serialized_workflows: List[Dict[str, Any]],
    ) -> int:
        """
        Count number of steps for the operation. Used to track task progress.
        """

        # Return zero for now, since we don't have Triggers and Actions yet.
        return 0

    def import_nodes(
        self,
        workflow: AutomationWorkflow,
        serialized_nodes: List[AutomationNodeDict],
        id_mapping: Dict[str, Dict[int, int]],
        import_export_config: Optional[ImportExportConfig] = None,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress: Optional[ChildProgressBuilder] = None,
        cache: Optional[Dict[str, Any]] = None,
    ) -> List[AutomationNode]:
        """
        Import nodes into the provided workflow.

        :param workflow: The AutomationWorkflow instance to import the nodes into.
        :param serialized_nodes: The serialized nodes to import.
        :param id_mapping: A map of old->new id per data type
        :param import_export_config: provides configuration options for the
            import/export process to customize how it works.
        :param files_zip: Contains files to import if any.
        :param storage: Storage to get the files from.
        :param progress: A progress object that can be used to report progress.
        :param cache: A cache to use for storing temporary data.
        :return: A list of the newly created nodes.
        """

        imported_nodes = []

        imported_nodes = AutomationNodeHandler().import_nodes(
            workflow,
            serialized_nodes,
            id_mapping,
            import_export_config=import_export_config,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            progress=progress,
        )

        return imported_nodes

    def import_workflows(
        self,
        automation: Automation,
        serialized_workflows: List[AutomationWorkflowDict],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress: Optional[ChildProgressBuilder] = None,
        cache: Optional[Dict[str, any]] = None,
        import_export_config: Optional[ImportExportConfig] = None,
    ) -> List[AutomationWorkflow]:
        """
        Import multiple workflows at once.

        :param automation: The Automation instance the new workflow should
            belong to.
        :param serialized_workflows: The serialized version of the workflows.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :param files_zip: Contains files to import if any.
        :param storage: Storage to get the files from.
        :param progress: A progress object that can be used to report progress.
        :param cache: A cache to use for storing temporary data.
        :return: the newly created instances.
        """

        if cache is None:
            cache = {}

        child_total = sum(
            self._ops_count_for_import_workflow(w) for w in serialized_workflows
        )
        progress = ChildProgressBuilder.build(progress, child_total=child_total)

        imported_workflows = []
        for serialized_workflow in serialized_workflows:
            workflow_instance = self.import_workflow_only(
                automation,
                serialized_workflow,
                id_mapping,
                files_zip=files_zip,
                storage=storage,
                progress=progress,
                cache=cache,
            )
            imported_workflows.append([workflow_instance, serialized_workflow])

        for workflow_instance, serialized_workflow in imported_workflows:
            self.import_nodes(
                workflow_instance,
                serialized_workflow["nodes"],
                id_mapping,
                import_export_config=import_export_config,
                files_zip=files_zip,
                storage=storage,
                progress=progress,
                cache=cache,
            )

            workflow_instance.get_graph().migrate_graph(id_mapping)

        return [i[0] for i in imported_workflows]

    def import_workflow(
        self,
        automation: Automation,
        serialized_workflow: AutomationWorkflowDict,
        id_mapping: Dict[str, Dict[int, int]],
        import_export_config: Optional[ImportExportConfig] = None,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress: Optional[ChildProgressBuilder] = None,
        cache: Optional[Dict[str, any]] = None,
    ) -> AutomationWorkflow:
        """
        Creates an instance of AutomationWorkflow using the serialized version
        previously exported with `.export_workflow`.

        :param automation: The Automation instance the new workflow should
            belong to.
        :param serialized_workflow: The serialized version of the
            AutomationWorkflow.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :param files_zip: Contains files to import if any.
        :param storage: Storage to get the files from.
        :param progress: A progress object that can be used to report progress.
        :param cache: A cache to use for storing temporary data.
        :return: the newly created instance.
        """

        return self.import_workflows(
            automation,
            [serialized_workflow],
            id_mapping,
            import_export_config=import_export_config,
            files_zip=files_zip,
            storage=storage,
            progress=progress,
            cache=cache,
        )[0]

    def import_workflow_only(
        self,
        automation: Automation,
        serialized_workflow: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        progress: Optional[ChildProgressBuilder] = None,
        *args: Any,
        **kwargs: Any,
    ):
        if "automation_workflows" not in id_mapping:
            id_mapping["automation_workflows"] = {}

        workflow_instance = AutomationWorkflow.objects.create(
            automation=automation,
            name=serialized_workflow["name"],
            order=serialized_workflow["order"],
            state=serialized_workflow["state"] or WorkflowState.DRAFT,
            graph=serialized_workflow.get("graph", {}),
        )

        id_mapping["automation_workflows"][serialized_workflow["id"]] = (
            workflow_instance.id
        )

        if progress is not None:
            progress.increment(state=IMPORT_SERIALIZED_IMPORTING)

        return workflow_instance

    def clean_up_previously_published_automations(
        self, workflow: AutomationWorkflow
    ) -> None:
        published_automations = list(
            Automation.objects.filter(published_from=workflow).order_by("id")
        )
        if not published_automations:
            return

        if len(published_automations) > 1:
            # Delete all but the last published automation
            ids_to_delete = [a.id for a in published_automations[:-1]]
            Automation.objects.filter(id__in=ids_to_delete).delete()

        # Disable the last published workflow
        if published_workflow := published_automations[-1].workflows.first():
            published_workflow.state = WorkflowState.DISABLED
            published_workflow.save(update_fields=["state"])

    def publish(
        self,
        workflow: AutomationWorkflow,
        progress: Optional[Progress] = None,
    ) -> AutomationWorkflow:
        """
        Publishes an Automation and a specific workflow. If the automation was
        already published, the previous versions are deleted and a new one
        is created.

        When an automation is published, a clone of the current version is
        created to avoid further modifications to the original automation
        which could affect the published version.

        :param workflow: The workflow to be published.
        :param progress: An object to track the publishing progress.
        :return: The published workflow.
        """

        # Make sure we are the only process to update the automation workflow
        # to prevent race conditions.
        workflow = self.get_workflow(workflow.id, for_update=True)

        self.clean_up_previously_published_automations(workflow)

        import_export_config = ImportExportConfig(
            include_permission_data=True,
            reduce_disk_space_usage=False,
            exclude_sensitive_data=False,
            is_publishing=True,
        )
        default_storage = get_default_storage()
        application_type = workflow.automation.get_type()

        exported_automation = application_type.export_serialized(
            workflow.automation,
            import_export_config,
            None,
            default_storage,
            workflows=[workflow],
        )

        # Manually set the published status for the newly created workflow.
        exported_automation["workflows"][0]["state"] = WorkflowState.LIVE

        progress_builder = None
        if progress:
            progress.increment(by=50)
            progress_builder = progress.create_child_builder(represents_progress=50)

        id_mapping = {"import_workspace_id": workflow.automation.workspace.id}

        duplicate_automation = application_type.import_serialized(
            None,
            exported_automation,
            import_export_config,
            id_mapping,
            None,
            default_storage,
            progress_builder=progress_builder,
        )

        duplicate_automation.published_from = workflow
        duplicate_automation.save(update_fields=["published_from"])

        self._invalidate_workflow_caches(workflow)

        return duplicate_automation.workflows.first()

    def disable_workflow(self, workflow: AutomationWorkflow) -> None:
        """
        Disable the provided workflow, as well as the original workflow.
        """

        original_workflow = workflow.get_original()

        # The two workflows are always different because we call it only for published
        # workflows
        workflow.state = WorkflowState.DISABLED
        workflow.save(update_fields=["state"])
        original_workflow.state = WorkflowState.DISABLED
        original_workflow.save(update_fields=["state"])

        automation_workflow_updated.send(self, user=None, workflow=original_workflow)

    def set_workflow_temporary_states(self, workflow, simulate_until_node=None):
        """
        Sets the temporary states necessary to allow an unpublished workflow to be
        ran by the next event. By default a full test run is scheduled unless the
        simulate_until_node parameter is used.

        :param workflow: The workflow to consider.
        :param simulate_until_node: If set, schedules a simulation run instead.
        """

        fields_to_save = []
        if simulate_until_node is not None:
            # Switch to simulate until the given node
            workflow.simulate_until_node = simulate_until_node

            automation_node_updated.send(self, user=None, node=simulate_until_node)

            fields_to_save.append("simulate_until_node")

        else:
            # Full test run
            workflow.allow_test_run_until = timezone.now() + timedelta(
                minutes=ALLOW_TEST_RUN_MINUTES
            )
            fields_to_save.append("allow_test_run_until")

        if fields_to_save:
            workflow.save(update_fields=fields_to_save)
            automation_workflow_updated.send(self, user=None, workflow=workflow)

    def reset_workflow_temporary_states(self, workflow):
        """
        Reset the temporary states set when we want to test or simulate a workflow.
        This should be executed after an event for this workflow is received.
        """

        fields_to_save = []
        if workflow.allow_test_run_until:
            workflow.allow_test_run_until = None
            fields_to_save.append("allow_test_run_until")

        if workflow.simulate_until_node:
            workflow.simulate_until_node = None
            fields_to_save.append("simulate_until_node")

        if fields_to_save:
            workflow.save(update_fields=fields_to_save)
            automation_workflow_updated.send(self, user=None, workflow=workflow)

    def toggle_test_run(
        self, workflow: AutomationWorkflow, simulate_until_node: bool = None
    ):
        """
        Trigger a test run if none is in progress or cancel the planned run. If the
        workflow can immediately be dispatched, it will be by this function, otherwise
        the workflow is switched in "listening" state and wait for the trigger event to
        happens. When in simulate mode, the sample data of the simulated node will be
        updated.

        :param workflow: The workflow we want to trigger the test run for.
        :param simulate_until_node: If we want to simulate until a particular node.
        """

        if workflow.simulate_until_node is not None or workflow.allow_test_run_until:
            # We just stop waiting for the event
            self.reset_workflow_temporary_states(workflow)
            return

        if simulate_until_node is None:  # Full test
            AutomationWorkflowHandler().set_workflow_temporary_states(workflow)
            if workflow.can_immediately_be_tested():
                # If the service related to the trigger can immediately be tested
                # we immediately trigger the workflow run
                self.async_start_workflow(workflow)

        else:
            AutomationWorkflowHandler().set_workflow_temporary_states(
                workflow, simulate_until_node=simulate_until_node
            )
            trigger = workflow.get_trigger()

            dispatch_context = AutomationDispatchContext(
                workflow,
                # This is a placeholder value, no actual history exists yet
                # (it's created later in start_workflow). This is fine
                # for now, because get_sample_data() doesn't use history.
                history=None,
                simulate_until_node=simulate_until_node,
            )
            if workflow.can_immediately_be_tested() or (
                trigger.service.get_type().get_sample_data(
                    trigger.service.specific, dispatch_context
                )
                is not None
                and trigger.id != simulate_until_node.id
            ):
                # If the trigger is immediately dispatchable or if we already have
                # the sample data for it we can immediately dispatch the workflow
                # except if we are updating the trigger sample data by itself
                self.async_start_workflow(workflow)

    def _clear_old_history(self, original_workflow: AutomationWorkflow) -> None:
        """
        Clear any old history entries related to the workflow.

        It will delete any history entries that are older than MAX_HISTORY_DAYS and only
        keep the most recent MAX_HISTORY_ENTRIES entries.
        """

        oldest_history_date = timezone.now() - timedelta(
            days=settings.AUTOMATION_WORKFLOW_HISTORY_MAX_DAYS
        )
        original_workflow.workflow_histories.exclude(
            status=HistoryStatusChoices.STARTED
        ).filter(started_on__lt=oldest_history_date).delete()

        history_ids_to_keep = list(
            original_workflow.workflow_histories.order_by("-started_on").values_list(
                "id", flat=True
            )[: settings.AUTOMATION_WORKFLOW_HISTORY_MAX_ENTRIES]
        )
        original_workflow.workflow_histories.exclude(
            status=HistoryStatusChoices.STARTED
        ).exclude(id__in=history_ids_to_keep).delete()

    def _mark_failure_for_timed_out_history(
        self, original_workflow: AutomationWorkflow
    ) -> None:
        """
        If an history entry is still not finished after a certain duration, this execution
        is marked as failed.
        """

        max_history_date = timezone.now() - timedelta(
            hours=settings.AUTOMATION_WORKFLOW_TIMEOUT_HOURS
        )
        original_workflow.workflow_histories.filter(
            status=HistoryStatusChoices.STARTED, started_on__lt=max_history_date
        ).update(
            status=HistoryStatusChoices.ERROR,
            message="This workflow took too long and was timed out.",
        )

    def _get_workflow_history_rate_limit_cache_key(
        self, original_workflow: AutomationWorkflow
    ) -> str:
        return WORKFLOW_HISTORY_RATE_LIMIT_CACHE_PREFIX.format(original_workflow.id)

    def _get_histories_for_current_workflow_version(self, workflow: AutomationWorkflow):
        original_workflow = workflow.get_original()
        histories = AutomationHistoryHandler().get_workflow_histories(original_workflow)

        if workflow != original_workflow:
            histories = histories.filter(started_on__gte=workflow.created_on)

        return histories

    def _check_is_rate_limited(self, workflow: AutomationWorkflow) -> bool:
        """
        Checks workflow histories against the configured rate limit windows.

        The histories are fetched once for the largest configured window and each
        smaller window is evaluated in Python to avoid issuing one COUNT query per
        configured rate limit.

        Raises AutomationWorkflowRateLimited when the workflow exceeds one of the
        configured rate limits.
        """

        rate_limits = settings.AUTOMATION_WORKFLOW_RATE_LIMITS
        if not rate_limits:
            return False

        now = timezone.now()
        largest_window_seconds = max(
            window_seconds for _, window_seconds in rate_limits
        )
        oldest_start_window = now - timedelta(seconds=largest_window_seconds)
        history_windows = list(
            self._get_histories_for_current_workflow_version(workflow)
            .filter(
                Q(started_on__gte=oldest_start_window)
                | Q(status=HistoryStatusChoices.STARTED)
            )
            .order_by()
            .values_list("started_on", "status")
        )

        for max_runs, window_seconds in rate_limits:
            start_window = now - timedelta(seconds=window_seconds)
            if (
                sum(
                    started_on >= start_window or status == HistoryStatusChoices.STARTED
                    for started_on, status in history_windows
                )
                >= max_runs
            ):
                raise AutomationWorkflowRateLimited(
                    "The workflow was rate limited due to too many recent or "
                    f"unfinished runs. Limit exceeded: {max_runs} runs in "
                    f"{window_seconds} seconds."
                )

        return False

    def _check_too_many_errors(self, workflow: AutomationWorkflow) -> bool:
        """
        Checks if the given workflow has too many consecutive errors. If so,
        raises AutomationWorkflowTooManyErrors.
        """

        original_workflow = workflow.get_original()

        if original_workflow == workflow:
            # We don't want to rate limit a test execution or a simulation
            return False

        max_errors = settings.AUTOMATION_WORKFLOW_MAX_CONSECUTIVE_ERRORS

        statuses = (
            self._get_histories_for_current_workflow_version(workflow)
            .exclude(status=HistoryStatusChoices.STARTED)
            .order_by("-started_on")
            .values_list("status", flat=True)[: max_errors + 1]
        )

        return (
            len([s for s in statuses if s == HistoryStatusChoices.ERROR]) > max_errors
        )

    def before_run(self, workflow: AutomationWorkflow) -> None:
        """
        Runs pre-flight checks  and actions before a workflow is allowed to run.

        Each check may raise a subclass of the AutomationWorkflowBeforeRunError error.
        """

        original_workflow = workflow.get_original()

        # If we don't come from an event, we need to reset the states to prevent
        # another execution
        self.reset_workflow_temporary_states(original_workflow)

        # If we have history entries that are too old it probably means something
        # went wrong with Celery so we mark these entries as failed.
        self._mark_failure_for_timed_out_history(original_workflow)

        # We remove old history entries to avoid storing too many entries.
        self._clear_old_history(original_workflow)

        if self._check_too_many_errors(workflow):
            raise AutomationWorkflowTooManyErrors(
                "The workflow was disabled due to too many consecutive errors."
            )

        self._check_is_rate_limited(workflow)

    def async_start_workflow(
        self,
        workflow: AutomationWorkflow,
        event_payload: Optional[List[Dict]] = None,
    ) -> None:
        """
        Runs the provided workflow in a celery task.

        :param workflow: The AutomationWorkflow ID that should be executed.
        :param event_payload: The payload from the action.
        """

        error = None
        history_status = HistoryStatusChoices.ERROR
        create_history_entry = True

        original_workflow = workflow.get_original()

        simulate_until_node = (
            workflow.get_graph().get_node(workflow.simulate_until_node_id)
            if workflow.simulate_until_node_id
            else None
        )

        try:
            self.before_run(workflow)
        except AutomationWorkflowRateLimited as e:
            history_cache_timeout = (
                settings.AUTOMATION_WORKFLOW_HISTORY_RATE_LIMIT_CACHE_EXPIRY_SECONDS
            )
            history_cache_key = self._get_workflow_history_rate_limit_cache_key(
                original_workflow
            )

            error = str(e)
            # We create an history entry only if we don't have a value in the cache
            # It limits the number of created history entry to one every
            # AUTOMATION_WORKFLOW_HISTORY_RATE_LIMIT_CACHE_EXPIRY_SECONDS seconds
            if global_cache.get(
                history_cache_key, default=True, timeout=history_cache_timeout
            ):
                # Set the value to prevent next executions
                global_cache.update(
                    history_cache_key,
                    lambda v: False,
                    timeout=history_cache_timeout,
                )
            else:
                create_history_entry = False
        except AutomationWorkflowTooManyErrors as e:
            error = str(e)
            history_status = HistoryStatusChoices.DISABLED
            self.disable_workflow(workflow)
        except AutomationWorkflowBeforeRunError as e:
            error = str(e)
        except Exception as e:
            error = f"Unknown exception: {str(e)}"

        if error:
            if create_history_entry and simulate_until_node is None:
                now = timezone.now()

                AutomationHistoryHandler().create_workflow_history(
                    original_workflow,
                    is_test_run=original_workflow == workflow,
                    started_on=now,
                    completed_on=now,
                    message=error,
                    status=history_status,
                )
            return

        # If the currently running workflow is an unpublished workflow then we are
        # testing it.
        is_test_run = original_workflow == workflow

        history = AutomationHistoryHandler().create_workflow_history(
            original_workflow,
            started_on=timezone.now(),
            is_test_run=is_test_run,
            event_payload=event_payload,
            simulate_until_node=simulate_until_node,
        )

        transaction.on_commit(
            lambda: start_workflow_celery_task.delay(workflow.id, history.id)
        )

    def start_workflow(
        self,
        workflow: AutomationWorkflow,
        history: AutomationWorkflowHistory,
    ) -> Signature:
        """Runs the workflow."""

        return chain(
            dispatch_node_celery_task.si(
                workflow.get_trigger().id,
                history.id,
            ),
            handle_workflow_dispatch_done.si(
                history_id=history.id,
                simulate_until_node_id=history.simulate_until_node_id,
            ),
        )
