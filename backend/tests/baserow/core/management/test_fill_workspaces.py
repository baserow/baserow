from django.contrib.auth import get_user_model
from django.core.management import call_command

import pytest

from baserow.core.models import SharedApplication, WorkspaceUser

User = get_user_model()


@pytest.mark.django_db
def test_fill_workspaces_creates_a_person_who_administers_the_workspace():
    call_command("fill_workspaces", 1)

    membership = WorkspaceUser.objects.get(workspace__name="Auto generated 0")
    assert User.objects.filter(id=membership.user_id).exists()


@pytest.mark.django_db
def test_fill_workspaces_creates_the_shared_application_of_each_workspace():
    call_command("fill_workspaces", 2)

    shared_applications = SharedApplication.objects.filter(
        workspace__name__startswith="Auto generated "
    )
    assert sorted(shared_applications.values_list("workspace__name", flat=True)) == [
        "Auto generated 0",
        "Auto generated 1",
    ]
