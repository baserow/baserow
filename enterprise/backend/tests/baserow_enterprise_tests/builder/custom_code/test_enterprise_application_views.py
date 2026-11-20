from django.shortcuts import reverse
from django.test import override_settings

import pytest
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
    HTTP_406_NOT_ACCEPTABLE,
)

from baserow.api.applications.serializers import (
    PolymorphicApplicationResponseSerializer,
    PublicPolymorphicApplicationResponseSerializer,
)
from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.preview import (
    BuilderPreviewGrantHandler,
    get_builder_preview_cookie_name,
)
from baserow.core.registries import ImportExportConfig
from baserow_enterprise.builder.custom_code.models import BuilderCustomScript

HEAD_HTML = '\n  <meta name="description" content="Example">\n<script>demo()</script>  '


def authenticate_builder_preview(api_client, builder, user):
    token = BuilderPreviewGrantHandler().create_grant(builder, user)
    _, session_token = BuilderPreviewGrantHandler().exchange_token(token)
    api_client.cookies[get_builder_preview_cookie_name()] = session_token


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
    application.custom_code.html = HEAD_HTML
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
    assert response_json["head_html"] == HEAD_HTML


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
            "head_html": HEAD_HTML,
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
    assert builder.custom_code.html == HEAD_HTML


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
            "head_html": HEAD_HTML,
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
    assert builder.custom_code.html == ""


