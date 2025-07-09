from io import BytesIO
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_402_PAYMENT_REQUIRED,
    HTTP_403_FORBIDDEN,
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import datetime_from_epoch

from baserow.core.context import clear_current_workspace_id, set_current_workspace_id
from baserow.core.storage import get_default_storage
from baserow.core.user.handler import UserHandler
from baserow_enterprise.secure_file_serve.constants import SecureFileServePermission


def dummy_storage(tmpdir):
    storage = get_default_storage()

    class FakeFileSystemStorage(storage.__class__):
        def exists(self, name: str) -> bool:
            return True

        def get_available_name(self, name: str, max_length: int | None = ...) -> str:
            return "test.txt"

        def open(self, name, mode="rb"):
            return BytesIO(b"Hello World")

        def delete(self, name):
            pass

    return FakeFileSystemStorage(location=str(tmpdir), base_url="http://localhost")


@pytest.mark.django_db()
@override_settings(DEBUG=True)
def test_files_are_served_by_base_file_storage_by_default(
    enterprise_data_fixture, api_client, tmpdir
):
    _, token = enterprise_data_fixture.create_user_and_token()

    with patch("baserow.core.storage.get_default_storage", new=dummy_storage(tmpdir)):
        file = SimpleUploadedFile("test.txt", b"Hello World")
        response = api_client.post(
            reverse("api:user_files:upload_file"),
            data={"file": file},
            format="multipart",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["url"].startswith(settings.MEDIA_URL)


@pytest.mark.django_db()
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION="DISABLED",
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_files_can_be_served_by_the_backend(
    enterprise_data_fixture, api_client, tmpdir
):
    _, token = enterprise_data_fixture.create_user_and_token()

    with patch("baserow.core.storage.get_default_storage", new=dummy_storage(tmpdir)):
        file = SimpleUploadedFile("test.txt", b"Hello World")
        response = api_client.post(
            reverse("api:user_files:upload_file"),
            data={"file": file},
            format="multipart",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK, response.json()
    assert response.json()["url"].startswith("http://localhost:8000/api/files/")


@pytest.mark.django_db()
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.DISABLED,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_secure_file_serve_requires_license_to_download_files(
    enterprise_data_fixture, api_client, tmpdir
):
    _, token = enterprise_data_fixture.create_user_and_token()

    with patch("baserow.core.storage.get_default_storage", new=dummy_storage(tmpdir)):
        file = SimpleUploadedFile("test.txt", b"Hello World")
        response = api_client.post(
            reverse("api:user_files:upload_file"),
            data={"file": file},
            format="multipart",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK, response.json()
    backend_file_url = response.json()["url"]

    response = api_client.get(
        backend_file_url.replace("http://localhost:8000", ""),
    )
    assert response.status_code == HTTP_402_PAYMENT_REQUIRED


@pytest.mark.django_db()
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.DISABLED,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_files_can_be_downloaded_by_the_backend_with_valid_license(
    enable_enterprise, enterprise_data_fixture, api_client, tmpdir
):
    _, token = enterprise_data_fixture.create_user_and_token()

    storage = dummy_storage(tmpdir)
    with patch("baserow.core.storage.get_default_storage", new=storage):
        file = SimpleUploadedFile("test.txt", b"Hello World")
        response = api_client.post(
            reverse("api:user_files:upload_file"),
            data={"file": file},
            format="multipart",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK, response.json()
    backend_file_url = response.json()["url"]

    with patch("baserow.core.storage.get_default_storage", new=storage):
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", ""),
        )
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db()
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.DISABLED,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_files_urls_must_be_valid(
    enable_enterprise, enterprise_data_fixture, api_client, tmpdir
):
    _, token = enterprise_data_fixture.create_user_and_token()

    storage = dummy_storage(tmpdir)
    with patch("baserow.core.storage.get_default_storage", new=storage):
        file = SimpleUploadedFile("test.txt", b"Hello World")
        response = api_client.post(
            reverse("api:user_files:upload_file"),
            data={"file": file},
            format="multipart",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK, response.json()
    backend_file_url = response.json()["url"]

    # Even with a dummy storage returning always the same file, if the signed data is
    # invalid the file cannot be downloaded
    with patch("baserow.core.storage.get_default_storage", new=storage):
        response = api_client.get(
            reverse("api:enterprise:files:download", kwargs={"signed_data": ""}),
        )
    assert response.status_code == HTTP_403_FORBIDDEN

    # Even with a dummy storage returning always the same file, if the signed data is
    # invalid the file cannot be downloaded
    with patch("baserow.core.storage.get_default_storage", new=storage):
        response = api_client.get(
            reverse("api:enterprise:files:download", kwargs={"signed_data": "invalid"}),
        )
    assert response.status_code == HTTP_403_FORBIDDEN

    # Remove a couple of characters from the signed data
    with patch("baserow.core.storage.get_default_storage", new=storage):
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", "")[:-2],
        )
    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db()
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.DISABLED,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_EXPIRE_SECONDS=59,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_files_urls_can_expire(
    enable_enterprise, enterprise_data_fixture, api_client, tmpdir
):
    user = enterprise_data_fixture.create_user()

    storage = dummy_storage(tmpdir)
    with patch("baserow.core.storage.get_default_storage", new=storage):
        with freeze_time("2024-01-01 12:00:00"):
            file = SimpleUploadedFile("test.txt", b"Hello World")
            token = enterprise_data_fixture.generate_token(user)
            response = api_client.post(
                reverse("api:user_files:upload_file"),
                data={"file": file},
                format="multipart",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )

    assert response.status_code == HTTP_200_OK, response.json()
    backend_file_url = response.json()["url"]

    # before expiration the url can be accessed
    with (
        patch("baserow.core.storage.get_default_storage", new=storage),
        freeze_time("2024-01-01 12:00:59"),
    ):
        token = enterprise_data_fixture.generate_token(user)
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", ""),
        )

    assert response.status_code == HTTP_200_OK

    # After expiration the url cannot be accessed anymore
    with (
        patch("baserow.core.storage.get_default_storage", new=storage),
        freeze_time("2024-01-01 12:01:00"),
    ):
        token = enterprise_data_fixture.generate_token(user)
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", ""),
        )

    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db()
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.SIGNED_IN,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_only_authenticated_users_can_download_files(
    enable_enterprise, enterprise_data_fixture, api_client, tmpdir
):
    user = enterprise_data_fixture.create_user(password="password")

    # Login to generate the signed cookie we need to download files
    response = api_client.post(
        reverse("api:user:token_auth"),
        data={"email": user.email, "password": "password"},
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    cookie = response.json()["user_session"]

    storage = dummy_storage(tmpdir)
    with patch("baserow.core.storage.get_default_storage", new=storage):
        file = SimpleUploadedFile("test.txt", b"Hello World")
        token = enterprise_data_fixture.generate_token(user)
        response = api_client.post(
            reverse("api:user_files:upload_file"),
            data={"file": file},
            format="multipart",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK, response.json()
    backend_file_url = response.json()["url"]

    # without cookie the url cannot be accessed
    with patch("baserow.core.storage.get_default_storage", new=storage):
        token = enterprise_data_fixture.generate_token(user)
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", ""),
        )

    assert response.status_code == HTTP_403_FORBIDDEN

    # with cookie the url can be accessed
    with patch("baserow.core.storage.get_default_storage", new=storage):
        token = enterprise_data_fixture.generate_token(user)
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", ""),
            HTTP_COOKIE=f"user_session={cookie}",
        )

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db()
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.SIGNED_IN,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_sign_out_prevents_file_download(
    enable_enterprise, enterprise_data_fixture, api_client, tmpdir
):
    user = enterprise_data_fixture.create_user(password="password")

    # Login to generate the signed cookie we need to download files
    response = api_client.post(
        reverse("api:user:token_auth"),
        data={"email": user.email, "password": "password"},
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    cookie = response.json()["user_session"]
    refresh_token = response.json()["refresh_token"]

    storage = dummy_storage(tmpdir)
    with patch("baserow.core.storage.get_default_storage", new=storage):
        file = SimpleUploadedFile("test.txt", b"Hello World")
        token = enterprise_data_fixture.generate_token(user)
        response = api_client.post(
            reverse("api:user_files:upload_file"),
            data={"file": file},
            format="multipart",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK, response.json()
    backend_file_url = response.json()["url"]

    with patch("baserow.core.storage.get_default_storage", new=storage):
        token = enterprise_data_fixture.generate_token(user)
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", ""),
            HTTP_COOKIE=f"user_session={cookie}",
        )

    assert response.status_code == HTTP_200_OK

    # If the user signs out, the cookie is invalidated and the url cannot be accessed
    expires_at = datetime_from_epoch(RefreshToken(refresh_token)["exp"])
    UserHandler().blacklist_refresh_token(refresh_token, expires_at)

    with patch("baserow.core.storage.get_default_storage", new=storage):
        token = enterprise_data_fixture.generate_token(user)
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", ""),
            HTTP_COOKIE=f"user_session={cookie}",
        )

    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db()
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.SIGNED_IN,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_deactivate_user_prevents_file_download(
    enable_enterprise, enterprise_data_fixture, api_client, tmpdir
):
    user = enterprise_data_fixture.create_user(password="password")

    # Login to generate the signed cookie we need to download files
    response = api_client.post(
        reverse("api:user:token_auth"),
        data={"email": user.email, "password": "password"},
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    cookie = response.json()["user_session"]

    storage = dummy_storage(tmpdir)
    with patch("baserow.core.storage.get_default_storage", new=storage):
        file = SimpleUploadedFile("test.txt", b"Hello World")
        token = enterprise_data_fixture.generate_token(user)
        response = api_client.post(
            reverse("api:user_files:upload_file"),
            data={"file": file},
            format="multipart",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    assert response.status_code == HTTP_200_OK, response.json()
    backend_file_url = response.json()["url"]

    with patch("baserow.core.storage.get_default_storage", new=storage):
        token = enterprise_data_fixture.generate_token(user)
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", ""),
            HTTP_COOKIE=f"user_session={cookie}",
        )

    assert response.status_code == HTTP_200_OK

    user.is_active = False
    user.save()

    with patch("baserow.core.storage.get_default_storage", new=storage):
        token = enterprise_data_fixture.generate_token(user)
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", ""),
            HTTP_COOKIE=f"user_session={cookie}",
        )

    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db()
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_EXPIRE_SECONDS=59,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.SIGNED_IN,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_files_urls_can_expire_also_for_authenticated_users(
    enable_enterprise, enterprise_data_fixture, api_client, tmpdir
):
    user = enterprise_data_fixture.create_user(password="password")

    # Login to generate the signed cookie we need to download files
    response = api_client.post(
        reverse("api:user:token_auth"),
        data={"email": user.email, "password": "password"},
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    cookie = response.json()["user_session"]

    storage = dummy_storage(tmpdir)
    with patch("baserow.core.storage.get_default_storage", new=storage):
        with freeze_time("2024-01-01 12:00:00"):
            file = SimpleUploadedFile("test.txt", b"Hello World")
            token = enterprise_data_fixture.generate_token(user)
            response = api_client.post(
                reverse("api:user_files:upload_file"),
                data={"file": file},
                format="multipart",
                HTTP_AUTHORIZATION=f"JWT {token}",
            )

    assert response.status_code == HTTP_200_OK, response.json()
    backend_file_url = response.json()["url"]

    # without cookie the url cannot be accessed
    with (
        patch("baserow.core.storage.get_default_storage", new=storage),
        freeze_time("2024-01-01 12:00:59"),
    ):
        token = enterprise_data_fixture.generate_token(user)
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", ""),
        )

    assert response.status_code == HTTP_403_FORBIDDEN

    # with cookie the url can be accessed
    with (
        patch("baserow.core.storage.get_default_storage", new=storage),
        freeze_time("2024-01-01 12:00:59"),
    ):
        token = enterprise_data_fixture.generate_token(user)
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", ""),
            HTTP_COOKIE=f"user_session={cookie}",
        )

    assert response.status_code == HTTP_200_OK

    # after expiration the url cannot be accessed anymore, even with cookie
    with (
        patch("baserow.core.storage.get_default_storage", new=storage),
        freeze_time("2024-01-01 12:01:00"),
    ):
        token = enterprise_data_fixture.generate_token(user)
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", ""),
            HTTP_COOKIE=f"user_session={cookie}",
        )

    assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db()
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.WORKSPACE_ACCESS,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_user_must_have_access_to_workspace_to_download_file(
    enable_enterprise, enterprise_data_fixture, api_client, tmpdir
):
    _, token = enterprise_data_fixture.create_user_and_token()
    user_2, token_2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user_2)

    set_current_workspace_id(workspace.id)
    storage = dummy_storage(tmpdir)
    with patch("baserow.core.storage.get_default_storage", new=storage):
        file = SimpleUploadedFile("test.txt", b"Hello World")
        response = api_client.post(
            reverse("api:user_files:upload_file"),
            data={"file": file},
            format="multipart",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    clear_current_workspace_id()
    assert response.status_code == HTTP_200_OK, response.json()
    backend_file_url = response.json()["url"]

    with (
        patch("baserow.core.storage.get_default_storage", new=storage),
        patch(
            "baserow_enterprise.api.authentication.AuthenticateFromUserSessionAuthentication.authenticate"
        ) as mock_authenticate,
    ):
        mock_authenticate.return_value = (user_2, None)
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", ""),
            HTTP_AUTHORIZATION=f"JWT {token_2}",
        )
        assert response.status_code == HTTP_200_OK


