from datetime import datetime, timezone
from unittest.mock import patch

from django.db import connection
from django.shortcuts import reverse
from django.test.utils import CaptureQueriesContext

import pytest
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from baserow.api.admin.templates.views import serialize_admin_row
from baserow.core.models import Template
from baserow.test_utils.helpers import user_template_plan_rows

pytestmark = pytest.mark.django_db

LIST_URL = reverse("api:admin:templates:list")
COUNTS_URL = reverse("api:admin:templates:counts")
# The states of the templates on the admin page.
LISTED_STATES = ["in_review", "public", "rejected"]
# The reason set by `set_user_template_state`.
REASONS = {"rejected": "Reason"}


def create_template(data_fixture, state="private", **kwargs):
    template = data_fixture.create_user_template(blocked_reason="Spam", **kwargs)
    return data_fixture.set_user_template_state(template, state)


def list_admin_templates(api_client, token, url=LIST_URL, **params):
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"} if token else {}
    return api_client.get(url, params, **headers)


def admin_rows(api_client, token, state, *fields, **params):
    """
    Lists a tab of the admin page.

    :param api_client: The API client.
    :param token: The token of a staff user.
    :param state: The state the tab lists.
    :param fields: The fields to keep of each row, all of them by default.
    :param params: The other query parameters.
    :return: The rows, each as the value of its only field, or as a tuple of
        `fields`.
    """

    response = list_admin_templates(api_client, token, state=state, **params)
    assert response.status_code == HTTP_200_OK
    rows = response.json()["results"]
    if len(fields) == 1:
        return [row[fields[0]] for row in rows]
    return [tuple(row[field] for field in fields) if fields else row for row in rows]


def get_staff_token(data_fixture):
    return data_fixture.create_user_and_token(is_staff=True)[1]


def review_template(api_client, token, action, template_id, **body):
    url = reverse(f"api:admin:templates:{action}", kwargs={"template_id": template_id})
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"} if token else {}
    return api_client.post(url, body, format="json", **headers)


@freeze_time("2026-10-01 12:00")
def test_list_rows(api_client, data_fixture):
    token = get_staff_token(data_fixture)
    author = data_fixture.create_user(first_name="Ann", email="ann@example.com")
    with freeze_time("2026-09-30 12:00"):
        edited = create_template(data_fixture, "public", user=author, name="First")
    # Dated by its latest revision.
    category = data_fixture.create_template_category(name="Planning")
    latest = data_fixture.create_user_template_revision(
        edited, name="Latest", description="Text", category=category
    )
    # Stays listed while its edit is in review.
    data_fixture.set_user_template_state(edited, "in_review", latest)
    without_author = create_template(data_fixture, "in_review", author=None)
    data_fixture.create_template()

    response = list_admin_templates(api_client, token, state="in_review")

    assert response.status_code == HTTP_200_OK
    rows = {row["id"]: row for row in response.json()["results"]}
    assert response.json()["count"] == len(rows) == 2
    assert rows[edited.id] == {
        "id": edited.id,
        "revision_id": latest.id,
        "type": "user",
        "name": "Latest",
        "description": "Text",
        "icon": "document",
        # Previewed by the admin: the content of the revision.
        "workspace_id": latest.workspace_id,
        "open_application": None,
        "categories": [{"id": category.id, "name": "Planning"}],
        "author": {"id": author.id, "first_name": "Ann", "email": "ann@example.com"},
        "state": "in_review",
        "reason": None,
        "listed": True,
        "can_approve": True,
        "edited_since_submitted": False,
        "can_reject": True,
        # Only the edit is rejected.
        "reject_unlists": False,
        "updated_on": "2026-10-01T12:00:00Z",
    }
    assert rows[without_author.id]["author"] is None
    # The ids are of the templates, not of their latest revisions.
    assert admin_rows(
        api_client, token, "in_review", "revision_id", ids=str(edited.id)
    ) == [latest.id]


@pytest.mark.parametrize("url", [LIST_URL, COUNTS_URL])
@pytest.mark.parametrize(
    "user,status",
    [
        (None, HTTP_401_UNAUTHORIZED),
        ("member", HTTP_403_FORBIDDEN),
        ("staff", HTTP_200_OK),
    ],
)
def test_list_permissions(api_client, data_fixture, user, status, url):
    token = None
    if user is not None:
        token = data_fixture.create_user_and_token(is_staff=user == "staff")[1]

    params = {"state": "in_review"} if url == LIST_URL else {}
    assert list_admin_templates(api_client, token, url, **params).status_code == status


