from django.core.management import call_command

import pytest

from baserow.core.models import SharedApplication, Workspace


@pytest.mark.django_db
def test_fill_users_creates_the_shared_application_of_each_new_workspace():
    call_command("fill_users", 3)

    # Not always 3: users whose generated email clashes are skipped.
    workspace_ids = sorted(Workspace.objects.values_list("id", flat=True))
    assert workspace_ids
    assert (
        sorted(SharedApplication.objects.values_list("workspace_id", flat=True))
        == workspace_ids
    )


@pytest.mark.django_db
def test_fill_users_in_an_existing_workspace_creates_no_shared_application(
    data_fixture,
):
    workspace = data_fixture.create_workspace()

    call_command("fill_users", 2, workspace_id=workspace.id)

    assert Workspace.objects.count() == 1
    assert not SharedApplication.objects.exists()
