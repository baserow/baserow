import re
import string
from io import BytesIO
from unittest.mock import MagicMock
from zipfile import ZIP_DEFLATED, ZipFile

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage

import httpretty
import pytest
import zipstream
from freezegun import freeze_time
from PIL import Image

from baserow.core.models import UserFile
from baserow.core.storage import ExportZipFile
from baserow.core.user_files.exceptions import (
    FileSizeTooLargeError,
    FileURLCouldNotBeReached,
    InvalidFileStreamError,
    InvalidFileURLError,
    MaximumUniqueTriesError,
)
from baserow.core.user_files.handler import UserFileHandler

GENERATED_FILE_NAME_LENGTH = 16  # 12 hexdigest + '.' + ext


@pytest.mark.django_db
def test_user_file_path(data_fixture):
    handler = UserFileHandler()
    assert handler.user_file_path("test.jpg") == "user_files/test.jpg"
    assert handler.user_file_path("another_file.png") == "user_files/another_file.png"

    user_file = data_fixture.create_user_file()
    assert handler.user_file_path(user_file) == f"user_files/{user_file.name}"


@pytest.mark.django_db
def test_user_file_thumbnail_path(data_fixture):
    handler = UserFileHandler()
    assert (
        handler.user_file_thumbnail_path("test.jpg", "tiny")
        == "thumbnails/tiny/test.jpg"
    )
    assert (
        handler.user_file_thumbnail_path("another_file.png", "small")
        == "thumbnails/small/another_file.png"
    )

    user_file = data_fixture.create_user_file()
    assert (
        handler.user_file_thumbnail_path(user_file, "tiny")
        == f"thumbnails/tiny/{user_file.name}"
    )


@pytest.mark.django_db
def test_generate_unique(data_fixture):
    user = data_fixture.create_user()
    handler = UserFileHandler()

    assert len(handler.generate_unique("test", "txt", 32)) == 32
    assert len(handler.generate_unique("test", "txt", 10)) == 10
    assert handler.generate_unique("test", "txt", 32) != handler.generate_unique(
        "test", "txt", 32
    )

    unique = handler.generate_unique("test", "txt", 32)
    assert not UserFile.objects.filter(unique=unique).exists()

    for char in string.ascii_letters + string.digits:
        data_fixture.create_user_file(
            uploaded_by=user, unique=char, original_extension="txt", sha256_hash="test"
        )

    with pytest.raises(MaximumUniqueTriesError):
        handler.generate_unique("test", "txt", 1, 3)

    handler.generate_unique("test2", "txt", 1, 3)
    handler.generate_unique("test", "txt2", 1, 3)


