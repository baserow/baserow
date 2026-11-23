from io import BytesIO
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

import pytest
from azure.core.exceptions import ResourceNotFoundError
from PIL import Image
from storages.backends.azure_storage import AzureStorage

from baserow.core.storage import get_default_storage
from baserow.core.user_files.handler import UserFileHandler
from baserow.core.user_files.models import UserFile


def upload_image(name):
    buffer = BytesIO()
    Image.new("RGB", (4, 4), "red").save(buffer, format="PNG")
    buffer.seek(0)
    return UserFileHandler().upload_user_file(None, name, buffer)


def remove_thumbnails(user_file):
    paths = [
        UserFileHandler().user_file_thumbnail_path(user_file, name)
        for name in settings.USER_THUMBNAILS
    ]
    for path in paths:
        get_default_storage().delete(path)
    return paths


@pytest.mark.django_db
@pytest.mark.usefixtures("use_tmp_media_root")
def test_regenerating_thumbnails_skips_images_without_an_original():
    vanished = upload_image("vanished.png")
    get_default_storage().delete(UserFileHandler().user_file_path(vanished))
    thumbnails = remove_thumbnails(upload_image("live.png"))

    call_command("regenerate_user_file_thumbnails")

    assert all(get_default_storage().exists(path) for path in thumbnails)


@pytest.mark.django_db
def test_regenerating_thumbnails_on_azure_skips_images_without_an_original(
    data_fixture,
):
    data_fixture.create_user_file(is_image=True)
    storage = AzureStorage(account_name="account", azure_container="container")
    storage._client = Mock()
    storage._client.download_blob.side_effect = ResourceNotFoundError()

    with patch(
        "baserow.core.management.commands.regenerate_user_file_thumbnails"
        ".get_default_storage",
        return_value=storage,
    ):
        call_command("regenerate_user_file_thumbnails")


@pytest.mark.django_db
@pytest.mark.usefixtures("use_tmp_media_root")
def test_regenerating_thumbnails_reaches_every_image_when_one_is_deleted_meanwhile(
    data_fixture,
):
    deleted, *_ = [data_fixture.create_user_file(is_image=True) for _ in range(100)]
    thumbnails = remove_thumbnails(upload_image("last.png"))
    user_file_path = UserFileHandler.user_file_path

    def delete_meanwhile(handler, user_file):
        UserFile.objects.filter(id=deleted.id).update(deleted_at=timezone.now())
        return user_file_path(handler, user_file)

    with patch.object(
        UserFileHandler, "user_file_path", autospec=True, side_effect=delete_meanwhile
    ):
        call_command("regenerate_user_file_thumbnails")

    assert all(get_default_storage().exists(path) for path in thumbnails)
