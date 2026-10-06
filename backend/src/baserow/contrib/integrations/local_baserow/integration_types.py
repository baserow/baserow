import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser

from rest_framework import serializers

from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.integrations.api.local_baserow.serializers import (
    LocalBaserowContextDataSerializer,
)
from baserow.contrib.integrations.local_baserow.models import LocalBaserowIntegration
from baserow.core.integrations.exceptions import IntegrationImproperlyConfigured
from baserow.core.integrations.models import Integration
from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.types import IntegrationDict
from baserow.core.models import Application
from baserow.core.registries import ImportExportConfig, subject_type_registry

logger = logging.getLogger(__name__)
User = get_user_model()


class AuthorizedSubjectSerializerField(serializers.Field):
    """Serialize a Local Baserow integration's authorization subject."""

    def to_representation(self, subject):
        if subject is None:
            return None
        serialized = subject_type_registry.get_serializer(subject).data
        serialized["type"] = subject_type_registry.get_by_model(subject).type
        return serialized


class LocalBaserowIntegrationType(IntegrationType):
    type = "local_baserow"
    model_class = LocalBaserowIntegration

    class SerializedDict(IntegrationDict):
        authorized_subject_type: Optional[str]
        authorized_subject_id: Optional[int]

    serializer_field_names = [
        "context_data",
        "authorized_subject",
    ]
    allowed_fields = [
        "authorized_subject_type",
        "authorized_subject_id",
        "authorized_user",
    ]
    sensitive_fields = ["authorized_subject_type", "authorized_subject_id"]

    serializer_field_overrides = {
        "context_data": LocalBaserowContextDataSerializer(read_only=True),
        "authorized_subject": AuthorizedSubjectSerializerField(read_only=True),
    }

    request_serializer_field_names = [
        "authorized_subject_id",
        "authorized_subject_type",
    ]
    request_serializer_field_overrides = {
        "authorized_subject_id": serializers.IntegerField(
            required=False,
            allow_null=True,
            help_text="The ID of the subject whose permissions authenticate the integration.",
        ),
        "authorized_subject_type": serializers.ChoiceField(
            choices=["auth.User", "core.Agent"], required=False, allow_null=True
        ),
    }

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        application: Optional[Application] = None,
    ) -> Dict[str, Any]:
        """Resolve and validate the typed authorization subject in this workspace."""

        subject_id = values.get("authorized_subject_id")
        subject_type_name = values.get("authorized_subject_type")
        if subject_id is None and subject_type_name is None:
            subject_type = subject_type_registry.get_by_model(user)
            values["authorized_subject_type"] = subject_type.type
            values["authorized_subject_id"] = user.id
        elif subject_id is None or subject_type_name is None:
            raise serializers.ValidationError(
                "authorized_subject_id and authorized_subject_type must be provided together."
            )
        else:
            subject_type = subject_type_registry.get(subject_type_name)
            subject = subject_type_registry.get_subject(subject_type_name, subject_id)
            workspace = application.workspace
            if subject is None or not subject_type.is_in_workspace(subject, workspace):
                raise serializers.ValidationError(
                    {"authorized_subject_id": "The subject does not exist."}
                )
            if getattr(subject, "trashed", False):
                raise serializers.ValidationError(
                    {"authorized_subject_id": "The agent is trashed."}
                )

        # A save migrates legacy values to the canonical pair.
        values["authorized_user"] = None

        return super().prepare_values(values, user)

    def serialize_property(
        self,
        integration: Integration,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """
        Serialize the canonical subject pair for import/export.
        """

        if prop_name == "authorized_subject":
            return None

        if prop_name == "authorized_subject_type":
            return integration.authorized_subject_type

        if prop_name == "authorized_subject_id":
            return integration.authorized_subject_id

        return super().serialize_property(
            integration, prop_name, files_zip=files_zip, storage=storage, cache=cache
        )

    def export_serialized(
        self,
        instance: LocalBaserowIntegration,
        import_export_config: Optional[ImportExportConfig] = None,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """Preserve canonical authorization only in same-workspace publications."""

        if import_export_config and import_export_config.is_publishing:
            subject = None
            if instance.authorized_subject_type and instance.authorized_subject_id:
                subject_type = subject_type_registry.get(
                    instance.authorized_subject_type
                )
                manager = getattr(
                    subject_type.model_class,
                    "objects_and_trash",
                    subject_type.model_class.objects,
                )
                subject = manager.filter(id=instance.authorized_subject_id).first()
            if getattr(subject, "trashed", False):
                raise IntegrationImproperlyConfigured(
                    "The authorized subject is trashed."
                )

        serialized = super().export_serialized(
            instance,
            import_export_config=import_export_config,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )
        if import_export_config and import_export_config.is_publishing:
            serialized["authorized_subject_type"] = instance.authorized_subject_type
            serialized["authorized_subject_id"] = instance.authorized_subject_id
        return serialized

    def after_import(
        self, user: AbstractUser, instance: LocalBaserowIntegration
    ) -> None:
        """
        After an application has been successfully imported, run all integration
        specific post-import logic.
        """

        if (
            instance.application.workspace_id is None
            and instance.authorized_subject_type
            and instance.authorized_subject_id
        ):
            return

        # Imports from another workspace are always reauthorized to the importer.
        instance.authorized_subject_type = subject_type_registry.get_by_model(user).type
        instance.authorized_subject_id = user.id
        instance.authorized_user = None
        instance.save(
            update_fields=[
                "authorized_subject_type",
                "authorized_subject_id",
                "authorized_user",
            ]
        )

    def import_serialized(
        self,
        application: Application,
        serialized_values: Dict[str, Any],
        id_mapping: Dict,
        files_zip=None,
        storage=None,
        cache=None,
        import_export_config: Optional[ImportExportConfig] = None,
    ) -> LocalBaserowIntegration:
        """
        Import a serialized integration, accepting legacy user authorization.

        Workspace exports made before typed subjects stored the user email in
        ``authorized_user``. Resolve it to the matching workspace user so the model
        save can migrate it to the canonical subject pair.
        """

        if cache is None:
            cache = {}

        serialized_values = serialized_values.copy()
        legacy_authorized_user = None
        username = serialized_values.pop("authorized_user", None)
        if username:
            workspace_users = cache.setdefault(
                "local_baserow_workspace_users",
                {
                    user.username: user
                    for user in User.objects.filter(
                        workspaceuser__workspace_id=id_mapping["import_workspace_id"]
                    )
                },
            )
            legacy_authorized_user = workspace_users.get(username)

        integration = super().import_serialized(
            application,
            serialized_values,
            id_mapping,
            import_export_config=import_export_config,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )
        if legacy_authorized_user:
            integration.authorized_user = legacy_authorized_user
            integration.save(update_fields=["authorized_user"])
        return integration

    def enhance_queryset(self, queryset):
        return queryset.select_related("authorized_user")

    def get_context_data(self, instance: LocalBaserowIntegration) -> Optional[Dict]:
        try:
            databases = LocalBaserowIntegrationType.get_local_baserow_databases(
                instance
            )
        except Exception:
            logger.exception(
                "Failed to compute context_data for integration %s; "
                "returning empty databases list.",
                instance.id,
                exc_info=True,
            )
            databases = []
        return {"databases": databases}

    @staticmethod
    def get_local_baserow_databases(integration: LocalBaserowIntegration) -> List:
        """
        This method returns the databases that the user has access to in a query
        efficient way while also checking for permissions. It will do so by fetching
        all the tables at ones, and then group them by database.

        A side effect of this solution is that databases without tables don't show up
        in this list.
        """

        if not integration.application.workspace_id:
            return []

        subject = integration.specific.authorized_subject
        workspace = integration.application.workspace

        tables = TableHandler().list_workspace_tables(subject, workspace)

        views = ViewHandler().list_workspace_views(subject, workspace, specific=False)

        views = list(
            views.only(
                "id",
                "name",
                "table_id",
                "order",
                "content_type",
            ),
        )

        views_by_table = defaultdict(list)
        [
            views_by_table[view.table_id].append(view)
            for view in views
            if view.get_type().can_filter or view.get_type().can_sort
        ]

        database_map = {}
        for table in tables:
            if table.database not in database_map:
                database_map[table.database] = table.database
                database_map[table.database].tables = []
                database_map[table.database].views = []

            database_map[table.database].tables.append(table)
            database_map[table.database].views += views_by_table.get(table.id, [])

        databases = list(database_map.values())
        databases.sort(key=lambda x: x.order)

        # Sort views. Tables are already sorted.
        [db.views.sort(key=lambda x: x.order) for db in databases]

        return databases
