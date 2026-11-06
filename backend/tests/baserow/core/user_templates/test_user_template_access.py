from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.shortcuts import reverse

import pytest

from baserow.core.exceptions import TemplateDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.jobs.constants import JOB_FINISHED
from baserow.core.models import Template
from baserow.core.user_templates.archive import clear_template_archive_stamp
from baserow.core.user_templates.exceptions import TemplateBlocked
from baserow.core.user_templates.handler import UserTemplateHandler
from baserow.test_utils.helpers import user_template_plan_rows
from tests.baserow.core.user_templates.utils import (
    create_template,
    request_download,
    request_install,
    revision_ids,
    run_job,
    store_template_archive,
)

pytestmark = pytest.mark.usefixtures("use_tmp_media_root")


def fake_copy():
    """Skips the copy of an install."""

    return patch.object(
        UserTemplateHandler, "serialize_template_content", return_value=[]
    )


def fake_build():
    """Stores a file as the archive of a download instead of exporting it."""

    return patch.object(
        UserTemplateHandler,
        "build_template_archive",
        autospec=True,
        side_effect=lambda handler, revision, **kwargs: store_template_archive(
            revision
        ),
    )


def requested(request):
    """
    Requests a job, and returns it, or None if it's refused.

    :param request: Requests the job.
    :return: The job, or None.
    """

    try:
        return request()
    except (TemplateDoesNotExist, TemplateBlocked):
        return None


def indexes(revisions, ids):
    return "".join(str(revisions.index(id)) for id in ids) or "-"


def what_the_actor_gets(api_client, actor, token, root, revisions):
    """
    What the actor is shown and allowed of the template, as
    "opens:shown:installs", by the indexes of the revisions, "-" for none: the
    revisions it opens, the one its template page shows, and the one an install
    copies. Also checks that a download goes like an install.

    :param api_client: The API client.
    :param actor: The user, or an anonymous user.
    :param token: The token of the user, None when anonymous.
    :param root: The template.
    :param revisions: The ids of its revisions, oldest first.
    :return: The outcome.
    """

    opens = [
        id for id in revisions if Template.objects.get(id=id).is_openable_by(actor)
    ]
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"} if token else {}
    response = api_client.get(
        reverse("api:templates:item", kwargs={"slug": root.slug}), **headers
    )
    shown = response.json()["revision_id"] if response.status_code == 200 else None
    assert shown is None or shown in opens
    if token is None:
        return f"{indexes(revisions, opens)}:{indexes(revisions, [shown] if shown else [])}"

    target = actor.workspaceuser_set.get().workspace
    latest = actor.id == root.owner_id
    install = requested(lambda: request_install(actor, target, root, latest))
    installs = [] if install is None else [install.template_id]
    assert set(installs) <= set(opens)
    # Downloaded as shown, with the access of an install.
    shown_or_listed = shown or root.public_revision_id or root.id
    download = requested(
        lambda: request_download(actor, root, Template.objects.get(id=shown_or_listed))
    )
    assert (download is None) == (install is None)
    for job in [install, download]:
        if job is not None:
            job.delete()
    return ":".join(
        indexes(revisions, ids) for ids in [opens, [shown] if shown else [], installs]
    )


def started(job):
    """
    Runs a requested job, and returns whether it went past its checks.

    :param job: The install or download job.
    :return: True if it finished.
    """

    clear_template_archive_stamp()
    with fake_copy(), fake_build():
        return run_job(job).state == JOB_FINISHED


