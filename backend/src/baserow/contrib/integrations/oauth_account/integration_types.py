from datetime import datetime
from typing import Any, Dict, Optional

from django.urls import URLResolver

from rest_framework import serializers

from baserow.core.integrations.types import IntegrationDict
from baserow.core.models import Application, WorkspaceUser
from baserow.core.registries import ImportExportConfig

from .models import OAuthAccountIntegrationMixin
from .providers import OAuthProvider

DATETIME_FIELDS = ("expires_at", "connected_at")
ACCOUNT_TEXT_FIELDS = ("account_id", "account_email", "account_name")


class OAuthAccountIntegrationDict(IntegrationDict):
    account_id: str
    account_email: str
    account_name: str
    scopes: list[str]
    access_token: str
    refresh_token: str
    expires_at: Optional[str]
    connected_at: Optional[str]
    connected_by_id: Optional[int]


class OAuthAccountIntegrationTypeMixin:
    """
    For the integration type of a model with `OAuthAccountIntegrationMixin`.
    The account is connected by signing in, through the endpoints under
    `/api/integrations/oauth/<type>/`, never by sending tokens to the
    integration API: only the name can be changed there.

    Put it before `IntegrationType` in the bases, and set `provider`. A type
    adding fields of its own extends the lists, e.g.
    `serializer_field_names = [*OAuthAccountIntegrationTypeMixin.serializer_field_names, "x"]`.
    """

    provider: OAuthProvider
    """How to sign in to the provider."""

    SerializedDict = OAuthAccountIntegrationDict

    serializer_field_names = [
        "connected",
        "account_email",
        "account_name",
        "scopes",
        "connected_at",
        "connected_by_name",
    ]
    serializer_field_overrides = {
        "connected": serializers.BooleanField(
            read_only=True,
            help_text="Whether an account is connected. False once the provider "
            "stopped accepting its tokens, or it was disconnected.",
        ),
        "account_email": serializers.CharField(read_only=True),
        "account_name": serializers.CharField(read_only=True),
        "scopes": serializers.ListField(
            child=serializers.CharField(),
            read_only=True,
            help_text="The permissions the account granted.",
        ),
        "connected_at": serializers.DateTimeField(read_only=True, allow_null=True),
        "connected_by_name": serializers.CharField(
            source="connected_by.first_name",
            read_only=True,
            allow_null=True,
            help_text="Who signed in. Services act as their account.",
        ),
    }
    request_serializer_field_names = []
    request_serializer_field_overrides = {}
    allowed_fields = []

    @property
    def sensitive_fields(self) -> list[str]:
        """
        The account and its tokens. Never in an export or a template: an
        imported integration must be connected again.
        """

        return self.get_connection_properties()

    @property
    def secret_fields(self) -> list[str]:
        return ["access_token", "refresh_token"]

    def get_connection_properties(self) -> list[str]:
        """
        :return: The serialized names of the fields a sign-in sets.
        """

        return [
            "connected_by_id" if name == "connected_by" else name
            for name in self.model_class.get_connection_fields()
        ]

    def get_api_urls(self) -> list[URLResolver]:
        # The sign-in endpoints are shared by every OAuth account type, and
        # registered once by the integrations plugin.
        return []

    def enhance_queryset(self, queryset):
        return queryset.select_related("connected_by")

    def serialize_property(
        self,
        integration: OAuthAccountIntegrationMixin,
        prop_name: str,
        import_export_config=None,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        if prop_name in DATETIME_FIELDS:
            value = getattr(integration, prop_name)
            return value.isoformat() if value else None
        return super().serialize_property(
            integration,
            prop_name,
            import_export_config=import_export_config,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
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
    ) -> OAuthAccountIntegrationMixin:
        """
        Only a live copy keeps the account: a duplicate in a workspace, or a
        published copy of one, and only while whoever connected it is still a
        member there. Anything else drops the account, tokens, scopes and who
        connected it, so the imported integration must be connected again:
        - a file or template, which anyone could have written;
        - a snapshot, which has no workspace: it never stores the account, so
          restoring one can't bring back an account that was disconnected, or
          one of a member who has left, since it was taken.
        """

        values = dict(serialized_values)
        if not self.keeps_connection(
            application, values, id_mapping, import_export_config
        ):
            for name in self.get_connection_properties():
                values[name] = None
        values = self.clean_connection_values(values)
        return super().import_serialized(
            application,
            values,
            id_mapping,
            import_export_config=import_export_config,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

    def clean_connection_values(self, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Turn the serialized connection into values the model accepts, whatever
        the file says. A type with fields of its own cleans those too.

        :param values: The serialized integration.
        :return: The values to import.
        """

        for name in ACCOUNT_TEXT_FIELDS:
            values[name] = str(values.get(name) or "")[:255]
        values["access_token"] = values.get("access_token") or ""
        values["refresh_token"] = values.get("refresh_token") or ""
        scopes = values.get("scopes")
        values["scopes"] = (
            [scope for scope in scopes if isinstance(scope, str)]
            if isinstance(scopes, list)
            else []
        )
        for name in DATETIME_FIELDS:
            values[name] = self._parse_datetime(values.get(name))
        connected_by_id = values.get("connected_by_id")
        values["connected_by_id"] = (
            connected_by_id if isinstance(connected_by_id, int) else None
        )
        for name in self.model_class.extra_connection_fields:
            if values.get(name) is None:
                values[name] = self.model_class._meta.get_field(name).get_default()
        return values

    def keeps_connection(
        self,
        application: Application,
        values: Dict[str, Any],
        id_mapping: Dict,
        import_export_config: Optional[ImportExportConfig],
    ) -> bool:
        """
        :param application: Where the integration is imported.
        :param values: The serialized integration.
        :param id_mapping: The import's id mapping. A publish names the
            workspace it publishes from.
        :param import_export_config: How it's imported.
        :return: Whether the imported integration keeps the connected account.
        """

        config = import_export_config
        if config is None or getattr(config, "is_template", False):
            return False
        is_publishing = getattr(config, "is_publishing", False)
        is_duplicate = getattr(config, "is_duplicate", False)
        if is_publishing:
            if not self.provider.keep_connection_in_published_copies:
                return False
        elif not (is_duplicate and self.provider.keep_connection_in_duplicates):
            return False
        workspace_id = application.workspace_id
        if workspace_id is None and is_publishing:
            workspace_id = (id_mapping or {}).get("import_workspace_id")
        connected_by_id = values.get("connected_by_id")
        if workspace_id is None or not isinstance(connected_by_id, int):
            return False
        return WorkspaceUser.objects.filter(
            workspace_id=workspace_id, user_id=connected_by_id
        ).exists()

    @staticmethod
    def _parse_datetime(value) -> Optional[datetime]:
        if not isinstance(value, str) or not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
