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

pytestmark = pytest.mark.django_db

LIST_URL = reverse("api:admin:templates:list")
COUNTS_URL = reverse("api:admin:templates:counts")
STATES = ["private", "in_review", "rejected", "blocked", "public"]
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

    response = list_admin_templates(api_client, token)

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
        "updated_on": "2026-10-01T12:00:00Z",
    }
    assert rows[without_author.id]["author"] is None
    # The ids are of the templates, not of their latest revisions.
    response = list_admin_templates(api_client, token, ids=str(edited.id))
    assert [row["revision_id"] for row in response.json()["results"]] == [latest.id]


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

    assert list_admin_templates(api_client, token, url).status_code == status


@pytest.mark.parametrize("state", [None, "rejected"])
def test_list_filter_by_state(api_client, data_fixture, state):
    token = get_staff_token(data_fixture)
    # Not published nor submitted, or gone, are never listed.
    templates = {name: create_template(data_fixture, name) for name in STATES}
    create_template(data_fixture, "marked")
    shown = [state] if state else LISTED_STATES
    expected = {(templates[s].id, s, REASONS.get(s), s == "public") for s in shown}

    params = {} if state is None else {"state": state}
    response = list_admin_templates(api_client, token, **params)

    assert response.status_code == HTTP_200_OK
    rows = response.json()["results"]
    assert {(r["id"], r["state"], r["reason"], r["listed"]) for r in rows} == expected


@pytest.mark.parametrize("state", ["private"])
def test_list_filter_by_invalid_state(api_client, data_fixture, state):
    token = get_staff_token(data_fixture)

    response = list_admin_templates(api_client, token, state=state)

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
    for day, (name, first_name, state) in enumerate(
        [("a", "Zoe", "rejected"), ("b", "Ann", "public"), ("c", "Bob", "in_review")],
        start=1,
    ):
        user = data_fixture.create_user(first_name=first_name)
        template = create_template(data_fixture, state, name=name, user=user)
        Template.objects.filter(id=template.id).update(
            created_on=datetime(2026, 10, day, tzinfo=timezone.utc)
        )
        names[template.id] = name

    params = {} if sorts is None else {"sorts": sorts}
    response = list_admin_templates(api_client, token, **params)

    assert "".join(names[row["id"]] for row in response.json()["results"]) == expected


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

    response = list_admin_templates(api_client, token, sorts="+author")

    assert "".join(names[row["id"]] for row in response.json()["results"]) == "cba"


def test_list_sorts_templates_updated_together_by_id(api_client, data_fixture):
    token = get_staff_token(data_fixture)
    ids = [create_template(data_fixture, "public").id for _ in range(3)]
    Template.objects.filter(id__in=ids).update(
        created_on=datetime(2026, 10, 1, tzinfo=timezone.utc)
    )

    response = list_admin_templates(api_client, token)

    assert [row["id"] for row in response.json()["results"]] == ids[::-1]


def test_list_query_count(api_client, data_fixture):
    token = get_staff_token(data_fixture)

    def create_templates(states):
        for state in states:
            template = create_template(data_fixture, state)
            data_fixture.create_user_template_revision(template)

    create_templates(["rejected"])
    with CaptureQueriesContext(connection) as one_template:
        assert list_admin_templates(api_client, token).json()["count"] == 1

    create_templates(["public", "rejected", "public"])
    with CaptureQueriesContext(connection) as four_templates:
        assert list_admin_templates(api_client, token).json()["count"] == 4

    assert len(four_templates.captured_queries) == len(one_template.captured_queries)


def test_counts(api_client, data_fixture):
    for state in STATES + ["in_review", "marked"]:
        create_template(data_fixture, state)
    data_fixture.create_template()

    response = list_admin_templates(
        api_client, get_staff_token(data_fixture), COUNTS_URL
    )

    assert response.status_code == HTTP_200_OK
    assert response.json() == {"in_review": 2, "public": 1, "rejected": 1}


def test_list_and_counts_template_with_revisions(api_client, data_fixture):
    token = get_staff_token(data_fixture)
    expected = "rejected"
    root = revision = create_template(data_fixture)
    for index, state in enumerate(["public", "rejected", "private"]):
        if index:
            revision = data_fixture.create_user_template_revision(root)
        data_fixture.set_user_template_state(root, state, revision)

    def listed(**params):
        rows = list_admin_templates(api_client, token, **params).json()["results"]
        return [(row["id"], row["revision_id"], row["state"]) for row in rows]

    # Once, with the state of its latest revision.
    assert listed() == listed(state=expected) == [(root.id, revision.id, expected)]
    assert all(listed(state=s) == [] for s in LISTED_STATES if s != expected)
    counts = list_admin_templates(api_client, token, COUNTS_URL).json()
    assert counts == {state: int(state == expected) for state in LISTED_STATES}


@pytest.mark.parametrize(
    "user,status",
    [
        (None, HTTP_401_UNAUTHORIZED),
        ("member", HTTP_403_FORBIDDEN),
        ("staff", HTTP_200_OK),
    ],
)
@pytest.mark.parametrize(
    "action,state,result",
    [("approve", "in_review", "public"), ("reject", "public", "rejected")],
)
def test_review_permissions(
    api_client, data_fixture, user, status, action, state, result
):
    token = None
    if user is not None:
        token = data_fixture.create_user_and_token(is_staff=user == "staff")[1]
    template = create_template(data_fixture, state)

    response = review_template(
        api_client,
        token,
        action,
        template.id,
        revision_id=template.id,
        state=state,
        listed=state == "public",
        reason="Spam",
    )

    assert response.status_code == status
    if status == HTTP_200_OK:
        assert response.json()["id"] == template.id
        assert response.json()["state"] == result


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
        ("approve", ["rejected", "private"], "previous", ("private", False), "UPDATED"),
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
    root = latest = create_template(data_fixture)
    for index, revision_state in enumerate(revision_states):
        if revision_state == "pruned":
            Template.objects.filter(id=latest.id).update(
                pruned_at=datetime.now(tz=timezone.utc)
            )
            continue
        if index:
            latest = data_fixture.create_user_template_revision(root)
        data_fixture.set_user_template_state(root, revision_state, latest)
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
    assert in_transaction == [True]
