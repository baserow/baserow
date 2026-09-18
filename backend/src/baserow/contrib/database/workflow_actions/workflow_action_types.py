from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional
from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db.models import Manager, Prefetch, QuerySet

from rest_framework import serializers

from baserow.contrib.database.api.workflow_actions.serializers import (
    DatabasePolymorphicServiceSerializer,
)
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionInvalidIntegration,
)
from baserow.contrib.database.workflow_actions.models import (
    CoreHTTPRequestWorkflowAction,
    CoreSMTPEmailWorkflowAction,
    CoreStartWorkflowWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    LocalBaserowUpdateRowWorkflowAction,
    OpenUrlWorkflowAction,
    SlackWriteMessageWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    DatabaseWorkflowActionType,
)
from baserow.contrib.database.workflow_actions.types import DatabaseWorkflowActionDict
from baserow.contrib.integrations.core.service_types import (
    CoreHTTPRequestServiceType,
    CoreSMTPEmailServiceType,
    CoreStartWorkflowServiceType,
)
from baserow.contrib.integrations.local_baserow.mixins import (
    UpdateRowRequiresRowIdMixin,
)
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowDeleteRowServiceType,
    LocalBaserowUpsertRowServiceType,
)
from baserow.contrib.integrations.slack.integration_types import SlackBotIntegrationType
from baserow.contrib.integrations.slack.service_types import (
    SlackWriteMessageServiceType,
)
from baserow.core.db import specific_queryset
from baserow.core.exceptions import PermissionException
from baserow.core.formula.serializers import FormulaSerializerField
from baserow.core.handler import CoreHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.operations import ReadIntegrationOperationType
from baserow.core.models import Workspace
from baserow.core.registries import ImportExportConfig
from baserow.core.registry import Instance
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.mixins import ServiceBackedTypeMixin
from baserow.core.services.models import Service
from baserow.core.services.registries import service_type_registry
from baserow.core.services.types import DispatchResult
from baserow.core.workflow_actions.models import WorkflowAction

if TYPE_CHECKING:
    from baserow.contrib.automation.workflows.models import AutomationWorkflow
    from baserow.contrib.database.fields.models import ButtonField
    from baserow.contrib.database.workflow_actions.dispatch_context import (
        DatabaseDispatchContext,
    )


