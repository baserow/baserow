from collections import defaultdict
from typing import Any, Dict, List, Optional
from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db import IntegrityError
from django.db.models import QuerySet

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.constants import (
    IMPORT_SERIALIZED_IMPORTING,
    WORKFLOW_NAME_MAX_LEN,
)
from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.types import AutomationWorkflowDict
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowDoesNotExist,
    AutomationWorkflowNameNotUnique,
    AutomationWorkflowNotInAutomation,
)
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.types import UpdatedAutomationWorkflow
from baserow.core.exceptions import IdDoesNotExist
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import (
    ChildProgressBuilder,
    MirrorDict,
    extract_allowed,
    find_unused_name,
)


class AutomationWorkflowHandler:
    allowed_fields = ["name"]

    def run_workflow(
        self, workflow: AutomationWorkflow, dispatch_context: AutomationDispatchContext
    ):
        """
        Runs the provided workflow.

        :param workflow: The AutomationWorkflow that should be executed.
        :param dispatch_context: The context used for the dispatch.
        """

        # todo should create the dispatch context using the event_payload
        # and run the next action nodes following the trigger

        print(f"Executing workflow={workflow.id}")

    def get_workflow(
        self, workflow_id: int, base_queryset: Optional[QuerySet] = None
    ) -> AutomationWorkflow:
        """
        Gets an AutomationWorkflow by its ID.

        :param workflow_id: The ID of the AutomationWorkflow.
        :param base_queryset: Can be provided to already filter or apply performance
            improvements to the queryset when it's being executed.
        :raises AutomationWorkflowDoesNotExist: If the workflow doesn't exist.
        :return: The model instance of the AutomationWorkflow
        """

        if base_queryset is None:
            base_queryset = AutomationWorkflow.objects

        try:
            return base_queryset.select_related("automation__workspace").get(
                id=workflow_id
            )
        except AutomationWorkflow.DoesNotExist:
            raise AutomationWorkflowDoesNotExist()

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
        *args: Any,
        **kwargs: Any,
    ) -> List[AutomationWorkflowDict]:
        """
        Serializes the given workflow.

        :param workflow: The AutomationWorkflow instance to serialize.
        :param files_zip: A zip file to store files in necessary.
        :param storage: Storage to use.
        :return: The serialized version.
        """

        return AutomationWorkflowDict(
            id=workflow.id,
            name=workflow.name,
            order=workflow.order,
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

    def import_workflows(
        self,
        automation: Automation,
        serialized_workflows: List[Dict[str, Any]],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress: Optional[ChildProgressBuilder] = None,
        cache: Optional[Dict[str, any]] = None,
    ):
        """
        Import multiple workflows at once.

        :param automation: The Automation instance the new workflow should
            belong to.
        :param serialized_workflows: The serialized version of the workflows.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :param files_zip: Contains files to import if any.
        :param storage: Storage to get the files from.
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

        return [i[0] for i in imported_workflows]

    def import_workflow(
        self,
        automation: Automation,
        serialized_workflow: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress: Optional[ChildProgressBuilder] = None,
        cache: Optional[Dict[str, any]] = None,
    ) -> AutomationWorkflow:
        """
        Creates an instance of AutomationWorkflow using the serialized version
        previously exported with `.export_workflow'.

        :param automation: The Automation instance the new workflow should
            belong to.
        :param serialized_workflow: The serialized version of the
            AutomationWorkflow.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :param files_zip: Contains files to import if any.
        :param storage: Storage to get the files from.
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
        )

        id_mapping["automation_workflows"][
            serialized_workflow["id"]
        ] = workflow_instance.id

        if progress is not None:
            progress.increment(state=IMPORT_SERIALIZED_IMPORTING)

        return workflow_instance
