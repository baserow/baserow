import os
import sys
import time
import uuid

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from faker import Faker
from tqdm import tqdm

from baserow.core.models import (
    WORKSPACE_USER_PERMISSION_ADMIN,
    WORKSPACE_USER_PERMISSION_MEMBER,
    UserProfile,
    Workspace,
    WorkspaceUser,
)
from baserow.core.registries import subject_type_registry
from baserow.core.utils import grouper

User = get_user_model()

EMAIL_PREFIX = "baserow_prefix_to_ensure_we_never_accidentally_email_a_real_person_"
CLASHING_EMAIL_COUNTER = 0


class Command(BaseCommand):
    help = (
        "Fills baserow with random users. If no workspace is provided, a new one will be created, "
        "otherwise the users will be added to the workspace of the provided id."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "limit", type=int, help="Amount of users that need to be inserted."
        )
        parser.add_argument(
            "--workspace_id", type=int, help="The workspace id.", default=None
        )

    def handle(self, *args, **options):
        limit = options["limit"]

        workspace_id = options["workspace_id"]
        if workspace_id is not None:
            try:
                workspace = Workspace.objects.get(id=workspace_id)
            except Workspace.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f"The workspace with id {workspace_id} was not found."
                    )
                )
                sys.exit(1)
        else:
            workspace = None

        tick = time.time()
        crete_users(limit, workspace)
        tock = time.time()
        self.stdout.write(
            self.style.SUCCESS(
                f"{limit} users have been created in {(tock - tick):.1f} secs."
            )
        )


def generate_unique_user_emails(fake, count):
    global CLASHING_EMAIL_COUNTER
    usernames = set(EMAIL_PREFIX + fake.email() for _ in range(count))
    valid_usernames = set()

    for _ in range(10):
        existing_usernames = set(
            User.objects.filter(username__in=usernames).values_list(
                "username", flat=True
            )
        )
        valid_usernames |= usernames - existing_usernames

        if len(existing_usernames) == 0:
            break

        # The fake email generator often creates the same email over
        # and over, user a simple counter to ensure username
        # uniqueness so we can insert the user successfully.
        CLASHING_EMAIL_COUNTER += 1
        usernames = set(
            [str(CLASHING_EMAIL_COUNTER) + username for username in existing_usernames]
        )

    return list(valid_usernames)


def crete_users(limit, workspace=None):
    fake = Faker()
    batch_size = 100

    with tqdm(
        total=limit, desc=f"Creating {limit} users in worker {os.getpid()}"
    ) as pbar:
        for group in grouper(batch_size, range(limit)):
            users, users_profiles, workspaces, workspace_users = [], [], [], []
            for username in generate_unique_user_emails(fake, len(group)):
                password = str(uuid.uuid4())
                name = fake.name()

                user = User(
                    first_name=name,
                    email=username,
                    username=username,
                    password=password,
                )
                users.append(user)

                # Manually create the user profile
                users_profiles.append(UserProfile(user=user))

                if workspace is None:
                    new_workspace = Workspace(name=name + "'s workspace")
                    workspaces.append(new_workspace)
                    workspace_user = WorkspaceUser(
                        workspace=new_workspace,
                        user=user,
                        order=1,
                        permissions=WORKSPACE_USER_PERMISSION_ADMIN,
                    )
                else:
                    workspace_user = WorkspaceUser(
                        user=user,
                        workspace=workspace,
                        order=1,
                        permissions=WORKSPACE_USER_PERMISSION_MEMBER,
                    )
                workspace_users.append(workspace_user)
                pbar.update(1)

            with transaction.atomic():
                User.objects.bulk_create(users, batch_size=batch_size)
                subject_type_registry.get_by_model(
                    User
                ).synchronize_persistent_subjects(users)
                for profile in users_profiles:
                    profile.subject_id = profile.user.pk
                UserProfile.objects.bulk_create(users_profiles, batch_size=batch_size)
                if workspaces:
                    Workspace.objects.bulk_create(workspaces, batch_size=batch_size)
                WorkspaceUser.objects.bulk_create(
                    workspace_users, batch_size=batch_size
                )
                pbar.refresh()