class DatabaseWorkflowServiceActionType(
    ServiceBackedTypeMixin, DatabaseWorkflowActionType
):
    service_type = None  # Must be implemented by subclasses.
    service_field_help_text = (
        "The service which this workflow action is associated with."
    )

    # Where `import_serialized` leaves the field it is importing into, for
    # `deserialize_property`, which the base class hands the cache but not the
    # parent.
    IMPORTING_FIELD_CACHE_KEY = "database_workflow_action_field"

    # Service values that shape the answer a click remembers. Changing one
    # makes an earlier capture describe a request no longer being made, so it
    # is dropped. Only read by a type that sets `captures_sample_data`.
    sample_data_shaping_fields: List[str] = []

    serializer_field_names = ["service"]
    serializer_field_overrides = {
        "service": DatabasePolymorphicServiceSerializer(
            help_text="The service which this workflow action is associated with."
        )
    }
    request_serializer_field_names = ["service"]

    class SerializedDict(DatabaseWorkflowActionDict):
        service: Dict

    @property
    def is_external(self) -> bool:
        # The service the action dispatches through already says whether it
        # reaches outside Baserow, so this reads that flag rather than
        # keeping a second one that could drift from it.
        return service_type_registry.get(self.service_type).is_external

    @property
    def allowed_fields(self) -> List[str]:
        return super().allowed_fields + ["service"]

    def export_prepared_values(self, instance: WorkflowAction) -> Dict[str, Any]:
        """
        Nests the service's own values in place of the service. Whatever the
        service type calls sensitive is left out: these values are stored on the
        undo action and copied into the audit log, and an HTTP action keeps its
        API keys in its headers. Undo leaves those fields as they are.
        """

        values = super().export_prepared_values(instance)
        service = instance.service.specific
        service_type = service.get_type()
        values["service"] = {
            key: value
            for key, value in service_type.export_prepared_values(service).items()
            if key not in service_type.sensitive_fields
        }
        return values

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        service_type = service_type_registry.get(self.service_type)
        return {"service": pytest_data_fixture.create_service(service_type.model_class)}

    def get_pytest_params_serialized(
        self, pytest_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        service_type = service_type_registry.get_by_model(pytest_params["service"])
        return {"service": service_type.export_serialized(pytest_params["service"])}

    def export_serialized(
        self,
        instance: WorkflowAction,
        import_export_config: Optional[Any] = None,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Blanks whatever the backing service calls sensitive. `serialize_property`
        is where the service is exported, and it is never handed the config, so
        the stripping happens here instead.

        A key on an HTTP action lives in the service's own headers rather than
        in an integration, so without this it travels with every export.
        """

        exported = super().export_serialized(
            instance, import_export_config, files_zip, storage, cache
        )

        if getattr(import_export_config, "exclude_sensitive_data", False):
            service = exported.get("service") or {}
            for prop_name in instance.service.specific.get_type().sensitive_fields:
                if prop_name not in service:
                    continue
                rows = service[prop_name]
                if isinstance(rows, list):
                    # Only the value is dropped. Blanking the whole list would
                    # take `Content-Type` and `api-version` with the key, and
                    # the imported button would send a different request while
                    # looking configured. Keeping the names says what has to be
                    # entered again, which is what the data sync types do.
                    service[prop_name] = [
                        {**row, "value": None} if isinstance(row, dict) else row
                        for row in rows
                    ]
                else:
                    service[prop_name] = None

        return exported

    def serialize_property(
        self,
        workflow_action: WorkflowAction,
        prop_name: str,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, Any]] = None,
    ) -> Any:
        if prop_name == "service":
            service = workflow_action.service.specific
            exported = service.get_type().export_serialized(
                service, files_zip=files_zip, storage=storage, cache=cache
            )
            # An export travels to snapshots, copies and templates, and what a
            # click remembered describes this installation's data. Nothing
            # needs it there: the editor rebuilds it from the next click.
            exported.pop("sample_data", None)
            return exported

        return super().serialize_property(
            workflow_action,
            prop_name,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

    def deserialize_property(
        self,
        prop_name: str,
        value: Any,
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Any:
        """
        Recreates the backing service from its serialized values. The service
        type remaps its own references, such as the target table id.
        """

        if prop_name == "service" and value:
            return ServiceHandler().import_service(
                self._imported_integration(value, id_mapping, cache),
                value,
                id_mapping,
                storage=storage,
                cache=cache,
                files_zip=files_zip,
                import_export_config=kwargs.get("import_export_config"),
            )

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

    def _imported_integration(
        self,
        serialized_service: Dict[str, Any],
        id_mapping: Dict[str, Any],
        cache: Optional[Dict[str, Any]] = None,
    ) -> Optional[Integration]:
        """
        The integration an imported service should carry: the copy made by
        this import, or the original when the copy stays in the same database
        (a duplicated table or field). Whether the action may keep it is still
        settled in `import_serialized`; this only decides what to attach.

        :param serialized_service: The service as the export wrote it.
        :param id_mapping: What this import has remapped so far.
        :param cache: Carries the field being imported, put there by
            `import_serialized`.
        :return: The integration to attach, or None when it names none this
            database has.
        """

        integration_id = self._serialized_id_to_look_up(
            serialized_service.get("integration_id")
        )
        if integration_id is None:
            return None
        # After the coercion, not before: the mapping is keyed by integers
        # and a JSON round trip can turn the value beside them into a string.
        integration_id = id_mapping.get("integrations", {}).get(
            integration_id, integration_id
        )

        # Scoped to the database the action lands in. Unmapped ids are the
        # normal case for a duplicated field or table, and an export written
        # before 4c carries none at all, so an unscoped lookup would match
        # whatever row holds that number here — another workspace's bot. The
        # later check would drop it, but the FK is written first.
        field = (cache or {}).get(self.IMPORTING_FIELD_CACHE_KEY)
        if field is None:
            return None
        return Integration.objects.filter(
            id=integration_id, application_id=field.table.database_id
        ).first()

    @staticmethod
    def _serialized_id_to_look_up(value: Any) -> Optional[int]:
        """
        The id a serialized service names, as an integer, or None when it
        names nothing usable.

        Nothing coerces this the way the endpoint's serializer does, so a
        hand-edited export would otherwise key the id mapping with a list or a
        dict and fail the whole import job with a `TypeError`, or slip a
        `True` through, which hashes equal to 1 and would pick up whatever
        row 1 was remapped to.

        :param value: What the export named, which is whatever was in the file.
        :return: The id to look up, or None.
        """

        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, int):
            return value or None
        if isinstance(value, str):
            # `int` also accepts "+1", " 1 " and "1_0", which no export writes.
            return int(value) or None if value.isdecimal() else None
        return None

    def import_serialized(
        self,
        parent: Any,
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> WorkflowAction:
        """
        Drops an integration the imported action may not carry: one of a type
        this action does not allow, one outside the field's own database, which
        an export made elsewhere could name by a number that happens to exist
        here, or one the person asking for the copy may not read. The action
        then says what it needs, as an unconfigured one does.

        `copied_by` is set on the paths where a person copies an existing
        action, since those never pass through the endpoint that checks the
        credential. An import from a file has no such actor.

        :param parent: The button field the action belongs to.
        :param serialized_values: The action as the export wrote it.
        :param id_mapping: What this import has remapped so far.
        :param files_zip: The archive the export's files came in, if any.
        :param storage: Where those files are written.
        :param cache: Shared across one import, for values worth reusing.
        :param kwargs: Passed on, and read for `copied_by`.
        :return: The imported action.
        """

        copied_by = kwargs.pop("copied_by", None)
        # `deserialize_property` needs the field to scope its integration
        # lookup, and the base class hands it the cache but not the parent.
        cache = {} if cache is None else cache
        cache[self.IMPORTING_FIELD_CACHE_KEY] = parent
        created_instance = super().import_serialized(
            parent, serialized_values, id_mapping, files_zip, storage, cache, **kwargs
        )
        service = created_instance.service
        integration = service.integration
        if integration is not None and not self._may_carry_integration(
            integration, created_instance.field, copied_by
        ):
            service.integration = None
            service.save(update_fields=["integration"])
        return created_instance

    def _may_carry_integration(
        self, integration: Integration, field, copied_by: Optional[AbstractUser]
    ) -> bool:
        """
        Whether an imported action keeps the integration it came with: it has
        to be usable by this action, and readable by whoever asked for the
        copy when there is one.

        :param integration: The integration the copy came with.
        :param field: The button field the copy belongs to.
        :param copied_by: Who asked for the copy, when a person did.
        :return: True when the copy keeps it.
        """

        if not self._integration_is_usable(integration, field):
            return False
        if copied_by is None:
            return True
        try:
            CoreHandler().check_permissions(
                copied_by,
                ReadIntegrationOperationType.type,
                workspace=field.table.database.workspace,
                context=integration,
            )
        except PermissionException:
            return False
        return True

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Optional[WorkflowAction] = None,
    ) -> Dict[str, Any]:
        """
        Creates the backing service when the action is new, and forwards any
        supplied service values to it.

        :param values: What the caller is setting on the action.
        :param user: Who is configuring it.
        :param instance: The action being updated, or None when creating one.
        :raises WorkflowActionInvalidIntegration: When the integration named
            cannot be carried, or the user may not read it.
        :return: The values to save, with the service among them.
        """

        service_type = service_type_registry.get(self.service_type)

        if not instance:
            service = ServiceHandler().create_service(service_type)
        else:
            service = instance.service.specific

        service_values = values.pop("service", None) or {}
        # An explicit null clears the credential, which takes nothing away
        # from anyone and so needs no permission to read the one going. A key
        # the request never sent keeps the one already carried, and that is
        # checked: an edit must not be a way to drive a credential the editor
        # may not read: the channel and the message are the whole of what a
        # bot does, so editing them is using it.
        unset = object()
        integration_id = service_values.get("integration_id", unset)
        if integration_id is unset:
            integration_id = service.integration_id if instance else None
        if integration_id is not None:
            field = values.get("field") or (instance.field if instance else None)
            integration = self._check_integration(integration_id, user, field)
            if "integration_id" in service_values:
                # Handed over rather than left as an id: this resolved it
                # already, and the service type would otherwise read the same
                # row twice more. Its own checks are looser than the ones
                # above, which have run.
                service_values.pop("integration_id")
                service_values["integration"] = integration
        prepared_service_values = service_type.prepare_values(
            service_values, user, service if instance else None
        )
        if instance and self._reshapes_the_request(service, prepared_service_values):
            # Saved by `update_service` below, in the same write.
            service.sample_data = None
        ServiceHandler().update_service(
            service_type, service, **prepared_service_values
        )

        values["service"] = service
        return super().prepare_values(values, user, instance)

    def _integration_is_usable(self, integration: Integration, field) -> bool:
        """
        The one rule save, import and dispatch all read, so they cannot
        drift: a carried integration is of a type this action accepts, and
        belongs to the field's own database.

        :param integration: The integration in question.
        :param field: The button field the action belongs to.
        :return: True when this action may carry it.
        """

        return (
            field is not None
            and integration.get_type().type in self.allowed_integration_types
            and integration.application_id == field.table.database_id
        )

    def _check_integration(
        self, integration_id: int, user: AbstractUser, field
    ) -> Integration:
        """
        Refuses an integration this type may not carry. `integration_id` is
        writable, and the service type resolves it without a permission check,
        so this is where a button is kept from using what its editor could not
        see: the integration must be usable by this action, and readable by
        the user.

        :param integration_id: The integration the caller wants to attach.
        :param user: The user configuring the action.
        :param field: The button field the action belongs to.
        :raises WorkflowActionInvalidIntegration: When it cannot be attached.
        :return: The integration, so the caller can hand it on rather than
            have the service type read the same row again.
        """

        integration = None
        if field is not None:
            # Scoped to the field's database, so someone else's integration
            # reads the same as nothing.
            integration = Integration.objects.filter(
                id=integration_id, application_id=field.table.database_id
            ).first()

        if integration is None or not self._integration_is_usable(integration, field):
            # One answer for every way of being wrong, or a caller could walk
            # the ids and learn what this installation holds.
            raise WorkflowActionInvalidIntegration(
                "This action cannot use that integration. It must be one the "
                "action accepts, from the database of the button field."
            )

        # Checked against the row already in hand.
        CoreHandler().check_permissions(
            user,
            ReadIntegrationOperationType.type,
            workspace=field.table.database.workspace,
            context=integration,
        )

        return integration

    def check_kept_service(
        self, service: Service, user: AbstractUser, field: "ButtonField"
    ) -> None:
        """
        Checks a service an undo or redo attaches as it is, the way an update
        setting the same values would, so it cannot give back access the user
        has since lost.

        :param service: The kept service about to be attached.
        :param user: Who is undoing or redoing.
        :param field: The button field the action belongs to.
        """

        if service.integration_id is not None:
            self._check_integration(service.integration_id, user, field)

    def _reshapes_the_request(
        self, service: Service, prepared_service_values: Dict[str, Any]
    ) -> bool:
        """
        Whether this update changes what the answer will look like, which is
        what makes an earlier capture stale. Read before the update, while the
        service still holds the values it is replacing.

        :param service: The service as it is stored right now.
        :param prepared_service_values: What the update is about to set. A
            value the caller left out is not compared: it is not changing.
        :return: True when a captured answer no longer describes this request.
        """

        if not self.captures_sample_data or not service.sample_data:
            return False

        for name in self.sample_data_shaping_fields:
            if name not in prepared_service_values:
                continue

            stored = getattr(service, name)
            supplied = prepared_service_values[name]

            if isinstance(stored, Manager):
                # A related row, such as a header or a query parameter.
                stored = [{"key": row.key, "value": row.value} for row in stored.all()]
                supplied = [
                    {"key": row["key"], "value": row["value"]} for row in supplied or []
                ]

            if stored != supplied:
                return True

        return False

    def formula_generator(
        self, workflow_action: WorkflowAction
    ) -> Generator[str | Instance, str, None]:
        yield from super().formula_generator(workflow_action)

        service = workflow_action.service.specific
        yield from service.get_type().formula_generator(service)

    def enhance_queryset(self, queryset: QuerySet) -> QuerySet:
        return (
            super()
            .enhance_queryset(queryset)
            .prefetch_related(
                Prefetch(
                    "service",
                    queryset=specific_queryset(
                        Service.objects.all(),
                        per_content_type_queryset_hook=(
                            lambda service, queryset: (
                                service_type_registry.get_by_model(
                                    service
                                ).enhance_queryset(queryset)
                            )
                        ),
                    ),
                )
            )
        )

    def get_result_field_names(self, workflow_action: WorkflowAction) -> Dict[str, str]:
        service = workflow_action.service.specific
        service_type = service.get_type()
        get_field_objects = getattr(service_type, "get_table_field_objects", None)
        if get_field_objects is None:
            return {}
        return {
            field_object["field"].db_column: field_object["field"].name
            for field_object in get_field_objects(service) or []
        }

    def dispatch(
        self,
        workflow_action: WorkflowAction,
        dispatch_context: "DatabaseDispatchContext",
    ) -> DispatchResult:
        service = workflow_action.service.specific
        # Never as an integration's `authorized_user` (ADR 006 section 5),
        # however the service reached this state.
        if service.integration_id is not None and not self._integration_is_usable(
            # From the context: reading it back through the action costs two
            # cold queries apiece, inside the lock.
            service.integration,
            dispatch_context.field,
        ):
            raise ServiceImproperlyConfiguredDispatchException(
                "A database service cannot use this integration."
            )
        return ServiceHandler().dispatch_service(service, dispatch_context)


class LocalBaserowCreateRowWorkflowActionType(DatabaseWorkflowServiceActionType):
    type = "local_baserow_create_row"
    model_class = LocalBaserowCreateRowWorkflowAction
    service_type = LocalBaserowUpsertRowServiceType.type


class LocalBaserowUpdateRowWorkflowActionType(
    UpdateRowRequiresRowIdMixin, DatabaseWorkflowServiceActionType
):
    type = "local_baserow_update_row"
    model_class = LocalBaserowUpdateRowWorkflowAction
    service_type = LocalBaserowUpsertRowServiceType.type


class LocalBaserowDeleteRowWorkflowActionType(DatabaseWorkflowServiceActionType):
    type = "local_baserow_delete_row"
    model_class = LocalBaserowDeleteRowWorkflowAction
    service_type = LocalBaserowDeleteRowServiceType.type


class CoreHTTPRequestWorkflowActionType(DatabaseWorkflowServiceActionType):
    type = "http_request"
    model_class = CoreHTTPRequestWorkflowAction
    service_type = CoreHTTPRequestServiceType.type

    # What an endpoint answers with is unknowable until it has answered once.
    captures_sample_data = True

    # Everything that decides which request goes out. `timeout` is left out:
    # it changes how long the answer may take, not what is in it.
    sample_data_shaping_fields = [
        "http_method",
        "url",
        "body_type",
        "body_content",
        "headers",
        "query_params",
        "form_data",
    ]

    def unusable_result_reason(self, result: DispatchResult) -> Optional[str]:
        data = result.data if isinstance(result.data, dict) else {}
        status_code = data.get("status_code")

        if isinstance(status_code, int) and 200 <= status_code < 300:
            return None

        # An error page describes the failure, not the endpoint, and would
        # replace the shape a working click learned. The status code says
        # nothing about the address, so it is safe to repeat.
        if status_code == 504:
            return "The last click timed out before the endpoint answered."
        if isinstance(status_code, int):
            return (
                f"The last click was answered with {status_code}, which "
                f"describes the failure rather than the endpoint."
            )
        return "The last click was not answered with anything describable."


class CoreSMTPEmailWorkflowActionType(DatabaseWorkflowServiceActionType):
    type = "smtp_email"
    model_class = CoreSMTPEmailWorkflowAction
    service_type = CoreSMTPEmailServiceType.type

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Optional[WorkflowAction] = None,
    ) -> Dict[str, Any]:
        """
        A database action carries no integration (ADR 006 section 5), so the
        instance server is the only thing it can send through. Pinned here
        rather than in the form, or an API client could store an action that
        can never send. Written into what the base is about to save, so the
        service is not saved a second time for it.
        """

        values["service"] = {
            **(values.get("service") or {}),
            "use_instance_smtp_settings": True,
        }
        values = super().prepare_values(values, user, instance)

        # The service type drops the pin while the instance cannot send, and
        # an update is not refused the way a create is. Left that way, the
        # action would fail on every click once sending is back. Only a write
        # in that case: the ordinary one is a single save above.
        service = values["service"]
        if not service.use_instance_smtp_settings:
            service.use_instance_smtp_settings = True
            service.save(update_fields=["use_instance_smtp_settings"])
        return values

    # What each reason the service gives means for a button, in the words the
    # API answers a refusal with.
    DEACTIVATED_REASONS = {
        CoreSMTPEmailServiceType.INSTANCE_SMTP_TURNED_OFF: (
            "Sending through this Baserow instance's own SMTP server is turned "
            "off, so a button cannot send email."
        ),
        CoreSMTPEmailServiceType.INSTANCE_SMTP_NO_SERVER: (
            "This Baserow instance has no SMTP server configured, so a button "
            "cannot send email."
        ),
    }

    def is_deactivated(self, workspace: Workspace) -> bool:
        """
        A database action carries no integration, so the instance SMTP server
        is the only way it can send. Without one, refuse it up front rather
        than failing on every click.

        :param workspace: The workspace the button field belongs to.
        :return: True when this installation cannot send at all.
        """

        return self.get_deactivated_reason(workspace) is not None

    def get_deactivated_reason(self, workspace: Workspace) -> Optional[str]:
        """
        Which of the two ways to be unable to send this installation is in.

        :param workspace: The workspace the button field belongs to.
        :return: The reason in words, or `None` when it can send.
        """

        service_type = service_type_registry.get(self.service_type)
        reason = service_type.instance_smtp_unavailable_reason()
        return self.DEACTIVATED_REASONS.get(reason)


class SlackWriteMessageWorkflowActionType(DatabaseWorkflowServiceActionType):
    type = "slack_write_message"
    model_class = SlackWriteMessageWorkflowAction
    service_type = SlackWriteMessageServiceType.type
    allowed_integration_types = [SlackBotIntegrationType.type]

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        service_type = service_type_registry.get(self.service_type)
        return {
            "service": pytest_data_fixture.create_service(
                service_type.model_class, integration=None
            )
        }


class CoreStartWorkflowWorkflowActionType(DatabaseWorkflowServiceActionType):
    """
    Queues an automation workflow. Nothing comes back, so it is neither
    external nor a data source for the actions after it.
    """

    type = "start_workflow"
    model_class = CoreStartWorkflowWorkflowAction
    service_type = CoreStartWorkflowServiceType.type

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Optional[WorkflowAction] = None,
    ) -> Dict[str, Any]:
        service_values = values.get("service") or {}
        if service_values.get("workflow_id") is not None:
            field = values.get("field") or (instance.field if instance else None)
            # Resolved here rather than by the service type, whose lookup
            # accepts any workflow the user can read, in any workspace.
            service_values["workflow"] = self._check_workflow(
                service_values.pop("workflow_id"), user, field
            )
        return super().prepare_values(values, user, instance)

    def check_kept_service(
        self, service: Service, user: AbstractUser, field: "ButtonField"
    ) -> None:
        super().check_kept_service(service, user, field)
        if service.workflow_id is not None:
            self._check_workflow(service.workflow_id, user, field)

    def _check_workflow(
        self, workflow_id: int, user: AbstractUser, field: "ButtonField"
    ) -> "AutomationWorkflow":
        """
        Resolves the workflow a button may start. Permission is checked before
        anything about the workflow is inspected, and refused the way a missing
        one is, so a refusal never says whether a workflow exists or what kind
        of trigger it has.

        :param workflow_id: The workflow the caller wants to start.
        :param user: Who is configuring the action.
        :param field: The button field the action belongs to.
        :raises serializers.ValidationError: When the workflow does not exist
            in the button's workspace or cannot be started on demand.
        :return: The workflow.
        """

        from baserow.contrib.automation.workflows.exceptions import (
            AutomationWorkflowDoesNotExist,
        )
        from baserow.contrib.automation.workflows.service import (
            AutomationWorkflowService,
        )

        try:
            workflow = AutomationWorkflowService().get_workflow(user, workflow_id)
        except (AutomationWorkflowDoesNotExist, PermissionException):
            raise serializers.ValidationError(
                CoreStartWorkflowServiceType.WORKFLOW_DOES_NOT_EXIST_ERROR.format(
                    workflow_id=workflow_id
                )
            )
        reason = self._unusable_workflow_reason(
            workflow, self._workspace_id_for(field, None)
        )
        if reason is not None:
            raise serializers.ValidationError(reason)
        return workflow

    @staticmethod
    def _workspace_id_for(
        field: "ButtonField", id_mapping: Optional[Dict[str, Any]]
    ) -> Optional[int]:
        """
        :param field: The button field the action belongs to.
        :param id_mapping: The import's mapping when this runs during an
            import. A snapshot is created with `workspace=None` on the
            application, so the field alone cannot name the workspace then.
        :return: The workspace id.
        """

        workspace_id = field.table.database.workspace_id
        if workspace_id is None and id_mapping is not None:
            workspace_id = id_mapping.get("import_workspace_id")
        return workspace_id

    @staticmethod
    def _unusable_workflow_reason(
        workflow: "AutomationWorkflow", workspace_id: Optional[int]
    ) -> Optional[str]:
        """
        The rule save and import both read: the workflow belongs to the
        button's workspace and its trigger can start on demand.

        :param workflow: The workflow the caller named.
        :param workspace_id: The workspace the button belongs to.
        :return: The refusal, worded as the service type words it, or None
            when the button may start the workflow.
        """

        if workflow.automation.workspace_id != workspace_id:
            return CoreStartWorkflowServiceType.WORKFLOW_DOES_NOT_EXIST_ERROR.format(
                workflow_id=workflow.id
            )
        if not workflow.can_be_immediately_dispatched():
            return CoreStartWorkflowServiceType.TRIGGER_NOT_ON_DEMAND_ERROR
        return None

    def import_serialized(
        self,
        parent: Any,
        serialized_values: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> WorkflowAction:
        serialized_service = serialized_values.get("service") or {}
        exported_workflow_id = serialized_service.get("workflow_id")
        # Decided before the row is written: the import runs this after the
        # application's transaction has committed, so a workflow id this
        # installation does not have would fail on insert.
        if exported_workflow_id is not None and not self._may_carry_workflow(
            exported_workflow_id,
            parent,
            id_mapping,
            kwargs.get("import_export_config"),
            kwargs.get("copied_by"),
        ):
            serialized_values = {
                **serialized_values,
                "service": {**serialized_service, "workflow_id": None},
            }
        return super().import_serialized(
            parent, serialized_values, id_mapping, files_zip, storage, cache, **kwargs
        )

    def _may_carry_workflow(
        self,
        exported_workflow_id: Any,
        field: "ButtonField",
        id_mapping: Dict[str, Any],
        import_export_config: ImportExportConfig | None,
        copied_by: Optional[AbstractUser],
    ) -> bool:
        """
        Whether an imported action keeps the workflow it came with.

        An export written on another installation can name an id this
        workspace happens to own. The reference is kept only when this import
        remapped it, or when the data never left the instance (duplicate,
        snapshot). A file import and a template install keep neither.

        :param exported_workflow_id: What the export named the workflow by,
            which is whatever was in the file.
        :param field: The button field the copy belongs to.
        :param id_mapping: What this import has remapped so far.
        :param import_export_config: What kind of import this is.
        :param copied_by: Who asked for the copy, when a person did.
        :return: True when the copy keeps it.
        """

        from baserow.contrib.automation.workflows.exceptions import (
            AutomationWorkflowDoesNotExist,
        )
        from baserow.contrib.automation.workflows.handler import (
            AutomationWorkflowHandler,
        )
        from baserow.contrib.automation.workflows.service import (
            AutomationWorkflowService,
        )

        exported_workflow_id = self._serialized_id_to_look_up(exported_workflow_id)
        if exported_workflow_id is None:
            return False

        # `.keys()`, not `in`: a `MirrorDict` answers `in` for every key, and
        # the key view only for what this import actually remapped.
        workflow_mapping = id_mapping.get("automation_workflows", {})
        remapped = exported_workflow_id in workflow_mapping.keys()
        stayed_here = bool(
            import_export_config
            and import_export_config.is_duplicate
            and not import_export_config.is_template
        )
        if not (remapped or stayed_here):
            return False

        # The id the service type will write.
        workflow_id = service_type_registry.get(self.service_type).deserialize_property(
            "workflow_id", exported_workflow_id, id_mapping
        )
        try:
            if copied_by is None:
                workflow = AutomationWorkflowHandler().get_workflow(workflow_id)
            else:
                workflow = AutomationWorkflowService().get_workflow(
                    copied_by, workflow_id
                )
        except (AutomationWorkflowDoesNotExist, PermissionException):
            return False

        workspace_id = self._workspace_id_for(field, id_mapping)
        return self._unusable_workflow_reason(workflow, workspace_id) is None


class OpenUrlWorkflowActionType(DatabaseWorkflowActionType):
    type = "open_url"
    model_class = OpenUrlWorkflowAction
    is_frontend_only = True

    allowed_fields = DatabaseWorkflowActionType.allowed_fields + ["url", "target"]
    serializer_field_names = ["url", "target"]
    # Remapped on import by the deferred pass in `DatabaseWorkflowActionType`.
    simple_formula_fields = ["url"]
    serializer_field_overrides = {
        "url": FormulaSerializerField(
            help_text="The URL to open, as a formula.",
            required=False,
        ),
    }

    class SerializedDict(DatabaseWorkflowActionDict):
        url: str
        target: str
