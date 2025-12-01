from baserow.core.mcp.models import MCPEndpoint
from baserow.core.utils import random_string


class MCPFixtures:
    def create_mcp_endpoint(self, **kwargs):
        if "name" not in kwargs:
            kwargs["name"] = self.fake.name()

        if "key" not in kwargs:
            kwargs["key"] = random_string(32)

        if "user" not in kwargs:
            kwargs["user"] = self.create_user()

        if "workspace" not in kwargs:
            kwargs["workspace"] = self.create_workspace(user=kwargs["user"])

        return MCPEndpoint.objects.create(**kwargs)
