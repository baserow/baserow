import random
import string
import time

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from loguru import logger

from baserow.core.handler import CoreHandler
from baserow.core.management.utils import run_command_concurrently
from baserow.core.models import (
    WORKSPACE_USER_PERMISSION_ADMIN,
    Template,
    Workspace,
    WorkspaceUser,
)

User = get_user_model()


def random_name():
    first_names = [
        "John",
        "Jane",
        "Alex",
        "Emily",
        "Chris",
        "Sara",
        "Michael",
        "Laura",
        "David",
        "Olivia",
    ]
    last_names = [
        "Smith",
        "Johnson",
        "Brown",
        "Williams",
        "Jones",
        "Garcia",
        "Miller",
        "Davis",
        "Martinez",
        "Lopez",
    ]
    return f"{random.choice(first_names)} {random.choice(last_names)}"  # nosec b331


# Generate a random email
def random_email():
    domains = ["example.com", "mail.com", "test.org", "random.net", "demo.co"]
    username = "".join(
        random.choices(string.ascii_lowercase + string.digits, k=8)  # nosec b331
    )
    return f"{username}@{random.choice(domains)}"  # nosec b331


class Command(BaseCommand):
    help = (
        "Creates a user and workspace for every, and fills it with all the templates. "
        "Can be used to fill up the database to replicate production like scenarios."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "limit", type=int, help="Amount of workspaces that need to be created."
        )
        parser.add_argument(
            "--concurrency",
            nargs="?",
            type=int,
            help="How many concurrent processes should be used to create workspaces.",
            default=1,
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        concurrency = options["concurrency"]

        tick = time.time()
        if concurrency == 1:
            for i in range(0, limit):
                workspace = Workspace.objects.create(name=f"Auto generated {i}")

                email = random_email()
                user = User(first_name=random_name(), email=email, username=email)
                user.save()

                WorkspaceUser.objects.create(
                    workspace=workspace,
                    user=user,
                    order=0,
                    permissions=WORKSPACE_USER_PERMISSION_ADMIN,
                )

                for template in Template.objects.all():
                    CoreHandler().install_template(
                        user=user, workspace=workspace, template=template
                    )
                    logger.success(
                        f"installed {template.name} in workspace {workspace.id} ("
                        f"iteration {i})"
                    )

        else:
            concurrency_args = [
                "./baserow",
                "fill_workspaces",
                str(int(limit / concurrency)),
                "--concurrency",
                "1",
            ]
            run_command_concurrently(
                concurrency_args,
                concurrency,
            )

        tock = time.time()
        self.stdout.write(
            self.style.SUCCESS(
                f"{limit} workspaces have been inserted in {(tock - tick):.1f} seconds."
            )
        )
