from datetime import datetime, timezone

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

from baserow.core.models import Template
from baserow.test_utils.helpers import user_template_plan_rows
from tests.baserow.core.user_templates.utils import (
    create_template,
    revision_ids,
)

pytestmark = pytest.mark.django_db

LIST_URL = reverse("api:admin:templates:list")
COUNTS_URL = reverse("api:admin:templates:counts")
LISTED_STATES = ["in_review", "public", "rejected"]
REASONS = {"rejected": "Reason"}


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
    :return: The rows: the value of the only field, a tuple of `fields`, or the
        whole row without `fields`.
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
        edited = create_template(data_fixture, author, "public", name="First")
    # Dated by its latest revision.
    category = data_fixture.create_template_category(name="Planning")
    latest = data_fixture.create_user_template_revision(
        edited, name="Latest", description="Text", category=category
    )
    # Stays listed while its edit is in review.
    data_fixture.set_user_template_state(edited, "in_review", latest)
    without_author = create_template(data_fixture, None, "in_review", author=None)
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


@pytest.mark.parametrize(
    "method,endpoint",
    [("get", "list"), ("get", "counts"), ("post", "approve"), ("post", "reject")],
)
@pytest.mark.parametrize(
    "user,status", [(None, HTTP_401_UNAUTHORIZED), ("member", HTTP_403_FORBIDDEN)]
)
def test_permissions(api_client, data_fixture, method, endpoint, user, status):
    headers = {}
    if user is not None:
        token = data_fixture.create_user_and_token()[1]
        headers["HTTP_AUTHORIZATION"] = f"JWT {token}"
    template = create_template(data_fixture, None, "in_review")

    if method == "get":
        url = reverse(f"api:admin:templates:{endpoint}")
        response = api_client.get(url, {"state": "in_review"}, **headers)
    else:
        url = reverse(
            f"api:admin:templates:{endpoint}", kwargs={"template_id": template.id}
        )
        body = {"revision_id": template.id, "state": "in_review", "listed": False}
        response = api_client.post(
            url, {**body, "reason": "Spam"}, format="json", **headers
        )

    assert response.status_code == status
    assert Template.objects.get(id=template.id).review_state == "pending"


@pytest.mark.parametrize("state", [None, "private"])
def test_list_filter_by_invalid_state(api_client, data_fixture, state):
    token = get_staff_token(data_fixture)
    params = {} if state is None else {"state": state}

    response = list_admin_templates(api_client, token, **params)

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_QUERY_PARAMETER_VALIDATION"


# The authors of the templates "a", "b" and "c", and the day each was updated on.
AUTHORS = [("Zoe", "z@x.com", 3), ("Ann", "a@x.com", 1), ("Bob", "b@x.com", 2)]


@pytest.mark.parametrize(
    "authors,sorts,expected",
    [
        # Newest first.
        (AUTHORS, None, "acb"),
        (AUTHORS, "+name", "abc"),
        # Named by email without a first name on the page, and sorted as named.
        (
            [("zoe", "z@x.com", 1), ("", "b@x.com", 1), ("ann", "a@x.com", 1)],
            "+author",
            "cba",
        ),
        # Updated together, the newest first.
        ([(name, email, 1) for name, email, _ in AUTHORS], None, "cba"),
    ],
)
def test_list_sorts(api_client, data_fixture, authors, sorts, expected):
    token = get_staff_token(data_fixture)
    names = {}
    for name, (first_name, email, day) in zip("abc", authors):
        user = data_fixture.create_user(first_name=first_name, email=email)
        template = create_template(data_fixture, user, "public", name=name)
        Template.objects.filter(id=template.id).update(
            created_on=datetime(2026, 10, day, tzinfo=timezone.utc)
        )
        names[template.id] = name

    params = {} if sorts is None else {"sorts": sorts}
    ids = admin_rows(api_client, token, "public", "id", **params)

    assert "".join(names[template_id] for template_id in ids) == expected


@pytest.mark.parametrize("state", LISTED_STATES)
def test_list_query_count(api_client, data_fixture, state):
    token = get_staff_token(data_fixture)

    def create_templates(count):
        for _ in range(count):
            template = create_template(data_fixture, None, state)
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