@pytest.mark.django_db
def test_upload_user_file(data_fixture, tmpdir):
    user = data_fixture.create_user()

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()

    with pytest.raises(InvalidFileStreamError):
        handler.upload_user_file(user, "test.txt", "NOT A STREAM!", storage=storage)

    with pytest.raises(InvalidFileStreamError):
        handler.upload_user_file(user, "test.txt", None, storage=storage)

    old_limit = settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB
    settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB = 6
    with pytest.raises(FileSizeTooLargeError):
        handler.upload_user_file(user, "test.txt", ContentFile(b"Hello World"))
    settings.BASEROW_FILE_UPLOAD_SIZE_LIMIT_MB = old_limit

    with freeze_time("2020-01-01 12:00"):
        user_file = handler.upload_user_file(
            user, "test.txt", ContentFile(b"Hello World"), storage=storage
        )

    assert user_file.original_name == "test.txt"
    assert user_file.original_extension == "txt"
    assert len(user_file.unique) == 32
    assert user_file.size == 11
    assert user_file.mime_type == "text/plain"
    assert user_file.uploaded_by_id == user.id
    assert user_file.uploaded_at.year == 2020
    assert user_file.uploaded_at.month == 1
    assert user_file.uploaded_at.day == 1
    assert user_file.is_image is False
    assert user_file.image_width is None
    assert user_file.image_height is None
    assert user_file.sha256_hash == (
        "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"
    )
    file_path = tmpdir.join("user_files", user_file.name)
    assert file_path.isfile()
    assert file_path.open().read() == "Hello World"

    user_file = handler.upload_user_file(
        user, "another.txt", BytesIO(b"Hello"), storage=storage
    )
    assert user_file.original_name == "another.txt"
    assert user_file.original_extension == "txt"
    assert user_file.mime_type == "text/plain"
    assert user_file.size == 5
    assert user_file.sha256_hash == (
        "185f8db32271fe25f561a6fc938b2e264306ec304eda518007d1764826381969"
    )
    file_path = tmpdir.join("user_files", user_file.name)
    assert file_path.isfile()
    assert file_path.open().read() == "Hello"

    assert (
        handler.upload_user_file(
            user, "another.txt", ContentFile(b"Hello"), storage=storage
        ).id
        == user_file.id
    )
    assert (
        handler.upload_user_file(
            user, "another_name.txt", ContentFile(b"Hello"), storage=storage
        ).id
        != user_file.id
    )

    image = Image.new("RGB", (100, 140), color="red")
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")

    user_file = handler.upload_user_file(
        user, "some image.png", image_bytes, storage=storage
    )
    assert user_file.mime_type == "image/png"
    assert user_file.is_image is True
    assert user_file.image_width == 100
    assert user_file.image_height == 140
    file_path = tmpdir.join("user_files", user_file.name)
    assert file_path.isfile()
    file_path = tmpdir.join("thumbnails", "tiny", user_file.name)
    assert file_path.isfile()
    thumbnail = Image.open(file_path.open("rb"))
    assert thumbnail.height == 21
    assert thumbnail.width == 21

    old_thumbnail_settings = settings.USER_THUMBNAILS
    settings.USER_THUMBNAILS = {"tiny": [None, 100]}
    image = Image.new("RGB", (1920, 1080), color="red")
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")
    user_file = handler.upload_user_file(user, "red.png", image_bytes, storage=storage)
    file_path = tmpdir.join("thumbnails", "tiny", user_file.name)
    assert file_path.isfile()
    thumbnail = Image.open(file_path.open("rb"))
    assert thumbnail.width == 178
    assert thumbnail.height == 100

    image = Image.new("RGB", (400, 400), color="red")
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")
    user_file = handler.upload_user_file(user, "red2.png", image_bytes, storage=storage)
    file_path = tmpdir.join("thumbnails", "tiny", user_file.name)
    assert file_path.isfile()
    thumbnail = Image.open(file_path.open("rb"))
    assert thumbnail.width == 100
    assert thumbnail.height == 100

    settings.USER_THUMBNAILS = {"tiny": [21, None]}
    image = Image.new("RGB", (1400, 1000), color="red")
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")
    user_file = handler.upload_user_file(user, "red3.png", image_bytes, storage=storage)
    file_path = tmpdir.join("thumbnails", "tiny", user_file.name)
    assert file_path.isfile()
    thumbnail = Image.open(file_path.open("rb"))
    assert thumbnail.width == 21
    assert thumbnail.height == 15
    settings.USER_THUMBNAILS = old_thumbnail_settings

    # uploading the same image won't generate another thumbnail
    image = Image.new("RGB", (1400, 1000), color="red")
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")
    assert (
        handler.upload_user_file(user, "red3.png", image_bytes, storage=storage).id
        == user_file.id
    )

    assert len(storage.listdir(tmpdir / "thumbnails/tiny")[1]) == 4
    assert len(storage.listdir(tmpdir / "user_files")[1]) == 7

    assert UserFile.objects.all().count() == 7

    image = Image.new("RGB", (1, 1), color="red")
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")
    user_file = handler.upload_user_file(
        user,
        "this_file_has_an_extreme_long_file_name_that_should_not_make_the_system_"
        "fail_hard_when_trying_to_upload.png",
        image_bytes,
        storage=storage,
    )

    assert (
        user_file.original_name == "this_file_has_an_extreme_long_f...hard_when_"
        "trying_to_upload.png"
    )


@pytest.mark.django_db
def test_upload_user_file_with_truncated_image(data_fixture, tmpdir):
    user = data_fixture.create_user()

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()

    image = Image.new("RGB", (100, 140), color="red")
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")

    truncated_bytes = BytesIO(image_bytes.getvalue()[:-100])

    user_file = handler.upload_user_file(
        user, "truncated_image.png", truncated_bytes, storage=storage
    )
    assert user_file.mime_type == "image/png"
    assert user_file.is_image is True
    assert user_file.image_width == 100
    assert user_file.image_height == 140

    file_path = tmpdir.join("thumbnails", "tiny", user_file.name)
    assert not file_path.isfile()


