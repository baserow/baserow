from typing import Any, Dict, Iterable, Iterator, List, Optional, Union, cast
from zipfile import ZipFile

from django.core.files.storage import Storage
from django.db.models import Q, QuerySet

from loguru import logger

from baserow.core.cache import local_cache
from baserow.core.db import specific_iterator
from baserow.core.exceptions import ApplicationOperationNotSupported
from baserow.core.integrations.exceptions import (
    IntegrationCannotMoveToApplication,
    IntegrationDoesNotExist,
    IntegrationNotInApplication,
    IntegrationNotInWorkspace,
    IntegrationNotUsable,
    IntegrationTypeNotAllowed,
)
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import (
    IntegrationType,
    integration_type_registry,
)
from baserow.core.models import (
    Application,
    SharedApplication,
)
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.storage import ExportZipFile
from baserow.core.utils import extract_allowed

from .types import IntegrationForUpdate


class IntegrationHandler:
    def get_integration(
        self,
        integration_id: int,
        base_queryset: Optional[QuerySet] = None,
        specific=True,
    ) -> Integration:
        """
        Returns an integration instance from the database.

        :param integration_id: The ID of the integration.
        :param base_queryset: The base queryset use to build the query if provided.
        :param specific: Whether we want the specific instance or not.
        :raises IntegrationDoesNotExist: If the integration can't be found.
        :return: The integration instance.
        """

        queryset = (
            base_queryset if base_queryset is not None else Integration.objects.all()
        )

        queryset = queryset.select_related("application__workspace")

        try:
            if specific:
                gen_integration = queryset.get(id=integration_id)
                # We use the enhanced version of the queryset to get the related
                # fields. This is also responsible for returning the specific instance.
                integration = (
                    gen_integration.get_type().get_queryset().get(id=integration_id)
                )
                integration.application = gen_integration.application
            else:
                integration = queryset.get(id=integration_id)
        except Integration.DoesNotExist:
            raise IntegrationDoesNotExist()

        return integration

    def get_integration_including_trashed(self, integration_id: int) -> Integration:
        """
        Returns an integration, falling back to a trashed one so a reference to it
        can still be set, for example by an undo step that runs before the step
        restoring the integration. A trashed integration isn't specific.

        :param integration_id: The ID of the integration.
        :raises IntegrationDoesNotExist: If no integration, trashed or not, has
            this ID.
        :return: The integration instance.
        """

        try:
            return self.get_integration(integration_id)
        except IntegrationDoesNotExist:
            return self.get_integration(
                integration_id,
                base_queryset=Integration.objects_and_trash.all(),
                specific=False,
            )

    def get_integration_for_import(
        self,
        integration_id: Optional[int],
        id_mapping: Dict[str, Dict[int, int]],
        application_id: Optional[int] = None,
        import_export_config: Optional[ImportExportConfig] = None,
    ) -> Optional[Integration]:
        """
        Returns the integration an imported service refers to. A trashed integration
        is returned too, so the copy reconnects when it's restored.

        :param integration_id: The exported integration ID, if any.
        :param id_mapping: The import ID mapping. The copies made for the
            application the service is imported into are looked up first, see
            `import_integration`.
        :param application_id: The application the service is imported into. When
            given, an integration the application can't use is dropped, see
            `check_integration_usable`.
        :param import_export_config: How the service is imported. An ID missing
            from the mapping names an integration the import didn't copy: a
            workspace integration, or an integration of the application a service
            is duplicated within. It's kept only when the import keeps unmapped
            references, see `ImportExportConfig.keeps_unmapped_references`.
            Without a config it's dropped, as for an import from a file.
        :return: The integration, or `None` when there's none to refer to.
        """

        if not integration_id:
            return None

        keep_unmapped = (
            import_export_config is not None
            and import_export_config.keeps_unmapped_references
        )
        copies_of_the_application = (
            id_mapping.get("integrations_by_application") or {}
        ).get(application_id, {})
        if integration_id in copies_of_the_application:
            integration_id = copies_of_the_application[integration_id]
        else:
            try:
                # A `defaultdict` mapping answers with its default, like the
                # `MirrorDict` a copy within an application uses.
                integrations = id_mapping["integrations"]
            except KeyError:
                # Nothing was imported into the mapping when the source
                # application has no integrations of its own, as when its
                # services only use workspace integrations.
                integrations = {}
            integration_id = integrations.get(
                integration_id, integration_id if keep_unmapped else None
            )
        if integration_id is None:
            return None

        try:
            integration = Integration.objects_and_trash.get(id=integration_id)
        except Integration.DoesNotExist:
            return None

        if application_id is not None:
            try:
                self.check_integration_usable(
                    integration, application_id=application_id
                )
            except IntegrationNotInApplication:
                return None

        return integration

    def check_integration_usable(
        self,
        integration: Integration,
        application_id: Optional[int] = None,
        workspace_id: Optional[int] = None,
        integration_types: Optional[Iterable[str]] = None,
    ):
        """
        Checks that an integration can be used from the given application or
        workspace, and is of one of the given types. Only the given constraints are
        checked, in that order.

        :param integration: The integration to check.
        :param application_id: The application the integration is used from. It can
            use its own integrations and the workspace integrations of its
            workspace.
        :param workspace_id: The workspace the integration must belong to.
        :param integration_types: The integration types accepted.
        :raises IntegrationNotInApplication: When the application can't use it.
        :raises IntegrationNotInWorkspace: When it belongs to another workspace.
        :raises IntegrationTypeNotAllowed: When it isn't of an accepted type.
        """

        if (
            application_id is not None
            and integration.application_id != application_id
            and not self.is_workspace_integration_of(integration, application_id)
        ):
            raise IntegrationNotInApplication()

        if (
            workspace_id is not None
            and self.get_integration_workspace_id(integration) != workspace_id
        ):
            raise IntegrationNotInWorkspace()

        if (
            integration_types is not None
            and integration.get_type().type not in integration_types
        ):
            raise IntegrationTypeNotAllowed()

    def get_integration_workspace_id(self, integration: Integration) -> Optional[int]:
        """
        Returns the ID of the workspace the integration's application belongs to. A
        published copy of an application has no workspace of its own, so the
        workspace of the application it's published from is resolved, once per
        request.

        :param integration: The integration.
        :return: The workspace ID, if any.
        """

        application = integration.application
        if application.workspace_id is not None:
            return application.workspace_id

        def resolve():
            workspace = application.specific.get_workspace()
            return workspace.id if workspace else None

        return local_cache.get(f"application_{application.id}_workspace_id", resolve)

    def is_shared_application(self, application: Application) -> bool:
        """
        Returns whether the application is the shared application of its workspace,
        whose integrations are the workspace integrations.

        :param application: The application, specific or not.
        :return: True for the shared application.
        """

        return application.specific_class is SharedApplication

    def is_workspace_integration_of(
        self, integration: Integration, application_id: int
    ) -> bool:
        """
        Returns whether the integration is a workspace integration of the given
        application's workspace. A published copy of an application has no workspace,
        so it never matches: publishing copies the workspace integrations its
        services use. A snapshot has no workspace either, but it counts as part of
        the workspace of the application it's taken from, as it keeps referring to
        the workspace integrations to restore them. The answer is cached for the
        request, as every dispatch of a service checks it.

        :param integration: The integration.
        :param application_id: The ID of the application it's used from.
        :return: True when its shared application is the one of that workspace.
        """

        shared_application_id = integration.application_id

        def resolve():
            shared_application = SharedApplication.objects_and_trash.filter(
                id=shared_application_id
            )
            return (
                shared_application.filter(
                    workspace__application__id=application_id
                ).exists()
                # Only asked when the application isn't in the workspace, which a
                # dispatch never needs: a snapshot is only imported and exported.
                or shared_application.filter(
                    workspace__application__snapshot_to__snapshot_to_application_id=(
                        application_id
                    )
                ).exists()
            )

        return local_cache.get(
            f"shared_application_{shared_application_id}_serves_{application_id}",
            resolve,
        )

    def is_integration_usable(
        self,
        integration: Integration,
        application_id: Optional[int] = None,
        workspace_id: Optional[int] = None,
        integration_types: Optional[Iterable[str]] = None,
    ) -> bool:
        """
        Returns whether `check_integration_usable` accepts the integration.

        :param integration: The integration to check.
        :param application_id: The application the integration is used from.
        :param workspace_id: The workspace the integration must belong to.
        :param integration_types: The integration types accepted.
        :return: True when the integration fits every given constraint.
        """

        try:
            self.check_integration_usable(
                integration,
                application_id=application_id,
                workspace_id=workspace_id,
                integration_types=integration_types,
            )
        except IntegrationNotUsable:
            return False

        return True

    def get_integration_for_update(
        self, integration_id: int, base_queryset: Optional[QuerySet] = None
    ) -> IntegrationForUpdate:
        """
        Returns an integration instance from the database that can be safely updated.

        :param integration_id: The ID of the integration.
        :param base_queryset: The base queryset use to build the query if provided.
        :raises IntegrationDoesNotExist: If the integration can't be found.
        :return: The integration instance.
        """

        queryset = (
            base_queryset if base_queryset is not None else Integration.objects.all()
        )

        queryset = queryset.select_for_update(of=("self",))

        return self.get_integration(
            integration_id,
            base_queryset=queryset,
        )

    def get_integrations(
        self,
        application: Optional[Application] = None,
        base_queryset: Optional[QuerySet] = None,
        specific: bool = True,
    ) -> Union[QuerySet[Integration], Iterable[Integration]]:
        """
        Gets all the specific integrations of a given application.

        :param application: The application that holds the integrations if provided.
        :param base_queryset: The base queryset to use to build the query.
        :param specific: Whether to return the generic integrations or the specific
            instances.
        :return: The integrations of that application.
        """

        queryset = (
            base_queryset if base_queryset is not None else Integration.objects.all()
        )

        if application:
            queryset = queryset.filter(application=application)

        if specific:
            # Enhance the queryset for the given integration type for better perf
            def per_content_type_queryset_hook(model, queryset):
                integration_type = integration_type_registry.get_by_model(model)
                return integration_type.enhance_queryset(queryset)

            queryset = queryset.select_related("application__workspace")

            return specific_iterator(
                queryset, per_content_type_queryset_hook=per_content_type_queryset_hook
            )
        else:
            return queryset

    def get_workspace_integration_types(self, application: Application) -> List[str]:
        """
        Returns the integration types of the workspace integrations the given
        application can use, see
        `ApplicationType.can_use_workspace_integration_type`. A type the shared
        application doesn't accept, like an MCP server, is never one.

        :param application: The application the integrations are used from,
            specific or not.
        :return: The integration types, in the registry's order.
        """

        application_type = application_type_registry.get_by_model(
            application.specific_class
        )
        shared_application_type = application_type_registry.get_by_model(
            SharedApplication
        )
        return [
            integration_type.type
            for integration_type in integration_type_registry.get_all()
            if shared_application_type.supports_integration_type(integration_type)
            and application_type.can_use_workspace_integration_type(integration_type)
        ]

    def get_usable_integrations(
        self, application: Application, specific: bool = True
    ) -> Union[QuerySet[Integration], Iterable[Integration]]:
        """
        Gets the integrations the given application can use: its own and the
        workspace integrations of its workspace, the ones `check_integration_usable`
        accepts from it. A published copy has no workspace, so it only gets its own.

        :param application: The application the integrations are used from.
        :param specific: Whether to return the generic integrations or the specific
            instances.
        :return: The integrations the application can use.
        """

        usable = Q(application=application)
        if application.workspace_id is not None:
            usable |= Q(
                application__sharedapplication__isnull=False,
                application__workspace_id=application.workspace_id,
            )

        return self.get_integrations(
            base_queryset=Integration.objects.filter(usable), specific=specific
        )

    def create_integration(
        self,
        integration_type: IntegrationType,
        application: Application,
        before=None,
        **kwargs,
    ) -> Integration:
        """
        Creates a new integration for an application.

        :param integration_type: The type of the integration.
        :param application: The application the integration exists in.
        :param before: The integration before which we want to create the integration.
            If not provided, the integration is added as last one.
        :param kwargs: Additional attributes of the integration.
        :raises CannotCalculateIntermediateOrder: If it's not possible to find an
            intermediate order. The full order of the integration of the application
            must be recalculated in this case before calling this method again.
        :return: The created integration.
        """

        application_type = application_type_registry.get_by_model(
            application.specific_class
        )

        if not application_type.supports_integration_type(integration_type):
            raise ApplicationOperationNotSupported()

        if before:
            order = Integration.get_unique_order_before_integration(before)
        else:
            order = Integration.get_last_order(application)

        shared_allowed_fields = ["type", "name"]
        allowed_values = extract_allowed(
            kwargs, shared_allowed_fields + integration_type.allowed_fields
        )

        model_class = cast(Integration, integration_type.model_class)

        integration = model_class(
            application=application, order=order, **allowed_values
        )
        integration.save()

        return integration

    def delete_integration(self, integration: Integration):
        """
        Deletes an integration.

        :param integration: The to-be-deleted integration.
        """

        integration.delete()

    def update_integration(
        self,
        integration_type: IntegrationType,
        integration: IntegrationForUpdate,
        application: Optional[Application] = None,
        allow_demotion: bool = False,
        **kwargs,
    ) -> Integration:
        """
        Updates and integration with values. Will also check if the values are allowed
        to be set on the integration first.

        :param integration_type: The type of the integration.
        :param integration: The integration that should be updated.
        :param application: The application to move the integration to, if any. It
            only moves between an application and the shared application of the
            same workspace, and is placed last there.
        :param allow_demotion: Whether it may move from the shared application
            back to an application, which only undoing a promotion does.
        :param kwargs: The values that should be set on the integration.
        :raises IntegrationCannotMoveToApplication: When it can't move to the
            application.
        :raises ApplicationOperationNotSupported: When the application doesn't
            accept integrations of its type, or the application on the other end
            of the move doesn't let its services choose their integration.
        :return: The updated integration.
        """

        if application is not None and application.id != integration.application_id:
            self._check_application_change(
                integration_type, integration, application, allow_demotion
            )
            integration.application = application
            integration.order = Integration.get_last_order(application)

        shared_allowed_fields = ["name"]
        allowed_updates = extract_allowed(
            kwargs, shared_allowed_fields + integration_type.allowed_fields
        )

        for key, value in allowed_updates.items():
            setattr(integration, key, value)

        integration.save()

        return integration

    def _check_application_change(
        self,
        integration_type: IntegrationType,
        integration: Integration,
        application: Application,
        allow_demotion: bool,
    ):
        """
        Checks that the integration can move to the given application: only
        between an application and the shared application of the same workspace,
        which is promoting it or, with `allow_demotion`, undoing that. Nothing else
        takes it out of the workspace, because other applications may use it by
        then, and only the undo checks that none started to. The integration of a
        published copy or a snapshot has no workspace, so it never moves. Neither
        does the integration of an application whose services can't choose theirs,
        like a dashboard: its new services would be left without one.

        :param integration_type: The type of the integration.
        :param integration: The integration, still in its current application.
        :param application: The application it moves to.
        :param allow_demotion: Whether it may move from the shared application to
            an application.
        :raises IntegrationCannotMoveToApplication: When it can't move there.
        :raises ApplicationOperationNotSupported: When the application doesn't
            accept integrations of its type, or the application on the other end
            of the move doesn't let its services choose their integration.
        """

        current = integration.application
        if (
            current.workspace_id is None
            or application.workspace_id != current.workspace_id
            or not (
                self.is_shared_application(current)
                or self.is_shared_application(application)
            )
        ):
            raise IntegrationCannotMoveToApplication()

        if not allow_demotion and not self.is_shared_application(application):
            raise IntegrationCannotMoveToApplication()

        # One end is the shared application, the other the application it's
        # promoted from or moved back to.
        other_end = current if self.is_shared_application(application) else application
        if not application_type_registry.get_by_model(
            other_end.specific_class
        ).lets_services_choose_integrations:
            raise ApplicationOperationNotSupported()

        application_type = application_type_registry.get_by_model(
            application.specific_class
        )
        if not application_type.supports_integration_type(integration_type):
            raise ApplicationOperationNotSupported()

    def move_integration(
        self, integration: IntegrationForUpdate, before: Optional[Integration] = None
    ) -> Integration:
        """
        Moves the given integration before the specified `before` integration in the
        same application.

        :param integration: The integration to move.
        :param before: The integration before which to move the `integration`. If
            before is not specified, the integration is moved at the end of the list.
        :raises CannotCalculateIntermediateOrder: If it's not possible to find an
            intermediate order. The full order of the integration of the application
            must be recalculated in this case before calling this method again.
        :return: The moved integration.
        """

        if before:
            integration.order = Integration.get_unique_order_before_integration(before)
        else:
            integration.order = Integration.get_last_order(integration.application)

        integration.save()

        return integration

    def recalculate_full_orders(
        self,
        application: Application,
    ):
        """
        Recalculates the order to whole numbers of all integrations of the given
        application.
        """

        Integration.recalculate_full_orders(
            queryset=Integration.objects.filter(application=application)
        )

    def export_integration(
        self,
        integration: Integration,
        import_export_config: Optional[ImportExportConfig] = None,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict] = None,
    ):
        return integration.get_type().export_serialized(
            integration,
            import_export_config,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

    def export_referenced_workspace_integrations(
        self,
        application: Application,
        serialized_content: Any,
        import_export_config: ImportExportConfig,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        Exports the workspace integrations an application's services and user
        sources use, as if the application owned them, so the copy gets
        integrations of its own: a published copy has no workspace to read them
        from, and a workspace export or template is imported without them. The
        sensitive fields are stripped the way the config strips the application's
        own integrations.

        A duplicate or a snapshot stays in the workspace, so it keeps referring to
        the workspace integrations and nothing is exported.

        :param application: The application being exported.
        :param serialized_content: The parts of the application's export that can
            refer to integrations. Every `integration_id` in them is read, apart
            from those in sample data. The row data of a table must be left out,
            as it's large and refers to none.
        :param import_export_config: How the application is exported.
        :param files_zip: The zip the export's files are written to, if any.
        :param storage: The storage the files are read from.
        :param cache: Shared across one export, for values worth reusing.
        :return: The serialized integrations, to add to the application's own.
        """

        if import_export_config.keeps_unmapped_references:
            return []

        integration_ids = set(self._find_integration_ids(serialized_content))
        if not integration_ids or application.workspace_id is None:
            return []

        integrations = self.get_integrations(
            base_queryset=Integration.objects.filter(
                application__sharedapplication__isnull=False,
                id__in=integration_ids,
                application__workspace_id=application.workspace_id,
            )
        )

        return [
            self.export_integration(
                integration,
                import_export_config,
                files_zip=files_zip,
                storage=storage,
                cache=cache,
            )
            for integration in integrations
        ]

    def _find_integration_ids(self, serialized: Any) -> Iterator[int]:
        """
        Yields every integration ID the serialized content names under an
        `integration_id` key, at any depth. A service's `sample_data` is skipped:
        it holds what a test dispatch returned, such as a webhook body, so any
        `integration_id` in it comes from outside and names no integration.

        :param serialized: Serialized content: dicts, lists and plain values.
        :return: The integration IDs, possibly repeated.
        """

        if isinstance(serialized, dict):
            for key, value in serialized.items():
                if key == "sample_data":
                    continue
                if key != "integration_id":
                    yield from self._find_integration_ids(value)
                # A boolean is an int too, and would read as integration 0 or 1.
                elif isinstance(value, int) and not isinstance(value, bool):
                    yield value
        elif isinstance(serialized, (list, tuple)):
            for item in serialized:
                yield from self._find_integration_ids(item)

    def import_integration(
        self,
        application,
        serialized_integration,
        id_mapping,
        cache: Optional[Dict] = None,
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        import_export_config: Optional[ImportExportConfig] = None,
    ) -> Optional[Integration]:
        """
        Imports a serialized integration into an application.

        :param application: The application it is imported into.
        :param serialized_integration: The integration as the export wrote it.
        :param id_mapping: What this import has remapped so far.
        :param cache: Shared across one import, for values worth reusing.
        :param files_zip: The archive the export's files came in, if any.
        :param storage: Where those files are written.
        :param import_export_config: Options controlling how integrations are imported.
        :return: The imported integration, or None when the application does
            not accept its type. `DatabaseApplicationType` and
            `AgentApplicationType` narrow what they accept, and both ignore
            what this returns. A type that starts narrowing has to look at its
            own call site.
        """

        if "integrations" not in id_mapping:
            id_mapping["integrations"] = {}

        integration_type = integration_type_registry.get(serialized_integration["type"])

        # The same gate `create_integration` applies, so an import cannot place
        # what the endpoint would refuse (ADR 006 section 4). Skipped rather
        # than raised: no export this instance writes can fail it today, but a
        # release that stops registering an action type would turn every
        # snapshot holding its integration into one that cannot be restored.
        # An action referring to a skipped integration imports unconfigured,
        # which is what it does for any integration it may not carry.
        application_type = application_type_registry.get_by_model(
            application.specific_class
        )
        if not application_type.supports_integration_type(integration_type):
            logger.warning(
                "Skipped a {type} integration on import: {application} does not "
                "accept that type.",
                type=integration_type.type,
                application=application_type.type,
            )
            return None

        integration = integration_type.import_serialized(
            application,
            serialized_integration,
            id_mapping,
            import_export_config=import_export_config,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

        id_mapping["integrations"][serialized_integration["id"]] = integration.id
        # Each application of an import that uses a workspace integration carries
        # a copy of it under the same ID, so the mapping above keeps only the last
        # copy. Every application's own copies are kept apart too, for the services
        # imported after the next application's integrations, like the actions of
        # database buttons. See `get_integration_for_import`.
        id_mapping.setdefault("integrations_by_application", {}).setdefault(
            application.id, {}
        )[serialized_integration["id"]] = integration.id

        return integration