@pytest.mark.parametrize("state", [None, "private"])
def test_list_filter_by_invalid_state(api_client, data_fixture, state):
    token = get_staff_token(data_fixture)
    params = {} if state is None else {"state": state}

    response = list_admin_templates(api_client, token, **params)

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"


@pytest.mark.parametrize(
    "sorts,expected",
    [
        (None, "cba"),
        ("+name", "abc"),
    ],
)
def test_list_sorts(api_client, data_fixture, sorts, expected):
    token = get_staff_token(data_fixture)
    names = {}
    for day, (name, first_name) in enumerate(
        [("a", "Zoe"), ("b", "Ann"), ("c", "Bob")], start=1
    ):
        user = data_fixture.create_user(first_name=first_name)
        template = create_template(data_fixture, "public", name=name, user=user)
        Template.objects.filter(id=template.id).update(
            created_on=datetime(2026, 10, day, tzinfo=timezone.utc)
        )
        names[template.id] = name

    params = {} if sorts is None else {"sorts": sorts}
    ids = admin_rows(api_client, token, "public", "id", **params)

    assert "".join(names[template_id] for template_id in ids) == expected


def test_list_sorts_authors_without_first_name_by_email(api_client, data_fixture):
    # They're named by email on the page then, and sorted as named.
    token = get_staff_token(data_fixture)
    names = {}
    for name, first_name, email in [
        ("a", "zoe", "zoe@example.com"),
        ("b", "", "bob@example.com"),
        ("c", "ann", "ann@example.com"),
    ]:
        user = data_fixture.create_user(first_name=first_name, email=email)
        template = create_template(data_fixture, "public", name=name, user=user)
        names[template.id] = name

    ids = admin_rows(api_client, token, "public", "id", sorts="+author")

    assert "".join(names[template_id] for template_id in ids) == "cba"


def test_list_sorts_templates_updated_together_by_id(api_client, data_fixture):
    token = get_staff_token(data_fixture)
    ids = [create_template(data_fixture, "public").id for _ in range(3)]
    Template.objects.filter(id__in=ids).update(
        created_on=datetime(2026, 10, 1, tzinfo=timezone.utc)
    )

    assert admin_rows(api_client, token, "public", "id") == ids[::-1]


@pytest.mark.parametrize("state", LISTED_STATES)
def test_list_query_count(api_client, data_fixture, state):
    token = get_staff_token(data_fixture)

    def create_templates(count):
        for _ in range(count):
            template = create_template(data_fixture, state)
            data_fixture.create_user_template_revision(template)

    def list_count():
        response = list_admin_templates(api_client, token, state=state)
        return response.json()["count"]

    create_templates(1)
    with CaptureQueriesContext(connection) as one_template:
        assert list_count() == 1

    create_templates(3)
    with CaptureQueriesContext(connection) as four_templates:
        assert list_count() == 4

    assert len(four_templates.captured_queries) == len(one_template.captured_queries)


def admin_page(api_client, token):
    """
    The rows of every tab of the admin page, checked against the counts of the
    tabs.

    :param api_client: The API client.
    :param token: The token of a staff user.
    :return: The rows by tab.
    """

    tabs = {state: admin_rows(api_client, token, state) for state in LISTED_STATES}
    counts = list_admin_templates(api_client, token, COUNTS_URL).json()
    assert counts == {state: len(rows) for state, rows in tabs.items()}
    return tabs


def review_outcome(root, revision_id, before, admin):
    """
    What a review of a user template did: "refused", its revision "listed",
    "rejected" while the listed one stays, or "unlisted". Also checks what every
    review keeps.

    :param root: The template.
    :param revision_id: The id of the reviewed revision.
    :param before: The rows of the templates before the review.
    :param admin: The admin who reviewed it.
    :return: The outcome.
    """

    after = {row["id"]: row for row in Template.objects.values()}
    changed = {row["id"] for row in before if after[row["id"]] != row}
    if not changed:
        return "refused"
    # Only the reviewed revision and the listing of its template change.
    assert changed <= {root.id, revision_id}
    reviewed = after[revision_id]
    assert reviewed["reviewed_by_id"] == admin.id
    listed_before = next(r for r in before if r["id"] == root.id)["public_revision_id"]
    listed = after[root.id]["public_revision_id"]
    if reviewed["review_state"] == Template.ReviewState.APPROVED:
        assert listed == revision_id
        return "listed"
    assert reviewed["review_state"] == Template.ReviewState.REJECTED
    assert reviewed["reject_reason"] == "Spam"
    if listed is None and listed_before is not None:
        return "unlisted"
    assert listed == listed_before
    return "rejected"