@pytest.mark.django_db
def test_get_enterprise_builder_custom_code_preview(
    enable_enterprise, api_client, data_fixture
):
    user, _token = data_fixture.create_user_and_token(
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

    url = reverse(
        "api:enterprise:builder_preview_custom_code:js",
        kwargs={"builder_id": builder.id},
    )
    authenticate_builder_preview(api_client, builder, user)

    response = api_client.get(
        url,
    )
    assert response.status_code == HTTP_200_OK
    assert response.content == b"testJs"

    url = reverse(
        "api:enterprise:builder_preview_custom_code:css",
        kwargs={"builder_id": builder.id},
    )

    response = api_client.get(
        url,
    )
    assert response.status_code == HTTP_200_OK
    assert response.content == b"testCss"


@pytest.mark.django_db
@override_settings(FRONTEND_COOKIE_PREFIX="baserow_3010_")
def test_get_enterprise_builder_custom_code_preview_with_prefixed_session_cookie(
    enable_enterprise, api_client, data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    builder.custom_code.css = "testCss"
    builder.custom_code.save()

    url = reverse(
        "api:enterprise:builder_preview_custom_code:css",
        kwargs={"builder_id": builder.id},
    )
    authenticate_builder_preview(api_client, builder, user)
    assert "baserow_3010_baserow_builder_preview" in api_client.cookies

    response = api_client.get(
        url,
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

    url = reverse(
        "api:enterprise:builder_preview_custom_code:js",
        kwargs={"builder_id": builder.id},
    )

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
@pytest.mark.parametrize("code_type", ["js", "html"])
def test_get_enterprise_builder_custom_code_public_no_licence(
    api_client, data_fixture, code_type
):
    workspace = data_fixture.create_workspace()
    builder = data_fixture.create_builder_application(
        workspace=workspace,
        order=1,
    )
    builder.custom_code.css = "testCss"
    builder.custom_code.js = "testJs"
    builder.custom_code.html = HEAD_HTML
    builder.custom_code.save()

    domain = data_fixture.create_builder_custom_domain(builder=builder)
    domain = DomainHandler().publish(domain)
    published_builder = domain.published_to

    url = reverse(
        f"api:enterprise:custom_code:public_{code_type}",
        kwargs={"builder_id": published_builder.id},
    )

    response = api_client.get(
        url,
    )
    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_get_enterprise_builder_custom_code_public_application_not_found(
    enable_enterprise, api_client, data_fixture
):
    url = reverse(
        "api:enterprise:custom_code:public_js",
        kwargs={"builder_id": 123456},
    )

    response = api_client.get(url)

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
@pytest.mark.parametrize("mode", ["preview", "public"])
@pytest.mark.parametrize("code_type", ["js", "css", "html"])
def test_untrusted_custom_code_requires_explicit_consent(
    enable_enterprise, api_client, data_fixture, settings, mode, code_type
):
    """Preview and public asset URLs refuse untrusted code, retaining it for review."""

    settings.PUBLIC_WEB_FRONTEND_HOSTNAME = "editor.example.org"
    settings.BUILDER_PREVIEW_HOSTNAME = "preview.example.org"

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        workspace=workspace, untrusted_content=True
    )
    builder.custom_code.js = "alert(1)"
    builder.custom_code.css = "body { color: red }"
    builder.custom_code.html = HEAD_HTML
    builder.custom_code.save()
    if mode == "preview":
        authenticate_builder_preview(api_client, builder, user)
        route = f"api:enterprise:builder_preview_custom_code:{code_type}"
    else:
        builder.untrusted_content = False
        builder.save(update_fields=["untrusted_content"])
        domain = data_fixture.create_builder_custom_domain(builder=builder)
        builder = DomainHandler().publish(domain).published_to
        # Public asset endpoints also protect existing copies marked untrusted.
        builder.untrusted_content = True
        builder.save(update_fields=["untrusted_content"])
        route = f"api:enterprise:custom_code:public_{code_type}"

    assert (
        PublicPolymorphicApplicationResponseSerializer(builder).data[
            "untrusted_content"
        ]
        is True
    )
    url = reverse(route, kwargs={"builder_id": builder.id})
    response = api_client.get(url)
    assert response.status_code == HTTP_404_NOT_FOUND
    if code_type == "html":
        assert response["Content-Type"] == "application/json"

    builder.untrusted_content = False
    builder.save(update_fields=["untrusted_content"])
    response = api_client.get(url)
    assert response.status_code == HTTP_200_OK
    if code_type == "html":
        assert response.json() == {"html": HEAD_HTML}
    else:
        assert response.content.decode() == (
            "alert(1)" if code_type == "js" else "body { color: red }"
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "content", ["empty", "css", "js", "html", "script", "stylesheet", "empty_script"]
)
def test_only_custom_code_content_requires_trust_on_import(
    enable_enterprise, data_fixture, content
):
    """Detect retained code and external assets, including files claiming to be safe."""

    builder = data_fixture.create_builder_application()
    if content in ["css", "js", "html"]:
        setattr(builder.custom_code, content, "custom content")
        builder.custom_code.save()
    if content in ["script", "stylesheet", "empty_script"]:
        BuilderCustomScript.objects.create(
            builder=builder,
            order=0,
            type="stylesheet" if content == "stylesheet" else "javascript",
            url="https://example.com/asset" if content != "empty_script" else "",
        )
    config = ImportExportConfig(include_permission_data=False)
    application_type = builder.get_type()
    serialized = application_type.export_serialized(builder, config)
    expected = content not in ["empty", "empty_script"]
    assert "untrusted_content" not in serialized
    serialized["untrusted_content"] = False

    imported = application_type.import_serialized(
        builder.workspace, serialized, config, {}
    )
    imported.refresh_from_db()
    assert imported.untrusted_content is expected
    assert imported.custom_code.css == builder.custom_code.css
    assert imported.custom_code.js == builder.custom_code.js
    assert imported.custom_code.html == builder.custom_code.html
    assert list(imported.scripts.values_list("url", flat=True)) == list(
        builder.scripts.values_list("url", flat=True)
    )

    expected_types = {
        "empty": [],
        "empty_script": [],
        "css": ["custom_css"],
        "js": ["custom_js"],
        "html": ["custom_html"],
        "script": ["external_script"],
        "stylesheet": ["external_stylesheet"],
    }
    assert [item["type"] for item in imported.import_report] == expected_types[content]
    if content in ["script", "stylesheet"]:
        assert imported.import_report[0]["id"] == imported.scripts.get().id
        assert imported.import_report[0]["url"] == "https://example.com/asset"
    assert (
        PolymorphicApplicationResponseSerializer(imported).data["import_report"]
        == imported.import_report
    )
    assert (
        "import_report"
        not in PublicPolymorphicApplicationResponseSerializer(imported).data
    )


@pytest.mark.django_db
@pytest.mark.parametrize("html", [HEAD_HTML, 12])
def test_update_builder_head_html_independently(
    enable_enterprise, api_client, data_fixture, html
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    code = builder.custom_code
    code.css = "old CSS"
    code.js = "old JS"
    code.save()
    url = reverse("api:applications:item", args=[builder.id])
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}

    response = api_client.patch(url, {"head_html": html}, format="json", **auth)
    assert response.status_code == HTTP_200_OK
    assert response.json()["custom_code"] == {"css": "old CSS", "js": "old JS"}
    assert response.json()["head_html"] == str(html)

    # Old forms can submit a stale nested HTML value while editing CSS.
    response = api_client.patch(
        url,
        {"custom_code": {"css": "new CSS", "html": "stale"}},
        format="json",
        **auth,
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["custom_code"] == {"css": "new CSS", "js": ""}
    assert response.json()["head_html"] == str(html)

    response = api_client.patch(url, {"head_html": ""}, format="json", **auth)
    assert response.status_code == HTTP_200_OK
    assert response.json()["head_html"] == ""
    code.refresh_from_db()
    assert code.html == ""
    assert code.css == "new CSS"


@pytest.mark.django_db
@pytest.mark.parametrize("invalid", [None, False, [], {}])
def test_update_builder_head_html_rejects_non_text(
    enable_enterprise, api_client, data_fixture, invalid
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    code = builder.custom_code
    code.html = HEAD_HTML
    code.save(update_fields=["html"])
    response = api_client.patch(
        reverse("api:applications:item", kwargs={"application_id": builder.id}),
        {"head_html": invalid},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["detail"]["head_html"]
    code.refresh_from_db()
    assert code.html == HEAD_HTML


@pytest.mark.django_db
def test_public_builder_head_html_serves_only_the_published_snapshot(
    enable_enterprise, api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    code = builder.custom_code
    code.html = HEAD_HTML
    code.save(update_fields=["html"])
    draft_url = reverse("api:enterprise:custom_code:public_html", args=[builder.id])
    response = api_client.get(draft_url, HTTP_AUTHORIZATION=f"JWT {token}")
    assert response.status_code == HTTP_404_NOT_FOUND

    domain = data_fixture.create_builder_custom_domain(builder=builder)
    published = DomainHandler().publish(domain).published_to
    published_url = reverse(
        "api:enterprise:custom_code:public_html", args=[published.id]
    )
    code.html = "<style>body { margin: 0; }</style>"
    code.save(update_fields=["html"])
    response = api_client.get(published_url)
    assert response.status_code == HTTP_200_OK
    assert response["Content-Type"] == "application/json"
    assert response["Cache-Control"] == "no-store"
    assert response.json() == {"html": HEAD_HTML}
    assert (
        api_client.get(published_url, HTTP_ACCEPT="text/html").status_code
        == HTTP_406_NOT_ACCEPTABLE
    )

    public_builder_url = reverse(
        "api:builder:domains:get_builder_by_domain_name", args=[domain.domain_name]
    )
    response = api_client.get(public_builder_url)
    assert response.status_code == HTTP_200_OK
    assert response.json()["custom_code"] == {"css": "", "js": ""}
    assert response.json()["has_head_html"] is True
    assert "head_html" not in response.json()

    republished = DomainHandler().publish(domain).published_to
    response = api_client.get(
        reverse("api:enterprise:custom_code:public_html", args=[republished.id])
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == {"html": code.html}


@pytest.mark.django_db
def test_preview_builder_head_html_requires_a_scoped_session(
    enable_enterprise, api_client, data_fixture, settings
):
    settings.PUBLIC_WEB_FRONTEND_HOSTNAME = "editor.example.org"
    settings.BUILDER_PREVIEW_HOSTNAME = "preview.example.org"
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    other_builder = data_fixture.create_builder_application(user=user)
    code = builder.custom_code
    code.html = HEAD_HTML
    code.save(update_fields=["html"])
    url = reverse("api:enterprise:builder_preview_custom_code:html", args=[builder.id])

    assert api_client.get(url).status_code == HTTP_401_UNAUTHORIZED
    authenticate_builder_preview(api_client, other_builder, user)
    assert api_client.get(url).status_code == HTTP_401_UNAUTHORIZED

    authenticate_builder_preview(api_client, builder, user)
    response = api_client.get(url)
    assert response.status_code == HTTP_200_OK
    assert response.json() == {"html": HEAD_HTML}
    assert response["Cache-Control"] == "no-store"

    response = api_client.get(reverse("api:builder:preview:current", args=[builder.id]))
    assert response.status_code == HTTP_200_OK
    assert response.json()["custom_code"] == {"css": "", "js": ""}
    assert response.json()["has_head_html"] is True
    assert "head_html" not in response.json()

    settings.BUILDER_PREVIEW_HOSTNAME = settings.PUBLIC_WEB_FRONTEND_HOSTNAME
    assert api_client.get(url).status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_builder_head_html_import_accepts_old_exports_and_preserves_duplicate(
    enable_enterprise, data_fixture
):
    builder = data_fixture.create_builder_application()
    code = builder.custom_code
    code.html = HEAD_HTML
    code.css = "old CSS"
    code.save(update_fields=["html", "css"])
    application_type = builder.get_type()
    config = ImportExportConfig(include_permission_data=False, is_duplicate=True)
    exported = application_type.export_serialized(builder, config)
    assert exported["custom_code"]["html"] == HEAD_HTML
    duplicate = application_type.import_serialized(
        builder.workspace, exported, config, {}
    )
    assert duplicate.custom_code.html == HEAD_HTML
    assert not duplicate.untrusted_content

    config = ImportExportConfig(include_permission_data=False)
    exported = application_type.export_serialized(builder, config)
    del exported["custom_code"]["html"]
    imported = application_type.import_serialized(
        builder.workspace, exported, config, {}
    )
    assert imported.custom_code.html == ""
    assert imported.custom_code.css == "old CSS"
    assert imported.import_report == [{"type": "custom_css"}]
