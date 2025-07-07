from collections import defaultdict
from typing import Any, Dict, List, Optional
from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db import IntegrityError
from django.db.models import QuerySet

from baserow.contrib.automation.constants import (
    IMPORT_SERIALIZED_IMPORTING,
    WORKFLOW_NAME_MAX_LEN,
)
from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.types import AutomationNodeDict
from baserow.contrib.automation.types import AutomationWorkflowDict
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowDoesNotExist,
    AutomationWorkflowNameNotUnique,
    AutomationWorkflowNotInAutomation,
)
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.tasks import run_workflow
from baserow.contrib.automation.workflows.types import UpdatedAutomationWorkflow
from baserow.core.cache import local_cache
from baserow.core.exceptions import IdDoesNotExist
from baserow.core.registries import ImportExportConfig
from baserow.core.storage import ExportZipFile, get_default_storage
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import (
    ChildProgressBuilder,
    MirrorDict,
    Progress,
    extract_allowed,
    find_unused_name,
)


class AutomationWorkflowHandler:
    allowed_fields = ["name", "allow_test_run_until", "paused"]

    def run_workflow(
        self, workflow_id: int, event_payload: Optional[List[Dict]] = None
    ) -> None:
        """
        Runs the provided workflow.

        :param workflow_id: The AutomationWorkflow ID that should be executed.
        :param event_payload: The payload from the action.
        """

        run_workflow.delay(workflow_id, event_payload)

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
                )
            raise

        return workflow

    def delete_workflow(self, user: AbstractUser, workflow: AutomationWorkflow) -> None:
        """
        Deletes the specified AutomationWorkflow.

        :param workflow: The AutomationWorkflow that must be deleted.
        """

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

        # paused is a special value that should only be set on the
        # published workflow, if available.
        paused = allowed_values.pop("paused", None)
        if paused is not None:
            if published_workflow := self.get_published_workflow(workflow):
                published_workflow.paused = paused
                published_workflow.save(update_fields=["paused"])

        for key, value in allowed_values.items():
            setattr(workflow, key, value)

        try:
            workflow.save()
        except IntegrityError as e:
            if "unique constraint" in e.args[0] and "name" in e.args[0]:
                raise AutomationWorkflowNameNotUnique(
                    name=workflow.name, automation_id=workflow.automation_id
                )
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

        new_workflow_clone = self.import_workflow(
            automation,
            exported_workflow,
            progress=progress.create_child_builder(represents_progress=import_progress),
            id_mapping=id_mapping,
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

    def _sort_serialized_nodes_by_priority(
        self, serialized_nodes: List[AutomationNodeDict]
    ) -> List[AutomationNodeDict]:
        """
        Sorts the serialized nodes so that root-level nodes (those without a parent)
        are first, and then sorts by their `order` ASC.
        """

        def _node_priority_sort(n):
            return n.get("parent_node_id") is not None, n.get("order", 0)

        return sorted(serialized_nodes, key=_node_priority_sort)

    def import_nodes(
        self,
        workflow: AutomationWorkflow,
        serialized_nodes: List[AutomationNodeDict],
        id_mapping: Dict[str, Dict[int, int]],
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
        :param files_zip: Contains files to import if any.
        :param storage: Storage to get the files from.
        :param progress: A progress object that can be used to report progress.
        :param cache: A cache to use for storing temporary data.
        :return: A list of the newly created nodes.
        """

        from baserow.contrib.automation.nodes.handler import AutomationNodeHandler

        imported_nodes = []
        prioritized_nodes = self._sort_serialized_nodes_by_priority(serialized_nodes)

        # True if we have imported at least one node on last iteration
        was_imported = True
        while was_imported:
            was_imported = False
            workflow_node_mapping = id_mapping.get("automation_workflow_nodes", {})

            for serialized_node in prioritized_nodes:
                parent_node_id = serialized_node["parent_node_id"]
                # check that the node has not already been imported in a
                # previous pass or if the parent doesn't exist yet.
                if serialized_node["id"] not in workflow_node_mapping and (
                    parent_node_id is None or parent_node_id in workflow_node_mapping
                ):
                    imported_node = AutomationNodeHandler().import_node(
                        workflow,
                        serialized_node,
                        id_mapping,
                        files_zip=files_zip,
                        storage=storage,
                        cache=cache,
                    )

                    imported_nodes.append(imported_node)

                    was_imported = True
                    if progress:
                        progress.increment(state=IMPORT_SERIALIZED_IMPORTING)

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
                files_zip=files_zip,
                storage=storage,
                progress=progress,
                cache=cache,
            )

        return [i[0] for i in imported_workflows]

    def import_workflow(
        self,
        automation: Automation,
        serialized_workflow: AutomationWorkflowDict,
        id_mapping: Dict[str, Dict[int, int]],
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
            published=serialized_workflow.get("published") or False,
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
        published_automations = list(Automation.objects.filter(published_from=workflow))
        if not published_automations:
            return

        if len(published_automations) > 1:
            # Delete all but the last published automation
            ids_to_delete = [a.id for a in published_automations[:-1]]
            Automation.objects.filter(id__in=ids_to_delete).delete()

        # Disable the last published workflow
        published_workflow = published_automations[-1].workflows.first()
        published_workflow.published = False
        published_workflow.save(update_fields=["published"])

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
        exported_automation["workflows"][0]["published"] = True
        exported_automation["workflows"][0]["paused"] = False
        exported_automation["workflows"][0]["disabled_on"] = None

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
