from django.dispatch import Signal

before_workspace_user_deleted = Signal()
before_workspace_user_updated = Signal()
before_user_deleted = Signal()

before_workspace_deleted = Signal()

user_updated = Signal()
user_deleted = Signal()
user_restored = Signal()
user_permanently_deleted = Signal()

workspace_created = Signal()
workspace_updated = Signal()
workspace_deleted = Signal()
workspace_restored = Signal()

workspace_user_added = Signal()
workspace_user_updated = Signal()
workspace_user_deleted = Signal()
workspaces_reordered = Signal()

application_created = Signal()
application_updated = Signal()
application_deleted = Signal()
application_imported = Signal()
applications_reordered = Signal()

permissions_updated = Signal()

workspace_invitation_updated_or_created = Signal()
workspace_invitation_accepted = Signal()
workspace_invitation_rejected = Signal()