@pytest.mark.django_db
def test_upload_user_file_with_unsupported_image_format(
    data_fixture, tmpdir, open_test_file
):
    user = data_fixture.create_user()

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()

    image_bytes = open_test_file("baserow/core/user_file/baserow.logo.psd")

    user_file = handler.upload_user_file(
        user, "truncated_image.psd", image_bytes, storage=storage
    )
    assert user_file.mime_type == "image/psd"
    assert user_file.is_image is False
    assert user_file.image_width is None
    assert user_file.image_height is None

    file_path = tmpdir.join("thumbnails", "tiny", user_file.name)
    assert not file_path.isfile()


@pytest.mark.django_db
@httpretty.activate(verbose=True, allow_net_connect=False)
def test_upload_user_file_by_url(data_fixture, tmpdir):
    user = data_fixture.create_user()

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()

    httpretty.register_uri(
        httpretty.GET,
        "https://baserow.io/test.txt",
        body=b"Hello World",
        status=200,
        content_type="text/plain",
    )

    httpretty.register_uri(
        httpretty.GET,
        "https://baserow.io/not-found.pdf",
        status=404,
    )

    # Could not be reached because it it responds with a 404
    with pytest.raises(FileURLCouldNotBeReached):
        handler.upload_user_file_by_url(
            user, "https://baserow.io/not-found.pdf", storage=storage
        )

    # Only the http and https protocol are supported.
    with pytest.raises(InvalidFileURLError):
        handler.upload_user_file_by_url(
            user, "ftp://baserow.io/not-found.pdf", storage=storage
        )

    with freeze_time("2020-01-01 12:00"):
        user_file = handler.upload_user_file_by_url(
            user, "https://baserow.io/test.txt", storage=storage
        )

    assert user_file.original_name == "test.txt"
    assert user_file.original_extension == "txt"
    assert len(user_file.unique) == 32
    assert user_file.size == 11
    assert user_file.mime_type == "text/plain"
    assert user_file.uploaded_by_id == user.id
    assert user_file.uploaded_at.year == 2020
    assert user_file.uploaded_at.month == 1
    assert user_file.uploaded_at.day == 1
    assert user_file.is_image is False
    assert user_file.image_width is None
    assert user_file.image_height is None
    assert user_file.sha256_hash == (
        "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"
    )
    file_path = tmpdir.join("user_files", user_file.name)
    assert file_path.isfile()
    assert file_path.open().read() == "Hello World"


@pytest.mark.django_db
def test_upload_user_file_by_url_within_private_network(data_fixture, tmpdir):
    user = data_fixture.create_user()

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()

    # Could not be reached because it is an internal private URL.
    with pytest.raises(FileURLCouldNotBeReached):
        handler.upload_user_file_by_url(
            user, "http://localhost/test.txt", storage=storage
        )

    with pytest.raises(FileURLCouldNotBeReached):
        handler.upload_user_file_by_url(
            user, "http://192.168.1.1/test.txt", storage=storage
        )


@pytest.mark.django_db
@httpretty.activate(verbose=True, allow_net_connect=False)
def test_upload_user_file_by_url_with_querystring(data_fixture, tmpdir) -> None:
    user = data_fixture.create_user()

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()

    remote_file = "https://baserow.io/test.txt?utm_source=google&utm_medium=email&utm_campaign=fall"

    httpretty.register_uri(
        httpretty.GET,
        remote_file,
        body=b"Hello World",
        status=200,
        content_type="text/plain",
    )

    with freeze_time("2022-08-30 09:00"):
        user_file = handler.upload_user_file_by_url(user, remote_file, storage=storage)

    assert user_file.original_name == "test.txt"
    assert user_file.original_extension == "txt"
    assert len(user_file.unique) == 32
    assert user_file.mime_type == "text/plain"
    assert user_file.uploaded_by_id == user.id
    assert user_file.uploaded_at.year == 2022
    assert user_file.uploaded_at.month == 8
    assert user_file.uploaded_at.day == 30
    assert user_file.is_image is False
    assert user_file.image_width is None
    assert user_file.image_height is None


