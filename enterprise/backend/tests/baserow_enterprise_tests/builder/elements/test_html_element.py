from django.urls import reverse

import pytest

from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow_enterprise.builder.elements.element_types import HTMLElementType


@pytest.mark.django_db
def test_html_element_round_trip(
    api_client, enterprise_data_fixture, enable_enterprise
):
    user, token = enterprise_data_fixture.create_user_and_token()
    page = enterprise_data_fixture.create_builder_page(user=user)
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    url = reverse("api:builder:element:list", args=[page.id])
    html = (
        '  <section id="anchor" class="widget" data-lang="en" aria-label="Demo">'
        "<button onclick=\"this.textContent='Updated'\">Click</button>"
        '<script src="/widget.js"></script></section>  '
    )
    response = api_client.post(
        url, {"type": "html", "html": html}, format="json", **auth
    )
    assert response.status_code == 200, response.json()
    assert response.json()["html"] == html
    element_id = response.json()["id"]
    item = reverse("api:builder:element:item", args=[element_id])
    html += "<p>Updated</p>"
    assert (
        api_client.patch(item, {"html": html}, format="json", **auth).json()["html"]
        == html
    )
    assert api_client.get(url, **auth).json()[0]["html"] == html
    duplicate = reverse("api:builder:element:duplicate", args=[element_id])
    assert api_client.post(duplicate, **auth).json()["elements"][0]["html"] == html


@pytest.mark.django_db
def test_html_element_requires_permission_and_license(
    api_client, enterprise_data_fixture, enable_enterprise
):
    user, token = enterprise_data_fixture.create_user_and_token()
    _, outsider = enterprise_data_fixture.create_user_and_token()
    page = enterprise_data_fixture.create_builder_page(user=user)
    url = reverse("api:builder:element:list", args=[page.id])
    data = {"type": "html", "html": "<p>Only editors</p>"}
    denied = api_client.post(
        url, data, format="json", HTTP_AUTHORIZATION=f"JWT {outsider}"
    )
    assert denied.status_code in (401, 403)
    enterprise_data_fixture.delete_all_licenses()
    denied = api_client.post(
        url, data, format="json", HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert denied.json()["error"] == "ERROR_ELEMENT_TYPE_DEACTIVATED"


@pytest.mark.django_db
def test_html_import_requires_trust_before_publication(
    api_client, enterprise_data_fixture, enable_enterprise
):
    user, token = enterprise_data_fixture.create_user_and_token()
    builder = enterprise_data_fixture.create_builder_application(user=user)
    page = enterprise_data_fixture.create_builder_page(builder=builder)
    html = (
        '<div id="map" onclick="initialize()"></div><script src="/widget.js"></script>'
    )
    enterprise_data_fixture.create_builder_element(
        HTMLElementType, page=page, html=html
    )
    app_type = application_type_registry.get("builder")
    config = ImportExportConfig(include_permission_data=False)
    exported = app_type.export_serialized(builder, config)
    imported = app_type.import_serialized(builder.workspace, exported, config, {})
    imported.refresh_from_db()
    assert imported.untrusted_content
    imported_page = imported.visible_pages.get()
    auth = {"HTTP_AUTHORIZATION": f"JWT {token}"}
    elements = reverse("api:builder:element:list", args=[imported_page.id])
    (element,) = api_client.get(elements, **auth).json()
    assert element["html"] == html
    assert imported.import_report == [
        {
            "type": "html",
            "id": element["id"],
            "page_name": page.name,
            "page_id": imported_page.id,
        }
    ]
    domain = enterprise_data_fixture.create_builder_custom_domain(builder=imported)
    publish = reverse("api:builder:domains:publish", args=[domain.id])
    assert (
        api_client.post(publish, **auth).json()["error"]
        == "ERROR_UNTRUSTED_CONTENT_CANNOT_BE_PUBLISHED"
    )
    trust = reverse("api:applications:item", args=[imported.id])
    assert (
        api_client.patch(
            trust, {"untrusted_content": False}, format="json", **auth
        ).json()["untrusted_content"]
        is False
    )
    published = DomainHandler().publish(domain).published_to
    assert not published.untrusted_content
    public_elements = reverse(
        "api:builder:domains:list_elements", args=[published.visible_pages.get().id]
    )
    assert api_client.get(public_elements).json()[0]["html"] == html


@pytest.mark.django_db
@pytest.mark.parametrize("flag", ["is_duplicate", "is_publishing", "is_template"])
def test_internal_html_copies_preserve_trust(
    enterprise_data_fixture, enable_enterprise, flag
):
    builder = enterprise_data_fixture.create_builder_application()
    page = enterprise_data_fixture.create_builder_page(builder=builder)
    enterprise_data_fixture.create_builder_element(
        HTMLElementType, page=page, html="<p>Widget</p>"
    )
    config = ImportExportConfig(include_permission_data=False, **{flag: True})
    app_type = application_type_registry.get("builder")
    copy = app_type.import_serialized(
        builder.workspace, app_type.export_serialized(builder, config), config, {}
    )
    copy.refresh_from_db()
    assert not copy.untrusted_content
    assert copy.import_report[0]["type"] == "html"


@pytest.mark.django_db
def test_empty_html_import_does_not_require_trust(
    enterprise_data_fixture, enable_enterprise
):
    builder = enterprise_data_fixture.create_builder_application()
    page = enterprise_data_fixture.create_builder_page(builder=builder)
    enterprise_data_fixture.create_builder_element(
        HTMLElementType, page=page, html="  "
    )
    config = ImportExportConfig(include_permission_data=False)
    app_type = application_type_registry.get("builder")
    imported = app_type.import_serialized(
        builder.workspace, app_type.export_serialized(builder, config), config, {}
    )
    assert not imported.untrusted_content
    assert imported.import_report == []
