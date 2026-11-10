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
LISTED_STATES = ["in_review", "public", "rejected", "blocked"]
REASONS = {"rejected": "Reason", "blocked": "Spam"}


def list_admin_templates(api_client, token, url=LIST_URL, **params):
    headers = {"HTTP_AUTHORIZATION": f"JWT {token}"} if token else {}
    return api_client.get(url, params, **headers)


def admin_rows(api_client, token, state, *fields, **params):
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
    category = data_fixture.create_template_category(name="Planning")
    latest = data_fixture.create_user_template_revision(
        edited, name="Latest", description="Text", category=category
    )
    data_fixture.set_user_template_state(edited, "in_review", latest)
    Template.objects.filter(id=edited.id).update(install_count=7)
    without_author = create_template(data_fixture, None, "in_review", author=None)
    data_fixture.create_template()

    response = list_admin_templates(api_client, token, state="in_review")

    assert response.status_code == HTTP_200_OK
    rows = {row["id"]: row for row in response.json()["results"]}
    assert response.json()["count"] == len(rows) == 2
    assert rows[edited.id] == {
        "id": edited.id,
        "revision_id": latest.id,
        "slug": edited.slug,
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
        "reject_unlists": False,
        "updated_on": "2026-10-01T12:00:00Z",
        "reviewed_on": None,
        "install_count": 7,
        "submitted_on": "2026-10-01T12:00:00Z",
    }
    assert rows[without_author.id]["author"] is None
    assert admin_rows(
        api_client, token, "in_review", "revision_id", ids=str(edited.id)
    ) == [latest.id]


