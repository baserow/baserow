import re
from typing import Iterable

from oauth2_provider.oauth2_validators import OAuth2Validator

MCP_SCOPE = "mcp"
ENDPOINT_SCOPE_RE = re.compile(r"^endpoint:(\d+)$")


def endpoint_scope(endpoint_id: int) -> str:
    return f"endpoint:{endpoint_id}"


def endpoint_id_from_scopes(scopes: Iterable[str]) -> int | None:
    for scope in scopes:
        match = ENDPOINT_SCOPE_RE.match(scope)
        if match:
            return int(match.group(1))
    return None


class MCPOAuth2Validator(OAuth2Validator):
    """
    Accepts the static `mcp` scope plus one `endpoint:<id>` scope. The endpoint scope
    is never requested by clients; the consent view adds it when issuing the code.
    """

    def validate_scopes(self, client_id, scopes, client, request, *args, **kwargs):
        scopes = list(scopes)
        endpoint_scopes = [s for s in scopes if ENDPOINT_SCOPE_RE.match(s)]
        others = [s for s in scopes if not ENDPOINT_SCOPE_RE.match(s)]
        return len(endpoint_scopes) <= 1 and set(others) <= {MCP_SCOPE}
