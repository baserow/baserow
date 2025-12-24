from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command

import pytest


@pytest.mark.django_db
def test_delete_files_uploaded_by_user_no_files(data_fixture):
    user = data_fixture.create_user()
    out = StringIO()

    call_command("delete_files_uploaded_by_user", user.id, stdout=out)

    output = out.getvalue()
    assert f"Found 0 file(s) uploaded by user ID {user.id}" in output


@pytest.mark.django_db
def test_delete_files_uploaded_by_user_aborts_on_no_confirmation(data_fixture):
    user = data_fixture.create_user()
    user_file = data_fixture.create_user_file(uploaded_by=user)

    with patch("builtins.input", return_value="n"):
        out = StringIO()
        call_command("delete_files_uploaded_by_user", user.id, stdout=out)

    output = out.getvalue()
    assert "Aborted by user." in output
    user_file.refresh_from_db()
    assert user_file.deleted_at is None


@pytest.mark.django_db
def test_delete_files_uploaded_by_user_deletes_files_with_yes_flag(data_fixture):
    user = data_fixture.create_user()
    user_file = data_fixture.create_user_file(uploaded_by=user)

    mock_storage = MagicMock()
    mock_storage.exists.return_value = True

    with patch(
        "baserow.core.management.commands.delete_files_uploaded_by_user.get_default_storage",
        return_value=mock_storage,
    ):
        out = StringIO()
        call_command("delete_files_uploaded_by_user", user.id, "--yes", stdout=out)

    output = out.getvalue()
    user_file.refresh_from_db()

    assert "Successfully deleted 1 file(s)" in output
    assert user_file.deleted_at is not None
    assert mock_storage.delete.called


@pytest.mark.django_db
def test_delete_files_uploaded_by_user_deletes_thumbnails(data_fixture, settings):
    user = data_fixture.create_user()
    data_fixture.create_user_file(uploaded_by=user)

    settings.USER_THUMBNAILS_DIRECTORY = "thumbnails"
    settings.USER_THUMBNAILS = {"tiny": [32, 32], "small": [64, 64]}

    mock_storage = MagicMock()
    mock_storage.exists.return_value = True

    with patch(
        "baserow.core.management.commands.delete_files_uploaded_by_user.get_default_storage",
        return_value=mock_storage,
    ):
        out = StringIO()
        call_command("delete_files_uploaded_by_user", user.id, "--yes", stdout=out)

    output = out.getvalue()

    # Verify main file was deleted
    assert "Successfully deleted 1 file(s)" in output
    # Verify thumbnails were also deleted
    delete_calls = [call[0][0] for call in mock_storage.delete.call_args_list]
    assert any("thumbnails/tiny" in path for path in delete_calls)
    assert any("thumbnails/small" in path for path in delete_calls)


@pytest.mark.django_db
def test_delete_files_uploaded_by_user_handles_missing_files(data_fixture):
    user = data_fixture.create_user()
    user_file = data_fixture.create_user_file(uploaded_by=user)

    mock_storage = MagicMock()
    mock_storage.exists.return_value = False

    with patch(
        "baserow.core.management.commands.delete_files_uploaded_by_user.get_default_storage",
        return_value=mock_storage,
    ):
        out = StringIO()
        call_command("delete_files_uploaded_by_user", user.id, "--yes", stdout=out)

    output = out.getvalue()
    user_file.refresh_from_db()

    assert "File not found in storage" in output
    assert user_file.deleted_at is not None


@pytest.mark.django_db
def test_delete_files_uploaded_by_user_logs_exceptions_but_continues(data_fixture):
    user = data_fixture.create_user()
    file1 = data_fixture.create_user_file(uploaded_by=user)
    file2 = data_fixture.create_user_file(uploaded_by=user)

    mock_storage = MagicMock()
    mock_storage.exists.return_value = True

    calls = {"count": 0}

    def delete_side_effect(*args, **kwargs):
        if calls["count"] == 0:
            calls["count"] += 1
            raise Exception("delete failed")
        return None

    mock_storage.delete.side_effect = delete_side_effect

    with patch(
        "baserow.core.management.commands.delete_files_uploaded_by_user.get_default_storage",
        return_value=mock_storage,
    ):
        out = StringIO()
        err = StringIO()
        call_command(
            "delete_files_uploaded_by_user",
            user.id,
            "--yes",
            stdout=out,
            stderr=err,
        )

    error_output = err.getvalue()
    file1.refresh_from_db()
    file2.refresh_from_db()

    # The error should be logged for the first file
    assert "Error deleting file" in error_output

    # file1 failed before marking deleted
    assert file1.deleted_at is None

    # file2 should succeed and be marked deleted
    assert file2.deleted_at is not None
