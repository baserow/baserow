from django.dispatch import Signal

# Sent before a snapshot, manual or automatic, is created, with the `workspace` and
# the `application`. A receiver can raise `MaximumSnapshotsReached` to stop it, for
# example once a workspace has been over its snapshot allowance for too long.
before_snapshot_created = Signal()
