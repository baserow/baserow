from django.contrib.auth import get_user_model
from django.db import models

from baserow.core.mixins import CreatedAndUpdatedOnMixin

User = get_user_model()

SKILL_NAME_MAX_LENGTH = 160
SKILL_DESCRIPTION_MAX_LENGTH = 500
SKILL_CONTENT_MAX_LENGTH = 50000


class WorkspaceSkill(CreatedAndUpdatedOnMixin, models.Model):
    """
    A reusable markdown document with instructions that agents of the
    workspace can follow. The description tells a model when the skill
    applies; the content is what it follows once it does. Skills are owned by
    the workspace so every agent (and later the assistant) can share them.
    """

    # A string reference: `core.models` imports this module to register it.
    workspace = models.ForeignKey(
        "core.Workspace", on_delete=models.CASCADE, related_name="skills"
    )
    name = models.CharField(max_length=SKILL_NAME_MAX_LENGTH)
    description = models.TextField(
        blank=True,
        db_default="",
        help_text="One or two sentences on when an agent should use the skill.",
    )
    content = models.TextField(
        blank=True, db_default="", help_text="The markdown instructions."
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"], name="unique_workspace_skill_name"
            )
        ]
