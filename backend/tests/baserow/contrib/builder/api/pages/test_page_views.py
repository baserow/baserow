from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)


@pytest.mark.django_db
def test_create_page(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)

    name = "test"
    path = "/test/:id/"
    path_params = [{"name": "id", "type": "text"}]

    url = reverse(
        "api:builder:builder_id:pages:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {"name": name, "path": path, "path_params": path_params},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["name"] == name
    assert response_json["path"] == path
    assert response_json["path_params"] == path_params


@pytest.mark.django_db
def test_create_page_user_not_in_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application()

    url = reverse(
        "api:builder:builder_id:pages:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {"name": "test", "path": "/test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_create_page_application_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:builder:builder_id:pages:list", kwargs={"builder_id": 9999})
    response = api_client.post(
        url,
        {"name": "test", "path": "/test"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_create_page_invalid_page_path(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)

    url = reverse(
        "api:builder:builder_id:pages:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {"name": "test", "path": "path with spaces"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_create_page_invalid_page_path_param(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)

    url = reverse(
        "api:builder:builder_id:pages:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {
            "name": "test",
            "path": "/test/:id",
            "path_params": [{"name": "id", "type": "unsupported"}],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_create_page_invalid_page_path_param_key(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)

    url = reverse(
        "api:builder:builder_id:pages:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {
            "name": "test",
            "path": "/test/:id",
            "path_params": [{"name": "test", "test": "hello"}],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert "path_params" in response_json["detail"]


@pytest.mark.django_db
def test_create_page_invalid_page_path_param_semantics(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)

    url = reverse(
        "api:builder:builder_id:pages:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {
            "name": "test",
            "path": "/test/:^test",
            "path_params": [{"name": "^test", "type": "text"}],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert "^test" in response_json["detail"]["path_params"][0]["name"][0]["error"]


@pytest.mark.django_db
def test_create_page_duplicate_page_name(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder, name="test")

    url = reverse(
        "api:builder:builder_id:pages:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {
            "name": page.name,
            "path": "/test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PAGE_NAME_NOT_UNIQUE"


@pytest.mark.django_db
def test_create_page_duplicate_page_path(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder, path="/test")

    url = reverse(
        "api:builder:builder_id:pages:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {
            "name": "test",
            "path": page.path,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PAGE_PATH_NOT_UNIQUE"


@pytest.mark.django_db
def test_create_page_duplicate_page_path_advanced(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    path_params = [
        {"name": "new", "type": "text"},
        {"name": "id", "type": "text"},
    ]
    data_fixture.create_builder_page(
        builder=builder, path="/test/:id/hello/:new", path_params=path_params
    )

    url = reverse(
        "api:builder:builder_id:pages:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {"name": "test", "path": "/test/:new/hello/:id", "path_params": path_params},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PAGE_PATH_NOT_UNIQUE"


@pytest.mark.django_db
def test_create_page_path_param_not_in_path(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)

    url = reverse(
        "api:builder:builder_id:pages:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {
            "name": "test",
            "path": "/test/test",
            "path_params": [{"name": "id", "type": "text"}],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PATH_PARAM_NOT_IN_PATH"


@pytest.mark.django_db
def test_create_page_path_param_not_defined(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)

    url = reverse(
        "api:builder:builder_id:pages:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {
            "name": "test",
            "path": "/test/:id",
            "path_params": [],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PATH_PARAM_NOT_DEFINED"


@pytest.mark.django_db
def test_create_page_incorrect_data_structure(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)

    url = reverse(
        "api:builder:builder_id:pages:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {
            "name": "test",
            "path": "/test/:id",
            "path_params": [{"test": "test"}],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
def test_create_page_duplicate_path_params_in_path(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)

    url = reverse(
        "api:builder:builder_id:pages:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {
            "name": "test",
            "path": "/test/:test/:test",
            "path_params": [{"name": "test", "type": "text"}],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_DUPLICATE_PATH_PARAMS_IN_PATH"


@pytest.mark.django_db
def test_update_page(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder, name="something")

    url = reverse("api:builder:pages:item", kwargs={"page_id": page.id})
    response = api_client.patch(
        url, {"name": "test"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["name"] == "test"


@pytest.mark.django_db
def test_update_page_page_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:builder:pages:item", kwargs={"page_id": 9999})
    response = api_client.patch(
        url, {"name": "test"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_PAGE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_update_shared_page(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    shared_page = builder.shared_page

    url = reverse("api:builder:pages:item", kwargs={"page_id": shared_page.id})
    response = api_client.patch(
        url, {"name": "test"}, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SHARED_PAGE_READ_ONLY"


@pytest.mark.django_db
def test_update_page_duplicate_page_name(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder, name="test")
    page_two = data_fixture.create_builder_page(builder=builder, name="test2")

    url = reverse("api:builder:pages:item", kwargs={"page_id": page_two.id})
    response = api_client.patch(
        url,
        {
            "name": page.name,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PAGE_NAME_NOT_UNIQUE"


@pytest.mark.django_db
def test_update_page_duplicate_page_path(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder, path="/test")
    page_two = data_fixture.create_builder_page(builder=builder, path="/test2")

    url = reverse("api:builder:pages:item", kwargs={"page_id": page_two.id})
    response = api_client.patch(
        url,
        {
            "path": page.path,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PAGE_PATH_NOT_UNIQUE"


@pytest.mark.django_db
def test_update_page_duplicate_page_path_advanced(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    path_params = [
        {"name": "id", "type": "text"},
        {"name": "new", "type": "text"},
    ]
    page = data_fixture.create_builder_page(
        builder=builder, path="/test/:id/hello/:new", path_params=path_params
    )
    page_two = data_fixture.create_builder_page(builder=builder, path="/test2")

    url = reverse("api:builder:pages:item", kwargs={"page_id": page_two.id})
    response = api_client.patch(
        url,
        {"path": "/test/:new/hello/:id", "path_params": path_params},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PAGE_PATH_NOT_UNIQUE"


@pytest.mark.django_db
def test_update_page_path_param_not_in_path_existing_path(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder, path="/test")

    url = reverse("api:builder:pages:item", kwargs={"page_id": page.id})
    response = api_client.patch(
        url,
        {"path_params": [{"name": "id", "type": "text"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PATH_PARAM_NOT_IN_PATH"


@pytest.mark.django_db
def test_update_page_path_param_not_in_path_new_path(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder, path="/test")

    url = reverse("api:builder:pages:item", kwargs={"page_id": page.id})
    response = api_client.patch(
        url,
        {"path": "/test/test", "path_params": [{"name": "id", "type": "text"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PATH_PARAM_NOT_IN_PATH"


@pytest.mark.django_db
def test_update_page_path_param_not_defined(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(
        builder=builder,
        path="/test",
    )

    url = reverse("api:builder:pages:item", kwargs={"page_id": page.id})
    response = api_client.patch(
        url,
        {
            "path": "/test/:test",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PATH_PARAM_NOT_DEFINED"


@pytest.mark.django_db
def test_update_page_invalid_page_path_param_semantics(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(
        builder=builder,
        path="/test",
    )

    url = reverse("api:builder:pages:item", kwargs={"page_id": page.id})
    response = api_client.patch(
        url,
        {"path": "/test/:^test", "path_params": [{"name": "^test", "type": "text"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_REQUEST_BODY_VALIDATION"
    assert "^test" in response_json["detail"]["path_params"][0]["name"][0]["error"]


@pytest.mark.django_db
def test_update_page_duplicate_path_params_in_path(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(
        builder=builder,
        path="/test",
    )

    url = reverse("api:builder:pages:item", kwargs={"page_id": page.id})
    response = api_client.patch(
        url,
        {
            "path": "/test/:test/:test",
            "path_params": [{"name": "test", "type": "text"}],
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_DUPLICATE_PATH_PARAMS_IN_PATH"


@pytest.mark.django_db
def test_order_pages(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page_one = data_fixture.create_builder_page(builder=builder, order=1)
    page_two = data_fixture.create_builder_page(builder=builder, order=2)

    url = reverse(
        "api:builder:builder_id:pages:order", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {"page_ids": [page_two.id, page_one.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_order_pages_user_not_in_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application()
    page_one = data_fixture.create_builder_page(builder=builder, order=1)
    page_two = data_fixture.create_builder_page(builder=builder, order=2)

    url = reverse(
        "api:builder:builder_id:pages:order", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {"page_ids": [page_two.id, page_one.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_order_pages_page_not_in_builder(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page_one = data_fixture.create_builder_page(builder=builder, order=1)
    page_two = data_fixture.create_builder_page(order=2)

    url = reverse(
        "api:builder:builder_id:pages:order", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {"page_ids": [page_two.id, page_one.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PAGE_NOT_IN_BUILDER"


@pytest.mark.django_db
def test_order_pages_shared_page(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    shared_page = builder.shared_page
    page_one = data_fixture.create_builder_page(builder=builder, order=1)

    url = reverse(
        "api:builder:builder_id:pages:order", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {"page_ids": [shared_page.id, page_one.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PAGE_NOT_IN_BUILDER"


@pytest.mark.django_db
def test_order_pages_application_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page_one = data_fixture.create_builder_page(builder=builder, order=1)
    page_two = data_fixture.create_builder_page(builder=builder, order=2)

    url = reverse("api:builder:builder_id:pages:order", kwargs={"builder_id": 99999})
    response = api_client.post(
        url,
        {"page_ids": [page_two.id, page_one.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_delete_page(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(builder=builder, order=1)

    url = reverse("api:builder:pages:item", kwargs={"page_id": page.id})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_delete_page_user_not_in_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application()
    page = data_fixture.create_builder_page(builder=builder, order=1)

    url = reverse("api:builder:pages:item", kwargs={"page_id": page.id})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_delete_page_page_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:builder:pages:item", kwargs={"page_id": 99999})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_PAGE_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_delete_shared_page(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    shared_page = builder.shared_page

    url = reverse("api:builder:pages:item", kwargs={"page_id": shared_page.id})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_SHARED_PAGE_READ_ONLY"


@pytest.mark.django_db
def test_rename_page_using_existing_page_name(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    page_1 = data_fixture.create_builder_page(builder=builder, order=1, name="test1")
    page_2 = data_fixture.create_builder_page(builder=builder, order=1, name="test2")

    url = reverse("api:builder:pages:item", kwargs={"page_id": page_2.id})
    response = api_client.patch(
        url,
        {
            "name": page_1.name,
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_PAGE_NAME_NOT_UNIQUE"
