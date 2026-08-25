from collections.abc import Mapping
from functools import cached_property

from django.db import models

from baserow.contrib.builder.domains.models import Domain, PublishDomainJob
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.theme.models import (
    ButtonThemeConfigBlock,
    ColorThemeConfigBlock,
    TypographyThemeConfigBlock,
)
from baserow.core.models import Application, UserFile

__all__ = [
    "Builder",
    "Page",
    "Domain",
    "PublishDomainJob",
    "Element",
    "ColorThemeConfigBlock",
    "TypographyThemeConfigBlock",
    "ButtonThemeConfigBlock",
]

DEFAULT_BUILDER_BREAKPOINTS = {"mobile": 640, "tablet": 1024}
LEGACY_BUILDER_BREAKPOINTS = {"mobile": 500, "tablet": 768}
MIN_BUILDER_BREAKPOINT = 320
MAX_BUILDER_BREAKPOINT = 1920


class BuilderBreakpointsValidationError(ValueError):
    """Raised when a Builder breakpoint configuration is invalid."""

    def __init__(self, errors: dict[str, list[str]]):
        self.errors = errors
        super().__init__("Invalid builder breakpoints.")


def validate_builder_breakpoints(breakpoints: object) -> dict[str, int]:
    """
    Validates the persisted Builder breakpoint configuration.

    The mobile and tablet breakpoints define the responsive layout boundaries. Extra
    named breakpoints are supported, but every persisted breakpoint must be an integer
    within the same supported range.
    """

    if not isinstance(breakpoints, Mapping):
        raise BuilderBreakpointsValidationError(
            {"non_field_errors": ["The breakpoints must be an object."]}
        )

    errors: dict[str, list[str]] = {}
    if "mobile" not in breakpoints or "tablet" not in breakpoints:
        message = "The mobile and tablet breakpoints must be configured together."
        errors = {"mobile": [message], "tablet": [message]}

    for name, value in breakpoints.items():
        if not isinstance(name, str):
            errors.setdefault("non_field_errors", []).append(
                "Breakpoint names must be strings."
            )
        elif not isinstance(value, int) or isinstance(value, bool):
            errors[name] = ["A breakpoint must be an integer."]
        elif not MIN_BUILDER_BREAKPOINT <= value <= MAX_BUILDER_BREAKPOINT:
            errors[name] = [
                "A breakpoint must be between "
                f"{MIN_BUILDER_BREAKPOINT} and {MAX_BUILDER_BREAKPOINT} pixels."
            ]

    if errors:
        raise BuilderBreakpointsValidationError(errors)

    if breakpoints["mobile"] >= breakpoints["tablet"]:
        raise BuilderBreakpointsValidationError(
            {
                "tablet": [
                    "The tablet breakpoint must be greater than the mobile breakpoint."
                ]
            }
        )

    return dict(breakpoints)


def default_builder_breakpoints():
    return DEFAULT_BUILDER_BREAKPOINTS.copy()


class Builder(Application):
    breakpoints = models.JSONField(
        default=default_builder_breakpoints,
        db_default=LEGACY_BUILDER_BREAKPOINTS,
    )

    favicon_file = models.ForeignKey(
        UserFile,
        on_delete=models.SET_NULL,
        null=True,
        related_name="builder_favicon_file",
    )

    login_page = models.OneToOneField(
        Page,
        on_delete=models.SET_NULL,
        help_text="The login page for this application. This is related to the "
        "visibility settings of builder pages.",
        related_name="login_page",
        null=True,
    )

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new:
            from baserow.contrib.builder.pages.handler import PageHandler

            # Create the shared page
            PageHandler().create_shared_page(self)

    def get_parent(self):
        # If we had select related workspace we want to keep it
        self.application_ptr.workspace = self.workspace
        # Parent is the Application here even if it's at the "same" level
        # but it's a more generic type
        return self.application_ptr

    @property
    def visible_pages(self):
        return self.page_set(manager="objects_without_shared")

    @cached_property
    def shared_page(self):
        from baserow.contrib.builder.pages.handler import PageHandler

        return PageHandler().get_shared_page(self)

    @property
    def is_published(self) -> bool:
        return hasattr(self, "published_from")

    def get_workspace(self):
        from baserow.contrib.builder.domains.handler import DomainHandler

        if not self.workspace_id:
            domain = DomainHandler().get_domain_for_builder(self)
            return domain.builder.workspace
        else:
            return self.workspace
