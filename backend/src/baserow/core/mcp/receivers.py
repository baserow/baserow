from django.dispatch import receiver

from baserow.core.signals import workspace_user_deleted


@receiver(workspace_user_deleted)
def revoke_mcp_grants_of_removed_workspace_user(sender, workspace_user, **kwargs):
    from baserow.core.mcp.handler import MCPEndpointHandler

    MCPEndpointHandler().revoke_workspace_grants(
        workspace_user.user_id, workspace_user.workspace_id
    )