@pytest.mark.django_db
@httpretty.activate(verbose=True, allow_net_connect=False)
def test_upload_user_file_by_url_with_image_without_extension_with_wrong_content_type(
    data_fixture, tmpdir
) -> None:
    user = data_fixture.create_user()

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()

    remote_file = "https://baserow.io/image-without-url"

    httpretty.register_uri(
        httpretty.GET,
        remote_file,
        body=bytes(
            [
                0x42,
                0x4D,
                0x3A,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x36,
                0x00,
                0x00,
                0x00,
                0x28,
                0x00,
                0x00,
                0x00,
                0x01,
                0x00,
                0x00,
                0x00,
                0x01,
                0x00,
                0x00,
                0x00,
                0x01,
                0x00,
                0x18,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x04,
                0x00,
                0x00,
                0x00,
                0x13,
                0x0B,
                0x00,
                0x00,
                0x13,
                0x0B,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0xFF,  # Red pixel data in BGR format
            ]
        ),
        status=200,
        content_type="image/jpeg",
    )

    with freeze_time("2022-08-30 09:00"):
        user_file = handler.upload_user_file_by_url(user, remote_file, storage=storage)

    assert user_file.original_name == "image-without-url"
    assert user_file.original_extension == ""
    assert user_file.mime_type == "image/bmp"
    assert user_file.uploaded_by_id == user.id
    assert user_file.uploaded_at.year == 2022
    assert user_file.uploaded_at.month == 8
    assert user_file.uploaded_at.day == 30
    assert user_file.is_image is True
    assert user_file.image_width == 1
    assert user_file.image_height == 1


@pytest.mark.django_db
@httpretty.activate(verbose=True, allow_net_connect=False)
def test_upload_user_file_by_url_with_slash(data_fixture, tmpdir) -> None:
    user = data_fixture.create_user()

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()

    remote_file = "https://baserow.io/test.txt/"

    httpretty.register_uri(
        httpretty.GET,
        remote_file,
        body=b"Hello World",
        status=200,
        content_type="text/plain",
    )

    with freeze_time("2022-08-30 09:00"):
        user_file = handler.upload_user_file_by_url(user, remote_file, storage=storage)

    assert user_file.original_name == "test.txt"
    assert user_file.original_extension == "txt"
    assert len(user_file.unique) == 32
    assert user_file.mime_type == "text/plain"
    assert user_file.uploaded_by_id == user.id
    assert user_file.uploaded_at.year == 2022
    assert user_file.uploaded_at.month == 8
    assert user_file.uploaded_at.day == 30
    assert user_file.is_image is False
    assert user_file.image_width is None
    assert user_file.image_height is None


@pytest.mark.django_db
@httpretty.activate(verbose=True, allow_net_connect=False)
def test_upload_user_file_by_url_without_path(data_fixture, tmpdir) -> None:
    user = data_fixture.create_user()

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()

    remote_file = "https://baserow.io/"

    httpretty.register_uri(
        httpretty.GET,
        remote_file,
        body=b"Hello World",
        status=200,
        content_type="text/plain; charset:utf-8",
    )

    with freeze_time("2022-08-30 09:00"):
        user_file = handler.upload_user_file_by_url(user, remote_file, storage=storage)

    assert (
        user_file.original_name
        and user_file.original_name.endswith(".txt")
        and len(user_file.original_name) == GENERATED_FILE_NAME_LENGTH
    )
    assert user_file.original_extension == "txt"
    assert len(user_file.unique) == 32
    assert user_file.mime_type == "text/plain"
    assert user_file.uploaded_by_id == user.id
    assert user_file.uploaded_at.year == 2022
    assert user_file.uploaded_at.month == 8
    assert user_file.uploaded_at.day == 30
    assert user_file.is_image is False
    assert user_file.image_width is None
    assert user_file.image_height is None


