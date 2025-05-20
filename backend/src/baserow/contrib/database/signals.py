# from django.dispatch import receiver

# from baserow.core.signals import workspace_created

#
# @receiver(workspace_created)
# def create_workspace_settings_table(sender, workspace, user, **kwargs):
#     """
#     Creates WorkspaceDatabaseSettings table for the workspace.
#     """
#
#     from .models import WorkspaceDatabaseSettings
#
#     WorkspaceDatabaseSettings.objects.get_or_create(workspace_id=workspace.id)
