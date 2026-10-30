from contextlib import nullcontext
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

from baserow.core.models import Template
from baserow.core.user.exceptions import DeactivatedUserException
from baserow.core.user_templates.exceptions import (
    TemplateAlreadyApproved,
    TemplateAlreadyRejected,
    TemplateBlocked,
    TemplateHasNoContent,
    TemplateNotReviewable,
    TemplateUpdated,
)
from baserow.core.user_templates.handler import UserTemplateHandler

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
    latest = data_fixture.create_user_template_revision(
        edited, name="Latest", description="Text"
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
        "name": "Latest",
        "description": "Text",
        "icon": "document",
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
        ("author", HTTP_403_FORBIDDEN),
        # Refused by the authentication of every endpoint.
        ("deactivated_staff", DeactivatedUserException),
        ("staff", HTTP_200_OK),
    ],
)
def test_list_permissions(api_client, data_fixture, user, status, url):
    token = None
    if user is not None:
        account, token = data_fixture.create_user_and_token(
            is_staff=user.endswith("staff"), is_active=user != "deactivated_staff"
        )
        if user == "author":
            create_template(data_fixture, user=account)

    if status is DeactivatedUserException:
        with pytest.raises(DeactivatedUserException):
            list_admin_templates(api_client, token, url)
    else:
        assert list_admin_templates(api_client, token, url).status_code == status


@pytest.mark.parametrize("state", [None, *LISTED_STATES])
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


@pytest.mark.parametrize("state", ["unknown", "", "private", "blocked"])
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
        ("+updated_on", "abc"),
        ("+author", "bca"),
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


@pytest.mark.parametrize("reason", [None, "  ", "x" * 1001])
def test_reject_reason_required(api_client, data_fixture, reason):
    template = create_template(data_fixture, "public")
    body = {"revision_id": template.id, "state": "public", "listed": True}
    if reason is not None:
        body["reason"] = reason

    response = review_template(
        api_client, get_staff_token(data_fixture), "reject", template.id, **body
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert list(response.json()["detail"]) == ["reason"]
    assert Template.objects.get(id=template.id).public_revision_id == template.id


@pytest.mark.parametrize(
    "error,status,code",
    [
        ("missing", HTTP_404_NOT_FOUND, "ERROR_TEMPLATE_DOES_NOT_EXIST"),
        (TemplateBlocked, HTTP_400_BAD_REQUEST, "ERROR_TEMPLATE_BLOCKED"),
        (TemplateUpdated, HTTP_400_BAD_REQUEST, "ERROR_TEMPLATE_UPDATED"),
        (
            TemplateAlreadyApproved,
            HTTP_400_BAD_REQUEST,
            "ERROR_TEMPLATE_ALREADY_APPROVED",
        ),
        (
            TemplateAlreadyRejected,
            HTTP_400_BAD_REQUEST,
            "ERROR_TEMPLATE_ALREADY_REJECTED",
        ),
        (TemplateNotReviewable, HTTP_400_BAD_REQUEST, "ERROR_TEMPLATE_NOT_REVIEWABLE"),
        (TemplateHasNoContent, HTTP_400_BAD_REQUEST, "ERROR_TEMPLATE_HAS_NO_CONTENT"),
    ],
)
def test_review_errors(api_client, data_fixture, error, status, code):
    template = create_template(data_fixture, "in_review")
    template_id = 0 if error == "missing" else template.id
    # When they're raised is tested with the handler, only their codes are here.
    raises = (
        nullcontext()
        if isinstance(error, str)
        else patch.object(
            UserTemplateHandler, "_get_revision_for_review", side_effect=error("")
        )
    )

    with raises:
        response = review_template(
            api_client,
            get_staff_token(data_fixture),
            "approve",
            template_id,
            revision_id=template.id,
            state="in_review",
            listed=False,
        )

    assert response.status_code == status
    assert response.json()["error"] == code
