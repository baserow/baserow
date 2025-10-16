from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

import pytest
from PIL import Image
from rest_framework.status import HTTP_200_OK

from baserow.api.user_files.serializers import UserFileSerializer
from baserow.contrib.builder.elements.element_types import ImageElementType
from baserow.contrib.builder.elements.models import ImageElement
from baserow.core.user_files.handler import UserFileHandler


@pytest.mark.django_db
def test_get_image_element(api_client, data_fixture, tmpdir):
    user, token = data_fixture.create_user_and_token()

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://locaslhost")
    image = Image.new("RGB", (100, 140), color="red")
    file = SimpleUploadedFile("test.png", b"")
    image.save(file, format="PNG")

    user_file = UserFileHandler().upload_user_file(user, "test", file, storage=storage)

    image_element = data_fixture.create_builder_image_element(
        user, image_file=user_file
    )

    url = reverse("api:builder:element:list", kwargs={"page_id": image_element.page.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 200

    [image_element_returned] = response.json()

    assert image_element_returned["image_file"]["name"] == image_element.image_file.name


@pytest.mark.django_db
def test_create_image_element(api_client, data_fixture, tmpdir):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://locaslhost")
    image = Image.new("RGB", (100, 140), color="red")
    file = SimpleUploadedFile("test.png", b"")
    image.save(file, format="PNG")

    user_file = UserFileHandler().upload_user_file(user, "test", file, storage=storage)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {
            "type": ImageElementType.type,
            "image_file": UserFileSerializer(user_file).data,
            "image_source_type": ImageElement.IMAGE_SOURCE_TYPES.UPLOAD,
            "alt_text": "'test'",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == 200
    assert response_json["image_file"]["name"] == user_file.name
    assert response_json["image_source_type"] == ImageElement.IMAGE_SOURCE_TYPES.UPLOAD
    assert response_json["alt_text"]["formula"] == "'test'"


@pytest.mark.django_db
def test_create_cant_set_image_of_incorrect_type(api_client, data_fixture, tmpdir):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://locaslhost")
    file = SimpleUploadedFile("test.txt", b"hello there")

    user_file = UserFileHandler().upload_user_file(user, "test", file, storage=storage)

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {
            "type": ImageElementType.type,
            "image_file": UserFileSerializer(user_file).data,
            "image_source_type": ImageElement.IMAGE_SOURCE_TYPES.UPLOAD,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"]["image_file"][0]["code"] == "invalid"


@pytest.mark.django_db
def test_cant_set_an_image_that_does_not_exist(api_client, data_fixture, tmpdir):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://locaslhost")
    file = SimpleUploadedFile("test.txt", b"hello there")

    user_file = UserFileHandler().upload_user_file(user, "test", file, storage=storage)

    user_file.id = 99999

    url = reverse("api:builder:element:list", kwargs={"page_id": page.id})
    response = api_client.post(
        url,
        {
            "type": ImageElementType.type,
            "image_file": UserFileSerializer(user_file).data,
            "image_source_type": ImageElement.IMAGE_SOURCE_TYPES.UPLOAD,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == 400
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert response.json()["detail"]["image_file"][0]["code"] == "invalid"


@pytest.mark.django_db
def test_image_file_is_not_deleted_when_not_explicitly_set(
    api_client, data_fixture, tmpdir
):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://locaslhost")

    image = Image.new("RGB", (100, 140), color="red")
    file = SimpleUploadedFile("test.png", b"")
    image.save(file, format="PNG")

    user_file = UserFileHandler().upload_user_file(user, "test", file, storage=storage)

    element = data_fixture.create_builder_image_element(
        user, image_file=user_file, page=page
    )

    assert element.image_file is not None

    url = reverse("api:builder:element:item", kwargs={"element_id": element.id})
    response = api_client.patch(
        url,
        {"alt_text": "'something'"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["image_file"] is not None

    element.refresh_from_db()

    assert element.image_file is not None


@pytest.mark.django_db
def test_image_file_can_be_deleted(api_client, data_fixture, tmpdir):
    user, token = data_fixture.create_user_and_token()
    page = data_fixture.create_builder_page(user=user)

    storage = FileSystemStorage(location=str(tmpdir), base_url="http://locaslhost")

    image = Image.new("RGB", (100, 140), color="red")
    file = SimpleUploadedFile("test.png", b"")
    image.save(file, format="PNG")

    user_file = UserFileHandler().upload_user_file(user, "test", file, storage=storage)

    element = data_fixture.create_builder_image_element(
        user, image_file=user_file, page=page
    )

    assert element.image_file is not None

    url = reverse("api:builder:element:item", kwargs={"element_id": element.id})
    response = api_client.patch(
        url,
        {"image_file": None},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["image_file"] is None

    element.refresh_from_db()

    assert element.image_file is None