@pytest.mark.parametrize("action", ["approve", "reject"])
@pytest.mark.parametrize(
    "revision_states,tab,row,approve_does,reject_does",
    user_template_plan_rows(
        "4",
        [
            # The tab and the row of the template on the admin page, by the index of
            # its revision, and what reviewing that row does.
            (["private"], None, None, None, None),
            (["shared"], None, None, None, None),
            (["in_review"], "in_review", 0, "listed", "rejected"),
            (["resubmitted"], "in_review", 0, "listed", "rejected"),
            (["in_review", "pruned"], "in_review", 0, "refused", "rejected"),
            (["rejected"], "rejected", 0, "listed", "refused"),
            (["withdrawn_rejected"], None, None, None, None),
            # Edited since it was rejected, so it's not approved as reviewed.
            (["rejected", "private"], "rejected", 0, "refused", "refused"),
            (["rejected", "in_review"], "in_review", 1, "listed", "rejected"),
            (["public"], "public", 0, "refused", "unlisted"),
            (["public", "private"], "public", 0, "refused", "unlisted"),
            # Only the edit is rejected, the approved revision stays listed.
            (["public", "in_review"], "in_review", 1, "listed", "rejected"),
            (["public", "resubmitted"], "in_review", 1, "listed", "rejected"),
            (["public", "rejected"], "rejected", 1, "listed", "unlisted"),
            (["public", "rejected", "private"], "rejected", 1, "refused", "unlisted"),
            (["rejected", "public"], "public", 1, "refused", "unlisted"),
            (["blocked"], None, None, None, None),
            (["public_blocked"], None, None, None, None),
            (["blocked", "in_review"], None, None, None, None),
            (["marked"], None, None, None, None),
            (["marked", "in_review"], None, None, None, None),
            (["public", "marked"], None, None, None, None),
        ],
    ),
)
def test_admin_is_shown_what_a_review_does(
    api_client,
    data_fixture,
    action,
    revision_states,
    tab,
    row,
    approve_does,
    reject_does,
):
    admin, token = data_fixture.create_user_and_token(is_staff=True)
    data_fixture.create_template()
    root = create_template(data_fixture)
    data_fixture.set_user_template_revision_states(root, revision_states)
    revisions = list(
        Template.objects.filter_by_root(id=root.id)
        .order_by("version")
        .values_list("id", flat=True)
    )

    tabs = admin_page(api_client, token)

    expected = [] if tab is None else [(tab, root.id, revisions[row])]
    rows = [(state, r) for state, rows in tabs.items() for r in rows]
    assert [(state, r["id"], r["revision_id"]) for state, r in rows] == expected
    # The admin opens what the page shows: its row and the listed revision.
    root = Template.objects.get(id=root.id)
    hidden = root.blocked_at or root.marked_for_deletion_at
    listed = None if hidden else root.public_revision_id
    opens = {
        id for id in revisions if Template.objects.get(id=id).is_openable_by(admin)
    }
    assert opens == {id for id in [listed, *(r["revision_id"] for _, r in rows)] if id}
    if tab is None:
        return
    shown = rows[0][1]
    assert (shown["state"], shown["reason"]) == (tab, REASONS.get(tab))
    assert shown["listed"] is (listed is not None)
    before = list(Template.objects.values())

    response = review_template(
        api_client,
        token,
        action,
        root.id,
        revision_id=shown["revision_id"],
        state=shown["state"],
        listed=shown["listed"],
        reason="Spam",
    )

    outcome = review_outcome(root, shown["revision_id"], before, admin)
    assert outcome == {"approve": approve_does, "reject": reject_does}[action]
    if action == "approve":
        assert shown["can_approve"] is (outcome == "listed")
        # The admin is told when it's not approved because it was edited.
        edited = response.json().get("error") == "ERROR_TEMPLATE_UPDATED"
        assert shown["edited_since_submitted"] is edited
    else:
        assert shown["can_reject"] is (outcome != "refused")
        assert shown["reject_unlists"] is (outcome == "unlisted")
    if outcome != "refused":
        # Responds with the row of the template in its tab now.
        assert response.status_code == HTTP_200_OK
        reviewed = response.json()
        assert admin_page(api_client, token)[reviewed["state"]] == [reviewed]


