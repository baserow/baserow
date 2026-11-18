from django.dispatch import Signal

# Sent before a snapshot, manual or automatic, is created, with the `workspace` and
# the `application`. A receiver can raise `MaximumSnapshotsReached` to stop it, for
# example once a workspace has been over its snapshot allowance for too long.
before_snapshot_created = Signal()

# Sent after the keep of an application or the workspace default keep changed, with
# the `workspace`. Raising a keep can take the workspace over its allowance when a
# plugin allows it, so the plugin can record when that happened.
snapshot_keep_updated = Signal()
