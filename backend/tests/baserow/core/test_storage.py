from types import SimpleNamespace

from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage, InMemoryStorage

import pytest
from botocore.stub import Stubber
from storages.backends.azure_storage import AzureStorage
from storages.backends.gcloud import GoogleCloudStorage
from storages.backends.s3 import S3Storage

from baserow.core.storage import iter_storage_names_with_prefixes

NAME_PREFIX = "tpl0000000012"
PREFIX = f"user_files/{NAME_PREFIX}"
NAMES = ["user_files/tpl0000000012_a.png", "user_files/tpl0000000012_b.png"]
NESTED = "user_files/tpl0000000012/c.png"


def listed_blobs(prefix):
    if prefix != f"media/{PREFIX}":
        return []
    return [SimpleNamespace(name=f"media/{name}") for name in NAMES + [NESTED]]


def file_system_storage(tmp_path):
    storage = FileSystemStorage(location=tmp_path)
    for name in NAMES + ["user_files/tpl0000000120_c.png", "user_files/d.png", NESTED]:
        storage.save(name, ContentFile(b""))
    return storage


def s3_storage(tmp_path):
    storage = S3Storage(
        bucket_name="bucket",
        location="media",
        region_name="eu-central-1",
        access_key="key",
        secret_key="secret",
    )
    stubber = Stubber(storage.connection.meta.client)
    params = {"Bucket": "bucket", "Prefix": f"media/{PREFIX}"}
    stubber.add_response(
        "list_objects_v2",
        {
            "Contents": [{"Key": f"media/{NAMES[0]}"}],
            "IsTruncated": True,
            "NextContinuationToken": "next",
        },
        params,
    )
    stubber.add_response(
        "list_objects_v2",
        {
            "Contents": [{"Key": f"media/{NAMES[1]}"}, {"Key": f"media/{NESTED}"}],
            "IsTruncated": False,
        },
        {**params, "ContinuationToken": "next"},
    )
    stubber.activate()
    return storage


def google_cloud_storage(tmp_path):
    storage = GoogleCloudStorage(bucket_name="bucket", location="media")
    storage._bucket = SimpleNamespace(list_blobs=lambda prefix: listed_blobs(prefix))
    return storage


def azure_storage(tmp_path, location="media"):
    storage = AzureStorage(
        account_name="account", azure_container="container", location=location
    )
    storage._client = SimpleNamespace(
        list_blobs=lambda name_starts_with: listed_blobs(name_starts_with)
    )
    return storage


@pytest.mark.parametrize(
    "build_storage,folder,name_prefixes,expected",
    [
        (file_system_storage, "user_files", [NAME_PREFIX], NAMES),
        (
            file_system_storage,
            "user_files",
            [NAME_PREFIX, "tpl0000000120"],
            NAMES + ["user_files/tpl0000000120_c.png"],
        ),
        (file_system_storage, "user_files", [], []),
        (file_system_storage, "thumbnails/tiny", [NAME_PREFIX], []),
        (s3_storage, "user_files", [NAME_PREFIX], NAMES),
        (google_cloud_storage, "user_files", [NAME_PREFIX], NAMES),
        (azure_storage, "user_files", [NAME_PREFIX], NAMES),
        (
            lambda tmp_path: azure_storage(tmp_path, ".media"),
            "user_files",
            [NAME_PREFIX],
            NAMES,
        ),
        (lambda tmp_path: InMemoryStorage(), "user_files", [NAME_PREFIX], []),
    ],
)
def test_iter_storage_names_with_prefixes(
    tmp_path, build_storage, folder, name_prefixes, expected
):
    storage = build_storage(tmp_path)

    assert (
        sorted(iter_storage_names_with_prefixes(storage, folder, name_prefixes))
        == expected
    )
