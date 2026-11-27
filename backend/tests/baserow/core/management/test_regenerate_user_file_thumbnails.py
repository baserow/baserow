from io import BytesIO, StringIO
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

import pytest
from azure.core.exceptions import ResourceNotFoundError
from botocore.exceptions import ClientError
from google.api_core.exceptions import NotFound
from PIL import Image
from storages.backends.azure_storage import AzureStorage
from storages.backends.gcloud import GoogleCloudStorage
from storages.backends.s3 import S3Storage

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


def first_read_fails(read_error):
    errors = [read_error]

    def read(fileobj, *args, **kwargs):
        if errors:
            raise errors.pop()
        Image.new("RGB", (4, 4), "red").save(fileobj, format="PNG")

    return read


def azure_storage(read_error):
    storage = AzureStorage(
        account_name="account", azure_container="container", overwrite_files=True
    )
    storage._client = Mock()
    storage._client.download_blob.return_value.readinto.side_effect = first_read_fails(
        read_error
    )
    return storage


def s3_storage(read_error):
    storage = S3Storage(bucket_name="bucket")
    storage._connections.connection = Mock()
    storage._bucket = Mock()
    storage._bucket.Object.return_value.download_fileobj.side_effect = first_read_fails(
        read_error
    )
    return storage


def gcs_storage(read_error):
    storage = GoogleCloudStorage(bucket_name="bucket")
    storage._bucket = Mock()
    storage._bucket.get_blob.return_value.download_to_file.side_effect = (
        first_read_fails(read_error)
    )
    return storage


def s3_error(status):
    return ClientError(
        {
            "Error": {"Code": str(status)},
            "ResponseMetadata": {"HTTPStatusCode": status},
        },
        "GetObject",
    )


def regenerate_on(storage):
    out = StringIO()
    with patch(
        "baserow.core.management.commands.regenerate_user_file_thumbnails"
        ".get_default_storage",
        return_value=storage,
    ):
        call_command("regenerate_user_file_thumbnails", stdout=out)
    return out.getvalue()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "create_storage,read_error",
    [
        (azure_storage, ResourceNotFoundError()),
        (s3_storage, s3_error(404)),
        (gcs_storage, NotFound("Gone.")),
    ],
    ids=["azure", "s3", "gcs"],
)
def test_regenerating_thumbnails_on_remote_storage_skips_images_without_an_original(
    data_fixture, create_storage, read_error
):
    data_fixture.create_user_file(is_image=True)
    data_fixture.create_user_file(is_image=True)

    output = regenerate_on(create_storage(read_error))

    assert "1 thumbnails have been regenerated." in output


def s3_storage_without_bucket(read_error):
    storage = s3_storage(read_error)
    storage._connections.connection.meta.client.head_bucket.side_effect = s3_error(404)
    return storage


def container_not_found():
    error = ResourceNotFoundError()
    error.error_code = "ContainerNotFound"
    return error


@pytest.mark.django_db
@pytest.mark.parametrize(
    "create_storage,read_error",
    [
        (s3_storage, s3_error(403)),
        (s3_storage_without_bucket, s3_error(404)),
        (azure_storage, container_not_found()),
    ],
    ids=["s3-denied", "s3-no-bucket", "azure-no-container"],
)
def test_regenerating_thumbnails_stops_on_other_storage_errors(
    data_fixture, create_storage, read_error
):
    data_fixture.create_user_file(is_image=True)

    with pytest.raises(type(read_error)):
        regenerate_on(create_storage(read_error))


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
