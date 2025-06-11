from django.shortcuts import reverse

import pytest
from rest_framework.status import HTTP_200_OK, HTTP_401_UNAUTHORIZED, HTTP_404_NOT_FOUND

from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.contrib.builder.models import Builder
from baserow_enterprise.builder.custom_code.models import BuilderCustomScript


@pytest.mark.django_db
def test_get_enterprise_builder_application(
    enable_enterprise, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    application = data_fixture.create_builder_application(
        workspace=workspace,
        order=1,
    )
    application.custom_code.css = "testCss"
    application.custom_code.js = "testJs"
    application.custom_code.save()

    custom_script = BuilderCustomScript.objects.create(builder=application, order=1)

    url = reverse("api:applications:item", kwargs={"application_id": application.id})

    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    assert response_json["type"] == "builder"

    assert response_json["scripts"] == [
        {
            "crossorigin": "",
            "id": custom_script.id,
            "load_type": "",
            "type": "javascript",
            "url": "",
        },
    ]
    assert response_json["custom_code"] == {"css": "testCss", "js": "testJs"}


@pytest.mark.django_db
def test_create_enterprise_builder_application(
    enable_enterprise, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse("api:applications:list", kwargs={"workspace_id": workspace.id}),
        {
            "name": "Test 1",
            "type": "builder",
            "scripts": [
                {
                    "crossorigin": "",
                    "load_type": "",
                    "type": "javascript",
                    "url": "http://test.com",
                },
            ],
            "custom_code": {"css": "testCss", "js": "testJs"},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "builder"

    builder = Builder.objects.filter()[0]

    assert builder.scripts.count() == 1
    assert builder.scripts.first().url == "http://test.com"
    assert builder.custom_code.css == "testCss"
    assert builder.custom_code.js == "testJs"


@pytest.mark.django_db
def test_create_enterprise_builder_application_no_licence(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = api_client.post(
        reverse("api:applications:list", kwargs={"workspace_id": workspace.id}),
        {
            "name": "Test 1",
            "type": "builder",
            "scripts": [
                {
                    "crossorigin": "",
                    "load_type": "",
                    "type": "javascript",
                    "url": "http://test.com",
                },
            ],
            "custom_code": {"css": "testCss", "js": "testJs"},
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert response_json["type"] == "builder"

    builder = Builder.objects.filter()[0]

    assert builder.scripts.count() == 0
    assert builder.custom_code.css == ""
    assert builder.custom_code.js == ""


@pytest.mark.django_db
def test_get_enterprise_builder_custom_code_preview(
    enable_enterprise, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token(
        email="test@test.nl", password="password", first_name="Test1"
    )
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        workspace=workspace,
        order=1,
    )
    builder.custom_code.css = "testCss"
    builder.custom_code.js = "testJs"
    builder.custom_code.save()

    url = reverse("api:enterprise:custom_code:js", kwargs={"builder_id": builder.id})

    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.content == b"testJs"

    url = reverse("api:enterprise:custom_code:css", kwargs={"builder_id": builder.id})

    response = api_client.get(
        url,
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.content == b"testCss"


@pytest.mark.django_db
def test_get_enterprise_builder_custom_code_preview_no_user(
    enable_enterprise, api_client, data_fixture
):
    workspace = data_fixture.create_workspace()
    builder = data_fixture.create_builder_application(
        workspace=workspace,
        order=1,
    )
    builder.custom_code.css = "testCss"
    builder.custom_code.js = "testJs"
    builder.custom_code.save()

    url = reverse("api:enterprise:custom_code:js", kwargs={"builder_id": builder.id})

    response = api_client.get(
        url,
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_get_enterprise_builder_custom_code_public_unpublished(
    enable_enterprise, api_client, data_fixture
):
    workspace = data_fixture.create_workspace()
    builder = data_fixture.create_builder_application(
        workspace=workspace,
        order=1,
    )
    builder.custom_code.css = "testCss"
    builder.custom_code.js = "testJs"
    builder.custom_code.save()

    url = reverse(
        "api:enterprise:custom_code:public_js", kwargs={"builder_id": builder.id}
    )

    response = api_client.get(
        url,
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_get_enterprise_builder_custom_code_public(
    enable_enterprise, api_client, data_fixture
):
    workspace = data_fixture.create_workspace()
    builder = data_fixture.create_builder_application(
        workspace=workspace,
        order=1,
    )
    builder.custom_code.css = "testCss"
    builder.custom_code.js = "testJs"
    builder.custom_code.save()

    domain = data_fixture.create_builder_custom_domain(builder=builder)
    domain = DomainHandler().publish(domain)
    published_builder = domain.published_to

    url = reverse(
        "api:enterprise:custom_code:public_js",
        kwargs={"builder_id": published_builder.id},
    )

    response = api_client.get(
        url,
    )
    assert response.status_code == HTTP_200_OK
    assert response.content == b"testJs"

    url = reverse(
        "api:enterprise:custom_code:public_css",
        kwargs={"builder_id": published_builder.id},
    )

    response = api_client.get(
        url,
    )
    assert response.status_code == HTTP_200_OK
    assert response.content == b"testCss"


@pytest.mark.django_db
def test_get_enterprise_builder_custom_code_public_no_licence(api_client, data_fixture):
    workspace = data_fixture.create_workspace()
    builder = data_fixture.create_builder_application(
        workspace=workspace,
        order=1,
    )
    builder.custom_code.css = "testCss"
    builder.custom_code.js = "testJs"
    builder.custom_code.save()

    domain = data_fixture.create_builder_custom_domain(builder=builder)
    domain = DomainHandler().publish(domain)
    published_builder = domain.published_to

    url = reverse(
        "api:enterprise:custom_code:public_js",
        kwargs={"builder_id": published_builder.id},
    )

    response = api_client.get(
        url,
    )
    assert response.status_code == HTTP_404_NOT_FOUND