@pytest.mark.django_db
@pytest.mark.parametrize("actor", ["owner", "user", "anonymous", "admin"])
@pytest.mark.parametrize(
    "revision_states,listed,owner,user,anonymous,admin",
    user_template_plan_rows(
        "3",
        [
            # Per actor "opens:shown:installs", by the index of the revisions.
            (["private"], False, "0:0:0", "-:-:-", "-:-", "-:-:-"),
            (["shared"], False, "0:0:0", "-:-:-", "-:-", "-:-:-"),
            (["public"], True, "0:0:0", "0:0:0", "0:0", "0:0:0"),
            # An admin previews the review queue from the admin page only.
            (["in_review"], False, "0:0:0", "-:-:-", "-:-", "0:-:-"),
            (["rejected"], False, "0:0:0", "-:-:-", "-:-", "0:-:-"),
            (["resubmitted"], False, "0:0:0", "-:-:-", "-:-", "0:-:-"),
            (["withdrawn_rejected"], False, "0:0:0", "-:-:-", "-:-", "-:-:-"),
            (["rejected", "private"], False, "01:1:1", "-:-:-", "-:-", "0:-:-"),
            (["rejected", "in_review"], False, "01:1:1", "-:-:-", "-:-", "1:-:-"),
            (["private", "in_review"], False, "01:1:1", "-:-:-", "-:-", "1:-:-"),
            # The owner is shown and installs their edit, everybody else the
            # listed revision.
            (["public", "private"], True, "01:1:1", "0:0:0", "0:0", "0:0:0"),
            (["public", "in_review"], True, "01:1:1", "0:0:0", "0:0", "01:0:0"),
            (["public", "rejected"], True, "01:1:1", "0:0:0", "0:0", "01:0:0"),
            (["rejected", "public"], True, "01:1:1", "1:1:1", "1:1", "1:1:1"),
            # Only its owner opens a blocked template, without installing it.
            (["blocked"], False, "0:0:-", "-:-:-", "-:-", "-:-:-"),
            (["public_blocked"], False, "0:0:-", "-:-:-", "-:-", "-:-:-"),
            (["blocked", "in_review"], False, "01:1:-", "-:-:-", "-:-", "-:-:-"),
            (["marked"], False, "-:-:-", "-:-:-", "-:-", "-:-:-"),
            (["public", "marked"], False, "-:-:-", "-:-:-", "-:-", "-:-:-"),
            (["marked", "in_review"], False, "-:-:-", "-:-:-", "-:-", "-:-:-"),
        ],
    ),
)
def test_actor_gets_what_it_is_shown(
    api_client,
    data_fixture,
    actor,
    revision_states,
    listed,
    owner,
    user,
    anonymous,
    admin,
):
    expected = {"owner": owner, "user": user, "anonymous": anonymous, "admin": admin}
    template_owner, owner_token = data_fixture.create_user_and_token()
    if actor == "owner":
        signed_in, token = template_owner, owner_token
    elif actor == "anonymous":
        signed_in, token = AnonymousUser(), None
    else:
        signed_in, token = data_fixture.create_user_and_token(is_staff=actor == "admin")
    root = create_template(data_fixture, template_owner)
    jobs = []
    if token is not None:
        data_fixture.create_workspace(user=signed_in)
        # Requested while the actor may install it, and run once in the state.
        if actor != "owner":
            data_fixture.set_user_template_state(root, "public")
        target = signed_in.workspaceuser_set.get().workspace
        jobs = [
            request_install(signed_in, target, root, latest=actor == "owner"),
            request_download(signed_in, root),
        ]
        Template.objects.filter(id=root.id).update(
            public_revision=None, review_state=Template.ReviewState.NOT_SUBMITTED
        )
    data_fixture.set_user_template_revision_states(root, revision_states)
    revisions = revision_ids(root)
    for revision in Template.objects.filter(root=root):
        data_fixture.create_database_application(workspace=revision.workspace)
    root = Template.objects.get(id=root.id)
    starts = [started(job) for job in jobs]

    gets = what_the_actor_gets(api_client, signed_in, token, root, revisions)

    assert gets == expected[actor]
    browser = CoreHandler().list_templates(AnonymousUser(), listed=True)
    assert browser.filter_by_root(id=root.id).exists() is listed
    # Checked again when it starts.
    assert starts == [not gets.endswith(":-")] * len(jobs)