@pytest.mark.parametrize(
    "uri,remote_file",
    [
        # uri is url used by http client, remote_file is the name
        # that UseFileHandler receives because
        # http client will translate `/.`, `/..`, `/../` paths to `/`
        (
            "https://baserow.io/",
            "https://baserow.io/../",
        ),
        ("https://baserow.io/", "https://baserow.io/../.."),
        ("https://baserow.io/", "https://baserow.io/../."),
        ("https://baserow.io/", "https://baserow.io/.."),
        (
            "https://baserow.io/",
            "https://baserow.io/.",
        ),
    ],
)
@pytest.mark.django_db
@httpretty.activate(verbose=True, allow_net_connect=False)
def test_upload_user_file_by_url_with_invalid_paths(
    data_fixture, tmpdir, uri, remote_file
) -> None:
    user = data_fixture.create_user()

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()

    httpretty.register_uri(
        httpretty.GET,
        uri=uri,
        body=b"Hello World",
        status=200,
        content_type="text/plain",
    )

    # upload will end up with django error
    with pytest.raises(SuspiciousFileOperation):
        handler.upload_user_file_by_url(user, remote_file, storage=storage)


@pytest.mark.django_db
@httpretty.activate(verbose=True, allow_net_connect=False)
def test_upload_user_file_by_url_with_invalid_content_type(
    data_fixture, tmpdir
) -> None:
    user = data_fixture.create_user()

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()

    remote_file = "https://baserow.io//"

    httpretty.register_uri(
        httpretty.GET,
        re.compile(r"https://baserow.io.*"),
        body=b"Hello World",
        status=200,
        content_type="foobar/barfoo",
    )

    with freeze_time("2022-08-30 09:00"):
        user_file = handler.upload_user_file_by_url(user, remote_file, storage=storage)

    assert (
        user_file.original_name
        and user_file.original_name.endswith(".bin")
        and len(user_file.original_name) == GENERATED_FILE_NAME_LENGTH
    )
    assert user_file.original_extension == "bin"
    assert len(user_file.unique) == 32
    assert user_file.mime_type == "application/octet-stream"
    assert user_file.uploaded_by_id == user.id
    assert user_file.uploaded_at.year == 2022
    assert user_file.uploaded_at.month == 8
    assert user_file.uploaded_at.day == 30
    assert user_file.is_image is False
    assert user_file.image_width is None
    assert user_file.image_height is None


def test_export_user_file_returns_none_if_user_file_is_empty():
    """Ensure that None is returned if user_file is empty."""

    handler = UserFileHandler()
    handler.user_file_path = MagicMock()
    assert handler.export_user_file(None) is None

    handler.user_file_path.assert_not_called()


@pytest.mark.django_db
def test_export_user_file_doesnt_add_if_file_exists_in_files_zip(
    data_fixture,
    tmpdir,
):
    """Ensure the file isn't added to files_zip if it already exists."""

    user = data_fixture.create_user()
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")

    # Create an image user file
    image = Image.new("RGB", (100, 140), color="red")
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")

    original_name = "mock_image.png"
    handler = UserFileHandler()
    user_file = handler.upload_user_file(
        user, original_name, image_bytes, storage=storage
    )

    zip_file = ExportZipFile(
        compress_level=settings.BASEROW_DEFAULT_ZIP_COMPRESS_LEVEL,
        compress_type=zipstream.ZIP_DEFLATED,
    )
    # Pretend the file already exists and verify that add() is not called.
    zip_file.info_list = MagicMock(return_value=[{"name": user_file.name}])
    zip_file.add = MagicMock()
    result = handler.export_user_file(user_file, files_zip=zip_file, storage=storage)

    assert result == {"name": user_file.name, "original_name": original_name}
    zip_file.add.assert_not_called()


@pytest.mark.django_db
def test_export_user_file_doesnt_add_if_file_in_cache(
    data_fixture,
    tmpdir,
):
    """Ensure the file isn't added to files_zip if it is in the cache."""

    user = data_fixture.create_user()
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")

    # Create an image user file
    image = Image.new("RGB", (100, 140), color="red")
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")

    original_name = "mock_image.png"
    handler = UserFileHandler()
    user_file = handler.upload_user_file(
        user, original_name, image_bytes, storage=storage
    )

    cache = {f"user_file_{user_file.name}": True}
    files_buffer = BytesIO()
    storage.open = MagicMock()
    with ZipFile(files_buffer, "a", ZIP_DEFLATED, False) as files_zip:
        result = handler.export_user_file(
            user_file, files_zip=files_zip, storage=storage, cache=cache
        )

    assert result == {"name": user_file.name, "original_name": original_name}
    storage.open.assert_not_called()


