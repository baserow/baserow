from django.contrib.auth import get_user_model
from django.db import models

from baserow.core.mixins import (
    HierarchicalModelMixin,
    ParentWorkspaceTrashableModelMixin,
)
from baserow.core.models import Workspace

User = get_user_model()


class MCPEndpoint(
    HierarchicalModelMixin,
    ParentWorkspaceTrashableModelMixin,
    models.Model,
):
    """
    An MCP endpoint can be used to authenticate and access the Baserow MCP server.
    It provides API access to the Machine Comprehension Protocol.
    """

    name = models.CharField(
        max_length=100,
        help_text="The human readable name of the MCP endpoint for the user.",
    )
    key = models.CharField(
        max_length=32,
        unique=True,
        db_index=True,
        help_text="The unique endpoint key that can be used to authorize for the MCP service.",
    )
    created = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, help_text="The user that owns the MCP endpoint."
    )
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        help_text="The workspace that the MCP endpoint belongs to.",
    )

    class Meta:
        ordering = ("id",)

    def get_parent(self):
        return self.workspace
