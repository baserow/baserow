from django.contrib.auth import get_user_model
from django.core.management import call_command

import pytest

from baserow.core.models import WorkspaceUser

User = get_user_model()


@pytest.mark.django_db
def test_fill_workspaces_creates_a_person_who_administers_the_workspace():
    call_command("fill_workspaces", 1)

    membership = WorkspaceUser.objects.get(workspace__name="Auto generated 0")
    assert User.objects.filter(id=membership.user_id).exists()
