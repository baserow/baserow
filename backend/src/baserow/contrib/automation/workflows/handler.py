from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from zipfile import ZipFile

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db import IntegrityError
from django.db.models import QuerySet
from django.utils import timezone

from loguru import logger
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
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.signals import automation_node_updated
from baserow.contrib.automation.nodes.types import AutomationNodeDict
from baserow.contrib.automation.types import AutomationWorkflowDict
from baserow.contrib.automation.workflows.constants import (
    ALLOW_TEST_RUN_MINUTES,
    WorkflowState,
)
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowBeforeRunError,
    AutomationWorkflowDoesNotExist,
    AutomationWorkflowNameNotUnique,
    AutomationWorkflowNotInAutomation,
    AutomationWorkflowRateLimited,
    AutomationWorkflowTooManyErrors,
)
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.signals import automation_workflow_updated
from baserow.contrib.automation.workflows.tasks import start_workflow_celery_task
from baserow.contrib.automation.workflows.types import UpdatedAutomationWorkflow
from baserow.core.cache import global_cache, local_cache
from baserow.core.exceptions import IdDoesNotExist
from baserow.core.psycopg import is_unique_violation_error
from baserow.core.registries import ImportExportConfig
from baserow.core.services.exceptions import DispatchException
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

WORKFLOW_RATE_LIMIT_CACHE_PREFIX = "automation_workflow_{}"
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

    def get_original_workflow(
        self, workflow: AutomationWorkflow
    ) -> Optional[AutomationWorkflow]:
        """
        Gets the original workflow related to the provided published
        AutomationWorkflow instance.

        If the workflow isn't published but allow_test_run_until is set,
        it indicates that the provided workflow is the one being run. Thus the
        same workflow is returned.

        :param workflow: The published workflow for which the original version
            should be returned.
        :return: The original workflow, if it exists.
        """

        if workflow.automation.published_from_id:
            return workflow.automation.published_from
        else:
            return workflow

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

        # Find a name unused in a trashed or existing workflow
        unused_name = self.find_unused_workflow_name(automation, name)

        try:
            workflow = AutomationWorkflow.objects.create(
                automation=automation,
                name=unused_name,
                order=last_order,
            )
        except IntegrityError as e:
            if "unique constraint" in e.args[0] and "name" in e.args[0]:
                raise AutomationWorkflowNameNotUnique(
                    name=name, automation_id=automation.id
                ) from e
            raise

        return workflow

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

        try:
            workflow.save()
        except IntegrityError as e:
            if is_unique_violation_error(e) and "name" in str(e):
                raise AutomationWorkflowNameNotUnique(
                    name=workflow.name, automation_id=workflow.automation_id
                ) from e
            raise

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

        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

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

        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

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

        id_mapping["automation_workflows"][
            serialized_workflow["id"]
        ] = workflow_instance.id

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

        return duplicate_automation.workflows.first()

    def before_run(self, workflow: AutomationWorkflow) -> None:
        """
        Runs pre-flight checks before a workflow is allowed to run.

        Each check may raise a subclass of the AutomationWorkflowBeforeRunError error.
        """

        # If we don't come from an event, we need to reset the states
        self.reset_workflow_temporary_states(workflow)

        self._check_too_many_errors(workflow)
        self._check_is_rate_limited(workflow.id)

    def _get_rate_limit_cache_key(self, workflow_id: int) -> str:
        return WORKFLOW_RATE_LIMIT_CACHE_PREFIX.format(workflow_id)

    def _check_is_rate_limited(self, workflow_id: int) -> None:
        """Uses a global cache key to track recent runs for the given workflow."""

        expiry_seconds = settings.AUTOMATION_WORKFLOW_RATE_LIMIT_CACHE_EXPIRY_SECONDS
        cache_key = self._get_rate_limit_cache_key(workflow_id)

        global_cache.update(
            cache_key,
            self._check_is_rate_limited_value,
            default_value=lambda: [],
            timeout=expiry_seconds,
        )

    def _check_is_rate_limited_value(self, data: List[datetime]) -> List[datetime]:
        """
        Given a list of recent workflow run timestamps, determines whether
        the workflow run should be rate limited. If so, raises the
        AutomationWorkflowRateLimited error.
        """

        now = timezone.now()
        expiry_seconds = settings.AUTOMATION_WORKFLOW_RATE_LIMIT_CACHE_EXPIRY_SECONDS
        start_window = now - timedelta(seconds=expiry_seconds)

        # Check the number of past runs that are in the window
        runs_in_window = [
            timestamp
            for timestamp in data
            if isinstance(timestamp, datetime) and timestamp > start_window
        ]

        if len(runs_in_window) >= settings.AUTOMATION_WORKFLOW_RATE_LIMIT_MAX_RUNS:
            raise AutomationWorkflowRateLimited(
                "The workflow was rate limited due to too many recent runs."
            )

        runs_in_window.append(now)

        return runs_in_window

    def _check_too_many_errors(self, workflow: AutomationWorkflow) -> None:
        """
        Checks if the given workflow has too many consecutive errors. If so,
        raises AutomationWorkflowTooManyErrors.
        """

        max_errors = settings.AUTOMATION_WORKFLOW_MAX_CONSECUTIVE_ERRORS

        statuses = (
            AutomationWorkflowHistory.objects.filter(workflow=workflow).order_by(
                "-started_on"
            )
            # +1 because we will ignore the latest entry, since the workflow may
            # have just started.
            .values_list("status", flat=True)[: max_errors + 1]
        )

        # Ignore the latest status if it is 'started'
        if statuses and statuses[0] == HistoryStatusChoices.STARTED:
            statuses = statuses[1:]

        # Not enough history to exceed threshold
        if len(statuses) < max_errors:
            return

        if all(status == HistoryStatusChoices.ERROR for status in statuses):
            raise AutomationWorkflowTooManyErrors(
                f"The workflow {workflow.id} was disabled due to too "
                "many consecutive errors."
            )

    def disable_workflow(self, workflow: AutomationWorkflow) -> None:
        """
        Disable the provided workflow, as well as the original workflow if it exists.
        """

        workflow_ids = {workflow.id}
        if original_workflow := self.get_original_workflow(workflow):
            workflow_ids.add(original_workflow.id)

        AutomationWorkflow.objects.filter(id__in=workflow_ids).update(
            state=WorkflowState.DISABLED
        )

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

        start_workflow_celery_task.delay(
            workflow.id,
            event_payload,
            simulate_until_node_id=workflow.simulate_until_node_id,
        )

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
        :param simulated_until_node: If we want to simulate until a particular node.
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
                None,
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

    def start_workflow(
        self,
        workflow: int,
        event_payload: Optional[Union[Dict, List[Dict]]],
        simulate_until_node: Optional[int] = None,
    ) -> None:
        """Runs the workflow."""

        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

        original_workflow = self.get_original_workflow(workflow)

        # If the currently running workflow is an unpublished workflow then we are
        # testing it.
        is_test_run = original_workflow == workflow

        is_simulation = simulate_until_node is not None

        dispatch_context = AutomationDispatchContext(
            workflow,
            event_payload,
            simulate_until_node=simulate_until_node,
        )

        start_time = timezone.now()

        history_handler = AutomationHistoryHandler()

        if not is_simulation:
            # No history stored in simulation, we want to populate the node sample data
            history = history_handler.create_workflow_history(
                original_workflow,
                started_on=start_time,
                is_test_run=is_test_run,
            )

        try:
            self.before_run(original_workflow)
            AutomationNodeHandler().dispatch_node(
                workflow.get_trigger(), dispatch_context
            )
        except AutomationWorkflowTooManyErrors as e:
            history_message = str(e)
            history_status = HistoryStatusChoices.DISABLED
            self.disable_workflow(workflow)
        except (DispatchException, AutomationWorkflowBeforeRunError) as e:
            history_message = str(e)
            history_status = HistoryStatusChoices.ERROR
        except Exception as e:
            history_message = (
                f"Unexpected error while running workflow {original_workflow.id}. "
                f"Error: {str(e)}"
            )
            history_status = HistoryStatusChoices.ERROR
            logger.exception(history_message)
        else:
            history_message = ""
            history_status = HistoryStatusChoices.SUCCESS
        finally:
            if not is_simulation:
                history.completed_on = timezone.now()
                history.message = history_message
                history.status = history_status
                history.save()
            else:
                # sample_data was updated as it's a simulation we should tell to
                # the frontend
                simulate_until_node.service.specific.refresh_from_db(
                    fields=["sample_data"]
                )
                automation_node_updated.send(self, user=None, node=simulate_until_node)