@pytest.mark.django_db
def test_export_user_file_adds_if_files_zip_is_empty_and_not_in_cache(
    data_fixture,
    tmpdir,
):
    """Ensure the file is added to files_zip."""

    user = data_fixture.create_user()
    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")

    # Create an image user file
    image = Image.new("RGB", (100, 140), color="red")
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")

    original_name = "mock_image.png"
    handler = UserFileHandler()
    user_file = handler.upload_user_file(
        user, original_name, image_bytes, storage=storage
    )

    files_buffer = BytesIO()
    cache = {}

    zip_file = ExportZipFile(
        compress_level=settings.BASEROW_DEFAULT_ZIP_COMPRESS_LEVEL,
        compress_type=zipstream.ZIP_DEFLATED,
    )
    result = handler.export_user_file(
        user_file, files_zip=zip_file, storage=storage, cache=cache
    )

    for chunk in zip_file:
        files_buffer.write(chunk)

    file_names_in_zip = [item["name"] for item in zip_file.info_list()]

    assert result == {"name": user_file.name, "original_name": original_name}
    assert user_file.name in file_names_in_zip
    assert cache[f"user_file_{user_file.name}"] is True


def test_import_user_file_returns_none_if_user_file_is_empty():
    """
    Ensure that None is returned if the serialized_user_file argument is an
    empty dict.
    """

    handler = UserFileHandler()

    result = handler.import_user_file({})

    assert result is None


def test_import_user_file_returns_user_file_from_handler_if_files_zip_is_none():
    """
    Ensure that if either files_zip or storage are None, the user_file is
    returned via UserFileHandler.
    """

    handler = UserFileHandler()
    mock_user_file = MagicMock()
    handler.get_user_file_by_name = MagicMock(return_value=mock_user_file)
    serialized_user_file = {"name": "foo", "original_name": "bar"}

    result = handler.import_user_file(
        serialized_user_file,
        files_zip=None,
        storage=None,
    )

    assert result is mock_user_file
    handler.get_user_file_by_name.assert_called_once_with(serialized_user_file["name"])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name,original_name",
    [
        (None, None),
        (None, "bar"),
        ("foo", None),
    ],
)
def test_import_user_file_returns_none_if_name_or_original_name_are_empty(
    tmpdir,
    name,
    original_name,
):
    """
    Ensure that if either name or original_name are falsey, None is returned.
    """

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()
    mock_user_file = MagicMock()
    handler.get_user_file_by_name = MagicMock(return_value=mock_user_file)
    handler.upload_user_file = MagicMock()
    serialized_user_file = {"name": name, "original_name": original_name}

    files_buffer = BytesIO()
    with ZipFile(files_buffer, "a", ZIP_DEFLATED, False) as files_zip:
        result = handler.import_user_file(
            serialized_user_file,
            files_zip=files_zip,
            storage=storage,
        )

    assert result is None
    handler.get_user_file_by_name.assert_not_called()
    handler.upload_user_file.assert_not_called()


def test_import_user_file_returns_user_file_from_files_zip(tmpdir):
    """Ensure UserFile is returned via the files_zip."""

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://localhost")
    handler = UserFileHandler()
    mock_user_file = MagicMock()
    handler.get_user_file_by_name = MagicMock()
    handler.upload_user_file = MagicMock(return_value=mock_user_file)
    name = "foo"
    original_name = "bar"
    serialized_user_file = {"name": name, "original_name": original_name}

    files_buffer = BytesIO()
    mock_handle = MagicMock()
    with ZipFile(files_buffer, "a", ZIP_DEFLATED, False) as files_zip:
        # Populate the files_zip with a file, which we expect import_user_file()
        # to later extract.
        files_zip.writestr(name, "")

        # Mock the "as stream:" in import_user_file()
        files_zip.open = MagicMock()
        files_zip.open.return_value.__enter__.return_value = mock_handle

        result = handler.import_user_file(
            serialized_user_file,
            files_zip=files_zip,
            storage=storage,
        )

    assert result is mock_user_file
    handler.get_user_file_by_name.assert_not_called()
    handler.upload_user_file.assert_called_once_with(
        None,
        original_name,
        mock_handle,
        storage=storage,
    )
