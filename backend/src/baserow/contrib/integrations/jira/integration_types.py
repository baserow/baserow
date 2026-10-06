import base64
from typing import Dict

from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.types import IntegrationDict

from .models import JIRA_AUTHENTICATION_API_TOKEN, JiraIntegration


class JiraIntegrationDict(IntegrationDict):
    url: str
    authentication: str
    username: str
    api_token: str


class JiraIntegrationType(IntegrationType):
    type = "jira"
    model_class = JiraIntegration
    SerializedDict = JiraIntegrationDict

    allowed_fields = ["url", "authentication", "username", "api_token"]
    serializer_field_names = ["url", "authentication", "username", "api_token"]
    request_serializer_field_names = serializer_field_names
    secret_fields = ["api_token"]
    sensitive_fields = ["api_token"]
    # A saved token must not be sent to a site somebody else typed in.
    secret_field_dependencies = {"api_token": ["url"]}

    def import_serialized(self, parent, serialized_values, id_mapping, **kwargs):
        if serialized_values.get("api_token") is None:
            serialized_values["api_token"] = ""
        return super().import_serialized(
            parent, serialized_values, id_mapping, **kwargs
        )

    def auth_headers(self, integration: JiraIntegration) -> Dict[str, str]:
        if integration.authentication == JIRA_AUTHENTICATION_API_TOKEN:
            credentials = f"{integration.username}:{integration.api_token}".encode()
            return {"Authorization": f"Basic {base64.b64encode(credentials).decode()}"}
        return {"Authorization": f"Bearer {integration.api_token}"}
