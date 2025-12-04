from unittest.mock import patch

from django.test.utils import override_settings

import pytest
from freezegun import freeze_time
from rest_framework.reverse import reverse
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_404_NOT_FOUND,
)

from baserow.core.handler import CoreHandler
from baserow.core.models import TrashEntry
from baserow.core.trash.handler import TrashHandler
from baserow.test_utils.helpers import AnyInt
from baserow_premium.row_comments.handler import RowCommentsNotificationModes
from baserow_premium.row_comments.models import RowComment


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comments_api_view(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second_row"], user=user
    )

    response = api_client.get(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }

    message = premium_data_fixture.create_comment_message_from_plain_text(
        "My test comment"
    )

    with freeze_time("2020-01-01 12:00"):
        token = premium_data_fixture.generate_token(user)
        response = api_client.post(
            reverse(
                "api:premium:row_comments:list",
                kwargs={"table_id": table.id, "row_id": rows[0].id},
            ),
            {"message": message},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK
    expected_comment_json = {
        "message": message,
        "created_on": "2020-01-01T12:00:00Z",
        "first_name": "Test User",
        "id": AnyInt(),
        "row_id": rows[0].id,
        "table_id": table.id,
        "updated_on": "2020-01-01T12:00:00Z",
        "user_id": user.id,
        "edited": False,
        "trashed": False,
    }
    assert response.json() == expected_comment_json

    token = premium_data_fixture.generate_token(user)
    response = api_client.get(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [expected_comment_json],
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comments_api_view_without_premium_license(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(first_name="Test User")
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second_row"], user=user
    )

    response = api_client.get(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comments_api_view_without_premium_license_for_workspace(
    premium_data_fixture, api_client, alternative_per_workspace_license_service
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second_row"], user=user
    )

    alternative_per_workspace_license_service.restrict_user_premium_to(
        user, table.database.workspace.id
    )

    response = api_client.get(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    alternative_per_workspace_license_service.restrict_user_premium_to(user, 0)
    response = api_client.get(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comments_cant_view_comments_for_invalid_table(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )

    response = api_client.get(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": 9999, "row_id": 0},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comments_cant_view_comments_for_invalid_row_in_table(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )

    response = api_client.get(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": 9999},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comments_users_cant_view_comments_for_table_they_are_not_in_workspace_for(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    other_user, other_token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )

    response = api_client.get(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    response = api_client.get(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comments_cant_create_comments_in_invalid_table(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )

    message = premium_data_fixture.create_comment_message_from_plain_text("Test")
    response = api_client.post(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": 9999, "row_id": 0},
        ),
        {"message": message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comments_cant_create_comments_in_invalid_row_in_table(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("Test")

    response = api_client.post(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": 9999},
        ),
        {"message": message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comments_users_cant_create_comments_for_table_they_are_not_in_workspace_for(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    other_user, other_token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("Test")

    response = api_client.post(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        {"message": message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    message = premium_data_fixture.create_comment_message_from_plain_text("Test")

    response = api_client.post(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        {"message": message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"
    assert response.status_code == HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cant_make_a_blank_row_comment(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("")

    response = api_client.post(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        {"message": message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"] == {
        "message": [
            {
                "code": "invalid",
                "error": "The message must be a valid ProseMirror JSON document.",
            }
        ]
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cant_make_a_null_row_comment(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )

    response = api_client.post(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"] == {
        "message": [{"error": "This field is required.", "code": "required"}]
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cant_make_a_row_without_premium_license(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token(first_name="Test User")
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("Test")

    response = api_client.post(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        {"message": message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_trashing_the_row_returns_404_for_comments(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("Test")

    with freeze_time("2020-01-01 12:00"):
        token = premium_data_fixture.generate_token(user)
        response = api_client.post(
            reverse(
                "api:premium:row_comments:list",
                kwargs={"table_id": table.id, "row_id": rows[0].id},
            ),
            {"message": message},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK

    token = premium_data_fixture.generate_token(user)
    response = api_client.get(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["results"][0]["row_id"] == rows[0].id

    TrashHandler.trash(user, table.database.workspace, table.database, rows[0])

    response = api_client.get(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND

    response = api_client.post(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        {"message": message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND

    TrashHandler.restore_item(user, "row", rows[0].id, table.id)

    response = api_client.get(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["results"][0]["row_id"] == rows[0].id


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_perm_deleting_a_trashed_row_with_comments_cleans_up_the_rows(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second row"], user=user
    )

    message = premium_data_fixture.create_comment_message_from_plain_text(
        "My test comment"
    )
    with freeze_time("2020-01-01 12:00"):
        token = premium_data_fixture.generate_token(user)
        response = api_client.post(
            reverse(
                "api:premium:row_comments:list",
                kwargs={"table_id": table.id, "row_id": rows[0].id},
            ),
            {"message": message},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK

    other_row_comment = premium_data_fixture.create_comment_message_from_plain_text(
        "My test comment on other row which should not be deleted"
    )
    with freeze_time("2020-01-01 12:00"):
        response = api_client.post(
            reverse(
                "api:premium:row_comments:list",
                kwargs={"table_id": table.id, "row_id": rows[1].id},
            ),
            {"message": other_row_comment},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK

    token = premium_data_fixture.generate_token(user)
    response = api_client.get(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["results"][0]["row_id"] == rows[0].id

    assert RowComment.objects.count() == 2
    model = table.get_model()
    assert model.objects.count() == 2

    TrashHandler.trash(user, table.database.workspace, table.database, rows[0])
    TrashEntry.objects.update(should_be_permanently_deleted=True)

    TrashHandler.permanently_delete_marked_trash()

    assert RowComment.objects.count() == 1
    assert model.objects.count() == 1
    assert RowComment.objects.first().row_id == rows[1].id


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_perm_deleting_a_trashed_table_with_comments_cleans_up_the_rows(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second row"], user=user
    )
    other_table, other_fields, other_rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text(
        "My test comment"
    )

    with freeze_time("2020-01-01 12:00"):
        token = premium_data_fixture.generate_token(user)
        response = api_client.post(
            reverse(
                "api:premium:row_comments:list",
                kwargs={"table_id": table.id, "row_id": rows[0].id},
            ),
            {"message": message},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK

    other_message = premium_data_fixture.create_comment_message_from_plain_text(
        "My test comment on other table which should not be deleted"
    )
    with freeze_time("2020-01-01 12:00"):
        response = api_client.post(
            reverse(
                "api:premium:row_comments:list",
                kwargs={"table_id": other_table.id, "row_id": rows[0].id},
            ),
            {"message": other_message},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK

    token = premium_data_fixture.generate_token(user)
    response = api_client.get(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["results"][0]["row_id"] == rows[0].id

    assert RowComment.objects.count() == 2
    model = table.get_model()
    assert model.objects.count() == 2

    TrashHandler.trash(user, table.database.workspace, table.database, table)
    TrashEntry.objects.update(should_be_permanently_deleted=True)

    TrashHandler.permanently_delete_marked_trash()

    assert RowComment.objects.count() == 1
    assert RowComment.objects.first().row_id == other_rows[0].id


@pytest.mark.django_db
@override_settings(DEBUG=True)
@patch("baserow.core.handler.CoreHandler.check_permissions")
def test_getting_row_comments_executes_fixed_number_of_queries(
    mock_check_permissions, premium_data_fixture, api_client, django_assert_num_queries
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    other_user, other_token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )

    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("Test")

    premium_data_fixture.create_user_workspace(
        user=other_user, workspace=table.database.workspace
    )

    response = api_client.post(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        {"message": message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    expected_num_of_fixed_queries = 6
    with django_assert_num_queries(expected_num_of_fixed_queries):
        response = api_client.get(
            reverse(
                "api:premium:row_comments:list",
                kwargs={"table_id": table.id, "row_id": rows[0].id},
            ),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["results"][0]["row_id"] == rows[0].id

    other_message = premium_data_fixture.create_comment_message_from_plain_text(
        "My test comment from another user"
    )
    response = api_client.post(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": rows[0].id},
        ),
        {"message": other_message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )
    assert response.status_code == HTTP_200_OK

    with django_assert_num_queries(expected_num_of_fixed_queries):
        response = api_client.get(
            reverse(
                "api:premium:row_comments:list",
                kwargs={"table_id": table.id, "row_id": rows[0].id},
            ),
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cant_update_a_row_comment_without_premium_license(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=False
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("Test")

    comment = RowComment.objects.create(
        table=table, row_id=rows[0].id, user=user, message=message
    )

    response = api_client.patch(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": table.id, "comment_id": comment.id},
        ),
        {"message": message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comments_cant_update_comments_with_invalid_text(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second row"], user=user
    )

    response = api_client.patch(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": 0, "comment_id": 0},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comments_cant_update_comments_for_invalid_table(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("Test")
    premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second row"], user=user
    )

    response = api_client.patch(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": 0, "comment_id": 0},
        ),
        {"message": message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comments_cant_update_comments_for_invalid_comment(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("Test")

    response = api_client.patch(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": table.id, "comment_id": 0},
        ),
        {"message": message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_COMMENT_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_only_the_author_can_update_a_row_comment(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="User 1", has_active_premium_license=True
    )
    other_user, other_token = premium_data_fixture.create_user_and_token(
        first_name="User 2", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("Test")

    comment = RowComment.objects.create(
        table=table, row_id=rows[0].id, user=user, message=message
    )

    updated_message = premium_data_fixture.create_comment_message_from_plain_text(
        "Updated comment"
    )
    response = api_client.patch(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": table.id, "comment_id": comment.id},
        ),
        {"message": updated_message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    CoreHandler().add_user_to_workspace(table.database.workspace, other_user)

    response = api_client.patch(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": table.id, "comment_id": comment.id},
        ),
        {"message": updated_message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_COMMENT_AUTHOR"

    response = api_client.patch(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": table.id, "comment_id": comment.id},
        ),
        {"message": updated_message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cant_delete_a_row_comment_without_premium_license(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=False
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("Test")

    comment = RowComment.objects.create(
        table=table, row_id=rows[0].id, user=user, message=message
    )

    response = api_client.delete(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": table.id, "comment_id": comment.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comments_cant_delete_comments_for_invalid_table(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    other_user, other_token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second row"], user=user
    )

    response = api_client.delete(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": 0, "comment_id": 0},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_row_comments_cant_delete_comments_for_invalid_comment(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second row"], user=user
    )

    response = api_client.delete(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": table.id, "comment_id": 0},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_COMMENT_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_only_the_author_can_delete_a_row_comment(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="User 1", has_active_premium_license=True
    )
    other_user, other_token = premium_data_fixture.create_user_and_token(
        first_name="User 2", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second row"], user=user
    )

    message = premium_data_fixture.create_comment_message_from_plain_text("Test")
    comment = RowComment.objects.create(
        table=table, row_id=rows[0].id, user=user, message=message
    )

    response = api_client.delete(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": table.id, "comment_id": comment.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    CoreHandler().add_user_to_workspace(table.database.workspace, other_user)

    response = api_client.delete(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": table.id, "comment_id": comment.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_COMMENT_AUTHOR"

    response = api_client.delete(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": table.id, "comment_id": comment.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["id"] == comment.id
    assert response_json["message"] is None
    assert response_json["trashed"] is True


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_only_the_author_can_see_deleted_row_comment_in_trash(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="User 1", has_active_premium_license=True
    )
    other_user, other_token = premium_data_fixture.create_user_and_token(
        first_name="User 2", has_active_premium_license=True
    )
    table, _, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second row"], user=user
    )

    message = premium_data_fixture.create_comment_message_from_plain_text("Test")
    comment = RowComment.objects.create(
        table=table, row_id=rows[0].id, user=user, message=message
    )
    workspace = table.database.workspace

    response = api_client.delete(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": table.id, "comment_id": comment.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["trashed"] is True

    response = api_client.get(
        reverse("api:trash:contents", kwargs={"workspace_id": workspace.id}),
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert len(response.json()["results"]) == 1
    assert response.json()["results"][0]["trash_item_type"] == "row_comment"
    assert response.json()["results"][0]["trash_item_id"] == comment.id

    CoreHandler().add_user_to_workspace(workspace, other_user)

    response = api_client.get(
        reverse("api:trash:contents", kwargs={"workspace_id": workspace.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )

    assert response.status_code == HTTP_200_OK
    assert len(response.json()["results"]) == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_only_the_author_can_restore_a_trashed_row_comment(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="User 1", has_active_premium_license=True
    )
    other_user, other_token = premium_data_fixture.create_user_and_token(
        first_name="User 2", has_active_premium_license=True
    )
    table, _, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second row"], user=user
    )
    message = premium_data_fixture.create_comment_message_from_plain_text("Test")
    comment = RowComment.objects.create(
        table=table, row_id=rows[0].id, user=user, message=message
    )
    workspace = table.database.workspace

    response = api_client.delete(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": table.id, "comment_id": comment.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK

    CoreHandler().add_user_to_workspace(workspace, other_user)

    response = api_client.patch(
        reverse("api:trash:restore"),
        {
            "trash_item_type": "row_comment",
            "trash_item_id": comment.id,
        },
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CANNOT_RESTORE_ITEM_NOT_OWNED_BY_USER"

    response = api_client.patch(
        reverse("api:trash:restore"),
        {
            "trash_item_type": "row_comment",
            "trash_item_id": comment.id,
        },
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_user_can_be_mentioned_in_message(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second_row"], user=user
    )
    user_2 = premium_data_fixture.create_user(
        first_name="Test User 2", workspace=table.database.workspace
    )

    message = premium_data_fixture.create_comment_message_with_mentions([user_2])

    with freeze_time("2020-01-01 12:00"):
        token = premium_data_fixture.generate_token(user)
        response = api_client.post(
            reverse(
                "api:premium:row_comments:list",
                kwargs={"table_id": table.id, "row_id": rows[0].id},
            ),
            {"message": message},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK

    expected_comment_json = {
        "message": message,
        "created_on": "2020-01-01T12:00:00Z",
        "first_name": "Test User",
        "id": AnyInt(),
        "row_id": rows[0].id,
        "table_id": table.id,
        "updated_on": "2020-01-01T12:00:00Z",
        "user_id": user.id,
        "edited": False,
        "trashed": False,
    }
    assert response.json() == expected_comment_json
    assert [u.pk for u in RowComment.objects.first().mentions.all()] == [user_2.pk]


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_user_cant_be_mentioned_in_comments_if_outside_workspace(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, _, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second_row"], user=user
    )
    user_2 = premium_data_fixture.create_user(first_name="Test User 2")

    message = premium_data_fixture.create_comment_message_with_mentions([user_2])

    with freeze_time("2020-01-01 12:00"):
        token = premium_data_fixture.generate_token(user)
        response = api_client.post(
            reverse(
                "api:premium:row_comments:list",
                kwargs={"table_id": table.id, "row_id": rows[0].id},
            ),
            {"message": message},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK
    assert RowComment.objects.first().mentions.count() == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_multiple_users_can_be_mentioned_in_a_comment(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, fields, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second_row"], user=user
    )
    user_2 = premium_data_fixture.create_user(
        first_name="Test User 2", workspace=table.database.workspace
    )
    user_3 = premium_data_fixture.create_user(
        first_name="Test User 3", workspace=table.database.workspace
    )

    message = premium_data_fixture.create_comment_message_with_mentions(
        [user_2, user_3]
    )

    with freeze_time("2020-01-01 12:00"):
        token = premium_data_fixture.generate_token(user)
        response = api_client.post(
            reverse(
                "api:premium:row_comments:list",
                kwargs={"table_id": table.id, "row_id": rows[0].id},
            ),
            {"message": message},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK

    expected_comment_json = {
        "message": message,
        "created_on": "2020-01-01T12:00:00Z",
        "first_name": "Test User",
        "id": AnyInt(),
        "row_id": rows[0].id,
        "table_id": table.id,
        "updated_on": "2020-01-01T12:00:00Z",
        "user_id": user.id,
        "edited": False,
        "trashed": False,
    }
    assert response.json() == expected_comment_json
    assert message == {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "mention",
                        "attrs": {"id": user_2.pk, "label": user_2.first_name},
                    },
                    {
                        "type": "mention",
                        "attrs": {"id": user_3.pk, "label": user_3.first_name},
                    },
                ],
            }
        ],
    }
    mentions = RowComment.objects.first().mentions.all()
    assert {u.pk for u in mentions} == {user_2.pk, user_3.pk}


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_user_without_premium_license_cannot_update_row_comments_notification_mode(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token()
    table, _, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second_row"], user=user
    )

    response = api_client.put(
        reverse(
            "api:premium:row_comments:notification_mode",
            kwargs={"row_id": rows[0].id, "table_id": table.id},
        ),
        {"mode": RowCommentsNotificationModes.MODE_ALL_COMMENTS.value},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED
    assert response.json()["error"] == "ERROR_FEATURE_NOT_AVAILABLE"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_user_cannot_update_row_comments_notification_mode_if_data_is_invalid(
    premium_data_fixture, api_client
):
    user, token = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True
    )
    external_table = premium_data_fixture.create_database_table()
    table, _, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second_row"], user=user
    )

    response = api_client.put(
        reverse(
            "api:premium:row_comments:notification_mode",
            kwargs={"row_id": 0, "table_id": external_table.id},
        ),
        {"mode": RowCommentsNotificationModes.MODE_ALL_COMMENTS.value},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    response = api_client.put(
        reverse(
            "api:premium:row_comments:notification_mode",
            kwargs={"row_id": rows[0].id, "table_id": 99999},
        ),
        {"mode": RowCommentsNotificationModes.MODE_ALL_COMMENTS.value},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TABLE_DOES_NOT_EXIST"

    response = api_client.put(
        reverse(
            "api:premium:row_comments:notification_mode",
            kwargs={"row_id": 0, "table_id": table.id},
        ),
        {"mode": RowCommentsNotificationModes.MODE_ALL_COMMENTS.value},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_ROW_DOES_NOT_EXIST"

    response = api_client.put(
        reverse(
            "api:premium:row_comments:notification_mode",
            kwargs={"row_id": rows[0].id, "table_id": table.id},
        ),
        {"mode": "invalid_mode"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"] == {
        "mode": [
            {"code": "invalid_choice", "error": '"invalid_mode" is not a valid choice.'}
        ]
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_user_update_row_comments_notification_mode(premium_data_fixture, api_client):
    user, token = premium_data_fixture.create_user_and_token(
        first_name="Test User", has_active_premium_license=True
    )
    table, _, rows = premium_data_fixture.build_table(
        columns=[("text", "text")], rows=["first row", "second_row"], user=user
    )

    response = api_client.put(
        reverse(
            "api:premium:row_comments:notification_mode",
            kwargs={"row_id": rows[0].id, "table_id": table.id},
        ),
        {"mode": RowCommentsNotificationModes.MODE_ALL_COMMENTS.value},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    response = api_client.put(
        reverse(
            "api:premium:row_comments:notification_mode",
            kwargs={"row_id": rows[1].id, "table_id": table.id},
        ),
        {"mode": RowCommentsNotificationModes.MODE_ONLY_MENTIONS.value},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_204_NO_CONTENT
