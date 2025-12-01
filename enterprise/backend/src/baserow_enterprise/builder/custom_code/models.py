from django.db import models

from baserow.core.fields import AutoOneToOneField


class ScriptType(models.TextChoices):
    STYLESHEET = "stylesheet", "Stylesheet"
    JAVASCRIPT = "javascript", "JavaScript"


class LoadType(models.TextChoices):
    NONE = "", "None"
    DEFER = "defer", "Defer"
    ASYNC = "async", "Async"


class CrossoriginType(models.TextChoices):
    NONE = "", "None"
    ANONYMOUS = "anonymous", "Anonymous"
    CREDENTIALS = "credentials", "Use credentials"


class BuilderCustomCode(models.Model):
    builder = AutoOneToOneField(
        "builder.Builder",
        on_delete=models.CASCADE,
        related_name="custom_code",
        help_text="The builder associated with this custom code.",
    )

    css = models.TextField(help_text="Custom CSS code.", blank=True)

    js = models.TextField(help_text="Custom JavaScript code.", blank=True)


class BuilderCustomScript(models.Model):
    builder = models.ForeignKey(
        "builder.Builder",
        on_delete=models.CASCADE,
        related_name="scripts",
        help_text="The builder associated with this custom script.",
    )

    order = models.PositiveIntegerField()

    type = models.CharField(
        max_length=20,
        choices=ScriptType.choices,
        default=ScriptType.JAVASCRIPT,
        help_text="The type of script.",
    )

    url = models.URLField(help_text="The URL of the script.", blank=True)

    load_type = models.CharField(
        max_length=10,
        choices=LoadType.choices,
        default=LoadType.NONE,
        help_text="The load type of the script.",
    )
    crossorigin = models.CharField(
        max_length=20,
        choices=CrossoriginType.choices,
        default=CrossoriginType.NONE,
        help_text="The Crossorigin type of the script.",
    )