@pytest.mark.parametrize(
    "method,endpoint",
    [
        ("get", "list"),
        ("get", "counts"),
        ("post", "approve"),
        ("post", "reject"),
        ("post", "block"),
        ("post", "unblock"),
    ],
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
        body = {
            "revision_id": template.id,
            "state": "in_review",
            "listed": False,
            "reviewed_on": None,
        }
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


AUTHORS = [("Zoe", "z@x.com", 3), ("Ann", "a@x.com", 1), ("Bob", "b@x.com", 2)]


@pytest.mark.parametrize(
    "authors,sorts,expected",
    [
        (AUTHORS, None, "acb"),
        (AUTHORS, "+name", "abc"),
        (AUTHORS, "+used", "bca"),
        (AUTHORS, "+submitted", "cab"),
        (AUTHORS, "-submitted", "acb"),
        (
            [("zoe", "z@x.com", 1), ("", "b@x.com", 1), ("ann", "a@x.com", 1)],
            "+author",
            "cba",
        ),
        (
            [("zoe", "z@x.com", 1), (None, "b@x.com", 1), ("ann", "a@x.com", 1)],
            "-author",
            "acb",
        ),
        ([(name, email, 1) for name, email, _ in AUTHORS], None, "cba"),
    ],
)
def test_list_sorts(api_client, data_fixture, authors, sorts, expected):
    token = get_staff_token(data_fixture)
    names = {}
    for name, (first_name, email, day), install_count in zip("abc", authors, [5, 1, 3]):
        user = data_fixture.create_user(first_name=first_name or "", email=email)
        template = create_template(data_fixture, user, "public", name=name)
        created_on = datetime(2026, 10, day, tzinfo=timezone.utc)
        Template.objects.filter(id=template.id).update(
            author=user if first_name is not None else None,
            created_on=created_on,
            install_count=install_count,
            submitted_on=None if name == "b" else created_on,
        )
        names[template.id] = name

    params = {} if sorts is None else {"sorts": sorts}
    ids = admin_rows(api_client, token, "public", "id", **params)

    assert "".join(names[template_id] for template_id in ids) == expected


@pytest.mark.parametrize(
    "search,expected",
    [
        ("sprint", ["Sprint board"]),
        ("ANN", ["Sprint board"]),
        ("ann@example", ["Sprint board"]),
        ("corp.io", ["Roadmap"]),
        ("carl", ["Roadmap"]),
        ("nothing", []),
    ],
)
def test_list_search(api_client, data_fixture, search, expected):
    token = get_staff_token(data_fixture)
    for name, first_name, email in [
        ("Sprint board", "Ann", "ann@example.com"),
        ("Budget", "", "bob@example.com"),
        ("Roadmap", "Carl", "ops@corp.io"),
    ]:
        user = data_fixture.create_user(first_name=first_name, email=email)
        template = create_template(data_fixture, user, "public", name=name)
    revision = data_fixture.create_user_template_revision(template, name=name)
    data_fixture.set_user_template_state(template, "in_review", revision)

    rows = [
        name
        for state in ["public", "in_review"]
        for name in admin_rows(api_client, token, state, "name", search=search)
    ]

    assert rows == expected


@pytest.mark.parametrize("state", LISTED_STATES)
def test_list_query_count(api_client, data_fixture, state):
    token = get_staff_token(data_fixture)

    def create_templates(count):
        for _ in range(count):
            template = create_template(data_fixture, None, state)
            data_fixture.create_user_template_revision(template)

    def list_count(**params):
        response = list_admin_templates(api_client, token, state=state, **params)
        return response.json()["count"]

    create_templates(1)
    with CaptureQueriesContext(connection) as one_template:
        assert list_count() == 1

    create_templates(3)
    with CaptureQueriesContext(connection) as four_templates:
        assert list_count() == 4
    with CaptureQueriesContext(connection) as searched:
        assert list_count(search="@", sorts="-used") == 4
    assert len(searched.captured_queries) == len(one_template.captured_queries)

    assert len(four_templates.captured_queries) == len(one_template.captured_queries)


def admin_page(api_client, token):
    tabs = {state: admin_rows(api_client, token, state) for state in LISTED_STATES}
    counts = list_admin_templates(api_client, token, COUNTS_URL).json()
    assert counts == {state: len(rows) for state, rows in tabs.items()}
    return tabs


def review_outcome(root, revision_id, before, admin):
    after = {row["id"]: row for row in Template.objects.values()}
    changed = {row["id"] for row in before if after[row["id"]] != row}
    if not changed:
        return "refused"
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
    return [
        pytest.param(*row.values, action, id=f"{row.id}-{action}" if action else row.id)
        for row in rows
        for action in (["approve", "reject"] if row.values[1] else [None])
    ]


@pytest.mark.parametrize(
    "revision_states,tab,row,approve_does,reject_does,action",
    per_review_action(
        user_template_plan_rows(
            "4",
            [
                (["private"], None, None, None, None),
                (["shared"], None, None, None, None),
                (["in_review"], "in_review", 0, "listed", "rejected"),
                (["resubmitted"], "in_review", 0, "listed", "rejected"),
                (["in_review", "pruned"], "in_review", 0, "refused", "rejected"),
                (["rejected"], "rejected", 0, "listed", "refused"),
                (["withdrawn_rejected"], None, None, None, None),
                (["rejected", "private"], "rejected", 0, "refused", "refused"),
                (["rejected", "in_review"], "in_review", 1, "listed", "rejected"),
                (["public"], "public", 0, "refused", "unlisted"),
                (["public", "private"], "public", 0, "refused", "unlisted"),
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
                (["blocked"], "blocked", 0, "refused", "refused"),
                (["public_blocked"], "blocked", 0, "refused", "refused"),
                (["blocked", "in_review"], "blocked", 1, "refused", "refused"),
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
    root = create_template(data_fixture, None, blocked_reason="Spam")
    data_fixture.set_user_template_revision_states(root, revision_states)
    revisions = revision_ids(root)

    tabs = admin_page(api_client, token)

    expected = [] if tab is None else [(tab, root.id, revisions[row])]
    rows = [(state, r) for state, rows in tabs.items() for r in rows]
    assert [(state, r["id"], r["revision_id"]) for state, r in rows] == expected
    root = Template.objects.get(id=root.id)
    hidden = root.blocked_at or root.marked_for_deletion_at
    listed = None if hidden else root.public_revision_id
    opens = {
        id
        for id in revisions
        if Template.objects.get(id=id).workspace.has_openable_template(admin)
    }
    queued = [r["revision_id"] for state, r in rows if state != "blocked"]
    assert opens == {id for id in [listed, *queued] if id}
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
        reviewed_on=shown["reviewed_on"],
        reason="Spam",
    )

    outcome = review_outcome(root, shown["revision_id"], before, admin)
    assert outcome == {"approve": approve_does, "reject": reject_does}[action]
    if action == "approve":
        assert shown["can_approve"] is (outcome == "listed")
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
    "action,state,result",
    [("block", "in_review", "blocked"), ("unblock", "blocked", "private")],
)
def test_block_and_unblock(api_client, data_fixture, action, state, result):
    token = get_staff_token(data_fixture)
    root = create_template(data_fixture, None, state)

    response = review_template(api_client, token, action, root.id, reason="Spam")

    assert response.status_code == HTTP_200_OK
    row = response.json()
    reason = "Spam" if result == "blocked" else None
    assert (row["id"], row["state"], row["reason"]) == (root.id, result, reason)
    tabs = admin_page(api_client, token)
    assert {state: rows for state, rows in tabs.items() if rows} == (
        {"blocked": [row]} if result == "blocked" else {}
    )


@pytest.mark.parametrize(
    "action,revision_states,revision,seen,reason,error",
    [
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
            "block",
            ["public"],
            "missing",
            ("public", True),
            "Spam",
            "ERROR_TEMPLATE_DOES_NOT_EXIST",
        ),
        *[
            (
                action,
                ["public"],
                "latest",
                ("public", True),
                reason,
                "ERROR_REQUEST_BODY_VALIDATION",
            )
            for action in ["reject", "block"]
            for reason in ["  ", "x" * 1001]
        ],
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
        reviewed_on=Template.objects.get(id=revision_id).reviewed_on,
        reason=reason,
    )

    missing = error == "ERROR_TEMPLATE_DOES_NOT_EXIST"
    status = HTTP_404_NOT_FOUND if missing else HTTP_400_BAD_REQUEST
    assert response.status_code == status
    assert response.json()["error"] == error
    assert list(Template.objects.values().order_by("id")) == before
