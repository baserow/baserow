import typing

from django.db import models

from baserow.contrib.builder.pages.validators import path_validation
from baserow.core.jobs.mixins import (
    JobWithUndoRedoIds,
    JobWithUserIpAddress,
    JobWithWebsocketId,
)
from baserow.core.jobs.models import Job
from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    HierarchicalModelMixin,
    OrderableMixin,
    TrashableModelMixin,
)

if typing.TYPE_CHECKING:
    from baserow.contrib.builder.models import Builder


class PageWithoutSharedManager(models.Manager):
    """
    Manager for the Page model.
    Excludes by default the shared page.
    """

    def get_queryset(self):
        return super().get_queryset().filter(shared=False)


class Page(
    HierarchicalModelMixin,
    TrashableModelMixin,
    CreatedAndUpdatedOnMixin,
    OrderableMixin,
    models.Model,
):
    class VISIBILITY_TYPES(models.TextChoices):
        ALL = "all"
        LOGGED_IN = "logged-in"

    class ROLE_TYPES(models.TextChoices):
        ALLOW_ALL = "allow_all"
        ALLOW_ALL_EXCEPT = "allow_all_except"
        DISALLOW_ALL_EXCEPT = "disallow_all_except"

    objects = models.Manager()
    objects_without_shared = PageWithoutSharedManager()

    builder = models.ForeignKey("builder.Builder", on_delete=models.CASCADE)
    order = models.PositiveIntegerField()
    name = models.CharField(max_length=255)
    path = models.CharField(max_length=255, validators=[path_validation])
    path_params = models.JSONField(default=dict)
    query_params = models.JSONField(default=list, blank=True, db_default=[])

    # Shared page is invisible to the user but contains all shared data like
    # shared data sources or shared elements. That way we keep everything working as
    # usual for this shared items but we have an easy way to get them.
    # We should have only one shared page per builder. Shared page can't be create
    # directly. They are created on demand when a shared element is created.
    shared = models.BooleanField(default=False, db_default=False)

    visibility = models.CharField(
        choices=VISIBILITY_TYPES.choices,
        max_length=20,
        db_index=True,
        default=VISIBILITY_TYPES.ALL,
        db_default=VISIBILITY_TYPES.ALL,
        help_text="Controls the page's visibility. When set to 'logged-in', the builder's login_page must also be set.",
    )

    role_type = models.CharField(
        choices=ROLE_TYPES.choices,
        max_length=19,
        db_index=True,
        default=ROLE_TYPES.ALLOW_ALL,
        db_default=ROLE_TYPES.ALLOW_ALL,
        help_text="Role type is used in conjunction with roles to control access to this page.",
    )
    roles = models.JSONField(
        default=list,
        db_default=[],
        help_text="List of user roles that are associated with this page. Used in conjunction with role_type.",
    )

    class Meta:
        ordering = (
            "-shared",  # First page is the shared one if any.
            "order",
        )
        unique_together = [["builder", "name"], ["builder", "path"]]
        indexes = [
            models.Index(fields=["-shared", "order"]),
            models.Index(fields=["builder", "-shared", "order"]),
        ]

    def get_parent(self):
        return self.builder

    @classmethod
    def get_last_order(cls, builder: "Builder"):
        queryset = Page.objects_without_shared.filter(builder=builder)
        return cls.get_highest_order_of_queryset(queryset) + 1


class DuplicatePageJob(
    JobWithUserIpAddress, JobWithWebsocketId, JobWithUndoRedoIds, Job
):
    original_page = models.ForeignKey(
        Page,
        null=True,
        related_name="duplicated_by_jobs",
        on_delete=models.SET_NULL,
        help_text="The baserow page to duplicate.",
    )

    duplicated_page = models.OneToOneField(
        Page,
        null=True,
        related_name="duplicated_from_jobs",
        on_delete=models.SET_NULL,
        help_text="The duplicated Baserow page.",
    )