@pytest.mark.parametrize(
    "user,status", [(None, HTTP_401_UNAUTHORIZED), ("member", HTTP_403_FORBIDDEN)]
)
@pytest.mark.parametrize("action", ["approve", "reject"])
def test_review_permissions(api_client, data_fixture, user, status, action):
    # Staff are allowed, as every other review test shows.
    token = None
    if user is not None:
        token = data_fixture.create_user_and_token()[1]
    template = create_template(data_fixture, "in_review")

    response = review_template(
        api_client,
        token,
        action,
        template.id,
        revision_id=template.id,
        state="in_review",
        listed=False,
        reason="Spam",
    )

    assert response.status_code == status
    assert Template.objects.get(id=template.id).review_state == "pending"


def test_reject_reason_required(api_client, data_fixture):
    template = create_template(data_fixture, "public")
    body = {"revision_id": template.id, "state": "public", "listed": True}

    response = review_template(
        api_client,
        get_staff_token(data_fixture),
        "reject",
        template.id,
        reason="  ",
        **body,
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert list(response.json()["detail"]) == ["reason"]
    assert Template.objects.get(id=template.id).public_revision_id == template.id


@pytest.mark.parametrize(
    "action,revision_states,revision,seen,code",
    [
        # Both views map the same errors, each code is checked once.
        ("reject", ["public"], "missing", ("public", True), "DOES_NOT_EXIST"),
        ("reject", ["public_blocked"], "latest", ("public", True), "BLOCKED"),
        (
            "approve",
            ["rejected", "private"],
            "previous",
            ("rejected", False),
            "UPDATED",
        ),
        ("reject", ["public"], "latest", ("in_review", False), "ALREADY_APPROVED"),
        ("approve", ["rejected"], "latest", ("rejected", True), "ALREADY_REJECTED"),
        ("reject", ["rejected"], "latest", ("rejected", False), "NOT_REVIEWABLE"),
        (
            "approve",
            ["in_review", "pruned"],
            "latest",
            ("in_review", False),
            "HAS_NO_CONTENT",
        ),
    ],
)
def test_review_errors(
    api_client, data_fixture, action, revision_states, revision, seen, code
):
    # When they're raised is tested with the handler, only their codes are here.
    root = create_template(data_fixture)
    latest = data_fixture.set_user_template_revision_states(root, revision_states)
    template_id = 0 if revision == "missing" else root.id
    revision_id = root.id if revision == "previous" else latest.id

    response = review_template(
        api_client,
        get_staff_token(data_fixture),
        action,
        template_id,
        revision_id=revision_id,
        state=seen[0],
        listed=seen[1],
        reason="Spam",
    )

    status = HTTP_404_NOT_FOUND if code == "DOES_NOT_EXIST" else HTTP_400_BAD_REQUEST
    assert response.status_code == status
    assert response.json()["error"] == f"ERROR_TEMPLATE_{code}"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("action", ["approve", "reject"])
def test_review_builds_the_row_in_its_transaction(api_client, data_fixture, action):
    # So that a deletion of the template can't commit between the review and
    # the row of the response.
    template = create_template(data_fixture, "in_review")
    in_transaction = []

    def serialize(revision):
        in_transaction.append(connection.in_atomic_block)
        return serialize_admin_row(revision)

    with patch(
        "baserow.api.admin.templates.views.serialize_admin_row", side_effect=serialize
    ):
        response = review_template(
            api_client,
            get_staff_token(data_fixture),
            action,
            template.id,
            revision_id=template.id,
            state="in_review",
            listed=False,
            reason="Spam",
        )

    assert response.status_code == HTTP_200_OK
    row = response.json()
    assert (row["id"], row["state"]) == (
        template.id,
        "public" if action == "approve" else "rejected",
    )
    assert in_transaction == [True]
