from django.test.utils import override_settings
from django.urls import reverse

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.builder.domains.domain_types import CustomDomainType, SubDomainType


@pytest.mark.django_db
def test_get_domains(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    domain_one = data_fixture.create_builder_custom_domain(builder=builder)
    domain_two = data_fixture.create_builder_custom_domain(builder=builder)

    url = reverse(
        "api:builder:builder_id:domains:list", kwargs={"builder_id": builder.id}
    )

    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    domain_ids = [domain["id"] for domain in response_json]
    assert response.status_code == HTTP_200_OK
    assert domain_one.id in domain_ids
    assert domain_two.id in domain_ids


@pytest.mark.django_db
def test_get_domains_builder_doesnt_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:builder:builder_id:domains:list", kwargs={"builder_id": 9999})

    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_create_domain(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)

    domain_name = "test.com"

    url = reverse(
        "api:builder:builder_id:domains:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {"type": CustomDomainType.type, "domain_name": domain_name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["domain_name"] == domain_name


@pytest.mark.django_db
def test_create_domain_user_not_in_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application()

    url = reverse(
        "api:builder:builder_id:domains:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {"type": CustomDomainType.type, "domain_name": "test.com"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_create_domain_application_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:builder:builder_id:domains:list", kwargs={"builder_id": 9999})
    response = api_client.post(
        url,
        {"type": CustomDomainType.type, "domain_name": "test.com"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_create_domain_domain_already_exists(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)

    domain_name = "test.com"

    data_fixture.create_builder_custom_domain(builder=builder, domain_name=domain_name)

    url = reverse(
        "api:builder:builder_id:domains:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {"type": CustomDomainType.type, "domain_name": domain_name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_DOMAIN_NAME_NOT_UNIQUE"


@pytest.mark.django_db
def test_create_domain_invalid_domain_name(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)

    domain_name = "test"

    url = reverse(
        "api:builder:builder_id:domains:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {"type": CustomDomainType.type, "domain_name": domain_name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"


@pytest.mark.django_db
@override_settings(BASEROW_BUILDER_DOMAINS=["test.com"])
def test_create_invalid_sub_domain(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)

    domain_name = "hello.nottest.com"

    url = reverse(
        "api:builder:builder_id:domains:list", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {"type": SubDomainType.type, "domain_name": domain_name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_SUB_DOMAIN_HAS_INVALID_DOMAIN_NAME"
    assert "test.com" in response_json["detail"]
    assert "nottest.com" in response_json["detail"]


@pytest.mark.django_db
def test_update_domain(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    domain = data_fixture.create_builder_custom_domain(
        builder=builder, domain_name="something.com"
    )

    url = reverse("api:builder:domains:item", kwargs={"domain_id": domain.id})
    response = api_client.patch(
        url,
        {"domain_name": "test.com"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["domain_name"] == "test.com"


@pytest.mark.django_db
def test_update_domain_domain_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:builder:domains:item", kwargs={"domain_id": 9999})
    response = api_client.patch(
        url,
        {"domain_name": "test.com"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DOMAIN_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_update_domain_with_same_name(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    domain = data_fixture.create_builder_custom_domain(user=user)

    url = reverse("api:builder:domains:item", kwargs={"domain_id": domain.id})
    response = api_client.patch(
        url,
        {"domain_name": domain.domain_name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_update_domain_name_uniqueness(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    domain = data_fixture.create_builder_custom_domain(user=user)
    domain_2 = data_fixture.create_builder_custom_domain(user=user)

    url = reverse("api:builder:domains:item", kwargs={"domain_id": domain.id})
    response = api_client.patch(
        url,
        {"domain_name": domain_2.domain_name},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST, response.json()


@pytest.mark.django_db
def test_order_domains(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    domain_one = data_fixture.create_builder_custom_domain(builder=builder, order=1)
    domain_two = data_fixture.create_builder_custom_domain(builder=builder, order=2)

    url = reverse(
        "api:builder:builder_id:domains:order", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {"domain_ids": [domain_two.id, domain_one.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_order_domains_user_not_in_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application()
    domain_one = data_fixture.create_builder_custom_domain(builder=builder, order=1)
    domain_two = data_fixture.create_builder_custom_domain(builder=builder, order=2)

    url = reverse(
        "api:builder:builder_id:domains:order", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {"domain_ids": [domain_two.id, domain_one.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_order_domains_domain_not_in_builder(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    domain_one = data_fixture.create_builder_custom_domain(builder=builder, order=1)
    domain_two = data_fixture.create_builder_custom_domain(order=2)

    url = reverse(
        "api:builder:builder_id:domains:order", kwargs={"builder_id": builder.id}
    )
    response = api_client.post(
        url,
        {"domain_ids": [domain_two.id, domain_one.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_DOMAIN_NOT_IN_BUILDER"


@pytest.mark.django_db
def test_order_domains_application_does_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    domain_one = data_fixture.create_builder_custom_domain(builder=builder, order=1)
    domain_two = data_fixture.create_builder_custom_domain(builder=builder, order=2)

    url = reverse("api:builder:builder_id:domains:order", kwargs={"builder_id": 99999})
    response = api_client.post(
        url,
        {"domain_ids": [domain_two.id, domain_one.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_APPLICATION_DOES_NOT_EXIST"


@pytest.mark.django_db
def test_delete_domain(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    domain = data_fixture.create_builder_custom_domain(builder=builder, order=1)

    url = reverse("api:builder:domains:item", kwargs={"domain_id": domain.id})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_delete_domain_user_not_in_workspace(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application()
    domain = data_fixture.create_builder_custom_domain(builder=builder, order=1)

    url = reverse("api:builder:domains:item", kwargs={"domain_id": domain.id})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_delete_domain_domain_not_exist(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()

    url = reverse("api:builder:domains:item", kwargs={"domain_id": 99999})
    response = api_client.delete(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_DOMAIN_DOES_NOT_EXIST"
