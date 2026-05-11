import json
import random
import string
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from baserow.contrib.builder.application_types import BuilderApplicationType
from baserow.core.handler import CoreHandler
from baserow.core.models import (
    WORKSPACE_USER_PERMISSION_ADMIN,
    Template,
    Workspace,
    WorkspaceUser,
)

User = get_user_model()


def find_builder_template_slugs() -> list:
    """
    Reads template JSON files and returns slugs for templates that contain at
    least one builder application.
    """
    templates_dir = Path(settings.APPLICATION_TEMPLATES_DIR)
    slugs = []
    for path in sorted(templates_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        if any(
            e.get("type") == BuilderApplicationType.type for e in data.get("export", [])
        ):
            slugs.append(path.stem)
    return slugs


def get_builder_templates():
    """Returns a queryset of Template instances that contain builder applications."""
    slugs = find_builder_template_slugs()
    return Template.objects.filter(slug__in=slugs)


def install_builder_templates(user, workspace, templates) -> dict:
    """
    Installs the given templates into the workspace.

    Returns a dict mapping template slug -> list of installed Application instances.
    """
    results = {}
    for template in templates:
        apps, _ = CoreHandler().install_template(
            user=user, workspace=workspace, template=template
        )
        results[template.slug] = apps
    return results


def _random_email():
    chars = string.ascii_lowercase + string.digits
    username = "".join(random.choices(chars, k=12))  # nosec B311
    return f"{username}@baserow.io"


def create_temp_user_and_workspace(workspace_name="Builder template tools"):
    """Creates a throwaway user and workspace for template installation."""
    workspace = Workspace.objects.create(name=workspace_name)
    email = _random_email()
    user = User(first_name="Temp", email=email, username=email)
    user.set_unusable_password()
    user.save()
    WorkspaceUser.objects.create(
        workspace=workspace,
        user=user,
        order=0,
        permissions=WORKSPACE_USER_PERMISSION_ADMIN,
    )
    return user, workspace


class Command(BaseCommand):
    help = (
        "Installs all builder templates into a temporary workspace. "
        "Useful for verifying template installs work without exporting anything."
    )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "This command is intended for development use only "
                "and must not be run in production."
            )
        templates = list(get_builder_templates())
        if not templates:
            self.stdout.write("No builder templates found.")
            return

        self.stdout.write(f"Installing {len(templates)} builder template(s)...")
        user, workspace = create_temp_user_and_workspace()
        try:
            results = install_builder_templates(user, workspace, templates)
            for slug, apps in results.items():
                self.stdout.write(
                    self.style.SUCCESS(f"  Installed: {slug} ({len(apps)} app(s))")
                )
        finally:
            workspace.delete()
            User.objects.filter(pk=user.pk).delete()

        self.stdout.write(self.style.SUCCESS("Done."))
