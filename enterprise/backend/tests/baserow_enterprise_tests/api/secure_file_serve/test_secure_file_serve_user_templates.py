from unittest.mock import patch

from django.core.files.base import ContentFile
from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_403_FORBIDDEN

from baserow.core.context import get_current_workspace_id
from baserow.core.models import Template
from baserow.core.storage import get_default_storage
from baserow.core.user_templates.archive import new_template_archive_name
from baserow_enterprise.secure_file_serve.constants import SecureFileServePermission

ARCHIVE_CONTENT = b"user template archive"


@pytest.fixture
def secure_file_serve(settings, use_tmp_media_root, request):
    settings.DEBUG = True
    settings.BASEROW_SERVE_FILES_THROUGH_BACKEND = True
    settings.BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION = request.param
    settings.STORAGES = {
        "default": {
            "BACKEND": "baserow_enterprise.secure_file_serve.storage.EnterpriseFileStorage"
        }
    }
    return request.param


def _create_user_template(data_fixture, owner, *, public=False):
    """
    A user template with a database and a valid archive in the secure storage, like
    a download built it.
    """

    root = data_fixture.create_user_template(user=owner)
    data_fixture.create_database_application(workspace=root.workspace)
    archive_name = get_default_storage().save(
        new_template_archive_name(root.id), ContentFile(ARCHIVE_CONTENT)
    )
    Template.objects.filter(id=root.id).update(archive=archive_name)
    if public:
        data_fixture.set_user_template_state(root, "public")
    root.refresh_from_db()
    return root


def _get_download_url(api_client, token, template):
    response = api_client.post(
        reverse("api:templates:download", kwargs={"slug": template.slug}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    # The archive is valid, so it's handed out without a job.
    assert response.status_code == HTTP_200_OK, response.json()
    # The URL is signed with the workspace only while it's made.
    assert get_current_workspace_id() is None
    url = response.json()["url"]
    # Served by the backend, not straight from the media folder.
    assert "/api/files/" in url
    return url


def _fetch(api_client, user, url):
    with patch(
        "baserow_enterprise.api.authentication.AuthenticateFromUserSessionAuthentication.authenticate"
    ) as mock_authenticate:
        mock_authenticate.return_value = (user, None)
        return api_client.get(url.replace("http://localhost:8000", ""))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "secure_file_serve", [SecureFileServePermission.WORKSPACE_ACCESS], indirect=True
)
def test_user_template_archive_can_be_downloaded_through_secure_file_serve(
    enable_enterprise, enterprise_data_fixture, api_client, secure_file_serve
):
    owner, owner_token = enterprise_data_fixture.create_user_and_token()
    viewer, viewer_token = enterprise_data_fixture.create_user_and_token()
    stranger = enterprise_data_fixture.create_user()
    private = _create_user_template(enterprise_data_fixture, owner)
    public = _create_user_template(enterprise_data_fixture, owner, public=True)

    response = _fetch(
        api_client, viewer, _get_download_url(api_client, viewer_token, public)
    )

    assert response.status_code == HTTP_200_OK
    assert b"".join(response.streaming_content) == ARCHIVE_CONTENT

    # The URL is signed with the template workspace, so it only opens for who can
    # open the template.
    url = _get_download_url(api_client, owner_token, private)
    response = _fetch(api_client, stranger, url)
    assert response.status_code == HTTP_403_FORBIDDEN