@pytest.mark.django_db()
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.WORKSPACE_ACCESS,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_user_with_wrong_workspace_cannot_download_file(
    enable_enterprise, enterprise_data_fixture, api_client, tmpdir
):
    user, token = enterprise_data_fixture.create_user_and_token()
    user_2, _ = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user_2)

    set_current_workspace_id(workspace.id)
    storage = dummy_storage(tmpdir)
    with patch("baserow.core.storage.get_default_storage", new=storage):
        file = SimpleUploadedFile("test.txt", b"Hello World")
        response = api_client.post(
            reverse("api:user_files:upload_file"),
            data={"file": file},
            format="multipart",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    clear_current_workspace_id()
    assert response.status_code == HTTP_200_OK, response.json()
    backend_file_url = response.json()["url"]

    with (
        patch("baserow.core.storage.get_default_storage", new=storage),
        patch(
            "baserow_enterprise.api.authentication.AuthenticateFromUserSessionAuthentication.authenticate"
        ) as mock_authenticate,
    ):
        mock_authenticate.return_value = (user, None)
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", ""),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db()
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.WORKSPACE_ACCESS,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_staff_user_can_download_file_without_workspace(
    enable_enterprise, enterprise_data_fixture, api_client, tmpdir
):
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)

    storage = dummy_storage(tmpdir)
    with patch("baserow.core.storage.get_default_storage", new=storage):
        file = SimpleUploadedFile("test.txt", b"Hello World")
        response = api_client.post(
            reverse("api:user_files:upload_file"),
            data={"file": file},
            format="multipart",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK, response.json()
    backend_file_url = response.json()["url"]

    with (
        patch("baserow.core.storage.get_default_storage", new=storage),
        patch(
            "baserow_enterprise.api.authentication.AuthenticateFromUserSessionAuthentication.authenticate"
        ) as mock_authenticate,
    ):
        mock_authenticate.return_value = (user, None)
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", ""),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK


@pytest.mark.django_db()
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.WORKSPACE_ACCESS,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_staff_user_cannot_download_file_outside_own_workspace(
    enable_enterprise, enterprise_data_fixture, api_client, tmpdir
):
    user, token = enterprise_data_fixture.create_user_and_token(is_staff=True)
    user_2, _ = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user_2)

    set_current_workspace_id(workspace.id)

    storage = dummy_storage(tmpdir)
    with patch("baserow.core.storage.get_default_storage", new=storage):
        file = SimpleUploadedFile("test.txt", b"Hello World")
        response = api_client.post(
            reverse("api:user_files:upload_file"),
            data={"file": file},
            format="multipart",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    clear_current_workspace_id()
    assert response.status_code == HTTP_200_OK, response.json()
    backend_file_url = response.json()["url"]

    with (
        patch("baserow.core.storage.get_default_storage", new=storage),
        patch(
            "baserow_enterprise.api.authentication.AuthenticateFromUserSessionAuthentication.authenticate"
        ) as mock_authenticate,
    ):
        mock_authenticate.return_value = (user, None)
        response = api_client.get(
            backend_file_url.replace("http://localhost:8000", ""),
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db()
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_exporting_csv_writes_file_to_storage_and_its_served_by_the_backend(
    enable_enterprise,
    enterprise_data_fixture,
    api_client,
    tmpdir,
    django_capture_on_commit_callbacks,
    use_tmp_media_root,
):
    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)

    token = enterprise_data_fixture.generate_token(user)
    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            reverse(
                "api:database:export:export_table",
                kwargs={"table_id": table.id},
            ),
            data={
                "exporter_type": "csv",
                "export_charset": "utf-8",
                "csv_include_header": "True",
                "csv_column_separator": ",",
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    response_json = response.json()
    job_id = response_json["id"]
    response = api_client.get(
        reverse("api:database:export:get", kwargs={"job_id": job_id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    json = response.json()

    # The file is served by the backend
    assert json["url"].startswith("http://localhost:8000/api/files/")

    # download it
    response = api_client.get(json["url"].replace("http://localhost:8000", ""))

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_audit_log_can_export_to_csv_and_be_served_by_the_backend(
    api_client,
    enterprise_data_fixture,
    synced_roles,
    django_capture_on_commit_callbacks,
    tmpdir,
    use_tmp_media_root,
):
    (
        admin_user,
        admin_token,
    ) = enterprise_data_fixture.create_enterprise_admin_user_and_token()

    csv_settings = {
        "csv_column_separator": ",",
        "csv_first_row_header": True,
        "export_charset": "utf-8",
    }

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            reverse("api:enterprise:audit_log:async_export"),
            data=csv_settings,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {admin_token}",
        )
        assert response.status_code == HTTP_202_ACCEPTED, response.json()
        job = response.json()
        assert job["id"] is not None
        assert job["state"] == "pending"
        assert job["type"] == "audit_log_export"

    admin_token = enterprise_data_fixture.generate_token(admin_user)
    response = api_client.get(
        reverse(
            "api:jobs:item",
            kwargs={"job_id": job["id"]},
        ),
        HTTP_AUTHORIZATION=f"JWT {admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    job = response.json()
    assert job["state"] == "finished"
    assert job["type"] == "audit_log_export"

    # The file is served by the backend
    assert job["url"].startswith("http://localhost:8000/api/files/")

    # download it
    response = api_client.get(job["url"].replace("http://localhost:8000", ""))

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db()
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_files_can_be_downloaded_with_dl_query_param_as_filename(
    enable_enterprise, enterprise_data_fixture, api_client, tmpdir, use_tmp_media_root
):
    _, token = enterprise_data_fixture.create_user_and_token()

    file = SimpleUploadedFile("test.txt", b"Hello World")
    response = api_client.post(
        reverse("api:user_files:upload_file"),
        data={"file": file},
        format="multipart",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK, response.json()
    backend_file_url = response.json()["url"]
    file_name = response.json()["name"]

    response = api_client.get(
        backend_file_url.replace("http://localhost:8000", ""),
    )
    assert response.status_code == HTTP_200_OK
    assert response.headers["Content-Disposition"] == f'inline; filename="{file_name}"'

    response = api_client.get(
        backend_file_url.replace("http://localhost:8000", "") + "?dl=",
    )
    assert response.status_code == HTTP_200_OK
    assert response.headers["Content-Disposition"] == f'inline; filename="{file_name}"'

    response = api_client.get(
        backend_file_url.replace("http://localhost:8000", "") + "?dl=download.txt",
    )
    assert response.status_code == HTTP_200_OK
    assert (
        response.headers["Content-Disposition"] == 'attachment; filename="download.txt"'
    )

    response = api_client.get(
        backend_file_url.replace("http://localhost:8000", "") + "?dl=1",
    )
    assert response.status_code == HTTP_200_OK
    assert response.headers["Content-Disposition"] == 'attachment; filename="1"'


@pytest.mark.django_db
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.WORKSPACE_ACCESS,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_audit_log_can_export_to_csv_and_be_served_by_the_backend_with_workspace_access(
    api_client,
    enterprise_data_fixture,
    synced_roles,
    django_capture_on_commit_callbacks,
    tmpdir,
    use_tmp_media_root,
):
    (
        admin_user,
        admin_token,
    ) = enterprise_data_fixture.create_enterprise_admin_user_and_token()

    wp_admin_user, wp_admin_token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=wp_admin_user)

    other_wp_admin_user = enterprise_data_fixture.create_user()

    csv_settings = {
        "filter_workspace_id": workspace.id,
        "csv_column_separator": ",",
        "csv_first_row_header": True,
        "export_charset": "utf-8",
    }

    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            reverse("api:enterprise:audit_log:async_export"),
            data=csv_settings,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {wp_admin_token}",
        )
        assert response.status_code == HTTP_202_ACCEPTED, response.json()
        job = response.json()
        assert job["id"] is not None
        assert job["state"] == "pending"
        assert job["type"] == "audit_log_export"

    response = api_client.get(
        reverse(
            "api:jobs:item",
            kwargs={"job_id": job["id"]},
        ),
        HTTP_AUTHORIZATION=f"JWT {wp_admin_token}",
    )
    assert response.status_code == HTTP_200_OK
    job = response.json()
    assert job["state"] == "finished"
    assert job["type"] == "audit_log_export"

    # The file is served by the backend
    assert job["url"].startswith("http://localhost:8000/api/files/")

    # download it
    with (
        patch(
            "baserow_enterprise.api.authentication.AuthenticateFromUserSessionAuthentication.authenticate",
            side_effect=[(wp_admin_user, None), (other_wp_admin_user, None)],
        ) as mock_authenticate,
    ):
        response = api_client.get(job["url"].replace("http://localhost:8000", ""))
        assert response.status_code == HTTP_200_OK

        response = api_client.get(job["url"].replace("http://localhost:8000", ""))
        assert response.status_code == HTTP_403_FORBIDDEN


@pytest.mark.django_db()
@override_settings(
    DEBUG=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND=True,
    BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION=SecureFileServePermission.WORKSPACE_ACCESS,
    STORAGES={
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    },
)
def test_exporting_csv_writes_file_to_storage_and_its_served_by_the_backend_with_workspace_access(
    enable_enterprise,
    enterprise_data_fixture,
    api_client,
    tmpdir,
    django_capture_on_commit_callbacks,
    use_tmp_media_root,
):
    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)

    other_user = enterprise_data_fixture.create_user()

    token = enterprise_data_fixture.generate_token(user)
    with django_capture_on_commit_callbacks(execute=True):
        response = api_client.post(
            reverse(
                "api:database:export:export_table",
                kwargs={"table_id": table.id},
            ),
            data={
                "exporter_type": "csv",
                "export_charset": "utf-8",
                "csv_include_header": "True",
                "csv_column_separator": ",",
            },
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    response_json = response.json()
    job_id = response_json["id"]
    response = api_client.get(
        reverse("api:database:export:get", kwargs={"job_id": job_id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    json = response.json()

    # The file is served by the backend
    assert json["url"].startswith("http://localhost:8000/api/files/")

    # download it
    with (
        patch(
            "baserow_enterprise.api.authentication.AuthenticateFromUserSessionAuthentication.authenticate",
            side_effect=[(user, None), (other_user, None)],
        ) as mock_authenticate,
    ):
        response = api_client.get(json["url"].replace("http://localhost:8000", ""))
        assert response.status_code == HTTP_200_OK

        response = api_client.get(json["url"].replace("http://localhost:8000", ""))
        assert response.status_code == HTTP_403_FORBIDDEN