def per_review_action(rows):
    """
    Runs each row once per review action, and once without a review when the
    template isn't on the admin page.
    """

    return [
        pytest.param(*row.values, action, id=f"{row.id}-{action}" if action else row.id)
        for row in rows
        # The tab is the second column.
        for action in (["approve", "reject"] if row.values[1] else [None])
    ]


@pytest.mark.parametrize(
    "revision_states,tab,row,approve_does,reject_does,action",
    per_review_action(
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
                (
                    ["public", "rejected", "private"],
                    "rejected",
                    1,
                    "refused",
                    "unlisted",
                ),
                (["rejected", "public"], "public", 1, "refused", "unlisted"),
                (["blocked"], None, None, None, None),
                (["public_blocked"], None, None, None, None),
                (["blocked", "in_review"], None, None, None, None),
                (["marked"], None, None, None, None),
                (["marked", "in_review"], None, None, None, None),
                (["public", "marked"], None, None, None, None),
            ],
        ),
    ),
)
def test_admin_is_shown_what_a_review_does(
    api_client,
    data_fixture,
    revision_states,
    tab,
    row,
    approve_does,
    reject_does,
    action,
):
    admin, token = data_fixture.create_user_and_token(is_staff=True)
    data_fixture.create_template()
    root = create_template(data_fixture, None)
    data_fixture.set_user_template_revision_states(root, revision_states)
    revisions = revision_ids(root)

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
        assert response.status_code == HTTP_200_OK
        reviewed = response.json()
        assert admin_page(api_client, token)[reviewed["state"]] == [reviewed]


@pytest.mark.parametrize(
    "action,revision_states,revision,seen,reason,error",
    [
        # Both views map the same errors, each code is checked once.
        (
            "reject",
            ["public"],
            "missing",
            ("public", True),
            "Spam",
            "ERROR_TEMPLATE_DOES_NOT_EXIST",
        ),
        (
            "reject",
            ["public_blocked"],
            "latest",
            ("public", True),
            "Spam",
            "ERROR_TEMPLATE_BLOCKED",
        ),
        (
            "approve",
            ["rejected", "private"],
            "previous",
            ("rejected", False),
            "Spam",
            "ERROR_TEMPLATE_UPDATED",
        ),
        (
            "reject",
            ["public"],
            "latest",
            ("in_review", False),
            "Spam",
            "ERROR_TEMPLATE_ALREADY_APPROVED",
        ),
        (
            "approve",
            ["rejected"],
            "latest",
            ("rejected", True),
            "Spam",
            "ERROR_TEMPLATE_ALREADY_REJECTED",
        ),
        (
            "reject",
            ["rejected"],
            "latest",
            ("rejected", False),
            "Spam",
            "ERROR_TEMPLATE_NOT_REVIEWABLE",
        ),
        (
            "approve",
            ["in_review", "pruned"],
            "latest",
            ("in_review", False),
            "Spam",
            "ERROR_TEMPLATE_HAS_NO_CONTENT",
        ),
        (
            "reject",
            ["public"],
            "latest",
            ("public", True),
            "  ",
            "ERROR_REQUEST_BODY_VALIDATION",
        ),
    ],
)
def test_review_errors(
    api_client, data_fixture, action, revision_states, revision, seen, reason, error
):
    root = create_template(data_fixture, None)
    latest = data_fixture.set_user_template_revision_states(root, revision_states)
    template_id = 0 if revision == "missing" else root.id
    revision_id = root.id if revision == "previous" else latest.id
    before = list(Template.objects.values().order_by("id"))

    response = review_template(
        api_client,
        get_staff_token(data_fixture),
        action,
        template_id,
        revision_id=revision_id,
        state=seen[0],
        listed=seen[1],
        reason=reason,
    )

    missing = error == "ERROR_TEMPLATE_DOES_NOT_EXIST"
    status = HTTP_404_NOT_FOUND if missing else HTTP_400_BAD_REQUEST
    assert response.status_code == status
    assert response.json()["error"] == error
    assert list(Template.objects.values().order_by("id")) == before
