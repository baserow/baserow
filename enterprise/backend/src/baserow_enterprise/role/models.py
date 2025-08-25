import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from baserow.core.mixins import CreatedAndUpdatedOnMixin
from baserow.core.models import Operation, Workspace


class RoleQuerySet(models.QuerySet):
    def get_by_natural_key(self, uid):
        return self.get(uid=uid)


class RoleManager(models.Manager):
    """
    A manager that adds `.get_by_natural_key()` to both Manager and QuerySet.
    """

    def get_queryset(self):
        return RoleQuerySet(self.model, using=self._db)

    def get_by_natural_key(self, uid):
        return self.get_queryset().get_by_natural_key(uid)


class Role(CreatedAndUpdatedOnMixin):
    """
    A Role is a set of allowed operation granted to those whom are associated to.
    """

    uid = models.CharField(
        max_length=255,
        unique=True,
        default=uuid.uuid4,
        help_text="Role unique identifier.",
    )
    name = models.CharField(max_length=255, help_text="Role human readable name.")
    operations = models.ManyToManyField(
        Operation,
        related_name="roles",
        help_text="List of allowed operation for this role.",
    )
    default = models.BooleanField(
        default=False,
        help_text="True if this role is a default role. The default role are the roles you can use by default.",
    )
    hidden = models.BooleanField(
        default=False,
        db_default=False,
        help_text="Hidden roles are not visible to the user and cannot be set. These "
        "are used for internal purposes.",
    )

    workspace = models.ForeignKey(
        Workspace,
        null=True,
        related_name="roles",
        on_delete=models.CASCADE,
        help_text="The optional group that this role belongs to.",
    )

    objects = RoleManager()

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return f"<Role '{self.name}' ({self.id})>"

    def natural_key(self):
        return (self.uid,)

    class Meta:
        ordering = ("id",)
        indexes = [
            models.Index(fields=["uid"]),
        ]


class RoleAssignment(CreatedAndUpdatedOnMixin):
    """
    A RoleAssignment is the association between a `Role` and a `Subject` for a
    particular `Workspace` over a given `Scope`. A Subject can be a user or anything
    else that can operate with the Baserow data.
    """

    subject = GenericForeignKey("subject_type", "subject_id")
    subject_id = models.IntegerField(help_text="The subject ID.")
    subject_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="The subject type.",
        related_name="role_subject_assignments",
    )

    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        help_text="The role given to the subject for the group.",
    )

    workspace = models.ForeignKey(
        Workspace,
        related_name="role_assignments",
        on_delete=models.CASCADE,
        help_text="The group that this role assignment belongs to.",
    )

    scope = GenericForeignKey("scope_type", "scope_id")
    scope_id = models.IntegerField(help_text="The unique scope ID.")
    scope_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="The scope type.",
        related_name="role_scope_assignments",
    )

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return f"<RoleAssignment {self.subject} - {self.role.name} - {self.workspace} - {self.scope}>"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["scope_id", "scope_type", "subject_id", "subject_type"],
                name="subject_and_scope_uniqueness",
            )
        ]
        ordering = ("id",)
