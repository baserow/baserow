from django.db import models


class Subject(models.Model):
    """Retained attribution identity, independent of authentication and permissions."""

    # Deliberately not AutoField: all identities share the auth User sequence.
    id = models.IntegerField(primary_key=True)
    type = models.CharField(max_length=64)
    name = models.TextField()
    uid = models.TextField()
    state = models.CharField(max_length=16, default="live", db_default="live")

    def get_type(self):
        """Return the registered actor type represented by this retained identity."""
        from baserow.core.subject.registries import subject_type_registry

        return subject_type_registry.get(self.type)

    class Meta:
        indexes = [models.Index(fields=["type", "uid"], name="subject_type_uid_idx")]


class SubjectRollout(models.Model):
    """Persisted, explicit activation barrier for non-human field references."""

    agent_references_enabled = models.BooleanField(default=False, db_default=False)
